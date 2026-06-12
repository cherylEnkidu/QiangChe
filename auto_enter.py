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
import sys

try:
    import pyautogui
except ImportError:
    print("Error: pyautogui library not found.")
    print("Please install it by running: pip3 install pyautogui")
    print("(macOS: You may need to grant Terminal/Python Accessibility permissions in System Settings > Privacy & Security)")
    sys.exit(1)

# Remove pyautogui's default 0.1s pause to ensure zero delay
pyautogui.PAUSE = 0            

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
    parser = argparse.ArgumentParser(description="Auto-Enter at specific time")
    parser.add_argument("-t", "--target", type=str, required=True, 
                        help="Target time (Format: 18:00:00 or 18:00:00.000)")
    parser.add_argument("-l", "--lead-ms", type=int, default=80, 
                        help="Lead milliseconds (Positive=Early, Negative=Late, Default: 80)")
    
    args = parser.parse_args()

    target_time = args.target
    lead_ms = args.lead_ms

    try:
        fire_ts = parse_target(target_time) - lead_ms / 1000.0
    except Exception as e:
        print(f"Failed to parse time: {e}")
        return

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
    while True:
        remaining = fire_ts - time.time()
        if remaining <= 0:
            break
            
        if remaining > 2.0:
            sys.stdout.write(f"\r⏳ Waiting, time remaining: {remaining:.1f} seconds...")
            sys.stdout.flush()
            time.sleep(0.5)
        elif remaining > 0.2:
            sys.stdout.write("\r" + " "*40 + "\r")
            sys.stdout.write("⚠️ Get ready to fire (Keep window focused, do not move mouse)...\n")
            sys.stdout.flush()
            time.sleep(remaining - 0.2)
        else:
            # Busy wait for the last 200ms for precision
            pass

    # Core action
    pyautogui.press("enter")
    
    print("\n✅ Sent! Current time:", datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3])

if __name__ == "__main__":
    main()
