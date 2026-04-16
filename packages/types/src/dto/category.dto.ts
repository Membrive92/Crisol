import type { CategoryKind } from '../models/category';

export interface CategoryCreateRequest {
  name: string;
  icon?: string | null;
  color?: string | null;
  kind: CategoryKind;
}

export interface CategoryUpdateRequest {
  name?: string;
  icon?: string | null;
  color?: string | null;
  kind?: CategoryKind;
}
