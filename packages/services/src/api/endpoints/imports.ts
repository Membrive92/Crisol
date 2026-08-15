import type {
  ImportColumnMappings,
  ImportJob,
  ImportListQuery,
  ImportListResponse,
  ImportPreviewResponse,
  ImportWarningKey,
} from '@crisol/types';

import { apiClient } from '../client';

export interface CreateImportPayload {
  /** PHASE-19.1: cuenta a la que se imputan las txs del lote. */
  accountId: string;
  file: File;
  columnMappings: ImportColumnMappings;
  currency: string;
  defaultCategoryId?: string | null;
}

export interface PreviewImportPayload extends CreateImportPayload {
  forceVision?: boolean;
}

export const importsApi = {
  async list(query: ImportListQuery = {}): Promise<ImportListResponse> {
    const response = await apiClient.get<ImportListResponse>('/imports', {
      params: query,
    });
    return response.data;
  },

  async get(id: string): Promise<ImportJob> {
    const response = await apiClient.get<ImportJob>(`/imports/${id}`);
    return response.data;
  },

  async create(payload: CreateImportPayload): Promise<ImportJob> {
    const formData = new FormData();
    formData.append('file', payload.file);
    formData.append('column_mappings', JSON.stringify(payload.columnMappings));
    formData.append('account_id', payload.accountId);
    formData.append('currency', payload.currency);
    if (payload.defaultCategoryId) {
      formData.append('default_category_id', payload.defaultCategoryId);
    }

    const response = await apiClient.post<ImportJob>('/imports', formData);
    return response.data;
  },

  async preview(payload: PreviewImportPayload): Promise<ImportPreviewResponse> {
    const formData = new FormData();
    formData.append('file', payload.file);
    formData.append('column_mappings', JSON.stringify(payload.columnMappings));
    formData.append('account_id', payload.accountId);
    formData.append('currency', payload.currency);
    if (payload.defaultCategoryId) {
      formData.append('default_category_id', payload.defaultCategoryId);
    }
    if (payload.forceVision) {
      formData.append('force_vision', 'true');
    }

    // El default del cliente axios es 15s. Para `forceVision` la inferencia
    // local con qwen2.5-vl en CPU tarda 3-5 min por página, y procesamos
    // hasta 5 páginas en serie → damos 30 min de holgura. Para CSV/XLSX/
    // heurística PDF basta con 60s (parsing rápido, pero 90 filas +
    // reconcile pueden tardar varios segundos en backend).
    const timeout = payload.forceVision ? 30 * 60 * 1000 : 60 * 1000;

    const response = await apiClient.post<ImportPreviewResponse>(
      '/imports/preview',
      formData,
      { timeout },
    );
    return response.data;
  },

  /**
   * Para un job en PREVIEW, pide al modelo de IA local sugerencias de
   * categoría para los conceptos del banco que aún no tienen
   * sugerencia. Devuelve `{concept_normalizado: category_id | null}`.
   */
  async aiSuggest(jobId: string): Promise<{ suggestions: Record<string, string | null> }> {
    const response = await apiClient.post<{ suggestions: Record<string, string | null> }>(
      `/imports/${jobId}/ai-suggest`,
      undefined,
      // Inferencia local con qwen2.5: subimos timeout a 5 min para
      // tener margen en CPU. La función backend usa 180s de Ollama
      // timeout pero damos holgura para latencias HTTP.
      { timeout: 5 * 60 * 1000 },
    );
    return response.data;
  },

  /**
   * Confirma el preview. `categoryOverrides` mapea concepto del banco
   * → category_id; las filas matching toman esa categoría y la
   * equivalencia se guarda para futuras importaciones.
   */
  async commit(
    jobId: string,
    options: {
      categoryOverrides?: Record<string, string>;
      /**
       * PHASE-47.A — avisos de "esto parece de otra cuenta" que el usuario ha
       * reconocido. Si falta alguno de los emitidos en el preview, el backend
       * responde 409 con los que quedan.
       */
      acknowledgedWarnings?: ImportWarningKey[];
    } = {},
  ): Promise<ImportJob> {
    const body =
      options.categoryOverrides || options.acknowledgedWarnings
        ? {
            category_overrides: options.categoryOverrides ?? {},
            acknowledged_warnings: options.acknowledgedWarnings ?? [],
          }
        : undefined;
    // El commit no llama a IA, solo persiste filas ya parseadas. Pero con
    // 90+ filas + reconcile_with_expected por cada una en serie puede
    // pasar de los 15s default. Subimos a 2 min para tener margen.
    const response = await apiClient.post<ImportJob>(
      `/imports/${jobId}/commit`,
      body,
      { timeout: 2 * 60 * 1000 },
    );
    return response.data;
  },
};
