import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  ImportJob,
  ImportListQuery,
  ImportPreviewResponse,
} from '@crisol/types';

import {
  importsApi,
  type CreateImportPayload,
  type PreviewImportPayload,
} from '../../api/endpoints/imports';
import { invalidateTransactionSideEffects } from '../invalidate';
import { queryKeys } from '../keys';

export function useImports(query: ImportListQuery = {}) {
  return useQuery({
    queryKey: queryKeys.imports.list(query),
    queryFn: () => importsApi.list(query),
    placeholderData: (previous) => previous,
  });
}

export function useImport(id: string | undefined) {
  return useQuery({
    queryKey: id ? queryKeys.imports.detail(id) : queryKeys.imports.all,
    queryFn: () => importsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateImport() {
  const queryClient = useQueryClient();
  return useMutation<ImportJob, Error, CreateImportPayload>({
    mutationFn: (payload) => importsApi.create(payload),
    onSuccess: () => {
      // El job en sí (imports.all). AUDIT-2026-06: si el create
      // persiste filas, mueve tx/dashboard/budgets/saldos/deuda igual
      // que cualquier alta de tx — antes faltaban budgets/accounts/debt.
      void queryClient.invalidateQueries({ queryKey: queryKeys.imports.all });
      invalidateTransactionSideEffects(queryClient);
    },
  });
}

export function usePreviewImport() {
  return useMutation<ImportPreviewResponse, Error, PreviewImportPayload>({
    mutationFn: (payload) => importsApi.preview(payload),
  });
}

/**
 * Pide al modelo de IA local sugerencias de categoría para los
 * conceptos sin sugerencia previa de un job en PREVIEW.
 */
export function useAiSuggestImport() {
  return useMutation<
    { suggestions: Record<string, string | null> },
    Error,
    string
  >({
    mutationFn: (jobId) => importsApi.aiSuggest(jobId),
  });
}

export interface CommitImportPayload {
  jobId: string;
  /**
   * Mapping `concepto banco → category_id` para autoasignar
   * categorías a las filas y guardar la equivalencia para futuras
   * importaciones (PHASE-19).
   */
  categoryOverrides?: Record<string, string>;
}

export function useCommitImport() {
  const queryClient = useQueryClient();
  return useMutation<ImportJob, Error, CommitImportPayload>({
    mutationFn: ({ jobId, categoryOverrides }) =>
      importsApi.commit(
        jobId,
        categoryOverrides ? { categoryOverrides } : {},
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.imports.all });
      // AUDIT-2026-06: commit persiste las tx del job → mismo blast
      // radius que un alta de tx. Antes faltaban budgets/accounts/debt
      // (saldos y lista de deuda quedaban stale tras importar).
      invalidateTransactionSideEffects(queryClient);
      // El commit puede haber creado equivalencias nuevas vía
      // `category_overrides` → invalida bank-mappings.
      void queryClient.invalidateQueries({ queryKey: queryKeys.bankMappings.all });
    },
  });
}
