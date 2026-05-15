"""EventDispatcher: routes decoded serial messages to registered handlers."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Callable

logger = logging.getLogger(__name__)

_REQUIRED_ENVELOPE_KEYS = {"type", "version", "timestamp_ms", "payload"}
_PROTOCOL_MAJOR = "1"

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
