# Apex 50K v2.6 機械化策略

> 自動化版嘅 v2.6 strategy — Python implementation of the [Apex 50K mechanical system](https://github.com/yip-lgtm/apex-bootcamp/blob/main/CHECKLIST.md).

---

## 1. 硬規則 (Hard Rules)

| 項目 | 數值 | 違反後果 |
|------|------|----------|
| **Risk per trade** | $100 | daily kill-switch 觸發 |
| **TP envelope** | $200 - $500 | 出 envelope 即降 C |
| **RR** | 2.0 - 5.0 | 唔合即 C |
| **Max contracts** | 1 micro (MGC/MNQ/MBT) / 2 micro (MCL) | 超出即違規 |
| **HTF alignment** | 1D 趨勢必須支持 5m bias | 逆勢 (1+1) 自動 C |
| **Killzone** | 09:00-11:00 EST | 窗外 trigger 唔考慮 |
| **Daily SL kill-switch** | -$100 立即停手 | 當日 P&L 觸即停 |

---

## 2. A/B/C 評級系統

依 [CHECKLIST 4.2](https://github.com/yip-lgtm/apex-bootcamp/blob/main/CHECKLIST.md) 同 [4.3](https://github.com/yip-lgtm/apex-bootcamp/blob/main/CHECKLIST.md) 規則：

### v2.6 評分矩陣

| HTF Score | Trigger Score | 總分 | Grade | 倉位 |
|-----------|---------------|------|-------|------|
| 2 (aligned) | 2 (A-pattern) | 4 | **A** | 1 micro (or 2 for MCL) |
| 2 | 1 (B-pattern) | 3 | **B** | 1 micro (減倉) |
| 1 (counter-trend) | 2 | 3 | **B** | 0.5 micro optional |
| 1 | 1 | 2 | **C** | skip |
| 0 (no HTF data) | any | <4 | **C** | skip |

### Trigger Quality 判斷

A-patterns (trig_score = 2):
- `mss_up` / `mss_down` — break of prior N-bar extreme
- `session_high_break` / `session_low_break` — breakout of session range
- `orb_break_long` / `orb_break_short` — first 30-min range break (with volume)
- Volume ratio > 1.5x average → auto upgrade to trig_score 2

B-patterns (trig_score = 1):
- `bullish_engulfing` / `bearish_engulfing`
- `pin_bar_long` / `pin_bar_short` (hammer / shooting star)
- `sweep_reject_long` / `sweep_reject_short` (liquidity sweep + rejection)
- `vwap_reject_long` / `vwap_reject_short` (VWAP test + rejection)

---

## 3. 結構 TP (Structure-based Take Profit)

唔再用 fixed $300，動態用 nearest swing H/L：

```python
LONG:  TP = nearest swing HIGH above trigger (from day's 5m bars)
SHORT: TP = nearest swing LOW  below trigger
```

Envelope 規則：
- TP reward ∈ [$200, $500] → 用結構 TP
- TP reward < $200 → C (TP 太 tight，達唔到 floor)
- TP reward > $500 → cap 去 $500
- 自動 fit 落 Apex 50K envelope

---

## 4. Killzone + Same-day Entry

**v2.6 嘅 magic sauce：**

1. **Trigger detection 只喺 09:00-11:00 EST**
   - 最高流動性 window
   - 減少 false signals (避免下午低 vol 噪音)
   - 5m bar 必須 `hour ∈ [9, 11)`

2. **Same-day entry (唔過夜)**
   - Entry = trigger 偵測後下一根 5m bar open
   - 通常係 10:55 trigger → 11:00 entry
   - 消除 overnight gap 風險（22 小時 gap 容易跳空 hit SL）

3. **Exit: SL / TP / EOD (16:00)**
   - TP/SL 喺同日內 hit → 出場
   - 都冇中 → 16:00 EOD mark-to-market exit

---

## 5. File Structure

```
AUTOMATION/
├── .env.example        # Template — copy to .env and fill in API keys
├── .gitignore          # Excludes .env, .venv/, etc.
├── requirements.txt    # Python deps (pandas, yfinance, openai, etc.)
├── src/
│   ├── apex_strategy.py  # Shared logic: TICKERS, fetch, detect_trigger, grade_setup
│   ├── apex_scan.py      # Daily scanner (LLM + det pre-screen)
│   ├── apex_backtest.py  # 60-day backtest engine
│   ├── apex_forward.py   # Forward-test paper simulator
│   └── apex_analyze.py   # Single-ticker ad-hoc analyzer
├── reports/            # Generated daily reports (gitignored by default)
└── docs/               # This file + additional strategy notes
```

---

## 6. Quick Start

```bash
cd AUTOMATION
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in your LLM API key

# 1. Run scanner for most recent session
python src/apex_scan.py

# 2. Run 60-day backtest
python src/apex_backtest.py 2026-06-02 2026-08-01

# 3. Forward-test (paper trade) a single day
python src/apex_forward.py 2026-07-31 --mode=combined
```

---

## 7. Backtest Result (v2.6)

60-day window (2026-06-02 → 2026-08-01):

| Metric | Value |
|--------|-------|
| Total trades | 29 |
| Hit rate (TP-only) | **52%** |
| Total P&L | **+$3,920** |
| Avg per trade | +$135 |
| Best ticker | MGC=F (71% hit, +$1,570) |
| Worst ticker | MCL=F (0 trades — daily vol too small) |

vs v1 baseline: 28 trades, 32% hit, +$76 total (6× improvement)

---

## 8. Forward-Test Result (3-day sample)

| Date | Trades | P&L | Source |
|------|--------|-----|--------|
| 2026-07-29 | 3 | -$201 | LLM (LLM-Det divergence) |
| 2026-07-30 | 3 | -$201 | LLM |
| 2026-07-31 | 4 | -$236 | mixed |
| **Total** | **10** | **-$638** | — |

⚠️ **3-day sample 統計意義唔夠** — 等 7-10 日數據累積先有結論。

Det-only sub-sample 顯示 det engine 較 LLM 保守（0 trades 喺 quiet days）但 hit rate 可能更高。

---

## 9. v2.6 改動日誌 (Changelog)

- **v1** (Aug 1) — baseline. Wide triggers, fixed $300 TP, 32% hit, +$76 / 60d
- **v2.0** — Add HTF alignment requirement (1+1 → C)
- **v2.5** — Add structure-based TP (swing H/L) + 2 micro for crude
- **v2.6** — Add killzone filter (9-11 EST) + same-day entry. **+$3,920 / 60d, 52% hit**
- **v2.7 (planned)** — Tighten LLM prompt to reduce false A grades; sentiment filter

---

## 10. Related

Links use GitHub web URLs (not relative paths) so they work whether STRATEGY.md
is viewed on github.com, the GitHub Pages site, or a local clone.

- [CHECKLIST.md](https://github.com/yip-lgtm/apex-bootcamp/blob/main/CHECKLIST.md) — daily mechanical workflow
- [RULES/apex-50k-rules.md](https://github.com/yip-lgtm/apex-bootcamp/blob/main/RULES/apex-50k-rules.md) — hard Apex rules
- [SETUP/llm-workflow.md](https://github.com/yip-lgtm/apex-bootcamp/blob/main/SETUP/llm-workflow.md) — LLM-augmented setup grading
- [PERFORMANCE/](https://github.com/yip-lgtm/apex-bootcamp/tree/main/PERFORMANCE) — manual trade tracking spreadsheet
- [JOURNAL/template.md](https://github.com/yip-lgtm/apex-bootcamp/blob/main/JOURNAL/template.md) — daily trade journal
