'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { colors, fromDateInputValue, toDateInputValue } from '@crisol/ui';
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
  TransactionUpdateRequest,
} from '@crisol/types';

import { Button } from '../ui/button';
import { Select, TextArea, TextInput } from '../ui/field';
import { CategoryCombobox } from './category-combobox';

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
      const preferred = pickPreferredAccount(accounts);
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

  const accountList = accounts ?? [];
  const noAccounts = !loadingAccounts && accountList.length === 0;

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
        onChange={(id) => handleChange('category_id', id)}
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
