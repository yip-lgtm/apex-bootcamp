"""Apex 50K v2.6 — Daily Pre-Market Reminder

Generates the mechanical-trader checklist with:
- 11 micro futures snapshot
- 3-panel charts (HTF-D / H4 / H1) for top 4 tickers
- LLM A/B/C grading for those 4 tickers

Pushes to Telegram at 20:30 HKT weekdays.
"""
from __future__ import annotations
import os
import sys
import warnings
import logging
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

# Local imports (add src to path)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yfinance as yf
import pandas as pd

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
HKT = timezone(timedelta(hours=8))

# Top tickers for chart + grading (most important Apex 50K instruments)
CHART_TICKERS = [
    ("MGC=F", "Micro Gold"),
    ("MNQ=F", "Micro Nasdaq"),
    ("MCL=F", "Micro Crude"),
    ("MBT=F", "Micro Bitcoin"),
]

# Full snapshot list
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
            rows.append({
                "tk": tk, "name": name,
                "last": float(last["Close"]),
                "chg": chg, "pct": pct,
                "high": float(last["High"]),
                "low": float(last["Low"]),
            })
        except Exception as e:
            rows.append({"tk": tk, "name": name, "err": str(e)[:40]})
    return rows


def fmt_price(v: float) -> str:
    if abs(v) > 1000: return f"{v:,.0f}"
    if abs(v) > 10:   return f"{v:.2f}"
    return f"{v:.4f}"


def fmt_chg_arrow(pct: float) -> str:
    if pct > 0.3:  return "🟢▲"
    if pct > 0:    return "🟢↗"
    if pct < -0.3: return "🔴▼"
    if pct < 0:    return "🔴↘"
    return "🟡→"


def bias_from_pct(pct: float) -> str:
    if pct > 0.5:  return "LONG"
    if pct < -0.5: return "SHORT"
    return "NEUTRAL"


def daily_news_block(date_str: str) -> str:
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


# --- Build reminder message ---
def build_reminder(
    snapshot: list[dict], today_hkt: str, weekday: str,
    grades: list[dict],
) -> str:
    snap_lines = ["📊 **當前快照** (Last close, change vs prior day)", "```"]
    snap_lines.append(f"{'Ticker':<8} {'Name':<20} {'Last':>10}  {'%Chg':>8}  Bias")
    snap_lines.append("-" * 64)
    for s in snapshot:
        if "err" in s:
            snap_lines.append(f"{s['tk']:<8} {s['name']:<20} {'n/a':>10}  {'-':>8}  ?")
            continue
        arrow = fmt_chg_arrow(s["pct"])
        bias = bias_from_pct(s["pct"])
        snap_lines.append(
            f"{s['tk']:<8} {s['name']:<20} {fmt_price(s['last']):>10}  "
            f"{arrow}{s['pct']:>+5.2f}  {bias}"
        )
    snap_lines.append("```")
    snap_text = "\n".join(snap_lines)

    long_tickers = [s["tk"] for s in snapshot if "err" not in s and bias_from_pct(s["pct"]) == "LONG"]
    short_tickers = [s["tk"] for s in snapshot if "err" not in s and bias_from_pct(s["pct"]) == "SHORT"]
    bias_summary = (
        f"📈 **HTF Bias consensus**: "
        f"LONG: {', '.join(long_tickers) if long_tickers else '(none)'}  |  "
        f"SHORT: {', '.join(short_tickers) if short_tickers else '(none)'}"
    )

    news = daily_news_block(today_hkt)

    # LLM A/B/C grades
    grade_lines = ["🎯 **LLM A/B/C 等級 (chart + levels 評估)**", "```"]
    grade_lines.append(f"{'Ticker':<8} {'Grade':<6} Reason")
    grade_lines.append("-" * 60)
    for g in grades:
        if g["grade"] == "?":
            grade_lines.append(f"{g['ticker']:<8} {'?':<6} {g['reason'][:50]}")
        else:
            emoji = {"A": "🟢 A", "B": "🟡 B", "C": "🔴 C"}.get(g["grade"], g["grade"])
            grade_lines.append(f"{g['ticker']:<8} {emoji:<6} {g['reason'][:50]}")
    grade_lines.append("```")
    grade_text = "\n".join(grade_lines)

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
- 確認今日 Higher TF Bias (above ↑ / below ↓)
- 標註 **DOL (PDH / PDC / PDL / ONH / ONL / PMH / PML)**
- 對齊昨日 / 上週結構

