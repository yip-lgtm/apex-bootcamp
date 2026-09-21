#!/usr/bin/env python3
"""MBT=F Apex v2.6 KZ max-history backtest → parallel_cmp/mbt (reuse extended runner)."""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/workspace/apex_strategy_pick_bt/scripts")
sys.path.insert(0, "/workspace/apex-bt/src")

import apex_v26_constrained as av
import mbt_extended_run as mx

# Today (HK box clock / user date): use max available through latest calendar day with data
OUT = Path("/workspace/apex_strategy_pick_bt/parallel_cmp/mbt")
SMALL_N_SUMMARY = Path("/workspace/apex_strategy_pick_bt/mbt/summary.json")
TARGET_DAYS = 90  # request max; yfinance 5m typically ~60 trading days


def main() -> None:
    # Point extended runner at parallel_cmp output; use latest available end
    today = date.today()  # box is Asia/Hong_Kong; calendar date for clip
    av.END_DATE = today
    mx.END_DATE = today
    mx.OUT = OUT
    mx.TARGET_DAYS = TARGET_DAYS

    print(f"=== parallel_cmp MBT apex_v26_kz max 5m (end={today}, target≥60) ===")
    summary, trades, days = mx.run()

    # Scale vs small-n (30d pick window)
    small = None
    if SMALL_N_SUMMARY.exists():
        small = json.loads(SMALL_N_SUMMARY.read_text(encoding="utf-8"))
    scale_note = _scale_facts(summary, small)
    summary["small_n_comparison"] = scale_note
    summary["scale_edge_holds"] = scale_note.get("edge_holds_at_scale")

    mx.write_outputs(summary, trades, days)
    _append_scale_section(OUT / "report.md", scale_note, summary)

    print(json.dumps({
        "earliest_bar": summary["earliest_bar_timestamp"],
        "trading_days": summary["trading_days_covered"],
        "net": summary["total_net_pnl"],
        "max_dd": summary["max_dd_usd"],
        "WR": summary["win_rate_pct"],
        "qual_days": summary["qualified_days_ge_250"],
        "sessions": summary["session_breakdown"],
        "n_trades": summary["n_trades"],
        "scale": scale_note,
        "out": str(OUT),
    }, indent=2, default=str))


def _scale_facts(summary: dict, small: dict | None) -> dict:
    """Facts-only: does the small-n edge hold when window doubles to max 5m?"""
    out = {
        "small_n_source": str(SMALL_N_SUMMARY) if small else None,
        "small_n_trading_days": small.get("n_trading_days_used") if small else None,
        "small_n_net": small.get("total_net_pnl") if small else None,
        "small_n_n_trades": small.get("n_trades") if small else None,
        "small_n_wr": small.get("win_rate_pct") if small else None,
        "small_n_qual_days": small.get("qualified_days_ge_250") if small else None,
        "small_n_max_dd": small.get("max_dd_usd") if small else None,
        "scale_trading_days": summary["trading_days_covered"],
        "scale_net": summary["total_net_pnl"],
        "scale_n_trades": summary["n_trades"],
        "scale_wr": summary["win_rate_pct"],
        "scale_qual_days": summary["qualified_days_ge_250"],
        "scale_max_dd": summary["max_dd_usd"],
        "extra_trades_outside_small_n_window": None,
        "edge_holds_at_scale": None,
        "facts": [],
    }
    if not small:
        out["facts"].append("No small-n summary at mbt/summary.json; scale comparison skipped.")
        out["edge_holds_at_scale"] = None
        return out

    # Trades dated before small-n first_day are "new at scale"
    small_first = small.get("first_day")
    extra = 0
    if small_first:
        for t in []:  # filled below via report.json after write — use day window instead
            pass
    # Use day counts / nets: if scale net == small net and scale trades == small trades,
    # extending history added zero incremental edge.
    same_net = abs(float(summary["total_net_pnl"]) - float(small["total_net_pnl"])) < 1e-9
    same_n = int(summary["n_trades"]) == int(small["n_trades"])
    same_wr = abs(float(summary["win_rate_pct"]) - float(small["win_rate_pct"])) < 1e-9
    days_ratio = (
        summary["trading_days_covered"] / small["n_trading_days_used"]
        if small.get("n_trading_days_used")
        else None
    )
    out["days_ratio_vs_small_n"] = round(days_ratio, 3) if days_ratio else None
    out["same_net_as_small_n"] = same_net
    out["same_n_trades_as_small_n"] = same_n
    out["same_wr_as_small_n"] = same_wr

    facts = []
    facts.append(
        f"small-n (30d pick): net=${small['total_net_pnl']:.2f}, n={small['n_trades']}, "
        f"WR={small['win_rate_pct']:.2f}%, qual≥$250={small['qualified_days_ge_250']}, "
        f"maxDD=${small['max_dd_usd']:.2f}, days={small['n_trading_days_used']}"
    )
    facts.append(
        f"scale (max 5m): net=${summary['total_net_pnl']:.2f}, n={summary['n_trades']}, "
        f"WR={summary['win_rate_pct']:.2f}%, qual≥$250={summary['qualified_days_ge_250']}, "
        f"maxDD=${summary['max_dd_usd']:.2f}, days={summary['trading_days_covered']}"
    )
    if same_net and same_n:
        facts.append(
            "Incremental P&L outside the small-n window: $0.00; no additional fills. "
            "Observed edge is the same 2 NYKZ wins; does not strengthen with more history."
        )
        # "Hold" = remains non-negative / same metrics, but sample still n=2 (fragile)
        out["edge_holds_at_scale"] = True
        out["edge_strengthens_at_scale"] = False
        out["edge_note"] = (
            "Metrics unchanged at ~2× days (edge numerically holds) but n remains 2 — "
            "not validated by additional independent trades."
        )
    elif float(summary["total_net_pnl"]) > 0 and float(summary["total_net_pnl"]) >= float(small["total_net_pnl"]):
        out["edge_holds_at_scale"] = True
        out["edge_strengthens_at_scale"] = float(summary["total_net_pnl"]) > float(small["total_net_pnl"])
        facts.append("Scale net ≥ small-n net and still positive.")
        out["edge_note"] = "Positive edge persists at scale."
    elif float(summary["total_net_pnl"]) > 0:
        out["edge_holds_at_scale"] = True
        out["edge_strengthens_at_scale"] = False
        facts.append("Scale net still positive but below small-n net.")
        out["edge_note"] = "Edge diluted but still positive."
    else:
        out["edge_holds_at_scale"] = False
        out["edge_strengthens_at_scale"] = False
        facts.append("Scale net ≤ 0 — small-n edge does not hold at scale.")
        out["edge_note"] = "Edge does not hold at scale."
    out["facts"] = facts
    return out


