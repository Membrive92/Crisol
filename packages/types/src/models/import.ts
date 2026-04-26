export type ImportJobStatus = 'pending' | 'processing' | 'completed' | 'failed';

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
