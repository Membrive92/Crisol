import { useEffect } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { authApi, useAccounts } from '@crisol/services';
import { useAuthStore } from '@crisol/store';

import { Toaster } from '../components/ui/toaster';
import { useAuthInit } from '../lib/auth-provider';
import { QueryProvider } from '../lib/query-provider';

export default function RootLayout() {
  return (
    <QueryProvider>
      <RootLayoutInner />
    </QueryProvider>
  );
}

/**
 * Vive dentro del `QueryProvider` para poder usar `useAccounts` en el
 * guard de onboarding (PHASE-19.1). El `useAccounts` se monta siempre
 * pero `enabled` no aplica porque el endpoint sólo devuelve datos
 * cuando hay sesión válida — fuera de sesión TanStack queda en idle y
 * el guard simplemente no actúa.
 */
function RootLayoutInner() {
  useAuthInit();

  const router = useRouter();
  const segments = useSegments();
  const { isAuthenticated, isHydrated, refreshToken, setTokens, setUser, logout } = useAuthStore();
  const accountsQuery = useAccounts();

  useEffect(() => {
    if (!isHydrated) return;

    const inAuthGroup = segments[0] === '(auth)';
    const inOnboardingGroup = segments[0] === 'onboarding';

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
      return;
    }

    if (isAuthenticated && inAuthGroup) {
      router.replace('/(modules)/personal-finance/(tabs)/analysis');
      return;
    }

    // PHASE-19.1: si hay sesión y la lista de cuentas ya cargó vacía,
    // empujamos al onboarding. Si la query falla (red caída, 5xx) no
    // redirigimos — sería peor atrapar al usuario en onboarding. La
    // pantalla destino renderiza su propio estado de error si hace falta.
    if (
      isAuthenticated &&
      !inOnboardingGroup &&
      !accountsQuery.isLoading &&
      !accountsQuery.isError &&
      (accountsQuery.data ?? []).length === 0
    ) {
      router.replace('/onboarding/accounts');
    }
  }, [
    isAuthenticated,
    isHydrated,
    segments,
    refreshToken,
    setTokens,
    setUser,
    logout,
    router,
    accountsQuery.data,
    accountsQuery.isLoading,
    accountsQuery.isError,
  ]);

  return (
    <>
      <StatusBar style="auto" />
      <Stack>
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />
        <Stack.Screen name="(modules)" options={{ headerShown: false }} />
        <Stack.Screen name="onboarding" options={{ headerShown: false }} />
      </Stack>
      <Toaster />
    </>
  );
}
