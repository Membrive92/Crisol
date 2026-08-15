export type ImportJobStatus =
  | 'pending'
  | 'processing'
  | 'preview'
  | 'completed'
  | 'failed';

export type ImportSource =
  | 'pdfplumber_smart'
  | 'pdfplumber_legacy'
  | 'vision'
  | 'csv'
  | 'xlsx'
  | 'xlsx_smart';

export interface ImportPreviewRow {
  amount: string;
  occurred_at: string;
  description: string | null;
  category_name: string | null;
  /**
   * PHASE-39 — saldo de la cuenta tras el movimiento, tal cual viene
   * del fichero (mismo formato original que `amount`). `null` si el
   * fichero no trae columna Saldo o la celda está vacía.
   */
  statement_balance: string | null;
}

export type ImportSuggestionSource = 'saved_mapping' | 'rule' | 'ai';

export interface ImportPreviewBankConceptGroup {
  /** Concepto del banco (sin normalizar — para mostrar al usuario). */
  concept: string;
  /** Cuántas filas tienen este concepto. */
  count: number;
  /**
   * Sugerencia de category_id según prioridad:
   *  1. Equivalencia exacta guardada (`suggestion_source='saved_mapping'`).
   *  2. Regla del usuario que matchea (`suggestion_source='rule'`).
   *  3. Sugerencia IA (`suggestion_source='ai'`, post-/imports/{id}/ai-suggest).
   *  4. `null` si nada matchea — el usuario asigna a mano.
   */
  suggested_category_id: string | null;
  suggestion_source: ImportSuggestionSource | null;
  /**
   * `true` cuando las filas del grupo resuelven a categorías DIFERENTES
   * por reglas (la description de cada fila matchea reglas distintas).
   * En ese caso `suggested_category_id` es null y la UI debe avisar al
   * usuario que las reglas se aplican fila a fila al confirmar.
   */
  has_mixed_rule_matches: boolean;
}

/**
 * PHASE-47.A — Claves de los avisos "este fichero puede no ser de esta cuenta".
 * Sincronizado con `ImportWarningKey` del backend.
 */
export type ImportWarningKey =
  | 'header_matches_other_account'
  | 'rows_exist_in_other_account';

/**
 * PHASE-47.A — Aviso BLOQUEABLE, no prohibición: el usuario puede tener razón.
 * Confirmar exige devolver su `key` en `acknowledged_warnings`, o el backend
 * responde 409.
 */
export interface ImportWarning {
  key: ImportWarningKey;
  /** Frase en español con los números dentro. */
  message: string;
  account_id: string | null;
  account_name: string | null;
  matched_rows: number;
  total_rows: number;
}

export interface ImportPreviewResponse {
  job_id: string;
  source: ImportSource;
  total_rows: number;
  rows: ImportPreviewRow[];
  bank_concept_groups: ImportPreviewBankConceptGroup[];
  error_sample?: string[];
  /** PHASE-47.A — vacío en el caso normal. */
  warnings?: ImportWarning[];
}

export interface BankCategoryMapping {
  id: string;
  user_id: string;
  bank_concept: string;
  category_id: string;
  created_at: string;
  updated_at: string;
}

export interface ImportErrorEntry {
  row: number;
  error: string;
  /**
   * P5 (transfers-ux): `true` cuando la fila SÍ se importó pero requiere
   * revisión manual (p. ej. una transferencia cuya dirección no se pudo
   * determinar). No es un error: la UI la muestra en el canal "A revisar",
   * no en "Errores", y no cuenta en `rows_failed`.
   */
  review?: boolean;
}

export interface ImportColumnMappings {
  amount: string;
  occurred_at: string;
  description?: string | null;
  category_name?: string | null;
  /** PHASE-39 — nombre de la columna del fichero con el saldo tras cada movimiento. */
  statement_balance?: string | null;
}

export interface ImportJob {
  id: string;
  user_id: string;
  /** PHASE-19.1: cuenta a la que se imputaron las txs del lote. */
  account_id: string | null;
  filename: string;
  status: ImportJobStatus;
  rows_total: number;
  rows_ok: number;
  rows_failed: number;
  rows_skipped: number;
  column_mappings: Record<string, unknown>;
  error_log: ImportErrorEntry[];
  /**
   * PHASE-39 — saldo del extracto anclado al confirmar, si el fichero
   * traía columna Saldo. `balance` es un string decimal (p. ej.
   * "5817.76") y `date` una fecha ISO `YYYY-MM-DD`. Solo viene en la
   * respuesta del commit y en el GET de un job concreto.
   */
  balance_anchor?: { balance: string; date: string } | null;
  created_at: string;
  updated_at: string;
}
