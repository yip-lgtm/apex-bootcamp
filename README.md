# Apex Bootcamp

Apex Trader Funding **50K** 帳戶機械化交易系統。

目標：通過 Evaluation → 穩定出金。

---

## 目錄結構

| 文件 / 資料夾 | 說明 |
|---------------|------|
| **[CHECKLIST.md](./CHECKLIST.md)** | 每日機械化 Checklist |
| **[RULES/apex-50k-rules.md](./RULES/apex-50k-rules.md)** | Apex 50K 規則 + 個人硬限制 |
| **[SETUP/](./SETUP/)** | 環境定義、A/B/C、圖表標準、LLM 流程 |
| **[PERFORMANCE/daily-log.md](./PERFORMANCE/daily-log.md)** | **每日 PnL / Win Rate / RR 記錄** |
| **[PERFORMANCE/summary.md](./PERFORMANCE/summary.md)** | 績效總覽 |
| **[JOURNAL/template.md](./JOURNAL/template.md)** | 每日交易日誌模板 |
| **[REFERENCE/point-values.md](./REFERENCE/point-values.md)** | Point Value 表 |

---

## 每日收盤後必做

1. 填寫 [JOURNAL/template.md](./JOURNAL/template.md)
2. 更新 [PERFORMANCE/daily-log.md](./PERFORMANCE/daily-log.md)（PnL、勝率、RR）
3. 更新 Notion 對應記錄
4. 檢查合格獲利日進度

---

## 核心原則

- Daily SL **$100** 觸及立即停手
- 最多 **1 張** Micro
- 優先做 A 級 Setup
- 套杀等複雜邏輯使用「規則 + LLM」混合判斷
- 時區 **UTC-4**

---

*Built for mechanical consistency + intelligent judgment.*
