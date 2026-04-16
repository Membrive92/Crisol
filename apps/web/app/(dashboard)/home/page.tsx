'use client';

import { useRouter } from 'next/navigation';

import { authApi } from '@finanzas/services';
import { useAuthStore } from '@finanzas/store';

export default function HomePage() {
  const router = useRouter();
  const { user, refreshToken, logout: clearAuth } = useAuthStore();

  async function handleLogout() {
    try {
      if (refreshToken) {
        await authApi.logout(refreshToken);
      }
    } finally {
      clearAuth();
      router.replace('/login');
    }
  }

  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem',
      }}
    >
      <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>
        Bienvenido, {user?.display_name ?? 'usuario'}
      </h1>
      <p style={{ color: '#666', marginBottom: '2rem' }}>{user?.email}</p>
      <button
        onClick={handleLogout}
        style={{
          padding: '0.75rem 2rem',
          background: '#d32f2f',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          fontSize: '1rem',
          cursor: 'pointer',
        }}
      >
        Cerrar sesión
      </button>
    </main>
  );
}
