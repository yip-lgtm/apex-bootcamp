#!/usr/bin/env python3
"""ORB + VWAP multi-variant / multi-symbol Apex strategy picker.

Hard constraints (all runs):
- 1 Micro fixed
- Bracket SL/TP
- Daily kill -$100 / daily TP +$300
- Skip T1 chase (entry already past TP)
- No scale / average / martingale
- Session tags LDLZ / NYKZ / other

Variants (MNQ pick first):
- base_15m: OR 09:30-09:45; C-skip if full OR risk > $100
- variant_A_5m: OR 09:30-09:35; C-skip if full OR risk > $100
- variant_B_30m_mid: OR 09:30-10:00; prefer mid-OR SL; C-skip if mid risk > $100
"""
from __future__ import annotations

import json
import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path("/workspace/apex_strategy_pick_bt")
NY = ZoneInfo("America/New_York")

CONTRACTS = 1
MAX_RISK_USD = 100.0
DAILY_KILL = -100.0
DAILY_TP_CAP = 300.0
RR = 1.5
END_DATE = date(2026, 9, 21)
N_TRADING_DAYS = 30

RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)
LDLZ = (time(2, 0), time(5, 0))
NYKZ = (time(8, 30), time(11, 0))

SYMBOLS = {
    "mnq": {"ticker": "MNQ=F", "point_value": 2.0, "name": "Micro Nasdaq"},
    "mgc": {"ticker": "MGC=F", "point_value": 10.0, "name": "Micro Gold"},
    "mbt": {"ticker": "MBT=F", "point_value": 0.1, "name": "Micro Bitcoin", "ticker_note": "MBT=F available via yfinance"},
}


@dataclass(frozen=True)
class Variant:
    key: str
    label: str
    or_end: time
    min_or_bars: int
    prefer_mid_sl: bool
    c_skip_mode: str  # "full_or" | "mid_or"


VARIANTS = [
    Variant("base_15m", "15m ORB + VWAP (opposite-OR SL, mid fallback)", time(9, 45), 3, False, "full_or"),
    Variant("variant_A_5m", "5m ORB + VWAP (opposite-OR SL, mid fallback)", time(9, 35), 1, False, "full_or"),
    Variant("variant_B_30m_mid", "30m ORB + VWAP (prefer mid-OR SL)", time(10, 0), 6, True, "mid_or"),
]


def tag_session(ts: pd.Timestamp) -> str:
    t = ts.tz_convert(NY).time()
    if LDLZ[0] <= t < LDLZ[1]:
        return "LDLZ"
    if NYKZ[0] <= t < NYKZ[1]:
        return "NYKZ"
    return "other"


def fetch_5m(ticker: str) -> pd.DataFrame:
    t = yf.Ticker(ticker)
    df = t.history(period="60d", interval="5m", auto_adjust=True)
    if df is None or df.empty:
        raise RuntimeError(f"yfinance empty for {ticker}")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(NY)
    else:
        df.index = df.index.tz_convert(NY)
    return df[["Open", "High", "Low", "Close", "Volume"]].sort_index()


def session_dates(df: pd.DataFrame, end: date, n: int) -> list[date]:
    rth = df[(df.index.time >= RTH_OPEN) & (df.index.time < RTH_CLOSE)]
    days = sorted({d.date() for d in rth.index})
    days = [d for d in days if d <= end]
    return days if len(days) < n else days[-n:]


def rth_bars(day_df: pd.DataFrame) -> pd.DataFrame:
    return day_df[(day_df.index.time >= RTH_OPEN) & (day_df.index.time < RTH_CLOSE)].copy()


def compute_rth_vwap(rth: pd.DataFrame) -> pd.Series:
    tp = (rth["High"] + rth["Low"] + rth["Close"]) / 3.0
    pv = tp * rth["Volume"].astype(float)
    cum_pv = pv.cumsum()
    cum_v = rth["Volume"].astype(float).cumsum().replace(0, np.nan)
    return cum_pv / cum_v


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


