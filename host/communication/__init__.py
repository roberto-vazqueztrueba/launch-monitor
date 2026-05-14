"""Serial communication channel between Raspberry Pi host and Pico firmware."""

from .channel import SerialChannel
from .dispatcher import EventDispatcher
from .messages import (
    make_led_set,
    make_buzzer_beep,
    make_state_transition,
    make_heartbeat_ack,
)

__all__ = [
    "SerialChannel",
    "EventDispatcher",
    "make_led_set",
    "make_buzzer_beep",
    "make_state_transition",
    "make_heartbeat_ack",
]
