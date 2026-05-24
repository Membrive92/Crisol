export interface TransferLinkRequest {
  out_transaction_id: string;
  in_transaction_id: string;
}

export interface TransferMatchOptions {
  /** Tolerancia (en días) entre `occurred_at` de salida y entrada. 0..14. */
  window_days?: number;
}

/** PHASE-23.1: marcar una tx como transferencia interna (is_transfer). */
export interface TransferMarkRequest {
  transaction_id: string;
}

/**
 * PHASE-23.1: convertir una tx en transferencia interna marcando
 * explícitamente la cuenta **ordenante** (de la que sale el dinero)
 * y la **beneficiaria** (donde entra). La tx origen debe pertenecer
 * a una de las dos; el backend deriva los signos y corrige la
 * categoría del origen al kind correcto.
 */
export interface TransferFromSourceRequest {
  source_transaction_id: string;
  originating_account_id: string;
  beneficiary_account_id: string;
}

/**
 * PHASE-24: datos para crear una cuenta liability al vuelo cuando
 * se convierte una tx en operación financiada. PHASE-24.2: los tres
 * tipos de deuda aceptan apr/term/start (incluyendo credit_card para
 * tarjetas financiadas con plan fijo).
 */
export interface NewLiabilityForDebt {
  name: string;
  type: 'credit_card' | 'loan' | 'mortgage';
  currency?: string;
  color?: string | null;
  icon?: string | null;
  /** TIN anual como decimal (0.0590 = 5.90%). 4 decimales máximo. */
  apr?: string | null;
  /** PHASE-24.2 — TAE anual como decimal, informativa. */
  tae?: string | null;
  term_months?: number | null;
  /** ISO date YYYY-MM-DD. */
  start_date?: string | null;
  /** PHASE-24.3 — Total contractualizado por el banco. */
  total_to_pay?: string | null;
  /** PHASE-24.3 — Primer pago sólo de intereses. */
  interest_only_first_payment?: string | null;
}

/**
 * PHASE-24: convertir una tx en operación financiada. Exactamente
 * uno entre `destination_account_id` (liability existente) y
 * `new_liability` (crear al vuelo) debe venir.
 */
export interface TransferFromSourceDebtRequest {
  source_transaction_id: string;
  destination_account_id?: string;
  new_liability?: NewLiabilityForDebt;
}
