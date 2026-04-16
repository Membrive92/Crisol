export type CategoryKind = 'income' | 'expense';

export interface Category {
  id: string;
  user_id: string;
  name: string;
  icon: string | null;
  color: string | null;
  kind: CategoryKind;
  created_at: string;
  updated_at: string;
}
