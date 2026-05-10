import type {
  Account,
  AccountBalancesResponse,
  AccountCreateRequest,
  AccountUpdateRequest,
} from '@finanzas/types';

import { apiClient } from '../client';

export interface AccountListQuery {
  /** Si `true`, incluye cuentas archivadas. Default `false`. */
  include_archived?: boolean;
}

export const accountsApi = {
  async list(query: AccountListQuery = {}): Promise<Account[]> {
    const response = await apiClient.get<Account[]>('/accounts', {
      params: query,
    });
    return response.data;
  },

  async balances(): Promise<AccountBalancesResponse> {
    const response = await apiClient.get<AccountBalancesResponse>(
      '/accounts/balances',
    );
    return response.data;
  },

  async get(id: string): Promise<Account> {
    const response = await apiClient.get<Account>(`/accounts/${id}`);
    return response.data;
  },

  async create(data: AccountCreateRequest): Promise<Account> {
    const response = await apiClient.post<Account>('/accounts', data);
    return response.data;
  },

  async update(id: string, data: AccountUpdateRequest): Promise<Account> {
    const response = await apiClient.put<Account>(`/accounts/${id}`, data);
    return response.data;
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`/accounts/${id}`);
  },
};
