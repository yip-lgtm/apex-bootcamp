<!--
歡迎提交 PR！請填妥以下 sections。
如果係 chart 改動，必須完成 4-Chart Standard checklist (見下方)。
-->

## 📝 改動描述

<!-- 一句話講呢個 PR 改咗咩 -->

**Type**: `feat` / `fix` / `docs` / `refactor` / `chore` / `test`
**Area** (label 必填): `area:charts` / `area:strategy` / `area:notify` / `area:ci` / `area:docs`
**Related issue**: #

---

## 🧪 Testing

- [ ] 本地 `python3 AUTOMATION/src/daily_reminder.py` 跑通
- [ ] TG message HTTP 200 (text + media group)
- [ ] Git push exit 0
- [ ] Backtest CI 仍 pass

---

## 📊 4-Chart Standard Checklist (chart 改動必填)

> 對齊 `AUTOMATION/docs/4-chart-standard.md`。
> 如果 PR 唔涉及 chart layout / panel 改動，可以 skip 呢一 section。

- [ ] **1. 開 issue 講點解** — 連結: #
- [ ] **2. 更新 `AUTOMATION/docs/4-chart-standard.md`** — 改動對應 section
- [ ] **3. 改 `AUTOMATION/src/chart_gen.py` 嘅 `make_chart_4panel()`** — 同步 panel 順序 / height_ratios
- [ ] **4. 同步 `AUTOMATION/src/daily_reminder.py` section + caption** — TG caption = `4-Chart Standard (D / H4 / H1 / 5m)`
- [ ] **5. TG msg ≤ 4096 chars** — 驗證: `python3 AUTOMATION/scripts/verify_4chart_standard.py` 會 check
- [ ] **6. 10 tickers gen ≤ 30s** — 同上 script check (6 workers parallel)
- [ ] **7. PR label `area:charts`** — 自動由 bot 喺 merge 前加

---

## 📸 Screenshots / Artifacts

<!-- 如果改動視覺嘢 (chart / TG message layout)，貼新 artifact -->

| Before | After |
|--------|-------|
| (paste) | (paste) |

---

## ⚠️ Risks

<!-- 講清楚有咩嘢會 break，例如：破壞現有 workflow、改 GHA timeout -->

- [ ] 影響 `daily-reminder.yml` GHA workflow? (如果係，要 timeout +1 步)
- [ ] 影響 `backtest.yml` GHA workflow?
- [ ] 影響 backtest 數據 / 結果?
- [ ] 新增 secrets 需求?

---

## ✅ Final checklist

- [ ] 已 rebase 喺最新 main
- [ ] commit messages 用 `type(scope):` 格式
- [ ] 無 large binary file 意外 commit
- [ ] TG bot credentials 無 leak 入 commit
- [ ] 自己 review 過 diff 至少一次
- [ ] 唔破壞 backward compatibility (或者喺 PR body 解釋)
