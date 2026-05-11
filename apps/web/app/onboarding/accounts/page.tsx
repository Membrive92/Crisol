'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';

import {
  formatApiError,
  useAccounts,
  useCreateAccount,
} from '@crisol/services';
import { toast, useAuthStore } from '@crisol/store';
import type { AccountCreateRequest } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  radius,
  spacing,
} from '@crisol/ui';

import {
  AccountFormFields,
  DEFAULT_ACCOUNT_FORM,
  type AccountFormErrors,
  type AccountFormValue,
} from '@/components/accounts/account-form-fields';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

const REDIRECT_TARGET = '/personal-finance';

function validate(form: AccountFormValue): AccountFormErrors | null {
  const errors: AccountFormErrors = {};
  if (!form.name.trim()) errors.name = 'El nombre es obligatorio';
  if (form.currency.trim().length !== 3) {
    errors.currency = 'Código ISO de 3 letras (ej: EUR)';
  }
  return Object.keys(errors).length > 0 ? errors : null;
}

function toCreatePayload(form: AccountFormValue): AccountCreateRequest {
  return {
    name: form.name.trim(),
    type: form.type,
    currency: form.currency.trim().toUpperCase(),
  };
}

/**
 * Pantalla bloqueante de "primera cuenta". Una sola vez por usuario:
 * tras crear la cuenta, el guard del layout `(app)` deja de redirigir y
 * el resto de pantallas pueden funcionar.
 */
export default function OnboardingAccountsPage() {
  const router = useRouter();
  const { isAuthenticated, isHydrated } = useAuthStore();

  // Aún sin sesión → fuera. El guard del layout `(app)` empuja aquí
  // sólo cuando hay sesión y la lista está vacía, pero alguien podría
  // entrar directo por URL antes de loguearse.
  useEffect(() => {
    if (!isHydrated) return;
    if (!isAuthenticated) router.replace('/login');
  }, [isAuthenticated, isHydrated, router]);

  // Si por lo que sea ya tiene cuentas (refresh tras crear), salimos.
  const accountsQuery = useAccounts();
  useEffect(() => {
    if (accountsQuery.data && accountsQuery.data.length > 0) {
      router.replace(REDIRECT_TARGET);
    }
  }, [accountsQuery.data, router]);

  const create = useCreateAccount();
  const [form, setForm] = useState<AccountFormValue>(DEFAULT_ACCOUNT_FORM);
  const [errors, setErrors] = useState<AccountFormErrors | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    const v = validate(form);
    if (v) {
      setErrors(v);
      return;
    }
    setErrors(null);
    create.mutate(toCreatePayload(form), {
      onSuccess: () => {
        toast.success('Cuenta creada. ¡A registrar!');
        router.replace(REDIRECT_TARGET);
      },
      onError: (err) => setSubmitError(formatApiError(err, 'No se pudo crear')),
    });
  }

  return (
    <div
      style={{
        width: '100%',
        maxWidth: 540,
        padding: spacing.lg,
        boxSizing: 'border-box',
      }}
    >
      <header style={{ marginBottom: spacing.lg, textAlign: 'center' }}>
        <h1
          style={{
            margin: 0,
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: colors.text,
            letterSpacing: '-0.02em',
            lineHeight: 1.1,
          }}
        >
          Bienvenido
        </h1>
        <p
          style={{
            margin: `${spacing.sm}px 0 0 0`,
            fontSize: fontSize.md,
            color: colors.textMuted,
            lineHeight: 1.5,
          }}
        >
          Antes de empezar, declara tu primera cuenta — necesitarás imputar
          cada transacción a una cuenta para que los KPIs sean correctos.
        </p>
      </header>

      <Card style={{ padding: spacing.lg }}>
        <form
          onSubmit={handleSubmit}
          style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}
        >
          <AccountFormFields
            value={form}
            onChange={setForm}
            variant="minimal"
            errors={errors ?? undefined}
          />
          {submitError ? (
            <div
              role="alert"
              style={{
                padding: spacing.sm,
                border: `1px solid ${colors.danger}`,
                borderRadius: radius.sm,
                color: colors.danger,
                fontSize: fontSize.sm,
              }}
            >
              {submitError}
            </div>
          ) : null}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Creando…' : 'Crear cuenta'}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
