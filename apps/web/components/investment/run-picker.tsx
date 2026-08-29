'use client';

import { colors, fontSize, fontWeight, radius, spacing, layout } from '@crisol/ui';
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
  onCompare: (id: string) => void;
}

export function RunPicker({ runs, selectedId, compareId, onSelect, onCompare }: RunPickerProps) {
  if (runs.length === 0) return null;
  // Sin selección explícita, el actual es el más reciente: es el que la página
  // está enseñando.
  const current = runs.find((r) => r.id === selectedId) ?? runs[0];

  return (
    <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
      <CardTitle size="sm">Análisis guardados</CardTitle>
      <p
        style={{
          margin: 0,
          maxWidth: layout.prose,
          color: colors.textMuted,
          fontSize: fontSize.sm,
          lineHeight: 1.6,
        }}
      >
        Cada análisis es una foto: se conserva tal y como se calculó. Elige cuál miras y contra cuál
        lo comparas.
      </p>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: spacing.xs }}>
        {runs.map((item) => {
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
              {isCurrent ? null : (
                <button
                  type="button"
                  onClick={() => onCompare(item.id)}
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
                    comparable
                      ? 'Comparar el actual contra éste'
                      : versionsKnown
                        ? 'Se calcularon con distinto método: la comparación sólo dirá qué cambió del motor, no de la empresa'
                        : 'No se sabe con qué calibración se calculó: la comparabilidad no se puede afirmar'
                  }
                >
                  {isBase ? 'comparando' : 'comparar'}
                  {comparable ? '' : ' ⚠'}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
