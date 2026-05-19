# UartChannel — MicroPython firmware for Raspberry Pi Pico
# Sends newline-delimited JSON messages over USB-serial (stdout / sys.stdout).
#
# MicroPython stdlib: ujson, sys, utime — no external dependencies.

import sys
import ujson
import utime
import config


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
        self._MAX_FRAME = config.MAX_FRAME_BYTES  # max bytes before discarding partial frame (RAM guard)

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
                msg["version"] = config.PROTOCOL_VERSION
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

        Reserved for urgent out-of-band transmissions that cannot wait for the
        next :meth:`flush` cycle — for example, a fatal error or assertion
        failure that must be reported before the firmware halts.  Under normal
        operation all outbound messages should go through the :class:`EventQueue`
        so that back-pressure and ordering are handled consistently.

        Args:
            msg: Dictionary with at least a ``type`` key.
        """
        if "version" not in msg:
            msg["version"] = config.PROTOCOL_VERSION
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
            # sys.stderr.write("WARN read_command: malformed JSON discarded: " + str(raw[:80]) + "\n")
            return None
        if not isinstance(msg, dict):
            # sys.stderr.write("WARN read_command: non-object JSON discarded\n")
            return None
        # Envelope field presence
        for key in ("type", "version", "timestamp_ms", "payload"):
            if key not in msg:
                # sys.stderr.write("WARN read_command: missing envelope field '" + key + "' — discarded\n")
                return None
        # Type checks
        if not isinstance(msg["type"], str) or not msg["type"]:
            # sys.stderr.write("WARN read_command: 'type' must be a non-empty string — discarded\n")
            return None
        if not isinstance(msg["payload"], dict):
            # sys.stderr.write("WARN read_command: 'payload' must be a JSON object — discarded\n")
            return None
        # timestamp_ms must be a non-negative integer
        ts = msg["timestamp_ms"]
        if isinstance(ts, bool) or not isinstance(ts, int) or ts < 0:
            # sys.stderr.write("WARN read_command: invalid 'timestamp_ms' — discarded\n")
            return None
        # Version: must be exactly "1.x.x" with numeric components
        version = msg["version"]
        if not isinstance(version, str):
            # sys.stderr.write("WARN read_command: 'version' must be a string — discarded\n")
            return None
        parts = version.split(".")
        if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
            # sys.stderr.write("WARN read_command: 'version' not semver — discarded: " + version + "\n")
            return None
        if parts[0] != "1":
            # sys.stderr.write("WARN read_command: incompatible MAJOR version — discarded: " + version + "\n")
            return None
        # Per-command payload schema validation for known RPi→Pico commands.
        # Unknown types pass through (forward-compatible — mirrors host dispatcher policy).
        cmd_type = msg["type"]
        payload = msg["payload"]
        if cmd_type == "led_set":
            if payload.get("led_id") not in ("status", "mode", "error"):
                # sys.stderr.write("WARN read_command: invalid led_set.led_id — discarded\n")
                return None
            if payload.get("state") not in ("on", "off", "blink_slow", "blink_fast"):
                # sys.stderr.write("WARN read_command: invalid led_set.state — discarded\n")
                return None
        elif cmd_type == "buzzer_beep":
            if payload.get("pattern") not in ("short", "long", "double", "error"):
                # sys.stderr.write("WARN read_command: invalid buzzer_beep.pattern — discarded\n")
                return None
        elif cmd_type == "state_transition":
            _VALID_STATES = (
                "BOOTING", "SELF_TEST", "WAITING_PROFILE", "WAITING_CLUB",
                "READY", "ARMED", "IMPACT_DETECTED", "PROCESSING",
                "RESULTS", "DIAGNOSTICS", "ERROR",
            )
            if payload.get("new_state") not in _VALID_STATES:
                # sys.stderr.write("WARN read_command: invalid state_transition.new_state — discarded\n")
                return None
        elif cmd_type in ("heartbeat_ack", "heartbeat_request"):
            if payload:
                # sys.stderr.write("WARN read_command: " + cmd_type + " payload must be empty — discarded\n")
                return None
        return msg
