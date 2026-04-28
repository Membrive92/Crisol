'use client';

import { type CSSProperties, type FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

import { authApi, formatApiError } from '@finanzas/services';
import { useAuthStore } from '@finanzas/store';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

const inputStyle: CSSProperties = {
  padding: spacing.sm + 2,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.sm,
  fontSize: fontSize.md,
  backgroundColor: colors.surface,
  color: colors.text,
};

const buttonStyle: CSSProperties = {
  padding: spacing.sm + 2,
  background: colors.primary,
  color: '#ffffff',
  border: 'none',
  borderRadius: radius.sm,
  fontSize: fontSize.md,
  fontWeight: fontWeight.semibold,
  cursor: 'pointer',
};

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
    <>
      <h1
        style={{
          margin: `0 0 ${spacing.lg}px`,
          fontSize: fontSize.xl,
          fontWeight: fontWeight.semibold,
          color: colors.text,
          textAlign: 'center',
        }}
      >
        Iniciar sesión
      </h1>
      {error ? (
        <p
          style={{
            color: colors.danger,
            fontSize: fontSize.sm,
            textAlign: 'center',
            marginBottom: spacing.sm,
          }}
        >
          {error}
        </p>
      ) : null}
      <form
        onSubmit={handleSubmit}
        style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}
      >
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
          style={inputStyle}
        />
        <input
          type="password"
          placeholder="Contraseña"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          autoComplete="current-password"
          style={inputStyle}
        />
        <button type="submit" disabled={loading} style={buttonStyle}>
          {loading ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
      <p
        style={{
          marginTop: spacing.md,
          textAlign: 'center',
          fontSize: fontSize.sm,
          color: colors.textMuted,
        }}
      >
        ¿No tienes cuenta?{' '}
        <Link
          href="/register"
          style={{ color: colors.primary, fontWeight: fontWeight.medium }}
        >
          Regístrate
        </Link>
      </p>
    </>
  );
}
