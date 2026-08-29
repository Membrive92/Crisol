'use client';

import { colors, diffRows, fontSize, fontWeight, radius, spacing, layout } from '@crisol/ui';
import type { DiffRow } from '@crisol/ui';
import type { RunDiff } from '@crisol/types';

import { Card, CardTitle } from '@/components/ui/card';

import { DegradedPanel, InlineNotice } from './degraded-panel';

/**
 * Qué ha cambiado entre dos análisis (PHASE-44.24.F).
 *
 * La distinción que gobierna la pantalla: cuando el motor o la calibración
 * cambian, NO se listan cambios de la empresa. Enseñarlos «con un aviso»
 * invitaría a leer un corte movido como una degradación del negocio, que es la
 * conclusión contraria a la verdadera.
 */
export interface RunComparisonProps {
  diff: RunDiff | undefined;
  loading: boolean;
  /**
   * Por qué no hay comparación, YA en lenguaje del usuario. `null` si la hubo.
   *
   * NO es un booleano a propósito: el servidor distingue cuatro motivos
   * («hacen falta dos análisis», «ese análisis no pertenece a este valor», «es
   * el más antiguo», «no se puede comparar consigo mismo») y colapsarlos en
   * «todavía no hay con qué comparar» le da al usuario una explicación que
   * puede ser FALSA — y encima tapa un 500 o una red caída.
   *
   * Lo formatea la PÁGINA, que es quien habla con la capa HTTP.
   */
  reason: string | null;
}

export function RunComparison({ diff, loading, reason }: RunComparisonProps) {
  if (reason) {
    return <DegradedPanel title="No se ha podido comparar" reason={reason} />;
  }
  if (loading || !diff) {
    return (
      <Card>
        <CardTitle size="sm">Comparación</CardTitle>
        <p
          style={{ margin: `${spacing.sm}px 0 0`, color: colors.textMuted, fontSize: fontSize.sm }}
        >
          {loading ? 'Cargando…' : 'Sin comparación disponible.'}
        </p>
      </Card>
    );
  }

  const view = diffRows(diff);
  const fecha = (value: string | null) =>
    value ? new Date(value).toLocaleDateString('es-ES') : '—';

  return (
    <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <CardTitle size="sm">
        Qué ha cambiado · {fecha(diff.base_date)} → {fecha(diff.target_date)}
      </CardTitle>

      {view.caveat ? <InlineNotice>{view.caveat}</InlineNotice> : null}

      {view.methodChanges.length > 0 ? (
        <div style={{ color: colors.textMuted, fontSize: fontSize.sm, lineHeight: 1.6 }}>
          <strong style={{ color: colors.text }}>Cambió el método: </strong>
          {view.methodChanges.join('; ')}.
        </div>
      ) : null}

      {view.restatements.length > 0 ? (
        <InlineNotice>
          {/* Una reexpresión explica que los números se muevan SIN que la
              empresa publique un cierre nuevo. Sin esto, el cambio parecería
              del negocio. */}
          Entre las dos fechas la SEC registró reexpresiones: {view.restatements.join(' ')}
        </InlineNotice>
      ) : null}

      {view.unchanged ? (
        <p
          style={{
            margin: 0,
            maxWidth: layout.prose,
            color: colors.textMuted,
            fontSize: fontSize.sm,
            lineHeight: 1.6,
          }}
        >
          Nada se ha movido: mismo perfil, mismas bandas, mismas banderas. Los dos análisis se
          calcularon con el mismo motor y la misma calibración, así que la comparación es limpia.
        </p>
      ) : null}

      {view.rows.length > 0 ? (
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: spacing.sm }}>
          {view.rows.map((row) => (
            <DiffLine key={row.key} row={row} />
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

const DIRECTION_COLOR: Record<DiffRow['direction'], string> = {
  worse: colors.danger,
  better: colors.success,
  flat: colors.textMuted,
};

/** `→` con la dirección en color; el texto la repite para quien no ve el color. */
const DIRECTION_WORD: Record<DiffRow['direction'], string> = {
  worse: 'empeora',
  better: 'mejora',
  flat: 'cambia',
};

function DiffLine({ row }: { row: DiffRow }) {
  const tone = DIRECTION_COLOR[row.direction];
  return (
    <li
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: spacing.sm,
        flexWrap: 'wrap',
        paddingBottom: spacing.sm,
        borderBottom: `1px solid ${colors.border}`,
      }}
    >
      <span
        style={{
          color: tone,
          backgroundColor: colors.surface,
          borderRadius: radius.sm,
          padding: `0 ${spacing.xs}px`,
          fontSize: fontSize.xs,
          fontWeight: fontWeight.semibold,
        }}
      >
        {DIRECTION_WORD[row.direction]}
      </span>
      <span style={{ color: colors.text, fontSize: fontSize.sm, fontWeight: fontWeight.semibold }}>
        {row.label}
      </span>
      <span style={{ color: colors.textMuted, fontSize: fontSize.sm }}>
        {row.before ?? '—'} → <strong style={{ color: tone }}>{row.after ?? '—'}</strong>
      </span>
    </li>
  );
}
