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
