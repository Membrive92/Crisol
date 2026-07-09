// PHASE-37.3 — Query del endpoint de estructura de gasto.

export interface ExpenseStructureQuery {
  /** Modo legacy: filtra por esta divisa y agrega crudo. */
  currency?: string;
  /** Modo conversión: convierte cada tx por fecha y agrega (PHASE-8.3). */
  target_currency?: string;
  date_from?: string;
  date_to?: string;
}

// PHASE-37.4 — Query del month-outlook (sin rango: siempre el mes en curso).
export interface MonthOutlookQuery {
  currency?: string;
  target_currency?: string;
}
