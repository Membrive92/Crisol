import { describe, expect, it } from 'vitest';

import type { MetricDefinition, MetricResult, ThresholdSpec } from '@crisol/types';

import { buildCatalogIndex } from './investment-metric-index';
import { helpParagraphs } from './investment-matrix';
import { metricGapLegend, metricRow } from './investment-metric-rows';
import type { MetricIndex } from './investment-metric-index';

/**
 * Regla 7 de honestidad: «el motor de aquel día no la calculaba» ≠ «no se pudo
 * calcular con estos datos».
 *
 * El caso real: el análisis de McDonald's se ejecutó con el motor 1.0.0, que no
 * emitía S7 ni S8 (llegaron en 1.2.0) ni las DUPONT_* (1.1.0). Las cuatro
 * pestañas que pintan métricas afirmaban «no calculable con los datos
 * disponibles» — una acusación FALSA contra las cuentas de la empresa, que
 * además desvía el diagnóstico hacia el emisor en vez de hacia el análisis.
 */

const CATALOG: MetricDefinition[] = [
  {
    key: 'S7',
    label: 'Endeudamiento',
    family: 'solvencia',
    unit: 'times',
    direction: 'lower_better',
    low_alarm: null,
    low_ok: null,
    high_ok: '2',
    high_alarm: '3',
    model_variant: null,
    note: '',
  },
];

function indexWith(series: (MetricResult | undefined)[]): MetricIndex {
  const years = [2023, 2024];
  return {
    get: (_key, year) => series[years.indexOf(year)],
    series: () => series,
    years,
    keys: ['S7'],
  };
}

function options(series: (MetricResult | undefined)[]) {
  return {
    index: indexWith(series),
    catalog: buildCatalogIndex(CATALOG),
    thresholdsUsed: undefined,
  };
}

const NOT_COMPUTABLE: MetricResult = {
  key: 'S7',
  fiscal_year: 2023,
  value: null,
  band: null,
  status: 'not_computable',
  provenance: 'sourced',
  reason: 'el balance no está clasificado',
};

describe('metricRow', () => {
  it('una métrica AUSENTE del run culpa al motor, no a las cuentas de la empresa', () => {
    const row = metricRow('S7', options([undefined, undefined]));
    expect(row.hint).toMatch(/no existía en la versión del motor/);
    expect(row.hint).not.toMatch(/no calculable con los datos disponibles/);
  });

  it('una métrica que el motor SÍ intentó conserva su motivo real', () => {
    // La distinción es el punto: aquí el motor lo intentó y no pudo, y decirlo
    // sí es cierto.
    const row = metricRow('S7', options([NOT_COMPUTABLE, NOT_COMPUTABLE]));
    expect(row.hint).toBe('el balance no está clasificado');
  });

  it('con un solo ejercicio ausente NO se declara ausente la métrica entera', () => {
    const row = metricRow('S7', options([undefined, NOT_COMPUTABLE]));
    expect(row.hint).not.toMatch(/no existía en la versión del motor/);
  });
});

/**
 * Regla 8 (PHASE-44.17) — el motivo que se enseña es el del ejercicio MÁS
 * RECIENTE.
 *
 * El caso real es el M-Score de McDonald's: falla en el primer ejercicio porque
 * no hay año anterior con el que comparar, y en todos los demás porque la
 * empresa no publica coste de ventas anual. `Array.find` sobre la serie —que va
 * de más antiguo a más reciente— devolvía el primero, así que el informe
 * invitaba a ingerir más historia. Ingerirla no habría arreglado nada.
 */
