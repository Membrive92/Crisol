export type TransactionSource = 'manual' | 'import' | 'receipt' | 'expected';

/**
 * Alert proactiva de presupuesto que viene en la respuesta del POST
 * /transactions cuando la nueva tx empuja la categoría afectada (o
 * el budget global) a `warning|over` (PHASE-14.5).
 *
 * Sólo presente en `Transaction.budget_alert` cuando el endpoint POST
 * la emite. Lecturas (list, get, put) lo dejan en `null`.
 */
export interface BudgetAlert {
  budget_id: string;
  category_id: string | null;
  status: 'warning' | 'over';
  percent_used: number;
  spent_this_month: string;
  amount: string;
  currency: string;
  /** Mensaje legible listo para toast: "Comida está al 85% del presupuesto." */
  next_due_label: string;
}

export interface Transaction {
  id: string;
  user_id: string;
  category_id: string | null;
  amount: string;
  currency: string;
  occurred_at: string;
  description: string | null;
  source: TransactionSource;
  receipt_id: string | null;
  created_at: string;
  updated_at: string;
  /**
   * Cuándo se soft-deleted (PHASE-10.1). `null` en activas. Timestamp
   * en filas que vienen del endpoint `/transactions/trash`. La UI lo
   * usa para pintar "borrada hace X días".
   */
  deleted_at: string | null;
  /**
   * Importe convertido a `converted_currency` con la tasa del día de
   * `occurred_at` (PHASE-8.4). Sólo viene cuando el caller pasa
   * `?target_currency=` al listado; en lecturas individuales y modo
   * legacy es `null`. `null` también si la subquery de la tasa no
   * encontró fila dentro de la ventana de fallback.
   */
  converted_amount: string | null;
  converted_currency: string | null;
  /**
   * Alert proactiva (PHASE-14.5). Sólo presente en la respuesta del
   * POST /transactions cuando la nueva tx empuja la categoría a
   * warning/over. `null` siempre en lecturas y cuando no aplica.
   */
  budget_alert?: BudgetAlert | null;
}
