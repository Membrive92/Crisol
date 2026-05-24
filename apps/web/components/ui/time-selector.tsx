'use client';

import { useMemo } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

const SPANISH_MONTHS_SHORT = [
  'Ene',
  'Feb',
  'Mar',
  'Abr',
  'May',
  'Jun',
  'Jul',
  'Ago',
  'Sep',
  'Oct',
  'Nov',
  'Dic',
];

export interface TimeSelectorRange {
  dateFrom: string | undefined;
  dateTo: string | undefined;
}

export interface TimeSelectorPeriod {
  year: number;
  /** Meses con datos (1-12). */
  months: number[];
}

export interface TimeSelectorProps {
  availablePeriods: TimeSelectorPeriod[];
  value: TimeSelectorRange;
  onChange: (next: TimeSelectorRange) => void;
}

/**
 * Selector temporal compacto: chips de años (sólo los presentes en
 * los datos), barra de meses del año contextual (sólo los presentes)
 * y display del rango efectivo a la derecha.
 *
 * Self-contained: calcula el rango (`date_from`/`date_to`) y lo
 * propaga al padre vía `onChange`. Sirve tanto en la lista de
 * transacciones como en cualquier vista de drill-down (categoría,
 * cuenta, etc.) que necesite filtrar por mes/año con datos reales.
 */
export function TimeSelector({
  availablePeriods,
  value,
  onChange,
}: TimeSelectorProps) {
  const years = useMemo(
    () => availablePeriods.map((p) => p.year),
    [availablePeriods],
  );
  const monthsByYear = useMemo(() => {
    const map = new Map<number, number[]>();
    for (const p of availablePeriods) map.set(p.year, p.months);
    return map;
  }, [availablePeriods]);

  const { activeYear, activeMonth, isFullYear, isFullMonth } = useMemo(
    () => inferActiveRange(value.dateFrom, value.dateTo),
    [value.dateFrom, value.dateTo],
  );

  // Año contextual: el activo si lo hay, si no el más reciente con
  // datos, si no el actual.
  const contextYear =
    activeYear ?? years[0] ?? new Date().getFullYear();
  const availableMonths = monthsByYear.get(contextYear) ?? [];

  function pickYear(year: number) {
    // Toggle: si ya estaba seleccionado ese año entero, limpiamos
    // el rango (vuelve a "Todo el histórico").
    if (isFullYear && activeYear === year) {
      onChange({ dateFrom: undefined, dateTo: undefined });
      return;
    }
    const start = new Date(year, 0, 1);
    const end = new Date(year, 11, 31, 23, 59, 59);
    onChange({ dateFrom: start.toISOString(), dateTo: end.toISOString() });
  }

  function pickMonth(year: number, monthIdx: number) {
    if (isFullMonth && activeYear === year && activeMonth === monthIdx) {
      onChange({ dateFrom: undefined, dateTo: undefined });
      return;
    }
    const start = new Date(year, monthIdx, 1);
    const end = new Date(year, monthIdx + 1, 0, 23, 59, 59);
    onChange({ dateFrom: start.toISOString(), dateTo: end.toISOString() });
  }

  if (years.length === 0) {
    return null;
  }

  const rangeDisplay = formatRangeDisplay({
    activeYear,
    activeMonth,
    isFullYear,
    isFullMonth,
    dateFrom: value.dateFrom,
    dateTo: value.dateTo,
  });

  return (
    <div
      style={{
        display: 'flex',
        gap: spacing.md,
        alignItems: 'stretch',
        flexWrap: 'wrap',
        padding: spacing.sm,
        backgroundColor: colors.surfaceMuted,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
      }}
    >
      <MonthBar
        contextYear={contextYear}
        availableMonths={availableMonths}
        activeYear={activeYear}
        activeMonth={activeMonth}
        isFullMonth={isFullMonth}
        onPickMonth={pickMonth}
      />
      <YearBar
        years={years}
        activeYear={activeYear}
        isFullYear={isFullYear}
        onPickYear={pickYear}
      />
      <RangeDisplay value={rangeDisplay} />
    </div>
  );
}