def simulate_day(day: date, df: pd.DataFrame, variant: Variant, point_value: float) -> dict:
    day_df = df[df.index.date == day]
    rth = rth_bars(day_df)
    result = {
        "date": day.isoformat(),
        "status": "no_data",
        "trades": [],
        "day_pnl": 0.0,
        "skips": [],
        "orh": None,
        "orl": None,
        "or_width": None,
        "grade": None,
        "variant": variant.key,
    }
    if len(rth) < max(4, variant.min_or_bars + 1):
        result["status"] = "insufficient_rth_bars"
        return result

    orb = rth[(rth.index.time >= RTH_OPEN) & (rth.index.time < variant.or_end)]
    if len(orb) < variant.min_or_bars:
        result["status"] = "incomplete_or"
        result["skips"].append({"reason": "incomplete_or", "n_or_bars": int(len(orb))})
        return result

    orh = float(orb["High"].max())
    orl = float(orb["Low"].min())
    or_mid = (orh + orl) / 2.0
    or_width = orh - orl
    result["orh"] = orh
    result["orl"] = orl
    result["or_width"] = or_width

    full_or_risk = or_width * point_value * CONTRACTS
    mid_half_width = (orh - or_mid)  # == or_width/2
    # For C-skip: full OR opposite SL, or mid-mode uses half-width as baseline risk from mid
    if variant.c_skip_mode == "full_or":
        c_risk = full_or_risk
    else:
        # Prefer mid: day is C if even stopping at mid from OR extreme exceeds risk
        # (worst-case entry at OR extreme with mid SL)
        c_risk = mid_half_width * point_value * CONTRACTS

    if c_risk > MAX_RISK_USD:
        result["status"] = "skip_c_too_wide"
        result["grade"] = "C"
        result["skips"].append({
            "reason": "or_too_wide",
            "or_width": or_width,
            "c_risk_usd": c_risk,
            "c_skip_mode": variant.c_skip_mode,
        })
        return result
    result["grade"] = "A"

    vwap = compute_rth_vwap(rth)
    post = rth[rth.index.time >= variant.or_end]
    if post.empty:
        result["status"] = "no_post_or_bars"
        return result

    day_pnl = 0.0
    locked = False
    trades: list[dict] = []

    for i, (ts, bar) in enumerate(post.iterrows()):
        if locked:
            break
        if day_pnl <= DAILY_KILL or day_pnl >= DAILY_TP_CAP:
            break

        close = float(bar["Close"])
        if ts not in vwap.index or math.isnan(float(vwap.loc[ts])):
            continue
        v = float(vwap.loc[ts])

        direction = None
        if close > orh and close > v:
            direction = "LONG"
        elif close < orl and close < v:
            direction = "SHORT"
        else:
            continue

        entry = close
        if direction == "LONG":
            if variant.prefer_mid_sl:
                sl_pref = or_mid
                sl_mode = "or_mid"
            else:
                sl_pref = orl
                sl_mode = "opposite_or"
            risk_pts = entry - sl_pref
            if (not variant.prefer_mid_sl) and risk_pts * point_value * CONTRACTS > MAX_RISK_USD:
                sl_pref = or_mid
                risk_pts = entry - sl_pref
                sl_mode = "or_mid"
            if risk_pts <= 0:
                result["skips"].append({"reason": "non_positive_risk", "ts": ts.isoformat(), "dir": direction})
                locked = True
                break
            if risk_pts * point_value * CONTRACTS > MAX_RISK_USD:
                result["skips"].append({
                    "reason": "risk_cap_exceeded",
                    "ts": ts.isoformat(),
                    "risk_usd": risk_pts * point_value * CONTRACTS,
                })
                locked = True
                break
            sl = entry - risk_pts
            tp = entry + RR * risk_pts
            if close >= tp:  # skip T1 chase
                result["skips"].append({
                    "reason": "chase_past_tp", "ts": ts.isoformat(), "dir": direction,
                    "close": close, "tp": tp,
                })
                locked = True
                break
        else:
            if variant.prefer_mid_sl:
                sl_pref = or_mid
                sl_mode = "or_mid"
            else:
                sl_pref = orh
                sl_mode = "opposite_or"
            risk_pts = sl_pref - entry
            if (not variant.prefer_mid_sl) and risk_pts * point_value * CONTRACTS > MAX_RISK_USD:
                sl_pref = or_mid
                risk_pts = sl_pref - entry
                sl_mode = "or_mid"
            if risk_pts <= 0:
                result["skips"].append({"reason": "non_positive_risk", "ts": ts.isoformat(), "dir": direction})
                locked = True
                break
            if risk_pts * point_value * CONTRACTS > MAX_RISK_USD:
                result["skips"].append({
                    "reason": "risk_cap_exceeded",
                    "ts": ts.isoformat(),
                    "risk_usd": risk_pts * point_value * CONTRACTS,
                })
                locked = True
                break
            sl = entry + risk_pts
            tp = entry - RR * risk_pts
            if close <= tp:  # skip T1 chase
                result["skips"].append({
                    "reason": "chase_past_tp", "ts": ts.isoformat(), "dir": direction,
                    "close": close, "tp": tp,
                })
                locked = True
                break

        remaining = post.iloc[i + 1 :]
        exit_price = None
        exit_ts = None
        exit_reason = None
        for ets, ebar in remaining.iterrows():
            hi = float(ebar["High"])
            lo = float(ebar["Low"])
            if direction == "LONG":
                hit_sl = lo <= sl
                hit_tp = hi >= tp
                if hit_sl and hit_tp:
                    exit_price, exit_ts, exit_reason = sl, ets, "SL_samebar_ambiguous"
                    break
                if hit_sl:
                    exit_price, exit_ts, exit_reason = sl, ets, "SL"
                    break
                if hit_tp:
                    exit_price, exit_ts, exit_reason = tp, ets, "TP"
                    break
            else:
                hit_sl = hi >= sl
                hit_tp = lo <= tp
                if hit_sl and hit_tp:
                    exit_price, exit_ts, exit_reason = sl, ets, "SL_samebar_ambiguous"
                    break
                if hit_sl:
                    exit_price, exit_ts, exit_reason = sl, ets, "SL"
                    break
                if hit_tp:
                    exit_price, exit_ts, exit_reason = tp, ets, "TP"
                    break

        if exit_price is None:
            last = rth.iloc[-1]
            exit_price = float(last["Close"])
            exit_ts = last.name
            exit_reason = "EOD"

        pnl_pts = (exit_price - entry) if direction == "LONG" else (entry - exit_price)
        pnl_usd = pnl_pts * point_value * CONTRACTS
        r_mult = pnl_pts / risk_pts if risk_pts else 0.0

        trade = {
            "date": day.isoformat(),
            "direction": direction,
            "entry_time": ts.isoformat(),
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "risk_pts": risk_pts,
            "risk_usd": risk_pts * point_value * CONTRACTS,
            "orh": orh,
            "orl": orl,
            "or_mid": or_mid,
            "sl_mode": sl_mode,
            "vwap_at_entry": v,
            "exit_time": exit_ts.isoformat() if exit_ts is not None else None,
            "exit": exit_price,
            "exit_reason": exit_reason,
            "pnl_usd": round(pnl_usd, 4),
            "r_multiple": round(r_mult, 4),
            "session_tag": tag_session(ts),
            "grade": result["grade"],
            "variant": variant.key,
        }
        trades.append(trade)
        day_pnl += pnl_usd
        locked = True
        break

    result["trades"] = trades
    result["day_pnl"] = round(day_pnl, 4)
    if trades:
        result["status"] = "traded"
    elif result["skips"]:
        result["status"] = "skipped"
    else:
        result["status"] = "no_signal"
    return result


