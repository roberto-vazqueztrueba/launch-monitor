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
            # print() adds \n; sleep gives USB CDC time to transmit this
            # packet before the next message is queued in the same USB frame.
            # Only sleep if there are more messages pending.
            print(ujson.dumps(msg))
            if not self._queue.empty():
                utime.sleep_ms(50)

    def send_now(self, msg: dict) -> None:
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
        # MicroPython's sys.stdin has no readline in non-blocking mode by
        # default; use select to avoid blocking.
        import select
        ready = select.select([sys.stdin], [], [], 0)[0]
        if not ready:
            return None
        raw = sys.stdin.readline()
        if not raw:
            return None
        raw = raw.strip()
        if not raw:
            return None
        try:
            msg = ujson.loads(raw)
        except ValueError:
            return None
        if not isinstance(msg, dict):
            return None
        # Basic envelope validation
        for key in ("type", "version", "timestamp_ms", "payload"):
            if key not in msg:
                return None
        return msg
