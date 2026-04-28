'use client';

import { type FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

import { authApi, formatApiError } from '@finanzas/services';
import { useAuthStore } from '@finanzas/store';
import { colors, fontWeight, spacing } from '@finanzas/ui';

import { AuthCard } from '@/components/auth/auth-card';
import { AuthInput } from '@/components/auth/auth-input';
import { IconLock, IconMail } from '@/components/auth/icons';
import { SubmitButton } from '@/components/auth/submit-button';

export default function LoginPage() {
  const router = useRouter();
  const { setTokens, setUser } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const tokens = await authApi.login({ email, password });
      setTokens(tokens.access_token, tokens.refresh_token);
      const user = await authApi.getMe();
      setUser(user);
      router.replace('/dashboard');
    } catch (err) {
      setError(formatApiError(err, 'Credenciales incorrectas.'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthCard
      title="Bienvenido de nuevo"
      subtitle="Accede para revisar tus gastos, importes y tickets."
      errorMessage={error || undefined}
      footer={
        <>
          ¿No tienes cuenta?{' '}
          <Link
            href="/register"
            style={{ color: colors.primary, fontWeight: fontWeight.semibold }}
          >
            Regístrate
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
          label="Email"
          type="email"
          placeholder="tu@email.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
          autoFocus
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
          autoComplete="current-password"
          icon={<IconLock size={18} />}
        />
        <SubmitButton loading={loading} loadingLabel="Entrando…">
          Entrar
        </SubmitButton>
      </form>
    </AuthCard>
  );
}
