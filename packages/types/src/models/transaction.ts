export type TransactionSource = 'manual' | 'import' | 'receipt';

export interface Transaction {
  id: string;
  user_id: string;
  category_id: string | null;
  amount: string;
  currency: string;
  occurred_at: string;
  description: string | null;
  source: TransactionSource;
  receipt_id: string | null;
  created_at: string;
  updated_at: string;
}
