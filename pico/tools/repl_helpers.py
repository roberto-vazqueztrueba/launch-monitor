# repl_helpers.py — Atajos para usar desde el REPL de MicroPython (Thonny o mpremote)
#
# Uso (desde el directorio raíz del Pico):
#   >>> exec(open("tools/repl_helpers.py").read())
#   >>> t0()           # envía t0_detected
#   >>> btn("BAD_SHOT") # envía input_button
#   >>> hb()           # envía heartbeat
#   >>> send_all()     # envía uno de cada tipo

import sys
if "communication" not in sys.path:
    sys.path.append("communication")

from channel import UartChannel
from event_queue import EventQueue
import messages as m

_q = EventQueue(maxlen=20)
_ch = UartChannel(queue=_q)
_LOG_SENT = False


def set_sent_logging(enabled: bool = False) -> None:
    """Activa o desactiva el log 'sent:' del helper REPL."""
    global _LOG_SENT
    _LOG_SENT = enabled


def _flush(msg: dict) -> None:
    _q.push(msg)
    _ch.flush()
    if _LOG_SENT:
        sys.stderr.write("sent: " + msg["type"] + "\n")


def t0(confidence: float = 0.95) -> None:
    """Envía t0_detected."""
    _flush(m.t0_detected(confidence))


def ambient(temp: float = 21.0, pressure: float = 1013.0, humidity: float = 55.0) -> None:
    """Envía sensor_ambient."""
    _flush(m.sensor_ambient(temp, pressure, humidity))


def imu(pitch: float = 0.0, roll: float = 0.0) -> None:
    """Envía sensor_imu."""
    _flush(m.sensor_imu(pitch, roll))


def btn(button_id: str = "BAD_SHOT", action: str = "press") -> None:
    """Envía input_button. button_id: BAD_SHOT | SAVE_SESSION | CALIBRATE | RESET_SESSION"""
    _flush(m.input_button(button_id, action))


def enc(action: str = "rotate", direction: str = "cw", steps: int = 1) -> None:
    """Envía input_encoder."""
    _flush(m.input_encoder(action, direction=direction, steps=steps))


def nfc(uid: str = "04:A3:2B:C1") -> None:
    """Envía input_nfc."""
    _flush(m.input_nfc(uid))


def hb() -> None:
    """Envía heartbeat."""
    import utime
    _flush(m.heartbeat(uptime_ms=utime.ticks_ms(), queue_size=_q.size()))


def send_all() -> None:
    """Envía uno de cada tipo de mensaje para verificación completa del canal."""
    t0()
    ambient()
    imu()
    btn()
    enc()
    nfc()
    hb()
