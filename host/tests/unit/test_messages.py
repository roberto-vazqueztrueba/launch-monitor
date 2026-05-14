import pytest
from host.communication.messages import (
    make_led_set,
    make_buzzer_beep,
    make_state_transition,
    make_heartbeat_ack,
    LED_IDS,
    LED_STATES,
    BUZZER_PATTERNS,
    SYSTEM_STATES,
    PROTOCOL_VERSION,
)


class TestMakeLedSet:
    def test_valid_message(self):
        msg = make_led_set("status", "on")
        assert msg["type"] == "led_set"
        assert msg["version"] == PROTOCOL_VERSION
        assert msg["payload"] == {"led_id": "status", "state": "on"}
        assert "timestamp_ms" in msg

    def test_all_valid_combinations(self):
        for led_id in LED_IDS:
            for state in LED_STATES:
                msg = make_led_set(led_id, state)
                assert msg["payload"]["led_id"] == led_id
                assert msg["payload"]["state"] == state

    def test_invalid_led_id_raises(self):
        with pytest.raises(ValueError, match="led_id"):
            make_led_set("unknown_led", "on")

    def test_invalid_state_raises(self):
        with pytest.raises(ValueError, match="state"):
            make_led_set("status", "purple")


class TestMakeBuzzerBeep:
    def test_valid_patterns(self):
        for pattern in BUZZER_PATTERNS:
            msg = make_buzzer_beep(pattern)
            assert msg["type"] == "buzzer_beep"
            assert msg["payload"]["pattern"] == pattern

    def test_invalid_pattern_raises(self):
        with pytest.raises(ValueError, match="pattern"):
            make_buzzer_beep("mystery")


class TestMakeStateTransition:
    def test_valid_states(self):
        for state in SYSTEM_STATES:
            msg = make_state_transition(state)
            assert msg["type"] == "state_transition"
            assert msg["payload"]["new_state"] == state

    def test_invalid_state_raises(self):
        with pytest.raises(ValueError, match="new_state"):
            make_state_transition("FLYING")


class TestMakeHeartbeatAck:
    def test_structure(self):
        msg = make_heartbeat_ack()
        assert msg["type"] == "heartbeat_ack"
        assert msg["payload"] == {}
        assert msg["version"] == PROTOCOL_VERSION
        assert isinstance(msg["timestamp_ms"], int)
