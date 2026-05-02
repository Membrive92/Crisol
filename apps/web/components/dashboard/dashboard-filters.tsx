'use client';

import type { ChangeEvent } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

export interface DashboardFiltersValue {
  currency: string;
  year: number;
}

export interface DashboardFiltersProps {
  value: DashboardFiltersValue;
  onChange: (next: DashboardFiltersValue) => void;
  /**
   * Lista de monedas con datos reales del usuario. Si está vacía, se
   * cae en `FALLBACK_CURRENCIES` para que el control siga siendo usable
   * (un usuario nuevo aún no tiene transacciones pero quiere elegir).
   */
  currencies?: string[] | undefined;
}

const FALLBACK_CURRENCIES = ['EUR', 'USD'] as const;

function buildYearOptions(): number[] {
  const current = new Date().getFullYear();
  return Array.from({ length: 5 }, (_, i) => current - i);
}

export function DashboardFilters({ value, onChange, currencies }: DashboardFiltersProps) {
  const yearOptions = buildYearOptions();
  const currencyOptions =
    currencies && currencies.length > 0
      ? currencies
      : (FALLBACK_CURRENCIES as readonly string[]);
  // Si la moneda activa no está entre las del usuario, la incluimos al
  // final para no perder selección (caso: cambia al borrar la última
  // transacción de esa moneda).
  const allOptions = currencyOptions.includes(value.currency)
    ? currencyOptions
    : [...currencyOptions, value.currency];

  function handleCurrency(e: ChangeEvent<HTMLSelectElement>) {
    onChange({ ...value, currency: e.target.value });
  }

  function handleYear(e: ChangeEvent<HTMLSelectElement>) {
    onChange({ ...value, year: Number(e.target.value) });
  }

  return (
    <div
      style={{
        display: 'flex',
        gap: spacing.md,
        alignItems: 'flex-end',
        marginBottom: spacing.lg,
        flexWrap: 'wrap',
      }}
    >
      <Field label="Moneda">
        <select value={value.currency} onChange={handleCurrency} style={selectStyle}>
          {allOptions.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Año">
        <select value={value.year} onChange={handleYear} style={selectStyle}>
          {yearOptions.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </Field>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
      <span
        style={{
          fontSize: fontSize.xs,
          fontWeight: fontWeight.medium,
          color: colors.textMuted,
        }}
      >
        {label}
      </span>
      {children}
    </label>
  );
}

const selectStyle: React.CSSProperties = {
  padding: `${spacing.sm}px ${spacing.md}px`,
  borderRadius: radius.md,
  border: `1px solid ${colors.border}`,
  backgroundColor: colors.surface,
  fontSize: fontSize.sm,
  color: colors.text,
  minWidth: 120,
};
