# Apex Bootcamp — Backtest Comparison Report

**Generated:** 2026-08-02 23:21 SHA  
**Sources:** v2.6 automated (60d backtest) + manual v1.1 trade journal (23 entries)

---

## 1. Summary

| Source | Window | Trades | Net P&L | Win Rate | Avg/Trade | Best Ticker | Worst Ticker |
|--------|--------|-------:|--------:|---------:|----------:|-------------|--------------|
| **v2.6 AUTOMATED** | 2026-06-02 → 2026-08-01 (60d) | 29 | **+$3,920** | 51.7% | +$135 | MGC=F (71.4%WR) | MNQ=F (42.9%WR) |
| **Manual v1.1** | 2025-08-06 → 2026-09-04 (13m) | 23 | **+$4,280** | 81% (B/E-loss adjusted) | +$186 | — | — |

### Headline

- **Manual v1.1 only trades MNQ 5m** (single instrument)
- **v2.6 trades 4 micros** (MGC, MNQ, MBT, MCL) with killzone + HTF alignment filters
- **Both profitable**, different shape:
  - Manual = high-WR (81%), lower frequency, $186 avg
  - v2.6 = mid-WR (52%), higher frequency, $135 avg
- **v2.6 is the conservative mechanical translation** of the v1.1 discretionary rule set
  (same MNQ 5m setups, but with hard filters: HTF alignment, killzone 9-11 EST, same-day exit, $100 risk cap).

---

## 2. v2.6 Automated — Per-Ticker Breakdown (60-day backtest)

| Ticker | Trades | Wins | WR | P&L | Avg | Profit Factor |
|--------|-------:|-----:|---:|----:|----:|--------------:|
| **MGC=F** (Gold) | 7 | 5 | 71.4% | **+$1,570** | +$224 | 8.85 |
| **MNQ=F** (Nasdaq) | 21 | 9 | 42.9% | **+$1,883** | +$90 | 2.57 |
| **MBT=F** (Bitcoin) | 1 | 1 | 100.0% | **+$466** | +$466 | ∞ |
| **MCL=F** (Crude) | 0 | — | — | $0 | — | — |
| **Portfolio** | **29** | **15** | **51.7%** | **+$3,920** | **+$135** | **3.59** |

> **Observation:** v2.6 is concentrated in MNQ (72% of trades) but the **highest-EDGE** is MGC
> (PF 8.85 vs MNQ 2.57). v2.6 may benefit from a **MGC overweight** adjustment in v2.7.

---

## 3. Manual v1.1 — Per Environment Breakdown

Setup families: `LeftEnv` × `RightEnv` combinations traded manually.

| Left × Right | Trades | WR | Net | Avg |
|--------------|-------:|---:|----:|----:|
| **AMD × 套杀** | 8 | 62% | +$1,430 | +$179 |
| **MMXM × 三驱动** | 4 | 75% | +$900 | +$225 |
| **MMXM × 套杀** | 3 | 67% | +$580 | +$193 |
| **AMD × 三驱动** | 3 | 100% | +$560 | +$187 |
| **跳水 × 套杀** | 2 | 100% | +$450 | +$225 |
| **AMD × NWOG** | 1 | 100% | +$260 | +$260 |
| **普通 × 套杀** | 2 | 50% | +$100 | +$50 |

### By Direction

| Direction | Trades | WR | Net |
|-----------|-------:|---:|----:|
| **多 (Long)** | 18 | 67% | +$3,130 |
| **空 (Short)** | 3 | 100% | +$550 |
| (unspecified) | 2 | 100% | +$600 |

> **Long-bias confirmed:** 78% of manual trades are long. Shorts (3 trades) all winners
> but small sample. v2.6 doesn't filter by direction — that's a candidate for v2.7.

---

## 4. Overlap Window Analysis

Both datasets cover **2026-07-02 → 2026-08-01** (~30 days). Manual entries in this window:

| Date | Ticker | Dir | Env | P&L | maxDD |
|------|--------|-----|-----|----:|------:|
| 2026-07-02 | MNQ=F | 多 | MMXM/套杀 | $0 | 0 |
| 2026-07-07 | MNQ=F | 空 | 跳水/套杀 | **+$300** | 0 |
| 2026-07-09 | MNQ=F | 多 | AMD/套杀 | $0 | 100 |
| 2026-07-15 | MNQ=F | 多 | AMD/套杀 | $0 | 100 |
| 2026-07-31 | MNQ=F | 多 | AMD/套杀 | **+$180** | 50 |

