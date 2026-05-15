import json
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# SerialChannel.send tests (no real serial port needed)
# ---------------------------------------------------------------------------

class TestSerialChannelSend:
    def _make_channel(self):
        from host.communication.dispatcher import EventDispatcher
        from host.communication.channel import SerialChannel

        dispatcher = EventDispatcher()
        with patch("serial.Serial"):
            channel = SerialChannel(port="/dev/ttyACM0", dispatcher=dispatcher)
        return channel, dispatcher

    def test_send_raises_when_no_type(self):
        channel, _ = self._make_channel()
        with pytest.raises(ValueError, match="type"):
            channel.send({"payload": {}})

    def test_send_adds_version_and_timestamp_if_missing(self):
        from host.communication.channel import PROTOCOL_VERSION

        channel, _ = self._make_channel()
        mock_serial = MagicMock()
        mock_serial.is_open = True
        channel._serial = mock_serial

        channel.send({"type": "led_set", "payload": {"led_id": "status", "state": "on"}})

        assert mock_serial.write.called
        written_bytes: bytes = mock_serial.write.call_args[0][0]
        written_str = written_bytes.decode("utf-8").strip()
        msg = json.loads(written_str)
        assert msg["version"] == PROTOCOL_VERSION
        assert "timestamp_ms" in msg

    def test_send_drops_message_when_port_closed(self):
        channel, _ = self._make_channel()
        channel._serial = None  # port not open
        # Should not raise; message is silently dropped
        channel.send({"type": "heartbeat_ack", "payload": {}})

    def test_send_writes_newline_terminated_json(self):
        channel, _ = self._make_channel()
        mock_serial = MagicMock()
        mock_serial.is_open = True
        channel._serial = mock_serial

        channel.send({"type": "led_set", "payload": {"led_id": "mode", "state": "off"}})

        written: bytes = mock_serial.write.call_args[0][0]
        assert written.endswith(b"\n")
        json.loads(written.strip())  # must be valid JSON


# ---------------------------------------------------------------------------
# ReconnectPolicy tests
# ---------------------------------------------------------------------------

class TestReconnectPolicy:
    def test_defaults(self):
        from host.communication.reconnect import ReconnectPolicy
        p = ReconnectPolicy()
        assert p.interval_s == 0.5
        assert p.heartbeat_timeout_s == 5.0
        assert p.max_attempts == 0

    def test_custom_values(self):
        from host.communication.reconnect import ReconnectPolicy
        p = ReconnectPolicy(interval_s=1.0, heartbeat_timeout_s=10.0, max_attempts=3)
        assert p.interval_s == 1.0
        assert p.heartbeat_timeout_s == 10.0
        assert p.max_attempts == 3


# ---------------------------------------------------------------------------
# SerialChannel uses ReconnectPolicy
# ---------------------------------------------------------------------------

class TestSerialChannelPolicy:
    def _make_channel(self, policy=None):
        from host.communication.dispatcher import EventDispatcher
        from host.communication.channel import SerialChannel
        from host.communication.reconnect import ReconnectPolicy

        dispatcher = EventDispatcher()
        p = policy or ReconnectPolicy()
        with patch("serial.Serial"):
            channel = SerialChannel(port="/dev/pico", dispatcher=dispatcher, policy=p)
        return channel, p

    def test_default_policy_applied(self):
        from host.communication.reconnect import ReconnectPolicy
        channel, _ = self._make_channel()
        assert isinstance(channel._policy, ReconnectPolicy)
        assert channel._policy.interval_s == 0.5

    def test_custom_policy_stored(self):
        from host.communication.reconnect import ReconnectPolicy
        p = ReconnectPolicy(interval_s=2.0, max_attempts=5)
        channel, stored = self._make_channel(policy=p)
        assert channel._policy is stored
        assert channel._policy.max_attempts == 5

    def test_max_attempts_stops_open_port(self):
        """_open_port() must stop retrying after max_attempts failures."""
        from host.communication.dispatcher import EventDispatcher
        from host.communication.channel import SerialChannel
        from host.communication.reconnect import ReconnectPolicy
        import serial as _serial

        dispatcher = EventDispatcher()
        p = ReconnectPolicy(interval_s=0, max_attempts=2)
        channel = SerialChannel(port="/dev/pico", dispatcher=dispatcher, policy=p)
        channel._running = True

        with patch("serial.Serial", side_effect=_serial.SerialException("no device")):
            with patch("time.sleep"):
                channel._open_port()

        assert channel._running is False  # gave up after max_attempts
