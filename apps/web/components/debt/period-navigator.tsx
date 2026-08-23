'use client';

import { useEffect } from 'react';

import {
  canStepCycleNext,
  canStepCyclePrev,
  canStepNext,
  canStepPrev,
  clampAnchor,
  clampCycleAnchor,
  periodLabel,
  stepAnchor,
  stepCycleAnchor,
} from '@crisol/services';
import type { PeriodKey } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  radius,
  spacing,
} from '@crisol/ui';

import { StitchPeriodToggle } from '@/components/analysis/stitch-period-toggle';
import {
  DatePicker,
  dataMaxDayStr,
  dataMinDayStr,
} from '@/components/ui/date-picker';

/** Menor de dos day-strings `YYYY-MM-DD` (comparación lexicográfica). `b` es el
 * tope duro; si `a` es null o posterior, gana `b`. */
function minDayStr(a: string | null | undefined, b: string): string {
  return a != null && a < b ? a : b;
}

/** Recorta un day-string al rango `[lo, hi]` (lo puede ser null = sin tope). */
function clampDay(day: string, lo: string | null, hi: string): string {
  let d = day;
  if (d > hi) d = hi;
  if (lo != null && d < lo) d = lo;
  return d;
}

export interface PeriodNavigatorProps {
  /**
   * C3a — El navegador habla en `PeriodKey` (vocabulario de la UI, con
   * `cycle`), NO en `DebtTimeRange` (el contrato de la API de deuda, que sólo
   * admite `month|year|custom`). Traducir el ciclo a lo que entiende el
   * servidor —`range=custom` con las fechas del ciclo— es cosa de la página,
   * que es quien construye la query. Mandar `range=cycle` daría 422.
   */
  range: PeriodKey;
  onRangeChange: (range: PeriodKey) => void;
  /** Mes ancla `YYYY-MM` del período mostrado. */
  anchor: string;
  onAnchorChange: (anchor: string) => void;
  availableFrom: string | null;
  availableTo: string | null;
  /**
   * PHASE-41 — expone la opción "Personalizado" (rango libre `from/to`).
   * Off por defecto: sólo donde el consumidor sabe manejar `range='custom'`.
   */
  allowCustom?: boolean;
  /** Rango libre activo (day-strings `YYYY-MM-DD`), sólo con `range='custom'`. */
  customFrom?: string | null;
  customTo?: string | null;
  onCustomRangeChange?: (from: string, to: string) => void;
  /**
   * C3a — Día en que empieza el mes del usuario (1–28). Con él, el toggle
   * ofrece «Mi ciclo» y las flechas saltan de ciclo en ciclo.
   *
   * Sin él (o mientras carga el perfil) el navegador es exactamente el de
   * siempre. `| undefined` explícito por `exactOptionalPropertyTypes`.
   */
  cycleStartDay?: number | undefined;
  /**
   * ¿Los `availableFrom`/`availableTo` que recibo YA son anclas de ciclo?
   *
   * Depende del endpoint que los produjo, y por eso lo declara el consumidor:
   * - `true` — vienen de un endpoint pedido con `cycle=true` (dashboard,
   *   análisis): el backend ya los bucketizó con la expresión desplazada, así
   *   que traducirlos otra vez habilitaría un ciclo VACÍO por la izquierda.
   * - `false` (default) — son MESES NATURALES. Es el caso de Deuda, cuyo
   *   `/debt/category-summary` no tiene parámetro `cycle`: aquí hay que
   *   traducirlos con `clampCycleAnchor`, o el ciclo que CONTIENE el primer
   *   movimiento queda inalcanzable (con D=14 y datos desde el 5 de marzo, ese
   *   pago vive en el ciclo que abre el 14 de febrero, y la flecha ◀ saldría
   *   deshabilitada en marzo).
   *
   * El default es `false` a propósito: equivocarse hacia «traducir» enseña un
   * período vacío de más, y equivocarse hacia «no traducir» ESCONDE
   * movimientos. Entre las dos, la que oculta datos nunca puede ser el default.
   */
  boundsAlreadyInCycles?: boolean;
}

/**
 * PHASE-30.8 / PHASE-41 — Navegador de período: granularidad (Mes / Año /
 * Personalizado, vía `StitchPeriodToggle`) + flechas ◀ ▶ para los períodos
 * navegables, o dos date-pickers para el rango libre `custom`. Limitado al
 * rango con datos (`availableFrom`/`availableTo`).
 */
