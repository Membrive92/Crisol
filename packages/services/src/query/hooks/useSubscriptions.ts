import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  Subscription,
  SubscriptionScanResponse,
  SubscriptionStatus,
} from '@finanzas/types';

import {
  type SubscriptionListQuery,
  subscriptionsApi,
} from '../../api/endpoints/subscriptions';
import { queryKeys } from '../keys';

export function useSubscriptions(query: SubscriptionListQuery = {}) {
  return useQuery({
    queryKey: queryKeys.subscriptions.list(query.status),
    queryFn: () => subscriptionsApi.list(query),
    placeholderData: (previous) => previous,
  });
}

export function useSubscription(id: string | undefined) {
  return useQuery({
    queryKey: id ? queryKeys.subscriptions.detail(id) : queryKeys.subscriptions.all,
    queryFn: () => subscriptionsApi.get(id as string),
    enabled: !!id,
  });
}

export function useScanSubscriptions() {
  const queryClient = useQueryClient();
  return useMutation<SubscriptionScanResponse, Error, void>({
    mutationFn: () => subscriptionsApi.scan(),
    onSuccess: () => {
      // Scan puede crear/refrescar todo — invalida el grupo entero.
      void queryClient.invalidateQueries({ queryKey: queryKeys.subscriptions.all });
    },
  });
}

export function useConfirmSubscription() {
  const queryClient = useQueryClient();
  return useMutation<Subscription, Error, string>({
    mutationFn: (id) => subscriptionsApi.confirm(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.subscriptions.all });
    },
  });
}

export function useDismissSubscription() {
  const queryClient = useQueryClient();
  return useMutation<Subscription, Error, string>({
    mutationFn: (id) => subscriptionsApi.dismiss(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.subscriptions.all });
    },
  });
}

export function useDeleteSubscription() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => subscriptionsApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.subscriptions.all });
    },
  });
}

export function usePauseSubscription() {
  const queryClient = useQueryClient();
  return useMutation<Subscription, Error, string>({
    mutationFn: (id) => subscriptionsApi.pause(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.subscriptions.all });
    },
  });
}

export function useResumeSubscription() {
  const queryClient = useQueryClient();
  return useMutation<Subscription, Error, string>({
    mutationFn: (id) => subscriptionsApi.resume(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.subscriptions.all });
    },
  });
}

export function useCancelSubscription() {
  const queryClient = useQueryClient();
  return useMutation<Subscription, Error, string>({
    mutationFn: (id) => subscriptionsApi.cancel(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.subscriptions.all });
    },
  });
}

export type { SubscriptionListQuery, SubscriptionStatus };
