#!/usr/bin/env python3
"""Verify 4-Chart Standard compliance.

Runs the 7-item contract checklist:
  1. Issue exists explaining the change
  2. 4-chart-standard.md is updated
  3. chart_gen.py has make_chart_4panel()
  4. daily_reminder.py has matching caption
  5. TG message length <= 4096 chars
  6. 10 tickers chart gen <= 30s
  7. PR has 'area:charts' label (manual check)

Usage:
  python3 verify_4chart_standard.py [--check] [--issue N] [--pr N]
"""
from __future__ import annotations
import sys
import os
import re
import time
import argparse
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "AUTOMATION" / "src"
DOCS = REPO / "AUTOMATION" / "docs"
CHARTS = [
    ("MGC=F", "Micro Gold"),
    ("MNQ=F", "Micro Nasdaq"),
    ("MCL=F", "Micro Crude Oil"),
    ("MBT=F", "Micro Bitcoin"),
    ("MES=F", "Micro S&P 500"),
    ("M2K=F", "Micro Russell 2000"),
    ("MYM=F", "Micro Dow"),
    ("M6A=F", "Micro AUD/USD"),
    ("M6B=F", "Micro GBP/USD"),
    ("6J=F",  "Micro JPY"),
]

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = PASS if ok else FAIL
    print(f"  {mark} {label}" + (f" — {detail}" if detail else ""))
    return ok


