import { useEffect, useState } from 'react';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  Receipt,
  ReceiptConfirmRequest,
  ReceiptExtractResponse,
  ReceiptListQuery,
} from '@crisol/types';

import { receiptsApi } from '../../api/endpoints/receipts';
import { queryKeys } from '../keys';

export function useReceipts(query: ReceiptListQuery = {}) {
  return useQuery({
    queryKey: queryKeys.receipts.list(query),
    queryFn: () => receiptsApi.list(query),
    placeholderData: (previous) => previous,
  });
}

export function useReceipt(id: string | undefined) {
  return useQuery({
    queryKey: id ? queryKeys.receipts.detail(id) : queryKeys.receipts.all,
    queryFn: () => receiptsApi.get(id as string),
    enabled: !!id,
  });
}

export function useExtractReceipt() {
  const queryClient = useQueryClient();
  return useMutation<ReceiptExtractResponse, Error, File>({
    mutationFn: (file) => receiptsApi.extract(file),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.receipts.all });
    },
  });
}

export function useConfirmReceipt(id: string) {
  const queryClient = useQueryClient();
  return useMutation<Receipt, Error, ReceiptConfirmRequest>({
    mutationFn: (payload) => receiptsApi.confirm(id, payload),
    onSuccess: (updated) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.receipts.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      queryClient.setQueryData(queryKeys.receipts.detail(updated.id), updated);
    },
  });
}

export function useRejectReceipt(id: string) {
  const queryClient = useQueryClient();
  return useMutation<Receipt, Error, void>({
    mutationFn: () => receiptsApi.reject(id),
    onSuccess: (updated) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.receipts.all });
      queryClient.setQueryData(queryKeys.receipts.detail(updated.id), updated);
    },
  });
}

/**
 * Descarga el blob del receipt y devuelve un `objectURL` listo para usar
 * como `src` de un `<img>`. Limpia el URL al desmontar o cambiar el id.
 *
 * Se hace fuera de TanStack Query a propósito: el resultado es un recurso
 * con ciclo de vida (URL.createObjectURL/revokeObjectURL) y cachearlo en
 * el query cache complica la liberación de memoria.
 */
export function useReceiptImage(id: string | undefined): {
  url: string | null;
  isLoading: boolean;
  error: Error | null;
} {
  const [url, setUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!id) {
      setUrl(null);
      return;
    }
    let cancelled = false;
    let createdUrl: string | null = null;
    setIsLoading(true);
    setError(null);

    receiptsApi
      .getBlob(id)
      .then((blob) => {
        if (cancelled) return;
        createdUrl = URL.createObjectURL(blob);
        setUrl(createdUrl);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err : new Error('No se pudo cargar la imagen'));
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
      setUrl(null);
    };
  }, [id]);

  return { url, isLoading, error };
}
