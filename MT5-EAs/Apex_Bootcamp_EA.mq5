//+------------------------------------------------------------------+
//|                                          Apex_Bootcamp_EA.mq5    |
//|                        Apex Bootcamp setup → MT5 mechanical EA   |
//|   Mirrors AUTOMATION backtest: killzone + A/B trade / skip C     |
//+------------------------------------------------------------------+
#property copyright "Apex Bootcamp"
#property link      "https://github.com/yip-lgtm/apex-bootcamp"
#property version   "1.00"
#property strict
#property description "Apex 50K mechanical EA (MNQ/MGC). A+B enter, C skip. Bracket SL+TP. LDLZ+NYKZ."

//--- Risk / Apex hard rules
input double RiskUSD            = 100.0;   // Risk per trade (USD) — Daily kill uses same
input double DailyKillUSD       = 100.0;   // Daily SL kill-switch (USD)
input double TP_MinUSD          = 200.0;   // Min TP reward (USD)
input double TP_MaxUSD          = 500.0;   // Max TP reward (USD)
input double RR_Target          = 3.5;     // Default RR if structure TP out of envelope
input int    MaxOpenTrades      = 1;       // Max concurrent (1 micro policy)
input double FixedLots          = 0.0;     // 0 = auto from RiskUSD; else fixed lots
input int    MagicNumber        = 260901;  // Magic
input int    SlippagePoints     = 30;      // Deviation

//--- Killzones (broker server time + offset → NY local)
input int    BrokerToNYOffsetH  = 0;       // Hours to add to TimeCurrent to get NY local
input bool   UseLDLZ            = true;    // London KZ 02:00–05:00 NY
input int    LDLZ_StartMin      = 120;     // 02:00 = 120
input int    LDLZ_EndMin        = 300;     // 05:00 = 300
input bool   UseNYKZ            = true;    // NY KZ 08:30–11:00 (indices)
input int    NYKZ_StartMin      = 510;     // 08:30 = 510
input int    NYKZ_EndMin        = 660;     // 11:00 = 660

//--- Point value for sizing ($ per 1.0 price move per 1.0 lot of THIS symbol)
// MNQ micro often ~$2 / point / contract; MGC ~$10. Set for the chart symbol.
input double PointValuePerLot   = 2.0;     // USD per 1.0 price unit per 1.0 lot

input bool   TradeLongs         = true;
input bool   TradeShorts        = true;
input bool   FlatBySessionEnd   = true;    // Close at NY 16:00
input int    SessionEndMin      = 960;     // 16:00 NY = 960
input bool   EnableAlerts       = true;
input bool   EnableComments     = true;

datetime g_lastBar = 0;
double   g_dayPnL  = 0;
int      g_dayYMD  = 0;
bool     g_killed  = false;

