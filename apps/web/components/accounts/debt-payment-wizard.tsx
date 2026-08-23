'use client';

import { useEffect, useMemo, useState } from 'react';

import {
  formatApiError,
  useAccounts,
  useAmortizationSchedule,
  useCategories,
  useCreateTransaction,
  useLinkTransfer,
  todayDayStr,
  usePayInstallments,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type { Account, AccountType, AmortizationRow } from '@crisol/types';
import { ASSET_ACCOUNT_TYPES } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  fromDateInputValue,
  radius,
  spacing,
} from '@crisol/ui';

import { Button } from '@/components/ui/button';
import { Select, TextInput } from '@/components/ui/field';

export interface DebtPaymentWizardProps {
  liabilityAccount: Account;
  open: boolean;
  onClose: () => void;
}

const INTEREST_CATEGORY_BY_TYPE: Partial<Record<AccountType, string>> = {
  mortgage: 'Intereses hipoteca',
  loan: 'Intereses préstamo',
  credit_card: 'Intereses tarjeta',
};

/**
 * Devuelve la fila del cuadro francés cuya fecha corresponde al mes
 * actual (o `undefined` si no aplica). Sirve para precargar el split
 * principal/intereses con los valores teóricos del préstamo.
 */
function findCurrentMonthRow(rows: AmortizationRow[]): AmortizationRow | undefined {
  const now = new Date();
  const target = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  return rows.find((row) => row.due_date.startsWith(target));
}

function parseAmount(value: string): number {
  const trimmed = value.trim().replace(',', '.');
  if (!trimmed) return 0;
  const numeric = Number(trimmed);
  return Number.isFinite(numeric) ? numeric : 0;
}

/**
 * Wizard para registrar el pago de una cuota de deuda (PHASE-22.2).
 *
 * Crea:
 * 1. Una transacción `expense` en la cuenta origen con la categoría de
 *    intereses correspondiente — sólo si el split de intereses > 0.
 * 2. Una transferencia interna que mueve el principal de la cuenta
 *    origen a la liability: dos transacciones sin categoría enlazadas
 *    vía `useLinkTransfer`. Esto reduce el saldo de la cuenta origen
 *    y reduce el saldo de la liability (porque para liabilities el
 *    sign está invertido).
 *
 * Si la liability tiene cuadro de amortización y la fecha actual cae
 * dentro del calendario, el split se precarga con los valores teóricos
 * del mes en curso.
 */
