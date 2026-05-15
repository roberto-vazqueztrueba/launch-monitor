# messages.py — MicroPython message constructors for Pico → RPi events
#
# All functions return a dict ready to push onto the EventQueue.
# timestamp_ms is filled in by UartChannel.flush() if omitted here;
# you may also supply it explicitly for precise timing.

import utime

_VERSION = "1.0.0"


def _msg(msg_type, payload, timestamp_ms=None):
    return {
        "type": msg_type,
        "version": _VERSION,
        "timestamp_ms": timestamp_ms if timestamp_ms is not None else utime.ticks_ms(),
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# Pico → RPi event constructors
# ---------------------------------------------------------------------------

def t0_detected(confidence: float) -> dict:
    """Impact detected by microphone.

    Args:
        confidence: Detection confidence [0.0–1.0].
    """
    return _msg("t0_detected", {"confidence": confidence})


def sensor_ambient(temperature_c: float, pressure_hpa: float, humidity_pct: float) -> dict:
    """BME280 ambient reading."""
    return _msg("sensor_ambient", {
        "temperature_c": temperature_c,
        "pressure_hpa": pressure_hpa,
        "humidity_pct": humidity_pct,
    })


def sensor_imu(pitch_deg: float, roll_deg: float) -> dict:
    """IMU inclination reading."""
    return _msg("sensor_imu", {"pitch_deg": pitch_deg, "roll_deg": roll_deg})


def input_button(button_id: str, action: str) -> dict:
    """Physical button event.

    Args:
        button_id: ``BAD_SHOT`` | ``SAVE_SESSION`` | ``CALIBRATE`` | ``RESET_SESSION``
        action: ``press`` | ``long_press``
    """
    return _msg("input_button", {"button_id": button_id, "action": action})


def input_encoder(action, direction=None, steps=None):
    """Rotary encoder event.

    Args:
        action: ``rotate`` | ``click`` | ``long_press``
        direction: ``cw`` | ``ccw`` (only when action == ``rotate``)
        steps: Number of detents (only when action == ``rotate``)
    """
    payload = {"action": action}
    if direction is not None:
        payload["direction"] = direction
    if steps is not None:
        payload["steps"] = steps
    return _msg("input_encoder", payload)


def input_nfc(uid: str) -> dict:
    """NFC tag read.

    Args:
        uid: Tag UID in hex colon-separated format, e.g. ``04:A3:2B:C1``.
    """
    return _msg("input_nfc", {"uid": uid})


def heartbeat(uptime_ms: int, queue_size: int) -> dict:
    """Periodic aliveness signal.

    Args:
        uptime_ms: Milliseconds since Pico boot.
        queue_size: Current EventQueue depth.
    """
    return _msg("heartbeat", {"uptime_ms": uptime_ms, "queue_size": queue_size})
