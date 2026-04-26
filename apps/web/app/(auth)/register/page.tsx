'use client';

import { type FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

import { authApi, formatApiError } from '@finanzas/services';
import { useAuthStore } from '@finanzas/store';

export default function RegisterPage() {
  const router = useRouter();
  const { setTokens, setUser } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
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
    <>
      <h1 style={{ margin: '0 0 1.5rem', fontSize: '1.5rem', textAlign: 'center' }}>
        Crear cuenta
      </h1>
      {error && (
        <p style={{ color: '#d32f2f', fontSize: '0.875rem', textAlign: 'center' }}>{error}</p>
      )}
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <input
          type="text"
          placeholder="Nombre"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          required
          style={inputStyle}
        />
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
          placeholder="Contraseña (mín. 8 caracteres)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          style={inputStyle}
        />
        <button type="submit" disabled={loading} style={buttonStyle}>
          {loading ? 'Registrando...' : 'Registrarse'}
        </button>
      </form>
      <p style={{ marginTop: '1rem', textAlign: 'center', fontSize: '0.875rem' }}>
        ¿Ya tienes cuenta?{' '}
        <Link href="/login" style={{ color: '#1976d2' }}>
          Inicia sesión
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
