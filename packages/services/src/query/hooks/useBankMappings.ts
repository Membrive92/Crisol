import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { BankCategoryMapping } from '@crisol/types';

import {
  bankMappingsApi,
  type BankMappingUpsertPayload,
} from '../../api/endpoints/bank-mappings';
import { queryKeys } from '../keys';

export function useBankMappings() {
  return useQuery({
    queryKey: queryKeys.bankMappings.all,
    queryFn: () => bankMappingsApi.list(),
    placeholderData: (previous) => previous,
  });
}

export function useUpsertBankMapping() {
  const queryClient = useQueryClient();
  return useMutation<BankCategoryMapping, Error, BankMappingUpsertPayload>({
    mutationFn: (payload) => bankMappingsApi.upsert(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.bankMappings.all,
      });
    },
  });
}

export function useDeleteBankMapping() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => bankMappingsApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.bankMappings.all,
      });
    },
  });
}
