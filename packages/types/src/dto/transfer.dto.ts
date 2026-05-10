export interface TransferLinkRequest {
  out_transaction_id: string;
  in_transaction_id: string;
}

export interface TransferMatchOptions {
  /** Tolerancia (en días) entre `occurred_at` de salida y entrada. 0..14. */
  window_days?: number;
}
