'use client';

import { useMemo } from 'react';

import {
  cycleBoundsForAnchor,
  cycleDaysForAnchor,
  isValidCycleStartDay,
} from '@crisol/services';
import {
  colors,
  cycleLabel,
  cycleRangeLabel,
  fontSize,
  fontWeight,
  radius,
  spacing,
} from '@crisol/ui';

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
  /**
   * C3b — Día en que empieza el mes del usuario (`users.cycle_start_day`, 1–28).
   *
   * **Sin esta prop el componente se comporta EXACTAMENTE como antes**: ni chip
   * de modo, ni ciclos, ni etiqueta de ciclo. Es el estado de todo el mundo
   * hasta que configura el ajuste, así que es el camino que más hay que
   * proteger (tiene su test).
   *
   * `| undefined` explícito porque los consumidores leen el perfil con `useMe()`
   * y mientras carga —o si el backend en marcha es anterior a la columna— el
   * valor no existe: con `exactOptionalPropertyTypes` una prop `?: number` no
   * admite que le pasen `undefined`. Y la validación de aquí dentro es por
   * VERDAD (`isValidCycleStartDay`), no `!== null`, porque `undefined !== null`
   * es `true` y ofrecería el preset a quien no lo tiene configurado
   * (lección PHASE-47.E).
   */
  cycleStartDay?: number | undefined;
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
 *
 * C3b — Con `cycleStartDay` aparece el chip «Mi ciclo». Pulsarlo NO cambia los
 * chips de la barra (siguen siendo los meses con datos): cambia lo que un chip
 * SIGNIFICA. En modo natural, «Ago» es del 1 al 31 de agosto; en modo ciclo,
 * «Ago» es el ciclo que ABRE en agosto (14 ago → 13 sep con D=14). Es la misma
 * convención de ancla que usa el resto de la app: un ciclo se nombra por el mes
 * que lo abre.
 */