def check_1_issue_exists(issue_n: str | None) -> bool:
    if not issue_n:
        print(f"  {WARN} 1. Issue number not provided — skip (--issue N)")
        return True
    print(f"\n[1/7] Issue #{issue_n} exists with rationale")
    r = subprocess.run(
        ["gh", "issue", "view", issue_n, "--json", "title,body,labels"],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        return check("gh CLI 可用 + issue 存在", False, r.stderr[:80])
    import json
    data = json.loads(r.stdout)
    title = data.get("title", "")
    body = data.get("body", "")
    has_label = any(l.get("name", "") == "area:charts" for l in data.get("labels", []))
    ok = "chart" in title.lower() or "4-chart" in title.lower()
    ok &= bool(body.strip())
    return check("Title 含 'chart' / '4-chart'", ok, title) and \
           check("Body 唔係空 (有 rationale)", bool(body.strip()))


def check_2_doc_updated() -> bool:
    print("\n[2/7] docs/4-chart-standard.md 存在 + 有實質內容")
    p = DOCS / "4-chart-standard.md"
    if not p.exists():
        return check("檔案存在", False, str(p))
    content = p.read_text(encoding="utf-8")
    has_panel_spec = "Panel 1" in content and "Panel 4" in content
    has_philosophy = "Bias" in content or "Trigger" in content
    has_history = "v2.6.4" in content and "v2.6.8" in content
    return (
        check("檔案存在", True, f"{len(content)} chars") and
        check("Panel 1-4 都有 spec", has_panel_spec) and
        check("哲學 / Trigger 提到", has_philosophy) and
        check("v2.6.4 → v2.6.8 升級史", has_history)
    )


def check_3_make_chart_4panel() -> bool:
    print("\n[3/7] chart_gen.py 有 make_chart_4panel()")
    p = SRC / "chart_gen.py"
    if not p.exists():
        return check("chart_gen.py 存在", False)
    content = p.read_text(encoding="utf-8")
    has_fn = "def make_chart_4panel" in content
    has_m5 = "df_m5" in content and "5m" in content.lower()
    has_4_panels = content.count("add_subplot") >= 5
    return (
        check("make_chart_4panel 函數存在", has_fn) and
        check("df_m5 數據 fetch (5m interval)", has_m5) and
        check("5 個 subplot (4 panels + volume)", has_4_panels)
    )


def check_4_daily_reminder_caption() -> bool:
    print("\n[4/7] daily_reminder.py 用 4-Chart Standard caption")
    p = SRC / "daily_reminder.py"
    if not p.exists():
        return check("daily_reminder.py 存在", False)
    content = p.read_text(encoding="utf-8")
    has_caption = "4-Chart Standard" in content
    no_old = "3-chart 標準" not in content.lower()
    return (
        check("'4-Chart Standard' 喺 src", has_caption) and
        check("冇遺留 '3-Chart 標準' (舊名)", no_old)
    )


def check_5_tg_message_length() -> bool:
    print("\n[5/7] TG message length ≤ 4096 chars")
    sys.path.insert(0, str(SRC))
    try:
        from daily_reminder import build_reminder
        from llm_grader import rank_trade_candidates
    except Exception as e:
        return check("可以 import build_reminder / rank_trade_candidates", False, str(e)[:60])

    mock_snapshot = [
        {"tk": tk, "name": name, "last": 100.0 + i, "chg": 0.5, "pct": 0.5}
        for i, (tk, name) in enumerate(CHARTS[:13])
    ]
    mock_grades = [
        {"ticker": tk, "grade": "C", "reason": f"test reason {i}"}
        for i, (tk, _) in enumerate(CHARTS)
    ]
    mock_grades[0]["grade"] = "A"
    candidates = rank_trade_candidates(mock_grades)
    msg = build_reminder(mock_snapshot, "2026-08-12", "Wed", mock_grades, candidates)
    length = len(msg)
    return check(
        f"TG msg length {length} chars ≤ 4096",
        length <= 4096,
        f"{4096 - length} chars 剩餘"
    )


def check_6_chart_gen_speed() -> bool:
    print("\n[6/7] 10 tickers chart gen ≤ 30s")
    sys.path.insert(0, str(SRC))
    try:
        from chart_gen import generate_for_ticker
    except Exception as e:
        return check("可以 import generate_for_ticker", False, str(e)[:60])

    out_dir = Path("/tmp/apex-verify-charts")
    out_dir.mkdir(exist_ok=True)
    for f in out_dir.glob("*.png"):
        f.unlink()

    from concurrent.futures import ThreadPoolExecutor, as_completed
    t0 = time.time()
    success = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {
            pool.submit(generate_for_ticker, tk, name, out_dir): tk
            for tk, name in CHARTS
        }
        for fut in as_completed(futs):
            p, _ = fut.result()
            if p:
                success += 1
    elapsed = time.time() - t0
    return (
        check(f"10 tickers gen {elapsed:.1f}s ≤ 30s", elapsed <= 30.0) and
        check(f"{success}/10 tickers 成功", success == 10, f"剩 {10 - success} 個 fail")
    )


def check_7_pr_label(pr_n: str | None) -> bool:
    if not pr_n:
        print(f"\n[7/7] PR number not provided — skip (--pr N)")
        print(f"  {WARN} 7. PR label 'area:charts' — 喺 GitHub UI 上加 (bot 自動加都 OK)")
        return True
    print(f"\n[7/7] PR #{pr_n} has 'area:charts' label")
    r = subprocess.run(
        ["gh", "pr", "view", pr_n, "--json", "labels"],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        return check("gh CLI 可用 + PR 存在", False, r.stderr[:80])
    import json
    data = json.loads(r.stdout)
    labels = [l.get("name", "") for l in data.get("labels", [])]
    return check("'area:charts' label", "area:charts" in labels, str(labels))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue", help="Issue number for item 1")
    parser.add_argument("--pr", help="PR number for item 7")
    args = parser.parse_args()

    print("=" * 60)
    print("4-Chart Standard Verification (7-Item Contract)")
    print("=" * 60)

    results = []
    results.append(check_1_issue_exists(args.issue))
    results.append(check_2_doc_updated())
    results.append(check_3_make_chart_4panel())
    results.append(check_4_daily_reminder_caption())
    results.append(check_5_tg_message_length())
    results.append(check_6_chart_gen_speed())
    results.append(check_7_pr_label(args.pr))

    print("\n" + "=" * 60)
    n_pass = sum(results)
    n_total = len(results)
    if n_pass == n_total:
        print(f"🎉 ALL {n_total} CHECKS PASSED — ready to merge")
        sys.exit(0)
    else:
        print(f"⚠️  {n_pass}/{n_total} passed — {n_total - n_pass} need fixing")
        sys.exit(1)


if __name__ == "__main__":
    main()
