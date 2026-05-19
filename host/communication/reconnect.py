"""Reconnection helper — encapsulates the retry-on-disconnect policy.

This module is intentionally thin: the reconnection logic lives inside
:class:`SerialChannel._run`. This module provides the configurable
parameters and the :class:`ReconnectPolicy` dataclass so they can be
customised and tested independently.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import (
    HEARTBEAT_TIMEOUT_S,
    RECONNECT_INTERVAL_S,
    RECONNECT_MAX_ATTEMPTS,
)


@dataclass
class ReconnectPolicy:
    """Parameters that govern automatic reconnection behaviour.

    Attributes:
        interval_s: Seconds to wait between reconnection attempts.
        heartbeat_timeout_s: Seconds without data before a
            ``heartbeat_request`` is sent.
        max_attempts: Maximum reconnection attempts before giving up.
            ``0`` means unlimited retries (default).
    """

    interval_s: float = RECONNECT_INTERVAL_S
    heartbeat_timeout_s: float = HEARTBEAT_TIMEOUT_S
    max_attempts: int = RECONNECT_MAX_ATTEMPTS  # 0 = unlimited


DEFAULT_POLICY = ReconnectPolicy()