export function PeriodNavigator({
  range,
  onRangeChange,
  anchor,
  onAnchorChange,
  availableFrom,
  availableTo,
  allowCustom = false,
  customFrom = null,
  customTo = null,
  onCustomRangeChange,
  cycleStartDay,
  boundsAlreadyInCycles = false,
}: PeriodNavigatorProps) {
  // Guarda POR VERDAD, nunca `!== undefined`: mientras `useMe()` carga el valor
  // no existe, y con un backend anterior a la columna tampoco. Ofrecer el chip
  // en ese estado lleva a un 422 del servidor (lección PHASE-47.E).
  const cycleEnabled = cycleStartDay != null && cycleStartDay >= 1;
  // PHASE-41 — `custom` (rango libre) no navega: las flechas/label sólo
  // aplican a los períodos navegables (month/year). Los guards estrechan
  // el tipo a `NavigableRange` para los helpers puros.
  /*
   * C3a — Con el preset activo, las flechas saltan de CICLO en ciclo, pero el
   * clamp que las acota es el MENSUAL llano (`canStepPrev`/`clampAnchor` con
   * granularidad `month`), no `canStepCyclePrev`. No es un descuido:
   *
   * `available_from`/`available_to` llegan del backend YA como anclas de ciclo
   * cuando se pide con `cycle=true` (los bucketea la misma expresión
   * desplazada). Los helpers `clampCycleAnchor`/`canStepCycle*` existen para
   * TRADUCIR meses naturales a ciclos —retroceden un mes cuando D>1, porque el
   * ciclo que contiene el día 1 del primer mes con datos abre el mes
   * anterior—, así que aplicarlos sobre unos bounds ya traducidos los
   * traduciría DOS VECES y habilitaría por la izquierda un ciclo vacío.
   *
   * Un ciclo es exactamente un mes de ancla, así que sobre anclas ya
   * traducidas la aritmética mensual es la correcta.
   */
  const navigable = range;
  // PHASE-47 — el disparador es el PERFIL, no un preset elegido: «Mes» corta
  // por el ciclo cuando el usuario declaró un día de inicio.
  const monthIsCycle = range === 'month' && cycleEnabled;
  // Con el preset, QUÉ clamp usar depende de en qué unidad llegan los bounds
  // (ver `boundsAlreadyInCycles`): si ya son anclas de ciclo, la aritmética
  // mensual es la correcta —un ciclo es un mes de ancla—; si son meses
  // naturales, hay que traducirlos, y de eso saben los helpers de ciclo.
  const translateBounds = monthIsCycle && !boundsAlreadyInCycles && cycleStartDay != null;
  const prevEnabled =
    range !== 'custom' &&
    (translateBounds && cycleStartDay != null
      ? canStepCyclePrev(anchor, availableFrom, cycleStartDay)
      : canStepPrev(navigable as 'month' | 'year', anchor, availableFrom));
  const nextEnabled =
    range !== 'custom' &&
    (translateBounds && cycleStartDay != null
      ? canStepCycleNext(anchor, availableTo, cycleStartDay)
      : canStepNext(navigable as 'month' | 'year', anchor, availableTo));

  // El ancla por defecto es el mes en curso, que puede caer FUERA del rango con
  // datos (p. ej. julio vacío cuando la última tx es de junio). `clampAnchor`
  // sólo corre al pulsar el toggle/flecha, así que sin esto te quedas en un
  // período sin datos hasta que navegas. Aquí lo re-acotamos en cuanto llegan
  // los límites (tras cargar): comparamos el clamp CON límites contra el clamp
  // SIN límites (mera normalización) — si difieren, el ancla estaba fuera y la
  // corregimos. Idempotente: una vez dentro, no vuelve a disparar.
  useEffect(() => {
    if (range === 'custom') return;
    if (availableFrom == null && availableTo == null) return;
    const g = range;
    const clamped =
      translateBounds && cycleStartDay != null
        ? clampCycleAnchor(anchor, availableFrom, availableTo, cycleStartDay)
        : clampAnchor(g, anchor, availableFrom, availableTo);
    const normalized = clampAnchor(g, anchor, null, null);
    if (clamped !== normalized) onAnchorChange(clamped);
  }, [range, anchor, availableFrom, availableTo, onAnchorChange]);

  // Rango personalizado acotado a los días CON DATOS: si el from/to sembrado
  // (o uno viejo de la URL) cae fuera de `[primer día, último día]` con datos,
  // lo recortamos. Cubre el caso del seed en modo Año, que llega hasta hoy
  // aunque el último dato sea de un mes anterior. Idempotente.
  useEffect(() => {
    if (range !== 'custom' || !customFrom || !customTo) return;
    const lo = dataMinDayStr(availableFrom);
    const hi = dataMaxDayStr(availableTo);
    const f = clampDay(customFrom, lo, hi);
    const t = clampDay(customTo, lo, hi);
    if (f !== customFrom || t !== customTo) onCustomRangeChange?.(f, t);
  }, [range, customFrom, customTo, availableFrom, availableTo, onCustomRangeChange]);

  function handleRangeChange(next: PeriodKey) {
    onRangeChange(next);
    // Re-snap + re-clamp el ancla a la nueva granularidad (custom no navega).
    if (next !== 'custom') {
      onAnchorChange(
        clampAnchor(next, anchor, availableFrom, availableTo),
      );
    }
  }

  function step(direction: 1 | -1) {
    if (range === 'custom') return;
    // Un ciclo avanza un mes de ancla, igual que el período mensual: el paso lo
    // da la función compartida en vez de sumar aquí, para que web y móvil no
    // puedan discrepar en el cruce de año.
    const nextAnchor = monthIsCycle
      ? stepCycleAnchor(anchor, direction)
      : stepAnchor(range, anchor, direction);
    onAnchorChange(
      translateBounds && cycleStartDay != null
        ? clampCycleAnchor(nextAnchor, availableFrom, availableTo, cycleStartDay)
        : clampAnchor(range, nextAnchor, availableFrom, availableTo),
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: spacing.md,
        flexWrap: 'wrap',
      }}
    >
      <StitchPeriodToggle
        value={range}
        onChange={handleRangeChange}
        options={[
          'month' as const,
          'year' as const,
          ...(allowCustom ? (['custom'] as const) : []),
        ]}
      />
      {range === 'custom' ? (
        <div
          style={{ display: 'inline-flex', alignItems: 'center', gap: spacing.xs }}
          role="group"
          aria-label="Rango de fechas"
        >
          <DatePicker
            value={customFrom}
            min={dataMinDayStr(availableFrom)}
            max={minDayStr(customTo, dataMaxDayStr(availableTo))}
            onChange={(from) => onCustomRangeChange?.(from, customTo ?? '')}
            ariaLabel="Desde"
          />
          <span style={{ color: colors.textMuted, fontSize: fontSize.sm }}>–</span>
          <DatePicker
            value={customTo}
            min={customFrom ?? dataMinDayStr(availableFrom)}
            max={dataMaxDayStr(availableTo)}
            onChange={(to) => onCustomRangeChange?.(customFrom ?? '', to)}
            ariaLabel="Hasta"
          />
        </div>
      ) : (
        <div
          style={{ display: 'inline-flex', alignItems: 'center', gap: spacing.xs }}
          role="group"
          aria-label="Navegar período"
        >
          <ArrowButton direction="prev" disabled={!prevEnabled} onClick={() => step(-1)} />
          <span
            style={{
              minWidth: 124,
              textAlign: 'center',
              fontSize: fontSize.sm,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {/*
              * PHASE-47 — el período se llama como el mes que lo ABRE, tenga
              * el usuario ciclo o no: «Julio 2026» va del 12 de julio al 11 de
              * agosto si ése es su corte.
              */}
            {periodLabel(range, anchor)}
          </span>
          <ArrowButton direction="next" disabled={!nextEnabled} onClick={() => step(1)} />
        </div>
      )}
    </div>
  );
}

function ArrowButton({
  direction,
  disabled,
  onClick,
}: {
  direction: 'prev' | 'next';
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={direction === 'prev' ? 'Período anterior' : 'Período siguiente'}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 32,
        height: 32,
        borderRadius: radius.sm,
        border: `1px solid ${colors.border}`,
        backgroundColor: colors.surface,
        color: disabled ? colors.textSubtle : colors.text,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        fontSize: fontSize.lg,
        lineHeight: 1,
        padding: 0,
      }}
    >
      {direction === 'prev' ? '‹' : '›'}
    </button>
  );
}
