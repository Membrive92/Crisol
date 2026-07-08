// PHASE-37.3 — Query del endpoint de estructura de gasto.

export interface ExpenseStructureQuery {
  /** Modo legacy: filtra por esta divisa y agrega crudo. */
  currency?: string;
  /** Modo conversión: convierte cada tx por fecha y agrega (PHASE-8.3). */
  target_currency?: string;
  date_from?: string;
  date_to?: string;
}
