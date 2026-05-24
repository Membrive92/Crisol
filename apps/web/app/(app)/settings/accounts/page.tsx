'use client';

import Link from 'next/link';
import { useState, type FormEvent } from 'react';

import {
  formatApiError,
  useAccountBalances,
  useAccounts,
  useCreateAccount,
  useDeleteAccount,
  useUpdateAccount,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type {
  Account,
  AccountBalance,
  AccountCreateRequest,
  AccountUpdateRequest,
} from '@crisol/types';
import { AMORTIZABLE_ACCOUNT_TYPES, LIABILITY_ACCOUNT_TYPES } from '@crisol/types';
import {
  DEFAULT_CATEGORY_COLOR,
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

import {
  AccountFormFields,
  DEFAULT_ACCOUNT_FORM,
  type AccountFormErrors,
  type AccountFormValue,
} from '@/components/accounts/account-form-fields';
import { AccountSwatch } from '@/components/accounts/account-swatch';
import { DebtPaymentWizard } from '@/components/accounts/debt-payment-wizard';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';

/**
 * Convierte el porcentaje del UI (ej. "3.5") a decimal serializado
 * para el backend (ej. "0.035"). Devuelve `null` si la entrada está
 * vacía o no es numérica. La precisión se mantiene como string para
 * evitar errores de float.
 */
function aprPercentToDecimal(percent: string): string | null {
  const trimmed = percent.trim().replace(',', '.');
  if (!trimmed) return null;
  const numeric = Number(trimmed);
  if (!Number.isFinite(numeric)) return null;
  // Backend caps APR at 4 decimal places (decimal_places=4). Avoid the
  // float artefact where `5.9 / 100` stringifies as "0.05900000000000001".
  return (numeric / 100).toFixed(4);
}

/** Inverso de `aprPercentToDecimal`: serializado backend → string UI. */
function aprDecimalToPercent(decimal: string | null): string {
  if (!decimal) return '';
  const numeric = Number(decimal);
  if (!Number.isFinite(numeric)) return '';
  // Recortamos ceros finales para que "0.035" → "3.5", "0.04" → "4".
  return (numeric * 100).toString();
}

/** Convierte el form en payload para POST. */
function toCreatePayload(form: AccountFormValue): AccountCreateRequest {
  const opening = form.opening_balance.trim().replace(',', '.');
  const payload: AccountCreateRequest = {
    name: form.name.trim(),
    type: form.type,
    currency: form.currency.trim().toUpperCase(),
    color: form.color,
    icon: form.icon,
  };
  if (opening) payload.opening_balance = opening;
  if (AMORTIZABLE_ACCOUNT_TYPES.includes(form.type)) {
    const apr = aprPercentToDecimal(form.apr_percent);
    if (apr !== null) payload.apr = apr;
    const tae = aprPercentToDecimal(form.tae_percent);
    if (tae !== null) payload.tae = tae;
    const term = form.term_months.trim();
    if (term) payload.term_months = Number(term);
    const start = form.start_date.trim();
    if (start) payload.start_date = start;
    const totalRaw = form.total_to_pay.trim().replace(',', '.');
    if (totalRaw) payload.total_to_pay = totalRaw;
    const interestOnlyRaw = form.interest_only_first_payment.trim().replace(',', '.');
    if (interestOnlyRaw) payload.interest_only_first_payment = interestOnlyRaw;
  }
  return payload;
}

/**
 * Genera el payload de update. El campo `opening_balance` del form
 * representa el SALDO ACTUAL que el usuario quiere ver, no el saldo
 * de apertura crudo (para que coincida con lo que ve en la cabecera).
 * Restamos los `movementsBalance` para que current_balance final
 * cuadre con lo introducido.
 *
 * **Excepción PHASE-24.3**: para liabilities amortizables (loan,
 * mortgage, credit_card con plan), el campo "Capital" NO debe
 * controlar el opening_balance vía esta operación — el principal del
 * cuadro vive en las cuotas persistidas y se modifica con
 * "Regenerar cuadro". Si el usuario quiere ajustarlo, debe usar ese
 * flujo. Aquí ignoramos el campo para evitar la trampa que pisaba
 * el opening_balance y des-sincronizaba las cuotas.
 */
function toUpdatePayload(
  form: AccountFormValue,
  movementsBalance?: string,
): AccountUpdateRequest {
  const opening = form.opening_balance.trim().replace(',', '.');
  const payload: AccountUpdateRequest = {
    name: form.name.trim(),
    type: form.type,
    currency: form.currency.trim().toUpperCase(),
    color: form.color,
    icon: form.icon,
  };
  const isAmortizable = AMORTIZABLE_ACCOUNT_TYPES.includes(form.type);
  if (opening && !isAmortizable) {
    if (movementsBalance !== undefined) {
      // El campo es "saldo actual"; el backend almacena opening_balance.
      // Ajustamos: opening = userInput − movements para que el saldo
      // final cuadre con lo introducido (movimientos no se tocan).
      const userValue = Number(opening);
      const mov = Number(movementsBalance);
      if (Number.isFinite(userValue) && Number.isFinite(mov)) {
        payload.opening_balance = (userValue - mov).toFixed(2);
      } else {
        payload.opening_balance = opening;
      }
    } else {
      payload.opening_balance = opening;
    }
  }
  if (AMORTIZABLE_ACCOUNT_TYPES.includes(form.type)) {
    const apr = aprPercentToDecimal(form.apr_percent);
    payload.apr = apr;
    payload.tae = aprPercentToDecimal(form.tae_percent);
    const term = form.term_months.trim();
    payload.term_months = term ? Number(term) : null;
    const start = form.start_date.trim();
    payload.start_date = start ? start : null;
    const totalRaw = form.total_to_pay.trim().replace(',', '.');
    payload.total_to_pay = totalRaw ? totalRaw : null;
    const interestOnlyRaw = form.interest_only_first_payment.trim().replace(',', '.');
    payload.interest_only_first_payment = interestOnlyRaw ? interestOnlyRaw : null;
  } else {
    payload.apr = null;
    payload.tae = null;
    payload.term_months = null;
    payload.start_date = null;
    payload.total_to_pay = null;
    payload.interest_only_first_payment = null;
  }
  return payload;
}

function validate(form: AccountFormValue): AccountFormErrors | null {
  const errors: AccountFormErrors = {};
  if (!form.name.trim()) errors.name = 'El nombre es obligatorio';
  if (form.currency.trim().length !== 3) {
    errors.currency = 'Código ISO de 3 letras (ej: EUR)';
  }
  const opening = form.opening_balance.trim().replace(',', '.');
  if (opening && Number.isNaN(Number(opening))) {
    errors.opening_balance = 'Importe inválido';
  }
  // Para loan/mortgage el principal es obligatorio: sin él el cuadro
  // de amortización no se puede generar (se quedaría con 0 cuotas y
  // todos los cálculos de salud financiera saldrían a 0).
  if (form.type === 'loan' || form.type === 'mortgage') {
    if (!opening) {
      errors.opening_balance =
        'El capital del préstamo es obligatorio (sin él no se genera el cuadro de amortización).';
    } else {
      const value = Number(opening);
      if (!Number.isFinite(value) || value <= 0) {
        errors.opening_balance =
          'El capital debe ser mayor que 0 para préstamos e hipotecas.';
      }
    }
  }
  if (AMORTIZABLE_ACCOUNT_TYPES.includes(form.type)) {
    const aprRaw = form.apr_percent.trim().replace(',', '.');
    if (aprRaw) {
      const apr = Number(aprRaw);
      if (!Number.isFinite(apr) || apr < 0) {
        errors.apr_percent = 'APR inválido (porcentaje, ej. 3.5)';
      }
    }
    const term = form.term_months.trim();
    if (term) {
      const months = Number(term);
      if (!Number.isInteger(months) || months <= 0) {
        errors.term_months = 'Plazo en meses (entero positivo)';
      }
    }
    const start = form.start_date.trim();
    if (start && !/^\d{4}-\d{2}-\d{2}$/.test(start)) {
      errors.start_date = 'Fecha en formato YYYY-MM-DD';
    }
  }
  return Object.keys(errors).length > 0 ? errors : null;
}

export default function AccountsSettingsPage() {
  const [includeArchived, setIncludeArchived] = useState(false);
  const list = useAccounts({ includeArchived });
  const balancesQuery = useAccountBalances();
  const create = useCreateAccount();
  const [form, setForm] = useState<AccountFormValue>(DEFAULT_ACCOUNT_FORM);
  const [createErrors, setCreateErrors] = useState<AccountFormErrors | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);

  // Map id → balance para evitar lookups O(n) por fila al renderizar.
  const balanceById = new Map<string, AccountBalance>();
  for (const item of balancesQuery.data?.items ?? []) {
    balanceById.set(item.account_id, item);
  }

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    const errors = validate(form);
    if (errors) {
      setCreateErrors(errors);
      return;
    }
    setCreateErrors(null);
    create.mutate(toCreatePayload(form), {
      onSuccess: () => {
        setForm(DEFAULT_ACCOUNT_FORM);
        toast.success('Cuenta creada.');
      },
      onError: (err) => setCreateError(formatApiError(err, 'No se pudo crear')),
    });
  }

  const items = list.data ?? [];
  const active = items.filter((a) => !a.is_archived);
  const archived = items.filter((a) => a.is_archived);

  return (
    <div style={{ maxWidth: 760, margin: '0 auto', padding: spacing.lg }}>
      <Link
        href="/settings"
        style={{
          fontSize: fontSize.sm,
          color: colors.textMuted,
          textDecoration: 'none',
        }}
      >
        ← Ajustes
      </Link>

      <header
        style={{
          marginTop: spacing.sm,
          marginBottom: spacing.lg,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: spacing.md,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ flex: '1 1 360px' }}>
          <h1
            style={{
              margin: 0,
              fontSize: fontSize.xl,
              fontWeight: fontWeight.bold,
              color: colors.text,
              letterSpacing: '-0.01em',
            }}
          >
            Cuentas
          </h1>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              fontSize: fontSize.sm,
              color: colors.textMuted,
              lineHeight: 1.4,
            }}
          >
            Cada transacción, importación y ticket se imputa a una cuenta.
            Las cuentas con histórico no se pueden borrar — archívalas
            para conservar las transacciones.
          </p>
        </div>
        <label
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: spacing.xs,
            fontSize: fontSize.sm,
            color: colors.textMuted,
            cursor: 'pointer',
          }}
        >
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(e) => setIncludeArchived(e.target.checked)}
            style={{ margin: 0 }}
          />
          Mostrar archivadas
        </label>
      </header>

      <Card style={{ padding: spacing.lg, marginBottom: spacing.lg }}>
        <h2
          style={{
            margin: 0,
            marginBottom: spacing.md,
            fontSize: fontSize.lg,
            fontWeight: fontWeight.semibold,
            color: colors.text,
          }}
        >
          Nueva cuenta
        </h2>
        <form
          onSubmit={handleCreate}
          style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}
        >
          <AccountFormFields
            value={form}
            onChange={setForm}
            errors={createErrors ?? undefined}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Creando…' : 'Crear'}
            </Button>
          </div>
        </form>
        {createError ? (
          <div
            style={{
              color: colors.danger,
              fontSize: fontSize.sm,
              marginTop: spacing.xs,
            }}
          >
            {createError}
          </div>
        ) : null}
      </Card>

      {list.isLoading ? (
        <p style={{ color: colors.textMuted }}>Cargando…</p>
      ) : list.isError ? (
        <p style={{ color: colors.danger }}>
          {formatApiError(list.error, 'Error cargando cuentas')}
        </p>
      ) : items.length === 0 ? (
        <Card style={{ padding: spacing.lg, textAlign: 'center' }}>
          <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
            Aún no tienes cuentas. Crea la primera arriba.
          </p>
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
          <AccountGroup
            title="Activas"
            items={active}
            balanceById={balanceById}
          />
          {includeArchived && archived.length > 0 ? (
            <AccountGroup
              title="Archivadas"
              items={archived}
              balanceById={balanceById}
            />
          ) : null}
        </div>
      )}
    </div>
  );
}

