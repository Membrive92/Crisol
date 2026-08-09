import { describe, expect, it } from 'vitest';

import type { MetricDefinition, MetricResult, ThresholdSpec } from '@crisol/types';

import { buildCatalogIndex } from './investment-metric-index';
import { metricRow } from './investment-metric-rows';
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
  return { index: indexWith(series), catalog: buildCatalogIndex(CATALOG), thresholdsUsed: undefined };
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
      index: indexWith([{ ...S7, band: 'healthy' }, { ...S7, band: 'healthy' }]),
      catalog: buildCatalogIndex(CATALOG),
      thresholdsUsed: thresholdFor({}),
    });
    expect(row.hint).toMatch(/sano entre/);
  });

  it('unas cuentas IFRS declaran que los cortes son US-GAAP sin recalibrar', () => {
    const row = metricRow('S7', {
      index: indexWith([{ ...S7, band: 'healthy' }, { ...S7, band: 'healthy' }]),
      catalog: buildCatalogIndex(CATALOG),
      thresholdsUsed: thresholdFor({ model_variant: 'uncalibrated' }),
    });
    expect(row.cells[0]?.mark).toContain('≠');
    expect(row.cells[0]?.title).toMatch(/se aplican sin recalibrar/);
  });
});
