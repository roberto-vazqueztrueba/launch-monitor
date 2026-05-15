# main.py — Pico entry point
#
# Minimal production bootstrap: sends heartbeats every 2s and echoes
# incoming commands.  Sensor drivers will be added in future features.

import utime
from communication.channel import UartChannel
from communication.event_queue import EventQueue
from communication import messages as m

HEARTBEAT_INTERVAL_MS = 2000
FLUSH_INTERVAL_MS = 10


def main() -> None:
    queue = EventQueue(maxlen=20)
    channel = UartChannel(queue=queue)

    # Wait for USB CDC to initialise
    utime.sleep_ms(2000)

    boot_ms = utime.ticks_ms()
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
            # Commands will be handled here as features are added
            pass

        utime.sleep_ms(FLUSH_INTERVAL_MS)


if __name__ == "__main__":
    main()
