import type {
  Account,
  AccountBalancesResponse,
  AccountCreateRequest,
  AccountUpdateRequest,
  AmortizationRow,
  AmortizationSchedule,
  InstallmentBulkPayRequest,
  InstallmentBulkPayResponse,
  InstallmentPayRequest,
  InstallmentUpdateRequest,
} from '@crisol/types';

import { apiClient } from '../client';

export interface AccountListQuery {
  /** Si `true`, incluye cuentas archivadas. Default `false`. */
  include_archived?: boolean;
}

export interface AccountBalancesQuery {
  /**
   * AUDIT-2026-06 — Convierte todos los saldos a esta divisa (tasa de
   * hoy), igual que `/accounts/debt-health`. Sin ella, `/balances`
   * devuelve saldos en su divisa nativa. Imprescindible para que la
   * DebtList y el patrimonio neto del hero respeten el selector del
   * header (PHASE-30.6).
   */
  target_currency?: string;
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

  async balances(
    query: AccountBalancesQuery = {},
  ): Promise<AccountBalancesResponse> {
    const params: Record<string, string> = {};
    if (query.target_currency) params['target_currency'] = query.target_currency;
    const response = await apiClient.get<AccountBalancesResponse>(
      '/accounts/balances',
      { params },
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

  /**
   * AUDIT-2026-07 (H-05): marca las cuotas que un pago de principal cubre.
   * Lo llama el asistente "Pagar cuota" tras crear la transferencia del
   * principal, para que el saldo dirigido por el cuadro (PHASE-36) baje.
   */
  async payInstallments(
    accountId: string,
    payload: InstallmentBulkPayRequest,
  ): Promise<InstallmentBulkPayResponse> {
    const response = await apiClient.post<InstallmentBulkPayResponse>(
      `/accounts/${accountId}/pay-installments`,
      payload,
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

  /**
   * PHASE-34 "Cuadrar saldo": fija el saldo real de una cuenta de activo;
   * el backend ajusta `opening_balance` para que cuadre. `currentBalance` es
   * un string decimal (misma convención que los importes en la API).
   */
  async reconcile(id: string, currentBalance: string): Promise<Account> {
    const response = await apiClient.post<Account>(`/accounts/${id}/reconcile`, {
      current_balance: currentBalance,
    });
    return response.data;
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`/accounts/${id}`);
  },
};
