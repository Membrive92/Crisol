import type { CategoryKind } from '../models/category';

export interface CategoryCreateRequest {
  name: string;
  icon?: string | null;
  color?: string | null;
  kind: CategoryKind;
  /** PHASE-23.1: marca la categoría como transferencia interna. */
  is_transfer?: boolean;
}

export interface CategoryUpdateRequest {
  name?: string;
  icon?: string | null;
  color?: string | null;
  kind?: CategoryKind;
  is_transfer?: boolean;
}