describe('el motivo de un hueco es el del ejercicio más reciente', () => {
  const MSCORE_CATALOG: MetricDefinition[] = [
    {
      key: 'm_score',
      label: 'M-Score de Beneish',
      family: 'forense',
      unit: 'score',
      direction: 'lower_better',
      low_alarm: null,
      low_ok: null,
      high_ok: '-2.22',
      high_alarm: '-1.78',
      model_variant: null,
      note: '',
    },
  ];

  const YEARS = [2021, 2022, 2023];

  function mcdIndex(series: (MetricResult | undefined)[]): MetricIndex {
    return {
      get: (_key, year) => series[YEARS.indexOf(year)],
      series: () => series,
      years: YEARS,
      keys: ['m_score'],
    };
  }

  const gap = (fiscal_year: number, reason: string): MetricResult => ({
    key: 'm_score',
    fiscal_year,
    value: null,
    band: null,
    status: 'not_computable',
    provenance: 'sourced',
    reason,
  });

  const SIN_ANTERIOR = gap(2021, 'no hay ejercicio anterior con el que comparar');
  const SIN_COGS = gap(2022, "falta la partida 'cogs'");

  const mcdOptions = (series: (MetricResult | undefined)[]) => ({
    index: mcdIndex(series),
    catalog: buildCatalogIndex(MSCORE_CATALOG),
    thresholdsUsed: undefined,
  });

  it('no manda a ingerir historia cuando lo que falta es una partida', () => {
    const row = metricRow(
      'm_score',
      mcdOptions([SIN_ANTERIOR, SIN_COGS, { ...SIN_COGS, fiscal_year: 2023 }]),
    );
    expect(row.hint).toMatch(/falta la partida 'cogs'/);
    expect(row.hint).not.toMatch(/no hay ejercicio anterior/);
  });

  it('declara que los ejercicios no fallan todos por lo mismo', () => {
    const row = metricRow(
      'm_score',
      mcdOptions([SIN_ANTERIOR, SIN_COGS, { ...SIN_COGS, fiscal_year: 2023 }]),
    );
    expect(row.hint).toMatch(/2023: /);
    expect(row.hint).toMatch(/otros ejercicios, por otro motivo/);
  });

  it('con un único motivo en toda la serie, lo dice sin adornos', () => {
    const row = metricRow(
      'm_score',
      mcdOptions([
        { ...SIN_COGS, fiscal_year: 2021 },
        SIN_COGS,
        { ...SIN_COGS, fiscal_year: 2023 },
      ]),
    );
    expect(row.hint).toBe("falta la partida 'cogs'");
  });

  it('la leyenda del bloque sale del run: sin huecos no se pinta nada', () => {
    const ok: MetricResult = {
      key: 'm_score',
      fiscal_year: 2021,
      value: '-2.9',
      band: 'healthy',
      status: 'ok',
      provenance: 'sourced',
      reason: null,
    };
    const legend = metricGapLegend(['m_score'], {
      index: mcdIndex([ok, { ...ok, fiscal_year: 2022 }, { ...ok, fiscal_year: 2023 }]),
      catalog: buildCatalogIndex(MSCORE_CATALOG),
    });
    expect(legend).toEqual([]);
  });

  it('la leyenda nombra los ejercicios reales, no «el primero»', () => {
    const legend = metricGapLegend(['m_score'], {
      index: mcdIndex([SIN_ANTERIOR, SIN_COGS, { ...SIN_COGS, fiscal_year: 2023 }]),
      catalog: buildCatalogIndex(MSCORE_CATALOG),
    });
    expect(legend).toHaveLength(1);
    expect(legend[0]).toMatch(/M-Score de Beneish: sin dato en 2021-2023/);
    expect(legend[0]).toMatch(/falta la partida 'cogs'/);
  });

  it('una métrica ausente de todo el run no entra en la leyenda: es cosa del motor', () => {
    const legend = metricGapLegend(['m_score'], {
      index: mcdIndex([undefined, undefined, undefined]),
      catalog: buildCatalogIndex(MSCORE_CATALOG),
    });
    expect(legend).toEqual([]);
  });
});

/**
 * PHASE-44.18 — los dos atributos por los que la tabla de umbrales se diferencia
 * del catálogo del motor viajaban hasta el cliente y se descartaban en la última
 * línea (`effectiveThreshold`). Con eso, «la vara no sirve para este sector» y
 * «no se pudo colorear» se veían exactamente igual, y unos cortes US-GAAP
 * aplicados a cuentas IFRS no se declaraban en ninguna parte.
 */
