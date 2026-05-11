'use client';

import { useEffect, useRef } from 'react';

import { configureApi, setAccessToken, setOnAuthFailure } from '@crisol/services';
import { useAuthStore } from '@crisol/store';

const API_URL = process.env['NEXT_PUBLIC_API_URL'] ?? '/api';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    // El refresh viaja en cookie httpOnly. axios necesita `withCredentials`
    // para que el navegador la incluya en cada request al backend (vía
    // /api/* rewrite, así que la cookie es same-origin).
    configureApi({ baseURL: API_URL, withCredentials: true });

    setOnAuthFailure(() => {
      useAuthStore.getState().logout();
      window.location.href = '/login';
    });

    // No leemos refresh de localStorage: vive en cookie httpOnly. El
    // dashboard layout intentará un /auth/refresh al montar; si la cookie
    // no existe o expiró, redirige a login.
    useAuthStore.getState().hydrate(null, null, null);

    useAuthStore.subscribe((state) => {
      setAccessToken(state.accessToken);
    });
  }, []);

  return <>{children}</>;
}
