#!/usr/bin/env python3
"""
Apex Bootcamp - 每日績效數據處理腳本（支援 HTML 報告解析）

用法一：直接帶參數
  python update_performance.py --pnl -23 --trades 3 --wins 1 --rr 1.5

用法二：從報告文字檔解析（推薦）
  1. 在 daily-report.html 產生報告後複製
  2. 貼到 report.txt 存檔
  3. python update_performance.py --from-report report.txt
"""

import argparse
import re
from datetime import datetime
from pathlib import Path

DAILY_LOG = Path(__file__).parent.parent / "PERFORMANCE" / "daily-log.md"
SUMMARY = Path(__file__).parent.parent / "PERFORMANCE" / "summary.md"

def parse_existing_log():
    if not DAILY_LOG.exists():
        return []
    lines = DAILY_LOG.read_text(encoding="utf-8").splitlines()
    rows = []
    for line in lines:
        if line.startswith("|") and "日期" not in line and "---" not in line and line.count("|") >= 7:
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if parts and parts[0] and parts[0] != "-":
                rows.append(parts)
    return rows

def append_daily_row(date, pnl, trades, wins, avg_rr, note=""):
    rows = parse_existing_log()

    total_pnl = sum(float(r[1]) for r in rows if r[1] not in ("-", "")) + float(pnl)
    total_trades = sum(int(float(r[2])) for r in rows if r[2] not in ("-", "")) + int(trades)
    total_wins = sum(int(float(r[3])) for r in rows if r[3] not in ("-", "")) + int(wins)
    win_rate = f"{(total_wins / total_trades * 100):.1f}%" if total_trades > 0 else "0%"

    new_row = f"| {date} | {pnl} | {total_pnl:.2f} | {trades} | {wins} | {win_rate} | {avg_rr} | {note} |"

    content = DAILY_LOG.read_text(encoding="utf-8") if DAILY_LOG.exists() else ""
    if "| 日期 |" in content:
        lines = content.splitlines()
        insert_idx = None
        for i, line in enumerate(lines):
            if line.startswith("| 202") or (line.startswith("|") and "日期" not in line and "---" not in line and line.count("|") >= 7):
                insert_idx = i + 1
        if insert_idx is None:
            for i, line in enumerate(lines):
                if re.match(r"^\|[\s-]+\|", line):
                    insert_idx = i + 1
                    break
        if insert_idx is not None:
            lines.insert(insert_idx, new_row)
            DAILY_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            content += "\n" + new_row + "\n"
            DAILY_LOG.write_text(content, encoding="utf-8")
    else:
        header = """# 每日績效記錄

| 日期 | 當日PnL | 累計PnL | 當日交易數 | 當日盈利數 | 累計勝率 | 當日平均RR | 備註 |
|------|---------|---------|------------|------------|----------|------------|------|
"""
        DAILY_LOG.write_text(header + new_row + "\n", encoding="utf-8")

    return total_pnl, total_trades, total_wins, win_rate

def update_summary(total_pnl, total_trades, total_wins, win_rate):
    content = f"""# 績效總覽

## 目前統計（自動更新）

| 項目 | 數值 |
|------|------|
| 累計 PnL | ${total_pnl:.2f} |
| 總交易次數 | {total_trades} |
| 盈利次數 | {total_wins} |
| 勝率 | {win_rate} |
| 最後更新 | {datetime.now().strftime("%Y-%m-%d %H:%M")} |

---

*此檔案由 update_performance.py 自動更新*
"""
    SUMMARY.write_text(content, encoding="utf-8")

