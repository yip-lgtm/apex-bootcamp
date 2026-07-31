# Apex 50K 交易機械化 Checklist

> 專為 Apex Trader Funding 50K 帳戶設計的機械化執行流程  
> 目標：通過 Evaluation → 穩定出金

---

## Apex 50K 核心參數（必須記住）

| 項目 | 數值 |
|------|------|
| **Profit Target** | $3,000 |
| **Max Drawdown** | $2,000 (Intraday Trail) |
| **Max Contracts** | **2 Micro** |
| **Daily SL Kill-switch** | **$100** |
| **合格獲利日** | 至少 **5 天**（單日淨利 ≥ $250 才算 1 天） |
| **Min Days To Pass** | 5 |
| **Scaling** | Built-in for PA |

### Point Value（最新）

| Symbol | $/point | Contracts |
|--------|---------|-----------|
| MES.F  | $5      | 2         |
| MNQ.F  | $2      | 2         |
| M2K.F  | $5      | 2         |
| MYM.F  | $0.5    | 2         |
| M6E.F  | $12,500 | 2         |
| M6A.F  | $10,000 | 2         |
| MCL.F  | $100    | 1         |
| MBT.F  | $0.1    | 1         |
| MET.F  | $0.1    | 1         |
| MGC.F  | $10     | 2         |
| SIL.F  | $5      | 1         |

---

## 使用方式

1. 每天開盤前打開本 Checklist，按順序逐項執行
2. **紅色分類（Apex風險規則）**是硬性限制，違反即停止當日交易
3. **綠色分類（進場條件）**全部確認才允許下單
4. **橙色分類（策略 Setup）**必須完成左右環境判定 + A/B/C 計分
5. 收盤後必須完成複盤並更新合格獲利日進度

---

## 1. 開盤前準備

- [ ] **檢查當日經濟數據 / High Impact News**  
  確認 FOMC、NFP、CPI、PPI 等高影響事件時間，避開或調整策略。

- [ ] **確定 Weekly Profile / HTF Bias**  
  根據 HTF 蠟燭、IPDA、地利判斷本週偏向（看漲 / 看跌 / 中性）。

- [ ] **確定 Daily Bias & DOL**  
  判斷今日最可能 OLHC 結構，確定 Draw on Liquidity 目標。

- [ ] **確認 Session Killzone 時間**  
  London / NY AM / NY PM Killzone 時間窗口清楚。

---

## 2. Apex 風險規則（硬限制）

- [ ] **Max Contracts ≤ 2 Micro**  
  嚴格限制最多 2 張 Micro 合約（MES / MNQ / M2K 等）。超過即違規。

- [ ] **Daily SL Kill-switch $100**  
  當日淨虧損達到 $100 立即停止交易，強制平倉，不再進場。

- [ ] **確認 Intraday Trail Drawdown 未觸及**  
  Max DD $2,000（Intraday Trail）。實時監控 Equity，遠離 $2k 回撤。

- [ ] **計算合格獲利日進度**  
  至少需要 5 個合格日（單日淨利 ≥ $250 才算 1 天）。記錄當前已達天數。

---

## 3. 進場條件

- [ ] **Narrative 明確**  
  今日故事線清楚（continuation / reversal / range）。無 Narrative 則不交易。

- [ ] **H1 POI 已建立**  
  在 H1 確定 Point of Interest（Order Block / FVG / Breaker 等）。

- [ ] **結合 Session Profile**  
  POI 與當前 Session 結構（Open Drive / Reversal / Range）一致。

- [ ] **LTF Confirmation / Retracement Entry**  
  在 Killzone 內，LTF 出現確認訊號或回撤進場模型才執行。

- [ ] **進場前確認風險回報**  
  單筆風險 ≤ Daily SL 剩餘額度。目標至少 1:2 以上。

---

## 4. 策略 Setup（核心）

### 4.1 左右環境判定

- [ ] **左側：交易範圍環境**  
  確認當前屬於哪一種：
  - **普通(打牌逻辑)**：常規震盪範圍，價格像打牌一樣順序推進
  - **AMD**：Accumulation → Manipulation → Distribution（Power of 3）
  - **SMT**：相關品種出現 Smart Money Divergence 背離
  - **跳水**：價格快速單邊下殺/上衝，明顯流動性獵取
  - **MMXM**：Market Maker Model / X 模型結構出現

- [ ] **右側：蠟燭形成環境**  
  確認當前屬於哪一種：
  - **三驱动**：Three Drives 三推結構
  - **NDOG**：New Day Opening Gap 出現並被使用
  - **SMT**：蠟燭層面出現 SMT Divergence
  - **NWOG**：New Week Opening Gap 出現並被使用
  - **普通(打牌逻辑)**：常規蠟燭形成順序邏輯
  - **套杀**：誘多/誘空後反轉（stop hunt / trap）

- [ ] **左右環境配合檢查**  
  左側交易範圍環境 + 右側蠟燭形成環境 是否形成合理敘事？  
  例如：AMD + 三驱动、SMT + 套杀、NWOG/NDOG + 普通 等。  
  如果左右完全衝突或不搭，則降級或跳過。

### 4.2 A / B / C 計分（主動 + 被動 + 工程 + 預設）

- [ ] **① 主動**  
  主動元素是否存在？

- [ ] **② 被動**  
  被動元素是否存在？

- [ ] **③ 工程**  
  工程元素是否存在？

- [ ] **④ 預設**  
  預設元素是否存在？

### 最終等級判定

| 等級 | 定義 | 執行方式 |
|------|------|----------|
| **A** | **2+2**（主動 + 被動 + 工程 + 預設 全有） | **正常倉位執行** |
| **B** | **2+1 / 1+2**（三個元素） | **減倉 / 更緊 SL** |
| **C** | **1+1**（兩個元素） | **禁止交易** |

- [ ] **最終執行規則確認**  
  A（2+2）→ 正常倉位執行  
  B（2+1 / 1+2）→ 減倉 / 更嚴風險  
  C（1+1）→ **禁止交易**

---

## 5. 持倉管理

- [ ] **使用 Bracket Order**  
  進場同時設置 Stop Loss + Take Profit，不留裸倉。

- [ ] **不移動 Stop 至不利方向**  
  只允許移動 Stop 保護利潤，禁止加大風險。

- [ ] **達到目標或觸及 SL 立即出場**  
  嚴格遵守計劃，不做情緒化加減倉。

---

## 6. 收盤後複盤

- [ ] **記錄交易細節**  
  截圖、進場理由、結果、情緒、是否機械執行全部記錄。

- [ ] **更新 Equity & 合格日計數**  
  更新當日 P&L、累計 Profit、已達合格獲利天數、距離 Target 進度。

- [ ] **檢討是否違反機械化規則**  
  任何偏離 Checklist 的行為必須寫下原因與改進。

---

## 每日執行總結

**今日 Setup 等級**： A / B / C  
**左側環境**： _______________  
**右側環境**： _______________  
**主動 / 被動 / 工程 / 預設**： _ / _ / _ / _  
**是否執行交易**： 是 / 否  
**當日 P&L**： $_______  
**合格日累計**： ___ / 5  
**距離 Target**： $_______

---

*最後更新：2026-07-31*  
*來源：Notion 交易機械化 Checklist + Apex 50K 規則*
