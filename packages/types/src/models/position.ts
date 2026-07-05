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
