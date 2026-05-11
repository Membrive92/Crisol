'use client';

import { type FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

import { authApi, formatApiError } from '@crisol/services';
import { useAuthStore } from '@crisol/store';
import { colors, fontWeight, spacing } from '@crisol/ui';

import { AuthCard } from '@/components/auth/auth-card';
import { AuthInput } from '@/components/auth/auth-input';
import { IconLock, IconMail, IconUser } from '@/components/auth/icons';
import { SubmitButton } from '@/components/auth/submit-button';

export default function RegisterPage() {
  const router = useRouter();
  const { setTokens, setUser } = useAuthStore();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const tokens = await authApi.register({
        email,
        password,
        display_name: displayName,
      });
      setTokens(tokens.access_token, tokens.refresh_token);
      const user = await authApi.getMe();
      setUser(user);
      router.replace('/dashboard');
    } catch (err) {
      setError(formatApiError(err, 'No se pudo completar el registro.'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthCard
      title="Crea tu cuenta"
      subtitle="Tus datos se guardan en local. Sin cuentas externas, sin tracking."
      errorMessage={error || undefined}
      footer={
        <>
          ¿Ya tienes cuenta?{' '}
          <Link
            href="/login"
            style={{ color: colors.primary, fontWeight: fontWeight.semibold }}
          >
            Inicia sesión
          </Link>
        </>
      }
    >
      <form
        onSubmit={handleSubmit}
        noValidate
        style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}
      >
        <AuthInput
          label="Nombre"
          type="text"
          placeholder="¿Cómo te llamas?"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          required
          autoComplete="name"
          autoFocus
          icon={<IconUser size={18} />}
        />
        <AuthInput
          label="Email"
          type="email"
          placeholder="tu@email.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
          icon={<IconMail size={18} />}
        />
        <AuthInput
          label="Contraseña"
          type="password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          autoComplete="new-password"
          icon={<IconLock size={18} />}
          hint="Mínimo 8 caracteres."
        />
        <SubmitButton loading={loading} loadingLabel="Registrando…">
          Crear cuenta
        </SubmitButton>
      </form>
    </AuthCard>
  );
}
