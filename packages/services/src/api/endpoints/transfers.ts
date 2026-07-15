import type {
  MisclassifiedTransfer,
  ReclassifyBulkResponse,
  TransferFromSourceDebtRequest,
  TransferFromSourceRequest,
  TransferLinkRequest,
  TransferPair,
} from '@crisol/types';

import { apiClient } from '../client';

// PHASE-41 (ADR-0005) — retirado el emparejado heurístico (list/candidates/
// match/suspects/mark). La verdad del dinero vive en `transactions.flow`, así
// que esa maquinaria ya no corrige nada. Se conserva: `link`/`unlink`
// (load-bearing del asistente de pago de deuda + deshacer desde la lista),
// `fromSource`/`fromSourceDebt` (convertir tx en transferencia/deuda desde el
// detalle) y `misclassified`/`reclassifyBulk` (data-hygiene en Transacciones).
export const transfersApi = {
  async link(payload: TransferLinkRequest): Promise<TransferPair> {
    const response = await apiClient.post<TransferPair>(
      '/transfers/link',
      payload,
    );
    return response.data;
  },

  async unlink(transactionId: string): Promise<void> {
    await apiClient.delete(`/transfers/${transactionId}`);
  },

  async fromSource(payload: TransferFromSourceRequest): Promise<TransferPair> {
    const response = await apiClient.post<TransferPair>(
      '/transfers/from-source',
      payload,
    );
    return response.data;
  },

  async fromSourceDebt(
    payload: TransferFromSourceDebtRequest,
  ): Promise<TransferPair> {
    const response = await apiClient.post<TransferPair>(
      '/transfers/from-source-debt',
      payload,
    );
    return response.data;
  },

  /** PHASE-31.2 — tx con categoría is_transfer y dirección dudosa. */
  async misclassified(): Promise<MisclassifiedTransfer[]> {
    const response = await apiClient.get<MisclassifiedTransfer[]>(
      '/transfers/misclassified',
    );
    return response.data;
  },

  /** PHASE-31.2 — recategorización en bloque. */
  async reclassifyBulk(payload: {
    transaction_ids: string[];
    target_category_id?: string;
  }): Promise<ReclassifyBulkResponse> {
    const response = await apiClient.post<ReclassifyBulkResponse>(
      '/transfers/reclassify-bulk',
      payload,
    );
    return response.data;
  },
};
