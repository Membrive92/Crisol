'use client';

import Link from 'next/link';

import {
  colors,
  distanceSentence,
  fontSize,
  fontWeight,
  orderedSignals,
  originSentence,
  spacing,
} from '@crisol/ui';
import type { QuestionSignal, ReportSignal, ThresholdSpec } from '@crisol/types';

import { BandChip } from './band-chip';
import { formatMetricValue, formatThreshold } from '@crisol/ui';
import { effectiveThreshold, type CatalogIndex } from '@crisol/ui';

export interface SignalTableProps {
  signals: QuestionSignal[];
  catalog: CatalogIndex;
  thresholdsUsed: Record<string, ThresholdSpec> | undefined;
  /**
   * La capa de lectura de ESTA pregunta (PHASE-44.24.C): distancia al corte,
   * orden por severidad y procedencia. Ausente en un backend anterior, y
   * entonces la tabla se comporta como antes.
   */
  report?: Map<string, ReportSignal> | undefined;
  /** Perfil efectivo de umbrales, para poder nombrarlo. */
  profile?: string | undefined;
  /**
   * A dónde lleva cada señal (PHASE-44.24.C.4). Lo compone la PÁGINA, que es la
   * única que lee la URL: meter aquí un hook de `next/navigation` haría que
   * `useRouter` lanzara en los tests —que montan esta tabla sin router— y, peor,
   * que `usePathname` devolviera `null` fuera del App Router y se pintaran
   * enlaces a `"null?tab=…"` sin que ningún test se cayera.
   */
  hrefFor?: ((signal: QuestionSignal) => string | null) | undefined;
}

/**
 * Las señales candidatas de una pregunta, con su valor, su banda y su corte.
 *
 * Enseña TODAS, no sólo las que salieron mal: saber qué se comprobó y salió bien
 * es la otra mitad del porqué. Las que no puntuaron van en gris con su motivo —
 * antes de PHASE-44.9 ni siquiera viajaban, y las que sí lo hacían llegaban como
 * la clave cruda (`B4_dividend_funded_externally`).
 */
export function SignalTable({
  signals,
  catalog,
  thresholdsUsed,
  report,
  profile,
  hrefFor,
}: SignalTableProps) {
  // Lista VACÍA, no ausente: el motor publicó el desglose y esta pregunta no
  // tuvo ninguna señal candidata. El caso «motor anterior» lo atiende
  // `LegacySignals`, donde la clave ni siquiera existe.
  if (signals.length === 0) {
    return (
      <p style={{ margin: 0, color: colors.textSubtle, fontSize: fontSize.xs }}>
        Esta pregunta no evaluó ninguna señal.
      </p>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      {/* `minWidth` 560: con 320 las cinco columnas se apretaban a 390 px y
          «a 0,3 puntos del corte» se partía en cuatro líneas. Con 560 la tabla
          hace scroll dentro de su contenedor, que es lo que hacen las matrices.
          La columna «Distancia» sólo existe si el servidor mandó la capa de
          lectura: sin ella salía entera en «—», que se lee como «no se pudo
          calcular» para cada señal. */}
      <table
        style={{ width: '100%', borderCollapse: 'collapse', fontSize: fontSize.xs, minWidth: 560 }}
      >
        <thead>
          <tr>
            <th style={headStyle('left')}>Señal</th>
            <th style={headStyle('right')}>Valor</th>
            <th style={headStyle('right')}>Banda</th>
            {report ? <th style={headStyle('left')}>Distancia</th> : null}
            <th style={headStyle('left')}>¿Puntúa?</th>
          </tr>
        </thead>
        <tbody>
          {orderedSignals(signals, report ? [...report.values()] : undefined).map((signal) => {
            const definition = effectiveThreshold(
              signal.key,
              thresholdsUsed,
              catalog.definition(signal.key),
            );
            const threshold = formatThreshold(definition);
            const read = report?.get(signal.key);
            const distance = distanceSentence(read?.distance, definition?.unit);
            const origin = read ? originSentence(read.threshold_origin, profile) : null;
            return (
              <tr key={signal.key}>
                <td style={cellStyle('left', signal.counted)}>
                  {(() => {
                    const href = hrefFor?.(signal) ?? null;
                    // `Link` y no `<a>`: un `<a>` plano hace una navegación
                    // COMPLETA —parpadeo y skeletons en cada clic—; `Link`
                    // cambia la URL en cliente y la página reacciona a los
                    // params. Un hash (`#ancla`) también pasa por aquí.
                    return href ? (
                      <Link href={href} style={{ color: 'inherit' }}>
                        {signal.label}
                      </Link>
                    ) : (
                      signal.label
                    );
                  })()}
                  {threshold ? (
                    <span
                      style={{
                        display: 'block',
                        color: colors.textSubtle,
                        fontSize: fontSize.xs,
                      }}
                    >
                      {threshold}
                      {/* La procedencia va pegada al corte y no en una columna
                          propia: sin ella, dos empresas con cortes distintos
                          parecen un bug del informe. */}
                      {origin ? ` · ${origin}` : ''}
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
                {report ? (
                  <td style={cellStyle('left', signal.counted)}>
                    {distance ? (
                      <span style={{ color: colors.textMuted }}>{distance}</span>
                    ) : (
                      <span style={{ color: colors.textSubtle }}>—</span>
                    )}
                </td>
                ) : null}
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
