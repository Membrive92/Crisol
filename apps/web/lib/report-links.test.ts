import { describe, expect, it } from 'vitest';

import {
  guideBackHref,
  guideHrefFor,
  printHrefFor,
  reportHrefFor,
  signalHrefFor,
} from './report-links';

describe('printHrefFor', () => {
  it('CONSERVA el análisis seleccionado', () => {
    // El defecto original: `href="?print=1"` sustituye la query entera, así que
    // el dictamen impreso era el del análisis más reciente y no el que estabas
    // mirando. En un papel que se archiva, imprimir otro análisis es el fallo
    // que importa.
    const href = printHrefFor('/investments/analysis/abc', 'run=r1&compare=r0&tab=veredicto');
    const params = new URLSearchParams(href.split('?')[1]);
    expect(params.get('run')).toBe('r1');
    expect(params.get('compare')).toBe('r0');
    expect(params.get('print')).toBe('1');
  });

  it('sin params previos produce sólo `print=1`', () => {
    expect(printHrefFor('/x', '')).toBe('/x?print=1');
  });

  it('no duplica `print` si ya venía', () => {
    const href = printHrefFor('/x', 'print=1&run=r1');
    expect(href.match(/print=1/g)).toHaveLength(1);
    expect(new URLSearchParams(href.split('?')[1]).get('run')).toBe('r1');
  });

  it('conserva la ruta tal cual, corchetes incluidos', () => {
    // El securityId es un segmento dinámico; el href se compone sobre el
    // `pathname` ya resuelto, no sobre la plantilla.
    expect(printHrefFor('/investments/analysis/9f1e', 'run=r1')).toBe(
      '/investments/analysis/9f1e?run=r1&print=1',
    );
  });
});

describe('signalHrefFor', () => {
  const P = '/investments/analysis/s1';
  const EN_VEREDICTO = { tab: 'veredicto', sub: 'dictamen' };

  it('una fila de OTRA pestaña enlaza con su sub y su metric', () => {
    const href = signalHrefFor(P, 'tab=veredicto&sub=dictamen', EN_VEREDICTO, 'L1');
    const params = new URLSearchParams(href!.split('?')[1]);
    expect(params.get('tab')).toBe('ratios');
    expect(params.get('sub')).toBe('liquidez');
    expect(params.get('metric')).toBe('L1');
  });

  it('una BANDERA no produce enlace', () => {
    // Antes producía uno a la misma pestaña: recargaba, cerraba el desglose y
    // no resaltaba nada. Veintiuna señales así.
    expect(signalHrefFor(P, 'tab=veredicto', EN_VEREDICTO, 'C3_inventory_vs_cogs')).toBeNull();
    expect(
      signalHrefFor(P, 'tab=veredicto', EN_VEREDICTO, 'B4_dividend_funded_externally'),
    ).toBeNull();
  });

  it('«stress» en el veredicto es un ancla: scroll sin recargar', () => {
    expect(signalHrefFor(P, 'tab=veredicto&sub=dictamen', EN_VEREDICTO, 'stress')).toBe(
      '#stress-scenarios',
    );
  });

  it('«stress» desde otra pestaña cambia de pestaña Y ancla', () => {
    const href = signalHrefFor(
      P,
      'tab=ratios&sub=liquidez',
      { tab: 'ratios', sub: 'liquidez' },
      'stress',
    );
    expect(href).toContain('tab=veredicto');
    expect(href?.endsWith('#stress-scenarios')).toBe(true);
    expect(href).not.toContain('metric=');
  });

  it('la tendencia de la caja libre resalta la FILA de la serie, no su propia clave', () => {
    // `fcf_trend` no es una fila de ninguna matriz; `fcf_cfo` sí.
    const href = signalHrefFor(P, 'tab=veredicto', EN_VEREDICTO, 'fcf_trend');
    const params = new URLSearchParams(href!.split('?')[1]);
    expect(params.get('tab')).toBe('evolucion');
    expect(params.get('metric')).toBe('fcf_cfo');
  });

  it('una señal que ya está a la vista no enlaza', () => {
    expect(
      signalHrefFor(P, 'tab=ratios&sub=liquidez', { tab: 'ratios', sub: 'liquidez' }, 'L1'),
    ).toBeNull();
  });

  it('conserva el resto de la query', () => {
    const href = signalHrefFor(P, 'run=r7&tab=veredicto', EN_VEREDICTO, 'L1');
    expect(new URLSearchParams(href!.split('?')[1]).get('run')).toBe('r7');
  });
});

describe('la guía y su vuelta', () => {
  it('el enlace a la guía lleva el informe de origen, query incluida', () => {
    const href = guideHrefFor('/investments/analysis/s1', 'tab=ratios&sub=liquidez');
    const back = new URLSearchParams(href.split('?')[1]).get('back');
    expect(back).toBe('/investments/analysis/s1?tab=ratios&sub=liquidez');
  });

  it('la vuelta sólo acepta rutas internas del informe', () => {
    // Un `back` con host sería un redirect abierto; uno a otra pantalla, un
    // enlace que no dice adónde va.
    expect(guideBackHref('/investments/analysis/s1?tab=veredicto')).toBe(
      '/investments/analysis/s1?tab=veredicto',
    );
    expect(guideBackHref('https://evil.example/x')).toBeNull();
    expect(guideBackHref('//evil.example/x')).toBeNull();
    expect(guideBackHref('/personal-finance/transactions')).toBeNull();
    expect(guideBackHref(null)).toBeNull();
  });
});

describe('reportHrefFor', () => {
  it('quita `print` y conserva el resto', () => {
    expect(reportHrefFor('/investments/analysis/s1', 'run=r7&print=1&tab=veredicto')).toBe(
      '/investments/analysis/s1?run=r7&tab=veredicto',
    );
  });

  it('sin más params vuelve a la ruta limpia', () => {
    expect(reportHrefFor('/investments/analysis/s1', 'print=1')).toBe('/investments/analysis/s1');
  });
});

describe('guideBackHref es estricta con la forma', () => {
  it('rechaza la propia guía (un bucle) y los segmentos `..`', () => {
    expect(guideBackHref('/investments/analysis/guide?back=x')).toBeNull();
    expect(guideBackHref('/investments/analysis/../../settings')).toBeNull();
    expect(guideBackHref('/investments/analysis/s1/extra')).toBeNull();
  });

  it('acepta exactamente /investments/analysis/<id> con su query', () => {
    expect(guideBackHref('/investments/analysis/9f1e?tab=ratios#x')).toBe(
      '/investments/analysis/9f1e?tab=ratios#x',
    );
  });
});
