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

export interface ImportPreviewResponse {
  job_id: string;
  source: ImportSource;
  total_rows: number;
  rows: ImportPreviewRow[];
  bank_concept_groups: ImportPreviewBankConceptGroup[];
  error_sample?: string[];
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
}

export interface ImportColumnMappings {
  amount: string;
  occurred_at: string;
  description?: string | null;
  category_name?: string | null;
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
  created_at: string;
  updated_at: string;
}
