# Session backtests — 2026-09-22 (voice / overnight)

Backup of on-box research from Grok Bot session (~HKT Sep 22). Data for live decisions remains Tradovate; these runs mostly used **yfinance 5m** (capped ~60 calendar days).

## Layout

| Path | Contents |
|------|----------|
| `orb_vwap_mnq_bt/` | MNQ 15m ORB+VWAP 30d (verdict **drop**); scripts + trades |
| `orb_vwap_mnq_bt/variant_A_5m/` | 5m OR variant |
| `orb_vwap_mnq_bt/variant_B_30m_mid/` | 30m OR mid-stop variant |
| `apex_strategy_pick_bt/` | Strategy pick pipeline (MNQ/MGC/MBT), rankings, BEST_COMBO |
| `apex_strategy_pick_bt/mbt/` | MBT 30d Apex v2.6 kz |
| `apex_strategy_pick_bt/mbt_extended/` | MBT max 5m history (~60 trading days) |
| `apex_strategy_pick_bt/mgc/` | MGC 30d same strategy |
| `apex_strategy_pick_bt/mnq/` | MNQ 30d same strategy |
| `apex_strategy_pick_bt/mnq_v26_bootcamp_30d/` | Bootcamp-params MNQ 30d (changelog $3900/60d check) |
| `apex_strategy_pick_bt/variants/` | ORB/kz variant reports |
| `apex_strategy_pick_bt/parallel_cmp/` | Parallel follow-ups (MBT scale / MNQ ORB fix / MGC feed) — may still be filling |
| `apex_strategy_pick_bt/scripts/` | Python runners used for constrained BTs |

## Headline results (as of backup)

- **BEST combo (30d):** `MBT=F` + Apex v2.6 kz → **+$600**, 2 qual days, n=2 → **tweak** (tiny sample)
- **MNQ bootcamp 30d:** **+$170**, WR 33%, n=9 → **tweak**; old ~$3900/60d changelog **does not** hold on last 30d
- **15m ORB+VWAP:** **drop** (OR too wide vs $100 risk)
- **Live lock:** Apex PyLab ORB on Tradovate (MNQ+MGC+MBT), −$100/+ $300, LDLZ+NYKZ

## Notes

- No Tradovate/Ninja OHLC archive on the box for these BTs — yfinance only.
- Do not treat yfinance continuous `MGC=F` as identical to Tradovate `MGCV6` (prior ~35pt sim vs Yahoo gap).
