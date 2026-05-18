# main.py — Pico entry point
#
# Minimal production bootstrap: sends heartbeats every 2s and handles the
# v1 command set. Hardware drivers (GPIO, PWM) will be wired in future
# features; for now each command is acknowledged via sys.stderr so the
# bidirectional channel can be verified end-to-end without real peripherals.

import utime
import sys

if "communication" not in sys.path:
    sys.path.append("communication")
from channel import UartChannel
from event_queue import EventQueue
import messages as m

HEARTBEAT_INTERVAL_MS = 2000
FLUSH_INTERVAL_MS = 10


def _log(msg):
    sys.stderr.write(msg + "\n")


def main() -> None:
    queue = EventQueue(maxlen=20)
    channel = UartChannel(queue=queue)
    boot_ms = utime.ticks_ms()

    # Wait for USB CDC to initialise
    utime.sleep_ms(2000)

    last_heartbeat = utime.ticks_ms()

    while True:
        now = utime.ticks_ms()

        if utime.ticks_diff(now, last_heartbeat) >= HEARTBEAT_INTERVAL_MS:
            uptime = utime.ticks_diff(now, boot_ms)
            queue.push(m.heartbeat(uptime_ms=uptime, queue_size=queue.size()))
            last_heartbeat = now

        channel.flush()

        cmd = channel.read_command()
        if cmd is not None:
            cmd_type = cmd["type"]
            payload = cmd["payload"]
            if cmd_type == "heartbeat_request":
                uptime = utime.ticks_diff(utime.ticks_ms(), boot_ms)
                queue.push(m.heartbeat(uptime_ms=uptime, queue_size=queue.size()))
            elif cmd_type == "led_set":
                # TODO: drive GPIO when LED hardware is wired
                _log("led_set {led_id}={state}".format(
                    led_id=payload.get("led_id", ""),
                    state=payload.get("state", ""),
                ))
            elif cmd_type == "buzzer_beep":
                # TODO: drive PWM when buzzer hardware is wired
                _log("buzzer_beep pattern={pattern}".format(
                    pattern=payload.get("pattern", ""),
                ))
            elif cmd_type == "state_transition":
                # TODO: update local state machine when implemented
                _log("state_transition new_state={new_state}".format(
                    new_state=payload.get("new_state", ""),
                ))

        utime.sleep_ms(FLUSH_INTERVAL_MS)


if __name__ == "__main__":
    main()
