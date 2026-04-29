import { apiClient } from '../client';

/**
 * Cliente HTTP para los endpoints de WebAuthn / Passkeys.
 *
 * Los `options` y `credential` se tipan como `unknown` a propósito: son
 * estructuras opacas definidas por la spec WebAuthn que la lib
 * `@simplewebauthn/browser` consume tal cual. Tipar campo a campo aquí
 * sería duplicar @simplewebauthn/types y mantenerlo sincronizado.
 */
export interface PasskeyResponse {
  id: string;
  label: string | null;
  transports: string | null;
  created_at: string;
  last_used_at: string | null;
}

export const passkeysApi = {
  async registrationOptions(): Promise<unknown> {
    const response = await apiClient.post<{ options: unknown }>(
      '/auth/webauthn/register-options',
    );
    return response.data.options;
  },

  async registrationVerify(payload: {
    credential: unknown;
    label?: string | null;
  }): Promise<PasskeyResponse> {
    const response = await apiClient.post<PasskeyResponse>(
      '/auth/webauthn/register-verify',
      payload,
    );
    return response.data;
  },

  /** Si `email` se omite, el backend genera options para Conditional UI
   *  (sin allowCredentials). Útil para autocompletado del navegador. */
  async authenticationOptions(email?: string): Promise<unknown> {
    const response = await apiClient.post<{ options: unknown }>(
      '/auth/webauthn/authenticate-options',
      email ? { email } : {},
    );
    return response.data.options;
  },

  async authenticationVerify(payload: {
    email?: string;
    credential: unknown;
  }): Promise<{ access_token: string; refresh_token: string; token_type: string }> {
    const response = await apiClient.post<{
      access_token: string;
      refresh_token: string;
      token_type: string;
    }>('/auth/webauthn/authenticate-verify', payload);
    return response.data;
  },

  async list(): Promise<PasskeyResponse[]> {
    const response = await apiClient.get<PasskeyResponse[]>('/auth/webauthn');
    return response.data;
  },

  async relabel(id: string, label: string): Promise<PasskeyResponse> {
    const response = await apiClient.patch<PasskeyResponse>(
      `/auth/webauthn/${id}`,
      { label },
    );
    return response.data;
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`/auth/webauthn/${id}`);
  },
};
