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

    def test_send_handles_write_timeout(self):
        import serial as _serial
        channel, _ = self._make_channel()
        mock_serial = MagicMock()
        mock_serial.is_open = True
        mock_serial.write.side_effect = _serial.SerialTimeoutException("write timeout")
        channel._serial = mock_serial
        # Must not raise; timeout is logged and message dropped
        channel.send({"type": "heartbeat_ack", "payload": {}})


class TestSerialChannelStop:
    def test_stop_from_reader_thread_does_not_join_self(self):
        """stop() called from the reader thread must skip join() to avoid RuntimeError."""
        import threading
        from host.communication.dispatcher import EventDispatcher
        from host.communication.channel import SerialChannel

        dispatcher = EventDispatcher()
        with patch("serial.Serial"):
            channel = SerialChannel(port="/dev/pico", dispatcher=dispatcher)

        # Simulate being called from the reader thread
        fake_thread = MagicMock(spec=threading.Thread)
        channel._thread = fake_thread
        channel._running = True

        with patch("threading.current_thread", return_value=fake_thread):
            channel.stop()

        fake_thread.join.assert_not_called()


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


# ---------------------------------------------------------------------------
# Frame size limit tests
# ---------------------------------------------------------------------------

class TestFrameSizeLimit:
    def _make_channel(self):
        from host.communication.dispatcher import EventDispatcher
        from host.communication.channel import SerialChannel
        dispatcher = EventDispatcher()
        with patch("serial.Serial"):
            channel = SerialChannel(port="/dev/pico", dispatcher=dispatcher)
        return channel, dispatcher

    def test_oversized_frame_without_newline_is_discarded(self):
        """_read_loop() must not dispatch a frame that fills readline()'s buffer (no newline)."""
        from host.communication.channel import _MAX_FRAME_BYTES
        channel, dispatcher = self._make_channel()
        received = []
        dispatcher.register("t0_detected", lambda m: received.append(m))

        mock_serial = MagicMock()
        mock_serial.is_open = True

        # First call: oversized frame (no trailing newline — fills the buffer exactly)
        # Second call: stop the loop
        oversized = b"x" * _MAX_FRAME_BYTES
        call_n = {"n": 0}
        def readline_side_effect(size):
            call_n["n"] += 1
            if call_n["n"] == 1:
                return oversized
            channel._running = False
            return b""
        mock_serial.readline.side_effect = readline_side_effect

        channel._serial = mock_serial
        channel._running = True
        channel._last_rx_time = 0.0

        with patch("time.monotonic", return_value=0.0):
            channel._read_loop()

        assert received == [], "dispatch must not be called for oversized frame"

    def test_readline_called_with_max_frame_size(self):
        """readline() must be called with _MAX_FRAME_BYTES as the size argument."""
        from host.communication.channel import _MAX_FRAME_BYTES, SerialChannel
        from host.communication.dispatcher import EventDispatcher

        dispatcher = EventDispatcher()
        channel = SerialChannel(port="/dev/pico", dispatcher=dispatcher)
        channel._running = True
        channel._last_rx_time = 0.0

        mock_serial = MagicMock()
        mock_serial.is_open = True
        # Return empty bytes to exit the loop after one readline call
        mock_serial.readline.return_value = b""
        channel._serial = mock_serial

        import time
        with patch.object(channel, "_running", True):
            # Patch _running to stop after one iteration
            original_readline = mock_serial.readline
            call_count = {"n": 0}
            def one_shot(*args, **kwargs):
                call_count["n"] += 1
                channel._running = False
                return b""
            mock_serial.readline.side_effect = one_shot

            with patch("time.monotonic", return_value=0.0):
                try:
                    channel._read_loop()
                except Exception:
                    pass

        mock_serial.readline.assert_called_with(_MAX_FRAME_BYTES)


# ---------------------------------------------------------------------------
# Heartbeat watchdog tests
# ---------------------------------------------------------------------------

