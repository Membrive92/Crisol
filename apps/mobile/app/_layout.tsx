import { useEffect } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { authApi } from '@finanzas/services';
import { useAuthStore } from '@finanzas/store';

import { useAuthInit } from '../lib/auth-provider';
import { QueryProvider } from '../lib/query-provider';

export default function RootLayout() {
  useAuthInit();

  const router = useRouter();
  const segments = useSegments();
  const { isAuthenticated, isHydrated, refreshToken, setTokens, setUser, logout } = useAuthStore();

  useEffect(() => {
    if (!isHydrated) return;

    const inAuthGroup = segments[0] === '(auth)';

    if (!isAuthenticated && refreshToken) {
      authApi
        .refresh(refreshToken)
        .then((tokens) => {
          setTokens(tokens.access_token, tokens.refresh_token);
          return authApi.getMe();
        })
        .then((user) => {
          setUser(user);
        })
        .catch(() => {
          logout();
        });
      return;
    }

    if (!isAuthenticated && !inAuthGroup) {
      router.replace('/(auth)/login');
    } else if (isAuthenticated && inAuthGroup) {
      router.replace('/(tabs)/home');
    }
  }, [isAuthenticated, isHydrated, segments, refreshToken, setTokens, setUser, logout, router]);

  return (
    <QueryProvider>
      <StatusBar style="auto" />
      <Stack>
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="transaction/new" options={{ title: 'Nueva transacción' }} />
        <Stack.Screen name="transaction/[id]" options={{ title: 'Editar transacción' }} />
      </Stack>
    </QueryProvider>
  );
}
