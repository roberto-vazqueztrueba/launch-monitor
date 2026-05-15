"""SerialChannel: non-blocking serial reader / writer for the RPi host."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import TYPE_CHECKING

import serial

if TYPE_CHECKING:
    from .dispatcher import EventDispatcher

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "1.0.0"
_RECONNECT_INTERVAL_S = 0.5
_HEARTBEAT_TIMEOUT_S = 5.0


class SerialChannel:
    """Opens a serial port and reads newline-delimited JSON messages in a
    dedicated background thread. Dispatches parsed messages via
    :class:`EventDispatcher`. Automatically reconnects on USB disconnect.

    Args:
        port: Device path, e.g. ``/dev/ttyACM0``.
        dispatcher: :class:`EventDispatcher` instance to route messages.
        baudrate: Baud rate (conventional; USB CDC ignores this).
        timeout: Read timeout in seconds for the underlying serial port.
    """

    def __init__(
        self,
        dispatcher: "EventDispatcher",
        port: str = "/dev/pico",
        baudrate: int = 115200,
        timeout: float = 1.0,
    ) -> None:
        self._port = port
        self._dispatcher = dispatcher
        self._baudrate = baudrate
        self._timeout = timeout
        self._serial: serial.Serial | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_rx_time: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background reader thread. Idempotent."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="serial-reader")
        self._thread.start()
        logger.info("SerialChannel started on %s", self._port)

    def stop(self) -> None:
        """Stop the background reader thread and close the port."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        self._close_port()
        logger.info("SerialChannel stopped")

    def send(self, message: dict) -> None:
        """Serialise *message* as JSON and write it to the serial port.

        Adds ``version`` if missing. Silently drops the message when the port
        is not open.

        Args:
            message: Dictionary representing the full envelope.

        Raises:
            ValueError: If *message* does not contain a ``type`` key.
        """
        if "type" not in message:
            raise ValueError("message must contain a 'type' key")
        if "version" not in message:
            message = {**message, "version": PROTOCOL_VERSION}
        if "timestamp_ms" not in message:
            message = {**message, "timestamp_ms": int(time.monotonic() * 1000)}
        if "payload" not in message:
            message = {**message, "payload": {}}

        line = json.dumps(message, separators=(",", ":")) + "\n"
        raw = line.encode("utf-8")

        with self._lock:
            if self._serial and self._serial.is_open:
                try:
                    self._serial.write(raw)
                except serial.SerialException as exc:
                    logger.warning("Send failed: %s", exc)
            else:
                logger.debug("send() called but port is not open; message dropped")

    @property
    def is_connected(self) -> bool:
        """Return ``True`` when the serial port is currently open."""
        with self._lock:
            return self._serial is not None and self._serial.is_open

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main loop: open port, read lines, reconnect on error."""
        while self._running:
            try:
                self._open_port()
                self._read_loop()
            except serial.SerialException as exc:
                logger.warning("Serial error: %s — reconnecting in %.1f s", exc, _RECONNECT_INTERVAL_S)
                self._close_port()
                time.sleep(_RECONNECT_INTERVAL_S)

    def _open_port(self) -> None:
        while self._running:
            try:
                ser = serial.Serial(
                    port=self._port,
                    baudrate=self._baudrate,
                    timeout=self._timeout,
                )
                # Discard at most one partial frame that may be in-flight when
                # the port opens. Subsequent messages will be complete lines.
                ser.reset_input_buffer()
                with self._lock:
                    self._serial = ser
                self._last_rx_time = time.monotonic()
                logger.info("Port %s opened", self._port)
                return
            except serial.SerialException as exc:
                logger.debug("Cannot open %s: %s — retrying in %.1f s", self._port, exc, _RECONNECT_INTERVAL_S)
                time.sleep(_RECONNECT_INTERVAL_S)

    def _read_loop(self) -> None:
        """Read newline-delimited frames and dispatch them."""
        while self._running:
            with self._lock:
                ser = self._serial
            if ser is None or not ser.is_open:
                break

            # Check heartbeat timeout
            if time.monotonic() - self._last_rx_time > _HEARTBEAT_TIMEOUT_S:
                logger.warning("No data from Pico for %.0f s — sending heartbeat_request", _HEARTBEAT_TIMEOUT_S)
                self._last_rx_time = time.monotonic()
                try:
                    self.send({"type": "heartbeat_request", "payload": {}})
                except Exception:
                    pass

            try:
                raw = ser.readline()
            except serial.SerialException:
                raise

            if not raw:
                continue

            self._last_rx_time = time.monotonic()
            self._dispatcher.dispatch(raw)

    def _close_port(self) -> None:
        with self._lock:
            if self._serial is not None:
                try:
                    self._serial.close()
                except Exception:
                    pass
                self._serial = None
