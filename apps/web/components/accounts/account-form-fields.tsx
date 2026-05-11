'use client';

import type { AccountType } from '@crisol/types';
import { ASSET_ACCOUNT_TYPES } from '@crisol/types';
import {
  DEFAULT_CATEGORY_COLOR,
  colors,
  fontSize,
  spacing,
} from '@crisol/ui';

import { CategoryAppearanceFields } from '@/components/ui/category-appearance';
import { Select, TextInput } from '@/components/ui/field';

/**
 * Estado que el caller mantiene sobre el form de cuenta. Se acepta tal
 * cual desde la pantalla de settings (full create/edit) y desde el
 * onboarding (subset mínimo — los campos extra siguen aplicando defaults).
 */
export interface AccountFormValue {
  name: string;
  type: AccountType;
  currency: string;
  color: string;
  icon: string | null;
  /** Decimal serializado como string. Vacío equivale a "0". */
  opening_balance: string;
}

export interface AccountFormErrors {
  name?: string | undefined;
  currency?: string | undefined;
  opening_balance?: string | undefined;
}

export interface AccountFormFieldsProps {
  value: AccountFormValue;
  onChange: (next: AccountFormValue) => void;
  /** Si está vacío, el caller decide qué campos pedir. Por defecto: full. */
  variant?: 'full' | 'minimal';
  errors?: AccountFormErrors | undefined;
}

const TYPE_LABEL: Record<AccountType, string> = {
  bank: 'Cuenta bancaria',
  savings: 'Ahorro',
  brokerage: 'Inversión / Bróker',
  crypto: 'Crypto',
  cash: 'Efectivo',
  // PHASE-20 — no se exponen en PHASE-19.1, los dejamos por exhaustividad.
  credit_card: 'Tarjeta de crédito',
  loan: 'Préstamo',
  mortgage: 'Hipoteca',
};

export const DEFAULT_ACCOUNT_FORM: AccountFormValue = {
  name: '',
  type: 'bank',
  currency: 'EUR',
  color: DEFAULT_CATEGORY_COLOR,
  icon: null,
  opening_balance: '',
};

/**
 * Campos de un form de cuenta. No incluye botón submit ni layout de
 * cabecera — se monta dentro de un wrapper (settings o onboarding) que
 * controla esos elementos.
 */
export function AccountFormFields({
  value,
  onChange,
  variant = 'full',
  errors,
}: AccountFormFieldsProps) {
  function patch<K extends keyof AccountFormValue>(field: K, next: AccountFormValue[K]) {
    onChange({ ...value, [field]: next });
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <div
        style={{
          display: 'flex',
          gap: spacing.md,
          alignItems: 'flex-end',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ flex: '2 1 220px', minWidth: 0 }}>
          <TextInput
            label="Nombre"
            value={value.name}
            onChange={(e) => patch('name', e.target.value)}
            maxLength={100}
            placeholder="Cuenta nómina, Ahorro Revolut, Caja…"
            error={errors?.name}
            required
          />
        </div>
        <div style={{ flex: '1 1 160px', minWidth: 0 }}>
          <Select
            label="Tipo"
            value={value.type}
            onChange={(e) => patch('type', e.target.value as AccountType)}
          >
            {ASSET_ACCOUNT_TYPES.map((t) => (
              <option key={t} value={t}>
                {TYPE_LABEL[t]}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <div
        style={{
          display: 'flex',
          gap: spacing.md,
          alignItems: 'flex-end',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ flex: '1 1 120px', minWidth: 0, maxWidth: 160 }}>
          <TextInput
            label="Moneda"
            type="text"
            maxLength={3}
            value={value.currency}
            onChange={(e) => patch('currency', e.target.value.toUpperCase())}
            error={errors?.currency}
            required
          />
        </div>
        {variant === 'full' ? (
          <div style={{ flex: '1 1 180px', minWidth: 0 }}>
            <TextInput
              label="Saldo inicial (opcional)"
              type="text"
              inputMode="decimal"
              placeholder="0.00"
              value={value.opening_balance}
              onChange={(e) => patch('opening_balance', e.target.value)}
              error={errors?.opening_balance}
            />
          </div>
        ) : null}
      </div>

      {variant === 'full' ? (
        <CategoryAppearanceFields
          color={value.color}
          icon={value.icon}
          onColorChange={(hex) => patch('color', hex)}
          onIconChange={(emoji) => patch('icon', emoji)}
        />
      ) : (
        <p
          style={{
            margin: 0,
            fontSize: fontSize.xs,
            color: colors.textMuted,
            lineHeight: 1.4,
          }}
        >
          Podrás añadir color, icono y saldo inicial más adelante desde Ajustes.
        </p>
      )}
    </div>
  );
}
