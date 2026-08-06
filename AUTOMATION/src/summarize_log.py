#!/usr/bin/env python3
"""Summarize apex-forward-log.jsonl for daily Telegram alerts.

Usage:
    python3 summarize_log.py <path-to-log>

Output: "<N> trades, $<total>"

Used by GitHub Actions daily-scan workflow and cron_runner.sh.
"""
import json
import sys

if len(sys.argv) != 2:
    print("?")
    sys.exit(0)

total = 0
n = 0
try:
    with open(sys.argv[1]) as f:
        for line in f:
            try:
                d = json.loads(line)
                total += d.get("pnl_usd", 0)
                n += 1
            except Exception:
                pass
    print(f"{n} trades, ${total:+,.0f}")
except Exception as e:
    print(f"err: {e}", file=sys.stderr)
    print("?")
