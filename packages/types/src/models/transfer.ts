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
}

/**
 * Sugerencia del matcher heurístico — todavía no escrito en BD.
 * El usuario debe confirmar (vía POST /transfers/link) o ignorar.
 */
export interface TransferCandidate {
  out_transaction_id: string;
  in_transaction_id: string;
  amount: string;
  currency: string;
  out_account_id: string;
  in_account_id: string;
  out_occurred_at: string;
  in_occurred_at: string;
  delta_days: number;
}

export interface TransferMatchResponse {
  /** Pares emparejados automáticamente por el matcher (sin ambigüedad). */
  linked_count: number;
  /**
   * Candidatos ambiguos que el usuario debe resolver — varios
   * importes coincidentes entre las mismas cuentas.
   */
  pending_candidates: TransferCandidate[];
}