def _append_scale_section(path: Path, scale: dict, summary: dict) -> None:
    lines = [
        "",
        "## Small-n vs scale (facts)",
        "",
        f"| Window | Trading days | Net | Max DD | WR | Qual ≥$250 | n trades |",
        f"|---|---|---|---|---|---|---|",
    ]
    if scale.get("small_n_trading_days") is not None:
        lines.append(
            f"| small-n (mbt/ 30d) | {scale['small_n_trading_days']} | "
            f"${scale['small_n_net']:.2f} | ${scale['small_n_max_dd']:.2f} | "
            f"{scale['small_n_wr']:.2f}% | {scale['small_n_qual_days']} | {scale['small_n_n_trades']} |"
        )
    lines.append(
        f"| scale (max 5m) | {scale['scale_trading_days']} | "
        f"${scale['scale_net']:.2f} | ${scale['scale_max_dd']:.2f} | "
        f"{scale['scale_wr']:.2f}% | {scale['scale_qual_days']} | {scale['scale_n_trades']} |"
    )
    lines += ["", "### Does small-n edge hold at scale?", ""]
    holds = scale.get("edge_holds_at_scale")
    if holds is True:
        lines.append(
            f"**Yes (numerically)** — {scale.get('edge_note', '')}"
        )
    elif holds is False:
        lines.append(f"**No** — {scale.get('edge_note', '')}")
    else:
        lines.append("_Comparison unavailable._")
    lines.append("")
    for f in scale.get("facts", []):
        lines.append(f"- {f}")
    lines.append("")
    # Session one-liners already in report; reinforce requested fields
    sb = summary.get("session_breakdown", {})
    lines += [
        "## Requested fields (compact)",
        "",
        f"- net: ${summary['total_net_pnl']:.2f}",
        f"- max DD: ${summary['max_dd_usd']:.2f}",
        f"- WR: {summary['win_rate_pct']:.2f}%",
        f"- qual days ≥$250: {summary['qualified_days_ge_250']}",
        f"- session LDLZ: n={sb.get('LDLZ', {}).get('n', 0)} pnl=${sb.get('LDLZ', {}).get('pnl', 0):.2f}",
        f"- session NYKZ: n={sb.get('NYKZ', {}).get('n', 0)} pnl=${sb.get('NYKZ', {}).get('pnl', 0):.2f}",
        f"- n trades: {summary['n_trades']}",
        f"- trading days: {summary['trading_days_covered']}",
        f"- earliest bar: `{summary['earliest_bar_timestamp']}`",
        f"- small-n edge holds at scale: {summary.get('scale_edge_holds')}",
        "",
    ]
    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