class TestHeartbeatWatchdog:
    """_read_loop() must send heartbeat_request when silent longer than heartbeat_timeout_s."""

    def _make_channel(self, heartbeat_timeout_s=5.0):
        from host.communication.dispatcher import EventDispatcher
        from host.communication.channel import SerialChannel
        from host.communication.reconnect import ReconnectPolicy

        dispatcher = EventDispatcher()
        policy = ReconnectPolicy(heartbeat_timeout_s=heartbeat_timeout_s)
        with patch("serial.Serial"):
            channel = SerialChannel(port="/dev/pico", dispatcher=dispatcher, policy=policy)
        return channel

    def test_watchdog_sends_heartbeat_request_after_timeout(self):
        """When no bytes arrive for > heartbeat_timeout_s, one heartbeat_request is sent."""
        import json as _json
        from host.communication.channel import _MAX_FRAME_BYTES

        channel = self._make_channel(heartbeat_timeout_s=5.0)

        mock_serial = MagicMock()
        mock_serial.is_open = True

        # readline returns empty (no data), simulating silence
        call_count = {"n": 0}
        def one_shot(*args, **kwargs):
            call_count["n"] += 1
            channel._running = False
            return b""
        mock_serial.readline.side_effect = one_shot

        channel._serial = mock_serial
        channel._running = True

        # Set last_rx_time far in the past so watchdog fires immediately
        t_now = 1000.0
        channel._last_rx_time = t_now - 10.0  # 10 s ago — beyond 5 s timeout

        with patch("time.monotonic", return_value=t_now):
            channel._read_loop()

        assert mock_serial.write.called
        written = mock_serial.write.call_args[0][0].decode("utf-8").strip()
        msg = _json.loads(written)
        assert msg["type"] == "heartbeat_request"

    def test_watchdog_does_not_fire_before_timeout(self):
        """No heartbeat_request sent when last_rx_time is within the timeout window."""
        channel = self._make_channel(heartbeat_timeout_s=5.0)

        mock_serial = MagicMock()
        mock_serial.is_open = True

        call_count = {"n": 0}
        def one_shot(*args, **kwargs):
            call_count["n"] += 1
            channel._running = False
            return b""
        mock_serial.readline.side_effect = one_shot

        channel._serial = mock_serial
        channel._running = True

        t_now = 1000.0
        channel._last_rx_time = t_now - 2.0  # only 2 s ago — within 5 s timeout

        with patch("time.monotonic", return_value=t_now):
            channel._read_loop()

        # write() must not have been called for a heartbeat_request
        for call in mock_serial.write.call_args_list:
            written = call[0][0].decode("utf-8").strip()
            import json as _json
            msg = _json.loads(written)
            assert msg["type"] != "heartbeat_request"

    def test_watchdog_resets_after_firing(self):
        """After sending heartbeat_request, _last_rx_time is updated so it does not spam."""
        import json as _json

        channel = self._make_channel(heartbeat_timeout_s=5.0)

        mock_serial = MagicMock()
        mock_serial.is_open = True

        iterations = {"n": 0}
        def two_shots(*args, **kwargs):
            iterations["n"] += 1
            if iterations["n"] >= 2:
                channel._running = False
            return b""
        mock_serial.readline.side_effect = two_shots

        channel._serial = mock_serial
        channel._running = True

        t_now = 1000.0
        channel._last_rx_time = t_now - 10.0

        with patch("time.monotonic", return_value=t_now):
            channel._read_loop()

        # heartbeat_request should appear exactly once
        hb_writes = [
            call for call in mock_serial.write.call_args_list
            if _json.loads(call[0][0].decode().strip())["type"] == "heartbeat_request"
        ]
        assert len(hb_writes) == 1


# ---------------------------------------------------------------------------
# Reconnect behaviour tests
# ---------------------------------------------------------------------------

class TestReconnectBehavior:
    """SerialChannel._open_port() reconnect retry logic."""

    def test_reconnects_after_transient_failure(self):
        """_open_port() opens port on second attempt when first raises SerialException."""
        import serial as _serial
        from host.communication.dispatcher import EventDispatcher
        from host.communication.channel import SerialChannel
        from host.communication.reconnect import ReconnectPolicy

        dispatcher = EventDispatcher()
        policy = ReconnectPolicy(interval_s=0, max_attempts=0)
        channel = SerialChannel(port="/dev/pico", dispatcher=dispatcher, policy=policy)
        channel._running = True

        mock_port = MagicMock()
        mock_port.is_open = True
        side_effects = [_serial.SerialException("busy"), mock_port]

        with patch("serial.Serial", side_effect=side_effects):
            with patch("time.sleep"):
                # Stop after second attempt by patching _running
                original = SerialChannel._open_port
                call_count = {"n": 0}
                def patched(self):
                    call_count["n"] += 1
                    if call_count["n"] > 2:
                        self._running = False
                    original(self)
                with patch.object(SerialChannel, "_open_port", patched):
                    channel._open_port()

        assert channel._serial is not None or not channel._running

    def test_max_attempts_zero_means_unlimited(self):
        """max_attempts=0 must never set _running=False regardless of failure count."""
        import serial as _serial
        from host.communication.dispatcher import EventDispatcher
        from host.communication.channel import SerialChannel
        from host.communication.reconnect import ReconnectPolicy

        dispatcher = EventDispatcher()
        policy = ReconnectPolicy(interval_s=0, max_attempts=0)
        channel = SerialChannel(port="/dev/pico", dispatcher=dispatcher, policy=policy)
        channel._running = True

        attempt = {"n": 0}
        def fail_then_succeed(*args, **kwargs):
            attempt["n"] += 1
            if attempt["n"] < 5:
                raise _serial.SerialException("not yet")
            channel._running = False  # stop loop externally
            raise _serial.SerialException("stopped")

        with patch("serial.Serial", side_effect=fail_then_succeed):
            with patch("time.sleep"):
                channel._open_port()

        # _running was set False externally, not by max_attempts logic
        assert attempt["n"] >= 5
