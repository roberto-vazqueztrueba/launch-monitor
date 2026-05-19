"""monitor.py — Live serial monitor for the RPi ↔ Pico channel.

Usage (from repo root):
    PYTHONPATH=. python3 host/tools/monitor.py [--port /dev/pico]

Shows all incoming messages with colour-coded output and lets you send
commands interactively by typing their shorthand.
"""

import argparse
import logging
import sys
import threading
import time

# Colour codes (degrade gracefully if terminal doesn't support them)
_COLOUR_ENABLED = sys.stdout.isatty()
_C = {
    "reset":   "\033[0m" if _COLOUR_ENABLED else "",
    "bold":    "\033[1m" if _COLOUR_ENABLED else "",
    "grey":    "\033[90m" if _COLOUR_ENABLED else "",
    "green":   "\033[92m" if _COLOUR_ENABLED else "",
    "yellow":  "\033[93m" if _COLOUR_ENABLED else "",
    "cyan":    "\033[96m" if _COLOUR_ENABLED else "",
    "red":     "\033[91m" if _COLOUR_ENABLED else "",
    "magenta": "\033[95m" if _COLOUR_ENABLED else "",
}

_TYPE_COLOUR = {
    "t0_detected":    "green",
    "sensor_ambient": "cyan",
    "sensor_imu":     "cyan",
    "input_button":   "yellow",
    "input_encoder":  "yellow",
    "input_nfc":      "magenta",
    "heartbeat":      "grey",
    "debug":          "grey",
}

_COMMANDS = """\
Commands you can type:
  led on          → led_set status on
  led off         → led_set status off
  led blink       → led_set status blink_fast
  buzz short      → buzzer_beep short
  buzz long       → buzzer_beep long
  buzz double     → buzzer_beep double
  state ARMED     → state_transition ARMED  (any valid state)
  ack             → heartbeat_ack
  q / quit        → exit
"""


def _c(name: str, text: str) -> str:
    return f"{_C.get(name, '')}{text}{_C['reset']}"


def _print_msg(msg: dict) -> None:
    msg_type = msg.get("type", "?")
    ts = msg.get("timestamp_ms", "?")
    payload = msg.get("payload", {})
    colour = _TYPE_COLOUR.get(msg_type, "bold")
    parts = ", ".join(f"{k}={v}" for k, v in payload.items())
    print(f"  {_c(colour, f'[{msg_type}]'):<35} ts={ts:<10} {parts}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Live Pico serial monitor",
        epilog=(
            "The default port /dev/pico requires a udev symlink rule. "
            "See specs/001-rpi-pico-serial-protocol/quickstart.md for setup instructions. "
            "Without the rule use --port /dev/ttyACM0 (or the appropriate COM port on Windows)."
        ),
    )
    parser.add_argument(
        "--port",
        default="/dev/pico",
        help="Serial port device (default: /dev/pico — requires udev rule; "
             "use /dev/ttyACM0 if the symlink is not configured)",
    )
    parser.add_argument("--time", type=int, default=0, help="Run for N seconds then exit (0=forever)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)  # suppress INFO noise in monitor

    from host.communication.dispatcher import EventDispatcher
    from host.communication.channel import SerialChannel
    from host.communication import messages as m

    dispatcher = EventDispatcher()

    # Register handler for every known type
    for msg_type in (
        "t0_detected", "sensor_ambient", "sensor_imu",
        "input_button", "input_encoder", "input_nfc",
        "heartbeat", "debug",
    ):
        dispatcher.register(msg_type, _print_msg)

    channel = SerialChannel(port=args.port, dispatcher=dispatcher)
    channel.start()

    print(_c("bold", f"\n=== Pico Monitor — {args.port} ==="))
    print(_c("grey", _COMMANDS))

    # Shared stop event: set by 'q'/KeyboardInterrupt in either thread so
    # the main thread wakes from its interruptible wait immediately.
    stop_event = threading.Event()

    def input_loop() -> None:
        while not stop_event.is_set():
            try:
                raw = input("> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                stop_event.set()
                channel.stop()
                return

            if raw in ("q", "quit", "exit"):
                stop_event.set()
                channel.stop()
                return
            elif raw == "led on":
                channel.send(m.make_led_set("status", "on"))
            elif raw == "led off":
                channel.send(m.make_led_set("status", "off"))
            elif raw == "led blink":
                channel.send(m.make_led_set("status", "blink_fast"))
            elif raw.startswith("led "):
                print(_c("red", "  Unknown led command"))
            elif raw == "buzz short":
                channel.send(m.make_buzzer_beep("short"))
            elif raw == "buzz long":
                channel.send(m.make_buzzer_beep("long"))
            elif raw == "buzz double":
                channel.send(m.make_buzzer_beep("double"))
            elif raw.startswith("state "):
                state = raw.split(" ", 1)[1].upper()
                try:
                    channel.send(m.make_state_transition(state))
                except ValueError as e:
                    print(_c("red", f"  {e}"))
            elif raw == "ack":
                channel.send(m.make_heartbeat_ack())
            elif raw == "":
                pass
            else:
                print(_c("grey", "  Unknown command. Type 'q' to quit."))

    t = threading.Thread(target=input_loop, daemon=True)
    t.start()

    try:
        if args.time:
            # Wait for the timeout or for an interactive quit — whichever comes first.
            stop_event.wait(timeout=args.time)
            if not stop_event.is_set():
                channel.stop()
        else:
            stop_event.wait()
    except KeyboardInterrupt:
        stop_event.set()
        channel.stop()


if __name__ == "__main__":
    main()
