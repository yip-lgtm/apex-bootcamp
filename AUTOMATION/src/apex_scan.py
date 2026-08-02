"""Apex 50K daily scanner (v2.6 aligned with backtest).
Runs all 4 micro futures in parallel, calls MiniMax-M3 to grade each with
v2.6 rules (HTF alignment required, structure TP, killzone-aware), then
emits one consolidated markdown report.

Usage:  .venv/bin/python apex_scan.py [YYYY-MM-DD]
        (default = most recent completed session in UTC-4)
"""
import os, sys, json, re, time
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
from notify import notify_actionable_setups

load_dotenv()

# --- LLM client (MiniMax) ---
API_KEY = os.environ.get("MINIMAX_API_KEY")
if not API_KEY:
    raise SystemExit("MINIMAX_API_KEY not set in .env")
client = OpenAI(api_key=API_KEY, base_url="https://api.minimax.io/v1")
MODEL  = "MiniMax-M3"


def session_today() -> str:
    """Most recent completed trading day in UTC-4."""
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(timezone(timedelta(hours=SESSION_TZ)))
    candidate = (now_et - timedelta(days=1)).date()
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate.isoformat()


def compute_levels(data: dict) -> dict:
    """Pre-compute key levels the LLM can quote."""
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
    """One-line per timeframe for the LLM prompt."""
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


def make_prompt(data: dict, levels: dict, point_value: float,
                max_contracts: int, date_str: str) -> str:
    """v2.6 prompt with killzone + HTF + structure TP rules."""
    ticker = data["ticker"]
    # Filter 5m to killzone window for the LLM to focus on
    kz_m5 = data["m5"][
        (data["m5"].index.hour >= KILLZONE_START_HOUR) &
        (data["m5"].index.hour <  KILLZONE_END_HOUR)
    ]

    return f"""你是 Apex Trader Funding 50K 帳戶的機械化交易系統（v2.6 策略）。
{ticker} 在 {date_str} (UTC-4) 的收盤結構分析。

【v2.6 硬規則 — 必須全部滿足，否則評 C】

**Risk sizing**:
- 1 micro contract: SL 距離 = $100 / ${point_value}/點 = {RISK_USD/point_value:.1f} 點
- {max_contracts} micro contracts: SL 距離 = $100 / {max_contracts} / ${point_value}/點 = {(RISK_USD/max_contracts)/point_value:.1f} 點
- 每日 SL 觸及 $100 立即停手

**Reward envelope**: TP 距離 × ${point_value}/點 × {max_contracts} contracts = $200-$500
  → TP 距離 = {TP_MIN/(point_value*max_contracts):.1f} - {TP_MAX/(point_value*max_contracts):.1f} 點

**RR**: 必須 2.0 - 5.0

**HTF alignment (NEW v2.6)**: 1D 趨勢必須支持 5m bias
- LONG 觸發: 需要 close > MA5 > MA10（多頭排列）OR 3日淨漲 > 0.5%
- SHORT 觸發: 需要 close < MA5 < MA10（空頭排列）OR 3日淨跌 < -0.5%
- 逆勢 (1+1) → 自動評 C 跳過

**Killzone (NEW v2.6)**: 只考慮 {KILLZONE_START_HOUR}:00-{KILLZONE_END_HOUR}:00 EST 的 5m bars
- 觸發必須喺呢個 2 小時 window 內先算數
- 出窗後唔再考慮，避免下午低流動性 false signals

**Structure TP (NEW v2.6)**: TP 優先用 nearest swing H/L
- LONG: 用觸發後最近 swing high
- SHORT: 用觸發後最近 swing low
- 結構 TP 喺 $200-500 envelope 內先採用
- 太近 (< $200) → C
- 太遠 (> $500) → cap 去 $500

【任務流程】
1) 確認 HTF 1D bias
2) 喺 9:00-11:00 EST 5m 找 trigger (MSS / ORB / engulfing / pin bar / VWAP reject)
3) 驗證 trigger 對齊 HTF bias
4) 計算結構 TP，符合 envelope → A/B，否則 C
5) 給出 grade + entry/SL/TP/RR + contracts

【Market snapshot】
{data['summary']}

【Killzone 5m bars (09:00-11:00 EST) — 重點分析】
{kz_m5.to_string() if not kz_m5.empty else '(no killzone data)'}

【Key levels (USD)】
{json.dumps(levels, indent=2)}

【H1 last 24 bars】
{data['hourly'].tail(24)[['Open','High','Low','Close','Volume']].to_string()}

【H4 (resampled) last 6 blocks】
{(data['hourly'].resample("4h")
                .agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"})
                .dropna().tail(6)[['Open','High','Low','Close','Volume']].to_string())}

【Daily last 5】
{data['daily'].tail(5)[['Open','High','Low','Close','Volume']].to_string()}

【輸出格式（嚴格按此結構）】
**Setup Grade**: A | B | C
**Bias**: LONG | SHORT | FLAT
**HTF Narrative**: (一句話，必須講 1D 趨勢支持與否)
**H1 Structure**: (一句話)
**5m Trigger**: (一句話，必須註明係 9-11 EST 邊個 pattern)
**Entry**: <price>
**Stop Loss**: <price>  (距離 = <X.X> 點, Risk = $XX)
**Take Profit**: <price>  (距離 = <X.X> 點, Reward = $XX)
**RR**: <X.XX>
**Contracts**: {max_contracts} micro
**If C, reason**: 為何不符合機械化規則 (HTF逆勢 / 結構TP出range / killzone外)
"""


