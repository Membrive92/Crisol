export type TransactionSource = 'manual' | 'import' | 'receipt' | 'expected';

/**
 * PHASE-34 (ADR-0004): dirección + naturaleza del movimiento — fuente de
 * verdad del dinero a nivel de transacción.
 * - `IN` / `OUT`: entra / sale → ingreso / gasto del mes.
 * - `TRANSFER_IN` / `TRANSFER_OUT`: movimiento interno entre cuentas propias
 *   (incluye pago de tarjeta) → neutro, fuera del cashflow.
 * El saldo se deriva de `flow` + naturaleza de la cuenta; la categoría es
 * descriptiva. `null` = sin clasificar (contribuye 0).
 */
export type TransactionFlow = 'IN' | 'OUT' | 'TRANSFER_IN' | 'TRANSFER_OUT';

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
  /** PHASE-19.1: cuenta a la que pertenece la transacción. Obligatorio. */
  account_id: string;
  category_id: string | null;
  /**
   * PHASE-19.3: si esta tx forma parte de una transferencia interna,
   * apunta a la otra mitad del par. NULL en movimientos normales.
   * Las parejas se excluyen de cashflow / tasa de ahorro / donut /
   * presupuestos pero SÍ afectan al saldo individual de su cuenta.
   */
  transfer_pair_id: string | null;
  amount: string;
  currency: string;
  occurred_at: string;
  description: string | null;
  source: TransactionSource;
  /**
   * PHASE-34: fuente de verdad de la dirección del dinero. La UI pinta el
   * signo/color y clasifica gasto/ingreso/transferencia desde aquí (no desde
   * `category.kind`). `null` en datos heredados sin migrar.
   */
  flow: TransactionFlow | null;
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
   * `true` cuando la transacción es una pata de un par de conversión a
   * deuda (activo↔pasivo): la lista la marca con el badge "Deuda" (en
   * vez de "Transferencia") y pinta el importe en neutro — coherente con
   * el fix activo-fantasma, donde la pata-activo aporta 0 al patrimonio.
   * Sólo el endpoint de listado lo computa; en lecturas individuales y
   * en POST/PUT es `false`.
   */
  is_debt_pair: boolean;
  /**
   * PHASE-37.3 — override de la clasificación estructural/puntual del
   * gasto (tri-estado). `null` = automático (decide la heurística de
   * recurrencia), `true` = puntual (one-off), `false` = estructural. El
   * detalle de la tx pinta el toggle "Gasto puntual" desde aquí.
   */
  is_exceptional?: boolean | null;
  /**
   * Alert proactiva (PHASE-14.5). Sólo presente en la respuesta del
   * POST /transactions cuando la nueva tx empuja la categoría a
   * warning/over. `null` siempre en lecturas y cuando no aplica.
   */
  budget_alert?: BudgetAlert | null;
}
