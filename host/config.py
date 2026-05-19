"""Centralized configuration for the host (RPi) side of the launch monitor.

All tuneable constants are defined here and imported by the rest of the
host package.  Change values in this single file; no other module needs
to be touched.

Usage::

    from host.config import BAUD_RATE, HEARTBEAT_TIMEOUT_S
"""

import time

# Capture the monotonic clock at import time.  All outgoing RPi→Pico envelopes
# use (time.monotonic() - PROCESS_START_S) * 1000 so that timestamp_ms represents
# milliseconds since the host process started, as required by the data model.
# time.monotonic() returns a float in seconds with sub-millisecond precision on
# most platforms; the * 1000 conversion introduces negligible floating-point
# rounding (at most 1 ms error after many hours of uptime).
PROCESS_START_S: float = time.monotonic()

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

PROTOCOL_VERSION: str = "1.0.0"
"""Semantic version string stamped on every outgoing envelope.
Must match MAJOR.MINOR.PATCH.  The Pico firmware rejects messages whose
MAJOR component differs from "1"."""

# ---------------------------------------------------------------------------
# Serial port
# ---------------------------------------------------------------------------

SERIAL_PORT: str = "/dev/pico"
"""Device path to the Pico USB-CDC port.
On Linux a udev rule creates the ``/dev/pico`` symlink; on macOS use
``/dev/tty.usbmodem*``; on Windows use ``COM<n>``."""

BAUD_RATE: int = 115200
"""Baud-rate configured on the pyserial port.
USB-CDC ignores this value at the hardware level, but pyserial requires
a non-zero integer.  Must match the value used by any external serial
monitor or log tool."""

SERIAL_TIMEOUT_S: float = 1.0
"""Read timeout in seconds for the underlying ``serial.Serial`` object.
Controls how long ``_read_loop`` blocks on each ``readline()`` call
before looping.  Shorter values reduce disconnect-detection latency but
increase CPU usage."""

MAX_FRAME_BYTES: int = 4096
"""Maximum byte length of a single inbound JSON frame.
Frames that exceed this limit before a newline is received are discarded
and the buffer is reset.  Protects against runaway or noisy input that
would exhaust host RAM."""

# ---------------------------------------------------------------------------
# Reconnection / watchdog
# ---------------------------------------------------------------------------

RECONNECT_INTERVAL_S: float = 0.5
"""Seconds to wait between reconnection attempts after a disconnect.
Shorter values restore the link faster; very short values can spam
``/dev/`` with open() calls while the USB enumeration is still settling."""

HEARTBEAT_TIMEOUT_S: float = 5.0
"""Seconds without any inbound data before the host sends a
``heartbeat_request`` to probe whether the Pico is still alive.
If the Pico does not respond, the watchdog will eventually trigger a
reconnect."""

RECONNECT_MAX_ATTEMPTS: int = 0
"""Maximum number of reconnection attempts before giving up.
``0`` means unlimited retries (default), which is appropriate for an
always-on device that can be physically unplugged and re-plugged."""
