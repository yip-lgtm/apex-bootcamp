# MNQ ORB+VWAP — 5m/10m OR + dynamic $100 risk (vs prior 15m drop)

**Generated:** 2026-09-21 13:48:23 EDT  
**Symbol:** MNQ=F · 1 Micro ($2.0/pt) · 5m yfinance  
**Window:** 2026-08-10 → 2026-09-21 (30 trading days, end 2026-09-21)  
**Data span:** 2026-07-13T00:00:00-04:00 → 2026-09-21T13:35:00-04:00

## Rule changes (vs prior 15m)

- OR window: **5m (09:30–09:35)** and **10m (09:30–09:40)** (prior: 15m 09:30–09:45)
- Dynamic risk: prefer opposite-OR SL; if risk > $100 use **OR mid**; skip only if mid also > $100
- Day C-skip threshold moved from full-OR risk > $100 (OR width > 50 pts) to **mid risk > $100** (OR width > 100 pts)
- Unchanged: VWAP filter, 1 Micro, brackets, daily −$100/+ $300, skip chase past T1, first-break lock, TP 1.5R, same-bar SL first

## Prior baseline (15m OR, full-OR C-skip)

| Metric | Value |
|---|---|
| Net P&L | $150.00 |
| Max DD | $0.00 |
| WR | 100.00% |
| Qual ≥$250 | 0 |
| n | 1 |
| C-skips | 29 |
| Verdict | **drop** |

## Variant comparison

| Variant | OR | Net | Max DD | WR | Qual≥$250 | n | C-skips | mid-SL | opp-SL | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| prior_15m | 09:30–09:45 | $150.00 | $0.00 | 100.0% | 0 | 1 | 29 | — | — | drop |
| `or_5m_dyn` | 09:30–09:35 | $-166.62 | $377.25 | 28.6% | 0 | 7 | 9 | 6 | 1 | drop |
| `or_10m_dyn` | 09:30–09:40 | $18.12 | $254.50 | 40.0% | 0 | 5 | 17 | 4 | 1 | tweak |

## BEST VARIANT: `or_10m_dyn`

**Label:** 10m ORB + VWAP (dyn risk: opp→mid, mid-cap C-skip)  
**OR window:** 09:30–09:40 America/New_York  
**Risk mode:** dynamic: opposite-OR if ≤$100 else mid; C-skip only if mid>$100

| Metric | Value |
|---|---|
| Total net P&L | $18.12 |
| Max DD $ | $254.50 |
| Win rate | 40.00% (2W / 3L / 0F) |
| Avg R | 0.0000 |
| Expectancy $/trade | $3.6250 |
| # Trades (n) | 5 |
| Qualified days (≥$250) | 0 |
| C-skips | 17 |
| Best day | 2026-09-18 ($140.25) |
| Worst day | 2026-09-11 ($-89.00) |

### Session split

| Tag | # | P&L | Win% | Avg R |
|---|---|---|---|---|
| LDLZ | 0 | $0.00 | 0.00% | 0.0000 |
| NYKZ | 5 | $18.12 | 40.00% | 0.0000 |
| other | 0 | $0.00 | 0.00% | 0.0000 |

### Day status counts

- `skip_c_too_wide`: 17
- `skipped`: 8
- `traded`: 5

### Trades

| Date | Dir | Entry NY | Tag | Entry | SL | TP | R$ | Mode | Exit | Why | P&L | R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-01 | LONG | 09:45 | NYKZ | 29143.00 | 29100.12 | 29207.31 | 85.75 | or_mid | 29100.12 | SL | $-85.75 | -1.00 |
| 2026-09-02 | SHORT | 09:50 | NYKZ | 29029.50 | 29069.38 | 28969.69 | 79.75 | or_mid | 29069.38 | SL | $-79.75 | -1.00 |
| 2026-09-11 | LONG | 09:40 | NYKZ | 29434.00 | 29389.50 | 29500.75 | 89.00 | or_mid | 29389.50 | SL | $-89.00 | -1.00 |
| 2026-09-14 | LONG | 09:40 | NYKZ | 28951.25 | 28907.12 | 29017.44 | 88.25 | or_mid | 29017.44 | TP | $132.38 | 1.50 |
| 2026-09-18 | SHORT | 09:45 | NYKZ | 29795.25 | 29842.00 | 29725.12 | 93.50 | opposite_or | 29725.12 | TP | $140.25 | 1.50 |

### Daily P&L (best variant)

