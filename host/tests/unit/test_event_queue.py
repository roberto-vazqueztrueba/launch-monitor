"""Tests for pico/communication/event_queue.py.

EventQueue is pure Python (no MicroPython-specific imports), so it runs
directly under CPython/pytest without stubs.
"""

import pathlib
import sys

_PICO_COMM = str(pathlib.Path(__file__).parents[3] / "pico" / "communication")
if _PICO_COMM not in sys.path:
    sys.path.insert(0, _PICO_COMM)

from event_queue import EventQueue  # noqa: E402


# ---------------------------------------------------------------------------
# Basic push / pop / empty / size
# ---------------------------------------------------------------------------

class TestBasicBehavior:
    def test_empty_on_creation(self):
        q = EventQueue(maxlen=5)
        assert q.empty()
        assert q.size() == 0

    def test_pop_on_empty_returns_none(self):
        q = EventQueue(maxlen=5)
        assert q.pop() is None

    def test_push_makes_not_empty(self):
        q = EventQueue(maxlen=5)
        q.push({"type": "a"})
        assert not q.empty()
        assert q.size() == 1

    def test_pop_returns_pushed_message(self):
        q = EventQueue(maxlen=5)
        msg = {"type": "t0_detected", "confidence": 0.9}
        q.push(msg)
        assert q.pop() == msg

    def test_pop_empties_queue(self):
        q = EventQueue(maxlen=5)
        q.push({"type": "a"})
        q.pop()
        assert q.empty()
        assert q.size() == 0


# ---------------------------------------------------------------------------
# FIFO ordering
# ---------------------------------------------------------------------------

class TestFIFOOrdering:
    def test_fifo_order_preserved(self):
        q = EventQueue(maxlen=5)
        msgs = [{"type": "a"}, {"type": "b"}, {"type": "c"}]
        for m in msgs:
            q.push(m)
        received = [q.pop(), q.pop(), q.pop()]
        assert received == msgs

    def test_interleaved_push_pop_preserves_order(self):
        q = EventQueue(maxlen=5)
        q.push({"type": "a"})
        q.push({"type": "b"})
        assert q.pop() == {"type": "a"}
        q.push({"type": "c"})
        assert q.pop() == {"type": "b"}
        assert q.pop() == {"type": "c"}
        assert q.pop() is None


# ---------------------------------------------------------------------------
# Backpressure: oldest message dropped when full
# ---------------------------------------------------------------------------

class TestBackpressure:
    def test_oldest_dropped_when_full(self):
        """When maxlen is reached, push() drops the oldest entry."""
        q = EventQueue(maxlen=3)
        q.push({"type": "first"})
        q.push({"type": "second"})
        q.push({"type": "third"})
        # Queue is now full — next push must drop "first"
        q.push({"type": "fourth"})
        assert q.size() == 3
        assert q.pop() == {"type": "second"}
        assert q.pop() == {"type": "third"}
        assert q.pop() == {"type": "fourth"}

    def test_multiple_overflows_keep_newest(self):
        """Repeated overflow always retains the most recent messages."""
        q = EventQueue(maxlen=2)
        for i in range(5):
            q.push({"type": str(i)})
        assert q.size() == 2
        assert q.pop() == {"type": "3"}
        assert q.pop() == {"type": "4"}

    def test_size_never_exceeds_maxlen(self):
        q = EventQueue(maxlen=3)
        for i in range(10):
            q.push({"type": str(i)})
        assert q.size() == 3

    def test_maxlen_one_always_keeps_latest(self):
        q = EventQueue(maxlen=1)
        q.push({"type": "old"})
        q.push({"type": "new"})
        assert q.size() == 1
        assert q.pop() == {"type": "new"}
