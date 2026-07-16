// PHASE-37.1 — Serie temporal de patrimonio (activos / pasivos / neto).

export interface PositionPoint {
  /** Primer día del mes (`YYYY-MM-DD`). */
  month: string;
  total_assets: string;
  /** Deuda agregada con signo positivo. */
  total_liabilities: string;
  /** `total_assets − total_liabilities`. */
  net_worth: string;
  /** `true` en la proyección (activos planos + deuda por cuadro teórico). */
  is_projection: boolean;
}

export interface PositionHistoryResponse {
  reference_currency: string;
  points: PositionPoint[];
  /** Neto actual − neto al inicio del rango pedido. `null` si <2 puntos. */
  delta_period: string | null;
  delta_period_pct: number | null;
}

/**
 * PHASE-41 — Patrimonio A FECHA `date_to` + Δ del patrimonio DURANTE el rango,
 * para que las cards de patrimonio del Análisis reflejen el período elegido
 * (no una foto de hoy). Mono-divisa (`reference_currency`).
 */
export interface PositionAsOf {
  reference_currency: string;
  total_assets: string;
  total_liabilities: string;
  net_worth: string;
  delta_assets: string;
  delta_net_worth: string;
}
