#!/usr/bin/env python3
"""Extended MBT=F + apex_v26_kz: max available 5m history ending 2026-09-21."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/workspace/apex_strategy_pick_bt/scripts")
sys.path.insert(0, "/workspace/apex-bt/src")

from apex_v26_constrained import (  # noqa: E402
    CONTRACTS,
    DAILY_KILL,
    DAILY_TP_CAP,
    END_DATE,
    NY,
    RTH_CLOSE,
    RTH_OPEN,
    execute_same_day,
    max_drawdown_from_zero,
    tag_session,
)
from apex_backtest import detect_trigger, fetch, grade_setup  # noqa: E402

OUT = Path("/workspace/apex_strategy_pick_bt/mbt_extended")
TICKER = "MBT=F"
POINT_VALUE = 0.1  # verified: Micro Bitcoin $0.10/pt
TARGET_DAYS = 90  # request ≥90; use all available if fewer


def all_session_dates(m5: pd.DataFrame, end: date) -> list[date]:
    rth = m5[(m5.index.time >= RTH_OPEN) & (m5.index.time < RTH_CLOSE)]
    days = sorted({d.date() for d in (rth.index if len(rth) else m5.index)})
    return [d for d in days if d <= end]


def week_key(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def month_key(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def run() -> tuple[dict, list, list]:
    end = pd.Timestamp(END_DATE)
    # Pull max; fetch() internally uses period=60d for 5m
    start = end - pd.Timedelta(days=120)
    data = fetch(
        TICKER,
        start.strftime("%Y-%m-%d"),
        (end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
    )
    m5, daily = data["fivem"], data["daily"]
    if m5.empty:
        raise RuntimeError(f"no 5m data for {TICKER}")

    # Clip 5m to end date (inclusive through that calendar day in NY)
    m5 = m5[m5.index.date <= END_DATE]
    if m5.empty:
        raise RuntimeError("no 5m bars on/before END_DATE")

    earliest_bar = m5.index[0]
    latest_bar = m5.index[-1]
    days = all_session_dates(m5, END_DATE)
    # Prefer last TARGET_DAYS if somehow more exist; else all available
    if len(days) > TARGET_DAYS:
        days = days[-TARGET_DAYS:]

    day_results = []
    all_trades = []

    for d in days:
        d_ts = pd.Timestamp(d)
        result = {
            "date": d.isoformat(),
            "status": "no_signal",
            "trades": [],
            "day_pnl": 0.0,
            "skips": [],
            "grade": None,
        }
        day_pnl = 0.0

        if day_pnl <= DAILY_KILL or day_pnl >= DAILY_TP_CAP:
            result["status"] = "daily_cap"
            day_results.append(result)
            continue

        trig = detect_trigger(m5, d_ts)
        if trig is None:
            result["status"] = "no_trigger"
            day_results.append(result)
            continue

        setup = grade_setup(trig, daily, d_ts, POINT_VALUE, m5, CONTRACTS)
        if setup is None:
            result["status"] = "no_setup"
            day_results.append(result)
            continue
        if setup["grade"] == "C":
            result["status"] = "grade_C"
            result["grade"] = "C"
            result["skips"].append({"reason": setup.get("reason", "C")})
            day_results.append(result)
            continue
        result["grade"] = setup["grade"]

        trigger_time = trig["trigger_time"]
        day_bars = m5[m5.index.date == d]
        post = day_bars[day_bars.index > trigger_time]
        if post.empty:
            result["status"] = "no_post_trigger_bars"
            day_results.append(result)
            continue

        exec_res = execute_same_day(setup, post, POINT_VALUE)
        if exec_res is None:
            result["status"] = "no_exec"
            day_results.append(result)
            continue
        if exec_res.get("skip_reason") == "chase_past_tp":
            result["status"] = "skipped"
            result["skips"].append(
                {
                    "reason": "chase_past_tp",
                    **{k: exec_res[k] for k in ("entry_fill", "tp", "sl") if k in exec_res},
                }
            )
            day_results.append(result)
            continue

        entry_ts = post.index[0]
        kz = trig.get("killzone") or tag_session(entry_ts)
        if kz not in ("LDLZ", "NYKZ"):
            kz = tag_session(pd.Timestamp(trig["trigger_time"]))
        if kz not in ("LDLZ", "NYKZ"):
            kz = tag_session(entry_ts)
        trade = {
            "date": d.isoformat(),
            "direction": setup["bias"],
            "entry_time": entry_ts.isoformat(),
            "entry": exec_res["entry_fill"],
            "sl": exec_res["sl"],
            "tp": exec_res["tp"],
            "risk_usd": exec_res["risk_usd"],
            "exit": exec_res["exit_price"],
            "exit_time": (
                pd.Timestamp(exec_res["exit_time"]).isoformat()
                if exec_res.get("exit_time") is not None
                else None
            ),
            "exit_reason": exec_res["exit_reason"],
            "pnl_usd": round(float(exec_res["pnl_usd"]), 4),
            "r_multiple": round(float(exec_res["r_multiple"]), 4),
            "session_tag": kz if kz in ("LDLZ", "NYKZ") else tag_session(entry_ts),
            "killzone": trig.get("killzone"),
            "pattern": setup.get("pattern"),
            "grade": setup["grade"],
            "variant": "apex_v26_kz",
        }
        all_trades.append(trade)
        result["trades"] = [trade]
        day_pnl = trade["pnl_usd"]
        result["day_pnl"] = round(day_pnl, 4)
        result["status"] = "traded"
        day_results.append(result)

    pnls = [t["pnl_usd"] for t in all_trades]
    total_net = sum(pnls) if pnls else 0.0
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    flats = [p for p in pnls if p == 0]
    win_rate = (len(wins) / len(pnls) * 100.0) if pnls else 0.0
    avg_r = float(np.mean([t["r_multiple"] for t in all_trades])) if all_trades else 0.0
    expectancy = (total_net / len(pnls)) if pnls else 0.0
    max_dd = max_drawdown_from_zero(pnls)
    daily_pnl = {r["date"]: r["day_pnl"] for r in day_results}
    best_day = max(daily_pnl.items(), key=lambda x: x[1]) if daily_pnl else (None, 0.0)
    worst_day = min(daily_pnl.items(), key=lambda x: x[1]) if daily_pnl else (None, 0.0)
    qualified_days = sum(1 for v in daily_pnl.values() if v >= 250.0)
    trail_breach = max_dd > 2000.0

    by_tag = {"LDLZ": [], "NYKZ": [], "other": []}
    for t in all_trades:
        by_tag.setdefault(t["session_tag"], []).append(t)

    def tag_stats(trades):
        if not trades:
            return {"n": 0, "pnl": 0.0, "win_rate": 0.0, "avg_r": 0.0}
        ps = [x["pnl_usd"] for x in trades]
        return {
            "n": len(trades),
            "pnl": round(sum(ps), 2),
            "win_rate": round(sum(1 for p in ps if p > 0) / len(ps) * 100.0, 2),
            "avg_r": round(float(np.mean([x["r_multiple"] for x in trades])), 4),
        }

    # Month / week breakdown from daily P&L (includes flat days as 0 contribution)
    month_pnl: dict[str, float] = defaultdict(float)
    week_pnl: dict[str, float] = defaultdict(float)
    month_trades: dict[str, int] = defaultdict(int)
    week_trades: dict[str, int] = defaultdict(int)
    for r in day_results:
        d = date.fromisoformat(r["date"])
        mk, wk = month_key(d), week_key(d)
        month_pnl[mk] += r["day_pnl"]
        week_pnl[wk] += r["day_pnl"]
    for t in all_trades:
        d = date.fromisoformat(t["date"])
        month_trades[month_key(d)] += 1
        week_trades[week_key(d)] += 1

    month_breakdown = [
        {
            "month": m,
            "pnl": round(month_pnl[m], 2),
            "n_trades": month_trades[m],
            "n_days": sum(1 for r in day_results if month_key(date.fromisoformat(r["date"])) == m),
        }
        for m in sorted(month_pnl)
    ]
    week_breakdown = [
        {
            "week": w,
            "pnl": round(week_pnl[w], 2),
            "n_trades": week_trades[w],
            "n_days": sum(1 for r in day_results if week_key(date.fromisoformat(r["date"])) == w),
        }
        for w in sorted(week_pnl)
    ]

    if not all_trades:
        verdict, why = "drop", "zero fills under apex_v26_kz hard constraints"
    elif trail_breach:
        verdict, why = "drop", f"maxDD ${max_dd:.2f} breaches $2000 trail"
    elif total_net <= 0:
        verdict, why = "drop", f"net ${total_net:.2f} — no edge"
    elif total_net >= 3000 and max_dd <= 2000 and qualified_days >= 3:
        verdict = "keep"
        why = f"net ${total_net:.2f}, maxDD ${max_dd:.2f}, {qualified_days} ≥$250 days"
    elif qualified_days >= 1 and total_net > 0 and max_dd <= 2000:
        verdict = "tweak"
        why = (
            f"net ${total_net:.2f}, WR {win_rate:.1f}%, n={len(all_trades)}, "
            f"qual_days={qualified_days}, expectancy=${expectancy:.2f}/trade — "
            f"positive but shy of keep gates (≥$3k / ≥3 qual days)"
        )
    else:
        verdict = "tweak" if total_net > 0 else "drop"
        why = (
            f"net ${total_net:.2f}, WR {win_rate:.1f}%, n={len(all_trades)}, "
            f"qual_days={qualified_days}"
        )

    calendar_span = (latest_bar.date() - earliest_bar.date()).days + 1
    yf_note = (
        f"yfinance 5m returned {len(m5)} bars spanning ~{calendar_span} calendar days "
        f"({earliest_bar.isoformat()} → {latest_bar.isoformat()}). "
        f"Requested ≥{TARGET_DAYS} trading days; got {len(days)}. "
        + (
            "5m history is capped (~60 calendar days); could not invent bars before earliest."
            if len(days) < TARGET_DAYS
            else "Full requested window available."
        )
    )

    summary = {
        "symbol_key": "mbt",
        "ticker": TICKER,
        "symbol_name": "Micro Bitcoin",
        "point_value": POINT_VALUE,
        "point_value_verified": True,
        "contracts": CONTRACTS,
        "variant": "apex_v26_kz",
        "variant_label": "Apex v2.6 LDLZ+NYKZ (HTF+structure TP, risk $100, TP cap $300)",
        "constraints": {
            "contracts": 1,
            "bracket_only": True,
            "daily_kill": DAILY_KILL,
            "daily_tp": DAILY_TP_CAP,
            "skip_t1_chase": True,
            "no_scale_average": True,
            "ldlz": "02:00–05:00 NY",
            "nykz": "08:30–11:00 NY",
        },
        "period_end": END_DATE.isoformat(),
        "n_trading_days_requested": TARGET_DAYS,
        "n_trading_days_used": len(days),
        "trading_days_covered": len(days),
        "earliest_bar_timestamp": earliest_bar.isoformat(),
        "latest_bar_timestamp": latest_bar.isoformat(),
        "first_day": days[0].isoformat() if days else None,
        "last_day": days[-1].isoformat() if days else None,
        "data_first_bar": earliest_bar.isoformat(),
        "data_last_bar": latest_bar.isoformat(),
        "n_5m_bars": int(len(m5)),
        "calendar_span_days": calendar_span,
        "yfinance_5m_note": yf_note,
        "goes_before_aug_17": (days[0] < date(2026, 8, 17)) if days else False,
        "total_net_pnl": round(total_net, 2),
        "max_dd_usd": round(max_dd, 2),
        "win_rate_pct": round(win_rate, 2),
        "avg_r": round(avg_r, 4),
        "expectancy_usd": round(expectancy, 4),
        "n_trades": len(all_trades),
        "n_wins": len(wins),
        "n_losses": len(losses),
        "n_flats": len(flats),
        "best_day": {"date": best_day[0], "pnl": round(best_day[1], 2)},
        "worst_day": {"date": worst_day[0], "pnl": round(worst_day[1], 2)},
        "qualified_days_ge_250": qualified_days,
        "cumulative_ge_3000": total_net >= 3000.0,
        "max_dd_vs_2000_trail_breach": trail_breach,
        "session_breakdown": {k: tag_stats(v) for k, v in by_tag.items()},
        "month_breakdown": month_breakdown,
        "week_breakdown": week_breakdown,
        "status_counts": {
            s: sum(1 for r in day_results if r["status"] == s)
            for s in sorted({r["status"] for r in day_results})
        },
        "verdict": verdict,
        "verdict_why": why,
    }
    return summary, all_trades, day_results


def write_outputs(summary: dict, trades: list, days: list) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summary, "trades": trades, "days": days}
    (OUT / "report.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    lines = [
        f"# {summary['ticker']} — Extended {summary['variant_label']}",
        "",
        f"**Generated:** {datetime.now(NY).strftime('%Y-%m-%d %H:%M:%S %Z')}  ",
        f"**Symbol:** {summary['ticker']} · 1 Micro (${summary['point_value']}/pt verified) · 5m yfinance  ",
        f"**Window:** {summary['first_day']} → {summary['last_day']} "
        f"({summary['trading_days_covered']} trading days)  ",
        f"**Earliest bar in dataset:** `{summary['earliest_bar_timestamp']}`  ",
        f"**Latest bar in dataset:** `{summary['latest_bar_timestamp']}`  ",
        f"**5m bars:** {summary['n_5m_bars']} · calendar span ~{summary['calendar_span_days']}d  ",
        "",
        f"> {summary['yfinance_5m_note']}",
        "",
        "## Hard constraints",
        "",
        "- 1 Micro fixed · brackets only · daily **−$100 / +$300** · skip T1 chase · no scale/average",
        "- Killzones: LDLZ 02:00–05:00 NY + NYKZ 08:30–11:00 NY",
        "- TP reward capped at $300 · Same-bar SL first",
        "",
        "## Headline metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| earliest_bar_timestamp | `{summary['earliest_bar_timestamp']}` |",
        f"| trading_days_covered | {summary['trading_days_covered']} |",
        f"| net P&L | ${summary['total_net_pnl']:.2f} |",
        f"| max DD | ${summary['max_dd_usd']:.2f} |",
        f"| $2k trail breach | {'Y' if summary['max_dd_vs_2000_trail_breach'] else 'N'} |",
        f"| qualified days ≥$250 | {summary['qualified_days_ge_250']} |",
        f"| WR | {summary['win_rate_pct']:.2f}% ({summary['n_wins']}W/{summary['n_losses']}L/{summary['n_flats']}F) |",
        f"| avg R | {summary['avg_r']:.4f} |",
        f"| worst day | {summary['worst_day']['date']} (${summary['worst_day']['pnl']:.2f}) |",
        f"| best day | {summary['best_day']['date']} (${summary['best_day']['pnl']:.2f}) |",
        f"| cum≥$3000 | {'Y' if summary['cumulative_ge_3000'] else 'N'} |",
        f"| n_trades | {summary['n_trades']} |",
        f"| expectancy $/trade | ${summary['expectancy_usd']:.4f} |",
        "",
        "## Month-by-month P&L",
        "",
        "| Month | Days | Trades | P&L |",
        "|---|---|---|---|",
    ]
    for m in summary["month_breakdown"]:
        lines.append(f"| {m['month']} | {m['n_days']} | {m['n_trades']} | ${m['pnl']:.2f} |")

    lines += [
        "",
        "## Week-by-week P&L",
        "",
        "| Week (ISO) | Days | Trades | P&L |",
        "|---|---|---|---|",
    ]
    for w in summary["week_breakdown"]:
        lines.append(f"| {w['week']} | {w['n_days']} | {w['n_trades']} | ${w['pnl']:.2f} |")

    lines += [
        "",
        "## Session tags",
        "",
        "| Tag | # | P&L | Win% | Avg R |",
        "|---|---|---|---|---|",
    ]
    for tag in ("LDLZ", "NYKZ", "other"):
        s = summary["session_breakdown"][tag]
        lines.append(
            f"| {tag} | {s['n']} | ${s['pnl']:.2f} | {s['win_rate']:.2f}% | {s['avg_r']:.4f} |"
        )

    lines += ["", "## Status counts", ""]
    for k, v in summary["status_counts"].items():
        lines.append(f"- `{k}`: {v}")

    lines += ["", "## Trades", ""]
    if not trades:
        lines.append("_No trades._")
    else:
        lines.append(
            "| Date | Dir | Entry NY | Tag | Pattern | Entry | SL | TP | Exit | Why | P&L | R |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for t in trades:
            et = pd.Timestamp(t["entry_time"])
            if et.tzinfo is None:
                et = et.tz_localize(NY)
            else:
                et = et.tz_convert(NY)
            lines.append(
                f"| {t['date']} | {t['direction']} | {et.strftime('%H:%M')} | "
                f"{t['session_tag']} | {t.get('pattern')} | "
                f"{t['entry']:.2f} | {t['sl']:.2f} | {t['tp']:.2f} | {t['exit']:.2f} | "
                f"{t['exit_reason']} | ${t['pnl_usd']:.2f} | {t['r_multiple']:.2f} |"
            )

    lines += [
        "",
        "## Daily P&L",
        "",
        "| Date | Status | Day P&L | Grade | #Trades |",
        "|---|---|---|---|---|",
    ]
    for r in days:
        lines.append(
            f"| {r['date']} | {r['status']} | ${r['day_pnl']:.2f} | "
            f"{r.get('grade')} | {len(r['trades'])} |"
        )

    lines += [
        "",
        "## VERDICT",
        "",
        f"**{summary['verdict']}** — {summary['verdict_why']}",
        "",
    ]
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    print("=== MBT extended apex_v26_kz (max 5m history) ===")
    summary, trades, days = run()
    write_outputs(summary, trades, days)
    print(json.dumps({
        "earliest_bar_timestamp": summary["earliest_bar_timestamp"],
        "trading_days_covered": summary["trading_days_covered"],
        "net": summary["total_net_pnl"],
        "max_dd": summary["max_dd_usd"],
        "trail_breach": summary["max_dd_vs_2000_trail_breach"],
        "qual_days": summary["qualified_days_ge_250"],
        "WR": summary["win_rate_pct"],
        "avg_r": summary["avg_r"],
        "worst": summary["worst_day"],
        "best": summary["best_day"],
        "cum_ge_3000": summary["cumulative_ge_3000"],
        "months": summary["month_breakdown"],
        "verdict": summary["verdict"],
        "why": summary["verdict_why"],
        "note": summary["yfinance_5m_note"],
        "out": str(OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
