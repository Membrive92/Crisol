import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  User,
} from '@crisol/types';

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

  /**
   * Rota el refresh token. En web déjalo sin argumento — el navegador
   * envía la cookie httpOnly. En mobile pasa el token guardado en
   * `expo-secure-store`.
   */
  async refresh(refreshToken?: string): Promise<TokenResponse> {
    const body = refreshToken ? { refresh_token: refreshToken } : {};
    const response = await apiClient.post<TokenResponse>('/auth/refresh', body);
    return response.data;
  },

  /**
   * Revoca el refresh token. Web puede llamar sin argumento (la cookie
   * basta); mobile pasa el token guardado.
   */
  async logout(refreshToken?: string): Promise<void> {
    const body = refreshToken ? { refresh_token: refreshToken } : {};
    await apiClient.post('/auth/logout', body);
  },

  async getMe(): Promise<User> {
    const response = await apiClient.get<User>('/auth/me');
    return response.data;
  },
};
