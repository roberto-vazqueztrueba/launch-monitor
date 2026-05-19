"""Tests for pico/communication/messages.py constructor validation.

MicroPython-specific modules (utime) are stubbed so this file runs under
standard CPython/pytest.
"""

import sys
import types
import pathlib
import pytest

# ---------------------------------------------------------------------------
# Bootstrap stubs
# ---------------------------------------------------------------------------

utime_mod = types.ModuleType("utime")
utime_mod.ticks_ms = lambda: 1000
sys.modules.setdefault("utime", utime_mod)

_PICO_ROOT = str(pathlib.Path(__file__).parents[3] / "pico")
if _PICO_ROOT not in sys.path:
    sys.path.insert(0, _PICO_ROOT)

_PICO_COMM = str(pathlib.Path(__file__).parents[3] / "pico" / "communication")
if _PICO_COMM not in sys.path:
    sys.path.insert(0, _PICO_COMM)

import messages as m  # noqa: E402 — must come after path setup


# ---------------------------------------------------------------------------
# t0_detected
# ---------------------------------------------------------------------------

class TestT0Detected:
    def test_valid_confidence(self):
        msg = m.t0_detected(0.85)
        assert msg["payload"]["confidence"] == 0.85

    def test_boundary_zero(self):
        assert m.t0_detected(0.0)["payload"]["confidence"] == 0.0

    def test_boundary_one(self):
        assert m.t0_detected(1.0)["payload"]["confidence"] == 1.0

    def test_above_range_raises(self):
        with pytest.raises(ValueError):
            m.t0_detected(1.01)

    def test_below_range_raises(self):
        with pytest.raises(ValueError):
            m.t0_detected(-0.1)


# ---------------------------------------------------------------------------
# sensor_ambient
# ---------------------------------------------------------------------------

class TestSensorAmbient:
    def test_valid(self):
        msg = m.sensor_ambient(22.5, 1013.25, 55.0)
        assert msg["payload"]["humidity_pct"] == 55.0

    def test_zero_pressure_raises(self):
        with pytest.raises(ValueError):
            m.sensor_ambient(20.0, 0.0, 50.0)

    def test_negative_pressure_raises(self):
        with pytest.raises(ValueError):
            m.sensor_ambient(20.0, -1.0, 50.0)

    def test_humidity_above_100_raises(self):
        with pytest.raises(ValueError):
            m.sensor_ambient(20.0, 1013.0, 100.1)

    def test_humidity_below_0_raises(self):
        with pytest.raises(ValueError):
            m.sensor_ambient(20.0, 1013.0, -0.1)

    def test_humidity_boundary_0(self):
        assert m.sensor_ambient(20.0, 1013.0, 0.0)

    def test_humidity_boundary_100(self):
        assert m.sensor_ambient(20.0, 1013.0, 100.0)


# ---------------------------------------------------------------------------
# sensor_imu
# ---------------------------------------------------------------------------

class TestSensorImu:
    def test_valid(self):
        msg = m.sensor_imu(-1.2, 0.5)
        assert msg["payload"]["pitch_deg"] == -1.2

    def test_pitch_out_of_range_raises(self):
        with pytest.raises(ValueError):
            m.sensor_imu(181.0, 0.0)

    def test_roll_out_of_range_raises(self):
        with pytest.raises(ValueError):
            m.sensor_imu(0.0, -181.0)

    def test_boundary_minus_180(self):
        assert m.sensor_imu(-180.0, -180.0)

    def test_boundary_plus_180(self):
        assert m.sensor_imu(180.0, 180.0)


# ---------------------------------------------------------------------------
# input_button
# ---------------------------------------------------------------------------

class TestInputButton:
    def test_valid(self):
        msg = m.input_button("CALIBRATE", "press")
        assert msg["payload"]["button_id"] == "CALIBRATE"

    def test_invalid_button_id_raises(self):
        with pytest.raises(ValueError):
            m.input_button("UNKNOWN", "press")

    def test_invalid_action_raises(self):
        with pytest.raises(ValueError):
            m.input_button("CALIBRATE", "double_click")


# ---------------------------------------------------------------------------
# input_encoder
# ---------------------------------------------------------------------------

class TestInputEncoder:
    def test_valid_rotate(self):
        msg = m.input_encoder("rotate", direction="cw", steps=2)
        assert msg["payload"]["steps"] == 2

    def test_valid_click(self):
        msg = m.input_encoder("click")
        assert msg["payload"]["action"] == "click"

    def test_invalid_action_raises(self):
        with pytest.raises(ValueError):
            m.input_encoder("spin")

    def test_invalid_direction_raises(self):
        with pytest.raises(ValueError):
            m.input_encoder("rotate", direction="left")

    def test_zero_steps_raises(self):
        with pytest.raises(ValueError):
            m.input_encoder("rotate", steps=0)

    def test_negative_steps_raises(self):
        with pytest.raises(ValueError):
            m.input_encoder("rotate", steps=-1)

    def test_float_steps_raises(self):
        with pytest.raises(ValueError):
            m.input_encoder("rotate", steps=1.5)

    def test_direction_on_click_raises(self):
        with pytest.raises(ValueError):
            m.input_encoder("click", direction="cw")

    def test_steps_on_click_raises(self):
        with pytest.raises(ValueError):
            m.input_encoder("click", steps=2)

    def test_direction_on_long_press_raises(self):
        with pytest.raises(ValueError):
            m.input_encoder("long_press", direction="ccw")


# ---------------------------------------------------------------------------
# input_nfc
# ---------------------------------------------------------------------------

class TestInputNfc:
    def test_valid(self):
        msg = m.input_nfc("DE:AD:BE:EF")
        assert msg["payload"]["uid"] == "DE:AD:BE:EF"

    def test_empty_uid_raises(self):
        with pytest.raises(ValueError):
            m.input_nfc("")


# ---------------------------------------------------------------------------
# heartbeat
# ---------------------------------------------------------------------------

class TestHeartbeat:
    def test_valid(self):
        msg = m.heartbeat(5000, 3)
        assert msg["payload"]["uptime_ms"] == 5000

    def test_negative_uptime_raises(self):
        with pytest.raises(ValueError):
            m.heartbeat(-1, 0)

    def test_negative_queue_size_raises(self):
        with pytest.raises(ValueError):
            m.heartbeat(0, -1)

    def test_zero_values_valid(self):
        assert m.heartbeat(0, 0)
