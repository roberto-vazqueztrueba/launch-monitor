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
