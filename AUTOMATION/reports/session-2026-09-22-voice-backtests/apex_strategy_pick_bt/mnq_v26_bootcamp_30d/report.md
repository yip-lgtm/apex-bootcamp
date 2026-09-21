# Apex Bootcamp v2.6 — MNQ 5m constrained 30-trading-day backtest

**Generated:** 2026-09-21 13:42:39 EDT  
**Symbol:** MNQ=F · 1 Micro ($2/pt) · brackets only  
**Window:** 2026-08-10 → 2026-09-21 (30 trading days, end 2026-09-21)  
**Earliest bar:** `2026-07-13T00:00:00-04:00`  
**Latest bar:** `2026-09-21T13:30:00-04:00`  
**Data source:** **yfinance** (no Tradovate/Ninja OHLC bar series found on machine; UI screenshot extracts only — dual-run skipped)  

## Caller constraints (exact)

- Risk **$100**/trade · TP envelope **$200–$500** · daily kill **−$100** · daily TP cap **+$300**
- RR **2–5** · **1 Micro** fixed · brackets only · no scale/average
- HTF alignment required · A/B only (skip C) · skip chase past T1/TP
- Killzones: **LDLZ 02:00–05:00 NY** + **NYKZ 08:30–11:00 NY**

## Headline metrics

| Metric | Value |
|---|---|
| Net P&L | $170.00 |
| Max DD vs $2k trail | $400.00 (breach=False) |
| Qual days ≥$250 | 2 |
| Win rate | 33.33% (3W / 6L / 0F) |
| Avg R | 0.1889 |
| Expectancy $/trade | $18.8889 |
| # Trades | 9 |
| Best day | 2026-09-03 ($300.00) |
| Worst day | 2026-08-19 ($-100.00) |
| Cum ≥ $3000? | N |

## LDLZ vs NYKZ

| Tag | # | P&L | Win% | Avg R |
|---|---|---|---|---|
| LDLZ | 0 | $0.00 | 0.00% | 0.0000 |
| NYKZ | 9 | $170.00 | 33.33% | 0.1889 |
| other | 0 | $0.00 | 0.00% | 0.0000 |

## Month-by-month

| Month | Session days | Traded days | Trades | W/L | WR% | P&L |
|---|---|---|---|---|---|---|
| 2026-08 | 16 | 4 | 4 | 0/4 | 0.00% | $-400.00 |
| 2026-09 | 14 | 5 | 5 | 3/2 | 60.00% | $570.00 |

## Status counts

- `grade_C`: 13
- `no_trigger`: 8
- `traded`: 9

## Changelog ~$3,900/60d vs LAST 30d

- **Prior claim:** +$3,920 / 60d, 52% hit (portfolio MGC+MNQ+MBT+MCL) (2026-06-02 → 2026-08-01 (~60 calendar days))
- **Prior MNQ-only in that sample:** $1883 / 21 trades / 42.9% WR
- **This run (last 30 trading days, MNQ, caller constraints):** net **$170.00**, WR 33.33%, n=9
- **Pro-rata 30d refs:** portfolio ≈ $1960; MNQ ≈ $942
- **Explicit answer: NO** — Last-30d MNQ-only constrained net=$170.00 vs changelog portfolio $3920/60d (and MNQ-only $1883/60d in sample). Pro-rata 30d portfolio≈$1960, MNQ≈$942. Last 30d is far below both; claim does not hold for this window under caller constraints.
- Caveat: Changelog v2.6 sample used NY AM killzone 09:00–11:00 EST and TP up to $500; this constrained run uses LDLZ 02:00–05:00 NY + NYKZ 08:30–11:00 NY, daily TP cap +$300, skip C, skip chase past T1/TP, 1 Micro brackets.

## Trades