def parse_report_text(text: str) -> dict:
    """從 daily-report.html 產生的報告文字中解析數據"""
    data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "pnl": 0.0,
        "trades": 0,
        "wins": 0,
        "rr": 0.0,
        "note": "",
        "grade": "",
        "symbol": "",
    }

    # 日期
    m = re.search(r"日期[：:]\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        data["date"] = m.group(1)

    # 品種
    m = re.search(r"品種[：:]\s*(\w+)", text)
    if m:
        data["symbol"] = m.group(1)

    # 當日 PnL
    m = re.search(r"當日\s*PnL[：:]\s*\$?\s*([-\d.]+)", text)
    if m:
        data["pnl"] = float(m.group(1))

    # 交易數
    m = re.search(r"當日交易數[：:]\s*(\d+)", text)
    if m:
        data["trades"] = int(m.group(1))

    # 盈利數
    m = re.search(r"當日盈利數[：:]\s*(\d+)", text)
    if m:
        data["wins"] = int(m.group(1))

    # 平均 RR
    m = re.search(r"當日平均\s*RR[：:]\s*([-\d.]+)", text)
    if m:
        data["rr"] = float(m.group(1))

    # 最終等級
    m = re.search(r"最終等級[：:]\s*([ABC])", text)
    if m:
        data["grade"] = m.group(1)

    # 備註
    m = re.search(r"備註[：:]\s*(.+?)(?:\n|$)", text)
    if m:
        note = m.group(1).strip()
        if note and note != "—":
            data["note"] = note

    # 組合 note
    note_parts = []
    if data["symbol"]:
        note_parts.append(data["symbol"])
    if data["grade"]:
        note_parts.append(f"{data['grade']}級")
    if data["note"]:
        note_parts.append(data["note"])
    data["note"] = " / ".join(note_parts)

    return data

def main():
    parser = argparse.ArgumentParser(description="Apex 每日績效更新腳本（支援報告解析）")
    parser.add_argument("--from-report", type=str, help="從報告文字檔解析（例如 report.txt）")
    parser.add_argument("--date", default=None, help="日期 YYYY-MM-DD")
    parser.add_argument("--pnl", type=float, default=None, help="當日 PnL")
    parser.add_argument("--trades", type=int, default=None, help="當日交易數")
    parser.add_argument("--wins", type=int, default=None, help="當日盈利數")
    parser.add_argument("--rr", type=float, default=0.0, help="當日平均 RR")
    parser.add_argument("--note", default="", help="備註")
    args = parser.parse_args()

    if args.from_report:
        report_path = Path(args.from_report)
        if not report_path.exists():
            print(f"❌ 找不到檔案：{report_path}")
            return
        text = report_path.read_text(encoding="utf-8")
        data = parse_report_text(text)
        print("📄 已從報告解析出以下數據：")
        print(f"   日期   : {data['date']}")
        print(f"   PnL    : {data['pnl']}")
        print(f"   交易數 : {data['trades']}")
        print(f"   盈利數 : {data['wins']}")
        print(f"   RR     : {data['rr']}")
        print(f"   備註   : {data['note']}")
        print()

        date = args.date or data["date"]
        pnl = args.pnl if args.pnl is not None else data["pnl"]
        trades = args.trades if args.trades is not None else data["trades"]
        wins = args.wins if args.wins is not None else data["wins"]
        rr = args.rr if args.rr != 0.0 else data["rr"]
        note = args.note or data["note"]
    else:
        if args.pnl is None or args.trades is None or args.wins is None:
            print("❌ 請提供 --pnl --trades --wins，或使用 --from-report")
            parser.print_help()
            return
        date = args.date or datetime.now().strftime("%Y-%m-%d")
        pnl = args.pnl
        trades = args.trades
        wins = args.wins
        rr = args.rr
        note = args.note

    print(f"正在更新 {date} 的績效數據...")
    total_pnl, total_trades, total_wins, win_rate = append_daily_row(
        date, pnl, trades, wins, rr, note
    )
    update_summary(total_pnl, total_trades, total_wins, win_rate)

    print("✅ 更新完成")
    print(f"   當日 PnL : ${pnl}")
    print(f"   累計 PnL : ${total_pnl:.2f}")
    print(f"   累計勝率 : {win_rate}")
    print(f"   總交易數 : {total_trades}")
    print("\n請執行：")
    print("  git add PERFORMANCE/")
    print("  git commit -m \"Update daily performance\"")
    print("  git push")

if __name__ == "__main__":
    main()
