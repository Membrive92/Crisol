import { StyleSheet, Text, View } from 'react-native';

import {
  cycleAnchorContaining,
  cycleBoundsForAnchor,
  cycleDaysForAnchor,
  formatApiError,
  stepCycleAnchor,
  todayDayStr,
  useTransactions,
} from '@crisol/services';
import type { Transaction } from '@crisol/types';
import {
  colors,
  cycleLabel,
  cycleRangeLabel,
  fontSize,
  fontWeight,
  formatAmount,
  formatCivilDate,
  pluralize,
  radius,
  spacing,
  withCount,
} from '@crisol/ui';

/**
 * C2 (móvil) — La previsualización del corte. **Esto ES la feature.**
 *
 * El usuario cobra «el 15», pero el banco fecha la nómina el 14. Con el corte
 * puesto en 15, esa nómina cae FUERA del ciclo que se supone que abre — y la
 * pregunta «¿mi mes empieza por fecha-valor o por fecha contable?» no se
 * responde razonando, se responde MIRANDO las filas. Por eso la pantalla no
 * explica el corte: lo enseña, con los movimientos reales del usuario a cada
 * lado.
 *
 * Paridad con `apps/web/components/settings/cycle-preview.tsx`: mismas dos
 * ventanas, mismos sentidos de orden, mismo recuento. Lo único que cambia es
 * que aquí los dos lados van APILADOS (en un teléfono, dos columnas de 260 px
 * no caben) y que las primitivas son nativas.
 *
 * Presentación pura: aquí no se escribe nada. Son dos lecturas del listado que
 * el usuario ya conoce (el mismo endpoint, sin excluir transferencias — es lo
 * que ve en su lista, y un preview que filtrara enseñaría otra cosa).
 */

/** Cuántas filas se enseñan a cada lado del corte. Suficiente para reconocer la nómina. */
const PREVIEW_ROWS = 5;

export interface CyclePreviewProps {
  /** Día que abre el ciclo (1–28). El llamante ya lo ha validado. */
  cycleStartDay: number;
}

export function CyclePreview({ cycleStartDay }: CyclePreviewProps) {
  // El ciclo EN CURSO es la referencia: es el que el usuario tiene en la
  // cabeza. El reloj se lee UNA vez, aquí, y la aritmética que lo recibe es
  // pura (`todayDayStr` es local a propósito: responde «¿qué día es hoy PARA
  // el usuario?»; los bounds que salen de abajo son UTC, que es como corta el
  // backend).
  const incomingAnchor = cycleAnchorContaining(todayDayStr(), cycleStartDay);
  const outgoingAnchor = stepCycleAnchor(incomingAnchor, -1);

  const incomingDays = cycleDaysForAnchor(cycleStartDay, incomingAnchor);
  const outgoingDays = cycleDaysForAnchor(cycleStartDay, outgoingAnchor);
  const incomingBounds = cycleBoundsForAnchor(cycleStartDay, incomingAnchor);
  const outgoingBounds = cycleBoundsForAnchor(cycleStartDay, outgoingAnchor);

  /*
   * Los dos extremos van acotados en AMBOS lados, no sólo por el corte.
   *
   * Para las filas bastaría con el corte (`order` + `limit` ya eligen las 5 que
   * tocan), pero el `total` de la respuesta se pinta como «N movimientos caen
   * en este ciclo» — y sin el otro extremo ese número sería «todo lo anterior
   * al corte», o sea el histórico entero. Una cifra falsa en pantalla cuesta
   * más que un hueco: el hueco se pregunta y la cifra se cree.
   *
   * `outgoing.date_to` es literalmente el corte menos un segundo
   * (`…13T23:59:59Z` frente a `…14T00:00:00Z`): el intervalo del backend es
   * CERRADO por los dos extremos, así que emitir el día del corte como tope
   * contaría su primer día dos veces.
   */
  const outgoing = useTransactions({
    date_from: outgoingBounds.dateFrom,
    date_to: outgoingBounds.dateTo,
    order: 'desc',
    limit: PREVIEW_ROWS,
  });
  const incoming = useTransactions({
    date_from: incomingBounds.dateFrom,
    date_to: incomingBounds.dateTo,
    order: 'asc',
    limit: PREVIEW_ROWS,
  });

  return (
    <View>
      <Text style={styles.intro}>
        Esto es lo que hay a cada lado del corte con tus movimientos de verdad.
        Si tu nómina no aparece donde esperas, el día no es el que creías:
        cámbialo y vuelve a mirar.
      </Text>

      {/*
        `isPlaceholderData` cuenta como "cargando", y no es un detalle: el hook
        conserva los datos anteriores mientras pide los nuevos, así que al
        cambiar el día la pantalla pintaba las filas y el recuento del ciclo
        VIEJO debajo del titular y el rango del ciclo NUEVO, sin ningún
        indicador. Es decir, atribuía un número a un ciclo que no es el suyo
        justo en el gesto que esta pantalla existe para sostener. Dura una ida y
        vuelta al servidor, que es exactamente la ventana en la que el usuario
        está mirando.
      */}
      <PreviewSection
        heading="Se queda en el ciclo anterior"
        subheading={`Últimos movimientos · ${cycleLabel(cycleStartDay, outgoingAnchor)}`}
        rangeLabel={cycleRangeLabel(outgoingDays.fromDay, outgoingDays.toDay)}
        isLoading={outgoing.isLoading || outgoing.isPlaceholderData}
        error={outgoing.isError ? formatApiError(outgoing.error, 'No se pudo leer') : null}
        total={outgoing.data?.total ?? null}
        rows={outgoing.data?.items ?? []}
      />
      <PreviewSection
        heading="Entra en el ciclo nuevo"
        subheading={`Primeros movimientos · ${cycleLabel(cycleStartDay, incomingAnchor)}`}
        rangeLabel={cycleRangeLabel(incomingDays.fromDay, incomingDays.toDay)}
        isLoading={incoming.isLoading || incoming.isPlaceholderData}
        error={incoming.isError ? formatApiError(incoming.error, 'No se pudo leer') : null}
        total={incoming.data?.total ?? null}
        rows={incoming.data?.items ?? []}
        highlighted
      />
    </View>
  );
}

