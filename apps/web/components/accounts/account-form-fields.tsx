'use client';

import { useCategories } from '@crisol/services';
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
   * TIN anual (porcentaje en UI, ej. "5.9" para 5.9%). Vacío = sin valor.
   * Aplica a tipos amortizables (loan/mortgage/credit_card PHASE-24.2).
   */
  apr_percent: string;
  /** PHASE-24.2 — TAE anual (% UI). Informativa, no afecta cálculo. */
  tae_percent: string;
  /** Plazo en meses como string para input numérico. Vacío = sin valor. */
  term_months: string;
  /** YYYY-MM-DD. Vacío = sin valor. */
  start_date: string;
  /** PHASE-24.3 — Total contractualizado por el banco (€). */
  total_to_pay: string;
  /** PHASE-24.3 — Primer pago sólo de intereses (€). Casi siempre 0. */
  interest_only_first_payment: string;
  /** PHASE-30.4 — Categoría de pagos vinculada. Sólo se rellena en
   * liabilities; el wizard la envía como `category_id` al backend
   * (cadena vacía = sin vincular). */
  category_id: string;
}

export interface AccountFormErrors {
  name?: string | undefined;
  currency?: string | undefined;
  opening_balance?: string | undefined;
  apr_percent?: string | undefined;
  tae_percent?: string | undefined;
  term_months?: string | undefined;
  start_date?: string | undefined;
  total_to_pay?: string | undefined;
  interest_only_first_payment?: string | undefined;
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
  tae_percent: '',
  term_months: '',
  start_date: '',
  total_to_pay: '',
  interest_only_first_payment: '',
  category_id: '',
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
  const categoriesQuery = useCategories();
  const debtCategories = (categoriesQuery.data ?? []).filter(
    (c) => c.role === 'DEBT_PAYMENT' || c.role === 'DEBT_INTEREST',
  );

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
        tae_percent: '',
        term_months: '',
        start_date: '',
        total_to_pay: '',
        interest_only_first_payment: '',
        // category_id sólo aplica a liabilities. Al cambiar a asset
        // limpiamos para no enviar un vínculo inválido al backend.
        category_id: isLiabilityType(nextType) ? value.category_id : '',
      });
      return;
    }
    onChange({
      ...value,
      type: nextType,
      category_id: isLiabilityType(nextType) ? value.category_id : '',
    });
  }

  const isLiability = isLiabilityType(value.type);
  const showAmortization = isAmortizableType(value.type);
  // Para loan/mortgage el principal es obligatorio (sin él no se genera
  // el cuadro). Para credit_card y assets el saldo inicial es opcional.
  const capitalRequired = value.type === 'loan' || value.type === 'mortgage';
  const balanceLabel = isLiability
    ? capitalRequired
      ? 'Capital'
      : 'Capital (opcional)'
    : 'Saldo inicial (opcional)';
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
              required={capitalRequired}
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

      {isLiability && variant === 'full' ? (
        <div>
          <Select
            label="Categoría de pagos vinculada (opcional)"
            value={value.category_id}
            onChange={(e) => patch('category_id', e.target.value)}
            disabled={categoriesQuery.isLoading || debtCategories.length === 0}
          >
            <option value="">— Sin vincular —</option>
            {debtCategories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.icon ? `${c.icon} ` : ''}
                {c.name}
              </option>
            ))}
          </Select>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              fontSize: fontSize.xs,
              color: colors.textMuted,
              lineHeight: 1.4,
            }}
          >
            {debtCategories.length === 0
              ? 'No tienes categorías con rol de deuda todavía. Crea una en Ajustes › Categorías marcando rol DEBT_PAYMENT o DEBT_INTEREST.'
              : 'Si las cuotas de este contrato aparecen en tus transacciones bajo una categoría, vincúlala aquí para cruzar Capa 1 (flujo) con Capa 2 (saldo) en el módulo de deuda.'}
          </p>
        </div>
      ) : null}

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
            Rellena TIN, plazo y fecha de inicio para que la app calcule
            la cuota mensual, los intereses y el saldo pendiente. TAE es
            informativa (la usan los bancos para legal disclosure) y
            no afecta al cálculo.
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
                label="TIN anual (%)"
                type="text"
                inputMode="decimal"
                placeholder="5,90"
                value={value.apr_percent}
                onChange={(e) => patch('apr_percent', e.target.value)}
                error={errors?.apr_percent}
              />
            </div>
            <div style={{ flex: '1 1 140px', minWidth: 0 }}>
              <TextInput
                label="TAE anual (%) opc."
                type="text"
                inputMode="decimal"
                placeholder="6,12"
                value={value.tae_percent}
                onChange={(e) => patch('tae_percent', e.target.value)}
                error={errors?.tae_percent}
              />
            </div>
            <div style={{ flex: '1 1 140px', minWidth: 0 }}>
              <TextInput
                label="Plazo (meses)"
                type="number"
                inputMode="numeric"
                min={1}
                step={1}
                placeholder="12"
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
          <p
            style={{
              margin: `${spacing.md}px 0 ${spacing.xs}px 0`,
              fontSize: fontSize.xs,
              color: colors.textMuted,
              lineHeight: 1.4,
            }}
          >
            Si copias estos datos de tu banco (ej. pantalla
            "Datos de la financiación" en BBVA), puedes pegar el
            <strong> Total a pagar</strong> tal cual — destaparemos
            como "cargos extra" cualquier diferencia con el cuadro
            teórico (comisiones que el banco no desglosa).
          </p>
          <div
            style={{
              display: 'flex',
              gap: spacing.md,
              flexWrap: 'wrap',
              alignItems: 'flex-end',
            }}
          >
            <div style={{ flex: '1 1 160px', minWidth: 0 }}>
              <TextInput
                label="Total a pagar (€) opc."
                type="text"
                inputMode="decimal"
                placeholder="913,86"
                value={value.total_to_pay}
                onChange={(e) => patch('total_to_pay', e.target.value)}
                error={errors?.total_to_pay}
              />
            </div>
            <div style={{ flex: '1 1 200px', minWidth: 0 }}>
              <TextInput
                label="1er pago sólo intereses (€) opc."
                type="text"
                inputMode="decimal"
                placeholder="0,00"
                value={value.interest_only_first_payment}
                onChange={(e) =>
                  patch('interest_only_first_payment', e.target.value)
                }
                error={errors?.interest_only_first_payment}
              />
            </div>
          </div>
        </fieldset>
      ) : null}
    </div>
  );
}
