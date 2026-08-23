'use client';

import { useState } from 'react';

import {
  formatApiError,
  useConvertToDebt,
  useFinancingMatches,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type { FinancingMatch } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatCivilDate,
  radius,
  spacing,
} from '@crisol/ui';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { AlertTriangleIcon } from '@/components/ui/icons';

/**
 * PHASE-46 — Abonos que son una financiación, no un ingreso.
 *
 * Cuando el banco aplaza un recibo te ABONA el importe y nace una deuda. Si ese
 * abono se queda suelto, la app lo cuenta como ingreso del mes (infla la
 * gráfica, la tasa de ahorro y el patrimonio a la vez) y la deuda que el
 * usuario dio de alta se queda sin el movimiento que la originó.
 *
 * La propuesta reconoce la pareja por el CAPITAL del cuadro de amortización y
 * no por la redacción del extracto: el banco ya la ha cambiado dos veces
 * («Operacion financiada» → «Recibo anterior … Otras financiaciones») y cada
 * cambio coló un ingreso que nadie cobró. El capital, en cambio, es el mismo
 * importe por definición.
 *
 * Sólo propone. Confirmar cambia dónde vive ese dinero —sale del ingreso del
 * mes y pasa a ser deuda—, y eso es una afirmación sobre la vida del usuario,
 * no sobre sus datos.
 */
export function FinancingMatchesSection() {
  const { data, isLoading } = useFinancingMatches();
  const items = data ?? [];

  if (isLoading || items.length === 0) return null;

  return (
    <Card
      style={{
        padding: spacing.lg,
        backgroundColor: colors.warningSoft,
        border: `1px solid ${colors.warning}`,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.md,
      }}
    >
      <header style={{ display: 'flex', alignItems: 'flex-start', gap: spacing.sm }}>
        <span aria-hidden style={{ color: colors.warning, flex: '0 0 auto', marginTop: 2 }}>
          <AlertTriangleIcon size={18} />
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3
            style={{
              margin: 0,
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              letterSpacing: '-0.01em',
            }}
          >
            {items.length === 1
              ? 'Un abono parece una financiación, no un ingreso'
              : `${items.length} abonos parecen financiaciones, no ingresos`}
          </h3>
          <p
            style={{
              margin: `${spacing.xs}px 0 0`,
              fontSize: fontSize.sm,
              color: colors.text,
              lineHeight: 1.5,
            }}
          >
            Cuando el banco aplaza un recibo te abona el importe y nace una
            deuda: el dinero entra, pero no lo has ganado. Al confirmarlo sale
            de tus ingresos y pasa a colgar de su cuadro de amortización.
          </p>
        </div>
      </header>

      <ul
        style={{
          margin: 0,
          padding: 0,
          listStyle: 'none',
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.xs,
        }}
      >
        {items.map((item) => (
          <FinancingMatchRow key={item.transaction_id} item={item} />
        ))}
      </ul>
    </Card>
  );
}

function FinancingMatchRow({ item }: { item: FinancingMatch }) {
  const convertMutation = useConvertToDebt();
  const [done, setDone] = useState(false);

  function handleConfirm() {
    convertMutation.mutate(
      {
        source_transaction_id: item.transaction_id,
        destination_account_id: item.liability_id,
      },
      {
        onSuccess: () => {
          setDone(true);
          // Ya no se retira ningún "cargo espejo" (PHASE-47.F): el cobro que
          // compensa a este abono se queda vivo y las dos líneas se cancelan
          // solas en el saldo, que es lo que hace el extracto.
          toast.success(`Enlazado con «${item.liability_name}»: ya no cuenta como ingreso.`);
        },
        onError: (err) =>
          toast.error(formatApiError(err, 'No se pudo enlazar con la deuda')),
      },
    );
  }

  return (
    <li
      style={{
        display: 'flex',
        gap: spacing.sm,
        alignItems: 'center',
        padding: `${spacing.sm}px ${spacing.md}px`,
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.sm,
        opacity: done ? 0.55 : 1,
      }}
    >
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            gap: spacing.sm,
            fontSize: fontSize.sm,
            color: colors.text,
          }}
        >
          <span
            style={{
              flex: 1,
              minWidth: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              fontWeight: fontWeight.medium,
            }}
          >
            {formatCivilDate(item.occurred_at)} · {item.description ?? '(sin descripción)'}
          </span>
          <span
            style={{
              fontVariantNumeric: 'tabular-nums',
              fontWeight: fontWeight.semibold,
              whiteSpace: 'nowrap',
            }}
          >
            {formatAmount(item.amount, item.currency)}
          </span>
        </div>
        <div style={{ fontSize: 11, color: colors.textMuted, lineHeight: 1.4 }}>
          {item.counted_as_income ? (
            <>
              <strong style={{ color: colors.danger }}>
                Ahora suma como ingreso.
              </strong>{' '}
            </>
          ) : null}
          {item.reason}
        </div>
      </div>
      <Button
        type="button"
        variant="primary"
        onClick={handleConfirm}
        disabled={done || convertMutation.isPending}
      >
        {done
          ? 'Enlazado'
          : convertMutation.isPending
            ? 'Enlazando…'
            : 'Es una financiación'}
      </Button>
    </li>
  );
}
