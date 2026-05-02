export type ReceiptStatus = 'pending' | 'confirmed' | 'rejected';

export interface ReceiptLineItem {
  description: string;
  quantity: string | null;
  unit_price: string | null;
  total: string;
}

export interface ReceiptExtraction {
  merchant: string | null;
  occurred_at: string | null;
  currency: string;
  // `total` puede venir null cuando el modelo no lo lee. El form de
  // confirmación pide al usuario que rellene `amount` antes de persistir.
  total: string | null;
  tax: string | null;
  line_items: ReceiptLineItem[];
  raw_text: string | null;
}

export interface Receipt {
  id: string;
  user_id: string;
  status: ReceiptStatus;
  blob_key: string;
  content_type: string;
  extraction: ReceiptExtraction | Record<string, unknown>;
  transaction_id: string | null;
  created_at: string;
  updated_at: string;
}
