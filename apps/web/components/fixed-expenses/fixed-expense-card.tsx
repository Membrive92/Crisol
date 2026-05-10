'use client';

import type { Account, Category, FixedExpense } from '@finanzas/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  radius,
  spacing,
} from '@finanzas/ui';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export interface FixedExpenseCardProps {
  fixedExpense: FixedExpense;
  categories: Category[];
  /** PHASE-19.1 — cuentas disponibles para asignar al cobro. */
  accounts?: Account[];
  /** Acción primaria (Confirmar para pending, Pausar para confirmed, etc.). */
  primaryAction?: { label: string; onClick: () => void; busy?: boolean };
  /** Acción secundaria (Descartar para pending, Cancelar para confirmed, etc.). */
  secondaryAction?: { label: string; onClick: () => void; busy?: boolean; danger?: boolean };
  /** PHASE-17.2 — toggle de auto-post. Sólo se muestra cuando el caller pasa el handler. */
  onToggleAutoPost?: (id: string, next: boolean) => void;
  autoPostBusy?: boolean;
  /** PHASE-19.1 — handler para cambiar la cuenta de cobro. Si null, se desactiva el autopost. */
  onChangeAccount?: (id: string, accountId: string | null) => void;
  accountBusy?: boolean;
}

const CADENCE_LABEL: Record<number, string> = {
  7: 'Semanal',
  14: 'Quincenal',
  30: 'Mensual',
  90: 'Trimestral',
  180: 'Semestral',
  365: 'Anual',
};

function findCategory(categories: Category[], id: string | null): Category | undefined {
  if (!id) return undefined;
  return categories.find((c) => c.id === id);
}

/**
 * Card de un gasto fijo detectado. Reusable entre las secciones
 * pending/confirmed/paused/cancelled/dismissed — los callers
 * controlan qué acciones ofrecer.
 */
export function FixedExpenseCard({
  fixedExpense: item,
  categories,
  accounts,
  primaryAction,
  secondaryAction,
  onToggleAutoPost,
  autoPostBusy,
  onChangeAccount,
  accountBusy,
}: FixedExpenseCardProps) {
  const category = findCategory(categories, item.category_id);
  const cadenceLabel = CADENCE_LABEL[item.cadence_days] ?? `${item.cadence_days}d`;
  const confidencePct = Math.round(item.confidence * 100);
  const accountList = accounts ?? [];
  const showAccountSelector = onChangeAccount !== undefined && accountList.length > 0;

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
        <div style={{ flex: 1, minWidth: 0 }}>
          <span
            style={{
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              display: 'block',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {item.raw_description}
          </span>
          <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
            {cadenceLabel} · {category?.name ?? 'Sin categoría'} · confianza{' '}
            {confidencePct}%
          </span>
        </div>
        <span
          style={{
            fontSize: fontSize.md,
            fontWeight: fontWeight.semibold,
            color: colors.text,
            fontVariantNumeric: 'tabular-nums',
            whiteSpace: 'nowrap',
          }}
        >
          {formatAmount(item.amount, item.currency)}
        </span>
      </div>

      {showAccountSelector ? (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: spacing.xs,
            paddingTop: spacing.xs,
            borderTop: `1px solid ${colors.border}`,
            marginTop: spacing.xs,
            fontSize: fontSize.xs,
            color: colors.textMuted,
          }}
        >
          <label
            htmlFor={`fixed-expense-${item.id}-account`}
            style={{ fontWeight: fontWeight.medium }}
          >
            Cuenta:
          </label>
          <select
            id={`fixed-expense-${item.id}-account`}
            value={item.account_id ?? ''}
            onChange={(e) => {
              const next = e.target.value;
              onChangeAccount(item.id, next ? next : null);
            }}
            disabled={accountBusy}
            style={{
              padding: `2px ${spacing.xs}px`,
              borderRadius: radius.sm,
              border: `1px solid ${colors.border}`,
              backgroundColor: colors.surface,
              color: colors.text,
              fontSize: fontSize.xs,
            }}
          >
            <option value="">— Sin cuenta —</option>
            {accountList.map((a) => (
              <option key={a.id} value={a.id}>
                {a.icon ? `${a.icon} ` : ''}
                {a.name} ({a.currency})
              </option>
            ))}
          </select>
          {item.account_id === null ? (
            <span style={{ color: colors.warning }}>
              Sin cuenta — el autopost no funcionará.
            </span>
          ) : null}
        </div>
      ) : null}

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: spacing.sm,
          padding: `${spacing.xs}px 0`,
          borderTop: showAccountSelector ? 'none' : `1px solid ${colors.border}`,
          marginTop: spacing.xs,
        }}
      >
        <div style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
          Próximo cargo:{' '}
          <strong style={{ color: colors.text, fontWeight: fontWeight.medium }}>
            {formatDate(item.next_due)}
          </strong>{' '}
          · {item.occurrence_count}{' '}
          {item.occurrence_count === 1 ? 'cargo' : 'cargos'} detectados
          {onToggleAutoPost ? (
            <>
              {' · '}
              <label
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  cursor: autoPostBusy ? 'wait' : 'pointer',
                  color: item.auto_post ? colors.primary : colors.textMuted,
                  fontWeight: item.auto_post ? fontWeight.semibold : fontWeight.medium,
                }}
              >
                <input
                  type="checkbox"
                  checked={item.auto_post}
                  onChange={(e) => onToggleAutoPost(item.id, e.target.checked)}
                  disabled={autoPostBusy || item.account_id === null}
                  style={{ margin: 0 }}
                  title={item.account_id === null ? 'Asigna una cuenta primero' : undefined}
                />
                Auto-añadir
              </label>
            </>
          ) : null}
        </div>
        <div style={{ display: 'inline-flex', gap: spacing.xs }}>
          {secondaryAction ? (
            <Button
              variant="ghost"
              onClick={secondaryAction.onClick}
              disabled={secondaryAction.busy}
              style={{
                padding: `4px ${spacing.sm}px`,
                color: secondaryAction.danger ? colors.danger : colors.text,
                borderColor: colors.border,
                borderRadius: radius.sm,
              }}
            >
              {secondaryAction.busy ? '…' : secondaryAction.label}
            </Button>
          ) : null}
          {primaryAction ? (
            <Button
              onClick={primaryAction.onClick}
              disabled={primaryAction.busy}
              style={{ padding: `4px ${spacing.sm + 2}px` }}
            >
              {primaryAction.busy ? '…' : primaryAction.label}
            </Button>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
