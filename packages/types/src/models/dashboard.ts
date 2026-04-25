import type { CategoryKind } from './category';

export interface DashboardSummary {
  income: string;
  expenses: string;
  balance: string;
  transaction_count: number;
  currency: string;
}

export interface CategoryBreakdownItem {
  category_id: string | null;
  category_name: string;
  category_kind: CategoryKind | null;
  total: string;
  count: number;
}

export interface MonthlyBucket {
  month: string;
  income: string;
  expenses: string;
  balance: string;
}

export interface TopExpenseItem {
  transaction_id: string;
  description: string | null;
  amount: string;
  occurred_at: string;
  category_id: string | null;
  category_name: string | null;
}
