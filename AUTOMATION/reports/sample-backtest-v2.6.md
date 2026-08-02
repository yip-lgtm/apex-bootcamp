# Apex 50K Backtest Report (v2.6 — killzone) — 2026-06-02 → 2026-08-01
_Window: 2026-06-02 → 2026-08-01 (UTC-4) · ~60 calendar days · yfinance 5m cap = 60 days_
**v2.6 engine:** HTF alignment required · structure-based TP · ORB / VWAP-reject patterns · **KILLZONE filter: only triggers in 09:00-11:00 EST** (NY AM session).
**Rules:** Risk $100 · TP $200-500 · RR 2-5 · 1 micro · daily kill-switch $100

## Headline
- **29 trades** over the window, **15 wins** (51.7% hit rate) → **PROFIT $3920** ($+135.2/trade avg)

## Per-ticker results
| Ticker | Trades | Wins | Hit% (TP-only) | TP/SL/EOD | P&L $ | Avg $ | MaxDD $ | Sharpe | PF |
|--------|--------|------|---------------|-----------|-------|-------|---------|--------|----|
| MGC=F | 7 | 5 | 71.4% | 5/2/0 | $+1,570 | $+224 | $100 | 16.13 | 8.85 |
| MNQ=F | 21 | 9 | 42.9% | 9/12/0 | $+1,883 | $+90 | $700 | 6.17 | 2.57 |
| MBT=F | 1 | 1 | 100.0% | 1/0/0 | $+466 | $+466 | $0 | 0.00 | inf |
| MCL=F | 0 | 0 | 0% | 0/0/0 | $+0 | $+0 | $0 | 0.00 | 0 |

## Equity curve (portfolio, 4 micro combined)
```
P&L  high=$+4,319  low=$+245  final=$+3,919  maxDD=$600
                                 ● ●            ●   ● ● ● ●   
                         ● ● ● ●     ● ●  ● ●     ●          ●
                       ●                      ●               
                    ●                                         
                                                              
                  ●                                           
              ● ●                                             
                                                              
          ● ●                                                 
      ● ●                                                     
    ●                                                         
  ●                                                           
  ────────────────────────────────────────────────────────────
              start               →                        now
```

### MGC=F equity curve
```
  $+354  ────────────────────────────────────────────────  $+1,670
                                               ●        ●
                                                         
                               ●       ●                 
                                                         
                       ●                                 
               ●                                         
                                                         
       ●                                                 
       final: $+1,570  (7 trades, 5 wins)
```

### MNQ=F equity curve
```
  $+145  ────────────────────────────────────────────────  $+2,484
                          ●  ● ● ●  ●           ●        
                     ●  ●             ●  ● ●       ● ●  ●
                   ●                          ●          
                                                         
              ● ●                                        
                                                         
       ●   ●                                             
         ●                                               
       final: $+1,883  (21 trades, 9 wins)
```

### MBT=F equity curve
```
  $+466  ────────────────────────────────────────────────  $+468
                                                         
                                                         
                                                         
                                                         
                                                         
                                                         
                                                         
       ●                                                 
       final: $+466  (1 trades, 1 wins)
```

## Top 5 wins
- 2026-06-29 MGC=F SHORT pin_bar_short        entry=4040.20 → exit=3990.20 (tp) **$+500**
- 2026-06-03 MNQ=F SHORT orb_break_short      entry=30667.25 → exit=30417.25 (tp) **$+500**
- 2026-06-04 MNQ=F LONG  mss_up               entry=30356.50 → exit=30595.50 (tp) **$+478**
- 2026-06-01 MNQ=F LONG  pin_bar_long         entry=30437.00 → exit=30671.50 (tp) **$+469**
- 2026-06-03 MBT=F SHORT vwap_reject_short    entry=66960.00 → exit=62295.00 (tp) **$+466**

## Top 5 losses
- 2026-07-31 MNQ=F LONG  pin_bar_long         entry=28308.50 → exit=28258.50 (sl) **$-100**
- 2026-07-28 MNQ=F SHORT orb_break_short      entry=27802.75 → exit=27852.75 (sl) **$-100**
- 2026-07-20 MNQ=F SHORT mss_down             entry=28891.50 → exit=28941.50 (sl) **$-100**
- 2026-07-01 MNQ=F SHORT orb_break_short      entry=30192.75 → exit=30242.75 (sl) **$-100**
- 2026-06-29 MNQ=F LONG  mss_up               entry=29714.00 → exit=29664.00 (sl) **$-100**

## Caveats & observations
- **yfinance 5m limit = 60 days**; requested 90 days was clamped. For 90-day backtest use 1h resolution (lower fidelity, but available).
- **Entry slippage = 1 bar** (next session's open). Gaps can fire the SL immediately.
- **Pattern detector is a deterministic proxy** for the LLM A/B/C grader. It catches the most common 5m triggers but won't replicate LLM nuance. Real LLM-driven A/B setups may differ.
- **EOD exits** mean neither TP nor SL hit by close — counted at mark-to-market. In live trading these would also exit EOD, but slippage may differ.
- **Apex daily kill-switch** at -$100 per ticker is enforced (no new entries same day).
- **No commissions / fees** modeled. Apex charges commissions on round-trip; deduct ~$2-5 per trade from each P&L.

## What to improve next
- Low hit rate on MCL=F → need stronger triggers or wider TP zone.
