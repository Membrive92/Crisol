'use client';

import type { Account, TransferCandidate, TransferPair } from '@finanzas/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  radius,
  spacing,
} from '@finanzas/ui';

import { AccountSwatch } from '@/components/accounts/account-swatch';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ArrowLeftRightIcon } from '@/components/ui/icons';

export interface TransferPairCardProps {
  /**
   * Soporta tanto pares ya emparejados (`TransferPair` viene de
   * `useTransfers`) como sugerencias del matcher (`TransferCandidate`
   * viene de `useTransferCandidates`). Tienen forma idéntica.
   */
  pair: TransferPair | TransferCandidate;
  accounts: Account[];
  /**
   * Acción primaria. En "pares activos" es "Deshacer"; en sugerencias
   * es "Enlazar". El caller controla label, handler y estado busy.
   */
  primaryAction: {
    label: string;
    onClick: () => void;
    busy?: boolean;
    /** Variante visual de la acción (`ghost` para deshacer, `primary` para enlazar). */
    variant?: 'primary' | 'ghost' | 'secondary';
  };
}

/**
 * Card de un par de transferencia interna. Reusable entre la sección
 * "Pares activos" (`useTransfers`) y "Sugerencias pendientes"
 * (`useTransferCandidates`) — sólo cambia la acción primaria.
 *
 * Layout:
 *   [importe + currency]                     [acción]
 *   [⇄ icono]  out: cuenta A · fecha
 *              in:  cuenta B · fecha · Δ X días
 */
export function TransferPairCard({
  pair,
  accounts,
  primaryAction,
}: TransferPairCardProps) {
  const outAccount = accounts.find((a) => a.id === pair.out_account_id);
  const inAccount = accounts.find((a) => a.id === pair.in_account_id);

  return (
    <Card style={{ padding: spacing.md }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: spacing.sm,
          marginBottom: spacing.sm,
        }}
      >
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: spacing.sm,
            minWidth: 0,
          }}
        >
          <span
            aria-hidden
            style={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              backgroundColor: colors.primarySoft,
              color: colors.primary,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              flex: '0 0 auto',
            }}
          >
            <ArrowLeftRightIcon size={16} />
          </span>
          <span
            style={{
              fontSize: fontSize.lg,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              fontVariantNumeric: 'tabular-nums',
              whiteSpace: 'nowrap',
            }}
          >
            {formatAmount(pair.amount, pair.currency)}
          </span>
        </div>
        <Button
          variant={primaryAction.variant ?? 'primary'}
          onClick={primaryAction.onClick}
          disabled={primaryAction.busy}
        >
          {primaryAction.busy ? '…' : primaryAction.label}
        </Button>
      </div>

      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.xs,
          paddingTop: spacing.xs,
          borderTop: `1px solid ${colors.border}`,
        }}
      >
        <Leg
          arrow="↑"
          arrowColor={colors.expense}
          legend="Salida desde"
          accountName={outAccount?.name ?? 'Cuenta desconocida'}
          accountColor={outAccount?.color ?? null}
          accountIcon={outAccount?.icon ?? null}
          when={pair.out_occurred_at}
        />
        <Leg
          arrow="↓"
          arrowColor={colors.income}
          legend="Entrada en"
          accountName={inAccount?.name ?? 'Cuenta desconocida'}
          accountColor={inAccount?.color ?? null}
          accountIcon={inAccount?.icon ?? null}
          when={pair.in_occurred_at}
          deltaDays={pair.delta_days}
        />
      </div>
    </Card>
  );
}

function Leg({
  arrow,
  arrowColor,
  legend,
  accountName,
  accountColor,
  accountIcon,
  when,
  deltaDays,
}: {
  arrow: string;
  arrowColor: string;
  legend: string;
  accountName: string;
  accountColor: string | null;
  accountIcon: string | null;
  when: string;
  deltaDays?: number;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.xs,
        fontSize: fontSize.sm,
        color: colors.text,
      }}
    >
      <span
        aria-hidden
        style={{
          color: arrowColor,
          fontWeight: fontWeight.bold,
          width: 16,
          textAlign: 'center',
          flex: '0 0 auto',
        }}
      >
        {arrow}
      </span>
      <span
        style={{
          fontSize: fontSize.xs,
          color: colors.textMuted,
          flex: '0 0 auto',
        }}
      >
        {legend}
      </span>
      <AccountSwatch color={accountColor} icon={accountIcon} size={20} />
      <span
        style={{
          fontWeight: fontWeight.medium,
          minWidth: 0,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {accountName}
      </span>
      <span
        style={{
          marginLeft: 'auto',
          fontSize: fontSize.xs,
          color: colors.textMuted,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        {formatDate(when)}
        {deltaDays !== undefined && deltaDays > 0 ? (
          <span
            style={{
              marginLeft: spacing.xs,
              padding: `1px ${spacing.xs}px`,
              borderRadius: radius.sm,
              backgroundColor: colors.surfaceMuted,
              color: colors.textMuted,
              fontSize: 11,
              fontWeight: fontWeight.semibold,
            }}
          >
            Δ {deltaDays}d
          </span>
        ) : null}
      </span>
    </div>
  );
}
