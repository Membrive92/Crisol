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

export function configureApi(config: { baseURL: string }): void {
  apiClient.defaults.baseURL = config.baseURL;
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
  if (!_refreshToken) return null;

  try {
    const response: AxiosResponse<TokenResponse> = await axios.post(
      `${apiClient.defaults.baseURL ?? ''}/auth/refresh`,
      { refresh_token: _refreshToken },
      { headers: { 'Content-Type': 'application/json' } },
    );
    const { access_token, refresh_token } = response.data;
    _accessToken = access_token;
    _refreshToken = refresh_token;
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
