"""Apex 50K v2.6 — Daily Pre-Market Reminder
Generates the mechanical-trader checklist and pushes to Telegram at 20:30 HKT.

Schedule: weekdays only (Mon-Fri)
Target: HKT 20:30 = 12:30 UTC = 30 min before US market open
"""
from __future__ import annotations
import os
import sys
import warnings
import logging
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

# --- Constants ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
HKT = timezone(timedelta(hours=8))
ET = timezone(timedelta(hours=-4))

WATCHLIST = [
    ("MES=F", "Micro S&P 500"),
    ("MNQ=F", "Micro Nasdaq"),
    ("M2K=F", "Micro Russell 2000"),
    ("MYM=F", "Micro Dow"),
    ("M6E=F", "Micro EUR/USD"),
    ("M6A=F", "Micro AUD/USD"),
    ("MCL=F", "Micro Crude Oil"),
    ("MBT=F", "Micro Bitcoin"),
    ("MET=F", "Micro Ether"),
    ("MGC=F", "Micro Gold"),
    ("SI=F",  "Micro Silver"),
]

# --- 11-futures snapshot ---
def pull_snapshot() -> list[dict]:
    """Pull daily close + change for the watchlist."""
    rows = []
    for tk, name in WATCHLIST:
        try:
            d = yf.download(tk, period="10d", interval="1d",
                            progress=False, auto_adjust=True)
            if d.empty:
                rows.append({"tk": tk, "name": name, "err": "no data"})
                continue
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            last = d.iloc[-1]
            prev = d.iloc[-2] if len(d) > 1 else last
            chg = float(last["Close"] - prev["Close"])
            pct = float(chg / prev["Close"] * 100) if prev["Close"] else 0.0
            high14 = float(d["High"].tail(14).max()) if len(d) >= 14 else float(last["High"])
            low14 = float(d["Low"].tail(14).min()) if len(d) >= 14 else float(last["Low"])
            rows.append({
                "tk": tk, "name": name,
                "last": float(last["Close"]),
                "chg": chg, "pct": pct,
                "high": float(last["High"]),
                "low": float(last["Low"]),
                "high14": high14, "low14": low14,
            })
        except Exception as e:
            rows.append({"tk": tk, "name": name, "err": str(e)[:40]})
    return rows


def fmt_price(v: float) -> str:
    if abs(v) > 1000:
        return f"{v:,.0f}"
    if abs(v) > 10:
        return f"{v:.2f}"
    return f"{v:.4f}"


def fmt_chg_arrow(pct: float) -> str:
    if pct > 0.3: return "🟢▲"
    if pct > 0:   return "🟢↗"
    if pct < -0.3: return "🔴▼"
    if pct < 0:   return "🔴↘"
    return "🟡→"


def bias_from_pct(pct: float) -> str:
    if pct > 0.5:  return "LONG"
    if pct < -0.5: return "SHORT"
    return "NEUTRAL"


# --- Daily news (USD high impact) ---
def daily_news_block(date_str: str) -> str:
    """Return a curated list of expected US data releases today.
    Falls back to a generic note when not in a known window.
    """
    # Static reference — replace with real calendar integration later
    # (e.g., forexfactory API, investing.com scraper, or Finnhub calendar)
    weekday = datetime.strptime(date_str, "%Y-%m-%d").strftime("%a")
    typical = {
        "Mon": ["No major US data expected pre-market"],
        "Tue": ["8:30 ET — NY Fed / Consumer Confidence (Tue)"],
        "Wed": ["8:30 ET — CPI / Retail Sales (mid-month)"],
        "Thu": ["8:30 ET — Initial Jobless Claims / PPI / Philly Fed"],
        "Fri": ["8:30 ET — Industrial Production / Consumer Sentiment"],
    }
    items = typical.get(weekday, [])
    if not items:
        return "• No specific data scheduled"
    return "\n".join(f"  • {x}" for x in items)


