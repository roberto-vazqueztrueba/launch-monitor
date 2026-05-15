# loopback.py — Test de loopback: el Pico envía mensajes y escucha sus propios ecos
#
# Útil para verificar que el canal bidireccional funciona sin necesitar la RPi.
# Ejecutar desde Thonny o mpremote como script independiente.
#
# Comportamiento:
#   1. Envía un burst de mensajes de prueba
#   2. Queda escuchando comandos entrantes durante 30 s
#   3. Imprime cada comando recibido en la consola

import sys
import utime
if "communication" not in sys.path:
    sys.path.append("communication")
from channel import UartChannel
from event_queue import EventQueue
import messages as m

LISTEN_S = 30


def main() -> None:
    q = EventQueue(maxlen=20)
    ch = UartChannel(queue=q)

    print("=== Pico loopback tool ===")
    print(f"Enviando burst y escuchando comandos durante {LISTEN_S} s...")

    # Burst de prueba
    q.push(m.t0_detected(0.99))
    q.push(m.sensor_ambient(22.5, 1012.0, 60.0))
    q.push(m.sensor_imu(-1.2, 0.5))
    q.push(m.input_button("CALIBRATE", "long_press"))
    q.push(m.input_encoder("rotate", direction="ccw", steps=3))
    q.push(m.input_nfc("DE:AD:BE:EF"))
    q.push(m.heartbeat(uptime_ms=utime.ticks_ms(), queue_size=q.size()))
    ch.flush()
    print("Burst enviado.")

    deadline = utime.ticks_add(utime.ticks_ms(), LISTEN_S * 1000)
    while utime.ticks_diff(deadline, utime.ticks_ms()) > 0:
        cmd = ch.read_command()
        if cmd:
            print("CMD recibido:", cmd["type"], cmd.get("payload", {}))
        utime.sleep_ms(20)

    print("=== Fin del loopback ===")


if __name__ == "__main__":
    main()
