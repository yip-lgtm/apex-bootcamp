"""Apex 50K mechanical setup analyzer — MGC=F / MNQ=F style micro futures.
Multi-timeframe (H4 / H1 / 5m) + A/B/C grading + Risk $100 / TP $200-500 / RR 2-5.

Usage: .venv/bin/python apex_analyze.py MGC=F 2026-07-31
       .venv/bin/python apex_analyze.py MNQ=F 2026-07-31
"""
import os, sys, json, math
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import yfinance as yf
from env_loader import load_env

load_env()

# --- Apex 50K hard rules (from apex-bootcamp/CHECKLIST.md) ---
RISK_USD = 100            # daily SL kill-switch
TP_MIN, TP_MAX = 200, 500 # target TP envelope
RR_MIN, RR_MAX = 2.0, 5.0
POINT_VALUES = {
    "MNQ=F": 2.0,    # Micro Nasdaq
    "MES=F": 5.0,    # Micro S&P
    "MGC=F": 10.0,   # Micro Gold
    "MYM=F": 0.5,    # Micro Dow
    "M2K=F": 5.0,    # Micro Russell
}
SESSION_TZ_OFFSET = -4   # UTC-4 per apex-bootcamp

# --- LLM client (MiniMax) ---
from openai import OpenAI
API_KEY = os.environ.get("MINIMAX_API_KEY")
if not API_KEY:
    raise SystemExit("MINIMAX_API_KEY not set in .env")
client = OpenAI(api_key=API_KEY, base_url="https://api.minimax.io/v1")
MODEL = "MiniMax-M3"


def fetch_data(ticker: str, date_str: str) -> dict:
    """Pull 1d / 1h / 5m around `date_str`. 1h is resampled into H4 blocks too."""
    end = pd.Timestamp(date_str, tz="UTC") + pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=10)  # 10 calendar days back is enough
    t = yf.Ticker(ticker)

    daily = t.history(start=start.tz_localize(None), end=end.tz_localize(None),
                      interval="1d").tz_localize(None)
    hourly = t.history(start=start.tz_localize(None), end=end.tz_localize(None),
                       interval="1h").tz_convert(f"Etc/GMT+{-SESSION_TZ_OFFSET}")
    fivem = t.history(start=start.tz_localize(None), end=end.tz_localize(None),
                      interval="5m").tz_convert(f"Etc/GMT+{-SESSION_TZ_OFFSET}")

    # H4 by resampling 1h
    h4 = (hourly.resample("4h", offset="0h")
                 .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
                 .dropna())

    # Slice to "session date" UTC-4 (the user-provided date)
    target = pd.Timestamp(date_str)
    h1_session = hourly[hourly.index.date == target.date()]
    m5_session = fivem[fivem.index.date == target.date()]
    h4_session = h4[h4.index.date <= target.date()].tail(2)  # last 2 H4 blocks incl target
    daily_window = daily[daily.index.date <= target.date()].tail(5)

    def summarize(df, name):
        if df.empty:
            return f"{name}: empty"
        first, last = df.iloc[0], df.iloc[-1]
        rng_h = df["High"].max()
        rng_l = df["Low"].min()
        vol = df["Volume"].sum()
        return (f"{name}  rows={len(df)}  "
                f"O={first['Open']:.2f}  H={rng_h:.2f}  L={rng_l:.2f}  C={last['Close']:.2f}  "
                f"Vol={vol:,.0f}")

    return {
        "ticker": ticker, "date": date_str,
        "daily": daily_window, "h4": h4_session, "h1": h1_session, "m5": m5_session,
        "summary": "\n".join([
            summarize(daily_window, "1D  "),
            summarize(h4_session,   "H4  "),
            summarize(h1_session,   "H1  "),
            summarize(m5_session,   "5m  "),
        ]),
    }