def llm_call(prompt: str) -> str:
    r = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role":"system","content":"你是一個嚴格的機械化交易員，遵守 Apex 50K v2.6 硬限制：HTF alignment + killzone 9-11 EST + structure TP。絕不妥協。"},
            {"role":"user",  "content": prompt},
        ],
        temperature=0.4,
    )
    return r.choices[0].message.content


def scan_one(ticker: str, point_value: float, label: str, max_contracts: int,
             date_str: str) -> dict:
    t0 = time.time()
    try:
        data = fetch(ticker,
                     (pd.Timestamp(date_str) - pd.Timedelta(days=10)).strftime("%Y-%m-%d"),
                     (pd.Timestamp(date_str) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
        if "error" in data or data["fivem"].empty:
            return {"ticker": ticker, "label": label, "ok": False,
                    "error": "no data", "elapsed_s": time.time()-t0}

        # Pre-screen via deterministic engine — get a baseline grade
        trig = detect_trigger(data["fivem"], pd.Timestamp(date_str))
        det_grade = "C"
        if trig is not None:
            setup = grade_setup(trig, data["daily"], pd.Timestamp(date_str),
                                point_value, max_contracts)
            if setup is not None:
                det_grade = setup.get("grade", "C")

        # Adapter: scanner historically uses "m5" + "summary" keys; data dict has "fivem"
        data_for_prompt = {**data, "m5": data["fivem"]}
        data_for_prompt["summary"] = summarize_timeframes(data_for_prompt, date_str)
        levels = compute_levels(data_for_prompt)
        prompt = make_prompt(data_for_prompt, levels, point_value, max_contracts, date_str)
        answer = llm_call(prompt)
        parsed = parse_setup(answer)
        return {
            "ticker": ticker, "label": label, "ok": True, "elapsed_s": time.time()-t0,
            "answer": answer, "parsed": parsed,
            "det_grade": det_grade, "trig_detected": trig is not None,
        }
    except Exception as e:
        return {"ticker": ticker, "label": label, "ok": False,
                "error": f"{type(e).__name__}: {e}", "elapsed_s": time.time()-t0}


def render_report(date_str: str, results: list) -> str:
    lines = [f"# Apex 50K Daily Scan (v2.6) — {date_str} (UTC-4)\n"]
    lines.append(f"_Generated: {datetime.now().isoformat(timespec='seconds')}_\n")
    lines.append("**Tickers:** MGC=F, MNQ=F, MBT=F, MCL=F  |  "
                 "**Rules (v2.6):** HTF alignment required · killzone 09:00-11:00 EST · "
                 "structure TP · Risk $100 / TP $200-500 / RR 2-5 / daily kill-switch $100\n\n")

    lines.append("## Summary table\n")
    lines.append("| Ticker | LLM Grade | Det Grade | Bias | Entry | SL | TP | Risk | Reward | RR | Validates? | Time |")
    lines.append("|--------|-----------|-----------|------|-------|----|----|------|--------|----|----|-----------|")
    for r in results:
        if not r["ok"]:
            lines.append(f"| {r['ticker']} | ERR | — | — | — | — | — | — | — | — | ❌ {r.get('error','')} | {r['elapsed_s']:.0f}s |")
            continue
        p = r["parsed"]
        v = "✅" if p["validation"]["passes"] else f"❌ {', '.join(p['validation']['violations'])}"
        lines.append(
            f"| {r['ticker']} | **{p['grade']}** | {r.get('det_grade','-')} | {p['bias']} | {p['entry']} | {p['sl']} | "
            f"{p['tp']} | ${p.get('risk','?')} | ${p.get('reward','?')} | {p['rr']} | {v} | {r['elapsed_s']:.0f}s |"
        )
    lines.append("\n_LLM Grade = MiniMax-M3 verdict · Det Grade = mechanical pre-screen (v2.6 engine)_\n")
    lines.append("---\n")

    actionable = [r for r in results if r["ok"]
                  and r["parsed"]["grade"] in ("A", "B")
                  and r["parsed"]["validation"]["passes"]]
    skipped = [r for r in results if r["ok"]
               and not (r["parsed"]["grade"] in ("A", "B")
                        and r["parsed"]["validation"]["passes"])]

    lines.append(f"## 🎯 Actionable (A/B + mechanical ✓): {len(actionable)}\n")
    if actionable:
        for r in actionable:
            lines.append(f"### {r['ticker']} — Grade {r['parsed']['grade']}\n")
            lines.append("```")
            lines.append(r["answer"].strip())
            lines.append("```\n")
    else:
        lines.append("_None — all setups are C, or A/B failed mechanical check._\n")

    lines.append(f"\n## ⏭ Skipped ({len(skipped)})\n")
    for r in skipped:
        if not r["ok"]:
            lines.append(f"### {r['ticker']} — fetch error: {r.get('error','')}\n")
            continue
        p = r["parsed"]
        reason = []
        if p["grade"] == "C":
            reason.append("Grade C")
        if p["validation"]["violations"]:
            reason.append("mechanical: " + "; ".join(p["validation"]["violations"]))
        lines.append(f"### {r['ticker']} — {' / '.join(reason) or 'skipped'}\n")
        lines.append("<details><summary>Show LLM analysis</summary>\n")
        lines.append("```")
        lines.append(r["answer"].strip()[:2000])
        lines.append("```\n</details>\n")

    return "\n".join(lines)


if __name__ == "__main__":
    date_str = sys.argv[1] if len(sys.argv) > 1 else session_today()
    print(f"# Apex 50K Daily Scan (v2.6) — {date_str} (UTC-4)")
    print(f"# Running {len(TICKERS)} tickers in parallel…\n")

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(scan_one, tk, pv, lab, mc, date_str): tk
                for tk, pv, lab, mc in TICKERS}
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            tag = "✓" if r["ok"] else "✗"
            grade = r["parsed"]["grade"] if r["ok"] else "ERR"
            det = r.get("det_grade", "-")
            print(f"  {tag} {r['ticker']:6s}  llm={grade}  det={det}  {r['elapsed_s']:.1f}s")

    order = {tk: i for i, (tk, *_ ) in enumerate(TICKERS)}
    results.sort(key=lambda r: order.get(r["ticker"], 99))

    report = render_report(date_str, results)

    print("\n" + "="*78 + "\n")
    print(report)

    out_dir = "/workspace/reports"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"apex-scan-{date_str}.md")
    with open(out_path, "w") as f:
        f.write(report)
    print(f"\n# Saved → {out_path}")

    # Webhook notification for actionable setups
    actionable_data = []
    for r in results:
        if r["ok"] and r["parsed"]["grade"] in ("A", "B") and r["parsed"]["validation"]["passes"]:
            p = r["parsed"]
            actionable_data.append({
                "ticker": r["ticker"],
                "grade": p["grade"],
                "bias": p["bias"],
                "entry": p["entry"],
                "sl": p["sl"],
                "tp": p["tp"],
                "rr": p["rr"],
                "contracts": p.get("contracts", "1"),
                "pattern": (r.get("det_setup") or {}).get("pattern", "llm"),
            })
    if actionable_data:
        try:
            results_wh = notify_actionable_setups(actionable_data, date_str)
            print(f"# Notified channels: {results_wh}")
        except Exception as e:
            print(f"# Notify failed: {e}")
