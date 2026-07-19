import type {
  CategoryKind,
  CategoryRole,
  ExpenseNature,
} from '../models/category';

export interface CategoryCreateRequest {
  name: string;
  icon?: string | null;
  color?: string | null;
  kind: CategoryKind;
  /** PHASE-23.1: marca la categoría como transferencia interna. */
  is_transfer?: boolean;
  /**
   * PHASE-30.1: rol semántico. Si se omite el backend asume `GENERIC`;
   * si se omite y `is_transfer` es true, el backend lo fuerza a
   * `TRANSFER`.
   */
  role?: CategoryRole;
  /** PHASE-43.2: override estructural/puntual. Default `auto` (heurística). */
  expense_nature?: ExpenseNature;
}

export interface CategoryUpdateRequest {
  name?: string;
  icon?: string | null;
  color?: string | null;
  kind?: CategoryKind;
  is_transfer?: boolean;
  role?: CategoryRole;
  expense_nature?: ExpenseNature;
}
