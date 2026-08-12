---
name: 📊 Chart Layout 改動
about: 提議改 4-Chart Standard (D / H4 / H1 / 5m) 嘅 panel 結構、height ratio、或者新 panel
title: "[Chart] "
labels: ["area:charts", "needs-review"]
assignees: []
---

## 🎯 改動目的

<!-- 講清楚點解要改 chart layout。例：
- 想加 M1 panel 做更精細 trigger
- 想減 H4 panel 因為太多 noise
- 想將 D panel 變 weekly (W1)
-->

**類型**:
- [ ] 加 panel (現時 4 個 → N 個)
- [ ] 減 panel (現時 4 個 → M 個)
- [ ] 改 panel 順序 / height ratio
- [ ] 換 timeframe (e.g. 5m → 1m)
- [ ] 改 levels 標記 (PDH/PDL/ONH/ONL)
- [ ] 改 dark theme / colors

---

## 📊 現時 vs 提議

| 項目 | 現時 (v2.6.8) | 提議 |
|------|--------------|------|
| Panel 1 | D (1D, 90d) | ? |
| Panel 2 | H4 (4h, 30d) | ? |
| Panel 3 | H1 (1h, 5d) | ? |
| Panel 4 | 5m (5-min, 2d) | ? |
| Figsize | 13×13 | ? |
| height_ratios | [3, 2, 1.6, 0.8, 2.6] | ? |

---

## 🤔 點解必要

<!-- 講清楚解決咩問題。如果只係 cosmetic，講清楚 -->

**失敗模式** (現時 layout 嘅 problem):
>

**提議 layout 點解決**:
>

---

## 📈 影響評估

- [ ] TG message 字數影響 (現時 2443 chars / 4096 limit)
- [ ] 10 tickers gen time (現時 ~20-26s / 30s limit)
- [ ] PNG file size (現時 ~134 KB / TG 10MB limit)
- [ ] GHA timeout (現時 15min)
- [ ] LLM grading prompt (要 rephrase 講新 layout)

---

## ✅ 7-Item Contract (PR 前必須完成)

- [ ] **1. 開呢個 issue** ← 你依家喺度
- [ ] **2. 更新 `AUTOMATION/docs/4-chart-standard.md`**
- [ ] **3. 改 `AUTOMATION/src/chart_gen.py` 嘅 `make_chart_4panel()`**
- [ ] **4. 同步 `AUTOMATION/src/daily_reminder.py` section + caption**
- [ ] **5. TG msg ≤ 4096 chars** (run `verify_4chart_standard.py`)
- [ ] **6. 10 tickers gen ≤ 30s** (run `verify_4chart_standard.py`)
- [ ] **7. PR label `area:charts`**

---

## 📎 Reference

- 4-Chart Standard doc: [`AUTOMATION/docs/4-chart-standard.md`](../../blob/main/AUTOMATION/docs/4-chart-standard.md)
- v2.7 招人 issue: [#1](https://github.com/yip-lgtm/apex-bootcamp/issues/1)
- 升級歷史: v2.6.4 (3 panel) → v2.6.6 (priority) → v2.6.7 (ranking) → **v2.6.8 (4 panel M5)**
