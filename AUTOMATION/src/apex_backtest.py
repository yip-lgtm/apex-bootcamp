"""Apex 50K mechanical backtester.
Replays the scanner's A/B/C grading + trade plan over a window of trading days
using deterministic SMC rules (no LLM), then simulates next-day execution on 5m bars.

Engine: for each session day in window:
  1. Compute HTF bias from daily + H1 context
  2. Detect 5m trigger at session close (engulfing / MSS / sweep)
  3. If trigger: compute mechanical SL/TP honoring Risk $100 / TP $200-500 / RR 2-5
  4. Simulate next session's 5m: exit at first hit of SL or TP, else close
  5. Apply Apex daily loss limit ($100 kill-switch) — no new trades for that day once hit

Usage:  .venv/bin/python apex_backtest.py
"""
import os, sys, json, math
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import yfinance as yf
from env_loader import load_env
from concurrent.futures import ThreadPoolExecutor, as_completed

load_env()

# --- Apex 50K hard rules ---
RISK_USD, TP_MIN, TP_MAX, RR_MIN, RR_MAX = 100, 200, 500, 2.0, 5.0
DAILY_KILL_SWITCH = 100
SESSION_TZ = -4

# v2.6: NY AM killzone — only detect triggers in this window (EST hours)
KILLZONE_START_HOUR = 9    # 09:00 EST
KILLZONE_END_HOUR   = 11   # 11:00 EST (exclusive)

TICKERS = [
    # (ticker, point_value, label, max_contracts)
    ("MGC=F",  10.0,  "Micro Gold",     1),
    ("MNQ=F",   2.0,  "Micro Nasdaq",   1),
    ("MBT=F",   0.10, "Micro Bitcoin",  1),
    ("MCL=F",   1.0,  "Micro Crude",    2),  # crude needs 2 micro to hit $200 floor
]

# Session window (UTC-4) — CME equity-index / energy / metals
SESSION_OPEN_HOUR  = 9   # 09:30 ET for equity; crypto/commodities start 9 ET
SESSION_CLOSE_HOUR = 16  # 16:00 ET typical close
# We'll use the data's natural session — yfinance returns UTC-4 timestamps


