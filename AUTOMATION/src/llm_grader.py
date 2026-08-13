"""LLM-based A/B/C grading for daily reminder.

For each ticker, sends a structured text prompt with the levels (PDH, PDL, etc.)
and recent price action summary to MiniMax-M3. Gets back A/B/C grade with reasoning.

A = high-probability setup (multi-TF aligned, clean structure)
B = marginal setup (some alignment, but not clean)
C = skip (no alignment, choppy structure)
"""
from __future__ import annotations
import os
import sys
import json
import logging
import warnings
from typing import Optional

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

import requests
import pandas as pd
import yfinance as yf

API_KEY = os.environ.get("MINIMAX_API_KEY", "")
API_URL = "https://api.minimax.io/v1"
MODEL = "MiniMax-M3"


def fetch_summary(ticker: str) -> dict:
    """Fetch compact summary of price action for LLM context."""
    d = yf.download(ticker, period="10d", interval="1d",
                    progress=False, auto_adjust=True)
    if d.empty:
        return {}
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d1h = yf.download(ticker, period="5d", interval="1h",
                      progress=False, auto_adjust=True)
    if isinstance(d1h.columns, pd.MultiIndex):
        d1h.columns = d1h.columns.get_level_values(0)
    last_d = d.iloc[-1]
    prev_d = d.iloc[-2] if len(d) > 1 else last_d
    h1_last = d1h.iloc[-1] if not d1h.empty else last_d
    h1_5avg = float(d1h["Close"].tail(5).mean()) if len(d1h) >= 5 else float(last_d["Close"])

    # Compute daily range position
    d_range = float(last_d["High"] - last_d["Low"])
    pos_in_range = ((float(last_d["Close"]) - float(last_d["Low"])) / d_range * 100) if d_range else 50

    return {
        "ticker": ticker,
        "last": float(last_d["Close"]),
        "prev_close": float(prev_d["Close"]),
        "today_chg_pct": float((last_d["Close"] - prev_d["Close"]) / prev_d["Close"] * 100),
        "today_open": float(last_d["Open"]),
        "today_high": float(last_d["High"]),
        "today_low": float(last_d["Low"]),
        "PDH": float(prev_d["High"]),
        "PDL": float(prev_d["Low"]),
        "PDC": float(prev_d["Close"]),
        "ONH": float(h1_last["High"]),
        "ONL": float(h1_last["Low"]),
        "h1_5avg": h1_5avg,
        "pos_in_today_range": pos_in_range,
    }


def build_prompt(s: dict) -> str:
    """Build the LLM grading prompt."""
    return f"""你是 Apex 50K v2.6 機械化交易員。評估以下 setup 並給 A/B/C 等級：

Ticker: {s['ticker']}
Last: {s['last']:.2f}
PDH={s['PDH']:.2f} | PDL={s['PDL']:.2f} | PDC={s['PDC']:.2f}
ONH={s['ONH']:.2f} | ONL={s['ONL']:.2f}
Today O={s['today_open']:.2f} H={s['today_high']:.2f} L={s['today_low']:.2f}
Today chg: {s['today_chg_pct']:+.2f}%
Position in today range: {s['pos_in_today_range']:.0f}%
H1 5-bar avg: {s['h1_5avg']:.2f}

Apex 50K v2.6 硬規則：
- HTF alignment required (1D MA5 > MA10 = LONG bias; else SHORT or no trade)
- Killzone entry: 9:00-11:00 EST only
- Risk $100, TP $200-500, RR 2-5
- Same-day exit (no overnight)
- Det engine must confirm: clean structure, no chase

Output format (1 line only):
GRADE: [A/B/C] | REASON: [10 words max Chinese]"""


