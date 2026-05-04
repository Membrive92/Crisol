export type TransactionSource = 'manual' | 'import' | 'receipt';

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
   * Importe convertido a `converted_currency` con la tasa del día de
   * `occurred_at` (PHASE-8.4). Sólo viene cuando el caller pasa
   * `?target_currency=` al listado; en lecturas individuales y modo
   * legacy es `null`. `null` también si la subquery de la tasa no
   * encontró fila dentro de la ventana de fallback.
   */
  converted_amount: string | null;
  converted_currency: string | null;
}
