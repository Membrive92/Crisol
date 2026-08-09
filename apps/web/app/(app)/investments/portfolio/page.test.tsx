import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import type { ReactElement } from 'react';
import { describe, expect, it } from 'vitest';

import { queryKeys } from '@crisol/services';
import type { PortfolioSummary, PositionSummary } from '@crisol/types';

import PortfolioPage from './page';

/**
 * La tabla de cartera era la única pantalla del módulo sin test de componente,
 * y es la que más formas tiene de mentir sobre dinero: mezclar divisas en un
 * total, valorar a coste una posición sin cotización, o etiquetar un precio con
 * la divisa equivocada.
 *
 * Los datos se siembran en la caché de TanStack Query, igual que en
 * `add-lot-form.test.tsx`: el hook importa el módulo de endpoints por ruta
 * interna, así que sustituir el `investmentApi` del índice del paquete no le
 * afecta.
 */

// Sin `as`: un cast apaga la única comprobación que tienes, y un fixture con
// una forma imposible es exactamente lo que dejó pasar el bug de PHASE-44.16.
function position(over: Partial<PositionSummary> = {}): PositionSummary {
  return {
    security_id: 'sec-1',
    ticker: 'JNJ',
    name: 'JOHNSON & JOHNSON',
    currency: 'USD',
    quantity: '10',
    avg_cost: '150.00',
    cost_basis: '1500.00',
    realized_pnl: '0',
    dividends_gross: '0',
    dividends_net: '0',
    has_quote: true,
    exclusion_reason: null,
    last_price: '160.00',
    prev_close: '158.00',
    quote_as_of: '2026-08-08T00:00:00Z',
    quote_stale: false,
    quote_currency: 'USD',
    currency_mismatch: false,
    market_value: '1600.00',
    market_value_base: '1400.00',
    cost_basis_base: '1320.00',
    unrealized_pnl_base: '90.00',
    fx_rate: '0.88',
    fx_as_of: '2026-08-08',
    unrealized_pnl: '100.00',
    unrealized_pnl_pct: '0.0667',
    price_effect: '100.00',
    fx_effect: '0',
    daily_change: '2.00',
    total_return: '100.00',
    yield_on_cost: '0',
    weight_pct: '1',
    ...over,
  };
}

function summary(over: Partial<PortfolioSummary> = {}): PortfolioSummary {
  return {
    pricing_enabled: true,
    base_currency: 'EUR',
    base_note: 'Totales en EUR.',
    total_cost_basis: '1500.00',
    total_cost_basis_base: '1320.00',
    total_market_value: '1600.00',
    total_market_value_base: '1400.00',
    total_unrealized_pnl: '100.00',
    total_unrealized_pnl_base: '90.00',
    total_realized_pnl: '0',
    total_dividends_net: '0',
    daily_pnl: '2.00',
    quoted_count: 1,
    unquoted_count: 0,
    currency_exposure: [],
    positions: [position()],
    ...over,
  };
}

function renderWith(data: PortfolioSummary): ReactElement {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(queryKeys.investment.summary(), data);
  return (
    <QueryClientProvider client={client}>
      <PortfolioPage />
    </QueryClientProvider>
  );
}

describe('Cartera', () => {
  it('los agregados se etiquetan con la divisa BASE, no con la de la primera posición', () => {
    // El defecto de PHASE-44.11.E: una suma de divisas mezcladas presentada
    // como si fuera toda de una.
    render(renderWith(summary({ base_currency: 'EUR', positions: [position({ currency: 'USD' })] })));
    expect(screen.getByText(/Valor de mercado \(EUR\)/)).toBeTruthy();
    expect(screen.queryByText(/Valor de mercado \(USD\)/)).toBeNull();
  });

  it('una posición sin cotización enseña su MOTIVO, no un valor a coste', () => {
    // Valorar a coste como sustituto sería inventarse un precio de mercado.
    render(
      renderWith(
        summary({
          positions: [
            position({
              market_value: null,
              unrealized_pnl: null,
              exclusion_reason: 'sin tasa de cambio para la fecha',
            }),
          ],
          unquoted_count: 1,
        }),
      ),
    );
    expect(screen.getByText('sin tasa de cambio para la fecha')).toBeTruthy();
    expect(screen.getByText(/1 posición queda fuera de los totales/)).toBeTruthy();
  });

  it('cuando el proveedor devuelve otra divisa, se dice y se valora con la suya', () => {
    // Un valor de Londres en peniques etiquetado como libras vale 100 veces más
    // (PHASE-44.11 D4): la divisa la declara el proveedor, no el catálogo.
    render(
      renderWith(
        summary({
          positions: [
            position({ currency: 'GBP', quote_currency: 'GBp', currency_mismatch: true }),
          ],
        }),
      ),
    );
    expect(screen.getByText(/divisa GBp/)).toBeTruthy();
  });

  it('sin proveedor de cotizaciones lo dice en vez de enseñar ceros', () => {
    render(renderWith(summary({ pricing_enabled: false })));
    expect(screen.getByText(/proveedor de cotizaciones está desactivado/)).toBeTruthy();
  });

  it('sin posiciones invita a añadir la primera, sin tabla vacía', () => {
    render(renderWith(summary({ positions: [] })));
    expect(screen.getByText(/Sin posiciones todavía/)).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });
});
