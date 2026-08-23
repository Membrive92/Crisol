import { useEffect } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  canStepCycleNext,
  canStepCyclePrev,
  canStepNext,
  canStepPrev,
  clampAnchor,
  clampCycleAnchor,
  dataMaxDayStr,
  dataMinDayStr,
  isValidCycleStartDay,
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

import { DateInput } from '../ui/date-input';

export interface PeriodNavigatorProps {
  /**
   * C3a — El navegador habla en `PeriodKey` (vocabulario de la UI, con
   * `cycle`), NO en `DebtTimeRange` (el contrato de la API de deuda, que sólo
   * admite `month|year|custom`). Traducir el ciclo a lo que entiende el
   * servidor —`range=custom` con las fechas del ciclo— es cosa de la pantalla,
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
   * PHASE-41 — expone la opción "Rango" (rango libre `from/to`). Off por
   * defecto: sólo donde el consumidor sabe manejar `range='custom'`.
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
   * ¿Los `availableFrom`/`availableTo` YA son anclas de ciclo?
   *
   * `true` — vienen de un endpoint pedido con `cycle=true` (dashboard,
   * análisis): ya están bucketizados y traducirlos otra vez habilitaría un
   * ciclo VACÍO por la izquierda. `false` (default) — son MESES NATURALES, el
   * caso de Deuda, cuyo endpoint no tiene ese parámetro: hay que traducirlos o
   * el ciclo que CONTIENE el primer movimiento queda inalcanzable.
   *
   * Default `false` a propósito: equivocarse hacia «traducir» enseña un período
   * vacío de más; hacia «no traducir», ESCONDE movimientos.
   */
  boundsAlreadyInCycles?: boolean;
}

const RANGE_LABEL: Record<PeriodKey, string> = {
  month: 'Mes',
  year: 'Año',
  custom: 'Rango',
};

/** Parsea un day-string `YYYY-MM-DD` a `Date` (UTC) para acotar los pickers. */
function toDate(day: string | null | undefined): Date | undefined {
  if (!day) return undefined;
  const [y, m, d] = day.split('-').map(Number);
  return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1));
}

/** Recorta un day-string al rango `[lo, hi]` (`lo` puede ser null = sin tope). */
function clampDay(day: string, lo: string | null, hi: string): string {
  let d = day;
  if (d > hi) d = hi;
  if (lo != null && d < lo) d = lo;
  return d;
}

