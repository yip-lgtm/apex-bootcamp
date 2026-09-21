# MGC feed gap: Yahoo MGC=F vs Tradovate MGCV6

**Generated:** 2026-09-22 01:48:58 HKT / 2026-09-21 13:48:58 EDT  
**Observation window:** ~2026-09-22 01:28 HKT (= 2026-09-21 13:28 EDT) — screenshots `/workspace/screenshots/mgc-latest-*.png` mtime 17:28 UTC.

## Cause hypothesis (primary)

**Contract mismatch after continuous roll — not stale quote, not timezone, not GLOBEX-vs-RTH.**

| Feed | Symbol | Meaning | Price near obs |
|---|---|---|---|
| Tradovate sim | **MGCV6** | Micro Gold **Oct 2026** (V) | Last **4347.4**, bid/ask **4347.5 / 4347.9** (screenshot header) |
| Yahoo continuous | **MGC=F** | Tracks front / most-active continuous | ~**4383–4384** at 13:25 EDT 5m |
| Yahoo specific | **MGCV26.CMX** | Oct 2026 | 5m close 13:25 EDT **4350.2** (13:20 **4346.9**) |
| Yahoo specific | **MGCZ26.CMX** | Dec 2026 | 5m close 13:25 EDT **4384.4** (matches MGC=F) |

**Calendar spread Z−V ≈ 34 pts** explains the ~35 pt gap:

- Pull-time fast last (2026-09-22 01:48 HKT): `MGC=F` **4377.1**, `MGCV26.CMX` **4343.3**, `MGCZ26.CMX` **4377.0** → **MGC=F − V ≈ 33.8**, **Z − V ≈ 33.7**.
- Same pattern on full-size gold: `GCZ26.CMX` **4377.1** vs `GCV26.CMX` **4342.5** (spread **34.6**).

### Roll evidence (daily closes)

Through **2026-09-18**, Yahoo `MGC=F` **identical** to `MGCV26.CMX` (and ~34 below Z).  
On **2026-09-21**, `MGC=F` **switched** to track `MGCZ26.CMX` (identical closes/volume **262030**); V volume only **26122**.

| Date | MGC=F | V26 | Z26 | vol V | vol Z |
|---|---:|---:|---:|---:|---:|
| 2026-09-18 | 4390.70 | 4390.70 | 4424.90 | 35193 | 342294 |
| 2026-09-21 | 4377.10 | 4343.30 | 4377.10 | 26122 | 262030 |

So Tradovate is still on the **October** contract the sim tab shows (`MGCV6`), while Yahoo continuous has **rolled to December**.

## Ruled out / secondary

| Hypothesis | Verdict | Evidence |
|---|---|---|
| Stale Tradovate quote | **No** | Live bid/ask sizes updating (3×6, 1×6, etc.); day change **−43.3 (−0.99%)** on header; earlier extract 04:15 CDT had LAST **4357.7** |
| Timezone misread | **No** | Screenshot axis shows **7:25 pm** chart clock; file mtimes 17:28 UTC = 13:28 EDT = 01:28 HKT — aligns with user obs time |
| GLOBEX vs RTH session gap | **No** | Both feeds updating mid-NY afternoon RTH/GLOBEX overlap; gap is stable ~34 across the day (calendar), not a session artifact |
| Wrong month code on sim | **Confirmed V=Oct** | Tab/header **MGCV6 / E-MICRO GOLD**; CME month code V = October. (One crop OCR said MGCU6; header screenshots and `tradovate-extract.json` consistently **MGCV6**) |

## Session note on box

`/workspace/reports/yw-tradovate-session/2026-09-21.json` already recorded the mismatch and an intentional skip:

- Yahoo MGC=F **4383.4** vs Tradovate mark **4348.0**
- Reason: levels from Yahoo short not enterable on MGCV6 (mark already through Yahoo T1; SL risk vs $100 kill)

No dedicated memory note on the feed gap beyond that session JSON and screenshots.

## Impact on MGC yfinance backtest validity for Tradovate sim

| Use case | Valid? | Why |
|---|---|---|
| Historical pattern / structure / ORB on `MGC=F` **before 2026-09-21** | **Mostly yes** (direction & shape) | Continuous was tracking **V** (same as MGCV6) for the sampled days through Sep 18 |
| Mapping **absolute Yahoo levels** (entry/SL/TP prices) onto Tradovate **MGCV6** **on/after Sep 21 roll** | **No** | Off by ~**34 pts** (Z vs V). Can invent false “already through T1” / oversized $ risk when marks differ |
| $ / R backtests that assume Yahoo mark = sim mark | **Invalid post-roll** without spread adjustment or same-contract data |
| Going-forward continuous `MGC=F` as proxy for **MGCV6** | **Invalid** until Tradovate also rolls, or you switch symbols |

Point value ($10/pt micro) is fine; the bug is **which contract’s price path**.

## Recommendation for live MGC on Tradovate

1. **Prefer align symbols:** trade **MGCZ6** (Dec) on Tradovate if you want Yahoo `MGC=F` / continuous backtests to map 1:1 — Z also has ~10× V volume on Sep 21 (better liquidity).
2. **Or keep MGCV6** but generate signals from **`MGCV26.CMX`** (or apply a live Z−V spread offset before sending brackets). Do **not** paste raw `MGC=F` prices onto MGCV6.
3. Treat the ~35 pt gap as **calendar spread**, not a data bug; re-check after Tradovate rolls front month.
4. Until aligned: continue **skipping** Yahoo-absolute MGC signals on MGCV6 sim (as in the 2026-09-21 session note).

## Tool data snapshot (no invented prices)

- Pull: 2026-09-22 01:48:34 HKT / 2026-09-21 13:48:34 EDT  
- `MGC=F` fast last **4377.10** (prev **4396.20**, day **4360.60–4422.20**, vol **262030**)  
- `MGCV26.CMX` fast last **4343.30**  
- `MGCZ26.CMX` fast last **4377.00**  
- Obs 5m closes 2026-09-21 13:25 EDT: MGC=F/Z **4384.40**, V **4350.20**  
- Tradovate screenshots ~13:28 EDT: MGCV6 last **4347.4**, bid **4347.5**, ask **4347.9**
