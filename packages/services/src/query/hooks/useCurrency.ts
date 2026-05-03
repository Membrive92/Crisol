import { useQuery } from '@tanstack/react-query';

import { currencyApi } from '../../api/endpoints/currency';
import { queryKeys } from '../keys';

// Las tasas de un día pasado son inmutables: cache eterna. Para hoy
// usamos 1 hora — el ECB publica una sola vez al día, así que más
// finura no aporta nada.
const PAST_STALE_TIME = Number.POSITIVE_INFINITY;
const TODAY_STALE_TIME = 60 * 60 * 1000;

function isToday(date: string | undefined): boolean {
  if (!date) return true;
  const todayIso = new Date().toISOString().slice(0, 10);
  return date === todayIso;
}

export interface ExchangeRatesResult {
  date: string;
  base: string;
  rates: Record<string, number>;
}

/**
 * Factory de opciones para `useQuery` / `useQueries`. La extraemos
 * para que la tabla de transacciones pueda pedir N fechas distintas
 * vía `useQueries` reusando exactamente la misma cache key + parser
 * que `useExchangeRates`.
 */
export function exchangeRatesQueryOptions(date: string | undefined) {
  return {
    queryKey: queryKeys.currency.rates(date),
    queryFn: async (): Promise<ExchangeRatesResult> => {
      const data = await currencyApi.rates(date);
      const rates: Record<string, number> = {};
      for (const row of data.rates) {
        const value = Number(row.rate);
        if (Number.isFinite(value)) {
          rates[row.quote.toUpperCase()] = value;
        }
      }
      return { date: data.rate_date, base: data.base, rates };
    },
    staleTime: isToday(date) ? TODAY_STALE_TIME : PAST_STALE_TIME,
  };
}

/**
 * Devuelve el mapa EUR→quote para `date`.
 *
 * - Acepta `YYYY-MM-DD`. Si se omite, el backend usa hoy en UTC.
 * - Cache infinita para fechas pasadas, 1h para hoy.
 * - El consumidor recibe `Record<string, number>` ya parseado a
 *   `number` listo para `convertAmount` / `formatConverted`.
 */
export function useExchangeRates(date?: string) {
  return useQuery({
    ...exchangeRatesQueryOptions(date),
    placeholderData: (previous) => previous,
  });
}
