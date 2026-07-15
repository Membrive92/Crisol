'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { colors, fontSize, fontWeight, fromDateInputValue, radius, spacing, toDateInputValue } from '@crisol/ui';
import {
  pickPreferredAccount,
  useAccounts,
  useCategories,
  useUserCurrencies,
} from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import type {
  Transaction,
  TransactionCreateRequest,
  TransactionFlow,
  TransactionUpdateRequest,
} from '@crisol/types';

import { Button } from '../ui/button';
import { Select, TextArea, TextInput } from '../ui/field';
import { CategoryCombobox } from './category-combobox';

// Mismas monedas siempre visibles que en el selector global del header.
// Mantener sincronizado con `currency-menu.tsx` cuando se amplíe.
const BASE_CURRENCIES = ['EUR', 'USD'] as const;

/** PHASE-34: dirección que el usuario declara con el segmento [Gasto]/[Ingreso].
 * La transfer-ness se gestiona en el flujo de transferencias, no aquí. */
type Direction = 'OUT' | 'IN';

function directionFromFlow(flow: TransactionFlow | null | undefined): Direction {
  return flow === 'IN' || flow === 'TRANSFER_IN' ? 'IN' : 'OUT';
}

export interface TransactionFormValues {
  amount: string;
  currency: string;
  occurred_at: string;
  category_id: string;
  account_id: string;
  description: string;
  direction: Direction;
}

export interface TransactionFormProps {
  initial?: Transaction;
  submitting?: boolean;
  submitLabel: string;
  onSubmit: (payload: TransactionCreateRequest | TransactionUpdateRequest) => void;
  onCancel?: () => void;
}

function buildInitialValues(
  initial: Transaction | undefined,
  defaultCurrency: string,
): TransactionFormValues {
  return {
    amount: initial?.amount ?? '',
    currency: initial?.currency ?? defaultCurrency,
    occurred_at: toDateInputValue(initial?.occurred_at ?? new Date().toISOString()),
    category_id: initial?.category_id ?? '',
    // PHASE-19.1: tx ahora vive con un `account_id` obligatorio. Si la
    // tx existente lo tiene, lo respetamos; si no (improbable tras la
    // migración), queda vacío y se rellena con la primera cuenta.
    account_id: initial?.account_id ?? '',
    description: initial?.description ?? '',
    // PHASE-34: por defecto Gasto (la mayoría de altas manuales lo son).
    direction: directionFromFlow(initial?.flow),
  };
}

