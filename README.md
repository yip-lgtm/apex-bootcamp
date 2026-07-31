# Apex Bootcamp

Apex Trader Funding **50K** 帳戶機械化交易系統。

目標：通過 Evaluation → 穩定出金。

---

## 目錄結構

| 文件 / 資料夾 | 說明 |
|---------------|------|
| **[CHECKLIST.md](./CHECKLIST.md)** | 每日機械化 Checklist（核心文件） |
| **[RULES/apex-50k-rules.md](./RULES/apex-50k-rules.md)** | Apex 50K 官方規則 + 個人硬限制 |
| **[SETUP/environments.md](./SETUP/environments.md)** | 左側 / 右側環境定義 |
| **[SETUP/abc-grading.md](./SETUP/abc-grading.md)** | A/B/C 計分系統（主動+被動+工程+預設） |
| **[SETUP/chart-standards.md](./SETUP/chart-standards.md)** | 交易日誌圖表標記標準（至少3張圖） |
| **[SETUP/llm-workflow.md](./SETUP/llm-workflow.md)** | **規則初篩 + LLM 二次判斷流程** |
| **[REFERENCE/point-values.md](./REFERENCE/point-values.md)** | Point Value 表 |
| **[JOURNAL/template.md](./JOURNAL/template.md)** | 每日交易日誌模板 |

---

## 快速開始

1. 每天開盤前打開 **[CHECKLIST.md](./CHECKLIST.md)**
2. 程式做規則初篩，出現候選訊號後走 **LLM 二次判斷流程**
3. 只優先做 LLM 評為 **A 級** 的 Setup
4. 收盤後按 chart-standards 截至少 3 張圖並填寫日誌

---

## 核心原則

- Daily SL **$100** 觸及立即停手
- 最多 **1 張** Micro（目前）
- C 級直接跳過
- 更小周期的畫圖不要出現在更高周期
- 時區統一 **UTC-4**
- 套杀等複雜邏輯使用「規則 + LLM」混合判斷

---

*Built for mechanical consistency + intelligent judgment.*
