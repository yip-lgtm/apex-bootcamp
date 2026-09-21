# Backtests (local runs)

Generated on the Night Shift / A皮 box. Engine: `AUTOMATION/src/apex_backtest.py` (v2.6 killzone, A+B trade / skip C).

## 2026-09-21 runs

| File | Window | Symbols | Killzone | Notes |
|------|--------|---------|----------|-------|
| `2026-09-01_2026-09-20-mnq-mgc-ldlz-nykz830.*` | 20d strict filter | MNQ+MGC | LDLZ 02–05 + NYKZ 08:30–11 | Filtered: 6 trades, 50%, +$755 |
| `2026-08-22_2026-09-20-mnq-30d.md` | ~30d | MNQ | prior window | +$294 / 18 / 22% |
| `2026-08-22_2026-09-20-mgc-30d.md` | ~30d | MGC | NY AM 09–11 style (earlier) | +$541 / 6 / 50% |
| `2026-08-22_2026-09-20-mgc-ldlz-nykz710.md` | ~30d | MGC | LDLZ + NYKZ 07–10 | filtered 30d −$800 |
| `2026-08-22_2026-09-20-mgc-ldlz-nykz830.md` | ~30d | MGC | LDLZ + NYKZ 08:30–11 | filtered 30d +$8 |

Caveat: raw engine 5m span can include days outside the requested window; prefer filtered notes in chat / README.
