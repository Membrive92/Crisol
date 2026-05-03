import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export interface CurrencyState {
  currency: string;
  /**
   * Cuando `true` (default) Dashboard, Análisis y los KPIs de
   * Transacciones suman cross-currency convirtiendo todo a `currency`.
   * Cuando `false` se mantiene el comportamiento previo a PHASE-8.2:
   * cada vista filtra por la moneda activa y los importes en otras
   * monedas no aparecen.
   */
  convertAll: boolean;
  setCurrency: (currency: string) => void;
  setConvertAll: (convertAll: boolean) => void;
}

const FALLBACK_CURRENCY = 'EUR';

/**
 * Moneda activa global. Se persiste en localStorage para sobrevivir
 * recargas y se comparte entre Dashboard / Análisis / Transacciones —
 * antes cada página tenía su propio `useState` con la misma lógica de
 * sincronización con `useUserCurrencies`. El selector vive en el header
 * (icono cartera) y al cambiarlo se reflejan todas las pantallas.
 */
export const useCurrencyStore = create<CurrencyState>()(
  persist(
    (set) => ({
      currency: FALLBACK_CURRENCY,
      convertAll: true,
      setCurrency: (currency) => set({ currency }),
      setConvertAll: (convertAll) => set({ convertAll }),
    }),
    {
      name: 'finanzas:currency',
      storage: createJSONStorage(() => localStorage),
      // Bumped al introducir `convertAll` en PHASE-8.2: si un cliente
      // tiene una versión antigua persistida (sin el campo), la inicia
      // con `true` (igual que el default). Sin migración explícita
      // perdería el campo y rompería el `setConvertAll`.
      version: 1,
      migrate: (persisted, version) => {
        if (!persisted || typeof persisted !== 'object') return persisted as CurrencyState;
        if (version < 1) {
          return { convertAll: true, ...(persisted as Partial<CurrencyState>) } as CurrencyState;
        }
        return persisted as CurrencyState;
      },
    },
  ),
);
