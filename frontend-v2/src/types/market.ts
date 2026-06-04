/**
 * types/market.ts
 * Contrato estricto de tipos para todos los datos de mercado de Iosef Finance.
 * Refleja exactamente el schema de salida de /api/scan del backend.
 */

export type Market = 'nasdaq100' | 'sp500' | 'europe';

export type SignalStatus = 'new' | 'active' | 'weakening' | 'expired' | '';
export type EntryWindowStatus = 'open' | 'narrowing' | 'late' | 'closed' | '';
export type TradeDirection = 'LONG' | 'SHORT' | '';
export type TradeResult = 'win' | 'loss' | 'expired' | '';

export interface TradePlan {
  direction: TradeDirection;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  sl_pct: number;
  tp_pct: number;
  risk_reward: string;
}

export interface TradeTracking {
  trade_status: 'open' | 'closed_win' | 'closed_loss' | 'closed_invalidated' | '';
  trade_opened_at: number | null;
  trade_closed_at: number | null;
  trade_result: TradeResult;
  pnl_percentage: number;
  pnl_absolute: number;
  trade_duration_seconds: number;
  exit_reason: string;
  trading_paused?: boolean;
}

export interface TickerEntry {
  ticker: string;
  price: number;
  change_pct: number;
  rsi: number;
  sma20: number;
  sma50: number;
  sma200: number;
  momentum_1m: number;
  relative_volume: number;
  composite_score: number;
  ma_breakout_signal: boolean;
  signal_strength_score: number;
  signal_strength_source: 'optimized' | 'fallback';
  signal_context_adjustment: number;
  market_context_used: 'bullish' | 'bearish' | 'neutral';
  sector: string | null;
  industry: string | null;

  // Human layer fields
  situation: string;
  human_signal: string;
  confidence_text: string;
  decision_clarity: 'alta' | 'media' | 'baja';
  suggested_action: string;
  holding_period: string;

  // Signal lifecycle
  signal_detected_at: string;
  signal_last_validated_at: string;
  signal_status: SignalStatus;
  signal_age_seconds: number;
  entry_window_status: EntryWindowStatus;
  signal_expired: boolean;
  signal_invalid_reason: string;

  // Trade plan
  trade_plan: TradePlan;
  trade_tracking: TradeTracking;
}

export interface ScanResponse {
  timestamp: string | null;
  market: Market;
  data: TickerEntry[];
  market_breadth?: number;
  alerts?: AlertItem[];
}

export interface AlertItem {
  ticker: string;
  type: string;
  message: string;
  strength: 'high' | 'medium' | 'low';
  color: 'green' | 'red' | 'yellow' | string;
}

export type SortKey = keyof Pick<
  TickerEntry,
  | 'ticker'
  | 'price'
  | 'change_pct'
  | 'rsi'
  | 'composite_score'
  | 'signal_strength_score'
  | 'relative_volume'
  | 'momentum_1m'
>;

export type SortDir = 'asc' | 'desc';
