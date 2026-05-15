# UartChannel — MicroPython firmware for Raspberry Pi Pico
# Sends newline-delimited JSON messages over USB-serial (stdout / sys.stdout).
#
# MicroPython stdlib: ujson, sys, utime — no external dependencies.

import sys
import ujson
import utime

_PROTOCOL_VERSION = "1.0.0"


class UartChannel:
    """Flush queued JSON messages to the USB-serial port.

    The Pico USB CDC port is exposed as ``sys.stdout`` in MicroPython;
    writing there sends data to the connected RPi host.

    Args:
        queue: :class:`EventQueue` instance that holds pending messages.
    """

    def __init__(self, queue) -> None:
        self._queue = queue
        self._rx_buf = b""  # persists across read_command() calls
        self._MAX_FRAME = 1024  # max bytes before discarding partial frame (RAM guard)

    def flush(self) -> None:
        """Drain the queue and write each message as a JSON line.

        Should be called regularly from the main loop (e.g. every 10 ms).
        """
        while not self._queue.empty():
            msg = self._queue.pop()
            if msg is None:
                break
            # Stamp version and timestamp if not already set
            if "version" not in msg:
                msg["version"] = _PROTOCOL_VERSION
            if "timestamp_ms" not in msg:
                msg["timestamp_ms"] = utime.ticks_ms()
            if "payload" not in msg:
                msg["payload"] = {}
            # print() adds \n and triggers a USB CDC packet flush in
            # MicroPython 1.28.  No inter-message sleep is needed: the USB
            # hardware handles framing and back-pressure, and each print()
            # call produces its own packet on the wire.
            # (The previous 50 ms sleep was added during early hardware
            # testing to work around frame-concatenation seen with
            # sys.stdout.write(); switching to print() eliminated the root
            # cause, so the sleep has been removed entirely.)
            print(ujson.dumps(msg))

    def send_now(self, msg):
        """Serialise and write *msg* immediately, bypassing the queue.

        Use sparingly — prefer :meth:`flush` with the queue for normal flow.

        Args:
            msg: Dictionary with at least a ``type`` key.
        """
        if "version" not in msg:
            msg["version"] = _PROTOCOL_VERSION
        if "timestamp_ms" not in msg:
            msg["timestamp_ms"] = utime.ticks_ms()
        if "payload" not in msg:
            msg["payload"] = {}
        print(ujson.dumps(msg))

    def read_command(self):
        """Try to read one command from the host (non-blocking).

        Returns:
            Parsed message dict if a complete JSON line was available,
            ``None`` otherwise. Malformed lines are discarded silently.
        """
        # Read one byte at a time so we never block on readline() waiting
        # for a newline that may arrive in a later USB packet.
        # _rx_buf persists across calls so partial frames are completed on
        # the next polling iteration rather than being discarded.
        import select
        while True:
            ready = select.select([sys.stdin], [], [], 0)[0]
            if not ready:
                return None
            ch = sys.stdin.read(1)
            if not ch:
                return None
            if ch == "\n":
                raw = self._rx_buf.strip()
                self._rx_buf = b""
                break
            self._rx_buf += ch.encode() if isinstance(ch, str) else ch
            if len(self._rx_buf) > self._MAX_FRAME:
                # Host sent too many bytes without a newline — discard and reset
                self._rx_buf = b""
                return None
        if not raw:
            return None
        try:
            msg = ujson.loads(raw)
        except ValueError:
            return None
        if not isinstance(msg, dict):
            return None
        # Envelope field presence
        for key in ("type", "version", "timestamp_ms", "payload"):
            if key not in msg:
                return None
        # Type checks
        if not isinstance(msg["type"], str) or not msg["type"]:
            return None
        if not isinstance(msg["payload"], dict):
            return None
        # timestamp_ms must be a non-negative integer
        ts = msg["timestamp_ms"]
        if isinstance(ts, bool) or not isinstance(ts, int) or ts < 0:
            return None
        # Version: must be exactly "1.x.x" with numeric components
        version = msg["version"]
        if not isinstance(version, str):
            return None
        parts = version.split(".")
        if len(parts) != 3:
            return None
        if parts[0] != "1":
            return None
        if not parts[1].isdigit() or not parts[2].isdigit():
            return None
        # Per-command payload schema validation for known RPi→Pico commands.
        # Unknown types pass through (forward-compatible — mirrors host dispatcher policy).
        cmd_type = msg["type"]
        payload = msg["payload"]
        if cmd_type == "led_set":
            if not isinstance(payload.get("led_id"), str) or not payload.get("led_id"):
                return None
            if payload.get("state") not in ("on", "off", "blink_slow", "blink_fast"):
                return None
        elif cmd_type == "buzzer_beep":
            if not isinstance(payload.get("pattern"), str) or not payload.get("pattern"):
                return None
        elif cmd_type == "state_transition":
            if not isinstance(payload.get("new_state"), str) or not payload.get("new_state"):
                return None
        return msg
