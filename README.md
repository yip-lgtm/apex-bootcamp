# A 皮盤房 **v1.1** + v2.6 automation

Apex Trader Funding **50K** 帳戶機械化交易系統。

[![4-Chart Standard](https://github.com/yip-lgtm/apex-bootcamp/actions/workflows/chart-verify.yml/badge.svg?branch=main)](https://github.com/yip-lgtm/apex-bootcamp/actions/workflows/chart-verify.yml)
[![Daily Reminder](https://github.com/yip-lgtm/apex-bootcamp/actions/workflows/daily-reminder.yml/badge.svg?branch=main)](https://github.com/yip-lgtm/apex-bootcamp/actions/workflows/daily-reminder.yml)
[![Backtest CI](https://github.com/yip-lgtm/apex-bootcamp/actions/workflows/backtest.yml/badge.svg?branch=main)](https://github.com/yip-lgtm/apex-bootcamp/actions/workflows/backtest.yml)

**版本：1.1** (manual) + **v2.6.8** (automated, 4-Chart Standard)

目標：通過 Evaluation → 穩定出金。

📊 **4-Chart Standard (D / H4 / H1 / 5m)** — 所有 chart 改動必須跟嘅 contract. 詳見 [`AUTOMATION/docs/4-chart-standard.md`](./AUTOMATION/docs/4-chart-standard.md).

---

## v1.1 更新

- 圖表日誌標準寫進報告（HTF-D / H4 / H1，必須 ≥3 張）
- 新增 **LLM Remark** 欄位
- 左右環境 = 策略（無獨立策略欄）
- 一次紀錄 → 各維度獨立分析

## v2.6.8 自動化更新 (2026-08-12)

- **4-Chart Standard** — 將圖表標準由 3 panel 升級到 4 panel (D / H4 / H1 / 5m)
- **M5 intraday panel** — 加入 5-min 圖用嚟做精確 entry trigger
- **Trade candidate ranking** — `priority_score()` 將 A/B/C grade + backtest PF 合成單一 priority 分數
- **Position sizing** — A 級 1.0µ / B 級 0.5µ / C 級 skip
- **7-Item 4-Chart Standard contract** — PR/Issue templates + `verify_4chart_standard.py` + GHA `chart-verify.yml` 自動 check
- **GHA workflows** — `chart-verify.yml` (PR), `daily-reminder.yml` (20:30 HKT), `backtest.yml` (CI)

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
- 日誌必須 **4 張圖**（**D / H4 / H1 / 5m**）— [4-Chart Standard](./AUTOMATION/docs/4-chart-standard.md)
- 複雜邏輯：規則初篩 + LLM 二次判斷 + Remark
- 時區 **UTC-4** (market) / HKT (ops)

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
python src/daily_reminder.py   # 20:30 HKT 預先提醒 (Telegram)
```

---

## 🤝 貢獻 (v2.7)

想加入 v2.7 改進？睇下呢啲：

1. 開 [issue #1](https://github.com/yip-lgtm/apex-bootcamp/issues/1) 揀想跟嘅 sub-task
2. 改 chart layout? 必須跟 [4-Chart Standard](./AUTOMATION/docs/4-chart-standard.md) (7 項 contract)
3. 改 push 之前: `python3 AUTOMATION/scripts/verify_4chart_standard.py` (5/7 自動 check)
4. 開 PR — [PR template](./.github/PULL_REQUEST_TEMPLATE.md) 內置 4-Chart Standard checklist
5. `chart-verify.yml` 會自動跑 + block merge 如果唔合 contract

GHA workflows:
- `chart-verify.yml` — PR 自動 check 4-Chart Standard (badge 喺頂)
- `daily-reminder.yml` — 每日 20:30 HKT 自動 reminder (badge 喺頂)
- `backtest.yml` — 每次 push 自動回測 (badge 喺頂)

---

*A 皮盤房 v1.1 + v2.6.8 automation (4-Chart Standard)*
