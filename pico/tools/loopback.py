# loopback.py — Pico channel smoke-test tool
#
# Sends a burst of v1 event messages over USB CDC and then listens for
# incoming host commands for 30 seconds, printing each one to sys.stderr.
#
# NOTE: despite the name, this is NOT a true loopback — the script does not
# wire its own stdout back into stdin.  A true loopback would require either
# a hardware TX→RX short or a host process echoing bytes, neither of which is
# practical over USB CDC in MicroPython.
#
# What it DOES verify:
#   • UartChannel.flush() encodes and writes all queued messages correctly
#   • UartChannel.read_command() can parse incoming commands from the host
#   • The full v1 message catalogue is exercisable from the Pico side
#
# To test the receive side, run a host script that sends commands after the
# burst (e.g. host/tools/monitor.py or the REPL helpers) while this script
# is running.
#
# To view output: mpremote run pico/tools/loopback.py
# Diagnostic messages go to sys.stderr; JSON protocol frames go to stdout.

import sys
import utime
if "communication" not in sys.path:
    sys.path.append("communication")
from channel import UartChannel
from event_queue import EventQueue
import messages as m

LISTEN_S = 30


def _log(msg):
    sys.stderr.write(msg + "\n")


def main() -> None:
    q = EventQueue(maxlen=20)
    ch = UartChannel(queue=q)

    _log("=== Pico loopback tool ===")
    _log("Enviando burst y escuchando comandos durante {} s...".format(LISTEN_S))

    # Burst de prueba
    q.push(m.t0_detected(0.99))
    q.push(m.sensor_ambient(22.5, 1012.0, 60.0))
    q.push(m.sensor_imu(-1.2, 0.5))
    q.push(m.input_button("CALIBRATE", "long_press"))
    q.push(m.input_encoder("rotate", direction="ccw", steps=3))
    q.push(m.input_nfc("DE:AD:BE:EF"))
    q.push(m.heartbeat(uptime_ms=utime.ticks_ms(), queue_size=q.size()))
    ch.flush()
    _log("Burst enviado.")

    deadline = utime.ticks_add(utime.ticks_ms(), LISTEN_S * 1000)
    while utime.ticks_diff(deadline, utime.ticks_ms()) > 0:
        cmd = ch.read_command()
        if cmd:
            _log("CMD recibido: {} {}".format(cmd["type"], cmd.get("payload", {})))
        utime.sleep_ms(20)

    _log("=== Fin del loopback ===")


if __name__ == "__main__":
    main()