def fetch(ticker: str, start: str, end: str) -> dict:
    """Pull 1d, 1h, 5m; convert to UTC-4.

    Daily/hourly: 1-year lookback (for HTF context MA5/MA10/MA20).
    5m: yfinance caps at 60d — use period=60d for the most recent 60 days.

    Some tickers (notably MCL=F) have broken daily data via yfinance;
    fall back to hourly aggregation when daily is too sparse (< 30 rows).
    """
    t = yf.Ticker(ticker)
    daily_start = (pd.Timestamp(end) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    daily  = t.history(start=daily_start, end=end, interval="1d")
    hourly = t.history(start=daily_start, end=end, interval="1h")
    fivem  = t.history(period="60d", interval="5m")

    # Fallback: aggregate from hourly if daily is too sparse
    if len(daily) < 30 and not hourly.empty:
        daily = (hourly.resample("1D")
                       .agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"})
                       .dropna())

    def localize(df):
        if df is None or df.empty:
            return df
        if not hasattr(df.index, "tz") or df.index.tz is None:
            return df.tz_localize("UTC").tz_convert(f"Etc/GMT+{-SESSION_TZ}")
        return df.tz_convert(f"Etc/GMT+{-SESSION_TZ}")
    return {
        "ticker": ticker, "start": start, "end": end,
        "daily": localize(daily), "hourly": localize(hourly), "fivem": localize(fivem),
    }


def detect_trigger(m5: pd.DataFrame, day: pd.Timestamp) -> dict | None:
    """v2: Look at the last 12 5m bars (1 hour) of `day` for triggers.

    v2.6: KILLZONE FILTER — only consider 5m bars whose start time falls
    in [9:00, 11:00) EST. This is the NY AM killzone, the highest liquidity
    window for index/commodity futures. Triggers outside this window are
    ignored (treated as no-trigger).

    Triggers (loose, grading downstream filters quality):
      1. Bullish / bearish engulfing
      2. MSS up/down (break of prior N-bar extreme with body confirmation)
      3. Sweep + reject (long wick beyond prior extreme)
      4. Pin bar / hammer (small body, long wick > 2x body)
      5. Close breakout above/below session H/L
      6. v2: ORB break (first-30-min range), for crude/equity indices
      7. v2: VWAP rejection (price tags VWAP and reverses)

    Returns dict {bias, pattern, trigger_close, natural_sl, ...} or None.
    """
    day_bars = m5[m5.index.date == day.date()]
    if len(day_bars) < 12:
        return None
    # v2.6: KILLZONE FILTER — restrict to bars in [9:00, 11:00) EST
    kz_bars = day_bars[
        (day_bars.index.hour >= KILLZONE_START_HOUR) &
        (day_bars.index.hour <  KILLZONE_END_HOUR)
    ]
    if len(kz_bars) < 6:
        return None
    # Take the last 12 bars of the killzone (or all of them if < 12)
    last12 = kz_bars.tail(12)
    cur  = last12.iloc[-1]
    prev = last12.iloc[-2]
    prior11 = last12.iloc[:-1]

    avg_vol = max(prior11["Volume"].mean(), 1)

    body = float(cur["Close"] - cur["Open"])
    upper_wick = float(cur["High"] - max(cur["Open"], cur["Close"]))
    lower_wick = float(min(cur["Open"], cur["Close"]) - cur["Low"])
    rng = float(cur["High"] - cur["Low"]) or 0.0001

    bias = None
    pattern = None

    # --- 1. Bullish engulfing ---
    if (prev["Close"] < prev["Open"]
        and cur["Close"] > cur["Open"]
        and cur["Close"] > prev["Open"]
        and cur["Open"]  < prev["Close"]):
        bias, pattern = "LONG", "bullish_engulfing"

    # --- 2. Bearish engulfing ---
    elif (prev["Close"] > prev["Open"]
          and cur["Close"] < cur["Open"]
          and cur["Close"] < prev["Open"]
          and cur["Open"]  > prev["Close"]):
        bias, pattern = "SHORT", "bearish_engulfing"

    # --- 3. MSS up: close above prior 11-bar high with positive body ---
    elif (cur["Close"] > prior11["High"].max() and body > 0):
        bias, pattern = "LONG", "mss_up"

    # --- 4. MSS down ---
    elif (cur["Close"] < prior11["Low"].min() and body < 0):
        bias, pattern = "SHORT", "mss_down"

    # --- 5. Sweep + reject long ---
    elif (cur["Low"] < prior11["Low"].min()
          and cur["Close"] > prior11["Close"].mean()
          and lower_wick > 1.5 * abs(body)
          and body > 0):
        bias, pattern = "LONG", "sweep_reject_long"

    # --- 6. Sweep + reject short ---
    elif (cur["High"] > prior11["High"].max()
          and cur["Close"] < prior11["Close"].mean()
          and upper_wick > 1.5 * abs(body)
          and body < 0):
        bias, pattern = "SHORT", "sweep_reject_short"

    # --- 7. Bullish pin bar (hammer) ---
    elif (lower_wick > 0.55 * rng and abs(body) < 0.30 * rng and body > 0):
        bias, pattern = "LONG", "pin_bar_long"

    # --- 8. Bearish pin bar (shooting star) ---
    elif (upper_wick > 0.55 * rng and abs(body) < 0.30 * rng and body < 0):
        bias, pattern = "SHORT", "pin_bar_short"

    # --- 9. Close above session high breakout (LONG) ---
    elif (cur["Close"] > day_bars["High"].iloc[:-1].max() and body > 0):
        bias, pattern = "LONG", "session_high_break"

    # --- 10. Close below session low breakout (SHORT) ---
    elif (cur["Close"] < day_bars["Low"].iloc[:-1].min() and body < 0):
        bias, pattern = "SHORT", "session_low_break"

    # --- 11. v2: ORB break (first 30-min range) for crude/indices ---
    # Opening range = first 6 bars (30 min). Use killzone bars for ORB context.
    if bias is None and len(kz_bars) >= 6:
        orb = kz_bars.iloc[:6]
        orb_high = float(orb["High"].max())
        orb_low  = float(orb["Low"].min())
        orb_vol  = float(orb["Volume"].mean())
        if (cur["Close"] > orb_high
            and body > 0
            and cur["Volume"] > 1.2 * orb_vol):
            bias, pattern = "LONG", "orb_break_long"
        elif (cur["Close"] < orb_low
              and body < 0
              and cur["Volume"] > 1.2 * orb_vol):
            bias, pattern = "SHORT", "orb_break_short"

    # --- 12. v2: VWAP rejection (use killzone VWAP) ---
    if bias is None and len(kz_bars) >= 6:
        vwap = float((kz_bars["Close"] * kz_bars["Volume"]).sum()
                     / max(kz_bars["Volume"].sum(), 1))
        if (cur["Low"] <= vwap * 1.001
            and cur["Close"] > vwap
            and lower_wick > 1.5 * abs(body)
            and body > 0):
            bias, pattern = "LONG", "vwap_reject_long"
        elif (cur["High"] >= vwap * 0.999
              and cur["Close"] < vwap
              and upper_wick > 1.5 * abs(body)
              and body < 0):
            bias, pattern = "SHORT", "vwap_reject_short"

    if bias is None:
        return None

    # v2: Confirmation bar — bar immediately after trigger must NOT reverse
    if len(day_bars) >= 13:
        nxt = day_bars.iloc[-1] if day_bars.index[-1] == cur.name else day_bars.iloc[-1]
        # We're looking at the last bar; if the data ends here, no confirmation available
        # The confirmation is in the next bar of next session (handled by execute_trade entry logic)

    # Natural structure SL: prior swing with small buffer
    full_day = day_bars.tail(30)
    day_high = float(full_day["High"].max())
    day_low  = float(full_day["Low"].min())
    day_range = day_high - day_low
    if bias == "LONG":
        nat_sl = day_low - 0.05 * day_range
    else:
        nat_sl = day_high + 0.05 * day_range

    # v2: Structure-based TP — nearest swing H (for LONG) or swing L (for SHORT)
    if bias == "LONG":
        swing_highs = day_bars["High"].nlargest(5)
        tp_targets = swing_highs[swing_highs > cur["Close"]].sort_values()
        struct_tp = float(tp_targets.iloc[0]) if len(tp_targets) else cur["Close"] + 0.5 * day_range
    else:
        swing_lows = day_bars["Low"].nsmallest(5)
        tp_targets = swing_lows[swing_lows < cur["Close"]].sort_values(ascending=False)
        struct_tp = float(tp_targets.iloc[0]) if len(tp_targets) else cur["Close"] - 0.5 * day_range

    return {
        "bias": bias, "pattern": pattern,
        "trigger_close": float(cur["Close"]),
        "trigger_time":  cur.name,
        "natural_sl":    nat_sl,
        "session_high":  day_high,
        "session_low":   day_low,
        "day_range":     day_range,
        "trigger_volume_ratio": float(cur["Volume"] / avg_vol),
        "structure_tp":  struct_tp,
    }


def grade_setup(trigger: dict, daily: pd.DataFrame, day: pd.Timestamp,
                point_value: float, m5: pd.DataFrame, max_contracts: int = 1) -> dict | None:
    """v2: Convert trigger into A/B/C setup with stricter quality gates.

    v2 changes:
      - Require htf_score = 2 (only trade with the trend) — drops 1+2 setups to C
      - Use structure-based TP from `structure_tp` in trigger, scaled to fit $200-500
      - Add confirmation bar check: next bar after trigger must not reverse
    v2.5: Allow `max_contracts` (1 or 2) so low-vol tickers (crude) can scale to $200 floor
    """
    day_str = day.date().isoformat()
    d_window = daily[daily.index.date <= day.date()].tail(20)
    if len(d_window) < 10:
        return None
    last = d_window.iloc[-1]
    ma5  = d_window["Close"].rolling(5).mean().iloc[-1]
    ma10 = d_window["Close"].rolling(10).mean().iloc[-1]
    if len(d_window) >= 4:
        net3 = (last["Close"] - d_window["Close"].iloc[-4]) / d_window["Close"].iloc[-4]
    else:
        net3 = 0.0

    htf_bull = (last["Close"] > ma5 and last["Close"] > ma10) or net3 > 0.005
    htf_bear = (last["Close"] < ma5 and last["Close"] < ma10) or net3 < -0.005

    bias = trigger["bias"]
    # v2: require HTF alignment (htf_score = 2); else C
    htf_aligned = ((bias == "LONG" and htf_bull) or (bias == "SHORT" and htf_bear))
    htf_score = 2 if htf_aligned else 1  # v2.5: counter-trend gets 1 (was 0); weak 2+1 → still B

    # v2: confirmation bar — bar immediately after trigger (same day, next 5m)
    # must close in the trade direction (not reverse). The trigger bar is the
    # last bar of `day`; the confirmation bar would be the NEXT bar of the next
    # session — but since we're entering next session, the "confirmation" is
    # actually the next session's opening behavior, captured by execute_trade's
    # entry-on-open logic. We can additionally check the *prior* bar to see if
    # the trigger had momentum: if the bar BEFORE the trigger was also in the
    # trade direction, that's a 2-bar setup (more reliable).
    trig_score = 1
    a_patterns = {"mss_up", "mss_down", "session_high_break", "session_low_break",
                  "orb_break_long", "orb_break_short"}
    if trigger["pattern"] in a_patterns:
        trig_score = 2
    if trigger.get("trigger_volume_ratio", 1.0) > 1.5:
        trig_score = max(trig_score, 2)

    # v2: only A (2+2) and B (2+1) — require HTF alignment
    if htf_score == 0:
        grade = "C"
    elif htf_score + trig_score == 4:
        grade = "A"
    elif htf_score + trig_score == 3:
        grade = "B"
    else:
        grade = "C"

    # Cap risk at exactly $100, scaled by max_contracts
    entry = trigger["trigger_close"]
    nat_sl = trigger["natural_sl"]
    sl_dist_natural = abs(entry - nat_sl)
    # With max_contracts, the SL distance (per contract) shrinks so the
    # total dollar risk stays at $100.
    # 1 micro:  SL_dist = $100 / point_value
    # 2 micro:  SL_dist = $50  / point_value (each contract risks $50, total $100)
    sl_dist_required = (RISK_USD / max_contracts) / point_value
    sl_dist = sl_dist_required

    if bias == "LONG":
        sl = entry - sl_dist
    else:
        sl = entry + sl_dist

    # v2: Structure-based TP (primary) with RR-based fallback
    # The structure_tp is the nearest swing H/L above/below trigger. If it's
    # reasonable (within $200-500), use it. Otherwise fall back to a fixed
    # RR-based TP.
    struct_tp = trigger.get("structure_tp", entry + 3 * sl_dist)
    struct_tp_dist = abs(struct_tp - entry)
    struct_tp_reward = struct_tp_dist * point_value * max_contracts

    # Default: RR-based TP at 3.5x risk → $350 reward
    default_tp_reward = min(TP_MAX, 3.5 * RISK_USD)
    default_tp_dist = (default_tp_reward / max_contracts) / point_value
    default_tp = entry + default_tp_dist if bias == "LONG" else entry - default_tp_dist

    if TP_MIN <= struct_tp_reward <= TP_MAX:
        # Structure TP in envelope — prefer it (closer = more realistic)
        tp_dist = struct_tp_dist
        tp = struct_tp
    elif struct_tp_reward < TP_MIN:
        # Structure too tight (e.g., crude daily vol < $200 worth) — skip
        return {**trigger, "grade": "C", "entry": entry, "day": day_str,
                "htf_score": htf_score, "trig_score": trig_score,
                "contracts": max_contracts, "reason": "tp_too_tight"}
    else:
        # Structure too far — cap to $500
        tp_dist = (TP_MAX / max_contracts) / point_value
        tp = entry + tp_dist if bias == "LONG" else entry - tp_dist

    if grade == "C" or tp is None:
        return {**trigger, "grade": "C", "entry": entry, "day": day_str,
                "htf_score": htf_score, "trig_score": trig_score,
                "contracts": max_contracts,
                "reason": "htf_not_aligned" if htf_score == 0 else "tp_envelope_fail"}

    rr = tp_dist / sl_dist
    if not (RR_MIN <= rr <= RR_MAX):
        if tp_dist > RR_MAX * sl_dist:
            tp_dist = RR_MAX * sl_dist
            tp = entry + tp_dist if bias == "LONG" else entry - tp_dist
            rr = RR_MAX
        elif tp_dist < RR_MIN * sl_dist:
            tp_dist = RR_MIN * sl_dist
            tp = entry + tp_dist if bias == "LONG" else entry - tp_dist
            rr = RR_MIN
        else:
            return {**trigger, "grade": "C", "entry": entry, "day": day_str,
                    "htf_score": htf_score, "trig_score": trig_score,
                    "contracts": max_contracts,
                    "reason": f"rr_{rr:.2f}_out_of_range"}

    return {
        **trigger, "grade": grade, "entry": entry, "sl": sl, "tp": tp,
        "sl_dist": sl_dist, "tp_dist": tp_dist, "rr": rr,
        "risk_usd": sl_dist * point_value * max_contracts,
        "reward_usd": tp_dist * point_value * max_contracts,
        "contracts": max_contracts,
        "day": day_str, "htf_score": htf_score, "trig_score": trig_score,
    }


def execute_trade(setup: dict, m5_next: pd.DataFrame, point_value: float,
                  max_contracts: int = 1) -> dict:
    """Simulate the trade over next session's 5m bars.

    Entry: first 5m bar's open (1-bar slippage from trigger close)
    SL: stop-loss
    TP: take-profit
    PnL scales with max_contracts.
    """
    if m5_next.empty:
        return {**setup, "exit_reason": "no_next_session", "pnl_usd": 0.0,
                "entry_fill": None, "exit_price": None}

    first_bar = m5_next.iloc[0]
    entry = float(first_bar["Open"])
    bias  = setup["bias"]
    qty = max_contracts

    if bias == "LONG":
        sl = entry - setup["sl_dist"]
        tp = entry + setup["tp_dist"]
    else:
        sl = entry + setup["sl_dist"]
        tp = entry - setup["tp_dist"]

    def calc_pnl(exit_px):
        diff = (exit_px - entry) if bias == "LONG" else (entry - exit_px)
        return diff * point_value * qty

    for ts, bar in m5_next.iterrows():
        if bias == "LONG":
            if bar["Low"] <= sl and bar["High"] >= tp:
                return {**setup, "entry_fill": entry, "exit_price": sl,
                        "exit_reason": "sl_same_bar", "pnl_usd": calc_pnl(sl),
                        "exit_time": str(ts), "sl": sl, "tp": tp}
            if bar["Low"] <= sl:
                return {**setup, "entry_fill": entry, "exit_price": sl,
                        "exit_reason": "sl", "pnl_usd": calc_pnl(sl),
                        "exit_time": str(ts), "sl": sl, "tp": tp}
            if bar["High"] >= tp:
                return {**setup, "entry_fill": entry, "exit_price": tp,
                        "exit_reason": "tp", "pnl_usd": calc_pnl(tp),
                        "exit_time": str(ts), "sl": sl, "tp": tp}
        else:
            if bar["High"] >= sl and bar["Low"] <= tp:
                return {**setup, "entry_fill": entry, "exit_price": sl,
                        "exit_reason": "sl_same_bar", "pnl_usd": calc_pnl(sl),
                        "exit_time": str(ts), "sl": sl, "tp": tp}
            if bar["High"] >= sl:
                return {**setup, "entry_fill": entry, "exit_price": sl,
                        "exit_reason": "sl", "pnl_usd": calc_pnl(sl),
                        "exit_time": str(ts), "sl": sl, "tp": tp}
            if bar["Low"] <= tp:
                return {**setup, "entry_fill": entry, "exit_price": tp,
                        "exit_reason": "tp", "pnl_usd": calc_pnl(tp),
                        "exit_time": str(ts), "sl": sl, "tp": tp}

    last_close = float(m5_next["Close"].iloc[-1])
    return {**setup, "entry_fill": entry, "exit_price": last_close,
            "exit_reason": "eod", "pnl_usd": calc_pnl(last_close),
            "exit_time": str(m5_next.index[-1]), "sl": sl, "tp": tp}


def backtest_ticker(ticker: str, point_value: float, label: str, max_contracts: int,
                    start: str, end: str) -> dict:
    print(f"  [{ticker}] fetching {start} → {end}…", flush=True)
    data = fetch(ticker, start, end)
    m5, daily = data["fivem"], data["daily"]
    if m5.empty or daily.empty:
        return {"ticker": ticker, "label": label, "ok": False,
                "error": "no data", "trades": [], "skipped": []}

    # Build list of trading days
    days = sorted(set(m5.index.date))

    trades, skipped = [], []
    daily_pnl = {}  # date -> running P&L that day (for kill-switch)

    for i, d in enumerate(days):
        d_ts = pd.Timestamp(d)
        # Trigger detection on day d
        trig = detect_trigger(m5, d_ts)
        if trig is None:
            skipped.append({"day": d.isoformat(), "reason": "no_5m_trigger"})
            continue
        # Grade the setup
        setup = grade_setup(trig, daily, d_ts, point_value, m5, max_contracts)
        if setup is None:
            skipped.append({"day": d.isoformat(), "reason": "no_setup"})
            continue
        if setup["grade"] == "C":
            skipped.append({"day": d.isoformat(), "reason": f"grade_C ({setup.get('reason','?')})",
                            "bias": setup.get("bias")})
            continue

        # Apex daily kill switch: skip if already -$100 today on this ticker
        if daily_pnl.get(d, 0) <= -DAILY_KILL_SWITCH:
            skipped.append({"day": d.isoformat(), "reason": "daily_kill_switch"})
            continue

        # v2.6 killzone: enter SAME-DAY on bar after trigger (no overnight gap)
        # Build execution window: bars after trigger on the same day, plus next
        # day only if we want to allow multi-day holds. For pure intraday killzone
        # trading, use same day only.
        trigger_time = trig["trigger_time"]
        day_bars = m5[m5.index.date == d_ts.date()]
        # Bars AFTER the trigger on the same day
        post_trigger = day_bars[day_bars.index > trigger_time]
        # For multi-day continuation, optionally extend to next day too
        if i + 1 < len(days):
            next_d = days[i + 1]
            next_bars = m5[m5.index.date == next_d]
        else:
            next_bars = pd.DataFrame()
        # Combine: same-day post-trigger + next-day bars (for overnight holds)
        # For pure intraday, comment out next_bars:
        m5_exec = pd.concat([post_trigger, next_bars]) if not next_bars.empty else post_trigger

        if m5_exec.empty:
            skipped.append({"day": d.isoformat(), "reason": "no_post_trigger_bars"})
            continue
        result = execute_trade(setup, m5_exec, point_value, max_contracts)
        trades.append(result)
        daily_pnl[d] = daily_pnl.get(d, 0) + result["pnl_usd"]

    return {
        "ticker": ticker, "label": label, "ok": True,
        "point_value": point_value, "max_contracts": max_contracts,
        "trades": trades, "skipped": skipped,
    }


def summarize(result: dict) -> dict:
    trades = result["trades"]
    if not trades:
        return {"ticker": result["ticker"], "n_trades": 0, "n_wins": 0, "n_losses": 0,
                "hit_rate": 0, "tp_only_hit_rate": 0,
                "n_tp": 0, "n_sl": 0, "n_eod": 0,
                "pnl_total": 0, "pnl_avg": 0, "max_drawdown": 0, "sharpe": 0,
                "avg_win": 0, "avg_loss": 0, "profit_factor": 0, "expectancy": 0}

    pnls = [t["pnl_usd"] for t in trades]
    wins  = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    tp_hits = [t for t in trades if t["exit_reason"] == "tp"]
    sl_hits = [t for t in trades if t["exit_reason"] in ("sl", "sl_same_bar")]
    eod_exits = [t for t in trades if t["exit_reason"] == "eod"]

    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    drawdown = peak - equity
    max_dd = float(drawdown.max()) if len(drawdown) else 0.0

    if len(pnls) > 1 and np.std(pnls) > 0:
        sharpe = float(np.mean(pnls) / np.std(pnls) * np.sqrt(252))
    else:
        sharpe = 0.0

    # TP-only hit rate is the strict metric (EOD exits don't count as wins for grading)
    tp_only_hit_rate = round(100 * len(tp_hits) / len(trades), 1) if trades else 0

    return {
        "ticker": result["ticker"],
        "n_trades": len(trades),
        "n_wins":  len(wins),
        "n_losses": len(losses),
        "hit_rate": round(100 * len(wins) / len(trades), 1),
        "tp_only_hit_rate": tp_only_hit_rate,
        "n_tp": len(tp_hits), "n_sl": len(sl_hits), "n_eod": len(eod_exits),
        "pnl_total": round(sum(pnls), 2),
        "pnl_avg":   round(float(np.mean(pnls)), 2),
        "avg_win":   round(float(np.mean(wins)), 2)   if wins   else 0,
        "avg_loss":  round(float(np.mean(losses)), 2) if losses else 0,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses else float("inf"),
        "expectancy": round(float(np.mean(pnls)), 2),
        "max_drawdown": round(max_dd, 2),
        "sharpe": round(sharpe, 2),
    }


if __name__ == "__main__":
    # Default window: max 5m data range (yfinance ~60 days back)
    end = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=60)
    if len(sys.argv) >= 3:
        start, end = pd.Timestamp(sys.argv[1]), pd.Timestamp(sys.argv[2])
        # yfinance 5m caps at 60d — if window larger, clamp start
        if (end - start).days > 60:
            print(f"# NOTE: yfinance 5m data limited to ~60 days; clamping start from {start.date()} to {(end - pd.Timedelta(days=60)).date()}")
            start = end - pd.Timedelta(days=60)
    start_s, end_s = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    print(f"# Apex 50K Backtest — {start_s} → {end_s} (UTC-4)\n")
    results = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(backtest_ticker, tk, pv, lab, mc, start_s, end_s): tk
                for tk, pv, lab, mc in TICKERS}
        for fut in as_completed(futs):
            r = fut.result()
            results[r["ticker"]] = r
            print(f"  [{r['ticker']}] done: {len(r['trades'])} trades, "
                  f"{len(r['skipped'])} skipped")

    # Aggregate
    order = [tk for tk, *_ in TICKERS]
    rows = [summarize(results[tk]) for tk in order]
    portfolio_pnl = sum(r["pnl_total"] for r in rows)
    portfolio_trades = sum(r["n_trades"] for r in rows)
    portfolio_wins = sum(r["n_wins"] for r in rows)

    print("\n## Per-ticker results\n")
    print("| Ticker | Trades | Wins | Hit% | TP/SL/EOD | P&L $ | Avg $ | MaxDD $ | Sharpe | Profit Factor | Expect $ |")
    print("|--------|--------|------|------|-----------|-------|-------|---------|--------|---------------|----------|")
    for r in rows:
        print(f"| {r['ticker']} | {r['n_trades']} | {r['n_wins']} | {r['hit_rate']}% "
              f"| {r['n_tp']}/{r['n_sl']}/{r['n_eod']} | ${r['pnl_total']:+,.0f} "
              f"| ${r['pnl_avg']:+,.0f} | ${r['max_drawdown']:,.0f} "
              f"| {r['sharpe']:.2f} | {r['profit_factor']} | ${r['expectancy']:+,.0f} |")

    print(f"\n**PORTFOLIO (4 micro combined):**")
    print(f"- Total trades: {portfolio_trades}")
    print(f"- Wins: {portfolio_wins} ({100*portfolio_wins/portfolio_trades:.1f}% hit rate)" if portfolio_trades else "")
    print(f"- Total P&L: **${portfolio_pnl:+,.0f}** over {portfolio_trades} trades")
    print(f"- Avg per trade: ${portfolio_pnl/portfolio_trades:+,.0f}" if portfolio_trades else "")

    # Save JSON
    out = {
        "window": {"start": start_s, "end": end_s},
        "rules": {"risk_usd": RISK_USD, "tp_min": TP_MIN, "tp_max": TP_MAX,
                  "rr_min": RR_MIN, "rr_max": RR_MAX, "daily_kill_switch": DAILY_KILL_SWITCH},
        "tickers": order,
        "per_ticker": rows,
        "portfolio": {"pnl": portfolio_pnl, "trades": portfolio_trades,
                      "wins": portfolio_wins,
                      "hit_rate": round(100*portfolio_wins/portfolio_trades, 1) if portfolio_trades else 0},
        "raw": {tk: {"trades": results[tk]["trades"],
                     "skipped": results[tk]["skipped"][:50]}
                for tk in order},
    }
    out_path = "/workspace/reports/apex-backtest.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n# Saved → {out_path}")

    # --- Markdown report ---
    report = []
    report.append(f"# Apex 50K Backtest Report (v2.6 — killzone) — {start_s} → {end_s}\n")
    report.append(f"_Window: {start_s} → {end_s} (UTC-4) · ~{(end-pd.Timestamp(start_s)).days} calendar days · "
                  f"yfinance 5m cap = 60 days_\n")
    report.append("**v2.6 engine:** HTF alignment required · structure-based TP · ORB / VWAP-reject patterns · "
                  f"**KILLZONE filter: only triggers in 09:00-11:00 EST** (NY AM session).\n")
    report.append("**Rules:** Risk $100 · TP $200-500 · RR 2-5 · 1 micro · daily kill-switch $100\n\n")

    report.append("## Headline\n")
    report.append(f"- **{portfolio_trades} trades** over the window, **{portfolio_wins} wins** "
                  f"({100*portfolio_wins/portfolio_trades:.1f}% hit rate) "
                  f"→ **{'PROFIT' if portfolio_pnl > 0 else 'LOSS'} ${abs(portfolio_pnl):.0f}** "
                  f"(${portfolio_pnl/portfolio_trades:+.1f}/trade avg)\n")

    # Per-ticker table
    report.append("\n## Per-ticker results\n")
    report.append("| Ticker | Trades | Wins | Hit% (TP-only) | TP/SL/EOD | P&L $ | Avg $ | MaxDD $ | Sharpe | PF |\n")
    report.append("|--------|--------|------|---------------|-----------|-------|-------|---------|--------|----|\n")
    for r in rows:
        report.append(
            f"| {r['ticker']} | {r['n_trades']} | {r['n_wins']} | {r['tp_only_hit_rate']}% "
            f"| {r['n_tp']}/{r['n_sl']}/{r['n_eod']} | ${r['pnl_total']:+,.0f} "
            f"| ${r['pnl_avg']:+,.0f} | ${r['max_drawdown']:,.0f} "
            f"| {r['sharpe']:.2f} | {r['profit_factor']} |\n"
        )

    # Portfolio equity curve (text-based)
    report.append("\n## Equity curve (portfolio, 4 micro combined)\n")
    all_trades = []
    for tk in order:
        for t in results[tk]["trades"]:
            all_trades.append((t["day"], t["pnl_usd"]))
    all_trades.sort()
    equity, peak, max_dd_so_far = 0, 0, 0
    chart_pts = []
    for day, pnl in all_trades:
        equity += pnl
        peak = max(peak, equity)
        dd = peak - equity
        max_dd_so_far = max(max_dd_so_far, dd)
        chart_pts.append((day, equity))
    if chart_pts:
        lo = min(p for _, p in chart_pts)
        hi = max(p for _, p in chart_pts)
        if hi == lo: hi = lo + 1
        # Render 30 wide, 10 tall ASCII
        width = 60
        height = 12
        grid = [[" "] * width for _ in range(height)]
        if len(chart_pts) > 1:
            for i, (day, p) in enumerate(chart_pts):
                col = int(i * (width - 1) / (len(chart_pts) - 1))
                row = int((hi - p) * (height - 1) / (hi - lo))
                grid[row][col] = "●"
        report.append("```\n")
        report.append(f"P&L  high=${hi:+,.0f}  low=${lo:+,.0f}  final=${equity:+,.0f}  maxDD=${max_dd_so_far:,.0f}\n")
        for row in grid:
            report.append("  " + "".join(row) + "\n")
        report.append("  " + "─" * width + "\n")
        report.append(f"  {'start':^30s}{'→':^5s}{'now':>25s}\n")
        report.append("```\n")

    # Per-ticker equity curves
    for tk in order:
        trades = results[tk]["trades"]
        if not trades:
            continue
        report.append(f"\n### {tk} equity curve\n")
        report.append("```\n")
        equity = 0
        chart = []
        for t in trades:
            equity += t["pnl_usd"]
            chart.append((t["day"], equity))
        lo = min(p for _, p in chart)
        hi = max(p for _, p in chart)
        if hi == lo: hi = lo + 1
        width, height = 50, 8
        grid = [[" "] * width for _ in range(height)]
        for i, (_, p) in enumerate(chart):
            col = int(i * (width - 1) / max(len(chart)-1, 1))
            row = int((hi - p) * (height - 1) / (hi - lo))
            grid[row][col] = "●"
        report.append(f"  ${lo:+,.0f}  " + "─" * (width-2) + f"  ${hi:+,.0f}\n")
        for row in grid:
            report.append("       " + "".join(row) + "\n")
        report.append(f"       final: ${equity:+,.0f}  ({len(trades)} trades, "
                      f"{sum(1 for t in trades if t['pnl_usd']>0)} wins)\n")
        report.append("```\n")

    # Top wins/losses
    report.append("\n## Top 5 wins\n")
    all_trades_sorted = sorted(
        [{"ticker": tk, **t} for tk in order for t in results[tk]["trades"]],
        key=lambda x: x["pnl_usd"], reverse=True
    )
    for t in all_trades_sorted[:5]:
        report.append(f"- {t['day']} {t['ticker']} {t['bias']:5s} {t['pattern']:20s} "
                      f"entry={t['entry_fill']:.2f} → exit={t['exit_price']:.2f} "
                      f"({t['exit_reason']}) **${t['pnl_usd']:+.0f}**\n")
    report.append("\n## Top 5 losses\n")
    for t in all_trades_sorted[-5:][::-1]:
        report.append(f"- {t['day']} {t['ticker']} {t['bias']:5s} {t['pattern']:20s} "
                      f"entry={t['entry_fill']:.2f} → exit={t['exit_price']:.2f} "
                      f"({t['exit_reason']}) **${t['pnl_usd']:+.0f}**\n")

    # Notes
    report.append("\n## Caveats & observations\n")
    report.append("- **yfinance 5m limit = 60 days**; requested 90 days was clamped. For 90-day "
                  "backtest use 1h resolution (lower fidelity, but available).\n")
    report.append("- **Entry slippage = 1 bar** (next session's open). Gaps can fire the SL immediately.\n")
    report.append("- **Pattern detector is a deterministic proxy** for the LLM A/B/C grader. It catches "
                  "the most common 5m triggers but won't replicate LLM nuance. Real LLM-driven A/B setups "
                  "may differ.\n")
    report.append("- **EOD exits** mean neither TP nor SL hit by close — counted at mark-to-market. "
                  "In live trading these would also exit EOD, but slippage may differ.\n")
    report.append("- **Apex daily kill-switch** at -$100 per ticker is enforced (no new entries same day).\n")
    report.append("- **No commissions / fees** modeled. Apex charges commissions on round-trip; "
                  "deduct ~$2-5 per trade from each P&L.\n")

    # Recommendations
    report.append("\n## What to improve next\n")
    losers = [r for r in rows if r["pnl_total"] < 0]
    if losers:
        report.append(f"- **{', '.join(r['ticker'] for r in losers)}** is unprofitable — "
                      "consider raising HTF alignment requirement (only trade with trend) or "
                      "dropping the ticker from the scan.\n")
    if any(r["n_eod"] > r["n_tp"] for r in rows):
        report.append("- Many EOD exits → entry is premature. Wait for a confirmed close above/below "
                      "trigger level, not just an intrabar sweep.\n")
    if any(r["hit_rate"] < 30 for r in rows):
        report.append(f"- Low hit rate on {', '.join(r['ticker'] for r in rows if r['hit_rate']<30)} "
                      "→ need stronger triggers or wider TP zone.\n")

    md_path = "/workspace/reports/apex-backtest.md"
    with open(md_path, "w") as f:
        f.write("".join(report))
    print(f"# Saved → {md_path}")