def summarize(day_results, all_trades, meta: dict) -> dict:
    pnls = [t["pnl_usd"] for t in all_trades]
    total_net = sum(pnls) if pnls else 0.0
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    flats = [p for p in pnls if p == 0]
    win_rate = (len(wins) / len(pnls) * 100.0) if pnls else 0.0
    avg_r = float(np.mean([t["r_multiple"] for t in all_trades])) if all_trades else 0.0
    expectancy = (total_net / len(pnls)) if pnls else 0.0  # $/trade
    max_dd = max_drawdown_from_zero(pnls)

    daily_pnl = {r["date"]: r["day_pnl"] for r in day_results}
    best_day = max(daily_pnl.items(), key=lambda x: x[1]) if daily_pnl else (None, 0.0)
    worst_day = min(daily_pnl.items(), key=lambda x: x[1]) if daily_pnl else (None, 0.0)
    qualified_days = sum(1 for v in daily_pnl.values() if v >= 250.0)

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

    tag_breakdown = {k: tag_stats(v) for k, v in by_tag.items()}
    trail_2000_breach = max_dd > 2000.0
    cum_ge_3000 = total_net >= 3000.0
    n_c = sum(1 for r in day_results if r["status"] == "skip_c_too_wide")

    if not all_trades:
        verdict, why = "drop", "zero fills under ORB+VWAP+$100 risk filters"
    elif trail_2000_breach:
        verdict, why = "drop", f"maxDD ${max_dd:.2f} breaches $2000 trail"
    elif total_net <= 0:
        verdict, why = "drop", f"net ${total_net:.2f} — no edge"
    elif len(all_trades) < 5 or n_c >= 20:
        verdict = "drop"
        why = f"only {len(all_trades)} trades / {n_c} C-wide days; net ${total_net:.2f}"
    elif total_net >= 3000 and max_dd <= 2000 and qualified_days >= 3:
        verdict = "keep"
        why = f"net ${total_net:.2f}, maxDD ${max_dd:.2f}, {qualified_days} ≥$250 days"
    else:
        verdict = "tweak"
        why = (
            f"net ${total_net:.2f}, WR {win_rate:.1f}%, n={len(all_trades)}, "
            f"qual_days={qualified_days}, expectancy=${expectancy:.2f}/trade"
        )

    summary = {
        **meta,
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
        "cumulative_ge_3000": cum_ge_3000,
        "max_dd_vs_2000_trail_breach": trail_2000_breach,
        "session_breakdown": tag_breakdown,
        "status_counts": {
            s: sum(1 for r in day_results if r["status"] == s)
            for s in sorted({r["status"] for r in day_results})
        },
        "verdict": verdict,
        "verdict_why": why,
    }
    return summary


