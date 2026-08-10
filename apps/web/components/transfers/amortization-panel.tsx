'use client';

import { useEffect, useState } from 'react';

import {
  formatApiError,
  useAccounts,
  useAmortization,
  useAmortize,
  usePreviewAmortization,
  useUndoAmortization,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type { AmortizationEffect, Transaction } from '@crisol/types';
import {
  amortizationChoiceHint,
  amortizationChoiceLabel,
  amortizationEffectCopy,
  amortizationRegisteredCopy,
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Select } from '@/components/ui/field';

interface Props {
  transaction: Transaction;
}

/**
 * PHASE-45: bloque "¿Es una amortización?" del detalle de transacción.
 *
 * Enlaza un cargo del banco con la deuda que amortiza para que la deuda BAJE
 * — hasta ahora un `ADEUDO MENSUAL DE TARJETA` sacaba el dinero de la cuenta
 * corriente sin tocar el módulo de deuda.
 *
 * Dos decisiones distintas, y cada una la toma quien sabe:
 * - **Cómo baja la deuda** lo decide el pasivo (cuadro de cuotas vs. saldo
 *   arrastrado) y lo calcula el servidor; aquí sólo se enseña.
 * - **Si cuenta como gasto** lo decide el usuario, porque depende de si ese
 *   dinero ya se contó al comprar. El servidor sugiere con su motivo escrito.
 *
 * El efecto se previsualiza con el MISMO endpoint que lo aplica (`dry_run`),
 * así que lo que se promete en pantalla y lo que ocurre no pueden discrepar.
 */
export function AmortizationPanel({ transaction }: Props) {
  const accountsQuery = useAccounts();
  const stateQuery = useAmortization(transaction.id);
  const preview = usePreviewAmortization();
  const amortize = useAmortize();
  const undo = useUndoAmortization();

  const [liabilityId, setLiabilityId] = useState('');
  const [countsAsExpense, setCountsAsExpense] = useState<boolean | null>(null);
  const [effect, setEffect] = useState<AmortizationEffect | null>(null);

  const liabilities = (accountsQuery.data ?? []).filter(
    (a) =>
      a.nature === 'liability' &&
      !a.is_archived &&
      a.currency === transaction.currency &&
      a.id !== transaction.account_id,
  );

  // Al elegir una deuda, pedimos el efecto al servidor. La elección
  // gasto/neutro se resetea a "la que sugiere el servidor" porque la
  // sugerencia depende de la cuenta elegida.
  useEffect(() => {
    if (!liabilityId) {
      setEffect(null);
      return;
    }
    let cancelled = false;
    preview.mutate(
      {
        source_transaction_id: transaction.id,
        liability_account_id: liabilityId,
      },
      {
        onSuccess: (result) => {
          if (cancelled) return;
          setEffect(result);
          setCountsAsExpense(result.suggested_counts_as_expense);
        },
        onError: (err) => {
          if (cancelled) return;
          setEffect(null);
          toast.error(formatApiError(err, 'No se pudo calcular el efecto'));
        },
      },
    );
    return () => {
      cancelled = true;
    };
    // Sólo reaccionamos a la cuenta elegida: `preview` es estable y meterlo
    // en las deps relanzaría la consulta en cada render.
  }, [liabilityId, transaction.id]);

  const registered = stateQuery.data ?? null;

  function handleSubmit() {
    if (!liabilityId || countsAsExpense === null) return;
    amortize.mutate(
      {
        source_transaction_id: transaction.id,
        liability_account_id: liabilityId,
        counts_as_expense: countsAsExpense,
      },
      {
        onSuccess: (result) => {
          setLiabilityId('');
          setEffect(null);
          toast.success(
            `Amortización registrada: ${result.liability_account_name} baja a ` +
              `${formatAmount(result.outstanding_after, result.currency)}.`,
          );
        },
        onError: (err) =>
          toast.error(formatApiError(err, 'No se pudo registrar la amortización')),
      },
    );
  }

  function handleUndo() {
    undo.mutate(transaction.id, {
      onSuccess: () => toast.success('Registro deshecho: la deuda vuelve a subir.'),
      onError: (err) => toast.error(formatApiError(err, 'No se pudo deshacer')),
    });
  }

  return (
    <Card style={{ padding: spacing.lg }}>
      <h2 style={titleStyle}>¿Es una amortización?</h2>

      {stateQuery.isLoading ? (
        <p style={hintStyle}>Comprobando…</p>
      ) : registered ? (
        <>
          <p style={hintStyle}>
            {amortizationRegisteredCopy({
              mode: registered.mode,
              installmentsMarked: registered.installments_marked,
              liabilityName: registered.liability_account_name,
            })}
          </p>
          <dl style={factsStyle}>
            <Fact
              label="Capital amortizado"
              value={formatAmount(registered.principal_covered, registered.currency)}
            />
            <Fact
              label="Deuda ahora"
              value={formatAmount(registered.outstanding_after, registered.currency)}
            />
            <Fact
              label="Cuenta como gasto"
              value={registered.counts_as_expense ? 'Sí' : 'No'}
            />
          </dl>
          <Button type="button" variant="ghost" onClick={handleUndo} disabled={undo.isPending}>
            {undo.isPending ? 'Deshaciendo…' : 'Deshacer registro'}
          </Button>
        </>
      ) : liabilities.length === 0 ? (
        <p style={hintStyle}>
          No tienes cuentas de deuda en {transaction.currency} distintas de la de este
          movimiento.
        </p>
      ) : (
        <>
          <p style={hintStyle}>
            Si este cargo paga una deuda tuya, dilo aquí y la deuda bajará. Elige a cuál va.
          </p>
          <Select
            label="Deuda que amortiza"
            dense
            value={liabilityId}
            onChange={(e) => setLiabilityId(e.target.value)}
          >
            <option value="">Selecciona una deuda…</option>
            {liabilities.map((acc) => (
              <option key={acc.id} value={acc.id}>
                {acc.name}
              </option>
            ))}
          </Select>

          {preview.isPending ? (
            <p style={{ ...hintStyle, marginTop: spacing.md }}>Calculando el efecto…</p>
          ) : effect ? (
            <>
              {(() => {
                const copy = amortizationEffectCopy({
                  mode: effect.mode,
                  installmentsMarked: effect.installments_marked,
                  liabilityName: effect.liability_account_name,
                  principalCovered: effect.principal_covered,
                  outstandingBefore: effect.outstanding_before,
                  outstandingAfter: effect.outstanding_after,
                  currency: effect.currency,
                });
                return (
                  <div style={effectBoxStyle}>
                    <p style={copy.tone === 'warning' ? warnStyle : { margin: 0 }}>
                      {copy.headline}
                    </p>
                    <p style={{ margin: `${spacing.xs}px 0 0 0` }}>{copy.balanceLine}</p>
                  </div>
                );
              })()}

              <span style={choiceLabelStyle}>¿Cuenta como gasto?</span>
              <div style={choiceGroupStyle} role="group" aria-label="¿Cuenta como gasto?">
                {[true, false].map((option) => (
                  <button
                    key={String(option)}
                    type="button"
                    onClick={() => setCountsAsExpense(option)}
                    aria-pressed={countsAsExpense === option}
                    style={{
                      ...choiceBtnStyle,
                      ...(countsAsExpense === option ? choiceBtnActiveStyle : {}),
                    }}
                  >
                    {amortizationChoiceLabel(option)}
                  </button>
                ))}
              </div>
              <p style={reasonStyle}>
                {amortizationChoiceHint(
                  countsAsExpense,
                  effect.suggested_counts_as_expense,
                  effect.suggestion_reason,
                )}
              </p>

              <Button
                type="button"
                onClick={handleSubmit}
                disabled={amortize.isPending || countsAsExpense === null}
                style={{ marginTop: spacing.md }}
              >
                {amortize.isPending ? 'Registrando…' : 'Registrar amortización'}
              </Button>
            </>
          ) : null}
        </>
      )}
    </Card>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt style={{ fontSize: fontSize.xs, color: colors.textSubtle, margin: 0 }}>{label}</dt>
      <dd
        style={{
          margin: 0,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: colors.text,
        }}
      >
        {value}
      </dd>
    </div>
  );
}

const titleStyle = {
  margin: 0,
  marginBottom: spacing.xs,
  fontSize: fontSize.md,
  fontWeight: fontWeight.semibold,
  color: colors.text,
} as const;

const hintStyle = {
  margin: `0 0 ${spacing.md}px 0`,
  fontSize: fontSize.sm,
  color: colors.textMuted,
  lineHeight: 1.4,
} as const;

const factsStyle = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: spacing.md,
  margin: `0 0 ${spacing.md}px 0`,
} as const;

