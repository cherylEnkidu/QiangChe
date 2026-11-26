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
import subprocess
import statistics
from pathlib import Path

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

def clock_text(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-3]


def prepare_macos_return(target_wechat=False):
    import Quartz
    from pyautogui import failSafeCheck

    if not Quartz.CGPreflightPostEventAccess():
        sys.exit("请在 macOS 辅助功能中授权运行脚本的终端，再重新打开终端。")
    post = Quartz.CGEventPost
    destination = Quartz.kCGHIDEventTap
    app = None
    if target_wechat:
        from AppKit import NSRunningApplication
        apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_("com.tencent.xinWeChat")
        if len(apps) != 1:
            sys.exit("请先打开一个 Mac 微信客户端，再启动定时。")
        app = apps[0]
        destination = app.processIdentifier()
        post = Quartz.CGEventPostToPid
    create = Quartz.CGEventCreateKeyboardEvent

    def prepare_events():
        failSafeCheck()
        down = create(None, 36, True)
        up = create(None, 36, False)
        if down is None or up is None:
            sys.exit("无法创建回车事件。")
        return down, up

    def press():
        down, up = prepare_events()
        if app is not None and app.isTerminated():
            sys.exit("微信已退出，请重新启动定时。")
        post(destination, down)
        down_ts = time.time()
        post(destination, up)
        return down_ts, time.time()

    return press, prepare_events


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

    parser.add_argument("--target-wechat", action="store_true",
                        help="Deliver Return to the current chat in Mac WeChat")
    parser.add_argument("--wechat-rtt", action="store_true",
                        help="Estimate lead from live WeChat TCP connections on macOS")
    parser.add_argument("--rtt-stat", choices=["min", "avg"],
                        help="Choose the RTT used for compensation (default: min)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run the timer without sending a key")
    parser.add_argument("--extra-lead-ms", type=int, metavar="MS",
                        help="Add MS to a positive automatic WeChat lead for this run")
    args = parser.parse_args()
    if args.target_wechat and sys.platform != "darwin":
        parser.error("--target-wechat requires macOS")
    if args.rtt_stat and not args.wechat_rtt:
        parser.error("--rtt-stat requires --wechat-rtt")
    if args.extra_lead_ms is not None and (not args.wechat_rtt or args.extra_lead_ms < 0):
        parser.error("--extra-lead-ms requires --wechat-rtt and a nonnegative millisecond value")
    if args.wechat_rtt and (args.home or args.work or args.lead_ms is not None):
        parser.error("--wechat-rtt selects the lead time; use it without -l, --home or --work")

    if not args.target and not args.next:
        parser.error("one of -t/--target or -n/--next is required")
    if args.home and args.work:
        parser.error("--home and --work cannot be used together")

    if not args.dry_run:
        try:
            if sys.platform == "darwin":
                press, prepare_events = prepare_macos_return(args.target_wechat)
            else:
                import pyautogui
                pyautogui.PAUSE = 0
        except ImportError as exc:
            parser.exit(1, f"按键组件加载失败：{exc}\n")

    if args.next:
        base_ts, target_time = compute_next_minute_target()
    else:
        target_time = args.target
        try:
            base_ts = parse_target(target_time)
        except ValueError as exc:
            parser.error(str(exc))

    # Resolve lead time: explicit -l wins, then --home/--work preset, then default.
    if args.wechat_rtt:
        prep_ms = 0
        if not args.dry_run and sys.platform == "darwin":
            durations = []
            for _ in range(7):
                start = time.perf_counter()
                prepare_events()
                durations.append((time.perf_counter() - start) * 1000)
            prep_ms = statistics.median(durations)
            print(f"本机按键准备耗时中位数 {prep_ms:.2f} ms（7 次模拟准备）")
        probe = Path(__file__).resolve().parent / "macOS_App_Source" / "wechat-rtt.sh"
        if base_ts <= time.time():
            parser.error("目标时间已过")
        print("请现在切换到目标输入框。将在目标前约 10 秒采样微信 RTT…", flush=True)
        time.sleep(max(0, base_ts - time.time() - 10))
        count = max(1, min(10, int(base_ts - time.time() + 0.25)))
        try:
            lead_ms = int(subprocess.check_output(["/bin/bash", str(probe), str(count), args.rtt_stat or "min"], timeout=count+3))
        except (OSError, subprocess.SubprocessError, ValueError):
            parser.exit(1, "无法测得微信 RTT，定时未启动。\n")
        if lead_ms > 0:
            lead_ms = min(15, lead_ms + int(prep_ms))
            if args.extra_lead_ms:
                print(f"自动提前 {lead_ms} ms，本次另加 {args.extra_lead_ms} ms")
                lead_ms += args.extra_lead_ms
        elif args.extra_lead_ms:
            print("自动提前量为零，本次跳过额外提前量。")
    elif args.lead_ms is not None:
        lead_ms = args.lead_ms
    elif args.home or args.work:
        config = load_config()
        lead_ms = config["home" if args.home else "work"]
    else:
        lead_ms = DEFAULT_LEAD_MS

    fire_ts = base_ts - lead_ms / 1000.0
    now = time.time()
    if fire_ts < now:
        print("Warning: Target time is in the past! If you meant tomorrow, please run this script tomorrow.")
        return

    print("="*40)
    print(f"🎯 Target Time: {target_time}")
    print(f"⏱️  Lead Time:   {lead_ms} ms")
    print(f"计划投递回车: {clock_text(fire_ts)}")
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

    if args.dry_run:
        print("\n模拟触发时间", clock_text(time.time()))
    elif sys.platform == "darwin":
        down_ts, up_ts = press()
        print(f"\n本机投递回车按下 {clock_text(down_ts)}（距目标 {(base_ts-down_ts)*1000:.1f} ms）")
        print(f"本机投递回车释放 {clock_text(up_ts)}（距目标 {(base_ts-up_ts)*1000:.1f} ms）")
    else:
        pyautogui.press("enter")
        print("\n按键调用完成", clock_text(time.time()))


if __name__ == "__main__":
    main()
