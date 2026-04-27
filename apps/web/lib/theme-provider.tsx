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

export type Theme = 'light' | 'dark';

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = 'finanzas_theme';

function readStoredTheme(): Theme | null {
  if (typeof window === 'undefined') return null;
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value === 'dark' || value === 'light' ? value : null;
  } catch {
    return null;
  }
}

function detectInitialTheme(): Theme {
  if (typeof document !== 'undefined') {
    const attr = document.documentElement.dataset.theme;
    if (attr === 'dark' || attr === 'light') return attr;
  }
  if (
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-color-scheme: dark)').matches
  ) {
    return 'dark';
  }
  return 'light';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Sincronizado con el script de bootstrap del layout: en cliente arranca
  // con el atributo que ya está aplicado al `<html>`, sin parpadeos.
  const [theme, setThemeState] = useState<Theme>(() => detectInitialTheme());

  const applyTheme = useCallback((next: Theme) => {
    if (typeof document === 'undefined') return;
    document.documentElement.dataset.theme = next;
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // no-op (modo privado, etc.)
    }
  }, []);

  // Si el usuario cambió la preferencia del SO y NO ha elegido manualmente
  // un tema (sin entrada en localStorage), seguimos al SO.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (readStoredTheme() !== null) return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    function onChange(event: MediaQueryListEvent) {
      const next: Theme = event.matches ? 'dark' : 'light';
      setThemeState(next);
      if (typeof document !== 'undefined') {
        document.documentElement.dataset.theme = next;
      }
    }
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  const setTheme = useCallback(
    (next: Theme) => {
      setThemeState(next);
      applyTheme(next);
    },
    [applyTheme],
  );

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      return next;
    });
  }, [applyTheme]);

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, toggleTheme, setTheme }),
    [theme, toggleTheme, setTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider');
  return ctx;
}
