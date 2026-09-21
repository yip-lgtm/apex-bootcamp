# MNQ Variant — 5m ORB + VWAP (opposite-OR SL, mid fallback)

**Generated:** 2026-09-21 13:27:48 EDT  
**Symbol:** MNQ=F (Micro Nasdaq) · **Size:** 1 Micro ($2.0/pt) · **Bars:** 5m (yfinance)  
**Strategy:** 5m ORB + VWAP (opposite-OR SL, mid fallback) (`variant_A_5m`)  
**Window:** 2026-08-10 → 2026-09-21 (30 trading days, end 2026-09-21)  
**Data span:** 2026-07-13T00:00:00-04:00 → 2026-09-21T13:15:00-04:00

## Hard constraints

- 1 Micro fixed · brackets · daily **−$100 / +$300** · skip T1 chase · no scale/average
- Session tags: LDLZ 02:00–05:00 NY · NYKZ 08:30–11:00 NY
- TP: **1.5R** · Same-bar SL+TP: **SL first**

## Summary

| Metric | Value |
|---|---|
| Total net P&L | $140.25 |
| Max DD $ | $0.00 |
| Win rate | 100.00% (1W / 0L / 0F) |
| Avg R | 1.5000 |
| Expectancy $/trade | $140.2500 |
| # Trades | 1 |
| Best day | 2026-09-18 ($140.25) |
| Worst day | 2026-08-10 ($0.00) |
| Qualified days (≥$250 net) | 0 |
| Cumulative ≥ $3000? | False |
| Max DD vs $2000 trail breach? | False |

## Session tag breakdown

| Tag | #Trades | P&L | Win% | Avg R |
|---|---|---|---|---|
| LDLZ | 0 | $0.00 | 0.00% | 0.0000 |
| NYKZ | 1 | $140.25 | 100.00% | 1.5000 |
| other | 0 | $0.00 | 0.00% | 0.0000 |

## Day status counts

- `skip_c_too_wide`: 27
- `skipped`: 2
- `traded`: 1

## Trades

| Date | Dir | Entry NY | Tag | Entry | SL | TP | R$ | Exit | Why | P&L | R |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-18 | SHORT | 09:45 | NYKZ | 29795.25 | 29842.00 | 29725.12 | 93.50 | 29725.12 | TP | $140.25 | 1.50 |

## Daily P&L

| Date | Status | Day P&L | Grade | OR width | #Trades |
|---|---|---|---|---|---|
| 2026-08-10 | skip_c_too_wide | $0.00 | C | 104.50 | 0 |
| 2026-08-11 | skip_c_too_wide | $0.00 | C | 116.50 | 0 |
| 2026-08-12 | skip_c_too_wide | $0.00 | C | 124.00 | 0 |
| 2026-08-13 | skip_c_too_wide | $0.00 | C | 84.25 | 0 |
| 2026-08-14 | skip_c_too_wide | $0.00 | C | 63.50 | 0 |
| 2026-08-17 | skip_c_too_wide | $0.00 | C | 75.25 | 0 |
| 2026-08-18 | skip_c_too_wide | $0.00 | C | 124.00 | 0 |
| 2026-08-19 | skip_c_too_wide | $0.00 | C | 93.75 | 0 |
| 2026-08-20 | skip_c_too_wide | $0.00 | C | 95.25 | 0 |
| 2026-08-21 | skip_c_too_wide | $0.00 | C | 114.75 | 0 |
| 2026-08-24 | skip_c_too_wide | $0.00 | C | 161.25 | 0 |
| 2026-08-25 | skip_c_too_wide | $0.00 | C | 97.75 | 0 |
| 2026-08-26 | skip_c_too_wide | $0.00 | C | 107.25 | 0 |
| 2026-08-27 | skip_c_too_wide | $0.00 | C | 137.00 | 0 |
| 2026-08-28 | skip_c_too_wide | $0.00 | C | 75.00 | 0 |
| 2026-08-31 | skip_c_too_wide | $0.00 | C | 100.00 | 0 |
| 2026-09-01 | skip_c_too_wide | $0.00 | C | 62.25 | 0 |
| 2026-09-02 | skip_c_too_wide | $0.00 | C | 59.25 | 0 |
| 2026-09-03 | skip_c_too_wide | $0.00 | C | 62.25 | 0 |
| 2026-09-04 | skip_c_too_wide | $0.00 | C | 81.25 | 0 |
| 2026-09-08 | skip_c_too_wide | $0.00 | C | 115.00 | 0 |
| 2026-09-09 | skip_c_too_wide | $0.00 | C | 82.00 | 0 |
| 2026-09-10 | skip_c_too_wide | $0.00 | C | 65.75 | 0 |
| 2026-09-11 | skip_c_too_wide | $0.00 | C | 79.00 | 0 |
| 2026-09-14 | skip_c_too_wide | $0.00 | C | 53.25 | 0 |
| 2026-09-15 | skip_c_too_wide | $0.00 | C | 54.00 | 0 |
| 2026-09-16 | skipped | $0.00 | A | 40.75 | 0 |
| 2026-09-17 | skip_c_too_wide | $0.00 | C | 96.75 | 0 |
| 2026-09-18 | traded | $140.25 | A | 41.00 | 1 |
| 2026-09-21 | skipped | $0.00 | A | 44.25 | 0 |

## VERDICT

**drop** — only 1 trades / 27 C-wide days; net $140.25
