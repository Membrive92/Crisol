'use client';

import { useState, type FormEvent } from 'react';

import {
  colors,
  fromDateInputValue,
  toDateInputValue,
} from '@finanzas/ui';
import { useCategories } from '@finanzas/services';
import type {
  Category,
  Transaction,
  TransactionCreateRequest,
  TransactionUpdateRequest,
} from '@finanzas/types';

import { Button } from '../ui/button';
import { Select, TextArea, TextInput } from '../ui/field';

export interface TransactionFormValues {
  amount: string;
  currency: string;
  occurred_at: string;
  category_id: string;
  description: string;
}

export interface TransactionFormProps {
  initial?: Transaction;
  submitting?: boolean;
  submitLabel: string;
  onSubmit: (payload: TransactionCreateRequest | TransactionUpdateRequest) => void;
  onCancel?: () => void;
}

function buildInitialValues(initial?: Transaction): TransactionFormValues {
  return {
    amount: initial?.amount ?? '',
    currency: initial?.currency ?? 'EUR',
    occurred_at: toDateInputValue(initial?.occurred_at ?? new Date().toISOString()),
    category_id: initial?.category_id ?? '',
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
  const [values, setValues] = useState<TransactionFormValues>(() => buildInitialValues(initial));
  const [error, setError] = useState<string | null>(null);

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

    const payload: TransactionCreateRequest = {
      amount,
      currency: values.currency.trim().toUpperCase() || 'EUR',
      occurred_at: fromDateInputValue(values.occurred_at),
      category_id: values.category_id || null,
      description: values.description.trim() || null,
    };

    onSubmit(payload);
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
      <TextInput
        label="Moneda"
        type="text"
        maxLength={3}
        value={values.currency}
        onChange={(e) => handleChange('currency', e.target.value)}
      />
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
