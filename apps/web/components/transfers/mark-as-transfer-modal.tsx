'use client';

import { useEffect, useMemo, useState } from 'react';

import {
  useAccounts,
  useCategories,
  useConvertToTransfer,
  useUnlinkTransfer,
} from '@crisol/services';
import type { Account, Transaction, TransferPair } from '@crisol/types';
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
import { Select } from '@/components/ui/field';

export interface MarkAsTransferModalProps {
  /** Tx que se está marcando. `null` mantiene el modal cerrado. */
  transaction: Transaction | null;
  onCancel: () => void;
  onSuccess: (pair: TransferPair) => void;
  onError: (err: unknown) => void;
}

/**
 * Modal de "Marcar como transferencia": el usuario indica
 * explícitamente cuál es la cuenta **ordenante** (sale el dinero) y
 * cuál la **beneficiaria** (entra). La tx que está editando tiene
 * que ser una de las dos — el dropdown opuesto se rellena con el
 * resto de sus cuentas en la misma moneda.
 *
 * Resuelve el caso del bug en que la dirección se inferia de
 * `category.kind` y un import con bank-mapping le ponía "Transferencias
 * (Gasto)" tanto a abonos como a cargos, dejando los abonos como
 * cargos en el saldo. Al marcar explícitamente la beneficiaria, el
 * backend fuerza la categoría correcta y los signos cuadran.
 */
