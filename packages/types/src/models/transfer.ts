/**
 * Tipos del módulo transfers (PHASE-19.3).
 *
 * Un par de transferencia es la representación de un movimiento
 * interno entre dos cuentas del usuario: una salida (out) en cuenta A
 * + una entrada (in) en cuenta B. Las dos transacciones existen como
 * registros independientes en la tabla `transactions`, vinculados por
 * `transfer_pair_id`.
 */

export interface TransferPair {
  out_transaction_id: string;
  in_transaction_id: string;
  amount: string;
  currency: string;
  out_account_id: string;
  in_account_id: string;
  out_occurred_at: string;
  in_occurred_at: string;
  delta_days: number;
  /**
   * PHASE-34: importe del "cargo espejo" anulado al registrar una operación
   * financiada (el ADEUDO del mismo importe que en el banco la compensa,
   * neto 0). `null`/ausente si no se encontró espejo. La UI lo usa para
   * avisar en el toast que ese cargo se movió a la papelera.
   */
  absorbed_mirror_amount?: string | null;
}

/**
 * PHASE-31.2 — tx con categoría is_transfer cuyo kind no encaja con
 * la dirección que indica la descripción. Candidata a recategorización
 * en bloque desde la UI.
 */
export interface MisclassifiedTransfer {
  transaction_id: string;
  amount: string;
  currency: string;
  account_id: string;
  occurred_at: string;
  description: string | null;
  current_category_id: string;
  current_category_name: string;
  /** `expense` o `income`. */
  current_category_kind: string;
  /** `income` si la descripción es entrante, `expense` si saliente. */
  suggested_kind: string;
}

export interface ReclassifyBulkResponse {
  reclassified: number;
  errors: string[];
}

/**
 * PHASE-46 — un abono de financiación y la deuda a la que parece pertenecer.
 *
 * Cuando el banco aplaza un recibo te abona el importe y nace una deuda: no es
 * un ingreso. La propuesta une las dos mitades reconociéndolas por el CAPITAL
 * del cuadro de amortización, no por la redacción del extracto — que ya ha
 * cambiado dos veces y con ella se coló un ingreso que nadie cobró.
 */
export interface FinancingMatch {
  transaction_id: string;
  description: string | null;
  amount: string;
  currency: string;
  occurred_at: string;
  /** `true` si HOY suma en la gráfica de ingresos: el estado a corregir. */
  counted_as_income: boolean;
  liability_id: string;
  liability_name: string;
  schedule_principal: string;
  /** Por qué se propone, en lenguaje llano, para que la pantalla explique. */
  reason: string;
}

/**
 * PHASE-45 — cómo baja la deuda con una amortización.
 *
 * `schedule`: el pasivo tiene cuadro, así que se marcan cuotas pagadas y la
 * deuda baja por el CAPITAL de esas cuotas (los intereses no amortizan).
 * `movement`: el pasivo no tiene cuadro (tarjeta con saldo arrastrado), así
 * que baja por el movimiento contrario que se crea en la cuenta de deuda.
 */
export type AmortizationMode = 'schedule' | 'movement';

/**
 * PHASE-45 — efecto de una amortización sobre la deuda: el previsto
 * (`dry_run: true`, no ha escrito nada) o el ya aplicado.
 */
export interface AmortizationEffect {
  source_transaction_id: string;
  liability_account_id: string;
  liability_account_name: string;
  amount: string;
  currency: string;
  /** El valor EFECTIVO: lo declarado, o la sugerencia en dry-run. */
  counts_as_expense: boolean;
  suggested_counts_as_expense: boolean;
  /** Por qué el servidor sugiere eso — se pinta junto a la elección. */
  suggestion_reason: string;
  mode: AmortizationMode;
  installments_marked: number;
  /** Capital amortizado de verdad (≠ importe pagado si hay intereses). */
  principal_covered: string;
  /** Sobrante que no llega a completar la siguiente cuota. Igual al importe
   * entero cuando el pago no cubre ninguna: ahí la deuda NO baja. */
  principal_uncovered: string;
  outstanding_before: string;
  outstanding_after: string;
  counterpart_transaction_id?: string | null;
  paired?: boolean;
  dry_run?: boolean;
}