interface PreviewSectionProps {
  heading: string;
  subheading: string;
  rangeLabel: string;
  isLoading: boolean;
  error: string | null;
  total: number | null;
  rows: Transaction[];
  /** El ciclo entrante se marca: es el lado que el usuario está estrenando. */
  highlighted?: boolean;
}

function PreviewSection({
  heading,
  subheading,
  rangeLabel,
  isLoading,
  error,
  total,
  rows,
  highlighted = false,
}: PreviewSectionProps) {
  return (
    <View style={[styles.section, highlighted && styles.sectionHighlighted]}>
      <Text style={[styles.sectionHeading, highlighted && styles.sectionHeadingHighlighted]}>
        {heading}
      </Text>
      <Text style={styles.sectionMeta}>{subheading}</Text>
      <Text style={styles.sectionMeta}>{rangeLabel}</Text>

      {isLoading ? (
        <Text style={styles.loading}>Cargando movimientos…</Text>
      ) : error ? (
        <Text style={styles.error} accessibilityRole="alert">
          {error}
        </Text>
      ) : (
        <>
          <Text style={styles.count}>{movementCountLabel(total)}</Text>
          {rows.length === 0 ? (
            <Text style={styles.empty}>Ningún movimiento en este tramo.</Text>
          ) : (
            <View style={styles.rows}>
              {rows.map((tx) => (
                <PreviewRow key={tx.id} tx={tx} />
              ))}
            </View>
          )}
        </>
      )}
    </View>
  );
}

/** «N movimientos caen en este ciclo», con el singular bien dicho. */
function movementCountLabel(total: number | null): string {
  if (total === null) return 'Sin datos del recuento.';
  // Misma frase que en web. La decide `pluralize` en vez de un ternario para
  // que el verbo y el sustantivo no puedan discrepar («1 movimiento caen»).
  return `${withCount(total, 'movimiento', 'movimientos')} ${pluralize(
    total,
    'cae',
    'caen',
  )} en este ciclo`;
}

function PreviewRow({ tx }: { tx: Transaction }) {
  // El color sale de `flow`, que es la fuente de verdad del dinero (ADR-0004),
  // no de la categoría. Un movimiento sin clasificar se pinta neutro en vez de
  // fingir una dirección.
  const tone =
    tx.flow === 'IN' ? colors.income : tx.flow === 'OUT' ? colors.expense : colors.textMuted;
  return (
    <View style={styles.row}>
      <View style={styles.rowMain}>
        <Text style={styles.rowDate}>{formatCivilDate(tx.occurred_at)}</Text>
        <Text style={styles.rowDescription} numberOfLines={1}>
          {tx.description ?? '(sin descripción)'}
        </Text>
      </View>
      <Text style={[styles.rowAmount, { color: tone }]}>
        {formatAmount(tx.amount, tx.currency)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  intro: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    lineHeight: 18,
    marginBottom: spacing.md,
  },
  section: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceMuted,
    padding: spacing.md,
    marginBottom: spacing.md,
    gap: spacing.xs,
  },
  sectionHighlighted: { borderColor: colors.primary },
  sectionHeading: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  sectionHeadingHighlighted: { color: colors.primary },
  sectionMeta: { fontSize: fontSize.xs, color: colors.textMuted },
  loading: { marginTop: spacing.sm, fontSize: fontSize.sm, color: colors.textMuted },
  error: { marginTop: spacing.sm, fontSize: fontSize.sm, color: colors.danger },
  count: {
    marginTop: spacing.xs,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  empty: { marginTop: spacing.xs, fontSize: fontSize.sm, color: colors.textMuted },
  rows: { marginTop: spacing.xs },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  rowMain: { flex: 1, minWidth: 0 },
  rowDate: { fontSize: fontSize.xs, color: colors.textMuted },
  rowDescription: { fontSize: fontSize.sm, color: colors.text },
  rowAmount: { fontSize: fontSize.sm, fontWeight: fontWeight.medium },
});