function AccountGroup({
  title,
  items,
  balanceById,
}: {
  title: string;
  items: Account[];
  balanceById: Map<string, AccountBalance>;
}) {
  if (items.length === 0) {
    return (
      <section>
        <SectionHeader title={title} count={0} />
        <Card style={{ padding: spacing.md }}>
          <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
            Ninguna en esta sección.
          </p>
        </Card>
      </section>
    );
  }
  return (
    <section>
      <SectionHeader title={title} count={items.length} />
      <Card style={{ padding: 0 }}>
        <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
          {items.map((account, idx) => (
            <li
              key={account.id}
              style={{
                borderTop: idx === 0 ? 'none' : `1px solid ${colors.border}`,
              }}
            >
              <AccountRow account={account} balance={balanceById.get(account.id)} />
            </li>
          ))}
        </ul>
      </Card>
    </section>
  );
}

function SectionHeader({ title, count }: { title: string; count: number }) {
  return (
    <h3
      style={{
        margin: 0,
        marginBottom: spacing.sm,
        fontSize: fontSize.sm,
        fontWeight: fontWeight.semibold,
        color: colors.textMuted,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
      }}
    >
      {title}
      {count > 0 ? ` · ${count}` : ''}
    </h3>
  );
}

const TYPE_LABEL: Record<string, string> = {
  bank: 'Banco',
  savings: 'Ahorro',
  brokerage: 'Bróker',
  crypto: 'Crypto',
  cash: 'Efectivo',
  credit_card: 'Tarjeta',
  loan: 'Préstamo',
  mortgage: 'Hipoteca',
};

