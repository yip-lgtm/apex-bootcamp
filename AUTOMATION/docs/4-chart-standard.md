# 4-Chart Standard (D / H4 / H1 / 5m)

> Apex 50K v2.6.8+ 官方 chart 標準。所有 daily reminder、forward test、backtest 都跟呢個 layout。
> 貢獻者 (v2.7 PR) 必須對齊呢個格式，唔好自行發明新 panel。

## 為咩係 4 個

由上而下由宏觀到微觀，每個 TF 解決一個特定問題：

| Panel | Timeframe | Period | 解決咩問題                              | 決策角色            |
|-------|-----------|--------|---------------------------------------|---------------------|
| **D**   | 1D        | 90d    | 呢個 ticker 嘅大方向係 LONG 定 SHORT？   | Bias (長線/週線)     |
| **H4**  | 4h        | 30d    | 中段結構 support / resistance 喺邊？     | Structure (結構)     |
| **H1**  | 1h        | 5d     | 今日 / 昨日嘅 killzone 點入？             | Setup (交易 plan)    |
| **5m**  | 5-min     | 2d     | 確切 entry trigger — 邊根 5-min bar 突破？ | Trigger (執行)       |

**哲學**: D = 方向, H4 = 結構, H1 = 計劃, 5m = 扣板機。

四個 panel 缺一不可：
- 只有 D/H4 → 知方向但唔知幾時入
- 只有 H1/5m → 入場但逆大方向 (自殺)
- 跳咗 H4 → 唔識 respect 中段 S/R
- 跳咗 5m → 結構睇完但 1-2pt 滑點就蝕晒 RR

## 圖表 spec

每個 panel 統一：

### 共用元素
- **底色** `#0d0d12` (dark)
- **文字** `#ccc`
- **網格** `#333` @ 0.2 alpha
- **升燭** `#10d97e`, **跌燭** `#ff4d6d`
- **Volume** 紅綠柱 @ 0.4 alpha
- **Time format** `MM-DD` (D/H4) / `MM-DD HH:MM` (H1) / `MM-DD HH:MM` (5m, 8 ticks)

### Panel 1: D (1D, 90d)
- **Height ratio**: 30%
- **Levels**: PDH / PDL / PDC (灰 `---`)
- **Annotation**: 最新 close 標價 (升綠/跌紅)
- **X-axis**: `MM-DD` 6 ticks

### Panel 2: H4 (4h, 30d)
- **Height ratio**: 20%
- **Levels**: PDH / PDL (黃 `---`, 跨 panel 對齊用)
- **X-axis**: `MM-DD` 6 ticks
- **Data source**: 1h → resample to 4h (`resample("4h").agg(agg)`)

### Panel 3: H1 (1h, 5d)
- **Height ratio**: 16% (candles) + 8% (volume)
- **Levels**: PDH / PDL / PDC / ONH / ONL (藍 `:`)
- **Highlight**: 最後 4-5 bars (今日 session) 用 `axvspan` 黃色
- **X-axis**: `MM-DD` 6 ticks

### Panel 4: 5m (5-min, 2d)
- **Height ratio**: 26%
- **Levels**: PDH / PDL / ONH / ONL (藍 `:`, 標喺最右)
- **Highlight**: 第二半 (今日 bars) 黃色 axvspan
- **Annotation**: 最新 close + " (NOW)" 標籤
- **X-axis**: `MM-DD HH:MM` 8 ticks
- **Data source**: yfinance `period="2d", interval="5m"` (約 400 bars)

## Output

- **File**: `AUTOMATION/reports/daily/{DATE}/{TICKER}_4chart.png`
- **Size**: ~134 KB per chart, 10 tickers ≈ 1.4 MB total
- **Gen time**: ~16s for 10 tickers in parallel (6 workers)
- **Total reminder**: 2443 chars (TG text) + 10 PNG media group

## Implementation

```python
# AUTOMATION/src/chart_gen.py
def make_chart_4panel(ticker, name, df_d, df_h4, df_h1, df_m5, out_path):
    fig = plt.figure(figsize=(13, 13), dpi=110)
    gs = fig.add_gridspec(5, 1, height_ratios=[3, 2, 1.6, 0.8, 2.6], ...)
    ax_d   = fig.add_subplot(gs[0])  # D
    ax_h4  = fig.add_subplot(gs[1])  # H4
    ax_h1  = fig.add_subplot(gs[2])  # H1
    ax_h1v = fig.add_subplot(gs[3])  # H1 volume
    ax_m5  = fig.add_subplot(gs[4])  # 5m
    ...
```

## 點解唔加第 5 個 panel (e.g. 1-min / weekly)?

考慮過但 reject：

- **1-min (M1)**: 太多 noise (4000+ bars for 2d)，LLM 反而 confused。5m 已經夠 trigger precision
- **Weekly (W1)**: 已經包喺 D panel 入面 (D 嘅 90 日 = 13 週 ≈ 1 quarter)
- **Tick (1-tick)**: 唔適用於 swing/scalp 策略，而且 yfinance 唔提供

## 點解唔減到 3 個 panel?

考慮過但 reject：

- **無 5m**: 變返 v2.6.7。問題：H1 入場時機唔夠細，1-2pt slippage 都 miss
- **無 D**: 變返 v2.6.6。問題：HTF bias 唔睇，逆大方向高機會輸
- **無 H4**: 變返 v2.6.5。問題：中段 S/R 唔 respect，stops 容易畀打

## 升級歷史

| Version | Panels | 變化                          |
|---------|--------|------------------------------|
| v2.6.4  | 3      | HTF-D + H4 + H1 (原版)        |
| v2.6.6  | 3      | 加 priority order / 10 charts |
| v2.6.7  | 3      | 加 trade candidate ranking    |
| **v2.6.8**  | **4**      | **加 M5 (5-min) intraday panel** |

## TG caption

```
📊 4-Chart Standard (D / H4 / H1 / 5m)
```

## v2.7 貢獻者 checklist

如果你改動 chart layout，必須：
1. ✋ 開 issue 講明點解加 / 減 panel
2. ✋ 更新本 `4-chart-standard.md`
3. ✋ 同步改 `chart_gen.py` 嘅 `make_chart_4panel()`
4. ✋ 更新 `daily_reminder.py` 嘅 section title + caption
5. ✋ TG message 字數要 ≤ 4096
6. ✋ 10 tickers gen time 要 ≤ 30s (GHA 15min timeout)
7. ✋ Submit PR label `area:charts`

否則 PR 會被 reject。

---

最後更新: 2026-08-11 (v2.6.8)
維護: @yip-lgtm + 皮盤房 bot
