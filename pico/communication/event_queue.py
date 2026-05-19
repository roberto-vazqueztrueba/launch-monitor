# EventQueue — bounded FIFO for MicroPython firmware
#
# Uses collections.deque (available in MicroPython RP2 stdlib).
# Older MicroPython builds may need a manual ring-buffer; deque is preferred.

from collections import deque


class EventQueue:
    """Bounded FIFO message queue for single execution-context use.

    This queue does not provide locking or atomicity guarantees and should
    not be treated as safe for concurrent access from multiple threads or
    interrupt contexts.

    When the queue is full, the oldest message is dropped to make room for
    the newest one, ensuring freshness under backpressure.

    Args:
        maxlen: Maximum number of messages to hold. Defaults to 20.
    """

    def __init__(self, maxlen: int = 20) -> None:
        self._maxlen = maxlen
        self._q = deque((), maxlen)

    def push(self, msg: dict) -> None:
        """Enqueue *msg*. If the queue is full, drop the oldest entry first.

        Args:
            msg: Message dictionary with at least a ``type`` key.
        """
        if len(self._q) >= self._maxlen:
            # Drop oldest to preserve real-time freshness
            try:
                self._q.popleft()
            except IndexError:
                pass
        self._q.append(msg)

    def pop(self):
        """Dequeue and return the oldest message, or ``None`` if empty."""
        try:
            return self._q.popleft()
        except IndexError:
            return None

    def empty(self) -> bool:
        """Return ``True`` when the queue has no pending messages."""
        return len(self._q) == 0

    def size(self) -> int:
        """Return the current number of queued messages."""
        return len(self._q)
