# verify_channel.py — Manual verification script for Pico firmware
#
# Flash this file onto the Pico (copy to flash root as main.py or run from REPL).
# It sends a burst of test messages and then enters a heartbeat loop.
# On the RPi, run: screen /dev/pico 115200  (or /dev/ttyACMx if udev rule not set)
#
# Expected output (JSON lines):
#   {"type":"t0_detected","version":"1.0.0","timestamp_ms":...,"payload":{"confidence":0.95}}
#   {"type":"sensor_ambient",...}
#   {"type":"heartbeat",...}  (every 2 seconds)

import utime
import sys
if "communication" not in sys.path:
    sys.path.append("communication")
from channel import UartChannel
from event_queue import EventQueue
import messages as m

HEARTBEAT_INTERVAL_MS = 2000
FLUSH_INTERVAL_MS = 10


def main():
    queue = EventQueue(maxlen=20)
    channel = UartChannel(queue=queue)

    boot_ms = utime.ticks_ms()

    # Wait for USB CDC to fully initialise before sending the burst.
    # Without this, the first messages may be dropped or concatenated.
    utime.sleep_ms(2000)

    # --- Burst of test events on startup ---
    queue.push(m.t0_detected(confidence=0.95))
    queue.push(m.sensor_ambient(temperature_c=22.0, pressure_hpa=1012.5, humidity_pct=55.0))
    queue.push(m.sensor_imu(pitch_deg=0.0, roll_deg=0.0))
    queue.push(m.input_button("BAD_SHOT", "press"))
    queue.push(m.input_encoder("rotate", direction="cw", steps=3))
    queue.push(m.input_nfc("04:A3:2B:C1"))
    channel.flush()

    last_heartbeat = utime.ticks_ms()

    # --- Main loop: heartbeat + command echo ---
    while True:
        now = utime.ticks_ms()

        # Send heartbeat periodically
        if utime.ticks_diff(now, last_heartbeat) >= HEARTBEAT_INTERVAL_MS:
            uptime = utime.ticks_diff(now, boot_ms)
            queue.push(m.heartbeat(uptime_ms=uptime, queue_size=queue.size()))
            last_heartbeat = now

        channel.flush()

        # Read and echo any incoming command
        cmd = channel.read_command()
        if cmd is not None:
            msg_type = cmd.get("type", "")
            # Handle heartbeat_ack silently
            if msg_type == "heartbeat_ack":
                pass
            # Handle LED command — would set GPIO here
            elif msg_type == "led_set":
                led_id = cmd["payload"].get("led_id", "")
                state = cmd["payload"].get("state", "")
                sys.stdout.write(
                    '{"type":"debug","version":"1.0.0","timestamp_ms":%d,'
                    '"payload":{"echo":"led_set %s=%s"}}\n' % (utime.ticks_ms(), led_id, state)
                )
            # Handle buzzer command
            elif msg_type == "buzzer_beep":
                pattern = cmd["payload"].get("pattern", "")
                sys.stdout.write(
                    '{"type":"debug","version":"1.0.0","timestamp_ms":%d,'
                    '"payload":{"echo":"buzzer_beep %s"}}\n' % (utime.ticks_ms(), pattern)
                )

        utime.sleep_ms(FLUSH_INTERVAL_MS)


if __name__ == "__main__":
    main()
