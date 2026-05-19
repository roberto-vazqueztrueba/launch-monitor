# config.py — Centralized configuration for the Pico firmware.
#
# All tuneable constants are defined here and imported by the rest of the
# firmware.  Change values in this single file; no other module needs to
# be touched.
#
# MicroPython stdlib only — no external dependencies.
#
# Usage:
#   import config
#   utime.sleep_ms(config.USB_STARTUP_DELAY_MS)

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = "1.0.0"
# Semantic version string stamped on every outgoing envelope.
# Must be MAJOR.MINOR.PATCH.  The host rejects messages whose MAJOR
# component differs from "1".

# ---------------------------------------------------------------------------
# Timing — main loop
# ---------------------------------------------------------------------------

HEARTBEAT_INTERVAL_MS = 2000
# Milliseconds between spontaneous heartbeat messages sent to the host.
# Shorter values increase host visibility into Pico health but consume
# more USB bandwidth and CPU cycles.

FLUSH_INTERVAL_MS = 10
# Milliseconds the main loop sleeps between each call to channel.flush().
# Controls the maximum latency for outbound messages: a message pushed to
# the queue can wait up to this many ms before being transmitted.
# Shorter values reduce latency; very short values increase CPU load.

USB_STARTUP_DELAY_MS = 2000
# Milliseconds to wait after boot before sending any serial data.
# Gives the host USB-CDC driver time to enumerate the virtual COM port.
# Too short a delay can cause the first frames to be lost on the host side.

# ---------------------------------------------------------------------------
# Serial / channel
# ---------------------------------------------------------------------------

MAX_FRAME_BYTES = 1024
# Maximum byte length of a single inbound JSON frame (host→Pico command).
# If more bytes arrive without a newline, the partial frame is discarded
# and the receive buffer is reset.  Keeps RAM usage bounded on the Pico.

# ---------------------------------------------------------------------------
# Event queue
# ---------------------------------------------------------------------------

EVENT_QUEUE_MAXLEN = 20
# Maximum number of outbound messages held in the EventQueue at once.
# When the queue is full the oldest message is dropped to make room for
# the newest one, ensuring freshness under backpressure.
# Increase this value if bursts of sensor events are being silently dropped;
# decrease it to reduce peak RAM usage.
