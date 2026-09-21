# MNQ Variant — 30m ORB + VWAP (prefer mid-OR SL)

**Generated:** 2026-09-21 13:27:48 EDT  
**Symbol:** MNQ=F (Micro Nasdaq) · **Size:** 1 Micro ($2.0/pt) · **Bars:** 5m (yfinance)  
**Strategy:** 30m ORB + VWAP (prefer mid-OR SL) (`variant_B_30m_mid`)  
**Window:** 2026-08-10 → 2026-09-21 (30 trading days, end 2026-09-21)  
**Data span:** 2026-07-13T00:00:00-04:00 → 2026-09-21T13:15:00-04:00

## Hard constraints

- 1 Micro fixed · brackets · daily **−$100 / +$300** · skip T1 chase · no scale/average
- Session tags: LDLZ 02:00–05:00 NY · NYKZ 08:30–11:00 NY
- TP: **1.5R** · Same-bar SL+TP: **SL first**

## Summary

| Metric | Value |
|---|---|
| Total net P&L | $0.00 |
| Max DD $ | $0.00 |
| Win rate | 0.00% (0W / 0L / 0F) |
| Avg R | 0.0000 |
| Expectancy $/trade | $0.0000 |
| # Trades | 0 |
| Best day | 2026-08-10 ($0.00) |
| Worst day | 2026-08-10 ($0.00) |
| Qualified days (≥$250 net) | 0 |
| Cumulative ≥ $3000? | False |
| Max DD vs $2000 trail breach? | False |

## Session tag breakdown

| Tag | #Trades | P&L | Win% | Avg R |
|---|---|---|---|---|
| LDLZ | 0 | $0.00 | 0.00% | 0.0000 |
| NYKZ | 0 | $0.00 | 0.00% | 0.0000 |
| other | 0 | $0.00 | 0.00% | 0.0000 |

## Day status counts

- `skip_c_too_wide`: 28
- `skipped`: 2

## Trades

_No trades._

## Daily P&L

| Date | Status | Day P&L | Grade | OR width | #Trades |
|---|---|---|---|---|---|
| 2026-08-10 | skip_c_too_wide | $0.00 | C | 122.25 | 0 |
| 2026-08-11 | skip_c_too_wide | $0.00 | C | 206.75 | 0 |
| 2026-08-12 | skip_c_too_wide | $0.00 | C | 148.25 | 0 |
| 2026-08-13 | skip_c_too_wide | $0.00 | C | 318.25 | 0 |
| 2026-08-14 | skip_c_too_wide | $0.00 | C | 110.75 | 0 |
| 2026-08-17 | skip_c_too_wide | $0.00 | C | 100.50 | 0 |
| 2026-08-18 | skip_c_too_wide | $0.00 | C | 165.00 | 0 |
| 2026-08-19 | skip_c_too_wide | $0.00 | C | 334.25 | 0 |
| 2026-08-20 | skip_c_too_wide | $0.00 | C | 161.00 | 0 |
| 2026-08-21 | skip_c_too_wide | $0.00 | C | 215.25 | 0 |
| 2026-08-24 | skip_c_too_wide | $0.00 | C | 296.00 | 0 |
| 2026-08-25 | skip_c_too_wide | $0.00 | C | 136.75 | 0 |
| 2026-08-26 | skip_c_too_wide | $0.00 | C | 159.50 | 0 |
| 2026-08-27 | skip_c_too_wide | $0.00 | C | 181.00 | 0 |
| 2026-08-28 | skip_c_too_wide | $0.00 | C | 141.50 | 0 |
| 2026-08-31 | skip_c_too_wide | $0.00 | C | 130.25 | 0 |
| 2026-09-01 | skip_c_too_wide | $0.00 | C | 117.75 | 0 |
| 2026-09-02 | skip_c_too_wide | $0.00 | C | 101.75 | 0 |
| 2026-09-03 | skip_c_too_wide | $0.00 | C | 176.00 | 0 |
| 2026-09-04 | skip_c_too_wide | $0.00 | C | 138.25 | 0 |
| 2026-09-08 | skip_c_too_wide | $0.00 | C | 232.00 | 0 |
| 2026-09-09 | skip_c_too_wide | $0.00 | C | 150.00 | 0 |
| 2026-09-10 | skip_c_too_wide | $0.00 | C | 146.00 | 0 |
| 2026-09-11 | skip_c_too_wide | $0.00 | C | 127.75 | 0 |
| 2026-09-14 | skip_c_too_wide | $0.00 | C | 165.75 | 0 |
| 2026-09-15 | skipped | $0.00 | A | 81.00 | 0 |
| 2026-09-16 | skip_c_too_wide | $0.00 | C | 108.50 | 0 |
| 2026-09-17 | skip_c_too_wide | $0.00 | C | 132.00 | 0 |
| 2026-09-18 | skipped | $0.00 | A | 79.50 | 0 |
| 2026-09-21 | skip_c_too_wide | $0.00 | C | 206.25 | 0 |

## VERDICT

**drop** — zero fills under ORB+VWAP+$100 risk filters
