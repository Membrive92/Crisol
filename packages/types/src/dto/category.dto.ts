import type { CategoryKind, CategoryRole } from '../models/category';

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
}

export interface CategoryUpdateRequest {
  name?: string;
  icon?: string | null;
  color?: string | null;
  kind?: CategoryKind;
  is_transfer?: boolean;
  role?: CategoryRole;
}
