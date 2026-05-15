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
        import select
        buf = b""
        while True:
            ready = select.select([sys.stdin], [], [], 0)[0]
            if not ready:
                # No byte available right now — return what we accumulated.
                # Incomplete frames are silently dropped; the host will
                # retransmit or the next call will start fresh.
                return None
            ch = sys.stdin.read(1)
            if not ch:
                return None
            if ch == "\n":
                break
            buf += ch.encode() if isinstance(ch, str) else ch
        raw = buf.strip()
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
