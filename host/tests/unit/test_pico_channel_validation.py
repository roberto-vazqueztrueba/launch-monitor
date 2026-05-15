"""Tests for pico/communication/channel.py read_command() envelope validation.

MicroPython-specific modules (ujson, utime, select) are mocked so the pico
channel module can be imported and exercised under standard CPython/pytest.
"""

import json
import sys
import types
import importlib
from unittest.mock import MagicMock
import pytest


# ---------------------------------------------------------------------------
# Bootstrap MicroPython stubs before importing the pico module
# ---------------------------------------------------------------------------

def _install_micropython_stubs():
    """Register lightweight stubs for MicroPython-only modules."""
    # ujson — delegate to stdlib json
    ujson_mod = types.ModuleType("ujson")
    ujson_mod.dumps = json.dumps
    ujson_mod.loads = json.loads
    sys.modules.setdefault("ujson", ujson_mod)

    # utime — not used by read_command, but imported at module level
    utime_mod = types.ModuleType("utime")
    utime_mod.ticks_ms = lambda: 0
    utime_mod.sleep_ms = lambda ms: None
    sys.modules.setdefault("utime", utime_mod)


_install_micropython_stubs()

# Add pico/ directory to path so the module can be imported directly
import pathlib
_PICO_COMM = str(pathlib.Path(__file__).parents[3] / "pico" / "communication")
if _PICO_COMM not in sys.path:
    sys.path.insert(0, _PICO_COMM)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_CMD = {
    "type": "led_set",
    "version": "1.0.0",
    "timestamp_ms": 1000,
    "payload": {"led_id": "status", "state": "on"},
}


def _make_channel_with_input(line: str):
    """Return a UartChannel whose stdin yields *line* byte-by-byte."""
    import select as _select_real

    # Import fresh each time to avoid state leakage from _rx_buf
    if "channel" in sys.modules:
        del sys.modules["channel"]
    import channel as pico_channel  # noqa: PLC0415

    # Patch select inside the module to return ready on each byte then stop
    chars = list(line)
    call_count = {"n": 0}

    def fake_select(rlist, wlist, xlist, timeout):
        i = call_count["n"]
        if i < len(chars):
            return (rlist, [], [])
        return ([], [], [])

    def fake_read(n):
        i = call_count["n"]
        call_count["n"] += 1
        if i < len(chars):
            return chars[i]
        return ""

    select_mod = types.ModuleType("select")
    select_mod.select = fake_select
    sys.modules["select"] = select_mod

    from event_queue import EventQueue
    q = EventQueue(maxlen=5)
    ch = pico_channel.UartChannel(queue=q)
    ch._queue = q
    # Patch sys.stdin.read inside the call
    real_stdin = sys.stdin
    mock_stdin = MagicMock()
    mock_stdin.read.side_effect = lambda n: fake_read(n)
    sys.stdin = mock_stdin

    result = ch.read_command()

    sys.stdin = real_stdin
    return result