| Date | Dir | Entry NY | Tag | Pattern | Grade | Entry | SL | TP | Exit | Why | P&L | R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-08-19 | LONG | 11:00 | NYKZ | mss_up | B | 29623.25 | 29573.25 | 29742.25 | 29573.25 | SL | $-100.00 | -1.00 |
| 2026-08-24 | SHORT | 11:00 | NYKZ | orb_break_short | A | 29083.00 | 29133.00 | 28962.75 | 29133.00 | SL | $-100.00 | -1.00 |
| 2026-08-26 | LONG | 11:00 | NYKZ | orb_break_long | B | 29252.25 | 29202.25 | 29402.25 | 29202.25 | SL | $-100.00 | -1.00 |
| 2026-08-27 | LONG | 11:00 | NYKZ | orb_break_long | A | 29601.25 | 29551.25 | 29704.00 | 29551.25 | SL | $-100.00 | -1.00 |
| 2026-09-03 | LONG | 11:00 | NYKZ | orb_break_long | A | 29363.50 | 29313.50 | 29513.50 | 29513.50 | TP | $300.00 | 3.00 |
| 2026-09-04 | LONG | 11:00 | NYKZ | pin_bar_long | B | 29520.50 | 29470.50 | 29670.50 | 29470.50 | SL | $-100.00 | -1.00 |
| 2026-09-08 | LONG | 11:00 | NYKZ | mss_up | A | 29563.00 | 29513.00 | 29713.00 | 29513.00 | SL | $-100.00 | -1.00 |
| 2026-09-15 | LONG | 11:00 | NYKZ | orb_break_long | B | 29240.00 | 29190.00 | 29390.00 | 29331.50 | EOD | $183.00 | 1.83 |
| 2026-09-21 | LONG | 11:00 | NYKZ | orb_break_long | A | 30550.75 | 30500.75 | 30694.25 | 30694.25 | TP | $287.00 | 2.87 |

## Daily P&L

| Date | Status | Day P&L | Grade | #Trades |
|---|---|---|---|---|
| 2026-08-10 | grade_C | $0.00 | C | 0 |
| 2026-08-11 | grade_C | $0.00 | C | 0 |
| 2026-08-12 | grade_C | $0.00 | C | 0 |
| 2026-08-13 | no_trigger | $0.00 | None | 0 |
| 2026-08-14 | grade_C | $0.00 | C | 0 |
| 2026-08-17 | grade_C | $0.00 | C | 0 |
| 2026-08-18 | grade_C | $0.00 | C | 0 |
| 2026-08-19 | traded | $-100.00 | B | 1 |
| 2026-08-20 | no_trigger | $0.00 | None | 0 |
| 2026-08-21 | grade_C | $0.00 | C | 0 |
| 2026-08-24 | traded | $-100.00 | A | 1 |
| 2026-08-25 | no_trigger | $0.00 | None | 0 |
| 2026-08-26 | traded | $-100.00 | B | 1 |
| 2026-08-27 | traded | $-100.00 | A | 1 |
| 2026-08-28 | grade_C | $0.00 | C | 0 |
| 2026-08-31 | no_trigger | $0.00 | None | 0 |
| 2026-09-01 | grade_C | $0.00 | C | 0 |
| 2026-09-02 | no_trigger | $0.00 | None | 0 |
| 2026-09-03 | traded | $300.00 | A | 1 |
| 2026-09-04 | traded | $-100.00 | B | 1 |
| 2026-09-08 | traded | $-100.00 | A | 1 |
| 2026-09-09 | no_trigger | $0.00 | None | 0 |
| 2026-09-10 | no_trigger | $0.00 | None | 0 |
| 2026-09-11 | grade_C | $0.00 | C | 0 |
| 2026-09-14 | no_trigger | $0.00 | None | 0 |
| 2026-09-15 | traded | $183.00 | B | 1 |
| 2026-09-16 | grade_C | $0.00 | C | 0 |
| 2026-09-17 | grade_C | $0.00 | C | 0 |
| 2026-09-18 | grade_C | $0.00 | C | 0 |
| 2026-09-21 | traded | $287.00 | A | 1 |

## VERDICT

**tweak — net $170.00, WR 33.3%, n=9, qual_days=2, expectancy=$18.89/trade — positive but shy of keep gates (≥$3k / ≥3 qual days)**