# --- Build the reminder message ---
def build_reminder(snapshot: list[dict], today_hkt: str, weekday: str) -> str:
    """Construct the full daily reminder text."""
    # --- Snapshot table ---
    snap_lines = []
    snap_lines.append(f"📊 **當前快照** (Last close, change vs prior day)")
    snap_lines.append("```")
    snap_lines.append(f"{'Ticker':<8} {'Name':<20} {'Last':>10}  {'%Chg':>7}  Bias")
    snap_lines.append("-" * 64)
    for s in snapshot:
        if "err" in s:
            snap_lines.append(f"{s['tk']:<8} {s['name']:<20} {'n/a':>10}  {'-':>7}  ?")
            continue
        arrow = fmt_chg_arrow(s["pct"])
        bias = bias_from_pct(s["pct"])
        snap_lines.append(
            f"{s['tk']:<8} {s['name']:<20} {fmt_price(s['last']):>10}  "
            f"{arrow}{s['pct']:>+5.2f}  {bias}"
        )
    snap_lines.append("```")
    snap_text = "\n".join(snap_lines)

    # --- Bias summary ---
    long_tickers = [s["tk"] for s in snapshot if "err" not in s and bias_from_pct(s["pct"]) == "LONG"]
    short_tickers = [s["tk"] for s in snapshot if "err" not in s and bias_from_pct(s["pct"]) == "SHORT"]
    bias_summary = (
        f"📈 **HTF Bias (multi-ticker consensus)**: "
        f"LONG: {', '.join(long_tickers) if long_tickers else '(none)'}  |  "
        f"SHORT: {', '.join(short_tickers) if short_tickers else '(none)'}"
    )

    # --- News block ---
    news = daily_news_block(today_hkt)

    # --- Build full message ---
    msg = f"""🚨 **A 皮盤房 v2.6 — 每日執行提醒** 🚨
📅 {today_hkt} ({weekday})  ⏰ 20:30 HKT / 12:30 UTC / 08:30 ET (T-30min)
🔥 **核心重點：A 級優先執行 → B 級減倉 → C 級直接跳過**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 1️⃣ 開盤前準備
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### 📰 當日經濟數據
{news}

### 📈 自動拉圖分析（11 個 micro futures）
{snap_text}

### 🎯 Weekly Profile / HTF Bias
{bias_summary}

### 📅 Daily Bias & DOL (Day-of-Level)
- 確認今日 Higher TF Bias（above ↑ / below ↓）
- 標註 **DOL (PDH / PDC / PDL / ONH / ONL / PMH / PML)**
- 對齊昨日 / 上週結構，識別 **Asia / London 預期方向**

### ⏰ Session Killzone 時間
- **NY AM Killzone**：09:00-11:00 ET (核心進場窗口)
- **NY PM Killzone**：13:30-15:00 ET (減倉或觀察)
- **Asia / London**：僅用於 HTF 結構確認，不主動進場

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 2️⃣ 風險規則檢查 (Apex 50K Hard Limits)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- ✅ **單倉限制**：嚴格 **1 張 Micro 合約**（無論任何 setup）
- ✅ **Daily SL Kill-switch**：**-$100** → 即停當日所有交易
- ✅ **Intraday Trail Drawdown**：累計 **-$2,000** → 觸發即停
- ✅ **合格獲利日進度**：單日 **≥ $250**（half of $500 target）
- ✅ **Max TP / Trade**：單 trade TP **$200-500**，RR 鎖定 **2:1 ~ 5:1**
- ✅ **Same-day exit**：未平倉部位 EOD 強制平倉，不持倉過夜

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 3️⃣ 規則初篩 + LLM 二次判斷流程
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**流程 (v2.6)**：
```
[1] 程式初篩 (apex_scan.py)
    ↓ A/B/C grade + Det 引擎判斷
[2] LLM 自動拉圖 (WeBull/TV 3 張)
    ↓ HTF-D / H4 / H1
[3] 填模板給 LLM (MiniMax-M3)
    ↓ 多週期驗證 + HTF alignment
[4] 最終 grade
    ↓
[5] 執行 (A 滿倉) / (B 半倉) / (C 跳過)
```

**執行守則**：
- **A 級 (2+2)**：**滿倉 1 micro**，嚴守 SL，不加碼
- **B 級 (1+1)**：**減倉 0.5 micro** (or 觀察)，等 A 級確認再進
- **C 級 (0+0)**：**直接跳過**，唔好 chase
- **A→C 衝突**：以 Det 引擎為準，LLM 唔可以 override Det

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 4️⃣ 圖表標準 (3 張必備)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- 📊 **HTF Daily**：週 / 月結構 + 關鍵 S/R
- 📊 **H4**：當日趨勢 + 中繼結構
- 📊 **H1 / 5m**：進場 K 線形態 + Killzone 標記

**標記要求**：
- ✅ 標注 PDH/PDL/PDC、ONH/ONL、PMH/PML
- ✅ 標注進場點、SL、TP
- ✅ 標注 Risk / Reward ratio
- ✅ 標注 killzone 窗口

**交易記錄**：
- 入場後即時更新 **Equity / 合格日 / PnL / Win Rate / RR**
- 每 trade 結束後檢討：**有無違反機械化規則？**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💪 **今日口號**：
> 「A 級才動手，C 級直接過。保護本金 > 一切。」

🔗 https://github.com/yip-lgtm/apex-bootcamp
"""
    return msg


def send_telegram(text: str) -> int:
    """Send a message to Telegram. Returns HTTP code."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=15)
    return r.status_code


def main() -> int:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("FATAL: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set", file=sys.stderr)
        return 1

    now_hkt = datetime.now(HKT)
    today_str = now_hkt.strftime("%Y-%m-%d")
    weekday = now_hkt.strftime("%a")

    # Skip weekends
    if weekday in ("Sat", "Sun"):
        print(f"[daily_reminder] {weekday} - skipping (weekend)")
        return 0

    print(f"[daily_reminder] Generating reminder for {today_str} ({weekday})")
    snapshot = pull_snapshot()
    msg = build_reminder(snapshot, today_str, weekday)
    code = send_telegram(msg)
    print(f"[daily_reminder] Telegram HTTP {code}")
    return 0 if code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
