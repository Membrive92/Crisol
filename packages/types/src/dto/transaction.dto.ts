import type { Transaction, TransactionFlow, TransactionSource } from '../models/transaction';

export interface TransactionCreateRequest {
  account_id: string;
  category_id?: string | null;
  amount: string;
  currency?: string;
  occurred_at: string;
  description?: string | null;
  source?: TransactionSource;
  /** PHASE-34: dirección/transfer-ness explícita. Si se omite, el backend la
   * deriva de la categoría (puente de transición). */
  flow?: TransactionFlow | null;
  /** PHASE-37.3: override estructural/puntual. Normalmente se omite al crear
   * (deja que decida la heurística). */
  is_exceptional?: boolean | null;
}

export interface TransactionUpdateRequest {
  account_id?: string;
  category_id?: string | null;
  amount?: string;
  currency?: string;
  occurred_at?: string;
  description?: string | null;
  flow?: TransactionFlow | null;
  /**
   * PHASE-37.3 — override tri-estado. Enviar `null` EXPLÍCITO resetea a
   * automático (el backend usa `exclude_unset`, así que omitirlo no lo
   * toca). `true` = puntual, `false` = estructural.
   */
  is_exceptional?: boolean | null;
}

export interface TransactionListQuery {
  account_id?: string;
  category_id?: string;
  /**
   * Filtra las transacciones SIN categoría (`category_id IS NULL`).
   * Sostiene el atajo "Ver y categorizar" del banner. Excluyente con
   * `category_id`: si se pasa `uncategorized`, el backend ignora
   * `category_id`. No combinar con acciones bulk (el backend de borrado/
   * reasignación NO aplica este filtro; la UI deshabilita esos botones
   * mientras está activo).
   */
  uncategorized?: boolean;
  date_from?: string;
  date_to?: string;
  search?: string;
  /**
   * Cuando se pasa, el backend devuelve `converted_amount` +
   * `converted_currency` por fila (PHASE-8.4). La UI puede pintar el
   * equivalente en moneda activa sin lanzar fetches por fecha.
   */
  target_currency?: string;
  /**
   * Restringe a transacciones de deuda (rol de categoría `DEBT_PAYMENT`/
   * `DEBT_INTEREST` o pata de par de conversión a deuda). La card de deuda del
   * análisis lo usa para traer TODOS los movimientos de deuda del periodo sin
   * que el tope de `limit` deje fuera los antiguos.
   */
  debt_only?: boolean;
  limit?: number;
  offset?: number;
}

export interface TransactionListResponse {
  items: Transaction[];
  total: number;
  limit: number;
  offset: number;
}
