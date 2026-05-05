'use client';

import { useState } from 'react';

import type { BudgetCreateRequest, Category } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { Button } from '@/components/ui/button';

export interface BudgetFormProps {
  categories: Category[];
  /** Monedas disponibles del usuario (de `useUserCurrencies`). Se cae a EUR si vacía. */
  currencies?: string[];
  submitting?: boolean;
  onSubmit: (data: BudgetCreateRequest) => void;
}

const DEFAULT_CURRENCY = 'EUR';

function todayISO(): string {
  const today = new Date();
  return [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, '0'),
    String(today.getDate()).padStart(2, '0'),
  ].join('-');
}

/**
 * Form para crear un nuevo presupuesto. Sólo categorías de
 * `kind='expense'` aparecen en el dropdown — los budgets miden
 * gasto, no ingreso.
 *
 * Validación local: amount > 0 y currency 3 letras. El 409 del
 * backend (ya hay activo para esa categoría) lo gestiona el caller
 * con un toast.
 */
export function BudgetForm({
  categories,
  currencies,
  submitting,
  onSubmit,
}: BudgetFormProps) {
  const [categoryId, setCategoryId] = useState<string>('');
  const [amount, setAmount] = useState<string>('');
  const [currency, setCurrency] = useState<string>(currencies?.[0] ?? DEFAULT_CURRENCY);
  const [effectiveFrom, setEffectiveFrom] = useState<string>(todayISO());
  const [error, setError] = useState<string | null>(null);

  const expenseCategories = categories.filter((c) => c.kind === 'expense');
  const currencyOptions = currencies && currencies.length > 0 ? currencies : [DEFAULT_CURRENCY];

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = amount.trim().replace(',', '.');
    if (!trimmed || Number.isNaN(Number(trimmed)) || Number(trimmed) <= 0) {
      setError('El importe debe ser un número positivo.');
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(effectiveFrom)) {
      setError('La fecha debe estar en formato YYYY-MM-DD.');
      return;
    }
    onSubmit({
      ...(categoryId ? { category_id: categoryId } : { category_id: null }),
      amount: trimmed,
      currency: currency.toUpperCase(),
      effective_from: effectiveFrom,
    });
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <div>
        <label style={labelStyle}>Categoría</label>
        <select
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          style={inputStyle}
        >
          <option value="">Global (todas las categorías de gasto)</option>
          {expenseCategories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div style={{ display: 'flex', gap: spacing.sm }}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Importe mensual</label>
          <input
            type="text"
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="300.00"
            style={inputStyle}
          />
        </div>
        <div style={{ width: 120 }}>
          <label style={labelStyle}>Moneda</label>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            style={inputStyle}
          >
            {currencyOptions.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label style={labelStyle}>Vigente desde</label>
        <input
          type="date"
          value={effectiveFrom}
          onChange={(e) => setEffectiveFrom(e.target.value)}
          style={inputStyle}
        />
      </div>

      {error ? (
        <div style={{ color: colors.danger, fontSize: fontSize.sm }}>{error}</div>
      ) : null}

      <Button type="submit" disabled={submitting}>
        {submitting ? 'Creando…' : 'Crear presupuesto'}
      </Button>
    </form>
  );
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: fontSize.sm,
  fontWeight: fontWeight.medium,
  color: colors.text,
  marginBottom: 4,
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  padding: `${spacing.sm}px ${spacing.sm + 4}px`,
  fontSize: fontSize.sm,
  color: colors.text,
  backgroundColor: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.sm,
};
