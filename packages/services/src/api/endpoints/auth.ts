import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  User,
} from '@finanzas/types';

import { apiClient } from '../client';

export const authApi = {
  async register(data: RegisterRequest): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/register', data);
    return response.data;
  },

  async login(data: LoginRequest): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/login', data);
    return response.data;
  },

  async refresh(refreshToken: string): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    });
    return response.data;
  },

  async logout(refreshToken: string): Promise<void> {
    await apiClient.post('/auth/logout', { refresh_token: refreshToken });
  },

  async getMe(): Promise<User> {
    const response = await apiClient.get<User>('/auth/me');
    return response.data;
  },
};