def compute_levels(data: dict) -> dict:
    """Pre-compute key levels the LLM can quote: PDH/PDL, session H/L, ATR, 20-bar MA."""
    d = data["daily"]
    h1 = data["h1"]
    m5 = data["m5"]

    if len(d) < 2:
        return {}
    prior = d.iloc[-2]  # the day before target
    target_day = d.iloc[-1]
    atr14_d = (pd.concat([d["High"] - d["Low"],
                          (d["High"] - d["Close"].shift()).abs(),
                          (d["Low"]  - d["Close"].shift()).abs()], axis=1).max(axis=1)
                .rolling(14).mean().iloc[-1])

    h1_atr = (pd.concat([h1["High"] - h1["Low"],
                         (h1["High"] - h1["Close"].shift()).abs(),
                         (h1["Low"]  - h1["Close"].shift()).abs()], axis=1).max(axis=1)
                .rolling(14).mean().iloc[-1]) if len(h1) >= 14 else float("nan")

    sess_h = m5["High"].max() if not m5.empty else float("nan")
    sess_l = m5["Low"].min()  if not m5.empty else float("nan")
    sess_close = m5["Close"].iloc[-1] if not m5.empty else float("nan")
    sess_vwap = float((m5["Close"] * m5["Volume"]).sum() / m5["Volume"].sum()) if not m5.empty and m5["Volume"].sum() else float("nan")

    return {
        "PDH": float(prior["High"]),
        "PDL": float(prior["Low"]),
        "PDC": float(prior["Close"]),
        "DO":  float(target_day["Open"]),
        "today_H": float(target_day["High"]),
        "today_L": float(target_day["Low"]),
        "today_C": float(target_day["Close"]),
        "ATR14_D": float(atr14_d),
        "ATR14_H1": float(h1_atr),
        "sess_H": float(sess_h),
        "sess_L": float(sess_l),
        "sess_Close": float(sess_close),
        "sess_VWAP": float(sess_vwap),
    }


def make_prompt(data: dict, levels: dict) -> str:
    pv = POINT_VALUES.get(data["ticker"], 1.0)
    return f"""你是 Apex Trader Funding 50K 帳戶的機械化交易系統。
{ticker} 在 {date} 收盤 UTC-4。
Point value = ${pv}/point。每日 SL 觸及 $100 立即停手，最多 1 張 micro。

【任務】
1) 解讀當日結構（H4 → H1 → 5m）
2) 給出 A / B / C 評級
3) 若非 C：規劃一個 LONG 或 SHORT setup：
   - 進場觸發（5m LTF retest / engulfing / MSS）
   - 止損（必須讓 Risk ≈ $100；i.e. SL distance × point_value × qty(1) ≈ $100，距離約 {100/pv:.1f} 點）
   - TP 必須在 $200-$500 區間（距離 {200/pv:.1f} - {500/pv:.1f} 點）
   - RR 必須在 2.0 - 5.0 之間
   - 若三者無法同時滿足 → 評為 C 跳過

【Market snapshot】
{data['summary']}

【Pre-computed key levels (USD)】
{json.dumps(levels, indent=2)}

【5m last 30 bars (UTC-4) — 用來確認 LTF 觸發】
{data['m5'].tail(30)[['Open','High','Low','Close','Volume']].to_string()}

【H1 last 24 bars】
{data['h1'].tail(24)[['Open','High','Low','Close','Volume']].to_string()}

【H4 last 6 blocks】
{data['h4'].tail(6)[['Open','High','Low','Close','Volume']].to_string()}

【Daily last 5】
{data['daily'].tail(5)[['Open','High','Low','Close','Volume']].to_string()}

【輸出格式（嚴格）】
**Setup Grade**: A | B | C
**Bias**: LONG | SHORT | FLAT
**HTF Narrative** (一句話):
**H1 Structure** (一句話):
**5m Trigger** (一句話):
**Entry**: <price>
**Stop Loss**: <price>  (距離 = <X.X> 點, Risk = $XX)
**Take Profit**: <price>  (距離 = <X.X> 點, Reward = $XX)
**RR**: <X.XX>
**Contracts**: 1 micro
**If C, reason**: 為何不符合機械化規則
"""


def llm_call(prompt: str) -> str:
    r = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "你是一個嚴格的機械化交易員，遵守 Apex 50K 硬限制，不含糊。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    return r.choices[0].message.content


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "MGC=F"
    date   = sys.argv[2] if len(sys.argv) > 2 else "2026-07-31"

    print(f"# Apex 50K Setup — {ticker} @ {date} (UTC-4)\n")
    data = fetch_data(ticker, date)
    print("## Raw timeframe summary\n```\n" + data["summary"] + "\n```\n")

    levels = compute_levels(data)
    print("## Key levels\n```json\n" + json.dumps(levels, indent=2) + "\n```\n")

    prompt = make_prompt(data, levels)
    print("## LLM call (this may take 30-60s)…\n")
    answer = llm_call(prompt)
    print("## Setup output\n")
    print(answer)
