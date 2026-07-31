# Apex Bootcamp **v1.0**

Apex Trader Funding **50K** 帳戶機械化交易系統。

**版本：1.0**（左右環境 = 策略｜規則 + LLM｜績效維度分析）

目標：通過 Evaluation → 穩定出金。

---

## 線上工具

| 工具 | 網址 |
|------|------|
| **分析儀表板 v1.0** | https://yip-lgtm.github.io/apex-bootcamp/ |
| 每日報告產生器 | [TOOLS/daily-report.html](./TOOLS/daily-report.html) |

---

## 目錄結構

| 文件 / 資料夾 | 說明 |
|---------------|------|
| **[CHECKLIST.md](./CHECKLIST.md)** | 每日機械化 Checklist |
| **[RULES/apex-50k-rules.md](./RULES/apex-50k-rules.md)** | Apex 50K 規則 + 個人硬限制 |
| **[SETUP/](./SETUP/)** | 環境定義、A/B/C、圖表標準、LLM 流程 |
| **[PERFORMANCE/](./PERFORMANCE/)** | 每日 PnL / Win Rate / RR |
| **[JOURNAL/template.md](./JOURNAL/template.md)** | 每日交易日誌模板 |
| **[REFERENCE/point-values.md](./REFERENCE/point-values.md)** | Point Value 表 |
| **[TOOLS/](./TOOLS/)** | 報告產生器、績效腳本 |
| **[docs/](./docs/)** | GitHub Pages 儀表板 |

---

## v1.0 核心設計

- **左右環境 = 策略**（不再另設策略欄）
- **一次紀錄** → 自動拆成品種 / 左 / 右 / 等級 / LLM / ABCD 獨立分析
- Daily SL **$100**、最多 **1~2 張** Micro
- 優先 A 級（2+2）；C 級跳過
- 複雜邏輯：規則初篩 + LLM 二次判斷
- 時區 **UTC-4**

---

## 每日流程

1. 開盤前 Checklist
2. 候選訊號 → LLM 判斷
3. 收盤填報告（或儀表板）
4. 更新合格獲利日進度

---

*Apex Bootcamp v1.0 — mechanical consistency + intelligent judgment.*
