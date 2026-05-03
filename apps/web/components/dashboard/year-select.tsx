'use client';

import type { ChangeEvent } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

export interface YearSelectProps {
  value: number;
  onChange: (year: number) => void;
}

/**
 * Selector de año para el Dashboard. La moneda se gestiona globalmente
 * desde el header (ver `CurrencyMenu`), así que aquí sólo queda el año.
 */
export function YearSelect({ value, onChange }: YearSelectProps) {
  const current = new Date().getFullYear();
  const options = Array.from({ length: 5 }, (_, i) => current - i);

  function handleChange(e: ChangeEvent<HTMLSelectElement>) {
    onChange(Number(e.target.value));
  }

  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
      <span
        style={{
          fontSize: fontSize.xs,
          fontWeight: fontWeight.medium,
          color: colors.textMuted,
        }}
      >
        Año
      </span>
      <select
        value={value}
        onChange={handleChange}
        style={{
          padding: `${spacing.sm}px ${spacing.md}px`,
          borderRadius: radius.md,
          border: `1px solid ${colors.border}`,
          backgroundColor: colors.surface,
          fontSize: fontSize.sm,
          color: colors.text,
          minWidth: 120,
        }}
      >
        {options.map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </select>
    </label>
  );
}
