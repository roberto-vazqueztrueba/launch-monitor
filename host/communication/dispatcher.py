"""EventDispatcher: routes decoded serial messages to registered handlers."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Callable

logger = logging.getLogger(__name__)

_REQUIRED_ENVELOPE_KEYS = {"type", "version", "timestamp_ms", "payload"}
_PROTOCOL_MAJOR = "1"

# ---------------------------------------------------------------------------
# Known payload validation rules for Pico → RPi event types.
# Each entry maps a message type to a list of (field, expected_python_type)
# tuples that must all be present and correctly typed for the message to be
# dispatched.  Unknown types pass through unchecked (forward-compatibility).
# ---------------------------------------------------------------------------
_NUMERIC = (int, float)

_BUTTON_IDS = frozenset({"BAD_SHOT", "SAVE_SESSION", "CALIBRATE", "RESET_SESSION"})
_BUTTON_ACTIONS = frozenset({"press", "long_press"})
_ENCODER_ACTIONS = frozenset({"rotate", "click", "long_press"})
_ENCODER_DIRECTIONS = frozenset({"cw", "ccw"})

# (field_name, required_type_or_types) — None means "any non-None value"
_PAYLOAD_REQUIRED_FIELDS: dict[str, list[tuple[str, type | tuple]]] = {
    "t0_detected": [("confidence", _NUMERIC)],
    "sensor_ambient": [
        ("temperature_c", _NUMERIC),
        ("pressure_hpa", _NUMERIC),
        ("humidity_pct", _NUMERIC),
    ],
    "sensor_imu": [
        ("pitch_deg", _NUMERIC),
        ("roll_deg", _NUMERIC),
    ],
    "input_button": [
        ("button_id", str),
        ("action", str),
    ],
    "input_encoder": [
        ("action", str),
    ],
    "input_nfc": [("uid", str)],
    "heartbeat": [
        ("uptime_ms", int),
        ("queue_size", int),
    ],
}


def _validate_known_payload(msg_type: str, payload: dict) -> str | None:
    """Return an error string if *payload* fails validation, else None."""
    rules = _PAYLOAD_REQUIRED_FIELDS.get(msg_type)
    if rules is None:
        return None  # unknown type — pass through

    for field, expected in rules:
        if field not in payload:
            return f"payload missing required field '{field}'"
        value = payload[field]
        # bool is a subclass of int in Python — reject it for numeric fields
        if isinstance(value, bool):
            return f"payload field '{field}' must be {expected}, got bool"
        if not isinstance(value, expected):
            return f"payload field '{field}' must be {expected}, got {type(value).__name__}"

    # Extra enum / range checks for specific types
    if msg_type == "t0_detected":
        c = payload["confidence"]
        if not (0.0 <= c <= 1.0):
            return f"payload 'confidence' must be in [0.0, 1.0], got {c}"

    elif msg_type == "input_button":
        if payload["button_id"] not in _BUTTON_IDS:
            return f"payload 'button_id' must be one of {sorted(_BUTTON_IDS)}, got {payload['button_id']!r}"
        if payload["action"] not in _BUTTON_ACTIONS:
            return f"payload 'action' must be one of {sorted(_BUTTON_ACTIONS)}, got {payload['action']!r}"

    elif msg_type == "input_encoder":
        if payload["action"] not in _ENCODER_ACTIONS:
            return f"payload 'action' must be one of {sorted(_ENCODER_ACTIONS)}, got {payload['action']!r}"
        if payload["action"] == "rotate":
            if "direction" not in payload:
                return "payload missing required field 'direction' for rotate action"
            if payload["direction"] not in _ENCODER_DIRECTIONS:
                return f"payload 'direction' must be one of {sorted(_ENCODER_DIRECTIONS)}, got {payload['direction']!r}"
            if "steps" not in payload:
                return "payload missing required field 'steps' for rotate action"
            steps = payload["steps"]
            if isinstance(steps, bool) or not isinstance(steps, int):
                return f"payload 'steps' must be int, got {type(steps).__name__}"

    elif msg_type == "heartbeat":
        for field in ("uptime_ms", "queue_size"):
            if payload[field] < 0:
                return f"payload '{field}' must be >= 0, got {payload[field]}"

    return None

MessageHandler = Callable[[dict], None]


class EventDispatcher:
    """Route newline-delimited JSON messages to typed event handlers.

    Usage::

        dispatcher = EventDispatcher()

        @dispatcher.on("t0_detected")
        def handle_t0(msg):
            print(msg["payload"]["confidence"])

        dispatcher.dispatch(raw_bytes)
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[MessageHandler]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def on(self, message_type: str) -> Callable[[MessageHandler], MessageHandler]:
        """Decorator — register *func* as a handler for *message_type*.

        Args:
            message_type: The ``type`` field value to listen for, e.g.
                ``"t0_detected"``.

        Returns:
            The original function unchanged (transparent decorator).
        """
        def decorator(func: MessageHandler) -> MessageHandler:
            self._handlers[message_type].append(func)
            return func
        return decorator

    def register(self, message_type: str, handler: MessageHandler) -> None:
        """Register *handler* programmatically (alternative to decorator).

        Args:
            message_type: The ``type`` field value to listen for.
            handler: Callable that accepts a single decoded message dict.
        """
        self._handlers[message_type].append(handler)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, raw: bytes) -> None:
        """Parse *raw* as UTF-8 JSON and call matching handlers.

        Malformed or invalid frames are logged and silently discarded.

        Args:
            raw: A single newline-delimited JSON frame (bytes).
        """
        stripped = raw.strip()
        if not stripped:
            return

        try:
            msg = json.loads(stripped.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("Malformed message discarded: %s | raw=%r", exc, raw[:120])
            return

        if not isinstance(msg, dict):
            logger.warning("Message is not a JSON object — discarded: %r", msg)
            return

        missing = _REQUIRED_ENVELOPE_KEYS - msg.keys()
        if missing:
            logger.warning("Message missing required fields %s — discarded: %r", missing, msg)
            return

        # Validate field types to enforce data-model invariants
        msg_type = msg["type"]
        if not isinstance(msg_type, str) or not msg_type:
            logger.warning("Field 'type' must be a non-empty string — discarded: %r", msg_type)
            return

        version = msg["version"]
        if not isinstance(version, str):
            logger.warning("Field 'version' must be a string — discarded: %r", version)
            return
        parts = version.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            logger.warning(
                "Field 'version' must be a MAJOR.MINOR.PATCH numeric string — discarded: %r",
                version,
            )
            return

        ts = msg["timestamp_ms"]
        if isinstance(ts, bool) or not isinstance(ts, int) or ts < 0:
            logger.warning("Field 'timestamp_ms' must be a non-negative integer — discarded: %r", ts)
            return

        payload = msg["payload"]
        if not isinstance(payload, dict):
            logger.warning("Field 'payload' must be a JSON object — discarded: %r", payload)
            return

        # Validate payload structure for known event types
        payload_error = _validate_known_payload(msg_type, payload)
        if payload_error is not None:
            logger.warning(
                "Invalid payload for known type '%s' — discarded: %s | msg=%r",
                msg_type,
                payload_error,
                msg,
            )
            return

        # Version compatibility: reject incompatible MAJOR versions
        if parts[0] != _PROTOCOL_MAJOR:
            logger.error(
                "Incompatible protocol MAJOR version '%s' (expected %s) — discarded",
                version,
                _PROTOCOL_MAJOR,
            )
            return
        handlers = self._handlers.get(msg_type, [])

        if not handlers:
            logger.debug("No handler for message type '%s' — ignored", msg_type)
            return

        for handler in handlers:
            try:
                handler(msg)
            except Exception as exc:
                logger.exception("Handler %r raised for type '%s': %s", handler, msg_type, exc)