export function DebtPaymentWizard({
  liabilityAccount,
  open,
  onClose,
}: DebtPaymentWizardProps) {
  const accountsQuery = useAccounts();
  const categoriesQuery = useCategories();
  // Amortización opcional: si la cuenta no tiene los datos, el query
  // devolverá 400 y dejamos `rows = []`.
  const scheduleQuery = useAmortizationSchedule(
    liabilityAccount.id,
  );

  const principalTxMutation = useCreateTransaction();
  const liabilityTxMutation = useCreateTransaction();
  const interestTxMutation = useCreateTransaction();
  const linkMutation = useLinkTransfer();
  const payInstallmentsMutation = usePayInstallments();

  const accounts = accountsQuery.data ?? [];
  const categories = categoriesQuery.data ?? [];

  // Sólo cuentas asset activas distintas a la propia liability.
  const sourceAccounts = accounts.filter(
    (a) =>
      !a.is_archived &&
      ASSET_ACCOUNT_TYPES.includes(a.type) &&
      a.currency === liabilityAccount.currency,
  );

  const interestCategoryName = INTEREST_CATEGORY_BY_TYPE[liabilityAccount.type];
  const interestCategory = categories.find(
    (c) => c.kind === 'expense' && c.name === interestCategoryName,
  );

  const currentMonthRow = useMemo(() => {
    if (!scheduleQuery.data) return undefined;
    return findCurrentMonthRow(scheduleQuery.data.rows);
  }, [scheduleQuery.data]);

  // AUDIT-2026-07 (H-05): sólo las liabilities CON cuadro derivan el saldo del
  // schedule (PHASE-36), así que sólo entonces marcamos cuotas al pagar. Sin
  // cuadro (p.ej. tarjeta sin plan), el saldo lo mueven los movimientos y la
  // transferencia ya lo reduce.
  const hasSchedule = (scheduleQuery.data?.rows.length ?? 0) > 0;

  const [sourceAccountId, setSourceAccountId] = useState<string>('');
  const [totalAmount, setTotalAmount] = useState<string>('');
  const [principalAmount, setPrincipalAmount] = useState<string>('');
  const [interestAmount, setInterestAmount] = useState<string>('');
  const [categoryId, setCategoryId] = useState<string>('');
  const [occurredAt, setOccurredAt] = useState<string>(todayDayStr());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // El usuario marca qué campo controla: cuando edita "principal", el
  // "interest" se recalcula como total - principal, y viceversa. Sin
  // este estado el side-effect ping-pong consigo mismo en cada render.
  const [lastEdited, setLastEdited] = useState<'principal' | 'interest'>('principal');

  // Cuando se abre el wizard, precargamos:
  // - Cuenta origen: primera asset disponible
  // - Total: cuota del mes actual del cuadro o vacío
  // - Split: principal/interest del cuadro o 100% principal
  // - Categoría: la de intereses del tipo de liability
  // - Fecha: hoy
  useEffect(() => {
    if (!open) return;
    if (sourceAccounts[0] && !sourceAccountId) {
      setSourceAccountId(sourceAccounts[0].id);
    }
    if (interestCategory && !categoryId) {
      setCategoryId(interestCategory.id);
    }
    if (currentMonthRow && !totalAmount) {
      setTotalAmount(currentMonthRow.payment);
      setPrincipalAmount(currentMonthRow.principal);
      setInterestAmount(currentMonthRow.interest);
    }
    // Las deps son intencionales: queremos correr el bootstrap una vez
    // al abrir o cuando llegan los datos necesarios. No reaccionamos a
    // cambios posteriores del propio usuario.
  }, [open, sourceAccounts.length, interestCategory?.id, currentMonthRow?.payment]);

  /**
   * Cuando cambia el total y nada más, repartimos manteniendo la
   * proporción del último split conocido si era no trivial; si no,
   * vamos 100% principal por simplicidad.
   */
  function handleTotalChange(next: string) {
    setTotalAmount(next);
    const totalNum = parseAmount(next);
    if (totalNum <= 0) {
      setPrincipalAmount('');
      setInterestAmount('');
      return;
    }
    const prevPrincipal = parseAmount(principalAmount);
    const prevInterest = parseAmount(interestAmount);
    const prevTotal = prevPrincipal + prevInterest;
    if (prevTotal > 0) {
      const ratio = prevPrincipal / prevTotal;
      const newPrincipal = (totalNum * ratio).toFixed(2);
      const newInterest = (totalNum - Number(newPrincipal)).toFixed(2);
      setPrincipalAmount(newPrincipal);
      setInterestAmount(newInterest);
    } else {
      setPrincipalAmount(totalNum.toFixed(2));
      setInterestAmount('0.00');
    }
  }

  function handlePrincipalChange(next: string) {
    setPrincipalAmount(next);
    setLastEdited('principal');
    const totalNum = parseAmount(totalAmount);
    const principalNum = parseAmount(next);
    if (totalNum > 0) {
      const remainder = Math.max(0, totalNum - principalNum);
      setInterestAmount(remainder.toFixed(2));
    }
  }

  function handleInterestChange(next: string) {
    setInterestAmount(next);
    setLastEdited('interest');
    const totalNum = parseAmount(totalAmount);
    const interestNum = parseAmount(next);
    if (totalNum > 0) {
      const remainder = Math.max(0, totalNum - interestNum);
      setPrincipalAmount(remainder.toFixed(2));
    }
  }

  function reset() {
    setSourceAccountId('');
    setTotalAmount('');
    setPrincipalAmount('');
    setInterestAmount('');
    setCategoryId('');
    setOccurredAt(todayDayStr());
    setError(null);
    setLastEdited('principal');
  }

  function handleClose() {
    if (submitting) return;
    reset();
    onClose();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const totalNum = parseAmount(totalAmount);
    const principalNum = parseAmount(principalAmount);
    const interestNum = parseAmount(interestAmount);

    if (!sourceAccountId) {
      setError('Selecciona la cuenta origen.');
      return;
    }
    if (totalNum <= 0) {
      setError('El importe total debe ser mayor que 0.');
      return;
    }
    // Permitimos 1 céntimo de holgura por redondeo.
    if (Math.abs(principalNum + interestNum - totalNum) > 0.01) {
      setError('El reparto principal + intereses debe sumar el total.');
      return;
    }
    if (principalNum < 0 || interestNum < 0) {
      setError('Los importes no pueden ser negativos.');
      return;
    }
    if (interestNum > 0 && !categoryId) {
      setError('Selecciona la categoría para los intereses.');
      return;
    }

    setSubmitting(true);
    try {
      const occurredAtIso = fromDateInputValue(occurredAt);
      const currency = liabilityAccount.currency;

      // 1. Crear la transferencia: expense en cuenta origen +
      //    income en liability (sin categoría), luego enlazar.
      // Las dos transacciones del par usan exactamente `principalNum`.
      let partialInstallment = false;
      if (principalNum > 0) {
        const outTx = await principalTxMutation.mutateAsync({
          account_id: sourceAccountId,
          amount: principalNum.toFixed(2),
          currency,
          occurred_at: occurredAtIso,
          description: `Pago a ${liabilityAccount.name} (principal)`,
          category_id: null,
        });
        const inTx = await liabilityTxMutation.mutateAsync({
          account_id: liabilityAccount.id,
          amount: principalNum.toFixed(2),
          currency,
          occurred_at: occurredAtIso,
          description: `Amortización ${liabilityAccount.name}`,
          category_id: null,
        });
        await linkMutation.mutateAsync({
          out_transaction_id: outTx.id,
          in_transaction_id: inTx.id,
        });

        // AUDIT-2026-07 (H-05): con PHASE-36 el saldo de una liability con
        // cuadro lo manda el schedule (Σ principal de cuotas no pagadas), no
        // los movimientos. Marcamos la(s) cuota(s) que este principal cubre
        // (enlazadas a la pata de amortización) para que el saldo baje; sin
        // esto el pago movía el dinero pero el saldo del préstamo no cambiaba.
        if (hasSchedule) {
          const payResult = await payInstallmentsMutation.mutateAsync({
            accountId: liabilityAccount.id,
            payload: {
              principal_amount: principalNum.toFixed(2),
              paid_at: occurredAtIso,
              paid_transaction_id: inTx.id,
            },
          });
          partialInstallment = payResult.marked_count === 0;
        }
      }

      // 2. Crear la expense de intereses sobre la cuenta origen.
      if (interestNum > 0) {
        await interestTxMutation.mutateAsync({
          account_id: sourceAccountId,
          amount: interestNum.toFixed(2),
          currency,
          occurred_at: occurredAtIso,
          description: `Intereses ${liabilityAccount.name}`,
          category_id: categoryId || null,
        });
      }

      if (partialInstallment) {
        toast.warning(
          'Pago registrado, pero el principal no cubre una cuota completa: ' +
            'el saldo del préstamo no baja hasta completar la cuota más antigua pendiente.',
        );
      } else {
        toast.success('Cuota registrada.');
      }
      reset();
      onClose();
    } catch (err) {
      const message = formatApiError(err, 'Error al registrar la cuota.');
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="debt-payment-title"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: spacing.lg,
        zIndex: 100,
      }}
      onClick={handleClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          backgroundColor: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: radius.md,
          padding: spacing.lg,
          width: '100%',
          maxWidth: 520,
          maxHeight: '90vh',
          overflow: 'auto',
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.18)',
        }}
      >
        <header style={{ marginBottom: spacing.md }}>
          <h2
            id="debt-payment-title"
            style={{
              margin: 0,
              fontSize: fontSize.lg,
              fontWeight: fontWeight.semibold,
              color: colors.text,
            }}
          >
            Pagar cuota
          </h2>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              fontSize: fontSize.sm,
              color: colors.textMuted,
              lineHeight: 1.4,
            }}
          >
            <strong>{liabilityAccount.name}</strong> · El importe principal
            se mueve como transferencia interna y los intereses se
            registran como gasto en la cuenta origen.
            {currentMonthRow ? (
              <>
                {' '}
                Precargado desde el cuadro francés para el mes actual.
              </>
            ) : null}
          </p>
        </header>

        <form
          onSubmit={(e) => {
            void handleSubmit(e);
          }}
          style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}
        >
          <Select
            label="Cuenta origen"
            value={sourceAccountId}
            onChange={(e) => setSourceAccountId(e.target.value)}
            required
          >
            <option value="">Selecciona cuenta…</option>
            {sourceAccounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.currency})
              </option>
            ))}
          </Select>
          {sourceAccounts.length === 0 ? (
            <p
              style={{
                margin: 0,
                fontSize: fontSize.xs,
                color: colors.warning,
              }}
            >
              No tienes cuentas asset en {liabilityAccount.currency} para
              pagar esta deuda.
            </p>
          ) : null}

          <TextInput
            label="Importe total"
            type="text"
            inputMode="decimal"
            placeholder="0.00"
            value={totalAmount}
            onChange={(e) => handleTotalChange(e.target.value)}
            required
          />

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: spacing.sm,
            }}
          >
            <TextInput
              label="Principal"
              type="text"
              inputMode="decimal"
              placeholder="0.00"
              value={principalAmount}
              onChange={(e) => handlePrincipalChange(e.target.value)}
            />
            <TextInput
              label="Intereses"
              type="text"
              inputMode="decimal"
              placeholder="0.00"
              value={interestAmount}
              onChange={(e) => handleInterestChange(e.target.value)}
            />
          </div>

          <div
            style={{
              display: 'flex',
              gap: spacing.sm,
              flexWrap: 'wrap',
              fontSize: fontSize.xs,
              color: colors.textMuted,
            }}
          >
            <span>
              Reparto: {formatAmount(principalAmount || '0', liabilityAccount.currency)}{' '}
              principal +{' '}
              {formatAmount(interestAmount || '0', liabilityAccount.currency)}{' '}
              intereses
            </span>
            {lastEdited === 'interest' ? (
              <span style={{ color: colors.textSubtle }}>
                · Principal se ajusta al cambiar intereses
              </span>
            ) : null}
          </div>

          <Select
            label="Categoría de intereses"
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            disabled={parseAmount(interestAmount) <= 0}
          >
            <option value="">Sin categoría</option>
            {categories
              .filter((c) => c.kind === 'expense')
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.icon ? `${c.icon} ` : ''}
                  {c.name}
                </option>
              ))}
          </Select>

          <TextInput
            label="Fecha"
            type="date"
            value={occurredAt}
            onChange={(e) => setOccurredAt(e.target.value)}
            required
          />

          {error ? (
            <div
              style={{
                padding: `${spacing.xs}px ${spacing.sm}px`,
                backgroundColor: colors.dangerSoft,
                color: colors.danger,
                borderRadius: radius.sm,
                fontSize: fontSize.sm,
              }}
            >
              {error}
            </div>
          ) : null}

          <div
            style={{
              display: 'flex',
              gap: spacing.sm,
              justifyContent: 'flex-end',
              marginTop: spacing.xs,
            }}
          >
            <Button
              type="button"
              variant="ghost"
              onClick={handleClose}
              disabled={submitting}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={submitting || sourceAccounts.length === 0}>
              {submitting ? 'Registrando…' : 'Pagar cuota'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
