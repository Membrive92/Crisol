import { create } from 'zustand';

import type { User } from '@crisol/types';

export interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isHydrated: boolean;

  setTokens: (accessToken: string, refreshToken: string) => void;
  setUser: (user: User) => void;
  hydrate: (accessToken: string | null, refreshToken: string | null, user: User | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isHydrated: false,

  setTokens: (accessToken, refreshToken) =>
    set({ accessToken, refreshToken, isAuthenticated: true }),

  setUser: (user) => set({ user }),

  hydrate: (accessToken, refreshToken, user) =>
    set({
      accessToken,
      refreshToken,
      user,
      isAuthenticated: !!accessToken,
      isHydrated: true,
    }),

  logout: () =>
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
    }),
}));
