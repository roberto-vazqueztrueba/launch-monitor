# messages.py — MicroPython message constructors for Pico → RPi events
#
# All functions return a dict ready to push onto the EventQueue.
# timestamp_ms is filled in by UartChannel.flush() if omitted here;
# you may also supply it explicitly for precise timing.

import utime
import config


def _msg(msg_type, payload, timestamp_ms=None):
    return {
        "type": msg_type,
        "version": config.PROTOCOL_VERSION,
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

    Raises:
        ValueError: If *confidence* is outside [0.0, 1.0].
    """
    if not (0.0 <= confidence <= 1.0):
        raise ValueError("confidence must be in [0.0, 1.0]")
    return _msg("t0_detected", {"confidence": confidence})


def sensor_ambient(temperature_c: float, pressure_hpa: float, humidity_pct: float) -> dict:
    """BME280 ambient reading.

    Raises:
        ValueError: If *pressure_hpa* <= 0 or *humidity_pct* outside [0.0, 100.0].
    """
    if pressure_hpa <= 0:
        raise ValueError("pressure_hpa must be > 0")
    if not (0.0 <= humidity_pct <= 100.0):
        raise ValueError("humidity_pct must be in [0.0, 100.0]")
    return _msg("sensor_ambient", {
        "temperature_c": temperature_c,
        "pressure_hpa": pressure_hpa,
        "humidity_pct": humidity_pct,
    })


def sensor_imu(pitch_deg: float, roll_deg: float) -> dict:
    """IMU inclination reading.

    Raises:
        ValueError: If *pitch_deg* or *roll_deg* are outside [-180.0, 180.0].
    """
    if not (-180.0 <= pitch_deg <= 180.0):
        raise ValueError("pitch_deg must be in [-180.0, 180.0]")
    if not (-180.0 <= roll_deg <= 180.0):
        raise ValueError("roll_deg must be in [-180.0, 180.0]")
    return _msg("sensor_imu", {"pitch_deg": pitch_deg, "roll_deg": roll_deg})


_BUTTON_IDS = ("BAD_SHOT", "SAVE_SESSION", "CALIBRATE", "RESET_SESSION")
_BUTTON_ACTIONS = ("press", "long_press")


def input_button(button_id: str, action: str) -> dict:
    """Physical button event.

    Args:
        button_id: ``BAD_SHOT`` | ``SAVE_SESSION`` | ``CALIBRATE`` | ``RESET_SESSION``
        action: ``press`` | ``long_press``

    Raises:
        ValueError: If *button_id* or *action* are not recognised values.
    """
    if button_id not in _BUTTON_IDS:
        raise ValueError("button_id must be one of: " + ", ".join(_BUTTON_IDS))
    if action not in _BUTTON_ACTIONS:
        raise ValueError("action must be one of: " + ", ".join(_BUTTON_ACTIONS))
    return _msg("input_button", {"button_id": button_id, "action": action})


_ENCODER_ACTIONS = ("rotate", "click", "long_press")
_ENCODER_DIRECTIONS = ("cw", "ccw")


def input_encoder(action, direction=None, steps=None):
    """Rotary encoder event.

    Args:
        action: ``rotate`` | ``click`` | ``long_press``
        direction: ``cw`` | ``ccw`` (only when action == ``rotate``)
        steps: Number of detents (only when action == ``rotate``)

    Raises:
        ValueError: If *action* or *direction* are not recognised values, or if
            *steps* is provided and is not a positive integer.
    """
    if action not in _ENCODER_ACTIONS:
        raise ValueError("action must be one of: " + ", ".join(_ENCODER_ACTIONS))
    if direction is not None and action != "rotate":
        raise ValueError("direction is only valid when action == 'rotate'")
    if steps is not None and action != "rotate":
        raise ValueError("steps is only valid when action == 'rotate'")
    if direction is not None and direction not in _ENCODER_DIRECTIONS:
        raise ValueError("direction must be one of: " + ", ".join(_ENCODER_DIRECTIONS))
    if steps is not None and (not isinstance(steps, int) or steps < 1):
        raise ValueError("steps must be a positive integer")
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

    Raises:
        ValueError: If *uid* is empty.
    """
    if not uid:
        raise ValueError("uid must not be empty")
    return _msg("input_nfc", {"uid": uid})


def heartbeat(uptime_ms: int, queue_size: int) -> dict:
    """Periodic aliveness signal.

    Args:
        uptime_ms: Milliseconds since Pico boot.
        queue_size: Current EventQueue depth.

    Raises:
        ValueError: If *uptime_ms* or *queue_size* are negative.
    """
    if uptime_ms < 0:
        raise ValueError("uptime_ms must be >= 0")
    if queue_size < 0:
        raise ValueError("queue_size must be >= 0")
    return _msg("heartbeat", {"uptime_ms": uptime_ms, "queue_size": queue_size})