### ⏰ Session Killzone 時間
- **NY AM Killzone**：09:00-11:00 ET (核心進場窗口)
- **NY PM Killzone**：13:30-15:00 ET (減倉或觀察)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 2️⃣ 風險規則檢查
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- ✅ **1 張 Micro 合約** 嚴格限制
- ✅ **Daily SL Kill-switch**: -$100 → 即停
- ✅ **Intraday Trail DD**: -$2,000 → 觸發即停
- ✅ **合格獲利日進度**: ≥$250 (half of $500 target)
- ✅ **TP/Trade**: $200-500, RR 2-5
- ✅ **Same-day exit**: EOD 強制平倉

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 3️⃣ LLM A/B/C 判定 (3-chart standard)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{grade_text}

**執行守則**：
- 🟢 **A 級**：滿倉 1 micro，嚴守 SL
- 🟡 **B 級**：減倉 0.5 micro (or 觀察)
- 🔴 **C 級**：直接跳過，唔 chase

**注意**：3 張 chart 附喺 message 後 (HTF-D / H4 / H1 各 ticker)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 4️⃣ 圖表標準
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

每張 chart 包含：
- 📊 **HTF-D** (1D, 90d) — 週 / 月結構
- 📊 **H4** (4-hour, 30d) — 中繼結構
- 📊 **H1** (1-hour, 5d) — 進場 TF

標記：PDH/PDL/PDC、ONH/ONL、Volume、Killzone 窗口

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💪 **今日口號**：
> 「A 級才動手，C 級直接過。保護本金 > 一切。」

