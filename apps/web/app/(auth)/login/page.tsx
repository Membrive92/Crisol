'use client';

import { type FormEvent, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

import { authApi, formatApiError } from '@finanzas/services';
import { useAuthStore } from '@finanzas/store';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { AuthCard } from '@/components/auth/auth-card';
import { AuthInput } from '@/components/auth/auth-input';
import { IconLock, IconMail } from '@/components/auth/icons';
import { PasskeyDivider } from '@/components/auth/passkey-divider';
import { SubmitButton } from '@/components/auth/submit-button';
import {
  PasskeyAbortError,
  authenticateWithPasskey,
  startConditionalAuthentication,
  supportsPasskeys,
} from '@/lib/webauthn';

export default function LoginPage() {
  const router = useRouter();
  const { setTokens, setUser } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [passkeyLoading, setPasskeyLoading] = useState(false);
  const [passkeySupported, setPasskeySupported] = useState(false);

  useEffect(() => {
    setPasskeySupported(supportsPasskeys());
  }, []);

  // Conditional UI: arranca un startAuthentication "en background" que se
  // queda esperando a que el usuario seleccione una passkey desde el
  // autocompletado del input email. Si el navegador no lo soporta o el
  // usuario nunca interactúa, no pasa nada.
  useEffect(() => {
    let cancelled = false;
    async function run() {
      try {
        const tokens = await startConditionalAuthentication();
        if (cancelled || !tokens) return;
        setTokens(tokens.access_token, tokens.refresh_token);
        const me = await authApi.getMe();
        if (cancelled) return;
        setUser(me);
        router.replace('/dashboard');
      } catch {
        // Conditional UI es best-effort: el usuario aún puede usar el
        // botón clásico o password. Silencioso a propósito.
      }
    }
    void run();
    return () => {
      cancelled = true;
    };
  }, [router, setTokens, setUser]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const tokens = await authApi.login({ email, password, remember_me: rememberMe });
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

  async function handlePasskeyLogin() {
    setError('');
    if (!email.trim()) {
      setError('Escribe tu email para entrar con passkey.');
      return;
    }
    setPasskeyLoading(true);
    try {
      const tokens = await authenticateWithPasskey(email);
      setTokens(tokens.access_token, tokens.refresh_token);
      const user = await authApi.getMe();
      setUser(user);
      router.replace('/dashboard');
    } catch (err) {
      if (err instanceof PasskeyAbortError) {
        // Usuario canceló el diálogo del SO — no es un error real, no
        // mostramos nada para no asustarle.
        return;
      }
      setError(formatApiError(err, 'No se pudo autenticar con passkey.'));
    } finally {
      setPasskeyLoading(false);
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
          autoComplete="email webauthn"
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
          autoComplete="current-password webauthn"
          icon={<IconLock size={18} />}
        />
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: spacing.sm,
            fontSize: fontSize.sm,
            color: colors.textMuted,
            cursor: 'pointer',
            userSelect: 'none',
          }}
        >
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
            style={{
              width: 16,
              height: 16,
              accentColor: colors.primary,
              cursor: 'pointer',
            }}
          />
          Recuérdame durante 30 días
        </label>
        <SubmitButton loading={loading} loadingLabel="Entrando…">
          Entrar
        </SubmitButton>

        {passkeySupported ? (
          <>
            <PasskeyDivider />
            <button
              type="button"
              onClick={handlePasskeyLogin}
              disabled={passkeyLoading}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: spacing.sm,
                width: '100%',
                padding: `${spacing.sm + 4}px ${spacing.md}px`,
                backgroundColor: colors.surface,
                color: colors.text,
                border: `1px solid ${colors.border}`,
                borderRadius: radius.sm,
                fontSize: fontSize.md,
                fontWeight: fontWeight.medium,
                cursor: passkeyLoading ? 'not-allowed' : 'pointer',
                opacity: passkeyLoading ? 0.6 : 1,
              }}
            >
              <span aria-hidden="true">🔑</span>
              <span>
                {passkeyLoading ? 'Esperando dispositivo…' : 'Entrar con passkey'}
              </span>
            </button>
          </>
        ) : null}
      </form>
    </AuthCard>
  );
}