def _parse(msg: dict):
    line = json.dumps(msg) + "\n"
    return _make_channel_with_input(line)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPicoChannelValidation:
    def test_valid_command_accepted(self):
        assert _parse(VALID_CMD) is not None

    def test_rejects_negative_timestamp(self):
        assert _parse({**VALID_CMD, "timestamp_ms": -1}) is None

    def test_rejects_float_timestamp(self):
        assert _parse({**VALID_CMD, "timestamp_ms": 1.5}) is None

    def test_rejects_string_timestamp(self):
        assert _parse({**VALID_CMD, "timestamp_ms": "now"}) is None

    def test_accepts_zero_timestamp(self):
        assert _parse({**VALID_CMD, "timestamp_ms": 0}) is not None

    def test_rejects_missing_timestamp(self):
        msg = {k: v for k, v in VALID_CMD.items() if k != "timestamp_ms"}
        assert _parse(msg) is None

    def test_rejects_empty_type(self):
        assert _parse({**VALID_CMD, "type": ""}) is None

    def test_rejects_list_payload(self):
        assert _parse({**VALID_CMD, "payload": [1, 2]}) is None

    def test_rejects_incompatible_major_version(self):
        assert _parse({**VALID_CMD, "version": "2.0.0"}) is None

    def test_rejects_non_semver_version(self):
        assert _parse({**VALID_CMD, "version": "1.0"}) is None

    def test_rejects_malformed_json(self):
        result = _make_channel_with_input("not json\n")
        assert result is None

    def test_oversized_frame_without_newline_is_discarded(self):
        """_rx_buf exceeding _MAX_FRAME bytes without a newline must be discarded."""
        if "channel" in sys.modules:
            del sys.modules["channel"]
        import channel as pico_channel

        from event_queue import EventQueue
        q = EventQueue(maxlen=5)
        ch = pico_channel.UartChannel(queue=q)

        # Fill _rx_buf beyond the limit without ever sending a newline
        oversized = "x" * (ch._MAX_FRAME + 1)
        chars = list(oversized)
        idx = {"i": 0}

        import types as _types
        select_mod = _types.ModuleType("select")
        select_mod.select = lambda r, w, x, t: (r, [], []) if idx["i"] < len(chars) else ([], [], [])
        sys.modules["select"] = select_mod

        from unittest.mock import MagicMock
        mock_stdin = MagicMock()
        def _read(n):
            i = idx["i"]
            idx["i"] += 1
            return chars[i] if i < len(chars) else ""
        mock_stdin.read.side_effect = _read

        real_stdin = sys.stdin
        sys.stdin = mock_stdin
        result = ch.read_command()
        sys.stdin = real_stdin

        assert result is None
        assert ch._rx_buf == b""  # buffer reset after discard


class TestPicoCommandPayloadValidation:
    """Per-command payload schema validation for known RPi→Pico command types."""

    # --- led_set ---

    def test_led_set_valid(self):
        msg = {**VALID_CMD, "type": "led_set", "payload": {"led_id": "status", "state": "on"}}
        assert _parse(msg) is not None

    def test_led_set_invalid_state(self):
        msg = {**VALID_CMD, "type": "led_set", "payload": {"led_id": "status", "state": "blink"}}
        assert _parse(msg) is None

    def test_led_set_missing_led_id(self):
        msg = {**VALID_CMD, "type": "led_set", "payload": {"state": "on"}}
        assert _parse(msg) is None

    def test_led_set_empty_led_id(self):
        msg = {**VALID_CMD, "type": "led_set", "payload": {"led_id": "", "state": "off"}}
        assert _parse(msg) is None

    # --- buzzer_beep ---

    def test_buzzer_beep_valid(self):
        msg = {**VALID_CMD, "type": "buzzer_beep", "payload": {"pattern": "short"}}
        assert _parse(msg) is not None

    def test_buzzer_beep_missing_pattern(self):
        msg = {**VALID_CMD, "type": "buzzer_beep", "payload": {}}
        assert _parse(msg) is None

    def test_buzzer_beep_empty_pattern(self):
        msg = {**VALID_CMD, "type": "buzzer_beep", "payload": {"pattern": ""}}
        assert _parse(msg) is None

    # --- state_transition ---

    def test_state_transition_valid(self):
        msg = {**VALID_CMD, "type": "state_transition", "payload": {"new_state": "ARMED"}}
        assert _parse(msg) is not None

    def test_state_transition_missing_new_state(self):
        msg = {**VALID_CMD, "type": "state_transition", "payload": {}}
        assert _parse(msg) is None

    def test_state_transition_empty_new_state(self):
        msg = {**VALID_CMD, "type": "state_transition", "payload": {"new_state": ""}}
        assert _parse(msg) is None

    # --- heartbeat_ack / heartbeat_request — empty payload allowed ---

    def test_heartbeat_ack_valid(self):
        msg = {**VALID_CMD, "type": "heartbeat_ack", "payload": {}}
        assert _parse(msg) is not None

    def test_heartbeat_request_valid(self):
        msg = {**VALID_CMD, "type": "heartbeat_request", "payload": {}}
        assert _parse(msg) is not None

    # --- unknown type passes through (forward-compatible) ---

    def test_unknown_type_passes_through(self):
        msg = {**VALID_CMD, "type": "future_cmd", "payload": {"x": 1}}
        assert _parse(msg) is not None
