"""Reconnection helper — encapsulates the retry-on-disconnect policy.

This module is intentionally thin: the reconnection logic lives inside
:class:`SerialChannel._run`. This module provides the configurable
parameters and the :class:`ReconnectPolicy` dataclass so they can be
customised and tested independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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

    interval_s: float = 0.5
    heartbeat_timeout_s: float = 5.0
    max_attempts: int = 0  # 0 = unlimited


DEFAULT_POLICY = ReconnectPolicy()
