# main.py — Pico entry point
#
# Minimal production bootstrap: sends heartbeats every 2s and handles the
# v1 command set. Hardware drivers (GPIO, PWM) will be wired in future
# features; stub handlers are silent until real peripherals are connected.

import utime
import sys
import config

if "communication" not in sys.path:
    sys.path.append("communication")
from channel import UartChannel
from event_queue import EventQueue
import messages as m

def main() -> None:
    queue = EventQueue(maxlen=config.EVENT_QUEUE_MAXLEN)
    channel = UartChannel(queue=queue)
    boot_ms = utime.ticks_ms()

    # Wait for USB CDC to initialise
    utime.sleep_ms(config.USB_STARTUP_DELAY_MS)

    last_heartbeat = utime.ticks_ms()

    while True:
        now = utime.ticks_ms()

        if utime.ticks_diff(now, last_heartbeat) >= config.HEARTBEAT_INTERVAL_MS:
            uptime = utime.ticks_diff(now, boot_ms)
            queue.push(m.heartbeat(uptime_ms=uptime, queue_size=queue.size()))
            last_heartbeat = now

        channel.flush()

        cmd = channel.read_command()
        if cmd is not None:
            cmd_type = cmd["type"]
            if cmd_type == "heartbeat_request":
                uptime = utime.ticks_diff(utime.ticks_ms(), boot_ms)
                queue.push(m.heartbeat(uptime_ms=uptime, queue_size=queue.size()))
            elif cmd_type == "led_set":
                pass  # TODO: drive GPIO when LED hardware is wired
            elif cmd_type == "buzzer_beep":
                pass  # TODO: drive PWM when buzzer hardware is wired
            elif cmd_type == "state_transition":
                pass  # TODO: update local state machine when implemented

        utime.sleep_ms(config.FLUSH_INTERVAL_MS)


if __name__ == "__main__":
    main()