function MonthBar({
  contextYear,
  availableMonths,
  activeYear,
  activeMonth,
  isFullMonth,
  onPickMonth,
}: {
  contextYear: number;
  availableMonths: number[];
  activeYear: number | null;
  activeMonth: number | null;
  isFullMonth: boolean;
  onPickMonth: (year: number, monthIdx: number) => void;
}) {
  if (availableMonths.length === 0) {
    return (
      <div
        style={{
          flex: '1 1 520px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: spacing.sm,
          color: colors.textMuted,
          fontSize: fontSize.xs,
        }}
      >
        Sin meses con datos en {contextYear}.
      </div>
    );
  }
  return (
    <div
      style={{
        flex: '1 1 520px',
        display: 'flex',
        gap: 4,
        overflowX: 'auto',
        scrollbarWidth: 'thin',
      }}
    >
      {availableMonths.map((month) => {
        const idx = month - 1;
        const label = SPANISH_MONTHS_SHORT[idx] ?? String(month);
        const isActive =
          isFullMonth && activeYear === contextYear && activeMonth === idx;
        return (
          <button
            key={month}
            type="button"
            onClick={() => onPickMonth(contextYear, idx)}
            style={{
              flex: '1 1 auto',
              minWidth: 56,
              padding: `${spacing.xs}px ${spacing.sm}px`,
              backgroundColor: isActive ? colors.primary : colors.surface,
              color: isActive ? colors.onPrimary : colors.text,
              border: `1px solid ${isActive ? colors.primary : colors.border}`,
              borderRadius: radius.sm,
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 2,
              lineHeight: 1.1,
            }}
            aria-pressed={isActive}
            aria-label={`${label} ${contextYear}`}
          >
            <span style={{ fontSize: fontSize.sm, fontWeight: fontWeight.semibold }}>
              {label}
            </span>
            <span
              style={{
                fontSize: 10,
                color: isActive ? colors.onPrimary : colors.textSubtle,
                opacity: isActive ? 0.85 : 1,
              }}
            >
              {contextYear}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function YearBar({
  years,
  activeYear,
  isFullYear,
  onPickYear,
}: {
  years: number[];
  activeYear: number | null;
  isFullYear: boolean;
  onPickYear: (year: number) => void;
}) {
  const sorted = [...years].sort((a, b) => a - b);
  return (
    <div
      style={{
        display: 'flex',
        gap: 4,
        flexShrink: 0,
        alignSelf: 'center',
      }}
    >
      {sorted.map((year) => {
        const isActive = isFullYear && activeYear === year;
        return (
          <button
            key={year}
            type="button"
            onClick={() => onPickYear(year)}
            style={{
              padding: `${spacing.xs}px ${spacing.sm + 2}px`,
              backgroundColor: isActive ? colors.primary : colors.surface,
              color: isActive ? colors.onPrimary : colors.text,
              border: `1px solid ${isActive ? colors.primary : colors.border}`,
              borderRadius: radius.sm,
              fontSize: fontSize.sm,
              fontWeight: fontWeight.semibold,
              cursor: 'pointer',
              fontVariantNumeric: 'tabular-nums',
            }}
            aria-pressed={isActive}
          >
            {year}
          </button>
        );
      })}
    </div>
  );
}

function RangeDisplay({
  value,
}: {
  value: { primary: string; secondary: string } | null;
}) {
  return (
    <div
      style={{
        flex: '0 0 auto',
        minWidth: 180,
        padding: `${spacing.xs}px ${spacing.md}px`,
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.sm,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 2,
        textAlign: 'center',
      }}
    >
      <span
        style={{
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: colors.text,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        {value?.primary ?? 'Todo el histórico'}
      </span>
      <span style={{ fontSize: 10, color: colors.textSubtle }}>
        {value?.secondary ?? 'sin filtro de fecha'}
      </span>
    </div>
  );
}

function inferActiveRange(
  dateFrom: string | undefined,
  dateTo: string | undefined,
): {
  activeYear: number | null;
  activeMonth: number | null;
  isFullYear: boolean;
  isFullMonth: boolean;
} {
  if (!dateFrom || !dateTo) {
    return { activeYear: null, activeMonth: null, isFullYear: false, isFullMonth: false };
  }
  const start = new Date(dateFrom);
  const end = new Date(dateTo);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return { activeYear: null, activeMonth: null, isFullYear: false, isFullMonth: false };
  }
  const year = start.getFullYear();
  const isFullYear =
    start.getMonth() === 0 &&
    start.getDate() === 1 &&
    end.getFullYear() === year &&
    end.getMonth() === 11 &&
    end.getDate() === 31;
  const month = start.getMonth();
  const lastDayOfMonth = new Date(year, month + 1, 0).getDate();
  const isFullMonth =
    start.getDate() === 1 &&
    end.getFullYear() === year &&
    end.getMonth() === month &&
    end.getDate() === lastDayOfMonth;
  return {
    activeYear: year,
    activeMonth: isFullMonth ? month : null,
    isFullYear,
    isFullMonth,
  };
}

function formatRangeDisplay({
  activeYear,
  activeMonth,
  isFullYear,
  isFullMonth,
  dateFrom,
  dateTo,
}: {
  activeYear: number | null;
  activeMonth: number | null;
  isFullYear: boolean;
  isFullMonth: boolean;
  dateFrom: string | undefined;
  dateTo: string | undefined;
}): { primary: string; secondary: string } | null {
  if (isFullMonth && activeYear !== null && activeMonth !== null) {
    const monthName = [
      'Enero',
      'Febrero',
      'Marzo',
      'Abril',
      'Mayo',
      'Junio',
      'Julio',
      'Agosto',
      'Septiembre',
      'Octubre',
      'Noviembre',
      'Diciembre',
    ][activeMonth];
    return { primary: `${monthName} ${activeYear}`, secondary: 'mes seleccionado' };
  }
  if (isFullYear && activeYear !== null) {
    return { primary: `${activeYear}`, secondary: 'año seleccionado' };
  }
  if (dateFrom && dateTo) {
    const f = formatShortDate(dateFrom);
    const t = formatShortDate(dateTo);
    return { primary: `${f} – ${t}`, secondary: 'rango personalizado' };
  }
  return null;
}

function formatShortDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  const day = String(d.getDate()).padStart(2, '0');
  const month = SPANISH_MONTHS_SHORT[d.getMonth()] ?? '';
  return `${day} ${month} ${d.getFullYear()}`;
}
