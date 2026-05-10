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
