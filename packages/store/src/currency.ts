import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { storage } from './storage';

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
  /**
   * Cuando `true` (default) las vistas de patrimonio neto restan los
   * pasivos a los activos (`net_worth = assets - liabilities`).
   * Cuando `false` se ignora la deuda y el patrimonio neto se muestra
   * como sólo activos — útil para evaluar la evolución del ahorro sin
   * el arrastre de la hipoteca o préstamos a largo plazo. El flag NO
   * altera el desglose por cuenta ni el módulo Deuda: sólo cambia el
   * agregado "Patrimonio neto" / "Salud financiera".
   */
  includeDebtInNetWorth: boolean;
  setCurrency: (currency: string) => void;
  setConvertAll: (convertAll: boolean) => void;
  setIncludeDebtInNetWorth: (include: boolean) => void;
}

const FALLBACK_CURRENCY = 'EUR';

/**
 * Moneda activa global. Se persiste vía adapter cross-platform
 * (`./storage`): `localStorage` en web, `AsyncStorage` en React
 * Native — Metro escoge `./storage.native.ts` automáticamente
 * (PHASE-11.2). Antes de 11.2 importaba `localStorage` directo y
 * sólo funcionaba en web.
 *
 * El selector vive en el header de web (icono cartera) y en el
 * `CurrencyPicker` de la pantalla Análisis mobile. Al cambiarlo se
 * reflejan todas las pantallas que consumen el store.
 */
export const useCurrencyStore = create<CurrencyState>()(
  persist(
    (set) => ({
      currency: FALLBACK_CURRENCY,
      convertAll: true,
      includeDebtInNetWorth: true,
      setCurrency: (currency) => set({ currency }),
      setConvertAll: (convertAll) => set({ convertAll }),
      setIncludeDebtInNetWorth: (includeDebtInNetWorth) =>
        set({ includeDebtInNetWorth }),
    }),
    {
      name: 'finanzas:currency',
      storage,
      // v1: introduce `convertAll` (PHASE-8.2).
      // v2: introduce `includeDebtInNetWorth` (PHASE-22+). Default `true`
      // mantiene el comportamiento previo (net_worth = assets -
      // liabilities). Sin migración el setter rompería para clientes
      // con un blob v1 persistido.
      version: 2,
      migrate: (persisted, version) => {
        if (!persisted || typeof persisted !== 'object') return persisted as CurrencyState;
        let next = persisted as Partial<CurrencyState>;
        if (version < 1) {
          next = { convertAll: true, ...next };
        }
        if (version < 2) {
          next = { includeDebtInNetWorth: true, ...next };
        }
        return next as CurrencyState;
      },
    },
  ),
);