def write_report(out_dir: Path, summary: dict, all_trades: list, day_results: list, title: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    with open(out_dir / "trades.json", "w") as f:
        json.dump({"summary": summary, "trades": all_trades, "days": day_results}, f, indent=2, default=str)

    lines = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now(NY).strftime('%Y-%m-%d %H:%M:%S %Z')}  ")
    lines.append(
        f"**Symbol:** {summary['ticker']} ({summary.get('symbol_name','')}) · "
        f"**Size:** 1 Micro (${summary['point_value']}/pt) · **Bars:** 5m (yfinance)  "
    )
    lines.append(
        f"**Strategy:** {summary['variant_label']} (`{summary['variant']}`)  "
    )
    lines.append(
        f"**Window:** {summary['first_day']} → {summary['last_day']} "
        f"({summary['n_trading_days_used']} trading days, end {summary['period_end']})  "
    )
    if summary.get("ticker_note"):
        lines.append(f"**Ticker note:** {summary['ticker_note']}  ")
    lines.append(f"**Data span:** {summary['data_first_bar']} → {summary['data_last_bar']}")
    lines.append("")
    lines.append("## Hard constraints")
    lines.append("")
    lines.append("- 1 Micro fixed · brackets · daily **−$100 / +$300** · skip T1 chase · no scale/average")
    lines.append("- Session tags: LDLZ 02:00–05:00 NY · NYKZ 08:30–11:00 NY")
    lines.append(f"- TP: **{RR}R** · Same-bar SL+TP: **SL first**")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Total net P&L | ${summary['total_net_pnl']:.2f} |")
    lines.append(f"| Max DD $ | ${summary['max_dd_usd']:.2f} |")
    lines.append(f"| Win rate | {summary['win_rate_pct']:.2f}% ({summary['n_wins']}W / {summary['n_losses']}L / {summary['n_flats']}F) |")
    lines.append(f"| Avg R | {summary['avg_r']:.4f} |")
    lines.append(f"| Expectancy $/trade | ${summary['expectancy_usd']:.4f} |")
    lines.append(f"| # Trades | {summary['n_trades']} |")
    lines.append(f"| Best day | {summary['best_day']['date']} (${summary['best_day']['pnl']:.2f}) |")
    lines.append(f"| Worst day | {summary['worst_day']['date']} (${summary['worst_day']['pnl']:.2f}) |")
    lines.append(f"| Qualified days (≥$250 net) | {summary['qualified_days_ge_250']} |")
    lines.append(f"| Cumulative ≥ $3000? | {summary['cumulative_ge_3000']} |")
    lines.append(f"| Max DD vs $2000 trail breach? | {summary['max_dd_vs_2000_trail_breach']} |")
    lines.append("")
    lines.append("## Session tag breakdown")
    lines.append("")
    lines.append("| Tag | #Trades | P&L | Win% | Avg R |")
    lines.append("|---|---|---|---|---|")
    for tag in ("LDLZ", "NYKZ", "other"):
        s = summary["session_breakdown"][tag]
        lines.append(f"| {tag} | {s['n']} | ${s['pnl']:.2f} | {s['win_rate']:.2f}% | {s['avg_r']:.4f} |")
    lines.append("")
    lines.append("## Day status counts")
    lines.append("")
    for k, v in summary["status_counts"].items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("## Trades")
    lines.append("")
    if not all_trades:
        lines.append("_No trades._")
    else:
        lines.append("| Date | Dir | Entry NY | Tag | Entry | SL | TP | R$ | Exit | Why | P&L | R |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for t in all_trades:
            et = pd.Timestamp(t["entry_time"]).tz_convert(NY).strftime("%H:%M")
            lines.append(
                f"| {t['date']} | {t['direction']} | {et} | {t['session_tag']} | "
                f"{t['entry']:.2f} | {t['sl']:.2f} | {t['tp']:.2f} | {t['risk_usd']:.2f} | "
                f"{t['exit']:.2f} | {t['exit_reason']} | ${t['pnl_usd']:.2f} | {t['r_multiple']:.2f} |"
            )
    lines.append("")
    lines.append("## Daily P&L")
    lines.append("")
    lines.append("| Date | Status | Day P&L | Grade | OR width | #Trades |")
    lines.append("|---|---|---|---|---|---|")
    for r in day_results:
        ow = f"{r['or_width']:.2f}" if r["or_width"] is not None else ""
        lines.append(
            f"| {r['date']} | {r['status']} | ${r['day_pnl']:.2f} | {r.get('grade')} | "
            f"{ow} | {len(r['trades'])} |"
        )
    lines.append("")
    lines.append("## VERDICT")
    lines.append("")
    lines.append(f"**{summary['verdict']}** — {summary['verdict_why']}")
    lines.append("")
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def run_one(sym_key: str, variant: Variant, df: pd.DataFrame | None = None) -> tuple[dict, list, list]:
    sym = SYMBOLS[sym_key]
    ticker = sym["ticker"]
    pv = sym["point_value"]
    if df is None:
        print(f"Fetching {ticker} 5m...")
        df = fetch_5m(ticker)
    days = session_dates(df, END_DATE, N_TRADING_DAYS)
    day_results = []
    all_trades = []
    for d in days:
        r = simulate_day(d, df, variant, pv)
        day_results.append(r)
        all_trades.extend(r["trades"])
    meta = {
        "symbol_key": sym_key,
        "ticker": ticker,
        "symbol_name": sym["name"],
        "ticker_note": sym.get("ticker_note"),
        "point_value": pv,
        "contracts": CONTRACTS,
        "variant": variant.key,
        "variant_label": variant.label,
        "or_window": f"09:30–{variant.or_end.strftime('%H:%M')} America/New_York",
        "tp_rr": RR,
        "period_end": END_DATE.isoformat(),
        "n_trading_days_requested": N_TRADING_DAYS,
        "n_trading_days_used": len(days),
        "first_day": days[0].isoformat() if days else None,
        "last_day": days[-1].isoformat() if days else None,
        "data_first_bar": df.index[0].isoformat(),
        "data_last_bar": df.index[-1].isoformat(),
    }
    summary = summarize(day_results, all_trades, meta)
    return summary, all_trades, day_results


def rank_key(s: dict):
    # Rank: qualified days desc, then prefer no $2k trail breach, then net P&L, then expectancy
    no_breach = 0 if s["max_dd_vs_2000_trail_breach"] else 1
    return (
        s["qualified_days_ge_250"],
        no_breach,
        s["total_net_pnl"],
        s["expectancy_usd"],
    )


def main():
    print("=== Phase 1: MNQ variant pick ===")
    mnq_df = fetch_5m("MNQ=F")
    variant_results = []
    for v in VARIANTS:
        summary, trades, days = run_one("mnq", v, mnq_df)
        out = ROOT / "variants" / v.key
        write_report(out, summary, trades, days, f"MNQ Variant — {v.label}")
        # also mirror into orb_vwap_mnq_bt variant dirs for continuity
        if v.key == "variant_A_5m":
            write_report(Path("/workspace/orb_vwap_mnq_bt/variant_A_5m"), summary, trades, days, f"MNQ Variant A — {v.label}")
        if v.key == "variant_B_30m_mid":
            write_report(Path("/workspace/orb_vwap_mnq_bt/variant_B_30m_mid"), summary, trades, days, f"MNQ Variant B — {v.label}")
        variant_results.append(summary)
        print(
            f"  {v.key}: n={summary['n_trades']} net=${summary['total_net_pnl']} "
            f"qual={summary['qualified_days_ge_250']} exp=${summary['expectancy_usd']} "
            f"verdict={summary['verdict']}"
        )

    best_variant_summary = max(variant_results, key=rank_key)
    best_variant = next(v for v in VARIANTS if v.key == best_variant_summary["variant"])
    print(f"\nBest strategy on MNQ: {best_variant.key} ({best_variant.label})")

    with open(ROOT / "variants" / "mnq_pick.json", "w") as f:
        json.dump(
            {
                "best_variant": best_variant.key,
                "best_label": best_variant.label,
                "ranking": sorted(
                    [
                        {
                            "variant": s["variant"],
                            "qualified_days_ge_250": s["qualified_days_ge_250"],
                            "trail_breach": s["max_dd_vs_2000_trail_breach"],
                            "total_net_pnl": s["total_net_pnl"],
                            "expectancy_usd": s["expectancy_usd"],
                            "verdict": s["verdict"],
                        }
                        for s in variant_results
                    ],
                    key=lambda x: (
                        x["qualified_days_ge_250"],
                        0 if x["trail_breach"] else 1,
                        x["total_net_pnl"],
                        x["expectancy_usd"],
                    ),
                    reverse=True,
                ),
            },
            f,
            indent=2,
        )

    print("\n=== Phase 2: same strategy on MNQ / MGC / MBT ===")
    symbol_summaries = []
    for sym_key in ("mnq", "mgc", "mbt"):
        summary, trades, days = run_one(sym_key, best_variant)
        write_report(
            ROOT / sym_key,
            summary,
            trades,
            days,
            f"{summary['ticker']} — {best_variant.label}",
        )
        symbol_summaries.append(summary)
        print(
            f"  {sym_key}: n={summary['n_trades']} net=${summary['total_net_pnl']} "
            f"qual={summary['qualified_days_ge_250']} exp=${summary['expectancy_usd']} "
            f"breach={summary['max_dd_vs_2000_trail_breach']} verdict={summary['verdict']}"
        )

    ranked = sorted(symbol_summaries, key=rank_key, reverse=True)
    winner = ranked[0]

    ranking_payload = {
        "strategy": best_variant.key,
        "strategy_label": best_variant.label,
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
            "strategy": best_variant.key,
            "combo": f"{winner['ticker']} + {best_variant.key}",
        },
        "winner_full_stats": winner,
    }
    with open(ROOT / "ranking.json", "w") as f:
        json.dump(ranking_payload, f, indent=2)

    # Single best combo brief for parent
    brief = {
        "best_combo": f"{winner['ticker']} + {best_variant.key}",
        "strategy_label": best_variant.label,
        "stats": winner,
        "keep_tweak_drop": winner["verdict"],
        "why": winner["verdict_why"],
        "rank_vs_peers": ranking_payload["rank_order"],
        "mnq_variant_pick": best_variant.key,
    }
    with open(ROOT / "BEST_COMBO.json", "w") as f:
        json.dump(brief, f, indent=2)

    # Markdown for parent relay
    md = []
    md.append(f"# BEST: {winner['ticker']} + `{best_variant.key}`")
    md.append("")
    md.append(f"**Strategy:** {best_variant.label}  ")
    md.append(f"**Verdict:** **{winner['verdict']}** — {winner['verdict_why']}  ")
    md.append("")
    md.append("## Full stats")
    md.append("")
    md.append("| Metric | Value |")
    md.append("|---|---|")
    for k in (
        "ticker", "point_value", "variant", "first_day", "last_day",
        "n_trading_days_used", "total_net_pnl", "max_dd_usd", "win_rate_pct",
        "avg_r", "expectancy_usd", "n_trades", "qualified_days_ge_250",
        "cumulative_ge_3000", "max_dd_vs_2000_trail_breach",
    ):
        md.append(f"| {k} | {winner.get(k)} |")
    md.append("")
    md.append("### Session breakdown")
    md.append("```json")
    md.append(json.dumps(winner["session_breakdown"], indent=2))
    md.append("```")
    md.append("")
    md.append("## Peer ranking (same strategy)")
    md.append("")
    md.append("| Rank | Symbol | Qual≥$250 | Trail breach | Net P&L | Expectancy | Verdict |")
    md.append("|---|---|---|---|---|---|---|")
    for r in ranking_payload["rank_order"]:
        md.append(
            f"| {r['rank']} | {r['ticker']} | {r['qualified_days_ge_250']} | "
            f"{r['trail_breach']} | ${r['total_net_pnl']} | ${r['expectancy_usd']} | {r['verdict']} |"
        )
    md.append("")
    md.append("## MNQ strategy pick (pre-symbol)")
    md.append("")
    with open(ROOT / "variants" / "mnq_pick.json") as f:
        pick = json.load(f)
    for r in pick["ranking"]:
        md.append(
            f"- `{r['variant']}`: qual={r['qualified_days_ge_250']} net=${r['total_net_pnl']} "
            f"exp=${r['expectancy_usd']} breach={r['trail_breach']} → {r['verdict']}"
        )
    md.append("")
    md.append(f"Reports: `/workspace/apex_strategy_pick_bt/{{mnq,mgc,mbt}}/`")
    (ROOT / "BEST_COMBO.md").write_text("\n".join(md), encoding="utf-8")
    print("\n=== WINNER ===")
    print(json.dumps(brief, indent=2, default=str))


if __name__ == "__main__":
    main()
