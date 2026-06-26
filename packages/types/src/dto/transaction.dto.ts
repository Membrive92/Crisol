import type { Transaction, TransactionSource } from '../models/transaction';

export interface TransactionCreateRequest {
  account_id: string;
  category_id?: string | null;
  amount: string;
  currency?: string;
  occurred_at: string;
  description?: string | null;
  source?: TransactionSource;
}

export interface TransactionUpdateRequest {
  account_id?: string;
  category_id?: string | null;
  amount?: string;
  currency?: string;
  occurred_at?: string;
  description?: string | null;
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
  limit?: number;
  offset?: number;
}

export interface TransactionListResponse {
  items: Transaction[];
  total: number;
  limit: number;
  offset: number;
}