//+------------------------------------------------------------------+
int OnInit()
{
   if(RiskUSD <= 0 || PointValuePerLot <= 0)
   {
      Print("ERROR: RiskUSD/PointValuePerLot must be > 0");
      return INIT_PARAMETERS_INCORRECT;
   }
   Print("Apex_Bootcamp_EA v1.00 on ", _Symbol,
         " Risk=$", RiskUSD, " Kill=$", DailyKillUSD,
         " PV/lot=", PointValuePerLot);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { Comment(""); }

void OnTick()
{
   UpdateDayState();
   if(FlatBySessionEnd && InFlatWindow()) CloseAllMagic();

   datetime bar = iTime(_Symbol, PERIOD_M5, 1);
   if(bar == 0) return;
   bool newBar = (bar != g_lastBar);
   if(newBar) g_lastBar = bar;

   if(EnableComments) DrawStatus();

   if(g_killed) return;
   if(!newBar) return;
   if(CountOpen() >= MaxOpenTrades) return;
   if(!InKillzone()) return;

   string pattern = "";
   int bias = DetectTrigger(pattern); // +1 long, -1 short, 0 none
   if(bias == 0) return;
   if(bias > 0 && !TradeLongs) return;
   if(bias < 0 && !TradeShorts) return;

   string grade = "";
   double entry = 0, sl = 0, tp = 0;
   if(!GradeAndPlan(bias, pattern, grade, entry, sl, tp))
   {
      Print("Skip ", pattern, " grade=", grade);
      return;
   }
   if(grade != "A" && grade != "B")
   {
      Print("Skip C: ", pattern);
      return;
   }
   OpenBracket(bias, grade, pattern, entry, sl, tp);
}

//+------------------------------------------------------------------+
void UpdateDayState()
{
   MqlDateTime dt; TimeToStruct(NYNow(), dt);
   int ymd = dt.year * 10000 + dt.mon * 100 + dt.day;
   if(ymd != g_dayYMD)
   {
      g_dayYMD = ymd;
      g_dayPnL = 0;
      g_killed = false;
   }
   // Approximate day PnL from closed deals today with our magic
   g_dayPnL = TodayClosedPnL();
   if(g_dayPnL <= -DailyKillUSD) g_killed = true;
}

datetime NYNow()
{
   return TimeCurrent() + BrokerToNYOffsetH * 3600;
}

int NYMinuteOfDay()
{
   MqlDateTime dt; TimeToStruct(NYNow(), dt);
   return dt.hour * 60 + dt.min;
}

bool InKillzone()
{
   int m = NYMinuteOfDay();
   if(UseLDLZ && m >= LDLZ_StartMin && m < LDLZ_EndMin) return true;
   if(UseNYKZ && m >= NYKZ_StartMin && m < NYKZ_EndMin) return true;
   return false;
}

bool InFlatWindow()
{
   return (NYMinuteOfDay() >= SessionEndMin);
}

string KillzoneName()
{
   int m = NYMinuteOfDay();
   if(UseLDLZ && m >= LDLZ_StartMin && m < LDLZ_EndMin) return "LDLZ";
   if(UseNYKZ && m >= NYKZ_StartMin && m < NYKZ_EndMin) return "NYKZ";
   return "OFF";
}

//+------------------------------------------------------------------+
int DetectTrigger(string &pattern)
{
   pattern = "";
   // Need enough M5 bars in killzone window of *today* — use last 12 M5 bars as proxy
   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, PERIOD_M5, 1, 30, r) < 14) return 0;

   // Filter last bars that fall in killzone by their open time (+offset)
   MqlRates kz[];
   ArrayResize(kz, 0);
   for(int i = 29; i >= 0; i--)
   {
      datetime t = r[i].time + BrokerToNYOffsetH * 3600;
      MqlDateTime dt; TimeToStruct(t, dt);
      int m = dt.hour * 60 + dt.min;
      bool in = (UseLDLZ && m >= LDLZ_StartMin && m < LDLZ_EndMin) ||
                (UseNYKZ && m >= NYKZ_StartMin && m < NYKZ_EndMin);
      if(in)
      {
         int n = ArraySize(kz);
         ArrayResize(kz, n + 1);
         kz[n] = r[i];
      }
   }
   int nkz = ArraySize(kz);
   if(nkz < 6) return 0;

   // Use last 12 of kz (series: last element is newest if we appended chronologically)
   // Rebuild as series newest-first
   MqlRates s[];
   int take = MathMin(12, nkz);
   ArrayResize(s, take);
   for(int i = 0; i < take; i++) s[i] = kz[nkz - 1 - i]; // s[0]=newest

   MqlRates cur = s[0], prev = s[1];
   double body = cur.close - cur.open;
   double upper = cur.high - MathMax(cur.open, cur.close);
   double lower = MathMin(cur.open, cur.close) - cur.low;
   double rng = cur.high - cur.low; if(rng <= 0) rng = _Point;

   double priorHigh = s[1].high, priorLow = s[1].low;
   for(int i = 2; i < take; i++)
   {
      if(s[i].high > priorHigh) priorHigh = s[i].high;
      if(s[i].low < priorLow) priorLow = s[i].low;
   }
   // prior 11 excluding current: use s[1..]
   priorHigh = s[1].high; priorLow = s[1].low;
   for(int i = 2; i < take; i++)
   {
      if(s[i].high > priorHigh) priorHigh = s[i].high;
      if(s[i].low < priorLow) priorLow = s[i].low;
   }

   // Session day high/low from today's M5
   double dayHigh = r[0].high, dayLow = r[0].low;
   MqlDateTime nowdt; TimeToStruct(NYNow(), nowdt);
   for(int i = 0; i < 30; i++)
   {
      MqlDateTime bdt; TimeToStruct(r[i].time + BrokerToNYOffsetH * 3600, bdt);
      if(bdt.day != nowdt.day) continue;
      if(r[i].high > dayHigh) dayHigh = r[i].high;
      if(r[i].low < dayLow) dayLow = r[i].low;
   }

   // 1 bullish engulfing
   if(prev.close < prev.open && cur.close > cur.open && cur.close > prev.open && cur.open < prev.close)
   { pattern = "bullish_engulfing"; return 1; }
   // 2 bearish engulfing
   if(prev.close > prev.open && cur.close < cur.open && cur.close < prev.open && cur.open > prev.close)
   { pattern = "bearish_engulfing"; return -1; }
   // 3 MSS up
   if(cur.close > priorHigh && body > 0) { pattern = "mss_up"; return 1; }
   // 4 MSS down
   if(cur.close < priorLow && body < 0) { pattern = "mss_down"; return -1; }
   // 5/6 sweep reject
   double meanClose = 0;
   for(int i = 1; i < take; i++) meanClose += s[i].close;
   meanClose /= (take - 1);
   if(cur.low < priorLow && cur.close > meanClose && lower > 1.5 * MathAbs(body) && body > 0)
   { pattern = "sweep_reject_long"; return 1; }
   if(cur.high > priorHigh && cur.close < meanClose && upper > 1.5 * MathAbs(body) && body < 0)
   { pattern = "sweep_reject_short"; return -1; }
   // 7/8 pin
   if(lower > 0.55 * rng && MathAbs(body) < 0.30 * rng && body > 0)
   { pattern = "pin_bar_long"; return 1; }
   if(upper > 0.55 * rng && MathAbs(body) < 0.30 * rng && body < 0)
   { pattern = "pin_bar_short"; return -1; }

   // ORB: first 6 kz bars of day
   MqlRates orb[];
   ArrayResize(orb, 0);
   for(int i = nkz - 1; i >= 0 && ArraySize(orb) < 6; i--)
   {
      MqlDateTime bdt; TimeToStruct(kz[i].time + BrokerToNYOffsetH * 3600, bdt);
      if(bdt.day != nowdt.day) continue;
      int n = ArraySize(orb); ArrayResize(orb, n + 1); orb[n] = kz[i];
   }
   if(ArraySize(orb) >= 6)
   {
      double orbH = orb[0].high, orbL = orb[0].low, orbVol = 0;
      for(int i = 0; i < 6; i++)
      {
         if(orb[i].high > orbH) orbH = orb[i].high;
         if(orb[i].low < orbL) orbL = orb[i].low;
         orbVol += (double)orb[i].tick_volume;
      }
      orbVol /= 6.0;
      if(cur.close > orbH && body > 0 && (double)cur.tick_volume > 1.2 * orbVol)
      { pattern = "orb_break_long"; return 1; }
      if(cur.close < orbL && body < 0 && (double)cur.tick_volume > 1.2 * orbVol)
      { pattern = "orb_break_short"; return -1; }
   }
   return 0;
}