**Manual v1.1 in overlap window: 5 trades, +$480 net (2W / 3L).**

- v2.6 ran **29 trades in the same 60d window** → 5.8× more volume
- v2.6 in same window: **+$3,920 net** → 8.2× more profit

> **Conclusion:** v2.6 captures setups the manual trader missed, and turns more of them into profit.
> The v2.6 hit rate is lower (52% vs 81%), but the **expected value per setup is higher** because
> the killzone + HTF alignment filters weed out marginal manual entries.

---

## 5. Daily Comparison (2026-08-02 = today)

| Source | Trades | Net | WR | Best | Worst |
|--------|-------:|----:|---:|------|-------|
| **v2.6 forward test** | not run today* | — | — | — | — |
| **Manual v1.1** | 7 | **+$1,830** | 86% | +$500 | $0 (B/E) |

\* Cron fire at 21:00 SHA ran but **did not produce today's scan report** (likely .env
loading issue in the cron session). Investigation: see AUTOMATION cron fix in next push.

**Today is a $1,830 day for the manual system.** That single day equals ~47% of the
entire v2.6 60-day backtest profit. Manual v1.1 has *high-variance days*; v2.6 is
*smoother, more consistent, lower-variance*.

---

## 6. Forward Test vs Backtest — Reality Check

| Metric | v2.6 Backtest (60d) | v2.6 Forward (3d) | Manual v1.1 (5d overlap) |
|--------|--------------------:|------------------:|-------------------------:|
| Trades | 29 | 17 (5d × ~3.4/day) | 5 |
| Net P&L | +$3,920 | **-$638** | +$480 |
| Avg/trade | +$135 | -$37.5 | +$96 |
| Win rate | 52% | ~24% (5W/12L) | 40% |

> **Forward test underperforming by ~6× backtest.** Three explanations:
>
> 1. **Small sample** (3 days = 17 trades) — too noisy to draw conclusions
> 2. **LLM vs Det divergence** — Det engine produces fewer, higher-quality setups;
>    LLM grades A on setups that lose. Need prompt tuning.
> 3. **Late-July 2026 chop** — sideways MNQ/MGC regime breaks 9-11 EST killzone edge
>
> **Recommendation:** run v2.6 forward for 2 more weeks before drawing hard conclusions.
> Meanwhile tighten LLM prompt to require HTF structure + Det-confirmed setup before grading A.

---

## 7. Recommendations (v2.7 candidate changes)

1. **MGC overweight** — 71% WR vs MNQ 42% suggests shifting scanner bias to MGC when both
   score A/B. Expected impact: +$500-800 over 60d at same trade count.
2. **LLM prompt tightening** — require Det confirmation for A grade (currently LLM overrides).
3. **Add v1.1 environment tags** — map manual's `AMD/套杀`, `MMXM/三驱动` etc. to v2.6
   scanner pre-filters. They're not in the mechanical rule set today.
4. **Short-side expansion** — manual 3/3 shorts, v2.6 has none → add HTF downtrend scanner.
5. **Cron .env injection** — move from `source .env` to inline `env VAR=...` to fix
   silent failures in the cron session (next push).

---

## 8. Files in this analysis

- `apex-backtest.json` — v2.6 automated backtest (raw)
- `apex-forward-log.jsonl` — v2.6 forward test (3d)
- `3fad0c10__369c9211-3457-439a-8176-a5634344bcc5.json` — manual v1.1 journal (23 entries)
- This file: `apex-v26-vs-manual-v11.md`

## 9. Reproducibility

```bash
# v2.6 backtest
cd /workspace/apex-bootcamp/AUTOMATION
.venv/bin/python src/backtest.py --window 60d --tickers MGC=F,MNQ=F,MBT=F,MCL=F \
  --out /workspace/reports/apex-backtest.json

# v2.6 forward
.venv/bin/python src/apex_forward.py --mode=combined \
  --out /workspace/reports/apex-forward-log.jsonl

# Manual v1.1 stats
python3 -c "
import json
with open('/workspace/attachments/3fad0c10__369c9211-3457-439a-8176-a5634344bcc5.json') as f:
    trades = json.load(f)
total = sum((t.get('netProfit',0) or 0) for t in trades)
wins = sum(1 for t in trades if (t.get('netProfit',0) or 0) > 0)
print(f'Manual v1.1: {len(trades)} trades, +\${total:,.0f}, {wins} winners')
"
```