🔗 https://github.com/yip-lgtm/apex-bootcamp
"""
    return msg


# --- Telegram send ---
def send_telegram_text(text: str) -> int:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=15)
    return r.status_code


def send_telegram_photos(photo_paths: list[Path], caption: str = "") -> int:
    """Send multiple photos as a media group."""
    if not photo_paths:
        return 0
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMediaGroup"
    # Build media group payload
    media = []
    files = []
    for i, p in enumerate(photo_paths):
        attach_id = f"attach_{i}"
        media.append({
            "type": "photo",
            "media": f"attach://{attach_id}",
            **({"caption": caption} if i == 0 and caption else {}),
        })
        files.append((attach_id, (p.name, open(p, "rb"), "image/png")))
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "media": json.dumps(media),
    }
    r = requests.post(url, data=payload, files=files, timeout=60)
    for f_tuple in files:
        # f_tuple structure: (attach_id, (filename, fileobj, mimetype))
        fh = f_tuple[1][1]
        fh.close()
    return r.status_code


# Need json for media group
import json
import subprocess
import shutil

# --- Save artifacts to repo + git push ---
REPO_DIR = Path("/workspace/apex-bootcamp")
ARTIFACTS_DIR = REPO_DIR / "AUTOMATION" / "reports" / "daily"

# Identity for the auto-push commit (overridable via env)
GIT_USER_NAME = os.environ.get("GIT_USER_NAME", "Apex 皮盤房 bot")
GIT_USER_EMAIL = os.environ.get("GIT_USER_EMAIL", "bot@apex.local")


def git_push_artifacts(repo_dir: Path, paths: list[Path], commit_msg: str) -> int:
    """Stage, commit, push paths in repo_dir. Returns push exit code (0 OK)."""
    # Use HTTPS+PAT if GITHUB_PAT env var present, else SSH
    # Use HTTPS+PAT if GITHUB_PAT env var present, else GITHUB_TOKEN (GHA), else SSH
    pat = os.environ.get("GITHUB_PAT", "") or os.environ.get("GITHUB_TOKEN", "")
    if pat:
        subprocess.run(
            ["git", "-C", str(repo_dir), "remote", "set-url", "origin",
             f"https://x-access-token:{pat}@github.com/yip-lgtm/apex-bootcamp.git"],
            check=False, capture_output=True
        )
    try:
        # git add
        rel_paths = [str(p.relative_to(repo_dir)) for p in paths if p.exists()]
        if not rel_paths:
            print("[git_push] No paths to add")
            return 0
        subprocess.run(
            ["git", "-C", str(repo_dir), "add"] + rel_paths,
            check=True, capture_output=True
        )
        # Check if anything to commit
        r = subprocess.run(
            ["git", "-C", str(repo_dir), "diff", "--cached", "--name-only"],
            capture_output=True, text=True, check=True
        )
        if not r.stdout.strip():
            print("[git_push] Nothing to commit (artifacts unchanged)")
            return 0
        # Commit
        subprocess.run(
            ["git", "-C", str(repo_dir), "-c", f"user.name={GIT_USER_NAME}",
             "-c", f"user.email={GIT_USER_EMAIL}",
             "commit", "-m", commit_msg],
            check=True, capture_output=True
        )
        # Push
        r = subprocess.run(
            ["git", "-C", str(repo_dir), "push", "origin", "main"],
            capture_output=True, text=True
        )
        if r.returncode == 0:
            print(f"[git_push] ✅ Pushed: {commit_msg[:60]}")
            return 0
        else:
            print(f"[git_push] ❌ Push failed: {r.stderr[:200]}")
            return r.returncode
    except subprocess.CalledProcessError as e:
        print(f"[git_push] ❌ Error: {e.stderr[:200] if e.stderr else str(e)[:200]}")
        return 1


# --- Main ---
def main() -> int:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("FATAL: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set", file=sys.stderr)
        return 1

    now_hkt = datetime.now(HKT)
    today_str = now_hkt.strftime("%Y-%m-%d")
    weekday = now_hkt.strftime("%a")

    if weekday in ("Sat", "Sun"):
        print(f"[daily_reminder] {weekday} - skipping (weekend)")
        return 0

    print(f"[daily_reminder] Generating reminder for {today_str} ({weekday})")

    # Step 1: 11-ticker snapshot
    print("[daily_reminder] Pulling 11-ticker snapshot...")
    snapshot = pull_snapshot()

    # Step 2: Generate charts for top 4
    # Save to BOTH /tmp (for TG) and tracked reports dir (for git push)
    print("[daily_reminder] Generating 3-panel charts for top 4 tickers...")
    from chart_gen import generate_for_ticker

    tg_chart_dir = Path("/tmp/apex-charts")
    tg_chart_dir.mkdir(parents=True, exist_ok=True)
    tracked_chart_dir = ARTIFACTS_DIR / today_str
    tracked_chart_dir.mkdir(parents=True, exist_ok=True)

    chart_paths = []   # paths to send via TG (from /tmp)
    tracked_charts = []  # paths to commit to git
    for tk, name in CHART_TICKERS:
        # Generate into /tmp first
        p_tmp, _ = generate_for_ticker(tk, name, tg_chart_dir)
        if p_tmp:
            # Copy to tracked dir for git commit
            p_track = tracked_chart_dir / p_tmp.name
            try:
                shutil.copy2(p_tmp, p_track)
                tracked_charts.append(p_track)
            except Exception as e:
                print(f"  ! copy failed: {e}")
            chart_paths.append(p_tmp)
            print(f"  ✓ {tk} → {p_tmp.name}")

    # Step 3: LLM A/B/C grading
    print("[daily_reminder] Running LLM A/B/C grading...")
    from llm_grader import grade_ticker
    grades = [grade_ticker(tk) for tk, _ in CHART_TICKERS]
    for g in grades:
        print(f"  {g['ticker']:6s} → {g['grade']}  {g['reason'][:60]}")

    # Step 4: Build message
    msg = build_reminder(snapshot, today_str, weekday, grades)

    # Step 4.5: Save text reminder + grades JSON to tracked dir
    print("[daily_reminder] Saving artifacts to AUTOMATION/reports/daily/...")
    txt_path = ARTIFACTS_DIR / today_str / f"reminder-{today_str}.md"
    json_path = ARTIFACTS_DIR / today_str / f"grades-{today_str}.json"
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(msg, encoding="utf-8")
    json_path.write_text(json.dumps({
        "date": today_str,
        "weekday": weekday,
        "generated_hkt": now_hkt.isoformat(),
        "grades": [
            {k: v for k, v in g.items() if k != "summary"}
            for g in grades
        ],
        "snapshot": [{k: v for k, v in s.items() if k != "summary"} for s in snapshot],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {txt_path.relative_to(REPO_DIR)}")
    print(f"  ✓ {json_path.relative_to(REPO_DIR)}")

    # Step 5: Send text message
    print("[daily_reminder] Sending text message to Telegram...")
    code1 = send_telegram_text(msg)
    print(f"[daily_reminder] Text message HTTP {code1}")

    # Step 6: Send charts as media group
    if chart_paths:
        print(f"[daily_reminder] Sending {len(chart_paths)} charts as media group...")
        code2 = send_telegram_photos(chart_paths, caption="📊 3-Chart Standard (HTF-D / H4 / H1)")
        print(f"[daily_reminder] Charts HTTP {code2}")

    # Step 7: Git push artifacts
    print("[daily_reminder] Committing + pushing artifacts to GitHub...")
    artifacts_to_push = [txt_path, json_path] + tracked_charts
    push_code = git_push_artifacts(
        REPO_DIR,
        artifacts_to_push,
        f"auto(reminder): daily analysis {today_str} ({weekday})"
    )
    print(f"[daily_reminder] Git push exit {push_code}")

    return 0 if code1 == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
