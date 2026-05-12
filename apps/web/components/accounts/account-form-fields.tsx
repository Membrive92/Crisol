'use client';

import type { AccountType } from '@crisol/types';
import {
  AMORTIZABLE_ACCOUNT_TYPES,
  ASSET_ACCOUNT_TYPES,
  LIABILITY_ACCOUNT_TYPES,
} from '@crisol/types';
import {
  DEFAULT_CATEGORY_COLOR,
  colors,
  fontSize,
  fontWeight,
  spacing,
} from '@crisol/ui';

import { CategoryAppearanceFields } from '@/components/ui/category-appearance';
import { Select, TextInput } from '@/components/ui/field';

/**
 * Estado que el caller mantiene sobre el form de cuenta. Se acepta tal
 * cual desde la pantalla de settings (full create/edit) y desde el
 * onboarding (subset mínimo — los campos extra siguen aplicando defaults).
 *
 * PHASE-22: `apr`, `term_months` y `start_date` sólo se piden cuando el
 * tipo es `loan` o `mortgage`. En el resto de tipos quedan como cadenas
 * vacías y el caller los convierte a `null` al enviar al backend.
 */
export interface AccountFormValue {
  name: string;
  type: AccountType;
  currency: string;
  color: string;
  icon: string | null;
  /** Decimal serializado como string. Vacío equivale a "0". */
  opening_balance: string;
  /**
   * APR anual (porcentaje en UI, ej. "3.5" para 3.5%). Vacío = sin valor.
   * Sólo aplica a tipos `loan` y `mortgage`; en otros tipos se ignora.
   */
  apr_percent: string;
  /** Plazo en meses como string para input numérico. Vacío = sin valor. */
  term_months: string;
  /** YYYY-MM-DD. Vacío = sin valor. */
  start_date: string;
}

export interface AccountFormErrors {
  name?: string | undefined;
  currency?: string | undefined;
  opening_balance?: string | undefined;
  apr_percent?: string | undefined;
  term_months?: string | undefined;
  start_date?: string | undefined;
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
  apr_percent: '',
  term_months: '',
  start_date: '',
};

function isLiabilityType(type: AccountType): boolean {
  return LIABILITY_ACCOUNT_TYPES.includes(type);
}

function isAmortizableType(type: AccountType): boolean {
  return AMORTIZABLE_ACCOUNT_TYPES.includes(type);
}

/**
 * Campos de un form de cuenta. No incluye botón submit ni layout de
 * cabecera — se monta dentro de un wrapper (settings o onboarding) que
 * controla esos elementos.
 *
 * PHASE-22: el selector de tipo agrupa "Activos" y "Pasivos / deuda".
 * Para `loan` y `mortgage` se piden APR, plazo y fecha de inicio en una
 * sección destacada. El swatch del saldo se pinta en rojo para tipos
 * liability para dejar claro que el importe representa deuda.
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

  function handleTypeChange(nextType: AccountType) {
    // Al cambiar a un tipo no amortizable, limpiamos los campos
    // específicos para que el caller no envíe valores residuales.
    if (!isAmortizableType(nextType)) {
      onChange({
        ...value,
        type: nextType,
        apr_percent: '',
        term_months: '',
        start_date: '',
      });
      return;
    }
    onChange({ ...value, type: nextType });
  }

  const isLiability = isLiabilityType(value.type);
  const showAmortization = isAmortizableType(value.type);
  const balanceLabel = isLiability ? 'Capital pendiente (opcional)' : 'Saldo inicial (opcional)';
  const balanceColor = isLiability ? colors.danger : undefined;

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
            onChange={(e) => handleTypeChange(e.target.value as AccountType)}
          >
            <optgroup label="Activos">
              {ASSET_ACCOUNT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {TYPE_LABEL[t]}
                </option>
              ))}
            </optgroup>
            <optgroup label="Pasivos / deuda">
              {LIABILITY_ACCOUNT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {TYPE_LABEL[t]}
                </option>
              ))}
            </optgroup>
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
              label={balanceLabel}
              type="text"
              inputMode="decimal"
              placeholder="0.00"
              value={value.opening_balance}
              onChange={(e) => patch('opening_balance', e.target.value)}
              error={errors?.opening_balance}
              style={balanceColor ? { color: balanceColor } : undefined}
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

      {showAmortization && variant === 'full' ? (
        <fieldset
          style={{
            margin: 0,
            padding: spacing.md,
            border: `1px solid ${colors.border}`,
            borderRadius: 8,
            backgroundColor: colors.surfaceMuted,
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.md,
          }}
        >
          <legend
            style={{
              padding: `0 ${spacing.xs}px`,
              fontSize: fontSize.xs,
              fontWeight: fontWeight.semibold,
              color: colors.textMuted,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Cuadro de amortización (francés)
          </legend>
          <p
            style={{
              margin: 0,
              fontSize: fontSize.xs,
              color: colors.textMuted,
              lineHeight: 1.4,
            }}
          >
            Rellena APR, plazo y fecha de inicio para que la app calcule
            la cuota mensual, los intereses y el saldo pendiente a lo
            largo de la vida del préstamo.
          </p>
          <div
            style={{
              display: 'flex',
              gap: spacing.md,
              flexWrap: 'wrap',
              alignItems: 'flex-end',
            }}
          >
            <div style={{ flex: '1 1 140px', minWidth: 0 }}>
              <TextInput
                label="APR anual (%)"
                type="text"
                inputMode="decimal"
                placeholder="3.50"
                value={value.apr_percent}
                onChange={(e) => patch('apr_percent', e.target.value)}
                error={errors?.apr_percent}
              />
            </div>
            <div style={{ flex: '1 1 140px', minWidth: 0 }}>
              <TextInput
                label="Plazo (meses)"
                type="number"
                inputMode="numeric"
                min={1}
                step={1}
                placeholder="360"
                value={value.term_months}
                onChange={(e) => patch('term_months', e.target.value)}
                error={errors?.term_months}
              />
            </div>
            <div style={{ flex: '1 1 160px', minWidth: 0 }}>
              <TextInput
                label="Fecha de inicio"
                type="date"
                value={value.start_date}
                onChange={(e) => patch('start_date', e.target.value)}
                error={errors?.start_date}
              />
            </div>
          </div>
        </fieldset>
      ) : null}
    </div>
  );
}
