'use client';

import { useState } from 'react';

import { useTransactionAvailablePeriods } from '@crisol/services';
import type { Account, Category, TransactionListQuery } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { FilterIcon, SearchIcon } from '@/components/ui/icons';
import { TimeSelector } from '@/components/ui/time-selector';

// Valor sentinela del <option> "Sin categoría" en el filtro de categoría.
// No colisiona con un `category_id` real (son UUIDs). Mapea a
// `uncategorized: true` en el query.
const CATEGORY_UNCATEGORIZED = '__uncategorized__';

export interface StitchSearchToolbarProps {
  value: TransactionListQuery;
  onChange: (next: TransactionListQuery) => void;
  categories: Category[];
  /** PHASE-19.4: cuentas disponibles para filtrar por imputación. */
  accounts: Account[];
}

/**
 * Toolbar de la página de Transactions: search bar con icono +
 * botones "Filtros" y "Este mes" como toggles. "Filtros" expone un
 * panel desplegable con categoría + rango de fechas. "Este mes" es un
 * shortcut que rellena `date_from`/`date_to` al rango del mes actual.
 */
export function StitchSearchToolbar({
  value,
  onChange,
  categories,
  accounts,
}: StitchSearchToolbarProps) {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const { data: availablePeriods = [] } = useTransactionAvailablePeriods();

  function update<K extends keyof TransactionListQuery>(
    key: K,
    next: TransactionListQuery[K] | '',
  ) {
    onChange({ ...value, [key]: next === '' ? undefined : next, offset: 0 });
  }

  // El filtro de categoría incluye un valor especial "sin categoría":
  // `category_id` y `uncategorized` son excluyentes, así que reconstruimos
  // `value` omitiendo ambos y añadiendo el que toque (evita asignar
  // `undefined` explícito — exactOptionalPropertyTypes).
  function applyCategoryFilter(next: string) {
    const { category_id: _c, uncategorized: _u, ...rest } = value;
    if (next === CATEGORY_UNCATEGORIZED) {
      onChange({ ...rest, uncategorized: true, offset: 0 });
    } else if (next) {
      onChange({ ...rest, category_id: next, offset: 0 });
    } else {
      onChange({ ...rest, offset: 0 });
    }
  }

  function applyTimeRange(range: {
    dateFrom: string | undefined;
    dateTo: string | undefined;
  }) {
    // Reconstruimos `value` omitiendo `date_from`/`date_to` para
    // respetar `exactOptionalPropertyTypes` (no podemos asignar
    // `undefined` explícito a un campo opcional).
    const { date_from: _df, date_to: _dt, ...rest } = value;
    onChange({
      ...rest,
      ...(range.dateFrom ? { date_from: range.dateFrom } : {}),
      ...(range.dateTo ? { date_to: range.dateTo } : {}),
      offset: 0,
    });
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
      <div style={{ display: 'flex', gap: spacing.sm, flexWrap: 'wrap' }}>
        <SearchInput
          value={value.search ?? ''}
          onChange={(v) => update('search', v)}
        />
        <ToolbarButton
          label="Filtros"
          icon={<FilterIcon size={16} />}
          active={filtersOpen}
          onClick={() => setFiltersOpen((v) => !v)}
        />
      </div>

      <TimeSelector
        availablePeriods={availablePeriods}
        value={{ dateFrom: value.date_from, dateTo: value.date_to }}
        onChange={applyTimeRange}
      />

      {filtersOpen ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: spacing.md,
            backgroundColor: colors.surfaceMuted,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            padding: spacing.md,
          }}
        >
          <FilterSelect
            label="Cuenta"
            value={value.account_id ?? ''}
            onChange={(v) => update('account_id', v)}
          >
            <option value="">Todas</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.icon ? `${a.icon} ` : ''}
                {a.name}
              </option>
            ))}
          </FilterSelect>
          <FilterSelect
            label="Categoría"
            value={value.uncategorized ? CATEGORY_UNCATEGORIZED : (value.category_id ?? '')}
            onChange={applyCategoryFilter}
          >
            <option value="">Todas</option>
            <option value={CATEGORY_UNCATEGORIZED}>Sin categoría</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </FilterSelect>
          <FilterDate
            label="Desde"
            value={value.date_from?.slice(0, 10) ?? ''}
            onChange={(v) => update('date_from', v ? `${v}T00:00:00Z` : '')}
          />
          <FilterDate
            label="Hasta"
            value={value.date_to?.slice(0, 10) ?? ''}
            onChange={(v) => update('date_to', v ? `${v}T23:59:59Z` : '')}
          />
        </div>
      ) : null}
    </div>
  );
}

function SearchInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <div style={{ position: 'relative', flex: '1 1 280px' }}>
      <span
        aria-hidden
        style={{
          position: 'absolute',
          left: spacing.sm + 4,
          top: '50%',
          transform: 'translateY(-50%)',
          color: colors.textSubtle,
          display: 'inline-flex',
          pointerEvents: 'none',
        }}
      >
        <SearchIcon size={16} />
      </span>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Buscar transacciones, comercios o importes"
        placeholder="Buscar transacciones, comercios o importes..."
        style={{
          width: '100%',
          padding: `${spacing.sm}px ${spacing.md}px ${spacing.sm}px ${spacing.xl + 4}px`,
          backgroundColor: colors.surface,
          color: colors.text,
          border: `1px solid ${colors.border}`,
          borderRadius: radius.md,
          fontSize: fontSize.sm,
          outline: 'none',
        }}
      />
    </div>
  );
}

function ToolbarButton({
  label,
  icon,
  active,
  onClick,
}: {
  label: string;
  icon: React.ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: spacing.xs,
        padding: `${spacing.sm}px ${spacing.md}px`,
        backgroundColor: active ? colors.primarySoft : colors.surfaceMuted,
        color: active ? colors.primary : colors.textMuted,
        border: `1px solid ${active ? colors.primary : colors.border}`,
        borderRadius: radius.md,
        fontSize: fontSize.sm,
        fontWeight: fontWeight.semibold,
        cursor: 'pointer',
        whiteSpace: 'nowrap',
      }}
    >
      {icon}
      {label}
    </button>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
  children: React.ReactNode;
}) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ fontSize: fontSize.xs, fontWeight: fontWeight.medium, color: colors.textMuted }}>
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          padding: `${spacing.sm}px ${spacing.sm}px`,
          backgroundColor: colors.surface,
          color: colors.text,
          border: `1px solid ${colors.border}`,
          borderRadius: radius.sm,
          fontSize: fontSize.sm,
        }}
      >
        {children}
      </select>
    </label>
  );
}

function FilterDate({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ fontSize: fontSize.xs, fontWeight: fontWeight.medium, color: colors.textMuted }}>
        {label}
      </span>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          padding: `${spacing.sm}px ${spacing.sm}px`,
          backgroundColor: colors.surface,
          color: colors.text,
          border: `1px solid ${colors.border}`,
          borderRadius: radius.sm,
          fontSize: fontSize.sm,
        }}
      />
    </label>
  );
}
