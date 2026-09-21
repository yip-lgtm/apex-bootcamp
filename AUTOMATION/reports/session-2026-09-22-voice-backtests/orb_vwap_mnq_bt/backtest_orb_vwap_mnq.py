#!/usr/bin/env python3
"""MNQ 15-minute ORB + VWAP filter backtest (fresh engine).

Exact params (documented):
- Symbol: MNQ=F (Micro Nasdaq, $2/point), 1 contract
- Bars: 5m via yfinance
- OR: first 15m of NY RTH 09:30–09:45 America/New_York (3×5m bars) → ORH/ORL
- Entry: first subsequent 5m CLOSE beyond ORH (long) or ORL (short); lock first break only
- VWAP: session VWAP from RTH open 09:30 NY cumulative typical price*volume;
        long iff close > VWAP; short iff close < VWAP
- SL: opposite OR side; if that risk > $100 use OR mid; if still > $100 skip signal
- A/B: skip day as C if OR width * $2 > $100 at 1 contract (too wide for opposite-OR SL)
- TP: 1.5R from entry; skip if entry close already past TP (chase)
- Daily kill -$100 / daily TP +$300: no new entries that day
- No scale / average / martingale
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

OUT_DIR = Path("/workspace/orb_vwap_mnq_bt")
NY = ZoneInfo("America/New_York")
POINT_VALUE = 2.0
CONTRACTS = 1
MAX_RISK_USD = 100.0
DAILY_KILL = -100.0
DAILY_TP_CAP = 300.0
RR = 1.5  # documented choice
END_DATE = date(2026, 9, 21)
N_TRADING_DAYS = 30

RTH_OPEN = time(9, 30)
OR_END = time(9, 45)
RTH_CLOSE = time(16, 0)

LDLZ = (time(2, 0), time(5, 0))
NYKZ = (time(8, 30), time(11, 0))


def tag_session(ts: pd.Timestamp) -> str:
    t = ts.tz_convert(NY).time()
    if LDLZ[0] <= t < LDLZ[1]:
        return "LDLZ"
    if NYKZ[0] <= t < NYKZ[1]:
        return "NYKZ"
    return "other"


def fetch_mnq_5m() -> pd.DataFrame:
    t = yf.Ticker("MNQ=F")
    df = t.history(period="60d", interval="5m", auto_adjust=True)
    if df is None or df.empty:
        raise RuntimeError("yfinance returned empty MNQ=F 5m history")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(NY)
    else:
        df.index = df.index.tz_convert(NY)
    for c in ("Open", "High", "Low", "Close", "Volume"):
        if c not in df.columns:
            raise RuntimeError(f"missing column {c}")
    return df[["Open", "High", "Low", "Close", "Volume"]].sort_index()


def session_dates(df: pd.DataFrame, end: date, n: int) -> list[date]:
    rth = df[(df.index.time >= RTH_OPEN) & (df.index.time < RTH_CLOSE)]
    days = sorted({d.date() for d in rth.index})
    days = [d for d in days if d <= end]
    return days if len(days) < n else days[-n:]


def rth_bars(day_df: pd.DataFrame) -> pd.DataFrame:
    return day_df[(day_df.index.time >= RTH_OPEN) & (day_df.index.time < RTH_CLOSE)].copy()


def compute_rth_vwap(rth: pd.DataFrame) -> pd.Series:
    """Session VWAP from RTH open 09:30 NY; typical price (H+L+C)/3."""
    tp = (rth["High"] + rth["Low"] + rth["Close"]) / 3.0
    pv = tp * rth["Volume"].astype(float)
    cum_pv = pv.cumsum()
    cum_v = rth["Volume"].astype(float).cumsum().replace(0, np.nan)
    return cum_pv / cum_v


def or_window(rth: pd.DataFrame) -> pd.DataFrame:
    return rth[(rth.index.time >= RTH_OPEN) & (rth.index.time < OR_END)]


def simulate_day(day: date, df: pd.DataFrame) -> dict:
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
    }
    if len(rth) < 4:
        result["status"] = "insufficient_rth_bars"
        return result

    orb = or_window(rth)
    if len(orb) < 3:
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

    full_or_risk = or_width * POINT_VALUE * CONTRACTS
    # A/B quality: OR width implies opposite-OR SL risk > $100 at 1 contract → C skip
    if full_or_risk > MAX_RISK_USD:
        result["status"] = "skip_c_too_wide"
        result["grade"] = "C"
        result["skips"].append({
            "reason": "or_too_wide",
            "or_width": or_width,
            "full_or_risk_usd": full_or_risk,
        })
        return result
    result["grade"] = "A"

    vwap = compute_rth_vwap(rth)
    post = rth[rth.index.time >= OR_END]
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
            sl_pref = orl
            risk_pts = entry - sl_pref
            sl_mode = "opposite_or"
            if risk_pts * POINT_VALUE * CONTRACTS > MAX_RISK_USD:
                sl_pref = or_mid
                risk_pts = entry - sl_pref
                sl_mode = "or_mid"
            if risk_pts <= 0:
                result["skips"].append({"reason": "non_positive_risk", "ts": ts.isoformat(), "dir": direction})
                locked = True
                break
            if risk_pts * POINT_VALUE * CONTRACTS > MAX_RISK_USD:
                result["skips"].append({
                    "reason": "risk_cap_exceeded_after_mid",
                    "ts": ts.isoformat(),
                    "risk_usd": risk_pts * POINT_VALUE * CONTRACTS,
                })
                locked = True
                break
            sl = entry - risk_pts
            tp = entry + RR * risk_pts
            if close >= tp:
                result["skips"].append({
                    "reason": "chase_past_tp", "ts": ts.isoformat(), "dir": direction,
                    "close": close, "tp": tp,
                })
                locked = True
                break
        else:
            sl_pref = orh
            risk_pts = sl_pref - entry
            sl_mode = "opposite_or"
            if risk_pts * POINT_VALUE * CONTRACTS > MAX_RISK_USD:
                sl_pref = or_mid
                risk_pts = sl_pref - entry
                sl_mode = "or_mid"
            if risk_pts <= 0:
                result["skips"].append({"reason": "non_positive_risk", "ts": ts.isoformat(), "dir": direction})
                locked = True
                break
            if risk_pts * POINT_VALUE * CONTRACTS > MAX_RISK_USD:
                result["skips"].append({
                    "reason": "risk_cap_exceeded_after_mid",
                    "ts": ts.isoformat(),
                    "risk_usd": risk_pts * POINT_VALUE * CONTRACTS,
                })
                locked = True
                break
            sl = entry + risk_pts
            tp = entry - RR * risk_pts
            if close <= tp:
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
        pnl_usd = pnl_pts * POINT_VALUE * CONTRACTS
        r_mult = pnl_pts / risk_pts if risk_pts else 0.0

        trade = {
            "date": day.isoformat(),
            "direction": direction,
            "entry_time": ts.isoformat(),
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "risk_pts": risk_pts,
            "risk_usd": risk_pts * POINT_VALUE * CONTRACTS,
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


def max_drawdown_from_zero(pnls: list[float]) -> float:
    """Max peak-to-trough DD on equity starting at 0."""
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


def main():
    print("Fetching MNQ=F 5m...")
    df = fetch_mnq_5m()
    print(f"bars={len(df)} range={df.index[0]} → {df.index[-1]}")

    days = session_dates(df, END_DATE, N_TRADING_DAYS)
    print(f"trading days selected: {len(days)} ({days[0]} → {days[-1]})")

    day_results = []
    all_trades = []
    for d in days:
        r = simulate_day(d, df)
        day_results.append(r)
        all_trades.extend(r["trades"])

    pnls = [t["pnl_usd"] for t in all_trades]
    total_net = sum(pnls) if pnls else 0.0
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    flats = [p for p in pnls if p == 0]
    win_rate = (len(wins) / len(pnls) * 100.0) if pnls else 0.0
    avg_r = float(np.mean([t["r_multiple"] for t in all_trades])) if all_trades else 0.0
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
        verdict, why = "drop", "zero fills under 15m ORB+VWAP+$100 risk filters"
    elif len(all_trades) < 5 or n_c >= 20:
        verdict = "drop"
        why = (
            f"only {len(all_trades)} trades / {n_c} days C-wide OR; "
            f"net ${total_net:.2f} — 15m MNQ OR rarely fits $100 risk at 1 contract"
        )
    elif total_net <= 0 or max_dd > 2000:
        verdict, why = "drop", f"net ${total_net:.2f}, maxDD ${max_dd:.2f} — fails edge/risk gates"
    elif total_net >= 3000 and max_dd <= 2000 and qualified_days >= 3:
        verdict = "keep as primary"
        why = f"net ${total_net:.2f}, maxDD ${max_dd:.2f}, {qualified_days} ≥$250 days"
    else:
        verdict = "tweak"
        why = f"net ${total_net:.2f}, WR {win_rate:.1f}%, n={len(all_trades)}, qual_days={qualified_days}"

    summary = {
        "symbol": "MNQ=F",
        "point_value": POINT_VALUE,
        "contracts": CONTRACTS,
        "or_window": "09:30–09:45 America/New_York (3×5m)",
        "vwap": "session VWAP from RTH open 09:30 NY; typical price (H+L+C)/3",
        "tp_rr": RR,
        "sl_logic": "opposite OR; mid-OR if entry-extended risk>$100; C-skip if OR width*$2>$100",
        "period_end": END_DATE.isoformat(),
        "n_trading_days_requested": N_TRADING_DAYS,
        "n_trading_days_used": len(days),
        "first_day": days[0].isoformat() if days else None,
        "last_day": days[-1].isoformat() if days else None,
        "data_first_bar": df.index[0].isoformat(),
        "data_last_bar": df.index[-1].isoformat(),
        "total_net_pnl": round(total_net, 2),
        "max_dd_usd": round(max_dd, 2),
        "win_rate_pct": round(win_rate, 2),
        "avg_r": round(avg_r, 4),
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

    trades_path = OUT_DIR / "trades.json"
    with open(trades_path, "w") as f:
        json.dump({"summary": summary, "trades": all_trades, "days": day_results}, f, indent=2, default=str)
    with open(OUT_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    lines = []
    lines.append("# MNQ 15m ORB + VWAP Backtest Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now(NY).strftime('%Y-%m-%d %H:%M:%S %Z')}  ")
    lines.append(f"**Symbol:** MNQ=F · **Size:** 1 Micro ($2/pt) · **Bars:** 5m (yfinance)  ")
    lines.append(f"**Window:** {summary['first_day']} → {summary['last_day']} ({summary['n_trading_days_used']} trading days, end {END_DATE})  ")
    lines.append(f"**Data span:** {summary['data_first_bar']} → {summary['data_last_bar']}")
    lines.append("")
    lines.append("## Strategy params (exact)")
    lines.append("")
    lines.append("- Opening range: **09:30–09:45 America/New_York** (3×5m) → ORH/ORL")
    lines.append("- Entry: first post-OR 5m **close** beyond ORH (long) / ORL (short); **first break only**")
    lines.append("- VWAP filter: **session VWAP from RTH open 09:30 NY**, typical price (H+L+C)/3; long iff close>VWAP, short iff close<VWAP")
    lines.append("- SL: opposite OR; if entry-extended risk > $100 use **OR mid**; if still > $100 skip signal")
    lines.append("- A/B: **C-skip day** if OR width × $2 > $100 (cannot place opposite-OR SL within risk cap at 1 contract)")
    lines.append(f"- TP: **{RR}R** from entry; skip if entry close already past TP (chase)")
    lines.append("- Daily kill **−$100** / daily TP **+$300**: no new entries that day")
    lines.append("- Same-bar SL+TP: **SL first** (conservative)")
    lines.append("- No scale / average / martingale / grid")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Total net P&L | ${summary['total_net_pnl']:.2f} |")
    lines.append(f"| Max DD $ | ${summary['max_dd_usd']:.2f} |")
    lines.append(f"| Win rate | {summary['win_rate_pct']:.2f}% ({summary['n_wins']}W / {summary['n_losses']}L / {summary['n_flats']}F) |")
    lines.append(f"| Avg R | {summary['avg_r']:.4f} |")
    lines.append(f"| # Trades | {summary['n_trades']} |")
    lines.append(f"| Best day | {summary['best_day']['date']} (${summary['best_day']['pnl']:.2f}) |")
    lines.append(f"| Worst day | {summary['worst_day']['date']} (${summary['worst_day']['pnl']:.2f}) |")
    lines.append(f"| Qualified days (≥$250 net) | {summary['qualified_days_ge_250']} |")
    lines.append(f"| Cumulative ≥ $3000? | {summary['cumulative_ge_3000']} |")
    lines.append(f"| Max DD vs $2000 trail breach? | {summary['max_dd_vs_2000_trail_breach']} |")
    lines.append("")
    lines.append("## Session tag breakdown (entry time)")
    lines.append("")
    lines.append("| Tag | #Trades | P&L | Win% | Avg R |")
    lines.append("|---|---|---|---|---|")
    for tag in ("LDLZ", "NYKZ", "other"):
        s = tag_breakdown[tag]
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
    lines.append(f"**{verdict}** — {why}")
    lines.append("")
    lines.append("---")
    lines.append("_Facts only from this fresh 15m ORB+VWAP run. Not the existing 30m ORB reports._")

    report_path = OUT_DIR / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {report_path}")
    print(f"Wrote {trades_path}")


if __name__ == "__main__":
    main()
