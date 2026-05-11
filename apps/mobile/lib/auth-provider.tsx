import { useEffect, useRef } from 'react';

import * as SecureStore from 'expo-secure-store';

import { configureApi, setAccessToken, setOnAuthFailure, setRefreshToken } from '@crisol/services';
import { useAuthStore } from '@crisol/store';

const API_URL = process.env['EXPO_PUBLIC_API_URL'] ?? 'http://localhost:8000';

const REFRESH_KEY = 'finanzas_refresh_token';

export function useAuthInit() {
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    configureApi({ baseURL: API_URL });

    setOnAuthFailure(() => {
      useAuthStore.getState().logout();
      SecureStore.deleteItemAsync(REFRESH_KEY);
    });

    SecureStore.getItemAsync(REFRESH_KEY).then((refreshToken) => {
      if (refreshToken) {
        setRefreshToken(refreshToken);
        useAuthStore.getState().hydrate(null, refreshToken, null);
      } else {
        useAuthStore.getState().hydrate(null, null, null);
      }
    });

    useAuthStore.subscribe((state) => {
      setAccessToken(state.accessToken);
      if (state.refreshToken) {
        setRefreshToken(state.refreshToken);
        SecureStore.setItemAsync(REFRESH_KEY, state.refreshToken);
      } else {
        setRefreshToken(null);
        SecureStore.deleteItemAsync(REFRESH_KEY);
      }
    });
  }, []);
}
