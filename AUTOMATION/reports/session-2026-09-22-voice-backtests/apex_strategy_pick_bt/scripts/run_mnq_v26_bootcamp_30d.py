#!/usr/bin/env python3
"""MNQ-only Apex Bootcamp v2.6 constrained 30d backtest → mnq_v26_bootcamp_30d/."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/workspace/apex_strategy_pick_bt/scripts")
from apex_v26_constrained import (  # noqa: E402
    END_DATE,
    N_TRADING_DAYS,
    NY,
    run_symbol,
)

OUT = Path("/workspace/apex_strategy_pick_bt/mnq_v26_bootcamp_30d")
CHANGELOG_CLAIM = {
    "source": "apex-bootcamp/AUTOMATION/docs/STRATEGY.md §9 + sample-backtest-v2.6.md",
    "claim": "+$3,920 / 60d, 52% hit (portfolio MGC+MNQ+MBT+MCL)",
    "window": "2026-06-02 → 2026-08-01 (~60 calendar days)",
    "portfolio_net": 3920.0,
    "portfolio_wr_pct": 51.7,
    "mnq_only_net": 1883.0,
    "mnq_only_trades": 21,
    "mnq_only_wr_pct": 42.9,
    "engine_note": (
        "Changelog v2.6 sample used NY AM killzone 09:00–11:00 EST and TP up to $500; "
        "this constrained run uses LDLZ 02:00–05:00 NY + NYKZ 08:30–11:00 NY, "
        "daily TP cap +$300, skip C, skip chase past T1/TP, 1 Micro brackets."
    ),
}


def month_breakdown(trades: list, day_results: list) -> list[dict]:
    by_m: dict[str, dict] = {}
    for r in day_results:
        m = r["date"][:7]
        b = by_m.setdefault(
            m,
            {"month": m, "days": 0, "traded_days": 0, "pnl": 0.0, "n_trades": 0, "wins": 0, "losses": 0},
        )
        b["days"] += 1
        b["pnl"] += float(r["day_pnl"])
        if r["status"] == "traded":
            b["traded_days"] += 1
    for t in trades:
        m = t["date"][:7]
        b = by_m[m]
        b["n_trades"] += 1
        if t["pnl_usd"] > 0:
            b["wins"] += 1
        elif t["pnl_usd"] < 0:
            b["losses"] += 1
    out = []
    for m in sorted(by_m):
        b = by_m[m]
        n = b["n_trades"]
        out.append(
            {
                "month": m,
                "session_days": b["days"],
                "traded_days": b["traded_days"],
                "n_trades": n,
                "wins": b["wins"],
                "losses": b["losses"],
                "win_rate_pct": round((b["wins"] / n * 100.0) if n else 0.0, 2),
                "pnl": round(b["pnl"], 2),
            }
        )
    return out


def main():
    print("Fetching MNQ=F via yfinance (no Tradovate/Ninja OHLC bars found on box)...")
    summary, trades, days = run_symbol("mnq")
    months = month_breakdown(trades, days)

    # Data source statement
    data_source = {
        "primary_requested": "Tradovate/NinjaTrader bars on machine",
        "primary_found": False,
        "actual_source": "yfinance",
        "ticker": "MNQ=F",
        "interval": "5m",
        "note": (
            "Searched /workspace and /home/box for MNQ/NQ OHLC csv/parquet/json bars; "
            "only Tradovate UI screenshot extracts found (no bar series). "
            "Fell back to yfinance MNQ=F 5m."
        ),
        "dual_run": False,
        "dual_run_reason": "No second OHLC source present for comparison",
    }

    # Changelog hold check for LAST 30d
    net = float(summary["total_net_pnl"])
    # Pro-rata of portfolio claim over 30/60 ≈ half; also compare MNQ-only half of prior MNQ
    pro_rata_portfolio_30d = CHANGELOG_CLAIM["portfolio_net"] * (30 / 60)
    pro_rata_mnq_30d = CHANGELOG_CLAIM["mnq_only_net"] * (30 / 60)
    holds_portfolio_scale = net >= pro_rata_portfolio_30d * 0.8  # soft? NO — explicit answer
    # Explicit: does ~$3900/60d hold for LAST 30d?
    # Answer is about whether last 30d performance is consistent with that claim.
    holds = bool(net >= 3000)  # if last 30d alone already near half+ of 60d claim's order
    # Better explicit logic:
    # Claim was ~$3920 over 60d portfolio. For LAST 30d MNQ-only under caller constraints:
    # - Does NOT hold if net << claim scale
    changelog_answer = {
        "question": "Does old changelog ~$3,900/60d hold for LAST 30d?",
        "answer": "NO",
        "rationale": (
            f"Last-30d MNQ-only constrained net=${net:.2f} vs changelog portfolio "
            f"${CHANGELOG_CLAIM['portfolio_net']:.0f}/60d (and MNQ-only ${CHANGELOG_CLAIM['mnq_only_net']:.0f}/60d "
            f"in sample). Pro-rata 30d portfolio≈${pro_rata_portfolio_30d:.0f}, MNQ≈${pro_rata_mnq_30d:.0f}. "
            f"Last 30d is far below both; claim does not hold for this window under caller constraints."
        ),
        "last_30d_net": net,
        "changelog_60d_portfolio_net": CHANGELOG_CLAIM["portfolio_net"],
        "changelog_60d_mnq_net": CHANGELOG_CLAIM["mnq_only_net"],
        "pro_rata_30d_portfolio": round(pro_rata_portfolio_30d, 2),
        "pro_rata_30d_mnq": round(pro_rata_mnq_30d, 2),
        "caveats": CHANGELOG_CLAIM["engine_note"],
    }
    # Override answer YES only if clearly holds
    if net >= pro_rata_portfolio_30d * 0.9:
        changelog_answer["answer"] = "YES"
        changelog_answer["rationale"] = (
            f"Last-30d net ${net:.2f} is within ~10% of pro-rata portfolio ${pro_rata_portfolio_30d:.0f}."
        )
    elif net >= pro_rata_mnq_30d * 0.9:
        changelog_answer["answer"] = "PARTIAL (MNQ-scale only)"
        changelog_answer["rationale"] = (
            f"Last-30d MNQ ${net:.2f} near pro-rata MNQ ${pro_rata_mnq_30d:.0f}, "
            f"but not the portfolio ~$3900/60d claim."
        )
    else:
        changelog_answer["answer"] = "NO"

    verdict_line = f"{summary['verdict']} — {summary['verdict_why']}"

    payload = {
        "generated_at_ny": datetime.now(NY).strftime("%Y-%m-%d %H:%M:%S %Z"),
        "strategy": "Apex Bootcamp v2.6 (constrained)",
        "constraints": {
            "risk_usd_per_trade": 100,
            "tp_envelope_usd": [200, 500],
            "daily_kill_usd": -100,
            "daily_tp_cap_usd": 300,
            "rr": [2, 5],
            "contracts": "1 Micro fixed",
            "brackets_only": True,
            "no_scale_average": True,
            "htf_alignment_required": True,
            "killzones": ["LDLZ 02:00–05:00 NY", "NYKZ 08:30–11:00 NY"],
            "grades": "A/B only, skip C",
            "skip_chase_past_t1_tp": True,
        },
        "period": {
            "end": END_DATE.isoformat(),
            "n_trading_days_requested": N_TRADING_DAYS,
            "n_trading_days_used": summary["n_trading_days_used"],
            "first_day": summary["first_day"],
            "last_day": summary["last_day"],
            "earliest_bar_timestamp": summary["data_first_bar"],
            "latest_bar_timestamp": summary["data_last_bar"],
        },
        "data_source": data_source,
        "metrics": {
            "net_pnl": summary["total_net_pnl"],
            "max_dd_usd": summary["max_dd_usd"],
            "max_dd_vs_2k_trail_breach": summary["max_dd_vs_2000_trail_breach"],
            "qualified_days_ge_250": summary["qualified_days_ge_250"],
            "win_rate_pct": summary["win_rate_pct"],
            "avg_r": summary["avg_r"],
            "expectancy_usd": summary["expectancy_usd"],
            "n_trades": summary["n_trades"],
            "n_wins": summary["n_wins"],
            "n_losses": summary["n_losses"],
            "n_flats": summary["n_flats"],
            "best_day": summary["best_day"],
            "worst_day": summary["worst_day"],
            "cumulative_ge_3000": summary["cumulative_ge_3000"],
        },
        "ldlz_vs_nykz": summary["session_breakdown"],
        "month_by_month": months,
        "status_counts": summary["status_counts"],
        "changelog_comparison": {
            **CHANGELOG_CLAIM,
            "last_30d_vs_claim": changelog_answer,
        },
        "verdict": summary["verdict"],
        "verdict_one_line": verdict_line,
        "summary_raw": summary,
        "trades": trades,
        "days": days,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    sb = summary["session_breakdown"]
    lines = [
        "# Apex Bootcamp v2.6 — MNQ 5m constrained 30-trading-day backtest",
        "",
        f"**Generated:** {payload['generated_at_ny']}  ",
        f"**Symbol:** MNQ=F · 1 Micro ($2/pt) · brackets only  ",
        f"**Window:** {summary['first_day']} → {summary['last_day']} "
        f"({summary['n_trading_days_used']} trading days, end {END_DATE.isoformat()})  ",
        f"**Earliest bar:** `{summary['data_first_bar']}`  ",
        f"**Latest bar:** `{summary['data_last_bar']}`  ",
        f"**Data source:** **yfinance** (no Tradovate/Ninja OHLC bar series found on machine; "
        f"UI screenshot extracts only — dual-run skipped)  ",
        "",
        "## Caller constraints (exact)",
        "",
        "- Risk **$100**/trade · TP envelope **$200–$500** · daily kill **−$100** · daily TP cap **+$300**",
        "- RR **2–5** · **1 Micro** fixed · brackets only · no scale/average",
        "- HTF alignment required · A/B only (skip C) · skip chase past T1/TP",
        "- Killzones: **LDLZ 02:00–05:00 NY** + **NYKZ 08:30–11:00 NY**",
        "",
        "## Headline metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Net P&L | ${summary['total_net_pnl']:.2f} |",
        f"| Max DD vs $2k trail | ${summary['max_dd_usd']:.2f} "
        f"(breach={summary['max_dd_vs_2000_trail_breach']}) |",
        f"| Qual days ≥$250 | {summary['qualified_days_ge_250']} |",
        f"| Win rate | {summary['win_rate_pct']:.2f}% "
        f"({summary['n_wins']}W / {summary['n_losses']}L / {summary['n_flats']}F) |",
        f"| Avg R | {summary['avg_r']:.4f} |",
        f"| Expectancy $/trade | ${summary['expectancy_usd']:.4f} |",
        f"| # Trades | {summary['n_trades']} |",
        f"| Best day | {summary['best_day']['date']} (${summary['best_day']['pnl']:.2f}) |",
        f"| Worst day | {summary['worst_day']['date']} (${summary['worst_day']['pnl']:.2f}) |",
        f"| Cum ≥ $3000? | {'Y' if summary['cumulative_ge_3000'] else 'N'} |",
        "",
        "## LDLZ vs NYKZ",
        "",
        "| Tag | # | P&L | Win% | Avg R |",
        "|---|---|---|---|---|",
    ]
    for tag in ("LDLZ", "NYKZ", "other"):
        s = sb[tag]
        lines.append(
            f"| {tag} | {s['n']} | ${s['pnl']:.2f} | {s['win_rate']:.2f}% | {s['avg_r']:.4f} |"
        )

    lines += [
        "",
        "## Month-by-month",
        "",
        "| Month | Session days | Traded days | Trades | W/L | WR% | P&L |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in months:
        lines.append(
            f"| {m['month']} | {m['session_days']} | {m['traded_days']} | {m['n_trades']} | "
            f"{m['wins']}/{m['losses']} | {m['win_rate_pct']:.2f}% | ${m['pnl']:.2f} |"
        )

    lines += [
        "",
        "## Status counts",
        "",
    ]
    for k, v in summary["status_counts"].items():
        lines.append(f"- `{k}`: {v}")

    lines += [
        "",
        "## Changelog ~$3,900/60d vs LAST 30d",
        "",
        f"- **Prior claim:** {CHANGELOG_CLAIM['claim']} ({CHANGELOG_CLAIM['window']})",
        f"- **Prior MNQ-only in that sample:** ${CHANGELOG_CLAIM['mnq_only_net']:.0f} "
        f"/ {CHANGELOG_CLAIM['mnq_only_trades']} trades / {CHANGELOG_CLAIM['mnq_only_wr_pct']}% WR",
        f"- **This run (last 30 trading days, MNQ, caller constraints):** "
        f"net **${net:.2f}**, WR {summary['win_rate_pct']:.2f}%, n={summary['n_trades']}",
        f"- **Pro-rata 30d refs:** portfolio ≈ ${pro_rata_portfolio_30d:.0f}; "
        f"MNQ ≈ ${pro_rata_mnq_30d:.0f}",
        f"- **Explicit answer: {changelog_answer['answer']}** — {changelog_answer['rationale']}",
        f"- Caveat: {CHANGELOG_CLAIM['engine_note']}",
        "",
        "## Trades",
        "",
    ]
    if not trades:
        lines.append("_No trades._")
    else:
        lines.append(
            "| Date | Dir | Entry NY | Tag | Pattern | Grade | Entry | SL | TP | Exit | Why | P&L | R |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for t in trades:
            et = pd.Timestamp(t["entry_time"]).tz_convert(NY).strftime("%H:%M")
            lines.append(
                f"| {t['date']} | {t['direction']} | {et} | {t['session_tag']} | "
                f"{t.get('pattern')} | {t.get('grade')} | {t['entry']:.2f} | {t['sl']:.2f} | "
                f"{t['tp']:.2f} | {t['exit']:.2f} | {t['exit_reason']} | "
                f"${t['pnl_usd']:.2f} | {t['r_multiple']:.2f} |"
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
            f"| {r['date']} | {r['status']} | ${r['day_pnl']:.2f} | {r.get('grade')} | {len(r['trades'])} |"
        )

    lines += [
        "",
        "## VERDICT",
        "",
        f"**{verdict_line}**",
        "",
    ]
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "out": str(OUT),
        "net": summary["total_net_pnl"],
        "max_dd": summary["max_dd_usd"],
        "qual_days": summary["qualified_days_ge_250"],
        "wr": summary["win_rate_pct"],
        "avg_r": summary["avg_r"],
        "n": summary["n_trades"],
        "cum_ge_3000": summary["cumulative_ge_3000"],
        "earliest_bar": summary["data_first_bar"],
        "changelog_holds": changelog_answer["answer"],
        "verdict": verdict_line,
        "months": months,
        "sessions": sb,
    }, indent=2))


if __name__ == "__main__":
    main()
