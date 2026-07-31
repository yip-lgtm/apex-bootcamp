# Tools

## 1. daily-report.html
瀏覽器打開即可使用的每日報告填寫工具（Yes/No、A/B/C 選項）。

使用後點「產生報告」→「複製報告」。

## 2. update_performance.py
每日績效數據處理腳本（支援從報告自動解析）。

### 方法一：從報告自動解析（推薦）

1. 用 `daily-report.html` 填寫並產生報告
2. 複製報告內容，貼到一個文字檔（例如 `report.txt`）
3. 執行：

```bash
python TOOLS/update_performance.py --from-report report.txt
```

腳本會自動抽出：日期、PnL、交易數、盈利數、RR、等級、備註。

### 方法二：手動帶參數

```bash
python TOOLS/update_performance.py --pnl -23 --trades 3 --wins 1 --rr 1.2 --note "A級"
```

### 執行後記得推送

```bash
git add PERFORMANCE/
git commit -m "Update daily performance"
git push
```
