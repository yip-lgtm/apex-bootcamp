# BEST: MBT=F + `apex_v26_kz`

**Strategy:** Apex v2.6 LDLZ+NYKZ (HTF+structure TP, risk $100, TP cap $300)  
**Verdict:** **tweak** — net $600.00, WR 100.0%, n=2, qual_days=2, expectancy=$300.00/trade — positive but shy of keep gates (≥$3k / ≥3 qual days)  

## Full stats

| Metric | Value |
|---|---|
| ticker | MBT=F |
| point_value | 0.1 |
| variant | apex_v26_kz |
| first_day | 2026-08-17 |
| last_day | 2026-09-21 |
| n_trading_days_used | 30 |
| total_net_pnl | 600.0 |
| max_dd_usd | 0.0 |
| win_rate_pct | 100.0 |
| avg_r | 3.0 |
| expectancy_usd | 300.0 |
| n_trades | 2 |
| n_wins | 2 |
| n_losses | 0 |
| qualified_days_ge_250 | 2 |
| cumulative_ge_3000 | False |
| max_dd_vs_2000_trail_breach | False |

### Session breakdown
```json
{
  "LDLZ": {
    "n": 0,
    "pnl": 0.0,
    "win_rate": 0.0,
    "avg_r": 0.0
  },
  "NYKZ": {
    "n": 2,
    "pnl": 600.0,
    "win_rate": 100.0,
    "avg_r": 3.0
  },
  "other": {
    "n": 0,
    "pnl": 0.0,
    "win_rate": 0.0,
    "avg_r": 0.0
  }
}
```

## Peer ranking (same strategy × 3 symbols)

| Rank | Symbol | Qual≥$250 | Trail breach | Net P&L | Expectancy | Verdict |
|---|---|---|---|---|---|---|
| 1 | MBT=F | 2 | False | $600.0 | $300.0 | tweak |
| 2 | MGC=F | 2 | False | $363.0 | $51.8576 | tweak |
| 3 | MNQ=F | 2 | False | $166.5 | $18.5 | tweak |

## MNQ strategy pick

- `apex_v26_kz`: qual=2 net=$166.5 exp=$18.5 n=9 → tweak
- `base_15m`: qual=0 net=$150.0 exp=$150.0 n=1 → drop
- `variant_A_5m`: qual=0 net=$140.25 exp=$140.25 n=1 → drop
- `variant_B_30m_mid`: qual=0 net=$0.0 exp=$0.0 n=0 → drop

Reports: `/workspace/apex_strategy_pick_bt/{mnq,mgc,mbt}/`
