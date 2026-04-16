'use client';

import { useEffect, useRef } from 'react';

import { configureApi, setAccessToken, setOnAuthFailure, setRefreshToken } from '@finanzas/services';
import { useAuthStore } from '@finanzas/store';

const API_URL = process.env['NEXT_PUBLIC_API_URL'] ?? 'http://localhost:8000';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    configureApi({ baseURL: API_URL });

    setOnAuthFailure(() => {
      useAuthStore.getState().logout();
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
    });

    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
      setRefreshToken(refreshToken);
      useAuthStore.getState().hydrate(null, refreshToken, null);
    } else {
      useAuthStore.getState().hydrate(null, null, null);
    }

    useAuthStore.subscribe((state) => {
      setAccessToken(state.accessToken);
      if (state.refreshToken) {
        setRefreshToken(state.refreshToken);
        localStorage.setItem('refresh_token', state.refreshToken);
      } else {
        setRefreshToken(null);
        localStorage.removeItem('refresh_token');
      }
    });
  }, []);

  return <>{children}</>;
}
