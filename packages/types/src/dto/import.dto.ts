import type { ImportJob } from '../models/import';

export interface ImportListQuery {
  limit?: number;
  offset?: number;
}

export interface ImportListResponse {
  items: ImportJob[];
  total: number;
  limit: number;
  offset: number;
}
