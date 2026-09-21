#!/usr/bin/env python3
"""Apex v2.6 LDLZ+NYKZ under hard constraints for strategy pick.

Hard constraints:
- 1 Micro fixed
- Bracket SL/TP (risk $100, TP reward capped to daily +$300 envelope)
- Daily kill -$100 / daily TP +$300: no new entries that day
- Skip T1 chase (entry fill already past TP)
- No scale / average
- Session tags LDLZ / NYKZ
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, "/workspace/apex-bt/src")
from apex_backtest import (  # noqa: E402
    DAILY_KILL_SWITCH,
    RISK_USD,
    detect_trigger,
    fetch,
    grade_setup,
)

ROOT = Path("/workspace/apex_strategy_pick_bt")
NY = ZoneInfo("America/New_York")
END_DATE = date(2026, 9, 21)
N_TRADING_DAYS = 30
CONTRACTS = 1
DAILY_KILL = -100.0
DAILY_TP_CAP = 300.0
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)

SYMBOLS = {
    "mnq": ("MNQ=F", 2.0, "Micro Nasdaq", None),
    "mgc": ("MGC=F", 10.0, "Micro Gold", None),
    "mbt": ("MBT=F", 0.1, "Micro Bitcoin", "MBT=F available via yfinance"),
}


def tag_session(ts) -> str:
    if ts is None:
        return "other"
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize(NY)
    else:
        t = t.tz_convert(NY)
    tm = t.time()
    if time(2, 0) <= tm < time(5, 0):
        return "LDLZ"
    if time(8, 30) <= tm < time(11, 0):
        return "NYKZ"
    return "other"


def session_dates_from_m5(m5: pd.DataFrame, end: date, n: int) -> list[date]:
    # Prefer RTH presence; fall back to any bars that day
    rth = m5[(m5.index.time >= RTH_OPEN) & (m5.index.time < RTH_CLOSE)]
    days = sorted({d.date() for d in (rth.index if len(rth) else m5.index)})
    days = [d for d in days if d <= end]
    return days if len(days) < n else days[-n:]


def max_drawdown_from_zero(pnls: list[float]) -> float:
    equity = [0.0]
    cum = 0.0
    for p in pnls:
        cum += p
        equity.append(cum)
    peak = equity[0]
    max_dd = 0.0
    for x in equity:
        peak = max(peak, x)
        max_dd = max(max_dd, peak - x)
    return max_dd


def execute_same_day(setup: dict, m5_exec: pd.DataFrame, point_value: float) -> dict | None:
    """Enter next bar open after trigger; skip if chase past TP; SL-first same bar."""
    if m5_exec.empty:
        return None
    first = m5_exec.iloc[0]
    entry = float(first["Open"])
    bias = setup["bias"]
    sl_dist = setup["sl_dist"]
    # Cap TP reward at DAILY_TP_CAP so a single fill can't exceed daily target by design
    tp_reward = min(float(setup["reward_usd"]), DAILY_TP_CAP)
    tp_dist = tp_reward / point_value / CONTRACTS

    if bias == "LONG":
        sl = entry - sl_dist
        tp = entry + tp_dist
        if entry >= tp:  # chase
            return {"skip_reason": "chase_past_tp", "entry_fill": entry, "tp": tp, "sl": sl}
    else:
        sl = entry + sl_dist
        tp = entry - tp_dist
        if entry <= tp:
            return {"skip_reason": "chase_past_tp", "entry_fill": entry, "tp": tp, "sl": sl}

    def calc_pnl(exit_px):
        diff = (exit_px - entry) if bias == "LONG" else (entry - exit_px)
        return diff * point_value * CONTRACTS

    # Manage from bar AFTER entry bar
    rest = m5_exec.iloc[1:]
    if rest.empty:
        # only entry bar — mark EOD at its close
        px = float(first["Close"])
        return {
            "entry_fill": entry, "exit_price": px, "exit_reason": "EOD",
            "pnl_usd": calc_pnl(px), "exit_time": first.name, "sl": sl, "tp": tp,
            "risk_usd": sl_dist * point_value * CONTRACTS,
            "reward_usd": tp_dist * point_value * CONTRACTS,
            "r_multiple": calc_pnl(px) / (sl_dist * point_value * CONTRACTS),
        }

    for ts, bar in rest.iterrows():
        hi, lo = float(bar["High"]), float(bar["Low"])
        if bias == "LONG":
            hit_sl, hit_tp = lo <= sl, hi >= tp
            if hit_sl and hit_tp:
                return _fill(entry, sl, ts, "SL_samebar_ambiguous", calc_pnl, sl, tp, sl_dist, tp_dist, point_value)
            if hit_sl:
                return _fill(entry, sl, ts, "SL", calc_pnl, sl, tp, sl_dist, tp_dist, point_value)
            if hit_tp:
                return _fill(entry, tp, ts, "TP", calc_pnl, sl, tp, sl_dist, tp_dist, point_value)
        else:
            hit_sl, hit_tp = hi >= sl, lo <= tp
            if hit_sl and hit_tp:
                return _fill(entry, sl, ts, "SL_samebar_ambiguous", calc_pnl, sl, tp, sl_dist, tp_dist, point_value)
            if hit_sl:
                return _fill(entry, sl, ts, "SL", calc_pnl, sl, tp, sl_dist, tp_dist, point_value)
            if hit_tp:
                return _fill(entry, tp, ts, "TP", calc_pnl, sl, tp, sl_dist, tp_dist, point_value)

    last = rest.iloc[-1]
    px = float(last["Close"])
    return _fill(entry, px, last.name, "EOD", calc_pnl, sl, tp, sl_dist, tp_dist, point_value)


def _fill(entry, exit_px, ts, reason, calc_pnl, sl, tp, sl_dist, tp_dist, point_value):
    pnl = calc_pnl(exit_px)
    risk = sl_dist * point_value * CONTRACTS
    return {
        "entry_fill": entry,
        "exit_price": exit_px,
        "exit_reason": reason,
        "pnl_usd": pnl,
        "exit_time": ts,
        "sl": sl,
        "tp": tp,
        "risk_usd": risk,
        "reward_usd": tp_dist * point_value * CONTRACTS,
        "r_multiple": (pnl / risk) if risk else 0.0,
    }


def run_symbol(sym_key: str) -> tuple[dict, list, list]:
    ticker, pv, name, note = SYMBOLS[sym_key]
    end = pd.Timestamp(END_DATE)
    start = end - pd.Timedelta(days=50)
    data = fetch(ticker, start.strftime("%Y-%m-%d"), (end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    m5, daily = data["fivem"], data["daily"]
    if m5.empty:
        raise RuntimeError(f"no 5m data for {ticker}")

    days = session_dates_from_m5(m5, END_DATE, N_TRADING_DAYS)
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

        # One setup per day max under Apex mechanical (detect once at KZ)
        if day_pnl <= DAILY_KILL or day_pnl >= DAILY_TP_CAP:
            result["status"] = "daily_cap"
            day_results.append(result)
            continue

        trig = detect_trigger(m5, d_ts)
        if trig is None:
            result["status"] = "no_trigger"
            day_results.append(result)
            continue

        setup = grade_setup(trig, daily, d_ts, pv, m5, CONTRACTS)
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

        exec_res = execute_same_day(setup, post, pv)
        if exec_res is None:
            result["status"] = "no_exec"
            day_results.append(result)
            continue
        if exec_res.get("skip_reason") == "chase_past_tp":
            result["status"] = "skipped"
            result["skips"].append({"reason": "chase_past_tp", **{k: exec_res[k] for k in ("entry_fill", "tp", "sl") if k in exec_res}})
            day_results.append(result)
            continue

        entry_ts = post.index[0]
        kz = trig.get("killzone") or tag_session(entry_ts)
        # Prefer engine killzone label (trigger window); fall back to entry-time tag
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
            "exit_time": pd.Timestamp(exec_res["exit_time"]).isoformat() if exec_res.get("exit_time") is not None else None,
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

    # summarize
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
        why = f"net ${total_net:.2f}, WR {win_rate:.1f}%, n={len(all_trades)}, qual_days={qualified_days}"

    summary = {
        "symbol_key": sym_key,
        "ticker": ticker,
        "symbol_name": name,
        "ticker_note": note,
        "point_value": pv,
        "contracts": CONTRACTS,
        "variant": "apex_v26_kz",
        "variant_label": "Apex v2.6 LDLZ+NYKZ (HTF+structure TP, risk $100, TP cap $300)",
        "or_window": "N/A (pattern/KZ trigger)",
        "tp_rr": "structure/RR 2-5 capped @$300",
        "period_end": END_DATE.isoformat(),
        "n_trading_days_requested": N_TRADING_DAYS,
        "n_trading_days_used": len(days),
        "first_day": days[0].isoformat() if days else None,
        "last_day": days[-1].isoformat() if days else None,
        "data_first_bar": m5.index[0].isoformat(),
        "data_last_bar": m5.index[-1].isoformat(),
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
        "status_counts": {
            s: sum(1 for r in day_results if r["status"] == s)
            for s in sorted({r["status"] for r in day_results})
        },
        "verdict": verdict,
        "verdict_why": why,
    }
    return summary, all_trades, day_results


def write_report(out_dir: Path, summary: dict, trades: list, days: list):
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    with open(out_dir / "trades.json", "w") as f:
        json.dump({"summary": summary, "trades": trades, "days": days}, f, indent=2, default=str)

    lines = [
        f"# {summary['ticker']} — {summary['variant_label']}",
        "",
        f"**Generated:** {datetime.now(NY).strftime('%Y-%m-%d %H:%M:%S %Z')}  ",
        f"**Symbol:** {summary['ticker']} · 1 Micro (${summary['point_value']}/pt) · 5m yfinance  ",
        f"**Window:** {summary['first_day']} → {summary['last_day']} ({summary['n_trading_days_used']} days)  ",
    ]
    if summary.get("ticker_note"):
        lines.append(f"**Ticker note:** {summary['ticker_note']}  ")
    lines += [
        "",
        "## Hard constraints",
        "",
        "- 1 Micro · brackets · daily **−$100 / +$300** · skip T1 chase · no scale/average",
        "- Killzones: LDLZ 02:00–05:00 NY + NYKZ 08:30–11:00 NY (engine filter + tags)",
        "- TP reward capped at $300 · Same-bar SL first",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total net P&L | ${summary['total_net_pnl']:.2f} |",
        f"| Max DD $ | ${summary['max_dd_usd']:.2f} |",
        f"| Win rate | {summary['win_rate_pct']:.2f}% ({summary['n_wins']}W / {summary['n_losses']}L / {summary['n_flats']}F) |",
        f"| Avg R | {summary['avg_r']:.4f} |",
        f"| Expectancy $/trade | ${summary['expectancy_usd']:.4f} |",
        f"| # Trades | {summary['n_trades']} |",
        f"| Best day | {summary['best_day']['date']} (${summary['best_day']['pnl']:.2f}) |",
        f"| Worst day | {summary['worst_day']['date']} (${summary['worst_day']['pnl']:.2f}) |",
        f"| Qualified days (≥$250) | {summary['qualified_days_ge_250']} |",
        f"| Cum ≥ $3000? | {summary['cumulative_ge_3000']} |",
        f"| $2000 trail breach? | {summary['max_dd_vs_2000_trail_breach']} |",
        "",
        "## Session tags",
        "",
        "| Tag | # | P&L | Win% | Avg R |",
        "|---|---|---|---|---|",
    ]
    for tag in ("LDLZ", "NYKZ", "other"):
        s = summary["session_breakdown"][tag]
        lines.append(f"| {tag} | {s['n']} | ${s['pnl']:.2f} | {s['win_rate']:.2f}% | {s['avg_r']:.4f} |")
    lines += ["", "## Status counts", ""]
    for k, v in summary["status_counts"].items():
        lines.append(f"- `{k}`: {v}")
    lines += ["", "## Trades", ""]
    if not trades:
        lines.append("_No trades._")
    else:
        lines.append("| Date | Dir | Entry NY | Tag | Pattern | Entry | SL | TP | Exit | Why | P&L | R |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for t in trades:
            et = pd.Timestamp(t["entry_time"]).tz_convert(NY).strftime("%H:%M")
            lines.append(
                f"| {t['date']} | {t['direction']} | {et} | {t['session_tag']} | {t.get('pattern')} | "
                f"{t['entry']:.2f} | {t['sl']:.2f} | {t['tp']:.2f} | {t['exit']:.2f} | "
                f"{t['exit_reason']} | ${t['pnl_usd']:.2f} | {t['r_multiple']:.2f} |"
            )
    lines += ["", "## Daily P&L", "", "| Date | Status | Day P&L | Grade | #Trades |", "|---|---|---|---|---|"]
    for r in days:
        lines.append(f"| {r['date']} | {r['status']} | ${r['day_pnl']:.2f} | {r.get('grade')} | {len(r['trades'])} |")
    lines += ["", "## VERDICT", "", f"**{summary['verdict']}** — {summary['verdict_why']}", ""]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def rank_key(s: dict):
    no_breach = 0 if s["max_dd_vs_2000_trail_breach"] else 1
    return (s["qualified_days_ge_250"], no_breach, s["total_net_pnl"], s["expectancy_usd"])


def main():
    # Load ORB variant pick for comparison
    orb_pick_path = ROOT / "variants" / "mnq_pick.json"
    orb_summaries = []
    for key in ("base_15m", "variant_A_5m", "variant_B_30m_mid"):
        p = ROOT / "variants" / key / "summary.json"
        if p.exists():
            orb_summaries.append(json.loads(p.read_text()))

    print("=== Run apex_v26_kz on MNQ (strategy pick) ===")
    mnq_sum, mnq_tr, mnq_days = run_symbol("mnq")
    write_report(ROOT / "variants" / "apex_v26_kz", mnq_sum, mnq_tr, mnq_days)
    print(f"  MNQ apex: n={mnq_sum['n_trades']} net=${mnq_sum['total_net_pnl']} "
          f"qual={mnq_sum['qualified_days_ge_250']} exp=${mnq_sum['expectancy_usd']} → {mnq_sum['verdict']}")

    candidates = orb_summaries + [mnq_sum]
    best = max(candidates, key=rank_key)
    print(f"Best strategy: {best['variant']} net=${best['total_net_pnl']} qual={best['qualified_days_ge_250']}")

    pick = {
        "best_variant": best["variant"],
        "best_label": best.get("variant_label"),
        "ranking": sorted(
            [
                {
                    "variant": s["variant"],
                    "qualified_days_ge_250": s["qualified_days_ge_250"],
                    "trail_breach": s["max_dd_vs_2000_trail_breach"],
                    "total_net_pnl": s["total_net_pnl"],
                    "expectancy_usd": s["expectancy_usd"],
                    "n_trades": s["n_trades"],
                    "verdict": s["verdict"],
                }
                for s in candidates
            ],
            key=lambda x: (
                x["qualified_days_ge_250"],
                0 if x["trail_breach"] else 1,
                x["total_net_pnl"],
                x["expectancy_usd"],
            ),
            reverse=True,
        ),
    }
    (ROOT / "variants" / "mnq_pick.json").write_text(json.dumps(pick, indent=2))

    print("=== Same strategy on MNQ / MGC / MBT ===")
    symbol_summaries = []
    if best["variant"] == "apex_v26_kz":
        # re-use MNQ already run; run MGC/MBT
        write_report(ROOT / "mnq", mnq_sum, mnq_tr, mnq_days)
        symbol_summaries.append(mnq_sum)
        for sk in ("mgc", "mbt"):
            s, tr, days = run_symbol(sk)
            write_report(ROOT / sk, s, tr, days)
            symbol_summaries.append(s)
            print(f"  {sk}: n={s['n_trades']} net=${s['total_net_pnl']} qual={s['qualified_days_ge_250']} "
                  f"exp=${s['expectancy_usd']} → {s['verdict']}")
    else:
        # ORB already written by prior script for 3 symbols — leave as-is unless needed
        for sk in ("mnq", "mgc", "mbt"):
            symbol_summaries.append(json.loads((ROOT / sk / "summary.json").read_text()))

    ranked = sorted(symbol_summaries, key=rank_key, reverse=True)
    winner = ranked[0]
    ranking_payload = {
        "strategy": best["variant"],
        "strategy_label": best.get("variant_label"),
        "rank_order": [
            {
                "rank": i + 1,
                "symbol_key": s["symbol_key"],
                "ticker": s["ticker"],
                "qualified_days_ge_250": s["qualified_days_ge_250"],
                "trail_breach": s["max_dd_vs_2000_trail_breach"],
                "total_net_pnl": s["total_net_pnl"],
                "expectancy_usd": s["expectancy_usd"],
                "n_trades": s["n_trades"],
                "verdict": s["verdict"],
            }
            for i, s in enumerate(ranked)
        ],
        "winner": {
            "symbol_key": winner["symbol_key"],
            "ticker": winner["ticker"],
            "strategy": best["variant"],
            "combo": f"{winner['ticker']} + {best['variant']}",
        },
        "winner_full_stats": winner,
    }
    (ROOT / "ranking.json").write_text(json.dumps(ranking_payload, indent=2))
    brief = {
        "best_combo": f"{winner['ticker']} + {best['variant']}",
        "strategy_label": best.get("variant_label"),
        "stats": winner,
        "keep_tweak_drop": winner["verdict"],
        "why": winner["verdict_why"],
        "rank_vs_peers": ranking_payload["rank_order"],
        "mnq_variant_pick": best["variant"],
        "mnq_strategy_ranking": pick["ranking"],
    }
    (ROOT / "BEST_COMBO.json").write_text(json.dumps(brief, indent=2))

    md = [
        f"# BEST: {winner['ticker']} + `{best['variant']}`",
        "",
        f"**Strategy:** {best.get('variant_label')}  ",
        f"**Verdict:** **{winner['verdict']}** — {winner['verdict_why']}  ",
        "",
        "## Full stats",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for k in (
        "ticker", "point_value", "variant", "first_day", "last_day",
        "n_trading_days_used", "total_net_pnl", "max_dd_usd", "win_rate_pct",
        "avg_r", "expectancy_usd", "n_trades", "n_wins", "n_losses",
        "qualified_days_ge_250", "cumulative_ge_3000", "max_dd_vs_2000_trail_breach",
    ):
        md.append(f"| {k} | {winner.get(k)} |")
    md += [
        "",
        "### Session breakdown",
        "```json",
        json.dumps(winner["session_breakdown"], indent=2),
        "```",
        "",
        "## Peer ranking (same strategy × 3 symbols)",
        "",
        "| Rank | Symbol | Qual≥$250 | Trail breach | Net P&L | Expectancy | Verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in ranking_payload["rank_order"]:
        md.append(
            f"| {r['rank']} | {r['ticker']} | {r['qualified_days_ge_250']} | {r['trail_breach']} | "
            f"${r['total_net_pnl']} | ${r['expectancy_usd']} | {r['verdict']} |"
        )
    md += ["", "## MNQ strategy pick", ""]
    for r in pick["ranking"]:
        md.append(
            f"- `{r['variant']}`: qual={r['qualified_days_ge_250']} net=${r['total_net_pnl']} "
            f"exp=${r['expectancy_usd']} n={r['n_trades']} → {r['verdict']}"
        )
    md += ["", "Reports: `/workspace/apex_strategy_pick_bt/{mnq,mgc,mbt}/`", ""]
    (ROOT / "BEST_COMBO.md").write_text("\n".join(md), encoding="utf-8")
    print("\n=== WINNER ===")
    print(json.dumps({k: brief[k] for k in ("best_combo", "keep_tweak_drop", "why", "rank_vs_peers")}, indent=2))


if __name__ == "__main__":
    main()