//+------------------------------------------------------------------+
bool GradeAndPlan(int bias, const string pattern, string &grade,
                  double &entry, double &sl, double &tp)
{
   entry = (bias > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                      : SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // HTF: D1 MA5/MA10 alignment
   double dclose[];
   ArraySetAsSeries(dclose, true);
   if(CopyClose(_Symbol, PERIOD_D1, 0, 20, dclose) < 15) { grade = "C"; return false; }
   double ma5 = 0, ma10 = 0;
   for(int i = 0; i < 5; i++) ma5 += dclose[i]; ma5 /= 5.0;
   for(int i = 0; i < 10; i++) ma10 += dclose[i]; ma10 /= 10.0;
   double net3 = (dclose[3] != 0.0) ? (dclose[0] - dclose[3]) / dclose[3] : 0.0;
   bool htfBull = (dclose[0] > ma5 && dclose[0] > ma10) || net3 > 0.005;
   bool htfBear = (dclose[0] < ma5 && dclose[0] < ma10) || net3 < -0.005;
   int htf = ((bias > 0 && htfBull) || (bias < 0 && htfBear)) ? 2 : 1;

   int trig = 1;
   if(pattern == "mss_up" || pattern == "mss_down" ||
      pattern == "orb_break_long" || pattern == "orb_break_short" ||
      pattern == "session_high_break" || pattern == "session_low_break")
      trig = 2;

   int score = htf + trig;
   if(score >= 4) grade = "A";
   else if(score == 3) grade = "B";
   else { grade = "C"; return false; }

   // SL distance from $ risk / point value (1 lot)
   double slDist = RiskUSD / PointValuePerLot;
   if(bias > 0) sl = entry - slDist;
   else         sl = entry + slDist;

   // TP from RR / envelope
   double tpReward = MathMin(TP_MaxUSD, MathMax(TP_MinUSD, RR_Target * RiskUSD));
   double tpDist = tpReward / PointValuePerLot;
   if(bias > 0) tp = entry + tpDist;
   else         tp = entry - tpDist;

   double dig = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   entry = NormalizeDouble(entry, (int)dig);
   sl    = NormalizeDouble(sl, (int)dig);
   tp    = NormalizeDouble(tp, (int)dig);
   return true;
}

//+------------------------------------------------------------------+
double LotsForRisk(double slDistPrice)
{
   if(FixedLots > 0) return FixedLots;
   if(slDistPrice <= 0) return 0;
   // risk = lots * PointValuePerLot * slDist
   double lots = RiskUSD / (PointValuePerLot * slDistPrice);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minl = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxl = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0) step = 0.01;
   lots = MathFloor(lots / step) * step;
   lots = MathMax(minl, MathMin(maxl, lots));
   return lots;
}

