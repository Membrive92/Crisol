import type { Receipt, ReceiptExtraction } from '../models/receipt';

export interface ReceiptListQuery {
  limit?: number;
  offset?: number;
}

export interface ReceiptListResponse {
  items: Receipt[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReceiptExtractResponse {
  receipt: Receipt;
  extraction: ReceiptExtraction;
}

export interface ReceiptConfirmRequest {
  amount: string;
  occurred_at: string;
  currency: string;
  description?: string | null;
  category_id?: string | null;
}