export function MarkAsTransferModal({
  transaction,
  onCancel,
  onSuccess,
  onError,
}: MarkAsTransferModalProps) {
  const accountsQuery = useAccounts({ includeArchived: false });
  const categoriesQuery = useCategories();
  const convertMutation = useConvertToTransfer();
  const unlinkMutation = useUnlinkTransfer();
  const isWorking = convertMutation.isPending || unlinkMutation.isPending;

  // El "lado fijo" es la cuenta donde vive la tx; lo único que el
  // usuario realmente elige es (a) en qué rol va su cuenta (ordenante
  // vs beneficiaria) y (b) cuál es la otra. Mantener ambos slots como
  // estado independiente nos da flexibilidad sin renderizar dos
  // dropdowns interdependientes.
  const [originatingId, setOriginatingId] = useState<string>('');
  const [beneficiaryId, setBeneficiaryId] = useState<string>('');

  const accounts: Account[] = accountsQuery.data ?? [];
  const sourceAccount = accounts.find((a) => a.id === transaction?.account_id);
  const otherAccounts = useMemo(
    () =>
      transaction
        ? accounts.filter(
            (a) =>
              a.id !== transaction.account_id &&
              a.currency === transaction.currency &&
              !a.is_archived,
          )
        : [],
    [accounts, transaction],
  );

  // Default al abrir: si la categoría actual es INCOME → la cuenta de
  // la tx es la beneficiaria; si EXPENSE/null → es la ordenante. El
  // usuario lo puede flipear en un click cambiando el dropdown.
  useEffect(() => {
    if (!transaction) return;
    const category = (categoriesQuery.data ?? []).find(
      (c) => c.id === transaction.category_id,
    );
    const sourceIsBeneficiary = category?.kind === 'income';
    if (sourceIsBeneficiary) {
      setBeneficiaryId(transaction.account_id);
      setOriginatingId('');
    } else {
      setOriginatingId(transaction.account_id);
      setBeneficiaryId('');
    }
  }, [transaction?.id, categoriesQuery.data]);

  useEffect(() => {
    if (!transaction) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && !isWorking) onCancel();
    }
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
    };
  }, [transaction, isWorking, onCancel]);

  if (!transaction) return null;

  const isAlreadyPaired = transaction.transfer_pair_id !== null;
  const sourceAccountName = sourceAccount?.name ?? 'esta cuenta';
  const sourceAccountIcon = sourceAccount?.icon ?? null;

  // Si la cuenta de la tx está en uno de los slots, el preview del
  // importe muestra '+' (entra) o '−' (sale). El usuario ve en tiempo
  // real cómo va a quedar.
  const sourceRole: 'originating' | 'beneficiary' | null =
    originatingId === transaction.account_id
      ? 'originating'
      : beneficiaryId === transaction.account_id
        ? 'beneficiary'
        : null;
  const previewSign = sourceRole === 'beneficiary' ? '+' : '−';

  function runConvert(sourceTxId: string) {
    convertMutation.mutate(
      {
        source_transaction_id: sourceTxId,
        originating_account_id: originatingId,
        beneficiary_account_id: beneficiaryId,
      },
      {
        onSuccess: (pair) => onSuccess(pair),
        onError: (err) => onError(err),
      },
    );
  }

  function handleSubmit() {
    if (!transaction || !originatingId || !beneficiaryId) return;
    if (sourceRole === null) return; // valida en el botón también
    const sourceTxId = transaction.id;
    if (isAlreadyPaired) {
      // Re-pareo: deshacemos el enlace actual antes de crear el nuevo.
      // Encadenado para que el usuario lo viva como una sola operación.
      unlinkMutation.mutate(sourceTxId, {
        onSuccess: () => runConvert(sourceTxId),
        onError: (err) => onError(err),
      });
      return;
    }
    runConvert(sourceTxId);
  }

  const canSubmit =
    !!originatingId &&
    !!beneficiaryId &&
    originatingId !== beneficiaryId &&
    sourceRole !== null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="mark-transfer-title"
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
      onClick={() => {
        if (!isWorking) onCancel();
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          backgroundColor: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: radius.md,
          padding: spacing.lg,
          width: '100%',
          maxWidth: 560,
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.18)',
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.md,
        }}
      >
        <header
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: spacing.sm,
          }}
        >
          <div>
            <h3
              id="mark-transfer-title"
              style={{
                margin: 0,
                fontSize: fontSize.lg,
                fontWeight: fontWeight.semibold,
                color: colors.text,
              }}
            >
              Marcar como transferencia
            </h3>
            <p
              style={{
                margin: `${spacing.xs}px 0 0`,
                fontSize: fontSize.sm,
                color: colors.textMuted,
                lineHeight: 1.4,
              }}
            >
              Dinos <strong>de qué cuenta sale</strong> el dinero y{' '}
              <strong>a qué cuenta entra</strong>. Ajustamos el saldo de cada
              cuenta y creamos el otro lado del movimiento automáticamente.
            </p>
          </div>
          <button
            type="button"
            aria-label="Cerrar"
            onClick={onCancel}
            disabled={isWorking}
            style={{
              background: 'transparent',
              border: 'none',
              color: colors.textMuted,
              cursor: isWorking ? 'not-allowed' : 'pointer',
              fontSize: fontSize.lg,
              lineHeight: 1,
              padding: 4,
            }}
          >
            ×
          </button>
        </header>

        {isAlreadyPaired ? (
          <div
            role="status"
            style={{
              padding: `${spacing.xs}px ${spacing.sm}px`,
              backgroundColor: colors.warningSoft,
              border: `1px solid ${colors.warning}`,
              borderRadius: radius.sm,
              fontSize: fontSize.xs,
              color: colors.warning,
              lineHeight: 1.4,
            }}
          >
            Esta tx ya formaba parte de una transferencia. Al guardar se{' '}
            <strong>deshará el enlace actual</strong> y se creará uno nuevo
            con las cuentas que elijas.
          </div>
        ) : null}

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            padding: spacing.sm,
            backgroundColor: colors.surfaceMuted,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.sm,
          }}
        >
          <div
            style={{
              display: 'flex',
              gap: spacing.sm,
              alignItems: 'center',
              fontSize: fontSize.xs,
              color: colors.textMuted,
            }}
          >
            <span>{formatCivilDate(transaction.occurred_at)}</span>
            <span aria-hidden>·</span>
            <span>
              {sourceAccountIcon ? `${sourceAccountIcon} ` : ''}
              {sourceAccountName}
            </span>
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
              gap: spacing.sm,
            }}
          >
            <span
              style={{
                fontSize: fontSize.sm,
                color: colors.text,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                minWidth: 0,
              }}
            >
              {transaction.description ?? '(sin descripción)'}
            </span>
            <span
              style={{
                fontSize: fontSize.md,
                fontWeight: fontWeight.semibold,
                color:
                  sourceRole === 'beneficiary' ? colors.income : colors.expense,
                fontVariantNumeric: 'tabular-nums',
                whiteSpace: 'nowrap',
              }}
            >
              {previewSign}
              {formatAmount(transaction.amount, transaction.currency)}
            </span>
          </div>
        </div>

        {otherAccounts.length === 0 ? (
          <p
            style={{
              margin: 0,
              fontSize: fontSize.sm,
              color: colors.textMuted,
              fontStyle: 'italic',
            }}
          >
            No tienes otras cuentas activas en {transaction.currency}. Crea
            una en Ajustes → Cuentas para poder enlazar la transferencia.
          </p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
            <Select
              label="¿De qué cuenta sale el dinero?"
              value={originatingId}
              onChange={(e) => setOriginatingId(e.target.value)}
            >
              <option value="">Selecciona la cuenta de origen…</option>
              {/* La cuenta de la tx aparece como opción explícita +
                  marcada para que sea obvio que es elegible. El resto
                  son las otras cuentas del usuario. */}
              {sourceAccount && !sourceAccount.is_archived ? (
                <option value={sourceAccount.id}>
                  {sourceAccount.icon ? `${sourceAccount.icon} ` : ''}
                  {sourceAccount.name} (cuenta de esta tx)
                </option>
              ) : null}
              {otherAccounts.map((acc) => (
                <option key={acc.id} value={acc.id}>
                  {acc.icon ? `${acc.icon} ` : ''}
                  {acc.name}
                </option>
              ))}
            </Select>

            <Select
              label="¿A qué cuenta entra el dinero?"
              value={beneficiaryId}
              onChange={(e) => setBeneficiaryId(e.target.value)}
            >
              <option value="">Selecciona la cuenta de destino…</option>
              {sourceAccount && !sourceAccount.is_archived ? (
                <option value={sourceAccount.id}>
                  {sourceAccount.icon ? `${sourceAccount.icon} ` : ''}
                  {sourceAccount.name} (cuenta de esta tx)
                </option>
              ) : null}
              {otherAccounts.map((acc) => (
                <option key={acc.id} value={acc.id}>
                  {acc.icon ? `${acc.icon} ` : ''}
                  {acc.name}
                </option>
              ))}
            </Select>

            {originatingId &&
            beneficiaryId &&
            originatingId === beneficiaryId ? (
              <p
                style={{
                  margin: 0,
                  fontSize: fontSize.xs,
                  color: colors.danger,
                }}
              >
                La cuenta de origen y la de destino no pueden ser la misma.
              </p>
            ) : null}

            {originatingId && beneficiaryId && sourceRole === null ? (
              <p
                style={{
                  margin: 0,
                  fontSize: fontSize.xs,
                  color: colors.danger,
                }}
              >
                La cuenta de esta transacción ({sourceAccountName}) tiene
                que ser la de origen o la de destino.
              </p>
            ) : null}
          </div>
        )}

        {convertMutation.isError || unlinkMutation.isError ? (
          <p
            style={{
              margin: 0,
              color: colors.danger,
              fontSize: fontSize.sm,
            }}
          >
            {(() => {
              const err = convertMutation.error ?? unlinkMutation.error;
              return err instanceof Error
                ? err.message
                : 'Error al crear la transferencia';
            })()}
          </p>
        ) : null}

        <div
          style={{
            display: 'flex',
            gap: spacing.sm,
            justifyContent: 'flex-end',
          }}
        >
          <Button
            type="button"
            variant="ghost"
            onClick={onCancel}
            disabled={isWorking}
          >
            Cancelar
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit || isWorking}
          >
            {isWorking
              ? isAlreadyPaired
                ? 'Reasignando…'
                : 'Creando…'
              : isAlreadyPaired
                ? 'Reasignar transferencia'
                : 'Crear transferencia'}
          </Button>
        </div>
      </div>
    </div>
  );
}
