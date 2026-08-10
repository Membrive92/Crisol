import type {
  AmortizationEffect,
  AmortizationRequest,
  FinancingMatch,
  MisclassifiedTransfer,
  ReclassifyBulkResponse,
  TransferFromSourceDebtRequest,
  TransferFromSourceRequest,
  TransferLinkRequest,
  TransferPair,
} from '@crisol/types';

import { AxiosError } from 'axios';

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

  /**
   * PHASE-45 — declara que un cargo del banco amortiza una deuda.
   * Con `dry_run: true` el servidor no escribe nada y devuelve el efecto
   * exacto que tendría, para enseñarlo antes de confirmar.
   */
  async amortize(payload: AmortizationRequest): Promise<AmortizationEffect> {
    const response = await apiClient.post<AmortizationEffect>(
      '/transfers/amortization',
      payload,
    );
    return response.data;
  },

  /**
   * PHASE-45 — el registro de amortización de una tx.
   *
   * `null` cuando no lo tiene: "esta tx no está registrada" es un estado
   * normal de la pantalla, no un error que haya que enseñar. Cualquier otro
   * fallo (403, 500, red) sí se propaga.
   */
  async amortization(transactionId: string): Promise<AmortizationEffect | null> {
    try {
      const response = await apiClient.get<AmortizationEffect>(
        `/transfers/amortization/${transactionId}`,
      );
      return response.data;
    } catch (error) {
      if (error instanceof AxiosError && error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  },

  /** PHASE-45 — deshace el registro: la deuda vuelve a subir. */
  async undoAmortization(transactionId: string): Promise<void> {
    await apiClient.delete(`/transfers/amortization/${transactionId}`);
  },

  /** PHASE-31.2 — tx con categoría is_transfer y dirección dudosa. */
  async misclassified(): Promise<MisclassifiedTransfer[]> {
    const response = await apiClient.get<MisclassifiedTransfer[]>(
      '/transfers/misclassified',
    );
    return response.data;
  },

  /**
   * PHASE-46 — abonos de financiación que encajan con el cuadro de una deuda ya
   * creada. Sólo propone: el enlace lo confirma el usuario con `fromSourceDebt`.
   */
  async financingMatches(): Promise<FinancingMatch[]> {
    const response = await apiClient.get<FinancingMatch[]>(
      '/transfers/financing-matches',
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
