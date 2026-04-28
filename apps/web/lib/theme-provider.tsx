'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

/**
 * Tres estados:
 *  - `light` / `dark`: preferencia explícita del usuario, persistida en
 *    localStorage. Ignora cambios del SO.
 *  - `system`: sigue `prefers-color-scheme` y reacciona si cambia. Es el
 *    valor por defecto cuando el usuario nunca ha tocado el toggle.
 *
 * `resolvedTheme` es el tema "real" que se está pintando ('light' | 'dark'),
 * útil para componentes que necesiten un literal sin reproducir la lógica.
 */
export type ThemePreference = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

interface ThemeContextValue {
  preference: ThemePreference;
  resolvedTheme: ResolvedTheme;
  setPreference: (next: ThemePreference) => void;
  cyclePreference: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = 'finanzas_theme';

function readStoredPreference(): ThemePreference {
  if (typeof window === 'undefined') return 'system';
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    if (value === 'dark' || value === 'light' || value === 'system') return value;
  } catch {
    // localStorage bloqueado (modo privado) — caemos a system.
  }
  return 'system';
}

function detectSystemTheme(): ResolvedTheme {
  if (
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-color-scheme: dark)').matches
  ) {
    return 'dark';
  }
  return 'light';
}

function resolve(pref: ThemePreference): ResolvedTheme {
  return pref === 'system' ? detectSystemTheme() : pref;
}

function readInitialAttribute(): ResolvedTheme {
  if (typeof document === 'undefined') return 'light';
  const attr = document.documentElement.dataset.theme;
  return attr === 'dark' ? 'dark' : 'light';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Sincronizado con el script de bootstrap del layout: el atributo del
  // <html> ya está aplicado en la primera pintura, sin parpadeo.
  const [preference, setPreferenceState] = useState<ThemePreference>(
    () => readStoredPreference(),
  );
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(
    () => readInitialAttribute(),
  );

  const apply = useCallback(
    (pref: ThemePreference) => {
      const next = resolve(pref);
      setResolvedTheme(next);
      if (typeof document !== 'undefined') {
        document.documentElement.dataset.theme = next;
      }
    },
    [],
  );

  const setPreference = useCallback(
    (next: ThemePreference) => {
      setPreferenceState(next);
      try {
        if (typeof window !== 'undefined') {
          if (next === 'system') {
            window.localStorage.removeItem(STORAGE_KEY);
          } else {
            window.localStorage.setItem(STORAGE_KEY, next);
          }
        }
      } catch {
        // no-op
      }
      apply(next);
    },
    [apply],
  );

  const cyclePreference = useCallback(() => {
    setPreferenceState((prev) => {
      const next: ThemePreference =
        prev === 'light' ? 'dark' : prev === 'dark' ? 'system' : 'light';
      try {
        if (typeof window !== 'undefined') {
          if (next === 'system') {
            window.localStorage.removeItem(STORAGE_KEY);
          } else {
            window.localStorage.setItem(STORAGE_KEY, next);
          }
        }
      } catch {
        // no-op
      }
      apply(next);
      return next;
    });
  }, [apply]);

  // Si la preferencia es 'system', escuchamos cambios del SO en vivo.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (preference !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    function onChange() {
      apply('system');
    }
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [preference, apply]);

  const value = useMemo<ThemeContextValue>(
    () => ({ preference, resolvedTheme, setPreference, cyclePreference }),
    [preference, resolvedTheme, setPreference, cyclePreference],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider');
  return ctx;
}