export function TimeSelector({
  availablePeriods,
  value,
  onChange,
  cycleStartDay,
}: TimeSelectorProps) {
  const cycleEnabled = isValidCycleStartDay(cycleStartDay);

  const years = useMemo(
    () => availablePeriods.map((p) => p.year),
    [availablePeriods],
  );
  const monthsByYear = useMemo(() => {
    const map = new Map<number, number[]>();
    for (const p of availablePeriods) map.set(p.year, p.months);
    return map;
  }, [availablePeriods]);

  const { activeYear, activeMonth, isFullYear, isFullMonth, isFullCycle } = useMemo(
    () => inferActiveRange(value.dateFrom, value.dateTo, cycleStartDay),
    [value.dateFrom, value.dateTo, cycleStartDay],
  );

  /*
   * El modo es controlado-por-el-usuario-si-lo-toca y DERIVADO si no
   * (`null` = «no lo ha tocado»), en vez de un `useState` sembrado en el mount.
   *
   * El motivo es concreto: los consumidores leen el día con `useMe()`, que es
   * asíncrono. En el primer render `cycleStartDay` llega `undefined`, así que un
   * estado sembrado en el mount se quedaría en «natural» PARA SIEMPRE aunque el
   * rango que hereda la pantalla (p. ej. el `?from&to` que trae el drill-down
   * desde Análisis) sea un ciclo. Derivándolo, el chip aparece pulsado en cuanto
   * el perfil llega, y en el momento en que el usuario lo toca manda él.
   */
  /*
   * PHASE-47 — el modo ya no se elige, se declara en Ajustes.
   *
   * Aquí vivía un `cycleModeRequested` de tres estados —«no lo ha tocado» /
   * natural / ciclo— con un chip para alternarlo. Ese chip preguntaba al
   * usuario, en cada pantalla, algo que ya había respondido una vez en su
   * perfil: si su mes empieza el día 1 o el día que cobra. Ahora un chip de mes
   * SIGNIFICA su mes, y no hay nada que alternar.
   */
  const cycleMode = cycleEnabled;

  // Año contextual: el activo si lo hay, si no el más reciente con
  // datos, si no el actual.
  const contextYear =
    activeYear ?? years[0] ?? new Date().getFullYear();
  const availableMonths = monthsByYear.get(contextYear) ?? [];

  /**
   * Emite el mes `monthIdx` de `year` como rango, en el modo pedido: el mes
   * natural completo, o el CICLO que abre en ese mes.
   *
   * Los bounds del ciclo salen de `cycleBoundsForAnchor` (capa compartida) y no
   * de un `Date.UTC` escrito aquí: esa función es la que sabe que el intervalo
   * del backend es cerrado por los dos extremos (`toDay` = día D−1 del mes
   * siguiente). Repetir la aritmética aquí sería una segunda definición del
   * borde, y el borde es justo lo que se cuenta dos veces cuando divergen.
   */
  function emitMonth(year: number, monthIdx: number, asCycle: boolean) {
    if (asCycle && isValidCycleStartDay(cycleStartDay)) {
      onChange(cycleBoundsForAnchor(cycleStartDay, utcAnchor(year, monthIdx)));
      return;
    }
    // Mismo motivo que `pickYear`: límites en UTC. Día 0 del mes
    // siguiente = último día del mes actual.
    const start = new Date(Date.UTC(year, monthIdx, 1, 0, 0, 0));
    const end = new Date(Date.UTC(year, monthIdx + 1, 0, 23, 59, 59));
    onChange({ dateFrom: start.toISOString(), dateTo: end.toISOString() });
  }

  function pickYear(year: number) {
    // Toggle: si ya estaba seleccionado ese año entero, limpiamos
    // el rango (vuelve a "Todo el histórico").
    if (isFullYear && activeYear === year) {
      onChange({ dateFrom: undefined, dateTo: undefined });
      return;
    }
    // Límites en UTC: las tx se guardan con `fromDateInputValue`
    // (`T00:00:00Z`), así que el rango debe construirse en UTC. Con
    // `new Date(year, 0, 1)` (hora local) → `.toISOString()` el límite se
    // desplazaba según el huso del navegador y dejaba fuera/dentro tx del
    // borde de año.
    //
    // El año sigue siendo el año NATURAL también con el preset activo: un año
    // de doce ciclos es otra pregunta y no la responde este chip.
    const start = new Date(Date.UTC(year, 0, 1, 0, 0, 0));
    const end = new Date(Date.UTC(year, 11, 31, 23, 59, 59));
    onChange({ dateFrom: start.toISOString(), dateTo: end.toISOString() });
  }

  function pickMonth(year: number, monthIdx: number) {
    // "Ya seleccionado" se juzga en el modo activo: el mismo chip señala el mes
    // natural o el ciclo según el modo, así que el toggle de limpiar también.
    const alreadyActive =
      (cycleMode ? isFullCycle : isFullMonth) &&
      activeYear === year &&
      activeMonth === monthIdx;
    if (alreadyActive) {
      onChange({ dateFrom: undefined, dateTo: undefined });
      return;
    }
    emitMonth(year, monthIdx, cycleMode);
  }


  if (years.length === 0) {
    return null;
  }

  const rangeDisplay = formatRangeDisplay({
    activeYear,
    activeMonth,
    isFullYear,
    isFullMonth,
    isFullCycle,
    cycleStartDay,
    dateFrom: value.dateFrom,
    dateTo: value.dateTo,
  });

  // Qué chip de mes se pinta activo: el que corresponde al modo. Con el rango
  // en ciclo y el modo natural (o al revés) no se marca ninguno, que es la
  // verdad — ese chip no produciría el rango que hay puesto.
  const highlightedMonth =
    (cycleMode ? isFullCycle : isFullMonth) && activeYear === contextYear
      ? activeMonth
      : null;

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
        highlightedMonth={highlightedMonth}
        cycleStartDay={cycleMode ? cycleStartDay : undefined}
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
  highlightedMonth,
  cycleStartDay,
  onPickMonth,
}: {
  contextYear: number;
  availableMonths: number[];
  highlightedMonth: number | null;
  /** Definido SÓLO en modo ciclo: cambia lo que significa cada chip. */
  cycleStartDay: number | undefined;
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
        const isActive = highlightedMonth === idx;
        // El nombre accesible dice qué se elige de verdad. En modo ciclo, «Ago»
        // no es agosto: es «Ciclo del 14 ago 2026», y sale de `cycleLabel` —
        // la misma función que titula el display y el navegador de período.
        const accessibleName =
          cycleStartDay === undefined
            ? `${label} ${contextYear}`
            : cycleLabel(cycleStartDay, utcAnchor(contextYear, idx));
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
            aria-label={accessibleName}
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

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

/** `(2026, 7)` (índice de mes, 0-11) → ancla `2026-08`. */
function utcAnchor(year: number, monthIdx: number): string {
  return `${String(year).padStart(4, '0')}-${pad2(monthIdx + 1)}`;
}

/** `Date` leída en UTC → day-string `YYYY-MM-DD`. */
function utcDayString(d: Date): string {
  return `${String(d.getUTCFullYear()).padStart(4, '0')}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())}`;
}

/**
 * ¿Este rango ES un ciclo del usuario? — la definición ÚNICA, exportada.
 *
 * La usan `inferActiveRange` (para el chip activo y la etiqueta) y el drill-down
 * de categoría (para pedir la serie mensual con `cycle=true`). Una segunda copia
 * en la página querría decir lo mismo y acabaría diciendo otra cosa: el
 * selector pintaría «Ciclo del 14 ago» mientras el chart de al lado sigue
 * cortando por mes natural, sin que nada avise (lección PHASE-46).
 *
 * Reconoce por ARITMÉTICA, no por comparación de cadenas: el rango puede haber
 * llegado de un `toISOString()` (`…T00:00:00.000Z`) o del filtro manual de
 * fechas (`…T00:00:00Z`), y las dos cadenas son el mismo instante. Compara el
 * día de apertura y el día de cierre en UTC, igual que hace `isFullMonth` con el
 * último día del mes.
 *
 * Guarda por VERDAD: con `cycleStartDay` ausente, `null`, 0 o 29 devuelve
 * `false` por la misma puerta (`isValidCycleStartDay`).
 */
export function isCycleRange(
  dateFrom: string | undefined,
  dateTo: string | undefined,
  cycleStartDay: number | null | undefined,
): boolean {
  if (!dateFrom || !dateTo) return false;
  if (!isValidCycleStartDay(cycleStartDay)) return false;
  const start = new Date(dateFrom);
  const end = new Date(dateTo);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return false;
  if (start.getUTCDate() !== cycleStartDay) return false;
  const { toDay } = cycleDaysForAnchor(
    cycleStartDay,
    utcAnchor(start.getUTCFullYear(), start.getUTCMonth()),
  );
  return utcDayString(end) === toDay;
}

function inferActiveRange(
  dateFrom: string | undefined,
  dateTo: string | undefined,
  cycleStartDay?: number | undefined,
): {
  activeYear: number | null;
  activeMonth: number | null;
  isFullYear: boolean;
  isFullMonth: boolean;
  isFullCycle: boolean;
} {
  const empty = {
    activeYear: null,
    activeMonth: null,
    isFullYear: false,
    isFullMonth: false,
    isFullCycle: false,
  };
  if (!dateFrom || !dateTo) {
    return empty;
  }
  const start = new Date(dateFrom);
  const end = new Date(dateTo);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return empty;
  }
  // Leemos en UTC para casar con los límites que emite `pickYear`/
  // `pickMonth` (construidos con `Date.UTC`). Con getters locales, un
  // navegador en huso != UTC nunca detectaría el año/mes como "completo".
  const year = start.getUTCFullYear();
  const isFullYear =
    start.getUTCMonth() === 0 &&
    start.getUTCDate() === 1 &&
    end.getUTCFullYear() === year &&
    end.getUTCMonth() === 11 &&
    end.getUTCDate() === 31;
  const month = start.getUTCMonth();
  const lastDayOfMonth = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const isFullMonth =
    start.getUTCDate() === 1 &&
    end.getUTCFullYear() === year &&
    end.getUTCMonth() === month &&
    end.getUTCDate() === lastDayOfMonth;
  // C3b — Un ciclo 14-ago → 13-sep no casa `isFullMonth` ni `isFullYear`, así
  // que sin esto caería al literal «rango personalizado» y el usuario vería su
  // propio mes descrito como una rareza.
  const isFullCycle = isCycleRange(dateFrom, dateTo, cycleStartDay);
  return {
    activeYear: year,
    // El mes activo es el del INICIO del rango, que en un ciclo es su ancla
    // (el mes que lo abre) — la misma convención que el resto de la app.
    activeMonth: isFullMonth || isFullCycle ? month : null,
    isFullYear,
    isFullMonth,
    isFullCycle,
  };
}

