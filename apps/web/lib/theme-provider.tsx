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
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    if (value === 'dark' || value === 'light' || value === 'system') return value;
  } catch {
    // localStorage bloqueado (modo privado) — caemos a system.
  }
  return 'system';
}

function detectSystemTheme(): ResolvedTheme {
  if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'light';
}

function resolveOnClient(pref: ThemePreference): ResolvedTheme {
  return pref === 'system' ? detectSystemTheme() : pref;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  // El primer render (SSR + hidratación cliente) arranca en 'system' / 'light':
  // server y client coinciden y no hay mismatch de hidratación. El estado real
  // (lo que hay en localStorage o el SO) se aplica en el efecto que corre
  // post-mount. El tema *visual* está bien desde el primer paint porque el
  // script de bootstrap del layout ya puso `data-theme` en el <html>; sólo
  // el contenido del toggle (icono/etiqueta) puede parpadear en ese instante.
  const [preference, setPreferenceState] = useState<ThemePreference>('system');
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>('light');

  // Hidratación: tras montar, alineamos el estado React con localStorage y
  // con el atributo `data-theme` que el bootstrap ya escribió.
  useEffect(() => {
    const stored = readStoredPreference();
    setPreferenceState(stored);
    const fromAttr = document.documentElement.dataset.theme;
    if (fromAttr === 'dark' || fromAttr === 'light') {
      setResolvedTheme(fromAttr);
    } else {
      setResolvedTheme(resolveOnClient(stored));
    }
  }, []);

  const apply = useCallback(
    (pref: ThemePreference) => {
      // Sólo se llama desde handlers/efectos cliente, así que `window` y
      // `document` están definidos.
      const next = resolveOnClient(pref);
      setResolvedTheme(next);
      document.documentElement.dataset.theme = next;
    },
    [],
  );

  const persistPreference = useCallback((next: ThemePreference) => {
    try {
      if (next === 'system') {
        window.localStorage.removeItem(STORAGE_KEY);
      } else {
        window.localStorage.setItem(STORAGE_KEY, next);
      }
    } catch {
      // no-op (modo privado, etc.)
    }
  }, []);

  const setPreference = useCallback(
    (next: ThemePreference) => {
      setPreferenceState(next);
      persistPreference(next);
      apply(next);
    },
    [apply, persistPreference],
  );

  const cyclePreference = useCallback(() => {
    setPreferenceState((prev) => {
      const next: ThemePreference =
        prev === 'light' ? 'dark' : prev === 'dark' ? 'system' : 'light';
      persistPreference(next);
      apply(next);
      return next;
    });
  }, [apply, persistPreference]);

  // Si la preferencia es 'system', escuchamos cambios del SO en vivo.
  useEffect(() => {
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
