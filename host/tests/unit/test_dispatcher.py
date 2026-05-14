import json
import pytest
from host.communication.dispatcher import EventDispatcher


def _make_raw(msg: dict) -> bytes:
    return (json.dumps(msg) + "\n").encode("utf-8")


VALID_MSG = {
    "type": "t0_detected",
    "version": "1.0.0",
    "timestamp_ms": 1000,
    "payload": {"confidence": 0.9},
}


class TestEventDispatcher:
    def test_calls_registered_handler(self):
        dispatcher = EventDispatcher()
        received = []
        dispatcher.on("t0_detected")(lambda msg: received.append(msg))

        dispatcher.dispatch(_make_raw(VALID_MSG))

        assert len(received) == 1
        assert received[0]["payload"]["confidence"] == 0.9

    def test_register_method_alternative(self):
        dispatcher = EventDispatcher()
        received = []
        dispatcher.register("t0_detected", lambda msg: received.append(msg))
        dispatcher.dispatch(_make_raw(VALID_MSG))
        assert len(received) == 1

    def test_multiple_handlers_for_same_type(self):
        dispatcher = EventDispatcher()
        calls = []
        dispatcher.register("t0_detected", lambda m: calls.append("a"))
        dispatcher.register("t0_detected", lambda m: calls.append("b"))
        dispatcher.dispatch(_make_raw(VALID_MSG))
        assert calls == ["a", "b"]

    def test_discards_malformed_json(self):
        dispatcher = EventDispatcher()
        called = []
        dispatcher.register("t0_detected", lambda m: called.append(m))
        dispatcher.dispatch(b"not json\n")
        assert called == []

    def test_discards_missing_envelope_fields(self):
        dispatcher = EventDispatcher()
        called = []
        dispatcher.register("t0_detected", lambda m: called.append(m))
        incomplete = {"type": "t0_detected", "version": "1.0.0"}
        dispatcher.dispatch(_make_raw(incomplete))
        assert called == []

    def test_discards_incompatible_major_version(self):
        dispatcher = EventDispatcher()
        called = []
        dispatcher.register("t0_detected", lambda m: called.append(m))
        bad_version_msg = {**VALID_MSG, "version": "2.0.0"}
        dispatcher.dispatch(_make_raw(bad_version_msg))
        assert called == []

    def test_accepts_compatible_minor_version(self):
        dispatcher = EventDispatcher()
        received = []
        dispatcher.register("t0_detected", lambda m: received.append(m))
        minor_msg = {**VALID_MSG, "version": "1.3.7"}
        dispatcher.dispatch(_make_raw(minor_msg))
        assert len(received) == 1

    def test_ignores_unknown_message_type(self):
        """Forward-compatible: unknown types should not raise."""
        dispatcher = EventDispatcher()
        dispatcher.dispatch(_make_raw({**VALID_MSG, "type": "future_event"}))

    def test_does_not_raise_on_empty_raw(self):
        dispatcher = EventDispatcher()
        dispatcher.dispatch(b"")
        dispatcher.dispatch(b"\n")

    def test_handler_exception_does_not_crash_dispatcher(self):
        dispatcher = EventDispatcher()
        second_called = []

        def bad_handler(msg):
            raise RuntimeError("handler bug")

        dispatcher.register("t0_detected", bad_handler)
        dispatcher.register("t0_detected", lambda m: second_called.append(m))

        dispatcher.dispatch(_make_raw(VALID_MSG))
        # second handler still runs
        assert len(second_called) == 1

    def test_dispatch_with_sample_messages_file(self):
        import pathlib
        fixtures = pathlib.Path(__file__).parent.parent / "fixtures" / "sample_messages.json"
        msgs = json.loads(fixtures.read_text(encoding="utf-8"))

        dispatcher = EventDispatcher()
        received: dict[str, list] = {}

        for msg in msgs:
            msg_type = msg["type"]
            if msg_type not in received:
                received[msg_type] = []
                dispatcher.register(msg_type, lambda m, t=msg_type: received[t].append(m))

        for msg in msgs:
            dispatcher.dispatch(_make_raw(msg))

        assert len(received["t0_detected"]) == 1
        assert len(received["heartbeat"]) == 1
