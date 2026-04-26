import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { ImportJob, ImportListQuery } from '@finanzas/types';

import { importsApi, type CreateImportPayload } from '../../api/endpoints/imports';
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
      void queryClient.invalidateQueries({ queryKey: queryKeys.imports.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    },
  });
}
