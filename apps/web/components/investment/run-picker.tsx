'use client';

import {
  colors,
  fontSize,
  fontWeight,
  radius,
  RUN_HISTORY_COPY,
  spacing,
  layout,
} from '@crisol/ui';
import type { AnalysisRunSummary } from '@crisol/types';

import { Card, CardTitle } from '@/components/ui/card';

/**
 * El histórico de análisis de un valor (PHASE-44.24.F).
 *
 * `useAnalysisRuns` existía desde 44.7 sin ningún consumidor: los análisis se
 * guardaban todos y no había forma de abrir uno que no fuera el último.
 *
 * Cada fila declara si es COMPARABLE con la seleccionada. Sin esa etiqueta, el
 * usuario elegiría dos runs de motores distintos esperando ver qué hizo la
 * empresa y recibiría una pantalla vacía sin entender por qué.
 */
export interface RunPickerProps {
  runs: AnalysisRunSummary[];
  selectedId: string | null;
  compareId: string | null;
  onSelect: (id: string) => void;
  /**
   * Elegir contra cuál se compara, y `null` para DEJAR de comparar.
   *
   * El `null` no es cosmético: sin él la comparación era de un solo sentido —
   * se entraba pulsando «comparar» y no había ningún gesto para salir, así que
   * el estado se quedaba pegado hasta editar la URL a mano.
   */
  onCompare: (id: string | null) => void;
}

export function RunPicker({ runs, selectedId, compareId, onSelect, onCompare }: RunPickerProps) {
  if (runs.length === 0) return null;
  // Sin selección explícita, el actual es el más reciente: es el que la página
  // está enseñando.
  const current = runs.find((r) => r.id === selectedId) ?? runs[0];

  // Las filas se resuelven ANTES de pintar para poder derivar la leyenda de lo
  // que de verdad sale en pantalla: explicar un ⚠ que hoy no lleva ninguna fila
  // es ruido, y no explicarlo cuando sí lo llevan deja un símbolo mudo.
  const rows = runs.map((item) => {
    const isCurrent = item.id === current?.id;
    const isBase = item.id === compareId;
    // Dos análisis con distinto motor o distinta calibración no se pueden
    // comparar como empresa. `thresholds_version` puede faltar si el
    // backend es anterior a esta fase: entonces no se afirma nada.
    const versionsKnown =
      current?.thresholds_version !== undefined && item.thresholds_version !== undefined;
    const comparable =
      versionsKnown &&
      item.engine_version === current?.engine_version &&
      item.thresholds_version === current?.thresholds_version;
    return { item, isCurrent, isBase, versionsKnown, comparable };
  });
  // La MISMA condición que pinta el glifo, no una aproximación.
  const hayAvisos = rows.some(
    ({ isCurrent, isBase, comparable }) => !isCurrent && !isBase && !comparable,
  );

  return (
    <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
      <CardTitle size="sm">Análisis guardados</CardTitle>
      {/* Qué hace esta área, dicho en la propia área: el texto anterior
          («elige cuál miras y contra cuál lo comparas») nombraba los dos
          gestos sin decir qué producía ninguno, así que «comparar» sólo se
          entendía pulsándolo. Las frases vienen de `@crisol/ui` porque la
          guía «Cómo leer este informe» cuenta lo mismo. */}
      <p
        style={{
          margin: 0,
          maxWidth: layout.prose,
          color: colors.textMuted,
          fontSize: fontSize.sm,
          lineHeight: 1.6,
        }}
      >
        {RUN_HISTORY_COPY.intro} {RUN_HISTORY_COPY.open} {RUN_HISTORY_COPY.compare}
      </p>
      <p
        style={{
          margin: 0,
          maxWidth: layout.prose,
          color: colors.textSubtle,
          fontSize: fontSize.xs,
          lineHeight: 1.6,
        }}
      >
        {RUN_HISTORY_COPY.contents}
      </p>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: spacing.xs }}>
        {rows.map(({ item, isCurrent, isBase, versionsKnown, comparable }) => {
          return (
            <li
              key={item.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: spacing.sm,
                flexWrap: 'wrap',
                padding: spacing.xs,
                borderRadius: radius.sm,
                backgroundColor: isCurrent ? colors.primarySoft : 'transparent',
              }}
            >
              <button
                type="button"
                onClick={() => onSelect(item.id)}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  cursor: 'pointer',
                  color: colors.text,
                  fontSize: fontSize.sm,
                  fontWeight: isCurrent ? fontWeight.semibold : fontWeight.regular,
                }}
              >
                {new Date(item.run_date).toLocaleDateString('es-ES')} ·{' '}
                {item.years_covered.join(', ')}
              </button>
              <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
                motor {item.engine_version}
              </span>
              {/* La fila ACTUAL no ofrece comparar contra sí misma… salvo que
                  ya sea la base (una URL con `run` y `compare` iguales, o
                  pegada de otro sitio): ahí el servidor responde «no se puede
                  comparar un análisis consigo mismo» y sin este botón el
                  usuario se queda con el error y sin ningún gesto para
                  quitarlo. */}
              {isCurrent && !isBase ? null : (
                <button
                  type="button"
                  aria-pressed={isBase}
                  onClick={() => onCompare(isBase ? null : item.id)}
                  style={{
                    marginLeft: 'auto',
                    background: 'none',
                    border: `1px solid ${isBase ? colors.primary : colors.border}`,
                    borderRadius: radius.sm,
                    color: isBase ? colors.primary : colors.textMuted,
                    fontSize: fontSize.xs,
                    padding: `2px ${spacing.sm}px`,
                    cursor: 'pointer',
                  }}
                  title={
                    isBase
                      ? 'Dejar de comparar contra éste'
                      : comparable
                        ? 'Comparar el actual contra éste'
                        : versionsKnown
                          ? 'Se calcularon con distinto método: la comparación sólo dirá qué cambió del motor, no de la empresa'
                          : 'No se sabe con qué calibración se calculó: la comparabilidad no se puede afirmar'
                  }
                >
                  {/* El botón dice la ACCIÓN, no el estado: «comparando» se lee
                      como un progreso en curso y no anuncia que pulsándolo se
                      sale. El estado ya lo dice el resaltado (y `aria-pressed`,
                      para quien no lo ve). */}
                  {isBase ? 'dejar de comparar' : 'comparar'}
                  {isBase || comparable ? '' : ' ⚠'}
                </button>
              )}
            </li>
          );
        })}
      </ul>
      {hayAvisos ? (
        <p
          style={{
            margin: 0,
            maxWidth: layout.prose,
            color: colors.textSubtle,
            fontSize: fontSize.xs,
            lineHeight: 1.6,
          }}
        >
          {RUN_HISTORY_COPY.incomparable}
        </p>
      ) : null}
    </Card>
  );
}
