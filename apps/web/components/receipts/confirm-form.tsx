'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { pickPreferredAccount, useAccounts, useCategories, todayDayStr } from '@crisol/services';
import type { ReceiptConfirmRequest, ReceiptExtraction } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatCategoryKind,
  fromDateInputValue,
  spacing,
  toDateInputValue,
} from '@crisol/ui';

import { Button } from '../ui/button';
import { Select, TextArea, TextInput } from '../ui/field';

export interface ReceiptConfirmFormProps {
  extraction: ReceiptExtraction | Record<string, unknown>;
  submitting?: boolean;
  errorMessage?: string | null;
  onSubmit: (payload: ReceiptConfirmRequest) => void;
  onReject?: () => void;
}

interface FormValues {
  amount: string;
  currency: string;
  occurred_at: string;
  category_id: string;
  account_id: string;
  description: string;
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function buildInitialValues(extraction: ReceiptExtraction | Record<string, unknown>): FormValues {
  const ext = extraction as Record<string, unknown>;
  const occurred = asString(ext['occurred_at']);
  return {
    amount: asString(ext['total']),
    currency: asString(ext['currency']) || 'EUR',
    occurred_at: occurred ? toDateInputValue(occurred) : todayDayStr(),
    category_id: '',
    account_id: '',
    description: asString(ext['merchant']),
  };
}

export function ReceiptConfirmForm({
  extraction,
  submitting,
  errorMessage,
  onSubmit,
  onReject,
}: ReceiptConfirmFormProps) {
  const { data: categories, isLoading: loadingCategories } = useCategories();
  const { data: accounts, isLoading: loadingAccounts } = useAccounts();
  const [values, setValues] = useState<FormValues>(() => buildInitialValues(extraction));
  const [validationError, setValidationError] = useState<string | null>(null);

  // Pre-seleccionar la cuenta principal (PHASE-32) o la primera cuando
  // llegue la lista. El guard del layout impide llegar aquí sin cuentas,
  // pero por defensa no dejamos crashear el form si llega vacía.
  useEffect(() => {
    if (!accounts || accounts.length === 0) return;
    setValues((prev) => {
      if (prev.account_id) return prev;
      const preferred = pickPreferredAccount(accounts);
      if (!preferred) return prev;
      return { ...prev, account_id: preferred.id };
    });
  }, [accounts]);

  const accountList = accounts ?? [];

  function handleChange<K extends keyof FormValues>(field: K, value: string) {
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidationError(null);

    const amount = values.amount.trim().replace(',', '.');
    if (!amount || Number.isNaN(Number(amount)) || Number(amount) <= 0) {
      setValidationError('Importe debe ser un número positivo');
      return;
    }
    const currency = values.currency.trim().toUpperCase();
    if (currency.length !== 3) {
      setValidationError('Moneda en formato ISO de 3 letras');
      return;
    }
    if (!values.account_id) {
      setValidationError('Selecciona una cuenta');
      return;
    }

    const payload: ReceiptConfirmRequest = {
      account_id: values.account_id,
      amount,
      currency,
      occurred_at: fromDateInputValue(values.occurred_at),
      description: values.description.trim() || null,
      category_id: values.category_id || null,
    };
    onSubmit(payload);
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <p
        style={{
          marginTop: 0,
          marginBottom: spacing.md,
          fontSize: fontSize.sm,
          color: colors.textMuted,
        }}
      >
        El modelo de visión propone estos datos. Revísalos y edítalos antes de confirmar — la
        transacción se crea con los valores definitivos.
      </p>

      <TextInput
        label="Importe"
        type="text"
        inputMode="decimal"
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
      <Select
        label="Cuenta"
        value={values.account_id}
        onChange={(e) => handleChange('account_id', e.target.value)}
        disabled={loadingAccounts || accountList.length === 0}
        required
      >
        {accountList.length === 0 ? <option value="">— Crea una cuenta primero —</option> : null}
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
        {(categories ?? []).map((c) => (
          <option key={c.id} value={c.id}>
            {c.name} ({formatCategoryKind(c.kind)})
          </option>
        ))}
      </Select>
      <TextArea
        label="Descripción"
        value={values.description}
        onChange={(e) => handleChange('description', e.target.value)}
        maxLength={500}
      />

      {validationError ? (
        <div style={{ color: colors.danger, fontSize: fontSize.sm, marginBottom: spacing.sm }}>
          {validationError}
        </div>
      ) : null}
      {errorMessage ? (
        <div style={{ color: colors.danger, fontSize: fontSize.sm, marginBottom: spacing.sm }}>
          {errorMessage}
        </div>
      ) : null}

      <div style={{ display: 'flex', gap: spacing.sm, marginTop: spacing.md }}>
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Confirmando…' : 'Confirmar y crear transacción'}
        </Button>
        {onReject ? (
          <Button type="button" variant="danger" onClick={onReject} disabled={submitting}>
            Rechazar
          </Button>
        ) : null}
      </div>
    </form>
  );
}

export interface ExtractionSummaryProps {
  extraction: ReceiptExtraction | Record<string, unknown>;
}

export function ExtractionSummary({ extraction }: ExtractionSummaryProps) {
  const ext = extraction as Record<string, unknown>;
  const lineItems = (ext['line_items'] as unknown[]) ?? [];
  if (!lineItems || lineItems.length === 0) return null;
  return (
    <details style={{ marginTop: spacing.md }}>
      <summary
        style={{
          fontSize: fontSize.sm,
          fontWeight: fontWeight.medium,
          color: colors.textMuted,
          cursor: 'pointer',
        }}
      >
        Líneas detectadas ({lineItems.length})
      </summary>
      <ul style={{ marginTop: spacing.xs, paddingLeft: spacing.lg, fontSize: fontSize.sm }}>
        {lineItems.map((raw, idx) => {
          const item = raw as Record<string, unknown>;
          const desc =
            typeof item['description'] === 'string' ? item['description'] : `Línea ${idx + 1}`;
          const total = typeof item['total'] === 'string' ? item['total'] : '—';
          return (
            <li key={idx} style={{ color: colors.text }}>
              {desc} — {total}
            </li>
          );
        })}
      </ul>
    </details>
  );
}
