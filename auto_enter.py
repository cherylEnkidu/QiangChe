#!/usr/bin/env python3
"""
Auto-Enter Assistant - Precise Scheduled Enter Key Simulator

Features:
1. Supports command line arguments
2. Countdown display
3. Time format error handling
"""

import time
import datetime
import argparse
import json
import os
import sys

# Persistent config for the "home"/"work" lead-time presets.
CONFIG_PATH = os.path.expanduser("~/.auto_enter_config.json")
DEFAULT_LEAD_MS = 80
DEFAULT_CONFIG = {"home": 100, "work": 100}
# Minimum seconds to leave for preparation when auto-targeting the next minute.
PREP_SECONDS = 5


def load_config() -> dict:
    """Load the lead-time presets, falling back to defaults on any error."""
    config = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        for key in DEFAULT_CONFIG:
            if isinstance(data.get(key), int):
                config[key] = data[key]
    except (FileNotFoundError, ValueError, OSError):
        pass
    return config


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f)


def handle_set(rest: list) -> None:
    """Handle: auto_enter.py set <home|work> <milliseconds>"""
    if len(rest) != 2 or rest[0] not in DEFAULT_CONFIG:
        print("Usage: auto_enter.py set <home|work> <milliseconds>")
        sys.exit(1)
    key = rest[0]
    try:
        value = int(rest[1])
    except ValueError:
        print(f"Invalid milliseconds value: {rest[1]}")
        sys.exit(1)
    config = load_config()
    config[key] = value
    save_config(config)
    print(f"✅ Set '{key}' lead time to {value} ms (saved to {CONFIG_PATH})")


def compute_next_minute_target():
    """
    Auto-target the upcoming minute boundary (HH:MM:00), leaving at least
    PREP_SECONDS to prepare. If the next boundary is too close (<= PREP_SECONDS
    away), skip to the following minute instead.
    Returns (timestamp, display_string).
    """
    now = datetime.datetime.now()
    target = now.replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
    if (target - now).total_seconds() <= PREP_SECONDS:
        target += datetime.timedelta(minutes=1)
    return target.timestamp(), target.strftime("%H:%M:%S")


def parse_target(s: str) -> float:
    """
    Parse the target time, supports HH:MM:SS or HH:MM:SS.mmm
    """
    parts = s.split(":")
    if len(parts) == 2:
        h, m = parts
        sec = "0"
    elif len(parts) == 3:
        h, m, sec = parts
    else:
        raise ValueError("Invalid time format, please use HH:MM:SS or HH:MM:SS.mmm")
        
    sec_parts = sec.split(".")
    if len(sec_parts) == 1:
        sec = sec_parts[0]
        ms = "0"
    else:
        sec, ms = sec_parts[:2]
        
    t = datetime.time(int(h), int(m), int(sec), int(ms.ljust(3, "0")) * 1000)
    return datetime.datetime.combine(datetime.date.today(), t).timestamp()

def main():
    # Subcommand to update saved lead-time presets, e.g. "set home 170".
    if len(sys.argv) >= 2 and sys.argv[1] == "set":
        handle_set(sys.argv[2:])
        return

    parser = argparse.ArgumentParser(description="Auto-Enter at specific time")
    parser.add_argument("-t", "--target", type=str, default=None,
                        help="Target time (Format: 18:00:00 or 18:00:00.000)")
    parser.add_argument("-n", "--next", action="store_true",
                        help="Auto-target the next minute (HH:MM:00), leaving "
                             f"at least {PREP_SECONDS}s to prepare")
    parser.add_argument("-l", "--lead-ms", type=int, default=None,
                        help="Lead milliseconds (Positive=Early, Negative=Late, Default: 80)")
    parser.add_argument("--home", action="store_true",
                        help="Use the saved 'home' lead time preset")
    parser.add_argument("--work", action="store_true",
                        help="Use the saved 'work' lead time preset")

    args = parser.parse_args()

    if not args.target and not args.next:
        parser.error("one of -t/--target or -n/--next is required")
    if args.home and args.work:
        parser.error("--home and --work cannot be used together")

    # Resolve lead time: explicit -l wins, then --home/--work preset, then default.
    if args.lead_ms is not None:
        lead_ms = args.lead_ms
    elif args.home or args.work:
        config = load_config()
        lead_ms = config["home" if args.home else "work"]
    else:
        lead_ms = DEFAULT_LEAD_MS

    if args.next:
        base_ts, target_time = compute_next_minute_target()
        fire_ts = base_ts - lead_ms / 1000.0
    else:
        target_time = args.target
        try:
            fire_ts = parse_target(target_time) - lead_ms / 1000.0
        except Exception as e:
            print(f"Failed to parse time: {e}")
            return

    try:
        import pyautogui
    except ImportError:
        print("Error: pyautogui library not found.")
        print("Please install it by running: pip3 install pyautogui")
        print("(macOS: You may need to grant Terminal/Python Accessibility permissions in System Settings > Privacy & Security)")
        return
    # Remove pyautogui's default 0.1s pause to ensure zero delay
    pyautogui.PAUSE = 0

    now = time.time()
    if fire_ts < now:
        print("Warning: Target time is in the past! If you meant tomorrow, please run this script tomorrow.")
        return

    print("="*40)
    print(f"🎯 Target Time: {target_time}")
    print(f"⏱️  Lead Time:   {lead_ms} ms")
    print(f"🚀 Actual Press: {datetime.datetime.fromtimestamp(fire_ts).strftime('%H:%M:%S.%f')[:-3]}")
    print("="*40)
    print("Please switch to the target window and leave your cursor in the input box...")

    # Countdown display
    warning_printed = False
    while True:
        remaining = fire_ts - time.time()
        if remaining <= 0:
            break
            
        if remaining > 2.0:
            sys.stdout.write(f"\r⏳ Waiting, time remaining: {remaining:.1f} seconds...   ")
            sys.stdout.flush()
            time.sleep(0.1)
        elif remaining > 0.2:
            if not warning_printed:
                sys.stdout.write("\r" + " "*60 + "\r")
                sys.stdout.write("⚠️ Get ready to fire (Keep window focused, do not move mouse)...")
                sys.stdout.flush()
                warning_printed = True
            time.sleep(remaining - 0.2)
        else:
            # Busy wait for the last 200ms for precision
            pass

    # Core action
    pyautogui.press("enter")
    
    print("\n✅ Sent! Current time:", datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3])

if __name__ == "__main__":
    main()
