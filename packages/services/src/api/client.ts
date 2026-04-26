import axios, {
  type AxiosError,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';

import type { TokenResponse } from '@finanzas/types';

let _accessToken: string | null = null;
let _refreshToken: string | null = null;
let _onAuthFailure: (() => void) | null = null;
let _isRefreshing = false;
interface RefreshQueueEntry {
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}
let _refreshQueue: RefreshQueueEntry[] = [];

export const apiClient = axios.create({
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
});

export interface ConfigureApiOptions {
  baseURL: string;
  /**
   * Si `true`, axios manda cookies en cada petición — necesario para que
   * la cookie httpOnly del refresh token llegue al backend (flujo web). En
   * mobile (Expo) déjalo en `false` y pasa el refresh por body.
   */
  withCredentials?: boolean;
}

export function configureApi(options: ConfigureApiOptions): void {
  apiClient.defaults.baseURL = options.baseURL;
  apiClient.defaults.withCredentials = options.withCredentials ?? false;
}

export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

export function setRefreshToken(token: string | null): void {
  _refreshToken = token;
}

export function setOnAuthFailure(fn: () => void): void {
  _onAuthFailure = fn;
}

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (_accessToken) {
    config.headers.Authorization = `Bearer ${_accessToken}`;
  }
  return config;
});

async function attemptRefresh(): Promise<string | null> {
  // Si el cliente no tiene refresh en memoria (flujo web con cookie httpOnly)
  // mandamos body vacío y el backend extrae el token de la cookie. En mobile,
  // el refresh sí está en memoria y va por body.
  const body = _refreshToken ? { refresh_token: _refreshToken } : {};

  try {
    const response: AxiosResponse<TokenResponse> = await axios.post(
      `${apiClient.defaults.baseURL ?? ''}/auth/refresh`,
      body,
      {
        headers: { 'Content-Type': 'application/json' },
        withCredentials: apiClient.defaults.withCredentials ?? false,
      },
    );
    const { access_token, refresh_token } = response.data;
    _accessToken = access_token;
    // Guardamos el refresh sólo si no estamos usando la cookie. Si estamos en
    // flujo web (withCredentials), el navegador ya gestiona la cookie y el
    // body refresh es información redundante que **no** queremos persistir.
    _refreshToken = apiClient.defaults.withCredentials ? null : refresh_token;
    return access_token;
  } catch {
    _accessToken = null;
    _refreshToken = null;
    return null;
  }
}

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;
    if (!originalRequest || error.response?.status !== 401) {
      return Promise.reject(error);
    }

    if ((originalRequest as unknown as Record<string, unknown>)._retry) {
      _onAuthFailure?.();
      return Promise.reject(error);
    }

    if (_isRefreshing) {
      return new Promise<AxiosResponse>((resolve, reject) => {
        _refreshQueue.push({
          resolve: (token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            resolve(apiClient(originalRequest));
          },
          reject,
        });
      });
    }

    (originalRequest as unknown as Record<string, unknown>)._retry = true;
    _isRefreshing = true;

    try {
      const newToken = await attemptRefresh();
      if (!newToken) {
        _onAuthFailure?.();
        _refreshQueue.forEach((q) => q.reject(error));
        _refreshQueue = [];
        return Promise.reject(error);
      }

      originalRequest.headers.Authorization = `Bearer ${newToken}`;
      _refreshQueue.forEach((q) => q.resolve(newToken));
      _refreshQueue = [];
      return apiClient(originalRequest);
    } finally {
      _isRefreshing = false;
    }
  },
);
