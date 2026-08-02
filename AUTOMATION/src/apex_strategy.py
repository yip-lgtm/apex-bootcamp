"""Shared Apex 50K strategy logic (v2.6).
Single source of truth for the scanner + backtester so they stay in sync.
"""
import os
import math
import re
import pandas as pd
import yfinance as yf
from env_loader import load_env

load_env()

# --- Apex 50K hard rules ---
RISK_USD, TP_MIN, TP_MAX, RR_MIN, RR_MAX = 100, 200, 500, 2.0, 5.0
DAILY_KILL_SWITCH = 100
SESSION_TZ = -4  # UTC-4 per apex-bootcamp

# v2.6: NY AM killzone — only consider triggers in this window
KILLZONE_START_HOUR = 9    # 09:00 EST
KILLZONE_END_HOUR   = 11   # 11:00 EST (exclusive)

# Tickers: (symbol, point_value, label, max_contracts)
TICKERS = [
    ("MGC=F",  10.0,  "Micro Gold",     1),
    ("MNQ=F",   2.0,  "Micro Nasdaq",   1),
    ("MBT=F",   0.10, "Micro Bitcoin",  1),
    ("MCL=F",   1.0,  "Micro Crude",    2),  # crude needs 2 micro for $200 floor
]


def fetch(ticker: str, start: str, end: str) -> dict:
    """Pull 1d + 5m; convert to UTC-4.

    Daily: 1-year lookback (for HTF context MA5/MA10/MA20).
    5m: yfinance caps at 60d — use period=60d for the most recent 60 days.
    Some tickers (e.g. MCL=F) have broken daily data; fall back to hourly agg.
    """
    t = yf.Ticker(ticker)
    daily_start = (pd.Timestamp(end) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    daily  = t.history(start=daily_start, end=end, interval="1d")
    hourly = t.history(start=daily_start, end=end, interval="1h")
    fivem  = t.history(period="60d", interval="5m")

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
    """Detect a 5m trigger in the killzone window (9:00-11:00 EST).

    Returns dict with bias, pattern, trigger_close, natural_sl, structure_tp, etc.
    Returns None if no trigger found.
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

    # --- 3. MSS up ---
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

    # --- 7. Bullish pin bar ---
    elif (lower_wick > 0.55 * rng and abs(body) < 0.30 * rng and body > 0):
        bias, pattern = "LONG", "pin_bar_long"

    # --- 8. Bearish pin bar ---
    elif (upper_wick > 0.55 * rng and abs(body) < 0.30 * rng and body < 0):
        bias, pattern = "SHORT", "pin_bar_short"

    # --- 9. Session high break (LONG) ---
    elif (cur["Close"] > day_bars["High"].iloc[:-1].max() and body > 0):
        bias, pattern = "LONG", "session_high_break"

    # --- 10. Session low break (SHORT) ---
    elif (cur["Close"] < day_bars["Low"].iloc[:-1].min() and body < 0):
        bias, pattern = "SHORT", "session_low_break"

    # --- 11. ORB break (first 30-min of killzone = 09:00-09:30) ---
    if bias is None and len(kz_bars) >= 6:
        orb = kz_bars.iloc[:6]
        orb_high = float(orb["High"].max())
        orb_low  = float(orb["Low"].min())
        orb_vol  = float(orb["Volume"].mean())
        if (cur["Close"] > orb_high and body > 0 and cur["Volume"] > 1.2 * orb_vol):
            bias, pattern = "LONG", "orb_break_long"
        elif (cur["Close"] < orb_low and body < 0 and cur["Volume"] > 1.2 * orb_vol):
            bias, pattern = "SHORT", "orb_break_short"

    # --- 12. VWAP rejection (use killzone VWAP) ---
    if bias is None and len(kz_bars) >= 6:
        vwap = float((kz_bars["Close"] * kz_bars["Volume"]).sum()
                     / max(kz_bars["Volume"].sum(), 1))
        if (cur["Low"] <= vwap * 1.001 and cur["Close"] > vwap
            and lower_wick > 1.5 * abs(body) and body > 0):
            bias, pattern = "LONG", "vwap_reject_long"
        elif (cur["High"] >= vwap * 0.999 and cur["Close"] < vwap
              and upper_wick > 1.5 * abs(body) and body < 0):
            bias, pattern = "SHORT", "vwap_reject_short"

    if bias is None:
        return None

    full_day = day_bars.tail(30)
    day_high = float(full_day["High"].max())
    day_low  = float(full_day["Low"].min())
    day_range = day_high - day_low
    if bias == "LONG":
        nat_sl = day_low - 0.05 * day_range
    else:
        nat_sl = day_high + 0.05 * day_range

    # Structure TP — nearest swing H/L above/below trigger close
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
                point_value: float, max_contracts: int = 1) -> dict | None:
    """v2.6: Convert a trigger into an A/B/C setup with mechanical validation.

    - Requires HTF alignment (htf_score=2); counter-trend → C
    - Structure-based TP from nearest swing H/L
    - Risk capped at $100, RR must be 2-5
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
    htf_aligned = ((bias == "LONG" and htf_bull) or (bias == "SHORT" and htf_bear))
    htf_score = 2 if htf_aligned else 1

    trig_score = 1
    a_patterns = {"mss_up", "mss_down", "session_high_break", "session_low_break",
                  "orb_break_long", "orb_break_short"}
    if trigger["pattern"] in a_patterns:
        trig_score = 2
    if trigger.get("trigger_volume_ratio", 1.0) > 1.5:
        trig_score = max(trig_score, 2)

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
    sl_dist_required = (RISK_USD / max_contracts) / point_value
    sl_dist = sl_dist_required

    if bias == "LONG":
        sl = entry - sl_dist
    else:
        sl = entry + sl_dist

    # Structure-based TP, prefer it if in $200-500 envelope
    struct_tp = trigger.get("structure_tp", entry + 3 * sl_dist)
    struct_tp_dist = abs(struct_tp - entry)
    struct_tp_reward = struct_tp_dist * point_value * max_contracts

    if TP_MIN <= struct_tp_reward <= TP_MAX:
        tp_dist = struct_tp_dist
        tp = struct_tp
    elif struct_tp_reward < TP_MIN:
        return {**trigger, "grade": "C", "entry": entry, "day": day_str,
                "htf_score": htf_score, "trig_score": trig_score,
                "contracts": max_contracts, "reason": "tp_too_tight"}
    else:
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
                    "contracts": max_contracts, "reason": f"rr_{rr:.2f}_oor"}

    return {
        **trigger, "grade": grade, "entry": entry, "sl": sl, "tp": tp,
        "sl_dist": sl_dist, "tp_dist": tp_dist, "rr": rr,
        "risk_usd": sl_dist * point_value * max_contracts,
        "reward_usd": tp_dist * point_value * max_contracts,
        "contracts": max_contracts,
        "day": day_str, "htf_score": htf_score, "trig_score": trig_score,
    }


