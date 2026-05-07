/**
 * Tipos del módulo fixed_expenses (PHASE-13.1 backend, PHASE-13.2
 * frontend; renombrado en PHASE-17.1).
 *
 * Importes vienen como `string` (Decimal serializado). Fechas
 * `next_due`/`first_seen_at`/`last_seen_at` son ISO date `YYYY-MM-DD`
 * (no timestamp completo).
 */

export type FixedExpenseStatus =
  | 'pending'
  | 'confirmed'
  | 'paused'
  | 'cancelled'
  | 'dismissed';

export interface FixedExpense {
  id: string;
  user_id: string;
  /** Normalizado (lowercase + alfanumérico, máx 30 chars). Forma parte de la huella. */
  merchant: string;
  /** Sample legible para mostrar al usuario. */
  raw_description: string;
  amount: string;
  currency: string;
  /** Canónico: 7/14/30/90/180/365. */
  cadence_days: number;
  /** ISO date `YYYY-MM-DD`. */
  next_due: string;
  status: FixedExpenseStatus;
  category_id: string | null;
  /** ISO date `YYYY-MM-DD`. */
  first_seen_at: string;
  /** ISO date `YYYY-MM-DD`. */
  last_seen_at: string;
  occurrence_count: number;
  /** 0..1. Frontend lo presenta como `Math.round(confidence * 100)%`. */
  confidence: number;
  created_at: string;
  updated_at: string;
}

export interface FixedExpenseScanResponse {
  created: number;
  updated: number;
  total_active_after: number;
}
