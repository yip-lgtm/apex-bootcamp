"""Apex 50K forward-test simulator.
For a given date, runs the v2.6 scanner, then for each actionable A/B setup
simulates the trade entry/exit using 5m data, and appends the result to a
JSONL log for ongoing P&L tracking.

Usage:  .venv/bin/python apex_forward.py [YYYY-MM-DD]
        (default = most recent completed session in UTC-4)
"""
import os, sys, json, time
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from openai import OpenAI

from apex_strategy import (
    TICKERS, fetch, detect_trigger, grade_setup, parse_setup,
    RISK_USD, TP_MIN, TP_MAX, RR_MIN, RR_MAX,
    KILLZONE_START_HOUR, KILLZONE_END_HOUR, SESSION_TZ,
)
from notify import notify_forward_pnl

load_dotenv()

API_KEY = os.environ.get("MINIMAX_API_KEY")
if not API_KEY:
    raise SystemExit("MINIMAX_API_KEY not set in .env")
client = OpenAI(api_key=API_KEY, base_url="https://api.minimax.io/v1")
MODEL  = "MiniMax-M3"

LOG_PATH = "/workspace/reports/apex-forward-log.jsonl"
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)


def session_today() -> str:
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(timezone(timedelta(hours=SESSION_TZ)))
    candidate = (now_et - timedelta(days=1)).date()
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate.isoformat()


def compute_levels(data: dict) -> dict:
    d = data["daily"]; h1 = data["hourly"]; m5 = data["m5"]
    if len(d) < 2: return {}
    prior, today = d.iloc[-2], d.iloc[-1]

    def atr(df, n=14):
        if len(df) < n: return float("nan")
        a = pd.concat([df["High"]-df["Low"],
                       (df["High"]-df["Close"].shift()).abs(),
                       (df["Low"] -df["Close"].shift()).abs()], axis=1).max(axis=1)
        return float(a.rolling(n).mean().iloc[-1])

    sess_vwap = float("nan")
    if not m5.empty and m5["Volume"].sum():
        sess_vwap = float((m5["Close"]*m5["Volume"]).sum() / m5["Volume"].sum())

    return {
        "PDH": float(prior["High"]), "PDL": float(prior["Low"]), "PDC": float(prior["Close"]),
        "DO":  float(today["Open"]),  "today_H": float(today["High"]),
        "today_L": float(today["Low"]), "today_C": float(today["Close"]),
        "ATR14_D": atr(d), "ATR14_H1": atr(h1),
        "sess_H": float(m5["High"].max()) if not m5.empty else float("nan"),
        "sess_L": float(m5["Low"].min())  if not m5.empty else float("nan"),
        "sess_Close": float(m5["Close"].iloc[-1]) if not m5.empty else float("nan"),
        "sess_VWAP": sess_vwap,
    }


def summarize_timeframes(data: dict, day_str: str) -> str:
    def summ(df, name):
        if df.empty: return f"{name}: empty"
        f, l = df.iloc[0], df.iloc[-1]
        return (f"{name}  rows={len(df)}  O={f['Open']:.2f}  H={df['High'].max():.2f}  "
                f"L={df['Low'].min():.2f}  C={l['Close']:.2f}  V={df['Volume'].sum():,.0f}")

    d = data["daily"]; h1 = data["hourly"]; m5 = data["m5"]
    target = pd.Timestamp(day_str)
    h1_sess = h1[h1.index.date == target.date()]
    m5_sess = m5[m5.index.date  == target.date()]
    h4 = (h1.resample("4h")
                .agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"})
                .dropna())
    h4_sess = h4[h4.index.date <= target.date()].tail(2)
    d_win   = d[d.index.date <= target.date()].tail(5)
    return "\n".join([summ(d_win,"1D  "), summ(h4_sess,"H4  "),
                      summ(h1_sess,"H1  "), summ(m5_sess,"5m  ")])


