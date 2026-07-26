'use client';

import { useState } from 'react';

import { SEARCH_MIN_LENGTH, useResolveSecurity, useSecuritySearch } from '@crisol/services';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';
import type { SecuritySearchHit } from '@crisol/types';

/**
 * Buscador estilo broker (PHASE-44.7). Busca en el catálogo local; si no hay
 * resultados, ofrece resolver el ticker tecleado contra EDGAR.
 *
 * El mercado lo decide el SERVIDOR (PHASE-44.8 E1): este componente ya no manda
 * `exchange`. Mandaba `'US'` —un país, no una plaza— y como la restricción única
 * del catálogo es `(ticker, exchange)`, el mismo valor podía acabar duplicado en
 * dos filas con dos ingestas y los lotes de cartera repartidos entre ambas.
 *
 * El buscador multi-mercado con fila rica (bolsa, divisa, tipo) llega en las
 * Entregas 3 y 5 de PHASE-44.8.
 */
export function SecuritySearch({
  onSelect,
  placeholder = 'Ticker o nombre (ej. MCD, Johnson & Johnson)',
}: {
  onSelect: (securityId: string) => void;
  placeholder?: string;
}) {
  const [q, setQ] = useState('');
  const search = useSecuritySearch(q);
  const resolve = useResolveSecurity();
  const query = q.trim();
  const results = search.data?.results ?? [];

  async function pick(hit: SecuritySearchHit): Promise<void> {
    if (hit.id) {
      onSelect(hit.id);
      return;
    }
    const security = await resolve.mutateAsync({ ticker: hit.ticker });
    onSelect(security.id);
  }

  async function resolveTyped(): Promise<void> {
    if (!query) return;
    const security = await resolve.mutateAsync({ ticker: query.toUpperCase() });
    onSelect(security.id);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={placeholder}
        style={{
          padding: `${spacing.sm}px ${spacing.md}px`,
          borderRadius: radius.md,
          border: `1px solid ${colors.border}`,
          backgroundColor: colors.surface,
          color: colors.text,
          fontSize: fontSize.md,
          outlineColor: colors.primary,
        }}
      />
      {resolve.isError ? (
        <span style={{ color: colors.danger, fontSize: fontSize.sm }}>
          No se pudo resolver el valor. Comprueba el ticker.
        </span>
      ) : null}
      {/* Con una sola letra no se busca (traería medio catálogo), pero callarse
          es peor: teclear y no ver NADA se lee como "está roto". */}
      {query.length > 0 && query.length < SEARCH_MIN_LENGTH ? (
        <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
          Escribe al menos {SEARCH_MIN_LENGTH} caracteres.
        </span>
      ) : null}
      {query.length >= SEARCH_MIN_LENGTH ? (
        <div
          style={{
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            backgroundColor: colors.surface,
            overflow: 'hidden',
          }}
        >
          {results.map((hit) => (
            <button
              key={`${hit.ticker}-${hit.exchange}`}
              type="button"
              onClick={() => void pick(hit)}
              disabled={resolve.isPending}
              style={{
                display: 'flex',
                width: '100%',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: spacing.md,
                padding: `${spacing.sm}px ${spacing.md}px`,
                border: 'none',
                borderBottom: `1px solid ${colors.border}`,
                backgroundColor: 'transparent',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <span style={{ color: colors.text, fontSize: fontSize.sm }}>
                <strong>{hit.ticker}</strong> · {hit.name}
              </span>
              {!hit.analysis_available ? (
                // "sin CIK" era jerga: al usuario no le dice nada. Lo que
                // importa es qué puede hacer con la fila.
                <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
                  sólo cartera
                </span>
              ) : null}
            </button>
          ))}
          {results.length === 0 && search.isFetching ? (
            // Sin esto, mientras llega la respuesta se pinta la escotilla de
            // EDGAR con la consulta a medio teclear, como si no hubiera nada.
            <span
              style={{
                display: 'block',
                padding: `${spacing.sm}px ${spacing.md}px`,
                color: colors.textSubtle,
                fontSize: fontSize.sm,
              }}
            >
              Buscando…
            </span>
          ) : null}
          {results.length === 0 && !search.isFetching ? (
            <button
              type="button"
              onClick={() => void resolveTyped()}
              disabled={resolve.isPending}
              style={{
                display: 'block',
                width: '100%',
                padding: `${spacing.sm}px ${spacing.md}px`,
                border: 'none',
                backgroundColor: 'transparent',
                color: colors.primary,
                fontSize: fontSize.sm,
                fontWeight: fontWeight.semibold,
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              {/* "Analizar" era falso en Cartera, donde lo que se está haciendo
                  es elegir el valor de una compra. "Traer" describe lo que hace
                  la acción —dar de alta el valor desde la SEC— y es cierto en las
                  dos pantallas. */}
              {resolve.isPending ? 'Buscando en EDGAR…' : `Traer «${query.toUpperCase()}» de EDGAR`}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