describe('el corte efectivo llega entero al cliente', () => {
  const S7: MetricResult = {
    key: 'S7',
    fiscal_year: 2024,
    value: '9.8',
    band: null, // el motor ya lo apagó: applies=false
    status: 'ok',
    provenance: 'sourced',
    reason: null,
  };

  function thresholdFor(over: Partial<ThresholdSpec>): Record<string, ThresholdSpec> {
    return {
      S7: {
        metric_key: 'S7',
        direction: 'band',
        low_alarm: null,
        low_ok: '1',
        high_ok: '2',
        high_alarm: '3',
        model_variant: null,
        applies: true,
        ...over,
      },
    };
  }

  it('un banco ve el número de S7 y se le dice por qué no lleva semáforo', () => {
    const used = thresholdFor({ applies: false });
    const row = metricRow('S7', {
      index: indexWith([S7, S7]),
      catalog: buildCatalogIndex(CATALOG),
      thresholdsUsed: used,
    });
    // El corte 1-2 NO se enseña: el motor lo descartó para este sector, y
    // pintarlo invitaría a comparar contra una vara que no se aplicó.
    expect(row.hint).not.toMatch(/sano entre/);
    expect(row.hint).toMatch(/no están calibrados para este tipo de empresa/);
    expect(row.cells[0]?.title).toMatch(/no están calibrados/);
    expect(row.cells[0]?.text).not.toBe('—');
  });

  it('una empresa normal sigue viendo su corte', () => {
    const row = metricRow('S7', {
      index: indexWith([
        { ...S7, band: 'healthy' },
        { ...S7, band: 'healthy' },
      ]),
      catalog: buildCatalogIndex(CATALOG),
      thresholdsUsed: thresholdFor({}),
    });
    expect(row.hint).toMatch(/sano entre/);
  });

  it('unas cuentas IFRS declaran que los cortes son US-GAAP sin recalibrar', () => {
    const row = metricRow('S7', {
      index: indexWith([
        { ...S7, band: 'healthy' },
        { ...S7, band: 'healthy' },
      ]),
      catalog: buildCatalogIndex(CATALOG),
      thresholdsUsed: thresholdFor({ model_variant: 'uncalibrated' }),
    });
    expect(row.cells[0]?.mark).toContain('≠');
    expect(row.cells[0]?.title).toMatch(/se aplican sin recalibrar/);
  });
});

/**
 * PHASE-44.24.A.1 — la ficha de una fila viaja en TRES campos.
 *
 * El riesgo que cubren estos tests no es que el texto sea feo: es que un
 * backend intermedio mande `help` y no los otros dos —la fase que los añade es
 * posterior a la del glosario— y la pantalla pinte un rótulo «Por qué importa:»
 * seguido de nada. La convención del repo desde PHASE-44.16 es que ausente y
 * vacío no son lo mismo, así que la clave se OMITE y el tramo no existe.
 */
describe('helpParagraphs', () => {
  it('devuelve los tres tramos en orden de lectura, y sólo el primero sin rótulo', () => {
    const parts = helpParagraphs({ help: 'qué mide', helpWhy: 'por qué', helpReading: 'cómo' });
    expect(parts.map((p) => p.text)).toEqual(['qué mide', 'por qué', 'cómo']);
    expect(parts[0]?.label).toBeUndefined();
    expect(parts[1]?.label).toBe('Por qué importa');
    expect(parts[2]?.label).toBe('Cómo se lee');
  });

  it('con sólo el «qué mide» no deja ningún rótulo huérfano', () => {
    // Es el caso de las 49 partidas canónicas: su glosario es de un campo.
    expect(helpParagraphs({ help: 'una partida del balance' })).toEqual([
      { text: 'una partida del balance' },
    ]);
  });

  it('sin ficha no devuelve nada, en vez de un tramo vacío', () => {
    expect(helpParagraphs({})).toEqual([]);
  });
});

describe('metricRow transporta la ficha completa', () => {
  const CON_FICHA: MetricDefinition[] = [
    { ...(CATALOG[0] as MetricDefinition), help: 'qué mide', why: 'por qué', reading: 'cómo' },
  ];
  const SOLO_HELP: MetricDefinition[] = [{ ...(CATALOG[0] as MetricDefinition), help: 'qué mide' }];

  it('lleva los tres campos cuando el catálogo los trae', () => {
    const row = metricRow('S7', {
      index: indexWith([NOT_COMPUTABLE, NOT_COMPUTABLE]),
      catalog: buildCatalogIndex(CON_FICHA),
      thresholdsUsed: undefined,
    });
    expect(helpParagraphs(row)).toHaveLength(3);
  });

  it('OMITE las claves que el backend no manda, no las pone vacías', () => {
    const row = metricRow('S7', {
      index: indexWith([NOT_COMPUTABLE, NOT_COMPUTABLE]),
      catalog: buildCatalogIndex(SOLO_HELP),
      thresholdsUsed: undefined,
    });
    // `in` y no `=== undefined`: con `exactOptionalPropertyTypes` la diferencia
    // entre ausente y presente-con-undefined es real, y es la que hace que la
    // pantalla no pinte un rótulo sin texto detrás.
    expect('helpWhy' in row).toBe(false);
    expect('helpReading' in row).toBe(false);
    expect(helpParagraphs(row)).toHaveLength(1);
  });
});
