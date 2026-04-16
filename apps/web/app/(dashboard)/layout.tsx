'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { useAuthStore } from '@finanzas/store';
import { authApi } from '@finanzas/services';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isHydrated, accessToken, refreshToken, setTokens, setUser, logout } =
    useAuthStore();

  useEffect(() => {
    if (!isHydrated) return;

    if (!isAuthenticated && !refreshToken) {
      router.replace('/login');
      return;
    }

    if (!accessToken && refreshToken) {
      authApi
        .refresh(refreshToken)
        .then((tokens) => {
          setTokens(tokens.access_token, tokens.refresh_token);
          return authApi.getMe();
        })
        .then((user) => setUser(user))
        .catch(() => {
          logout();
          router.replace('/login');
        });
      return;
    }

    if (accessToken && !useAuthStore.getState().user) {
      authApi
        .getMe()
        .then((user) => setUser(user))
        .catch(() => {
          logout();
          router.replace('/login');
        });
    }
  }, [isHydrated, isAuthenticated, accessToken, refreshToken, setTokens, setUser, logout, router]);

  if (!isHydrated || !isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
