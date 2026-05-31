import type {
  Account,
  AccountBalancesResponse,
  AccountCreateRequest,
  AccountUpdateRequest,
  AmortizationRow,
  AmortizationSchedule,
  InstallmentPayRequest,
  InstallmentUpdateRequest,
} from '@crisol/types';

import { apiClient } from '../client';

export interface AccountListQuery {
  /** Si `true`, incluye cuentas archivadas. Default `false`. */
  include_archived?: boolean;
}

// AUDIT-2026-05: `debtHealth`/`debtHistory` (+ sus query types) se
// movieron a `debtApi` para consolidar el módulo deuda.

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

  async amortizationSchedule(id: string): Promise<AmortizationSchedule> {
    const response = await apiClient.get<AmortizationSchedule>(
      `/accounts/${id}/amortization-schedule`,
    );
    return response.data;
  },

  async regenerateAmortization(id: string): Promise<AmortizationSchedule> {
    const response = await apiClient.post<AmortizationSchedule>(
      `/accounts/${id}/amortization-schedule/regenerate`,
    );
    return response.data;
  },

  async updateInstallment(
    installmentId: string,
    payload: InstallmentUpdateRequest,
  ): Promise<AmortizationRow> {
    const response = await apiClient.patch<AmortizationRow>(
      `/accounts/installments/${installmentId}`,
      payload,
    );
    return response.data;
  },

  async payInstallment(
    installmentId: string,
    payload: InstallmentPayRequest = {},
  ): Promise<AmortizationRow> {
    const response = await apiClient.post<AmortizationRow>(
      `/accounts/installments/${installmentId}/pay`,
      payload,
    );
    return response.data;
  },

  async unpayInstallment(installmentId: string): Promise<AmortizationRow> {
    const response = await apiClient.delete<AmortizationRow>(
      `/accounts/installments/${installmentId}/pay`,
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