def make_prompt(data: dict, levels: dict, point_value: float, max_contracts: int, date_str: str) -> str:
    ticker = data["ticker"]
    kz_m5 = data["m5"][
        (data["m5"].index.hour >= KILLZONE_START_HOUR) &
        (data["m5"].index.hour <  KILLZONE_END_HOUR)
    ]
    return f"""你是 Apex Trader Funding 50K 帳戶的機械化交易系統（v2.6 策略）。
{ticker} 在 {date_str} (UTC-4) 的收盤結構分析。

【v2.6 硬規則 — 必須全部滿足，否則評 C】
- SL 距離 = $100 / {max_contracts} contracts / ${point_value}/點 = {(RISK_USD/max_contracts)/point_value:.1f} 點
- TP 距離 = $200-$500 / ({max_contracts} × ${point_value}) = {TP_MIN/(point_value*max_contracts):.1f}-{TP_MAX/(point_value*max_contracts):.1f} 點
- RR = 2.0-5.0
- HTF alignment: 1D bias 必須支持 5m direction（逆勢自動 C）
- Killzone: trigger 必須喺 {KILLZONE_START_HOUR}:00-{KILLZONE_END_HOUR}:00 EST
- Structure TP: nearest swing H/L within envelope

【Market snapshot】
{data['summary']}

【Killzone 5m bars (09:00-11:00 EST) — 重點】
{kz_m5.to_string() if not kz_m5.empty else '(no data)'}

【Key levels】
{json.dumps(levels, indent=2)}

【Daily last 5】
{data['daily'].tail(5)[['Open','High','Low','Close','Volume']].to_string()}

【輸出格式】
**Setup Grade**: A | B | C
**Bias**: LONG | SHORT | FLAT
**HTF Narrative**: (一句話)
**H1 Structure**: (一句話)
**5m Trigger**: (一句話)
**Entry**: <price>
**Stop Loss**: <price>  (距離 = <X.X> 點, Risk = $XX)
**Take Profit**: <price>  (距離 = <X.X> 點, Reward = $XX)
**RR**: <X.XX>
**Contracts**: {max_contracts} micro
**If C, reason**: 為何不符
"""


def llm_call(prompt: str) -> str:
    r = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role":"system","content":"嚴格機械化交易員，遵守 Apex 50K v2.6 硬限制：HTF alignment + killzone 9-11 EST + structure TP。"},
            {"role":"user","content": prompt},
        ],
        temperature=0.4,
    )
    return r.choices[0].message.content


def simulate_trade(setup: dict, m5_day: pd.DataFrame, point_value: float,
                   max_contracts: int) -> dict:
    """Given a scanner setup, simulate entry/exit on the same day's 5m data.

    Entry: first 5m bar AFTER the killzone end (11:00) → first post-killzone bar.
    Exit: SL / TP / EOD.
    """
    bias = setup["bias"]
    sl = setup["sl"]
    tp = setup["tp"]
    qty = max_contracts

    # Find the first 5m bar at or after 11:00 EST on the same day
    day_date = m5_day.index[0].date() if len(m5_day) else None
    if day_date is None:
        return {**setup, "pnl_usd": 0.0, "exit_reason": "no_data"}

    # 11:00 EST = hour 11 in UTC-4
    post_kz = m5_day[m5_day.index.hour >= KILLZONE_END_HOUR]
    if post_kz.empty:
        return {**setup, "pnl_usd": 0.0, "exit_reason": "no_post_kz_bars"}

    first_bar = post_kz.iloc[0]
    entry = float(first_bar["Open"])
    # Re-anchor SL/TP distances
    if bias == "LONG":
        sl_adj = entry - setup["sl_dist"]
        tp_adj = entry + setup["tp_dist"]
    else:
        sl_adj = entry + setup["sl_dist"]
        tp_adj = entry - setup["tp_dist"]

    def calc_pnl(exit_px):
        diff = (exit_px - entry) if bias == "LONG" else (entry - exit_px)
        return diff * point_value * qty

    for ts, bar in post_kz.iloc[1:].iterrows():
        if bias == "LONG":
            if bar["Low"] <= sl_adj and bar["High"] >= tp_adj:
                return {**setup, "entry_fill": entry, "exit_price": sl_adj,
                        "exit_reason": "sl_same_bar", "pnl_usd": calc_pnl(sl_adj),
                        "exit_time": str(ts), "sl_actual": sl_adj, "tp_actual": tp_adj}
            if bar["Low"] <= sl_adj:
                return {**setup, "entry_fill": entry, "exit_price": sl_adj,
                        "exit_reason": "sl", "pnl_usd": calc_pnl(sl_adj),
                        "exit_time": str(ts), "sl_actual": sl_adj, "tp_actual": tp_adj}
            if bar["High"] >= tp_adj:
                return {**setup, "entry_fill": entry, "exit_price": tp_adj,
                        "exit_reason": "tp", "pnl_usd": calc_pnl(tp_adj),
                        "exit_time": str(ts), "sl_actual": sl_adj, "tp_actual": tp_adj}
        else:
            if bar["High"] >= sl_adj and bar["Low"] <= tp_adj:
                return {**setup, "entry_fill": entry, "exit_price": sl_adj,
                        "exit_reason": "sl_same_bar", "pnl_usd": calc_pnl(sl_adj),
                        "exit_time": str(ts), "sl_actual": sl_adj, "tp_actual": tp_adj}
            if bar["High"] >= sl_adj:
                return {**setup, "entry_fill": entry, "exit_price": sl_adj,
                        "exit_reason": "sl", "pnl_usd": calc_pnl(sl_adj),
                        "exit_time": str(ts), "sl_actual": sl_adj, "tp_actual": tp_adj}
            if bar["Low"] <= tp_adj:
                return {**setup, "entry_fill": entry, "exit_price": tp_adj,
                        "exit_reason": "tp", "pnl_usd": calc_pnl(tp_adj),
                        "exit_time": str(ts), "sl_actual": sl_adj, "tp_actual": tp_adj}

    last_close = float(post_kz["Close"].iloc[-1])
    return {**setup, "entry_fill": entry, "exit_price": last_close,
            "exit_reason": "eod", "pnl_usd": calc_pnl(last_close),
            "exit_time": str(post_kz.index[-1]),
            "sl_actual": sl_adj, "tp_actual": tp_adj}