const effectBoxStyle = {
  marginTop: spacing.md,
  padding: spacing.sm,
  borderRadius: radius.sm,
  backgroundColor: colors.surfaceMuted,
  color: colors.textMuted,
  fontSize: fontSize.sm,
  lineHeight: 1.4,
} as const;

const warnStyle = {
  margin: 0,
  color: colors.warning,
} as const;

const choiceLabelStyle = {
  display: 'block',
  marginTop: spacing.md,
  marginBottom: spacing.xs,
  fontSize: fontSize.sm,
  fontWeight: fontWeight.medium,
  color: colors.text,
} as const;

const choiceGroupStyle = {
  display: 'flex',
  gap: spacing.xs,
} as const;

// Borde en longhand, no shorthand: el estado activo sólo sobreescribe
// `borderColor`, y mezclarlos hace que React avise al re-render.
const choiceBtnStyle = {
  flex: 1,
  padding: `${spacing.sm}px ${spacing.sm}px`,
  borderRadius: radius.sm,
  borderWidth: 1,
  borderStyle: 'solid',
  borderColor: colors.border,
  backgroundColor: colors.surface,
  color: colors.textMuted,
  fontSize: fontSize.sm,
  fontWeight: fontWeight.medium,
  cursor: 'pointer',
} as const;

const choiceBtnActiveStyle = {
  borderColor: colors.primary,
  backgroundColor: colors.primarySoft,
  color: colors.text,
  fontWeight: fontWeight.semibold,
} as const;

const reasonStyle = {
  margin: `${spacing.xs}px 0 0 0`,
  fontSize: fontSize.xs,
  color: colors.textSubtle,
  lineHeight: 1.4,
} as const;