function formatRangeDisplay({
  activeYear,
  activeMonth,
  isFullYear,
  isFullMonth,
  isFullCycle,
  cycleStartDay,
  dateFrom,
  dateTo,
}: {
  activeYear: number | null;
  activeMonth: number | null;
  isFullYear: boolean;
  isFullMonth: boolean;
  isFullCycle: boolean;
  cycleStartDay: number | undefined;
  dateFrom: string | undefined;
  dateTo: string | undefined;
}): { primary: string; secondary: string } | null {
  // El mes natural se comprueba ANTES que el ciclo a propósito: con `D = 1` el
  // ciclo degenera en el mes natural (son el mismo rango), y ahí «Agosto 2026»
  // dice más que «Ciclo del 1 ago 2026».
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
  if (
    isFullCycle &&
    isValidCycleStartDay(cycleStartDay) &&
    activeYear !== null &&
    activeMonth !== null
  ) {
    // Titular = el ciclo por su día de cobro; debajo, el rango explícito. Las
    // dos cadenas salen de `@crisol/ui`: son el contrato de cómo se nombra un
    // ciclo, y móvil dice exactamente lo mismo.
    const anchor = utcAnchor(activeYear, activeMonth);
    const { fromDay, toDay } = cycleDaysForAnchor(cycleStartDay, anchor);
    return {
      primary: cycleLabel(cycleStartDay, anchor),
      secondary: cycleRangeLabel(fromDay, toDay),
    };
  }
  if (dateFrom && dateTo) {
    const f = formatShortDate(dateFrom);
    const t = formatShortDate(dateTo);
    return { primary: `${f} – ${t}`, secondary: 'rango personalizado' };
  }
  return null;
}

function formatShortDate(iso: string): string {
  // Lee en UTC porque lo que recibe son BOUNDS construidos con `Date.UTC`
  // (`boundsForCustomRange` y compañía). Leerlos con getters locales mezcla dos
  // convenciones en el mismo valor: el titular del rango salía un día antes en
  // husos negativos y un día DESPUÉS en +14, porque `dateTo` es 23:59:59Z.
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  const day = String(d.getUTCDate()).padStart(2, '0');
  const month = SPANISH_MONTHS_SHORT[d.getUTCMonth()] ?? '';
  return `${day} ${month} ${d.getUTCFullYear()}`;
}
