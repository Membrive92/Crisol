'use client';

import { useCategories } from '@finanzas/services';
import type { TransactionListQuery } from '@finanzas/types';
import { colors, spacing } from '@finanzas/ui';

import { Select, TextInput } from '../ui/field';

export interface TransactionFiltersProps {
  value: TransactionListQuery;
  onChange: (next: TransactionListQuery) => void;
}

export function TransactionFilters({ value, onChange }: TransactionFiltersProps) {
  const { data: categories } = useCategories();

  function update<K extends keyof TransactionListQuery>(
    key: K,
    next: TransactionListQuery[K] | '',
  ) {
    const merged = { ...value, [key]: next === '' ? undefined : next };
    onChange({ ...merged, offset: 0 });
  }

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: spacing.md,
        padding: spacing.md,
        backgroundColor: colors.surfaceMuted,
        borderRadius: 8,
        marginBottom: spacing.lg,
      }}
    >
      <TextInput
        label="Buscar"
        type="search"
        placeholder="Descripción…"
        value={value.search ?? ''}
        onChange={(e) => update('search', e.target.value)}
      />
      <Select
        label="Categoría"
        value={value.category_id ?? ''}
        onChange={(e) => update('category_id', e.target.value)}
      >
        <option value="">Todas</option>
        {(categories ?? []).map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </Select>
      <TextInput
        label="Desde"
        type="date"
        value={value.date_from?.slice(0, 10) ?? ''}
        onChange={(e) => update('date_from', e.target.value ? `${e.target.value}T00:00:00Z` : '')}
      />
      <TextInput
        label="Hasta"
        type="date"
        value={value.date_to?.slice(0, 10) ?? ''}
        onChange={(e) => update('date_to', e.target.value ? `${e.target.value}T23:59:59Z` : '')}
      />
    </div>
  );
}