def scan_and_simulate_one(ticker: str, point_value: float, label: str,
                          max_contracts: int, date_str: str, mode: str = "combined") -> dict:
    t0 = time.time()
    try:
        data = fetch(ticker,
                     (pd.Timestamp(date_str) - pd.Timedelta(days=10)).strftime("%Y-%m-%d"),
                     (pd.Timestamp(date_str) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
        if data["fivem"].empty:
            return {"ticker": ticker, "date": date_str, "ok": False,
                    "error": "no_data", "elapsed_s": time.time()-t0}

        data_p = {**data, "m5": data["fivem"]}
        data_p["summary"] = summarize_timeframes(data_p, date_str)
        levels = compute_levels(data_p)

        # Deterministic grade for ground truth
        trig = detect_trigger(data["fivem"], pd.Timestamp(date_str))
        det_grade = "C"
        det_setup = None
        if trig is not None:
            det_setup = grade_setup(trig, data["daily"], pd.Timestamp(date_str),
                                    point_value, max_contracts)
            if det_setup is not None:
                det_grade = det_setup.get("grade", "C")

        # LLM grade
        prompt = make_prompt(data_p, levels, point_value, max_contracts, date_str)
        answer = llm_call(prompt)
        parsed = parse_setup(answer)

        # Sanity: LLM may return N/A for entry/SL/TP if it graded C
        try:
            if parsed["grade"] in ("A", "B"):
                _ = float(parsed["entry"]); _ = float(parsed["sl"]); _ = float(parsed["tp"])
        except (ValueError, TypeError):
            parsed["grade"] = "C"
            parsed["validation"]["violations"].append("non_numeric_entry_sl_tp")
            parsed["validation"]["passes"] = False

        # Simulate the trade (use deterministic setup if LLM failed, else use LLM)
        # We always use the deterministic setup if it's A/B (most reliable)
        sim_source = "det"
        # Decide which setup to simulate based on --mode
        sim_setup = None
        if mode == "det-only":
            if det_setup and det_setup.get("grade") in ("A", "B"):
                sim_setup = det_setup
                sim_source = "det"
        elif mode == "llm-only":
            if parsed["grade"] in ("A", "B") and parsed["validation"]["passes"]:
                try:
                    sim_source = "llm"
                    sim_setup = {
                        "bias": parsed["bias"], "sl": float(parsed["sl"]),
                        "tp": float(parsed["tp"]),
                        "sl_dist": abs(float(parsed["sl"]) - float(parsed["entry"])),
                        "tp_dist": abs(float(parsed["tp"]) - float(parsed["entry"])),
                    }
                except (ValueError, TypeError):
                    sim_setup = None
        else:  # combined: prefer det, fallback to LLM
            if det_setup and det_setup.get("grade") in ("A", "B"):
                sim_setup = det_setup
                sim_source = "det"
            elif parsed["grade"] in ("A", "B") and parsed["validation"]["passes"]:
                try:
                    sim_source = "llm"
                    sim_setup = {
                        "bias": parsed["bias"], "sl": float(parsed["sl"]),
                        "tp": float(parsed["tp"]),
                        "sl_dist": abs(float(parsed["sl"]) - float(parsed["entry"])),
                        "tp_dist": abs(float(parsed["tp"]) - float(parsed["entry"])),
                    }
                except (ValueError, TypeError):
                    sim_setup = None

        sim_result = None
        if sim_setup is not None:
            m5_day = data["fivem"][data["fivem"].index.date == pd.Timestamp(date_str).date()]
            sim_result = simulate_trade(sim_setup, m5_day, point_value, max_contracts)
            sim_result["source"] = sim_source

        return {
            "ticker": ticker, "label": label, "date": date_str, "ok": True,
            "elapsed_s": time.time()-t0,
            "det_grade": det_grade, "det_setup": det_setup,
            "llm_answer": answer, "llm_parsed": parsed,
            "sim_result": sim_result,
        }
    except Exception as e:
        return {"ticker": ticker, "date": date_str, "ok": False,
                "error": f"{type(e).__name__}: {e}", "elapsed_s": time.time()-t0}


def append_log(entries: list):
    """Append entries to JSONL log."""
    with open(LOG_PATH, "a") as f:
        for entry in entries:
            f.write(json.dumps(entry, default=str) + "\n")


def render_day(date_str: str, results: list) -> str:
    """Render a one-day forward test report."""
    lines = [f"# Forward Test — {date_str}\n"]
    lines.append("## Setup proposals\n")
    lines.append("| Ticker | LLM | Det | Sim Source | Sim P&L | Exit | Pattern |")
    lines.append("|--------|-----|-----|------------|---------|------|---------|")
    for r in results:
        if not r["ok"]:
            lines.append(f"| {r['ticker']} | ERR | — | — | — | — | {r.get('error','')} |")
            continue
        llm = r["llm_parsed"]["grade"]
        det = r["det_grade"]
        sim = r.get("sim_result")
        if sim:
            pnl = sim["pnl_usd"]
            reason = sim["exit_reason"]
            src = sim.get("source", "?")
            pattern = (r["det_setup"] or {}).get("pattern", "?") if src == "det" else "llm"
            lines.append(f"| {r['ticker']} | **{llm}** | {det} | {src} | ${pnl:+.0f} | {reason} | {pattern} |")
        else:
            lines.append(f"| {r['ticker']} | **{llm}** | {det} | — | no sim | no trade | — |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("date", nargs="?", default=None)
    parser.add_argument("--mode", choices=["combined", "det-only", "llm-only"],
                        default="combined",
                        help="combined = LLM with det fallback; det-only = use only deterministic engine; llm-only = use only LLM")
    args = parser.parse_args()
    date_str = args.date if args.date else session_today()
    print(f"# Forward Test — {date_str} (UTC-4) — mode={args.mode}\n")

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(scan_and_simulate_one, tk, pv, lab, mc, date_str, args.mode): tk
                for tk, pv, lab, mc in TICKERS}
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            grade = r["llm_parsed"]["grade"] if r["ok"] else "ERR"
            det = r.get("det_grade", "-")
            sim = r.get("sim_result") or {}
            pnl = sim.get("pnl_usd", 0)
            reason = sim.get("exit_reason", "-")
            print(f"  ✓ {r['ticker']:6s}  llm={grade}  det={det}  "
                  f"sim_pnl=${pnl:+.0f}  ({reason})  {r['elapsed_s']:.1f}s")

    order = {tk: i for i, (tk, *_ ) in enumerate(TICKERS)}
    results.sort(key=lambda r: order.get(r["ticker"], 99))

    # Day P&L
    day_pnl = sum((r.get("sim_result") or {}).get("pnl_usd", 0) for r in results)
    n_trades = sum(1 for r in results if r.get("sim_result"))
    print(f"\nDay P&L: ${day_pnl:+.0f} over {n_trades} simulated trades\n")

    print(render_day(date_str, results))

    # Append to log
    log_entries = []
    for r in results:
        if r.get("sim_result"):
            log_entries.append({
                "date": date_str,
                "ticker": r["ticker"],
                "llm_grade": r["llm_parsed"]["grade"],
                "det_grade": r.get("det_grade"),
                "source": r["sim_result"].get("source"),
                "pnl_usd": r["sim_result"]["pnl_usd"],
                "exit_reason": r["sim_result"]["exit_reason"],
                "entry_fill": r["sim_result"].get("entry_fill"),
                "exit_price": r["sim_result"].get("exit_price"),
                "sl": r["sim_result"].get("sl_actual"),
                "tp": r["sim_result"].get("tp_actual"),
                "exit_time": r["sim_result"].get("exit_time"),
            })
    if log_entries:
        append_log(log_entries)
        print(f"\n# Logged {len(log_entries)} trades → {LOG_PATH}")

        # Webhook notification with day's P&L
        try:
            cum = day_pnl
            try:
                with open(LOG_PATH) as f:
                    for line in f:
                        try:
                            e = json.loads(line)
                            cum += float(e.get("pnl_usd", 0))
                        except Exception:
                            continue
            except FileNotFoundError:
                pass
            results_wh = notify_forward_pnl(day_pnl, cum, n_trades, date_str)
            print(f"# Notified channels: {results_wh}")
        except Exception as e:
            print(f"# Notify failed: {e}")
