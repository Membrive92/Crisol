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
  return (numeric / 100).toString();
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
    const term = form.term_months.trim();
    if (term) payload.term_months = Number(term);
    const start = form.start_date.trim();
    if (start) payload.start_date = start;
  }
  return payload;
}

function toUpdatePayload(form: AccountFormValue): AccountUpdateRequest {
  const opening = form.opening_balance.trim().replace(',', '.');
  const payload: AccountUpdateRequest = {
    name: form.name.trim(),
    type: form.type,
    currency: form.currency.trim().toUpperCase(),
    color: form.color,
    icon: form.icon,
  };
  if (opening) payload.opening_balance = opening;
  if (AMORTIZABLE_ACCOUNT_TYPES.includes(form.type)) {
    const apr = aprPercentToDecimal(form.apr_percent);
    // Si el usuario vacía el APR explícitamente, mandamos `null` para
    // limpiar el valor en BD; si nunca lo tocó, igualmente apr === null
    // (cadena vacía) y el backend lo trata como "sin cambio para los
    // campos opcionales con null". Mismo razonamiento para term/start.
    payload.apr = apr;
    const term = form.term_months.trim();
    payload.term_months = term ? Number(term) : null;
    const start = form.start_date.trim();
    payload.start_date = start ? start : null;
  } else {
    // Cambió a un tipo no amortizable — limpiamos los campos por si
    // tenían valor previo (ya el form los reseteó visualmente).
    payload.apr = null;
    payload.term_months = null;
    payload.start_date = null;
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
  const [draft, setDraft] = useState<AccountFormValue>(() => fromAccount(account));
  const [errors, setErrors] = useState<AccountFormErrors | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  const isLiability = LIABILITY_ACCOUNT_TYPES.includes(account.type);
  const isAmortizable = AMORTIZABLE_ACCOUNT_TYPES.includes(account.type);
  const hasFullAmortization =
    isAmortizable && !!account.apr && !!account.term_months && !!account.start_date;

  function startEdit() {
    setRowError(null);
    setErrors(null);
    setDraft(fromAccount(account));
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
    update.mutate(toUpdatePayload(draft), {
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

function fromAccount(account: Account): AccountFormValue {
  return {
    name: account.name,
    type: account.type,
    currency: account.currency,
    color: account.color ?? DEFAULT_CATEGORY_COLOR,
    icon: account.icon,
    opening_balance:
      account.opening_balance && account.opening_balance !== '0.00'
        ? account.opening_balance
        : '',
    apr_percent: aprDecimalToPercent(account.apr),
    term_months: account.term_months ? String(account.term_months) : '',
    start_date: account.start_date ?? '',
  };
}
