'use client';

import { useState } from 'react';

import {
  formatApiError,
  useApplyDeferredCycle,
  useClearDeferredCycle,
  useDeferredCycle,
} from '@crisol/services';
import { toast } from '@crisol/store';
import { colors, fontSize, fontWeight, formatAmount, formatDate, radius, spacing } from '@crisol/ui';

import { Button } from '@/components/ui/button';

/**
 * PHASE-47.E — Declarar qué gasto aplazó un recibo financiado.
 *
 * El sistema INICIA y el usuario DECLARA (ADR-0011): el panel enseña la
 * aritmética completa —qué compras, por cuánto, si cuadra— antes de escribir
 * nada, y el botón sólo se enciende cuando el ciclo queda determinado.
 *
 * No se ofrece «aproximar»: marcar las que más se acerquen repartiría el gasto
 * entre categorías que no son las suyas. La única holgura es de redondeo, y
 * cuando se usa se DICE — un cierre por un céntimo es válido pero no es lo
 * mismo que uno exacto, y no puede presentarse igual.
 */
export function DeferredCyclePanel({
  liabilityId,
  currency,
}: {
  liabilityId: string;
  currency: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const preview = useDeferredCycle(expanded ? liabilityId : null);
  const applyMutation = useApplyDeferredCycle();
  const clearMutation = useClearDeferredCycle();

  const data = preview.data;
  const alreadyDeclared = data?.already_declared ?? false;

  async function handleApply() {
    try {
      const result = await applyMutation.mutateAsync(liabilityId);
      toast.success(
        `${result.purchases.length} compras marcadas como aplazadas por este recibo.`,
      );
    } catch (error) {
      toast.error(formatApiError(error, 'No se pudo declarar el aplazamiento.'));
    }
  }

  async function handleClear() {
    try {
      await clearMutation.mutateAsync(liabilityId);
      toast.success('Marca retirada: esas compras vuelven a contar como gasto del mes.');
    } catch (error) {
      toast.error(formatApiError(error, 'No se pudo retirar la marca.'));
    }
  }

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        style={{
          background: 'none',
          border: 'none',
          padding: 0,
          color: colors.primary,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.medium,
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        ¿Qué gasto aplazó este recibo?
      </button>
    );
  }

  return (
    <section
      data-testid="deferred-cycle-panel"
      style={{
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        padding: spacing.md,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.sm,
      }}
    >
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h4
          style={{
            margin: 0,
            fontSize: fontSize.sm,
            fontWeight: fontWeight.semibold,
            color: colors.text,
          }}
        >
          Gasto aplazado por este recibo
        </h4>
        <button
          type="button"
          onClick={() => setExpanded(false)}
          style={{
            background: 'none',
            border: 'none',
            color: colors.textMuted,
            fontSize: fontSize.xs,
            cursor: 'pointer',
          }}
        >
          Cerrar
        </button>
      </header>

      {preview.isLoading ? (
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>Buscando el ciclo…</p>
      ) : preview.isError ? (
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.danger }}>
          {formatApiError(preview.error, 'No se pudo consultar el ciclo.')}
        </p>
      ) : data ? (
        <>
          <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted, lineHeight: 1.5 }}>
            {data.reason}
          </p>

          {data.purchases.length > 0 ? (
            <ul
              style={{
                listStyle: 'none',
                margin: 0,
                padding: 0,
                maxHeight: 220,
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: spacing.xs / 2,
              }}
            >
              {data.purchases.map((p) => (
                <li
                  key={p.id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: spacing.sm,
                    fontSize: fontSize.xs,
                    color: colors.text,
                  }}
                >
                  <span
                    style={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {formatDate(p.occurred_at)} · {p.description ?? '(sin descripción)'}
                  </span>
                  {/* Una devolución viaja en negativo: el banco liquida el neto,
                      así que forma parte del ciclo igual que una compra. */}
                  <span style={{ flex: '0 0 auto', color: Number(p.amount) < 0 ? colors.success : colors.text }}>
                    {formatAmount(p.amount, currency)}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}

          <footer
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: spacing.sm,
              borderTop: `1px solid ${colors.border}`,
              paddingTop: spacing.sm,
            }}
          >
            <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
              Suman {formatAmount(data.total, currency)} · recibo{' '}
              {formatAmount(data.receipt_amount, currency)}
              {data.closes && !data.is_exact ? ' · cierra absorbiendo un redondeo' : ''}
            </span>
            {alreadyDeclared ? (
              <Button
                variant="secondary"
                onClick={handleClear}
                disabled={clearMutation.isPending}
              >
                {clearMutation.isPending ? 'Retirando…' : 'Retirar la marca'}
              </Button>
            ) : (
              <Button
                onClick={handleApply}
                disabled={!data.closes || applyMutation.isPending}
              >
                {applyMutation.isPending ? 'Marcando…' : 'Declarar el aplazamiento'}
              </Button>
            )}
          </footer>
        </>
      ) : null}
    </section>
  );
}
