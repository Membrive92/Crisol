import { beforeEach, describe, expect, it } from 'vitest';

import type { User } from '@crisol/types';

import { useAuthStore } from './auth';

const USER: User = {
  id: 'u1',
  email: 'user@example.com',
  display_name: 'User',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

describe('useAuthStore', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isHydrated: false,
    });
  });

  it('setTokens marks the session authenticated', () => {
    useAuthStore.getState().setTokens('access', 'refresh');
    const s = useAuthStore.getState();
    expect(s.accessToken).toBe('access');
    expect(s.refreshToken).toBe('refresh');
    expect(s.isAuthenticated).toBe(true);
  });

  it('logout clears tokens and user', () => {
    useAuthStore.getState().setTokens('a', 'r');
    useAuthStore.getState().setUser(USER);
    useAuthStore.getState().logout();
    const s = useAuthStore.getState();
    expect(s.accessToken).toBeNull();
    expect(s.refreshToken).toBeNull();
    expect(s.user).toBeNull();
    expect(s.isAuthenticated).toBe(false);
  });

  it('hydrate authenticates only when an access token is present', () => {
    useAuthStore.getState().hydrate(null, null, null);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().isHydrated).toBe(true);

    useAuthStore.getState().hydrate('token', 'refresh', USER);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().user).toEqual(USER);
  });
});