void OpenBracket(int bias, const string grade, const string pattern,
                 double entry, double sl, double tp)
{
   double slDist = MathAbs(entry - sl);
   double lots = LotsForRisk(slDist);
   if(lots <= 0) { Print("Lots=0"); return; }

   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);
   req.action = TRADE_ACTION_DEAL;
   req.symbol = _Symbol;
   req.volume = lots;
   req.type = (bias > 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   req.price = entry;
   req.sl = sl;
   req.tp = tp;
   req.deviation = SlippagePoints;
   req.magic = MagicNumber;
   req.comment = StringFormat("Apex%s %s %s", grade, pattern, KillzoneName());

   if(!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE)
   {
      Print("OrderSend fail ret=", res.retcode, " err=", GetLastError());
      return;
   }
   Print("OPEN ", grade, " ", (bias > 0 ? "LONG" : "SHORT"),
         " ", pattern, " @", entry, " SL=", sl, " TP=", tp, " lots=", lots);
   if(EnableAlerts)
      Alert(StringFormat("Apex %s %s %s @%s SL=%s TP=%s",
            grade, bias > 0 ? "LONG" : "SHORT", pattern,
            DoubleToString(entry, _Digits),
            DoubleToString(sl, _Digits),
            DoubleToString(tp, _Digits)));
}

//+------------------------------------------------------------------+
int CountOpen()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      n++;
   }
   return n;
}

void CloseAllMagic()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      long type = PositionGetInteger(POSITION_TYPE);
      double vol = PositionGetDouble(POSITION_VOLUME);
      MqlTradeRequest req; MqlTradeResult res;
      ZeroMemory(req); ZeroMemory(res);
      req.action = TRADE_ACTION_DEAL;
      req.position = ticket;
      req.symbol = _Symbol;
      req.volume = vol;
      req.deviation = SlippagePoints;
      req.magic = MagicNumber;
      if(type == POSITION_TYPE_BUY)
      {
         req.type = ORDER_TYPE_SELL;
         req.price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      }
      else
      {
         req.type = ORDER_TYPE_BUY;
         req.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      }
      OrderSend(req, res);
   }
}

double TodayClosedPnL()
{
   double pnl = 0;
   datetime from = NYNow() - 86400; // enough lookback; filter by day
   MqlDateTime nowdt; TimeToStruct(NYNow(), nowdt);
   if(!HistorySelect(from, TimeCurrent())) return 0;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0) continue;
      if((int)HistoryDealGetInteger(d, DEAL_MAGIC) != MagicNumber) continue;
      if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol) continue;
      datetime t = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
      MqlDateTime ddt; TimeToStruct(t + BrokerToNYOffsetH * 3600, ddt);
      if(ddt.year != nowdt.year || ddt.mon != nowdt.mon || ddt.day != nowdt.day) continue;
      long entry = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT && entry != DEAL_ENTRY_OUT_BY) continue;
      pnl += HistoryDealGetDouble(d, DEAL_PROFIT)
           + HistoryDealGetDouble(d, DEAL_SWAP)
           + HistoryDealGetDouble(d, DEAL_COMMISSION);
   }
   return pnl;
}

void DrawStatus()
{
   Comment(StringFormat(
      "Apex_Bootcamp_EA | %s | KZ=%s | dayPnL=$%.0f%s\nRisk=$%.0f Kill=$%.0f | Open=%d",
      _Symbol, KillzoneName(), g_dayPnL, g_killed ? " KILLED" : "",
      RiskUSD, DailyKillUSD, CountOpen()));
}
//+------------------------------------------------------------------+