| Date | Status | Day P&L | Grade | OR width | Full$ | Mid$ | #Trades |
|---|---|---|---|---|---|---|---|
| 2026-08-10 | skip_c_too_wide | $0.00 | C | 114.50 | 229.00 | 114.50 | 0 |
| 2026-08-11 | skip_c_too_wide | $0.00 | C | 164.00 | 328.00 | 164.00 | 0 |
| 2026-08-12 | skip_c_too_wide | $0.00 | C | 135.00 | 270.00 | 135.00 | 0 |
| 2026-08-13 | skip_c_too_wide | $0.00 | C | 177.25 | 354.50 | 177.25 | 0 |
| 2026-08-14 | skipped | $0.00 | B | 99.50 | 199.00 | 99.50 | 0 |
| 2026-08-17 | skip_c_too_wide | $0.00 | C | 100.50 | 201.00 | 100.50 | 0 |
| 2026-08-18 | skip_c_too_wide | $0.00 | C | 124.00 | 248.00 | 124.00 | 0 |
| 2026-08-19 | skip_c_too_wide | $0.00 | C | 154.25 | 308.50 | 154.25 | 0 |
| 2026-08-20 | skip_c_too_wide | $0.00 | C | 131.75 | 263.50 | 131.75 | 0 |
| 2026-08-21 | skip_c_too_wide | $0.00 | C | 153.25 | 306.50 | 153.25 | 0 |
| 2026-08-24 | skip_c_too_wide | $0.00 | C | 177.75 | 355.50 | 177.75 | 0 |
| 2026-08-25 | skipped | $0.00 | B | 97.75 | 195.50 | 97.75 | 0 |
| 2026-08-26 | skip_c_too_wide | $0.00 | C | 107.25 | 214.50 | 107.25 | 0 |
| 2026-08-27 | skip_c_too_wide | $0.00 | C | 146.75 | 293.50 | 146.75 | 0 |
| 2026-08-28 | skipped | $0.00 | B | 97.25 | 194.50 | 97.25 | 0 |
| 2026-08-31 | skip_c_too_wide | $0.00 | C | 127.00 | 254.00 | 127.00 | 0 |
| 2026-09-01 | traded | $-85.75 | B | 80.75 | 161.50 | 80.75 | 1 |
| 2026-09-02 | traded | $-79.75 | B | 65.25 | 130.50 | 65.25 | 1 |
| 2026-09-03 | skip_c_too_wide | $0.00 | C | 135.25 | 270.50 | 135.25 | 0 |
| 2026-09-04 | skipped | $0.00 | B | 91.50 | 183.00 | 91.50 | 0 |
| 2026-09-08 | skip_c_too_wide | $0.00 | C | 125.25 | 250.50 | 125.25 | 0 |
| 2026-09-09 | skipped | $0.00 | B | 82.75 | 165.50 | 82.75 | 0 |
| 2026-09-10 | skip_c_too_wide | $0.00 | C | 127.50 | 255.00 | 127.50 | 0 |
| 2026-09-11 | traded | $-89.00 | B | 84.50 | 169.00 | 84.50 | 1 |
| 2026-09-14 | traded | $132.38 | B | 53.25 | 106.50 | 53.25 | 1 |
| 2026-09-15 | skipped | $0.00 | B | 70.00 | 140.00 | 70.00 | 0 |
| 2026-09-16 | skipped | $0.00 | A | 48.75 | 97.50 | 48.75 | 0 |
| 2026-09-17 | skip_c_too_wide | $0.00 | C | 132.00 | 264.00 | 132.00 | 0 |
| 2026-09-18 | traded | $140.25 | A | 43.25 | 86.50 | 43.25 | 1 |
| 2026-09-21 | skipped | $0.00 | B | 87.25 | 174.50 | 87.25 | 0 |

## Alternate: `or_5m_dyn`

Net $-166.62 · MaxDD $377.25 · WR 28.6% · n=7 · C-skips=9 · qual≥$250=0 · verdict=drop

| Date | Dir | Entry NY | Tag | R$ | Mode | Why | P&L | R |
|---|---|---|---|---|---|---|---|---|
| 2026-08-17 | SHORT | 09:35 | NYKZ | 98.75 | or_mid | SL | $-98.75 | -1.00 |
| 2026-09-01 | LONG | 09:45 | NYKZ | 98.25 | or_mid | SL | $-98.25 | -1.00 |
| 2026-09-02 | SHORT | 09:50 | NYKZ | 85.75 | or_mid | SL | $-85.75 | -1.00 |
| 2026-09-11 | LONG | 09:40 | NYKZ | 94.50 | or_mid | SL | $-94.50 | -1.00 |
| 2026-09-14 | LONG | 09:40 | NYKZ | 88.25 | or_mid | TP | $132.38 | 1.50 |
| 2026-09-15 | LONG | 09:35 | NYKZ | 62.00 | or_mid | SL | $-62.00 | -1.00 |
| 2026-09-18 | SHORT | 09:45 | NYKZ | 93.50 | opposite_or | TP | $140.25 | 1.50 |

## VERDICT vs prior 15m drop

**Best:** `or_10m_dyn` — net $18.12, maxDD $254.50, WR 40.0%, qual≥$250=0, n=5, C-skips=17 → **tweak**

Δ vs prior 15m (+$150 / n=1 / 29 C-skips): net -131.88, n +4, C-skips -12.

**Partial improve** — Dynamic mid-cap cut C-skips and raised fill count. Verdict remains **tweak** vs prior drop.

_Facts only. Source: yfinance `MNQ=F` 5m._
