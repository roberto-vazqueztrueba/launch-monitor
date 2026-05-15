"""monitor.py — Live serial monitor for the RPi ↔ Pico channel.

Usage (from repo root):
    PYTHONPATH=. python3 host/tools/monitor.py [--port /dev/ttyACM0]

Shows all incoming messages with colour-coded output and lets you send
commands interactively by typing their shorthand.
"""

import argparse
import logging
import sys
import threading
import time

# Colour codes (degrade gracefully if terminal doesn't support them)
_C = {
    "reset":   "\033[0m",
    "bold":    "\033[1m",
    "grey":    "\033[90m",
    "green":   "\033[92m",
    "yellow":  "\033[93m",
    "cyan":    "\033[96m",
    "red":     "\033[91m",
    "magenta": "\033[95m",
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
    parser = argparse.ArgumentParser(description="Live Pico serial monitor")
    parser.add_argument("--port", default="/dev/ttyACM0")
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

    def input_loop() -> None:
        while True:
            try:
                raw = input("> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                channel.stop()
                sys.exit(0)

            if raw in ("q", "quit", "exit"):
                channel.stop()
                sys.exit(0)
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
            time.sleep(args.time)
            channel.stop()
        else:
            while t.is_alive():
                time.sleep(0.1)
    except KeyboardInterrupt:
        channel.stop()


if __name__ == "__main__":
    main()