/**
 * PHASE-30.8 / PHASE-41 — Navegador de período (mobile parity del web): toggle
 * de granularidad (Mes / Año / Rango) + flechas ◀ ▶ para los períodos
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
  // Guarda POR VERDAD, nunca `!== null`: mientras `useMe()` carga el valor no
  // existe, y con un backend anterior a la columna tampoco. Ofrecer el chip en
  // ese estado lleva a un 422 del servidor (lección PHASE-47.E).
  const cycleEnabled = isValidCycleStartDay(cycleStartDay);
  const ranges: PeriodKey[] = [
    'month',
    'year',
    ...(allowCustom ? (['custom'] as const) : []),
  ];
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
   * traducidas la aritmética mensual es la correcta. Mismo contrato que el
   * navegador de web, con su test de regresión a cada lado.
   */
  const navigable: 'month' | 'year' = range === 'year' ? 'year' : 'month';
  // Qué clamp usar depende de en qué UNIDAD llegan los bounds (ver
  // `boundsAlreadyInCycles`), no de si el preset está activo.
  // PHASE-47 — el disparador ya no es un preset elegido, es el perfil: el
  // período «Mes» corta por el ciclo cuando el usuario declaró un día.
  const monthIsCycle = range === 'month' && cycleEnabled;
  const translateBounds = monthIsCycle && !boundsAlreadyInCycles && cycleStartDay != null;
  const prevEnabled =
    range !== 'custom' &&
    (translateBounds && cycleStartDay != null
      ? canStepCyclePrev(anchor, availableFrom, cycleStartDay)
      : canStepPrev(navigable, anchor, availableFrom));
  const nextEnabled =
    range !== 'custom' &&
    (translateBounds && cycleStartDay != null
      ? canStepCycleNext(anchor, availableTo, cycleStartDay)
      : canStepNext(navigable, anchor, availableTo));

  // El ancla por defecto es el mes en curso, que puede caer FUERA del rango con
  // datos (p. ej. julio vacío cuando la última tx es de junio). `clampAnchor`
  // sólo corre al pulsar el toggle/flecha, así que sin esto te quedas en un
  // período sin datos hasta que navegas. Aquí lo re-acotamos en cuanto llegan
  // los límites (tras cargar): comparamos el clamp CON límites contra el clamp
  // SIN límites (mera normalización) — si difieren, el ancla estaba fuera y la
  // corregimos. Idempotente: una vez dentro, no vuelve a disparar.
  // Con el ciclo esto deja de ser cosmético: un ancla fuera de datos ya no
  // aterriza en un mes flojo, pinta un período VACÍO.
  useEffect(() => {
    if (range === 'custom') return;
    if (availableFrom == null && availableTo == null) return;
    const g: 'month' | 'year' = range === 'year' ? 'year' : 'month';
    const clamped =
      translateBounds && cycleStartDay != null
        ? clampCycleAnchor(anchor, availableFrom, availableTo, cycleStartDay)
        : clampAnchor(g, anchor, availableFrom, availableTo);
    const normalized = clampAnchor(g, anchor, null, null);
    if (clamped !== normalized) onAnchorChange(clamped);
  }, [range, anchor, availableFrom, availableTo, onAnchorChange]);

  // Rango personalizado acotado a los días CON DATOS: si el from/to sembrado
  // cae fuera de `[primer día, último día]` con datos, lo recortamos. Cubre el
  // caso del seed en modo Año, que llega hasta fin de año aunque el último dato
  // sea de un mes anterior. Idempotente.
  useEffect(() => {
    if (range !== 'custom' || !customFrom || !customTo) return;
    const lo = dataMinDayStr(availableFrom);
    const hi = dataMaxDayStr(availableTo);
    const f = clampDay(customFrom, lo, hi);
    const t = clampDay(customTo, lo, hi);
    if (f !== customFrom || t !== customTo) onCustomRangeChange?.(f, t);
  }, [range, customFrom, customTo, availableFrom, availableTo, onCustomRangeChange]);

  function handleRange(next: PeriodKey) {
    onRangeChange(next);
    if (next !== 'custom') {
      onAnchorChange(
        clampAnchor(next === 'year' ? 'year' : 'month', anchor, availableFrom, availableTo),
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
      : stepAnchor(navigable, anchor, direction);
    onAnchorChange(
      translateBounds && cycleStartDay != null
        ? clampCycleAnchor(nextAnchor, availableFrom, availableTo, cycleStartDay)
        : clampAnchor(navigable, nextAnchor, availableFrom, availableTo),
    );
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.toggleRow}>
        {ranges.map((opt) => (
          <Pressable
            key={opt}
            onPress={() => handleRange(opt)}
            style={[styles.toggleBtn, opt === range && styles.toggleBtnActive]}
            accessibilityRole="tab"
            accessibilityState={{ selected: opt === range }}
          >
            <Text
              style={[styles.toggleText, opt === range && styles.toggleTextActive]}
            >
              {RANGE_LABEL[opt]}
            </Text>
          </Pressable>
        ))}
      </View>

      {range === 'custom' ? (
        <View style={styles.customRow}>
          <DateInput
            value={customFrom ?? ''}
            maximumDate={toDate(customTo)}
            onChange={(from) => onCustomRangeChange?.(from, customTo ?? '')}
          />
          <Text style={styles.dash}>–</Text>
          <DateInput
            value={customTo ?? ''}
            minimumDate={toDate(customFrom)}
            onChange={(to) => onCustomRangeChange?.(customFrom ?? '', to)}
          />
        </View>
      ) : (
        <View style={styles.navRow}>
          <Pressable
            onPress={() => step(-1)}
            disabled={!prevEnabled}
            style={[styles.arrow, !prevEnabled && styles.arrowDisabled]}
            accessibilityRole="button"
            accessibilityLabel="Período anterior"
          >
            <Text style={[styles.arrowText, !prevEnabled && styles.arrowTextDisabled]}>
              ‹
            </Text>
          </Pressable>
          <Text style={styles.label}>
            {/*
              * PHASE-47 — el período se llama como el mes que lo ABRE, tenga
              * el usuario ciclo o no: «Julio 2026» va del 12 de julio al 11 de
              * agosto si ése es su corte. Aquí ponía «Ciclo del 12 jul 2026»,
              * que era vocabulario nuevo para un concepto que el usuario ya
              * tenía nombrado.
              */}
            {periodLabel(navigable, anchor)}
          </Text>
          <Pressable
            onPress={() => step(1)}
            disabled={!nextEnabled}
            style={[styles.arrow, !nextEnabled && styles.arrowDisabled]}
            accessibilityRole="button"
            accessibilityLabel="Período siguiente"
          >
            <Text style={[styles.arrowText, !nextEnabled && styles.arrowTextDisabled]}>
              ›
            </Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    flexWrap: 'wrap',
  },
  toggleRow: {
    flexDirection: 'row',
    padding: 2,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  toggleBtn: {
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: radius.sm,
  },
  toggleBtnActive: {
    backgroundColor: colors.surface,
  },
  toggleText: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
  },
  toggleTextActive: {
    color: colors.text,
  },
  navRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  customRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  dash: {
    color: colors.textMuted,
    fontSize: fontSize.sm,
  },
  arrow: {
    width: 32,
    height: 32,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  arrowDisabled: {
    opacity: 0.4,
  },
  arrowText: {
    fontSize: fontSize.lg,
    color: colors.text,
    lineHeight: fontSize.lg + 4,
  },
  arrowTextDisabled: {
    color: colors.textMuted,
  },
  label: {
    minWidth: 96,
    textAlign: 'center',
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
});