export function TransactionForm({
  initial,
  submitting,
  submitLabel,
  onSubmit,
  onCancel,
}: TransactionFormProps) {
  const { data: categories, isLoading: loadingCategories } = useCategories();
  const { data: accounts, isLoading: loadingAccounts } = useAccounts();
  const userCurrencies = useUserCurrencies().data;
  // Pre-rellenamos con la moneda activa global — el usuario suele
  // crear transacciones en la moneda con la que está visualizando, y
  // si no, puede cambiarla en el desplegable.
  const activeCurrency = useCurrencyStore((s) => s.currency);
  const [values, setValues] = useState<TransactionFormValues>(() =>
    buildInitialValues(initial, activeCurrency),
  );
  // Errores por campo (AUDIT-2026-05): se pintan inline bajo el control
  // que falla, en vez de un único mensaje genérico al pie del form.
  const [fieldErrors, setFieldErrors] = useState<{
    amount?: string;
    account_id?: string;
  }>({});

  // Cuando el listado de cuentas llega, si no hay account_id seleccionado
  // tomamos la cuenta principal (PHASE-32) o, en su defecto, la primera.
  // El guard del layout impide llegar aquí sin cuentas, pero por defensa
  // añadimos un fallback visual abajo.
  useEffect(() => {
    if (!accounts || accounts.length === 0) return;
    setValues((prev) => {
      if (prev.account_id) return prev;
      // PHASE-35: nunca pre-seleccionar una compra a plazos (cuenta hija).
      const preferred = pickPreferredAccount(accounts.filter((a) => !a.parent_account_id));
      if (!preferred) return prev;
      return { ...prev, account_id: preferred.id };
    });
  }, [accounts]);

  // Opciones del selector: BASE (EUR + USD) + las que el usuario ya
  // usa + la actual del form (por si edita una transacción en una
  // moneda que ya no está en BD por borrados). Sin duplicados.
  const currencyOptions = Array.from(
    new Set([...BASE_CURRENCIES, ...(userCurrencies ?? []), values.currency].filter(Boolean)),
  );

  // PHASE-35: las compras a plazos (cuentas hijas de una tarjeta) no son
  // destino de transacciones → fuera del selector. Al editar una tx ya
  // asignada a una (heredada), se conserva su cuenta para no perderla.
  const selectableAccounts = (accounts ?? []).filter((a) => !a.parent_account_id);
  const accountList =
    values.account_id && !selectableAccounts.some((a) => a.id === values.account_id)
      ? [
          ...selectableAccounts,
          ...(accounts ?? []).filter((a) => a.id === values.account_id),
        ]
      : selectableAccounts;
  const noAccounts = !loadingAccounts && accountList.length === 0;
  // PHASE-34: editar una transferencia no usa el toggle Gasto/Ingreso — su
  // dirección la fija el par y el backend protege el invariante (409). El
  // segmento sólo aplica a movimientos normales y a altas nuevas.
  const isTransfer =
    initial != null &&
    (initial.transfer_pair_id != null ||
      initial.flow === 'TRANSFER_IN' ||
      initial.flow === 'TRANSFER_OUT');

  function handleChange<K extends keyof TransactionFormValues>(field: K, value: string) {
    setValues((prev) => ({ ...prev, [field]: value }));
    // Limpia el error del campo en cuanto el usuario lo edita.
    if (field === 'amount' || field === 'account_id') {
      setFieldErrors((prev) => {
        if (!(field in prev)) return prev;
        const { [field]: _removed, ...rest } = prev;
        return rest;
      });
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const amount = values.amount.trim().replace(',', '.');
    const nextErrors: { amount?: string; account_id?: string } = {};
    if (!amount || Number.isNaN(Number(amount)) || Number(amount) <= 0) {
      nextErrors.amount = 'El importe debe ser un número positivo.';
    }
    if (!values.account_id) {
      nextErrors.account_id = 'Selecciona una cuenta.';
    }
    if (nextErrors.amount || nextErrors.account_id) {
      setFieldErrors(nextErrors);
      return;
    }
    setFieldErrors({});

    const payload: TransactionCreateRequest = {
      account_id: values.account_id,
      amount,
      currency: values.currency.trim().toUpperCase() || 'EUR',
      occurred_at: fromDateInputValue(values.occurred_at),
      category_id: values.category_id || null,
      description: values.description.trim() || null,
    };
    // PHASE-34: enviamos `flow` explícito desde el segmento Gasto/Ingreso.
    // En una transferencia editada NO lo tocamos (lo fija el par; el
    // backend rechaza romperlo). El backend deriva flow de la categoría si
    // no llega, así que omitirlo en transferencias es seguro.
    if (!isTransfer) {
      payload.flow = values.direction;
    }

    onSubmit(payload);
  }

  if (noAccounts) {
    return (
      <div>
        <p style={{ color: colors.textMuted, marginTop: 0 }}>
          Crea una cuenta primero. Cada transacción debe imputarse a una cuenta para que los KPIs
          sean correctos.
        </p>
        {onCancel ? (
          <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
            <Button type="button" variant="ghost" onClick={onCancel}>
              Volver
            </Button>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <TextInput
        label="Importe"
        type="text"
        inputMode="decimal"
        placeholder="0.00"
        value={values.amount}
        onChange={(e) => handleChange('amount', e.target.value)}
        error={fieldErrors.amount}
        aria-invalid={fieldErrors.amount ? true : undefined}
        required
      />
      {isTransfer ? (
        <div style={transferBadgeStyle}>↔ Movimiento interno (transferencia)</div>
      ) : (
        <div style={{ marginBottom: spacing.md }}>
          <span style={segmentLabelStyle}>Tipo</span>
          <div style={segmentGroupStyle} role="group" aria-label="Tipo de movimiento">
            {(['OUT', 'IN'] as const).map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setValues((prev) => ({ ...prev, direction: d }))}
                aria-pressed={values.direction === d}
                style={{
                  ...segmentBtnStyle,
                  ...(values.direction === d ? segmentBtnActiveStyle : {}),
                }}
              >
                {d === 'OUT' ? 'Gasto' : 'Ingreso'}
              </button>
            ))}
          </div>
        </div>
      )}
      <Select
        label="Moneda"
        value={values.currency}
        onChange={(e) => handleChange('currency', e.target.value)}
      >
        {currencyOptions.map((code) => (
          <option key={code} value={code}>
            {code}
          </option>
        ))}
      </Select>
      <Select
        label="Cuenta"
        value={values.account_id}
        onChange={(e) => handleChange('account_id', e.target.value)}
        disabled={loadingAccounts}
        error={fieldErrors.account_id}
        aria-invalid={fieldErrors.account_id ? true : undefined}
        required
      >
        {accountList.map((a) => (
          <option key={a.id} value={a.id}>
            {a.icon ? `${a.icon} ` : ''}
            {a.name} ({a.currency})
          </option>
        ))}
      </Select>
      <TextInput
        label="Fecha"
        type="date"
        value={values.occurred_at}
        onChange={(e) => handleChange('occurred_at', e.target.value)}
        required
      />
      <CategoryCombobox
        label="Categoría"
        categories={categories ?? []}
        value={values.category_id}
        onChange={(id) => {
          // PHASE-38 — al elegir categoría, el segmento [Gasto]/[Ingreso]
          // sigue su `kind` (ingreso → Ingreso, gasto → Gasto): recategorizar
          // un reembolso a una categoría de ingreso lo vuelve positivo sin
          // tener que tocar el segmento aparte (el caso reportado). Es sólo un
          // default de UI — `flow` sigue siendo la verdad explícita (ADR-0004)
          // y el usuario puede re-togglear la dirección después. No aplica a
          // transferencias (segmento oculto, dirección la fija el par) ni a
          // categorías is_transfer.
          const cat = (categories ?? []).find((c) => c.id === id);
          setValues((prev) => ({
            ...prev,
            category_id: id,
            ...(cat && !cat.is_transfer && !isTransfer
              ? { direction: cat.kind === 'income' ? ('IN' as const) : ('OUT' as const) }
              : {}),
          }));
        }}
        disabled={loadingCategories}
      />
      <TextArea
        label="Descripción"
        value={values.description}
        onChange={(e) => handleChange('description', e.target.value)}
        maxLength={500}
      />

      <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Guardando…' : submitLabel}
        </Button>
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancelar
          </Button>
        ) : null}
      </div>
    </form>
  );
}

