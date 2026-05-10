'use client';

import { useEffect, useState, type FormEvent } from 'react';

import {
  colors,
  fromDateInputValue,
  toDateInputValue,
} from '@finanzas/ui';
import { useAccounts, useCategories, useUserCurrencies } from '@finanzas/services';
import { useCurrencyStore } from '@finanzas/store';
import type {
  Category,
  Transaction,
  TransactionCreateRequest,
  TransactionUpdateRequest,
} from '@finanzas/types';

import { Button } from '../ui/button';
import { Select, TextArea, TextInput } from '../ui/field';

// Mismas monedas siempre visibles que en el selector global del header.
// Mantener sincronizado con `currency-menu.tsx` cuando se amplíe.
const BASE_CURRENCIES = ['EUR', 'USD'] as const;

export interface TransactionFormValues {
  amount: string;
  currency: string;
  occurred_at: string;
  category_id: string;
  account_id: string;
  description: string;
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
  const [error, setError] = useState<string | null>(null);

  // Cuando el listado de cuentas llega, si no hay account_id seleccionado
  // tomamos la primera. El guard del layout impide llegar aquí sin
  // cuentas, pero por defensa añadimos un fallback visual abajo.
  useEffect(() => {
    if (!accounts || accounts.length === 0) return;
    setValues((prev) => {
      if (prev.account_id) return prev;
      const first = accounts[0];
      if (!first) return prev;
      return { ...prev, account_id: first.id };
    });
  }, [accounts]);

  // Opciones del selector: BASE (EUR + USD) + las que el usuario ya
  // usa + la actual del form (por si edita una transacción en una
  // moneda que ya no está en BD por borrados). Sin duplicados.
  const currencyOptions = Array.from(
    new Set([...BASE_CURRENCIES, ...(userCurrencies ?? []), values.currency].filter(Boolean)),
  );

  const accountList = accounts ?? [];
  const noAccounts = !loadingAccounts && accountList.length === 0;

  function handleChange<K extends keyof TransactionFormValues>(field: K, value: string) {
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const amount = values.amount.trim().replace(',', '.');
    if (!amount || Number.isNaN(Number(amount)) || Number(amount) <= 0) {
      setError('Importe debe ser un número positivo');
      return;
    }
    if (!values.account_id) {
      setError('Selecciona una cuenta');
      return;
    }

    const payload: TransactionCreateRequest = {
      account_id: values.account_id,
      amount,
      currency: values.currency.trim().toUpperCase() || 'EUR',
      occurred_at: fromDateInputValue(values.occurred_at),
      category_id: values.category_id || null,
      description: values.description.trim() || null,
    };

    onSubmit(payload);
  }

  if (noAccounts) {
    return (
      <div>
        <p style={{ color: colors.textMuted, marginTop: 0 }}>
          Crea una cuenta primero. Cada transacción debe imputarse a una
          cuenta para que los KPIs sean correctos.
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
        required
      />
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
      <Select
        label="Categoría"
        value={values.category_id}
        onChange={(e) => handleChange('category_id', e.target.value)}
        disabled={loadingCategories}
      >
        <option value="">— Sin categoría —</option>
        {(categories ?? []).map((c: Category) => (
          <option key={c.id} value={c.id}>
            {c.name} ({c.kind === 'income' ? 'Ingreso' : 'Gasto'})
          </option>
        ))}
      </Select>
      <TextArea
        label="Descripción"
        value={values.description}
        onChange={(e) => handleChange('description', e.target.value)}
        maxLength={500}
      />

      {error ? (
        <div style={{ color: colors.danger, fontSize: 14, marginBottom: 12 }}>{error}</div>
      ) : null}

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
