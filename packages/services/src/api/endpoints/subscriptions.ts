import type {
  Subscription,
  SubscriptionScanResponse,
  SubscriptionStatus,
} from '@finanzas/types';

import { apiClient } from '../client';

export interface SubscriptionListQuery {
  status?: SubscriptionStatus;
}

export const subscriptionsApi = {
  async list(query: SubscriptionListQuery = {}): Promise<Subscription[]> {
    const response = await apiClient.get<Subscription[]>('/subscriptions', {
      params: query,
    });
    return response.data;
  },

  async get(id: string): Promise<Subscription> {
    const response = await apiClient.get<Subscription>(`/subscriptions/${id}`);
    return response.data;
  },

  async scan(): Promise<SubscriptionScanResponse> {
    const response = await apiClient.post<SubscriptionScanResponse>(
      '/subscriptions/scan',
    );
    return response.data;
  },

  async confirm(id: string): Promise<Subscription> {
    const response = await apiClient.post<Subscription>(
      `/subscriptions/${id}/confirm`,
    );
    return response.data;
  },

  async dismiss(id: string): Promise<Subscription> {
    const response = await apiClient.post<Subscription>(
      `/subscriptions/${id}/dismiss`,
    );
    return response.data;
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`/subscriptions/${id}`);
  },
};
