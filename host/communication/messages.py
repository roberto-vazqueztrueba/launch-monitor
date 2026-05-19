"""Message factory functions for RPi → Pico commands.

All functions return a fully-formed envelope dict ready for
:meth:`SerialChannel.send`.
"""

from __future__ import annotations

import time

from ..config import PROTOCOL_VERSION, PROCESS_START_S

# ---------------------------------------------------------------------------
# Valid enumerated values (kept here for validation; also documents the spec)
# ---------------------------------------------------------------------------

LED_IDS = frozenset({"status", "mode", "error"})
LED_STATES = frozenset({"on", "off", "blink_slow", "blink_fast"})
BUZZER_PATTERNS = frozenset({"short", "long", "double", "error"})
SYSTEM_STATES = frozenset({
    "BOOTING", "SELF_TEST", "WAITING_PROFILE", "WAITING_CLUB",
    "READY", "ARMED", "IMPACT_DETECTED", "PROCESSING",
    "RESULTS", "DIAGNOSTICS", "ERROR",
})


def _envelope(msg_type: str, payload: dict) -> dict:
    return {
        "type": msg_type,
        "version": PROTOCOL_VERSION,
        "timestamp_ms": int((time.monotonic() - PROCESS_START_S) * 1000),
        "payload": payload,
    }


def make_led_set(led_id: str, state: str) -> dict:
    """Build a ``led_set`` command.

    Args:
        led_id: One of ``status``, ``mode``, ``error``.
        state: One of ``on``, ``off``, ``blink_slow``, ``blink_fast``.

    Raises:
        ValueError: If *led_id* or *state* are not valid enumerated values.
    """
    if led_id not in LED_IDS:
        raise ValueError(f"led_id must be one of {sorted(LED_IDS)}, got {led_id!r}")
    if state not in LED_STATES:
        raise ValueError(f"state must be one of {sorted(LED_STATES)}, got {state!r}")
    return _envelope("led_set", {"led_id": led_id, "state": state})


def make_buzzer_beep(pattern: str) -> dict:
    """Build a ``buzzer_beep`` command.

    Args:
        pattern: One of ``short``, ``long``, ``double``, ``error``.

    Raises:
        ValueError: If *pattern* is not a valid enumerated value.
    """
    if pattern not in BUZZER_PATTERNS:
        raise ValueError(f"pattern must be one of {sorted(BUZZER_PATTERNS)}, got {pattern!r}")
    return _envelope("buzzer_beep", {"pattern": pattern})


def make_state_transition(new_state: str) -> dict:
    """Build a ``state_transition`` command.

    Args:
        new_state: One of the valid system states (see :data:`SYSTEM_STATES`).

    Raises:
        ValueError: If *new_state* is not a valid enumerated value.
    """
    if new_state not in SYSTEM_STATES:
        raise ValueError(f"new_state must be one of {sorted(SYSTEM_STATES)}, got {new_state!r}")
    return _envelope("state_transition", {"new_state": new_state})


def make_heartbeat_ack() -> dict:
    """Build a ``heartbeat_ack`` command."""
    return _envelope("heartbeat_ack", {})


def make_heartbeat_request() -> dict:
    """Build a ``heartbeat_request`` command.

    Sent by the host watchdog when no data has been received for
    :attr:`ReconnectPolicy.heartbeat_timeout_s` seconds, to probe
    whether the Pico is still alive.
    """
    return _envelope("heartbeat_request", {})
