'use client';

import { type FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

import { authApi } from '@finanzas/services';
import { useAuthStore } from '@finanzas/store';

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
      router.replace('/home');
    } catch {
      setError('Credenciales incorrectas');
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <h1 style={{ margin: '0 0 1.5rem', fontSize: '1.5rem', textAlign: 'center' }}>
        Iniciar sesión
      </h1>
      {error && (
        <p style={{ color: '#d32f2f', fontSize: '0.875rem', textAlign: 'center' }}>{error}</p>
      )}
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          style={inputStyle}
        />
        <input
          type="password"
          placeholder="Contraseña"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          style={inputStyle}
        />
        <button type="submit" disabled={loading} style={buttonStyle}>
          {loading ? 'Entrando...' : 'Entrar'}
        </button>
      </form>
      <p style={{ marginTop: '1rem', textAlign: 'center', fontSize: '0.875rem' }}>
        ¿No tienes cuenta?{' '}
        <Link href="/register" style={{ color: '#1976d2' }}>
          Regístrate
        </Link>
      </p>
    </>
  );
}

const inputStyle: React.CSSProperties = {
  padding: '0.75rem',
  border: '1px solid #ddd',
  borderRadius: 6,
  fontSize: '1rem',
};

const buttonStyle: React.CSSProperties = {
  padding: '0.75rem',
  background: '#1976d2',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  fontSize: '1rem',
  cursor: 'pointer',
};
