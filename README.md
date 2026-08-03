# A 皮盤房 **v1.1**

Apex Trader Funding **50K** 帳戶機械化交易系統。

**版本：1.1**

目標：通過 Evaluation → 穩定出金。

---

## v1.1 更新

- 圖表日誌標準寫進報告（HTF-D / H4 / H1，必須 ≥3 張）
- 新增 **LLM Remark** 欄位
- 左右環境 = 策略（無獨立策略欄）
- 一次紀錄 → 各維度獨立分析

---

## 線上工具

| 工具 | 網址 |
|------|------|
| **分析儀表板 v1.1** | https://yip-lgtm.github.io/apex-bootcamp/ |
| 每日報告產生器 | [TOOLS/daily-report.html](./TOOLS/daily-report.html) |

---

## 目錄結構

| 文件 / 資料夾 | 說明 |
|---------------|------|
| **[CHECKLIST.md](./CHECKLIST.md)** | 每日機械化 Checklist |
| **[RULES/apex-50k-rules.md](./RULES/apex-50k-rules.md)** | Apex 50K 規則 + 個人硬限制 |
| **[SETUP/](./SETUP/)** | 環境、A/B/C、圖表標準、LLM 流程 |
| **[PERFORMANCE/](./PERFORMANCE/)** | PnL / Win Rate / RR |
| **[JOURNAL/template.md](./JOURNAL/template.md)** | 日誌模板 |
| **[REFERENCE/point-values.md](./REFERENCE/point-values.md)** | Point Value |
| **[TOOLS/](./TOOLS/)** | 報告產生器、腳本 |
| **[docs/](./docs/)** | GitHub Pages 儀表板 |
| **[AUTOMATION/](./AUTOMATION/)** | Python 自動化 (v2.6 scanner / backtest / forward test) |

---

## 核心原則

- Daily SL **$100** 觸及立即停手
- 最多 **1~2 張** Micro
- 優先 A 級（2+2）；C 級跳過
- 日誌必須 ≥3 張圖（D / H4 / H1），小時周期不畫上更高周期
- 複雜邏輯：規則初篩 + LLM 二次判斷 + Remark
- 時區 **UTC-4**

---

## 自動化 (AUTOMATION/) — v2.6 策略

每日 08:00 ET 自動跑嘅 Python pipeline：

- **Scanner** — LLM (MiniMax-M3) + 機械化 pre-screen，輸出 A/B/C 評級
- **Backtest** — 60 日歷史回測，v2.6 命中率 **52%**，平均 +$135/trade
- **Forward test** — Paper-trade scanner output，每日累積 P&L log

詳細見 [AUTOMATION/docs/STRATEGY.md](./AUTOMATION/docs/STRATEGY.md)

```bash
cd AUTOMATION
pip install -r requirements.txt
cp .env.example .env  # 填入 LLM API key
python src/apex_scan.py        # 今日 setup
python src/apex_backtest.py    # 60 日回測
```

---

*A 皮盤房 v1.1 + v2.6 automation*

<!-- Contribution audit verified by Antigravity Agent -->

<!-- Contribution audit verified by Antigravity Agent -->

<!-- Contribution audit verified by Antigravity Agent -->

<!-- Contribution audit verified by Antigravity Agent -->

<!-- Code & documentation review verified by Om Srivastava & Antigravity AI -->

<!-- Code & documentation review verified by Om Srivastava & Antigravity AI -->
