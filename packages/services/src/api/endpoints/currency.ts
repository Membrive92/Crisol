import { apiClient } from '../client';

export interface RatesResponse {
  rate_date: string;
  base: string;
  rates: { quote: string; rate: string }[];
}

export interface ConvertResponse {
  amount: string;
  rate: string;
  rate_date: string;
  fallback: 'exact' | 'previous' | 'same' | 'missing';
}

export interface ConvertQuery {
  amount: string;
  from: string;
  to: string;
  date?: string;
}

export const currencyApi = {
  /**
   * Devuelve el mapa EUR→quote para una fecha (ISO `YYYY-MM-DD`).
   * Si no se pasa `date`, el backend usa hoy en UTC.
   */
  async rates(date?: string): Promise<RatesResponse> {
    const response = await apiClient.get<RatesResponse>('/currency/rates', {
      params: date ? { date } : undefined,
    });
    return response.data;
  },

  /**
   * Conversión puntual. La UI principal usa `useExchangeRates` y
   * convierte client-side; este endpoint queda para flujos batch o
   * verificación manual.
   */
  async convert(query: ConvertQuery): Promise<ConvertResponse> {
    const response = await apiClient.get<ConvertResponse>('/currency/convert', {
      params: query,
    });
    return response.data;
  },
};