function AccountRow({
  account,
  balance,
}: {
  account: Account;
  balance: AccountBalance | undefined;
}) {
  const update = useUpdateAccount(account.id);
  const remove = useDeleteAccount();
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [payingDebt, setPayingDebt] = useState(false);
  const [draft, setDraft] = useState<AccountFormValue>(() =>
    fromAccount(account, balance),
  );
  const [errors, setErrors] = useState<AccountFormErrors | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  const isLiability = LIABILITY_ACCOUNT_TYPES.includes(account.type);
  const isAmortizable = AMORTIZABLE_ACCOUNT_TYPES.includes(account.type);
  const hasFullAmortization =
    isAmortizable && !!account.apr && !!account.term_months && !!account.start_date;

  function startEdit() {
    setRowError(null);
    setErrors(null);
    setDraft(fromAccount(account, balance));
    setEditing(true);
  }

  function saveEdit() {
    setRowError(null);
    const v = validate(draft);
    if (v) {
      setErrors(v);
      return;
    }
    setErrors(null);
    update.mutate(toUpdatePayload(draft, balance?.movements_balance), {
      onSuccess: () => {
        setEditing(false);
        toast.success('Cuenta actualizada.');
      },
      onError: (err) => setRowError(formatApiError(err, 'No se pudo guardar')),
    });
  }

  function toggleArchive(next: boolean) {
    setRowError(null);
    update.mutate(
      { is_archived: next },
      {
        onSuccess: () =>
          toast.info(next ? 'Cuenta archivada.' : 'Cuenta restaurada.'),
        onError: (err) =>
          setRowError(formatApiError(err, 'No se pudo cambiar el estado')),
      },
    );
  }

  function handleDelete() {
    setRowError(null);
    remove.mutate(account.id, {
      onSuccess: () => {
        setConfirming(false);
        toast.success('Cuenta eliminada.');
      },
      onError: (err) => {
        setConfirming(false);
        // El backend devuelve 409 con detail español si la cuenta tiene
        // transacciones — el toast lo muestra tal cual.
        toast.error(formatApiError(err, 'No se pudo eliminar'));
        setRowError(formatApiError(err, 'No se pudo eliminar'));
      },
    });
  }

  if (editing) {
    return (
      <div
        style={{
          padding: spacing.md,
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.md,
        }}
      >
        <AccountFormFields
          value={draft}
          onChange={setDraft}
          errors={errors ?? undefined}
        />
        <div
          style={{
            display: 'flex',
            gap: spacing.xs,
            justifyContent: 'flex-end',
          }}
        >
          <Button type="button" variant="ghost" onClick={() => setEditing(false)}>
            Cancelar
          </Button>
          <Button type="button" onClick={saveEdit} disabled={update.isPending}>
            {update.isPending ? 'Guardando…' : 'Guardar'}
          </Button>
        </div>
        {rowError ? (
          <div style={{ color: colors.danger, fontSize: fontSize.sm }}>
            {rowError}
          </div>
        ) : null}
      </div>
    );
  }

  const balanceColor = isLiability ? colors.danger : colors.text;
  const balancePrefix = isLiability ? '-' : '';

  return (
    <div
      style={{
        padding: `${spacing.sm}px ${spacing.md}px`,
        display: 'flex',
        alignItems: 'center',
        gap: spacing.md,
        flexWrap: 'wrap',
      }}
    >
      <AccountSwatch color={account.color} icon={account.icon} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: fontSize.md,
            fontWeight: fontWeight.medium,
            color: colors.text,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {account.name}
          {account.is_archived ? (
            <span
              style={{
                marginLeft: spacing.xs,
                fontSize: fontSize.xs,
                color: colors.textMuted,
                fontWeight: fontWeight.medium,
              }}
            >
              (archivada)
            </span>
          ) : null}
          {isLiability ? (
            <span
              style={{
                marginLeft: spacing.xs,
                fontSize: 10,
                fontWeight: fontWeight.semibold,
                color: colors.danger,
                backgroundColor: colors.dangerSoft,
                padding: '1px 6px',
                borderRadius: radius.sm,
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
              }}
            >
              Deuda
            </span>
          ) : null}
        </div>
        <div style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
          {TYPE_LABEL[account.type] ?? account.type} · {account.currency}
          {balance ? (
            <>
              {' · '}
              <span
                style={{
                  fontWeight: fontWeight.semibold,
                  color: balanceColor,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {balancePrefix}
                {formatAmount(balance.current_balance, balance.currency)}
              </span>
            </>
          ) : null}
        </div>
        {hasFullAmortization ? (
          <div style={{ marginTop: 2 }}>
            <Link
              href={`/personal-finance/accounts/${account.id}/amortization`}
              style={{
                fontSize: fontSize.xs,
                color: colors.primary,
                textDecoration: 'none',
                fontWeight: fontWeight.medium,
              }}
            >
              Ver cuadro →
            </Link>
          </div>
        ) : null}
      </div>
      <div style={{ display: 'flex', gap: spacing.xs, flexWrap: 'wrap' }}>
        {isLiability && !account.is_archived ? (
          <Button
            type="button"
            variant="secondary"
            onClick={() => setPayingDebt(true)}
          >
            Pagar cuota
          </Button>
        ) : null}
        <Button type="button" variant="ghost" onClick={startEdit}>
          Editar
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => toggleArchive(!account.is_archived)}
          disabled={update.isPending}
          style={{ borderRadius: radius.sm }}
        >
          {account.is_archived ? 'Restaurar' : 'Archivar'}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setConfirming(true)}>
          Eliminar
        </Button>
      </div>
      {rowError ? (
        <div
          style={{
            flex: '1 0 100%',
            color: colors.danger,
            fontSize: fontSize.sm,
          }}
        >
          {rowError}
        </div>
      ) : null}
      <ConfirmDialog
        open={confirming}
        title="¿Eliminar cuenta?"
        description={
          <>
            <strong>{account.name}</strong> sólo se podrá eliminar si no
            tiene transacciones. Si tiene histórico, archívala en su lugar.
          </>
        }
        confirmLabel="Eliminar"
        tone="danger"
        loading={remove.isPending}
        onConfirm={handleDelete}
        onCancel={() => setConfirming(false)}
      />
      {isLiability && payingDebt ? (
        <DebtPaymentWizard
          liabilityAccount={account}
          open={payingDebt}
          onClose={() => setPayingDebt(false)}
        />
      ) : null}
    </div>
  );
}

/**
 * Convierte una `Account` (+ su balance calculado opcional) al form.
 *
 * Para el campo "Capital / Saldo" mostramos el `current_balance`
 * (opening_balance + movements) cuando está disponible, no el
 * opening_balance crudo. Razón: para deudas creadas vía "Convertir
 * en operación financiada" el importe vive como tx contraparte
 * (movements_balance) y opening_balance es 0 — el usuario espera ver
 * lo que realmente debe, no un 0 falso.
 */
function fromAccount(
  account: Account,
  balance?: { current_balance: string; movements_balance: string },
): AccountFormValue {
  const display = balance?.current_balance ?? account.opening_balance;
  return {
    name: account.name,
    type: account.type,
    currency: account.currency,
    color: account.color ?? DEFAULT_CATEGORY_COLOR,
    icon: account.icon,
    opening_balance:
      display && display !== '0.00' ? display : '',
    apr_percent: aprDecimalToPercent(account.apr),
    tae_percent: aprDecimalToPercent(account.tae ?? null),
    term_months: account.term_months ? String(account.term_months) : '',
    start_date: account.start_date ?? '',
    total_to_pay: account.total_to_pay ?? '',
    interest_only_first_payment: account.interest_only_first_payment ?? '',
  };
}
