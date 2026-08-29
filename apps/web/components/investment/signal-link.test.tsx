import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import { locateMetric } from '@crisol/ui';
import type { QuestionSignal } from '@crisol/types';

import { SignalTable } from './signal-table';
import { buildCatalogIndex } from '@crisol/ui';

/**
 * El camino veredicto → evidencia (PHASE-44.24.C.4).
 *
 * Lo que se prueba aquí es lo que un test de la página no vería: que la tabla
 * NO lee la URL por su cuenta. Un hook de `next/navigation` dentro de
 * `SignalTable` haría que `useRouter` lanzara en estos tests —que la montan sin
 * router— y, peor, que `usePathname` devolviera `null` fuera del App Router y se
 * pintaran enlaces a `"null?tab=…"` sin que nada fallara.
 */

const signal = (key: string): QuestionSignal => ({
  key,
  label: key,
  kind: 'metric',
  band: 'stressed',
  value: '1',
  status: 'ok',
  counted: true,
  reason: null,
});

describe('SignalTable: el enlace lo compone quien lee la URL', () => {
  it('se monta SIN router y no revienta', () => {
    // Si algún día alguien mete `useRouter` aquí dentro, este test se cae — y
    // ése es su trabajo.
    render(
      <SignalTable
        signals={[signal('D2')]}
        catalog={buildCatalogIndex(undefined)}
        thresholdsUsed={undefined}
      />,
    );
    expect(screen.getByText('D2')).toBeTruthy();
  });

  it('pinta un enlace sólo cuando el padre le da uno', () => {
    const { container, rerender } = render(
      <SignalTable
        signals={[signal('D2')]}
        catalog={buildCatalogIndex(undefined)}
        thresholdsUsed={undefined}
      />,
    );
    expect(container.querySelector('a')).toBeNull();

    rerender(
      <SignalTable
        signals={[signal('D2')]}
        catalog={buildCatalogIndex(undefined)}
        thresholdsUsed={undefined}
        hrefFor={(s) => `/x?tab=${locateMetric(s.key)?.tab ?? ''}&metric=${s.key}`}
      />,
    );
    const link = container.querySelector('a');
    expect(link?.getAttribute('href')).toBe('/x?tab=dividendo&metric=D2');
  });
});

/**
 * El `metric` pegajoso: `setParam` conserva por diseño lo que no se toca, así
 * que sin borrarlo explícitamente el resaltado sobrevive al cambio de pestaña y
 * reaparece en cada visita.
 */
describe('la navegación limpia el resaltado', () => {
  function setParam(current: string, patch: Record<string, string | null>): string {
    const next = new URLSearchParams(current);
    for (const [key, value] of Object.entries(patch)) {
      if (value === null) next.delete(key);
      else next.set(key, value);
    }
    return next.toString();
  }

  it('cambiar de pestaña borra `metric`', () => {
    const after = setParam('tab=dividendo&metric=D2', {
      tab: 'ratios',
      sub: 'liquidez',
      metric: null,
    });
    expect(after).not.toContain('metric');
  });

  it('sin `metric: null` el resaltado sobrevive — el defecto que esto evita', () => {
    const after = setParam('tab=dividendo&metric=D2', { tab: 'ratios', sub: 'liquidez' });
    expect(after).toContain('metric=D2');
  });
});

/**
 * La columna «Distancia» sólo existe si el servidor mandó la capa de lectura.
 * Con un backend anterior salía entera en «—», que se lee como «no se pudo
 * calcular la distancia» de cada señal — una acusación a los datos que en
 * realidad era un campo que ese servidor no manda.
 */
describe('la columna Distancia', () => {
  it('no se pinta sin `report`', () => {
    render(
      <SignalTable
        signals={[signal('D2')]}
        catalog={buildCatalogIndex(undefined)}
        thresholdsUsed={undefined}
      />,
    );
    expect(screen.queryByText('Distancia')).toBeNull();
  });

  it('se pinta con `report`, aunque venga vacío', () => {
    render(
      <SignalTable
        signals={[signal('D2')]}
        catalog={buildCatalogIndex(undefined)}
        thresholdsUsed={undefined}
        report={new Map()}
      />,
    );
    expect(screen.getByText('Distancia')).toBeTruthy();
  });
});