def grade_ticker(ticker: str) -> dict:
    """Grade one ticker. Returns dict with grade + reason."""
    s = fetch_summary(ticker)
    if not s:
        return {"ticker": ticker, "grade": "?", "reason": "no data"}

    prompt = build_prompt(s)
    try:
        r = requests.post(
            f"{API_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "你是 Apex 50K v2.6 機械化交易員。\n\n輸出規則：\n1. 你可以喺 <think> 標籤入面做 reasoning\n2. 最後 </think> 之後必須輸出 EXACTLY 一行：\n   GRADE: A | REASON: 一句話繁中\n   或 GRADE: B | REASON: 一句話繁中\n   或 GRADE: C | REASON: 一句話繁中\n3. A = high-probability (HTF aligned + clean structure)\n   B = marginal (some alignment)\n   C = skip (no alignment OR chase zone)\n4. 你一定要 finish reasoning 同 output final grade。唔好 truncated。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 1500,
            },
            timeout=30,
        )
        if r.status_code != 200:
            return {"ticker": ticker, "grade": "?", "reason": f"http {r.status_code}"}
        content = r.json()["choices"][0]["message"]["content"].strip()
        # Strip <think>...</think> blocks
        import re
        # Look ONLY in the part after </think>, OR anywhere if not found
        after_think = re.split(r"</think>", content, maxsplit=1)
        search_text = after_think[-1] if len(after_think) > 1 else content
        # Strip leading whitespace + common noise (---, etc)
        search_text = search_text.strip()
        # Remove leading dashes / bullets that LLM sometimes leaves
        search_text = re.sub(r"^[-\s]+", "", search_text)

        m = re.search(
            r"GRADE:\s*([ABC])\s*\|\s*REASON:\s*(.+?)(?:\n|$)",
            search_text, re.MULTILINE | re.IGNORECASE
        )
        if m:
            grade = m.group(1).upper()
            reason = m.group(2).strip()[:80]
        else:
            # No GRADE found — check if response is incomplete (just thinking leaked)
            has_think = "<think>" in content
            after_len = len(search_text)
            if after_len < 5 or search_text in ("", "—", "-"):
                # LLM only output thinking block, no real answer
                grade = "?"
                reason = "LLM incomplete response (only thinking, no GRADE)"
            else:
                # Has some text but no GRADE pattern — try loose match
                m2 = re.search(r"GRADE:\s*([ABC])", search_text, re.IGNORECASE)
                grade = m2.group(1).upper() if m2 else "?"
                reason = search_text[:80] if search_text else "no grade pattern"
        return {"ticker": ticker, "grade": grade, "reason": reason, "summary": s}
    except Exception as e:
        return {"ticker": ticker, "grade": "?", "reason": str(e)[:60]}


def grade_batch(tickers: list[str]) -> list[dict]:
    """Grade multiple tickers."""
    return [grade_ticker(t) for t in tickers]


# --- Priority Ranking ---
# v2.6 backtest 60-day stats (per_ticker)
BACKTEST_PF = {
    "MGC=F": 8.85,  # Gold - best edge
    "MBT=F": 10.0,  # Bitcoin - 1 trade sample, capped at 10
    "MNQ=F": 2.57,  # Nasdaq
    "MCL=F": 0.0,   # Crude - 0 trades
    "MES=F": 1.0, "M2K=F": 1.0, "MYM=F": 1.0,
    "M6A=F": 1.0, "M6B=F": 1.0, "6J=F":  1.0,
}

BACKTEST_AVG = {
    "MGC=F": 224.29,  # $/trade
    "MBT=F": 466.0,
    "MNQ=F": 90.0,
    "MCL=F": 0.0,
    "MES=F": 0.0, "M2K=F": 0.0, "MYM=F": 0.0,
    "M6A=F": 0.0, "M6B=F": 0.0, "6J=F":  0.0,
}

GRADE_WEIGHT = {"A": 30, "B": 20, "C": 5, "?": 0}
# Position sizing based on grade
POSITION_SIZE = {
    "A": 1.0,   # full 1 micro
    "B": 0.5,   # half
    "C": 0.0,   # skip
    "?": 0.0,
}


def priority_score(grade: str, ticker: str) -> float:
    """Composite priority score for trade selection.

    Components:
    - Grade weight:  A=30, B=20, C=5
    - Backtest PF:   scaled to 0-10
    """
    gw = GRADE_WEIGHT.get(grade, 0)
    pf = BACKTEST_PF.get(ticker, 0.0)
    return gw + pf


def rank_trade_candidates(grades: list[dict]) -> list[dict]:
    """Rank grades by priority, attach sizing, return actionable candidates (A/B only).

    Returns sorted list (highest priority first).
    """
    candidates = []
    for g in grades:
        score = priority_score(g["grade"], g["ticker"])
        size = POSITION_SIZE.get(g["grade"], 0.0)
        avg = BACKTEST_AVG.get(g["ticker"], 0.0)
        ev = size * avg  # expected value
        candidates.append({
            **g,
            "priority_score": round(score, 2),
            "size_micro": size,
            "backtest_avg": avg,
            "expected_value_usd": round(ev, 0),
            "actionable": size > 0,
        })
    candidates.sort(key=lambda x: (x["priority_score"], x["grade"] != "A"),
                    reverse=True)
    return candidates


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python llm_grader.py MGC=F MNQ=F ...")
        sys.exit(1)
    results = grade_batch(sys.argv[1:])
    for r in results:
        print(f"  {r['ticker']:6s} | GRADE: {r['grade']} | {r['reason']}")
