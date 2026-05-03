import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export interface CurrencyState {
  currency: string;
  setCurrency: (currency: string) => void;
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
      setCurrency: (currency) => set({ currency }),
    }),
    {
      name: 'finanzas:currency',
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
