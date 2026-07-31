#!/usr/bin/env python3
"""
Apex Bootcamp - 每日績效數據處理腳本
用法：
  python update_performance.py
  或帶參數：
  python update_performance.py --date 2026-07-31 --pnl -23 --trades 3 --wins 1 --rr 1.5
"""

import argparse
from datetime import datetime
from pathlib import Path

# 檔案路徑（相對於專案根目錄）
DAILY_LOG = Path(__file__).parent.parent / "PERFORMANCE" / "daily-log.md"
SUMMARY = Path(__file__).parent.parent / "PERFORMANCE" / "summary.md"

def parse_existing_log():
    """讀取現有 daily-log.md，回傳已有的資料列"""
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
    """新增一列每日數據"""
    rows = parse_existing_log()

    # 計算累計
    total_pnl = sum(float(r[1]) for r in rows if r[1] not in ("-", "")) + float(pnl)
    total_trades = sum(int(float(r[2])) for r in rows if r[2] not in ("-", "")) + int(trades)
    total_wins = sum(int(float(r[3])) for r in rows if r[3] not in ("-", "")) + int(wins)
    win_rate = f"{(total_wins / total_trades * 100):.1f}%" if total_trades > 0 else "0%"

    new_row = f"| {date} | {pnl} | {total_pnl:.2f} | {trades} | {wins} | {win_rate} | {avg_rr} | {note} |"

    # 讀取原檔並在表格最後插入
    content = DAILY_LOG.read_text(encoding="utf-8") if DAILY_LOG.exists() else ""
    if "| 日期 |" in content:
        # 找到表格結束位置插入
        lines = content.splitlines()
        insert_idx = None
        for i, line in enumerate(lines):
            if line.startswith("| 202") or (line.startswith("|") and "日期" not in line and "---" not in line):
                insert_idx = i + 1
        if insert_idx is None:
            # 找表頭後第一行
            for i, line in enumerate(lines):
                if "---" in line and i > 0:
                    insert_idx = i + 1
                    break
        if insert_idx is not None:
            lines.insert(insert_idx, new_row)
            DAILY_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            content += "\n" + new_row + "\n"
            DAILY_LOG.write_text(content, encoding="utf-8")
    else:
        # 檔案不存在或格式不對，重建
        header = """# 每日績效記錄

| 日期 | 當日PnL | 累計PnL | 當日交易數 | 當日盈利數 | 累計勝率 | 當日平均RR | 備註 |
|------|---------|---------|------------|------------|----------|------------|------|
"""
        DAILY_LOG.write_text(header + new_row + "\n", encoding="utf-8")

    return total_pnl, total_trades, total_wins, win_rate

def update_summary(total_pnl, total_trades, total_wins, win_rate):
    """更新 summary.md"""
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

def main():
    parser = argparse.ArgumentParser(description="Apex 每日績效更新腳本")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="日期 YYYY-MM-DD")
    parser.add_argument("--pnl", type=float, required=True, help="當日 PnL")
    parser.add_argument("--trades", type=int, required=True, help="當日交易數")
    parser.add_argument("--wins", type=int, required=True, help="當日盈利數")
    parser.add_argument("--rr", type=float, default=0.0, help="當日平均 RR")
    parser.add_argument("--note", default="", help="備註")
    args = parser.parse_args()

    print(f"正在更新 {args.date} 的績效數據...")
    total_pnl, total_trades, total_wins, win_rate = append_daily_row(
        args.date, args.pnl, args.trades, args.wins, args.rr, args.note
    )
    update_summary(total_pnl, total_trades, total_wins, win_rate)

    print("✅ 更新完成")
    print(f"   當日 PnL : ${args.pnl}")
    print(f"   累計 PnL : ${total_pnl:.2f}")
    print(f"   累計勝率 : {win_rate}")
    print(f"   總交易數 : {total_trades}")
    print("\n請記得 git add + commit + push 來同步到 GitHub。")

if __name__ == "__main__":
    main()