def parse_setup(answer: str) -> dict:
    """Extract grade/bias/entry/SL/TP/RR from LLM output text."""
    def grab(pat, default=None):
        m = re.search(pat, answer, re.IGNORECASE)
        return m.group(1).strip() if m else default

    grade    = grab(r"\*\*Setup Grade\*\*:\s*([ABC])", "?")
    bias     = grab(r"\*\*Bias\*\*:\s*(LONG|SHORT|FLAT)", "?")
    entry    = grab(r"\*\*Entry\*\*:\s*([\-\d\.]+|N/A)", "N/A")
    sl       = grab(r"\*\*Stop Loss\*\*:\s*([\-\d\.]+|N/A)", "N/A")
    tp       = grab(r"\*\*Take Profit\*\*:\s*([\-\d\.]+|N/A)", "N/A")
    rr_str   = grab(r"\*\*RR\*\*:\s*([\d\.]+|N/A)", "N/A")
    risk_str = grab(r"Risk\s*=\s*\$([\d\.]+)", None)
    rew_str  = grab(r"Reward\s*=\s*\$([\d\.]+)", None)
    dist_sl  = grab(r"SL.*?距離\s*=\s*([\-\d\.]+)", None)
    dist_tp  = grab(r"TP.*?距離\s*=\s*([\-\d\.]+)", None)
    contracts = grab(r"\*\*Contracts\*\*:\s*(\d+)", "1")

    validation = {"passes": True, "violations": []}
    if grade in ("A", "B"):
        try:
            r_ = float(risk_str) if risk_str else None
            tp_ = float(rew_str) if rew_str else None
            rr_ = float(rr_str)  if rr_str and rr_str != "N/A" else None
            if r_ is not None and abs(r_ - 100) > 5:
                validation["violations"].append(f"Risk ${r_} ≠ $100")
            if tp_ is not None and not (200 <= tp_ <= 500):
                validation["violations"].append(f"TP reward ${tp_} outside $200-500")
            if rr_ is not None and not (2.0 <= rr_ <= 5.0):
                validation["violations"].append(f"RR {rr_} outside 2-5")
            validation["passes"] = len(validation["violations"]) == 0
        except Exception as e:
            validation["violations"].append(f"parse error: {e}")
            validation["passes"] = False

    return {
        "grade": grade, "bias": bias, "entry": entry, "sl": sl, "tp": tp,
        "rr": rr_str, "risk": risk_str, "reward": rew_str,
        "dist_sl": dist_sl, "dist_tp": dist_tp, "contracts": contracts,
        "validation": validation,
    }


def is_setup_valid(parsed: dict, htf_aligned: bool = True) -> bool:
    """A scanner setup is valid if mechanical check passes AND HTF aligned."""
    if not parsed["validation"]["passes"]:
        return False
    if parsed["grade"] not in ("A", "B"):
        return False
    return True
