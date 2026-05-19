"""SerialChannel: non-blocking serial reader / writer for the RPi host."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import TYPE_CHECKING

import serial

from ..config import (
    BAUD_RATE,
    MAX_FRAME_BYTES,
    PROTOCOL_VERSION,
    SERIAL_PORT,
    SERIAL_TIMEOUT_S,
    PROCESS_START_S,
)

if TYPE_CHECKING:
    from .dispatcher import EventDispatcher
    from .reconnect import ReconnectPolicy

logger = logging.getLogger(__name__)


class SerialChannel:
    """Opens a serial port and reads newline-delimited JSON messages in a
    dedicated background thread. Dispatches parsed messages via
    :class:`EventDispatcher`. Automatically reconnects on USB disconnect.

    Args:
        port: Device path, e.g. ``/dev/pico`` (udev symlink) or ``/dev/ttyACM0``.
        dispatcher: :class:`EventDispatcher` instance to route messages.
        baudrate: Baud rate (conventional; USB CDC ignores this).
        timeout: Read timeout in seconds for the underlying serial port.
    """

    def __init__(
        self,
        dispatcher: "EventDispatcher",
        port: str = SERIAL_PORT,
        baudrate: int = BAUD_RATE,
        timeout: float = SERIAL_TIMEOUT_S,
        policy: "ReconnectPolicy | None" = None,
    ) -> None:
        from .reconnect import ReconnectPolicy as _RP
        self._port = port
        self._dispatcher = dispatcher
        self._baudrate = baudrate
        self._timeout = timeout
        self._policy = policy if policy is not None else _RP()
        self._serial: serial.Serial | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_rx_time: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background reader thread. Idempotent.

        Raises:
            RuntimeError: If a previous reader thread is still alive (i.e.
                :meth:`stop` was called but the thread did not exit in time).
                Call :meth:`stop` again and wait before retrying.
        """
        if self._running:
            return
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError(
                "Cannot start SerialChannel: previous reader thread is still alive. "
                "Call stop() and wait for it to exit before calling start() again."
            )
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="serial-reader")
        self._thread.start()
        logger.info("SerialChannel started on %s", self._port)

    def stop(self) -> None:
        """Stop the background reader thread and close the port.

        The port is closed before joining so that any ``readline()`` blocked
        inside ``_read_loop`` gets a ``SerialException`` immediately rather
        than waiting for the full read timeout.  ``_thread`` is only set to
        ``None`` after the join confirms the thread has exited; if the join
        times out the reference is kept so that a subsequent :meth:`start`
        call can detect that the old thread is still alive and refuse to
        spawn a second one.
        """
        self._running = False
        # Close the port first so readline() unblocks immediately.
        self._close_port()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=3.0)
            if not self._thread.is_alive():
                self._thread = None
            else:
                logger.warning(
                    "stop(): reader thread did not exit within 3 s — "
                    "leaving reference intact to prevent duplicate threads"
                )
        logger.info("SerialChannel stopped")

    def send(self, message: dict) -> None:
        """Serialise *message* as JSON and write it to the serial port.

        Prefer the factory functions in :mod:`communication.messages`
        (``make_led_set``, ``make_buzzer_beep``, etc.) over passing raw dicts.
        Those functions validate enum values and produce well-formed envelopes;
        raw dicts bypass all payload validation.

        The envelope fields ``version``, ``timestamp_ms``, and ``payload`` are
        filled in automatically when absent.  The port write is silently
        skipped when the port is not open.

        Args:
            message: Dictionary with at least a ``type`` key.  Use the factory
                functions in :mod:`communication.messages` to build valid
                outgoing commands.

        Raises:
            ValueError: If *message* does not contain a ``type`` key.
        """
        if "type" not in message:
            raise ValueError("message must contain a 'type' key")
        if "version" not in message:
            message = {**message, "version": PROTOCOL_VERSION}
        if "timestamp_ms" not in message:
            # Host uses ms since process start; Pico uses utime.ticks_ms() (boot-relative).
            # These clocks are independent — do not compare timestamps across directions.
            message = {**message, "timestamp_ms": int((time.monotonic() - PROCESS_START_S) * 1000)}
        if "payload" not in message:
            message = {**message, "payload": {}}

        line = json.dumps(message, separators=(",", ":")) + "\n"
        raw = line.encode("utf-8")

        with self._lock:
            if self._serial and self._serial.is_open:
                try:
                    self._serial.write(raw)
                except serial.SerialTimeoutException as exc:
                    logger.warning("Send timed out (device stalled?): %s — message dropped", exc)
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
        """Main loop: open port, read lines, reconnect on error.

        Reconnection attempts are counted globally across the lifetime of this
        call.  When :attr:`ReconnectPolicy.max_attempts` is non-zero the loop
        stops after that many failed open/read cycles and sets
        ``_running = False``.
        """
        reconnect_attempts = 0
        while self._running:
            try:
                self._open_port()
                if not self._running:
                    # _open_port() exhausted max_attempts and set _running=False
                    break
                reconnect_attempts = 0  # successful open resets the counter
                self._read_loop()
            except serial.SerialException as exc:
                reconnect_attempts += 1
                max_a = self._policy.max_attempts
                if max_a > 0 and reconnect_attempts >= max_a:
                    logger.error(
                        "Serial error after %d reconnect attempt(s): %s — giving up",
                        reconnect_attempts, exc,
                    )
                    self._running = False
                    break
                logger.warning(
                    "Serial error: %s — reconnecting in %.1f s (attempt %d)",
                    exc, self._policy.interval_s, reconnect_attempts,
                )
                self._close_port()
                time.sleep(self._policy.interval_s)

    def _open_port(self) -> None:
        attempts = 0
        while self._running:
            try:
                ser = serial.Serial(
                    port=self._port,
                    baudrate=self._baudrate,
                    timeout=self._timeout,
                    write_timeout=self._timeout,
                )
                # Do NOT pre-drain the buffer here: any readline() call would
                # either block for a full serial timeout when no bytes are
                # present, or discard a complete buffered event (e.g. a Pico
                # startup burst or an early t0_detected).  Partial frames are
                # already handled by _read_loop: readline() returns whatever is
                # available at timeout expiry, which then fails JSON parsing and
                # is discarded harmlessly.
                with self._lock:
                    self._serial = ser
                self._last_rx_time = time.monotonic()
                logger.info("Port %s opened", self._port)
                return
            except serial.SerialException as exc:
                attempts += 1
                max_a = self._policy.max_attempts
                if max_a > 0 and attempts >= max_a:
                    logger.error(
                        "Cannot open %s after %d attempt(s): %s — giving up",
                        self._port, attempts, exc,
                    )
                    self._running = False
                    return
                logger.debug("Cannot open %s: %s — retrying in %.1f s", self._port, exc, self._policy.interval_s)
                time.sleep(self._policy.interval_s)

    def _read_loop(self) -> None:
        """Read newline-delimited frames and dispatch them."""
        while self._running:
            with self._lock:
                ser = self._serial
            if ser is None or not ser.is_open:
                break

            # Check heartbeat timeout
            if time.monotonic() - self._last_rx_time > self._policy.heartbeat_timeout_s:
                logger.warning("No data from Pico for %.0f s — sending heartbeat_request", self._policy.heartbeat_timeout_s)
                self._last_rx_time = time.monotonic()
                try:
                    from .messages import make_heartbeat_request
                    self.send(make_heartbeat_request())
                except Exception as exc:
                    logger.debug("heartbeat_request send failed: %s", exc)

            try:
                raw = ser.readline(MAX_FRAME_BYTES)
            except serial.SerialException:
                raise

            if not raw:
                continue

            if len(raw) == MAX_FRAME_BYTES and not raw.endswith(b"\n"):
                logger.warning("Frame exceeded %d bytes without newline — discarded", MAX_FRAME_BYTES)
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
