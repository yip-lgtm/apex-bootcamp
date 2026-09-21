# MNQ Variant — 15m ORB + VWAP (opposite-OR SL, mid fallback)

**Generated:** 2026-09-21 13:27:48 EDT  
**Symbol:** MNQ=F (Micro Nasdaq) · **Size:** 1 Micro ($2.0/pt) · **Bars:** 5m (yfinance)  
**Strategy:** 15m ORB + VWAP (opposite-OR SL, mid fallback) (`base_15m`)  
**Window:** 2026-08-10 → 2026-09-21 (30 trading days, end 2026-09-21)  
**Data span:** 2026-07-13T00:00:00-04:00 → 2026-09-21T13:15:00-04:00

## Hard constraints

- 1 Micro fixed · brackets · daily **−$100 / +$300** · skip T1 chase · no scale/average
- Session tags: LDLZ 02:00–05:00 NY · NYKZ 08:30–11:00 NY
- TP: **1.5R** · Same-bar SL+TP: **SL first**

## Summary

| Metric | Value |
|---|---|
| Total net P&L | $150.00 |
| Max DD $ | $0.00 |
| Win rate | 100.00% (1W / 0L / 0F) |
| Avg R | 1.5000 |
| Expectancy $/trade | $150.0000 |
| # Trades | 1 |
| Best day | 2026-09-18 ($150.00) |
| Worst day | 2026-08-10 ($0.00) |
| Qualified days (≥$250 net) | 0 |
| Cumulative ≥ $3000? | False |
| Max DD vs $2000 trail breach? | False |

## Session tag breakdown

| Tag | #Trades | P&L | Win% | Avg R |
|---|---|---|---|---|
| LDLZ | 0 | $0.00 | 0.00% | 0.0000 |
| NYKZ | 1 | $150.00 | 100.00% | 1.5000 |
| other | 0 | $0.00 | 0.00% | 0.0000 |

## Day status counts

- `skip_c_too_wide`: 29
- `traded`: 1

## Trades

| Date | Dir | Entry NY | Tag | Entry | SL | TP | R$ | Exit | Why | P&L | R |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-18 | SHORT | 09:45 | NYKZ | 29795.25 | 29845.25 | 29720.25 | 100.00 | 29720.25 | TP | $150.00 | 1.50 |

## Daily P&L

| Date | Status | Day P&L | Grade | OR width | #Trades |
|---|---|---|---|---|---|
| 2026-08-10 | skip_c_too_wide | $0.00 | C | 122.25 | 0 |
| 2026-08-11 | skip_c_too_wide | $0.00 | C | 164.00 | 0 |
| 2026-08-12 | skip_c_too_wide | $0.00 | C | 148.25 | 0 |
| 2026-08-13 | skip_c_too_wide | $0.00 | C | 191.00 | 0 |
| 2026-08-14 | skip_c_too_wide | $0.00 | C | 99.50 | 0 |
| 2026-08-17 | skip_c_too_wide | $0.00 | C | 100.50 | 0 |
| 2026-08-18 | skip_c_too_wide | $0.00 | C | 139.00 | 0 |
| 2026-08-19 | skip_c_too_wide | $0.00 | C | 181.50 | 0 |
| 2026-08-20 | skip_c_too_wide | $0.00 | C | 131.75 | 0 |
| 2026-08-21 | skip_c_too_wide | $0.00 | C | 160.25 | 0 |
| 2026-08-24 | skip_c_too_wide | $0.00 | C | 267.50 | 0 |
| 2026-08-25 | skip_c_too_wide | $0.00 | C | 97.75 | 0 |
| 2026-08-26 | skip_c_too_wide | $0.00 | C | 139.25 | 0 |
| 2026-08-27 | skip_c_too_wide | $0.00 | C | 146.75 | 0 |
| 2026-08-28 | skip_c_too_wide | $0.00 | C | 138.75 | 0 |
| 2026-08-31 | skip_c_too_wide | $0.00 | C | 127.00 | 0 |
| 2026-09-01 | skip_c_too_wide | $0.00 | C | 100.50 | 0 |
| 2026-09-02 | skip_c_too_wide | $0.00 | C | 82.25 | 0 |
| 2026-09-03 | skip_c_too_wide | $0.00 | C | 160.50 | 0 |
| 2026-09-04 | skip_c_too_wide | $0.00 | C | 91.50 | 0 |
| 2026-09-08 | skip_c_too_wide | $0.00 | C | 220.50 | 0 |
| 2026-09-09 | skip_c_too_wide | $0.00 | C | 89.50 | 0 |
| 2026-09-10 | skip_c_too_wide | $0.00 | C | 142.25 | 0 |
| 2026-09-11 | skip_c_too_wide | $0.00 | C | 93.00 | 0 |
| 2026-09-14 | skip_c_too_wide | $0.00 | C | 73.50 | 0 |
| 2026-09-15 | skip_c_too_wide | $0.00 | C | 70.00 | 0 |
| 2026-09-16 | skip_c_too_wide | $0.00 | C | 50.25 | 0 |
| 2026-09-17 | skip_c_too_wide | $0.00 | C | 132.00 | 0 |
| 2026-09-18 | traded | $150.00 | A | 46.50 | 1 |
| 2026-09-21 | skip_c_too_wide | $0.00 | C | 124.25 | 0 |

## VERDICT

**drop** — only 1 trades / 29 C-wide days; net $150.00
