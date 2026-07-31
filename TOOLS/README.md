# Tools

## 1. daily-report.html
瀏覽器打開即可使用的每日報告填寫工具（Yes/No、A/B/C 選項）。

## 2. update_performance.py
每日績效數據處理腳本。

### 使用方法

```bash
# 基本用法
python TOOLS/update_performance.py --pnl -23 --trades 3 --wins 1 --rr 1.2

# 完整參數
python TOOLS/update_performance.py \
  --date 2026-07-31 \
  --pnl 78 \
  --trades 5 \
  --wins 3 \
  --rr 2.1 \
  --note "A級套杀"
```

### 參數說明

| 參數 | 必填 | 說明 |
|------|------|------|
| `--date` | 否 | 日期，預設今天 |
| `--pnl` | 是 | 當日淨盈虧 |
| `--trades` | 是 | 當日交易筆數 |
| `--wins` | 是 | 當日盈利筆數 |
| `--rr` | 否 | 當日平均風險報酬比 |
| `--note` | 否 | 備註 |

執行後會自動更新：
- `PERFORMANCE/daily-log.md`
- `PERFORMANCE/summary.md`

記得之後執行：
```bash
git add PERFORMANCE/
git commit -m "Update daily performance"
git push
```
