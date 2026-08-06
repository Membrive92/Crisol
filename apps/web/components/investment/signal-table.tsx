'use client';

import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';
import type { QuestionSignal, ThresholdSpec } from '@crisol/types';

import { BandChip } from './band-chip';
import { formatMetricValue, formatThreshold } from './metric-format';
import { effectiveThreshold, type CatalogIndex } from './metric-index';

export interface SignalTableProps {
  signals: QuestionSignal[];
  catalog: CatalogIndex;
  thresholdsUsed: Record<string, ThresholdSpec> | undefined;
}

/**
 * Las señales candidatas de una pregunta, con su valor, su banda y su corte.
 *
 * Enseña TODAS, no sólo las que salieron mal: saber qué se comprobó y salió bien
 * es la otra mitad del porqué. Las que no puntuaron van en gris con su motivo —
 * antes de PHASE-44.9 ni siquiera viajaban, y las que sí lo hacían llegaban como
 * la clave cruda (`B4_dividend_funded_externally`).
 */
export function SignalTable({ signals, catalog, thresholdsUsed }: SignalTableProps) {
  if (signals.length === 0) {
    return (
      <p style={{ margin: 0, color: colors.textSubtle, fontSize: fontSize.xs }}>
        Este análisis se ejecutó antes de que el motor publicara las señales. Vuelve a
        ejecutarlo para ver el desglose.
      </p>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{ width: '100%', borderCollapse: 'collapse', fontSize: fontSize.xs, minWidth: 320 }}
      >
        <thead>
          <tr>
            <th style={headStyle('left')}>Señal</th>
            <th style={headStyle('right')}>Valor</th>
            <th style={headStyle('right')}>Banda</th>
            <th style={headStyle('left')}>¿Puntúa?</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((signal) => {
            const definition = effectiveThreshold(
              signal.key,
              thresholdsUsed,
              catalog.definition(signal.key),
            );
            const threshold = formatThreshold(definition);
            return (
              <tr key={signal.key}>
                <td style={cellStyle('left', signal.counted)}>
                  {signal.label}
                  {threshold ? (
                    <span
                      style={{
                        display: 'block',
                        color: colors.textSubtle,
                        fontSize: fontSize.xs,
                      }}
                    >
                      {threshold}
                    </span>
                  ) : null}
                </td>
                <td style={cellStyle('right', signal.counted)}>
                  {signal.kind === 'metric'
                    ? formatMetricValue(signal.value, definition?.unit)
                    : '—'}
                </td>
                <td style={{ ...cellStyle('right', signal.counted), whiteSpace: 'nowrap' }}>
                  <BandChip band={signal.band} />
                </td>
                <td style={cellStyle('left', signal.counted)}>
                  {signal.counted ? (
                    <span style={{ color: colors.text }}>sí</span>
                  ) : (
                    <span style={{ color: colors.textSubtle }}>no · {signal.reason}</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function headStyle(align: 'left' | 'right') {
  return {
    textAlign: align,
    padding: `${spacing.xs}px ${spacing.sm}px`,
    borderBottom: `1px solid ${colors.border}`,
    color: colors.textMuted,
    fontWeight: fontWeight.semibold,
    whiteSpace: 'nowrap' as const,
  };
}

function cellStyle(align: 'left' | 'right', counted: boolean) {
  return {
    textAlign: align,
    padding: `${spacing.xs}px ${spacing.sm}px`,
    borderBottom: `1px solid ${colors.border}`,
    color: counted ? colors.text : colors.textMuted,
    verticalAlign: 'top' as const,
    fontVariantNumeric: 'tabular-nums' as const,
  };
}