const segmentLabelStyle = {
  display: 'block',
  marginBottom: spacing.xs,
  fontSize: fontSize.sm,
  fontWeight: fontWeight.medium,
  color: colors.text,
} as const;

const segmentGroupStyle = {
  display: 'flex',
  gap: spacing.xs,
} as const;

const segmentBtnStyle = {
  flex: 1,
  padding: `${spacing.sm}px ${spacing.sm}px`,
  borderRadius: radius.sm,
  // Borde en longhand (no shorthand `border`): el estado activo sólo
  // sobreescribe `borderColor`, y mezclar shorthand+longhand hace que React
  // avise al re-render (quita `borderColor` con `border` aún puesto).
  borderWidth: 1,
  borderStyle: 'solid',
  borderColor: colors.border,
  backgroundColor: colors.surface,
  color: colors.textMuted,
  fontSize: fontSize.sm,
  fontWeight: fontWeight.medium,
  cursor: 'pointer',
} as const;

const segmentBtnActiveStyle = {
  borderColor: colors.primary,
  backgroundColor: colors.primarySoft,
  color: colors.text,
  fontWeight: fontWeight.semibold,
} as const;

const transferBadgeStyle = {
  marginBottom: spacing.md,
  padding: `${spacing.sm}px ${spacing.sm}px`,
  borderRadius: radius.sm,
  backgroundColor: colors.surfaceMuted,
  color: colors.textMuted,
  fontSize: fontSize.sm,
} as const;
