import { describe, expect, it } from 'vitest';

import type { MetricDefinition } from '@crisol/types';

import { formatMetricValue, formatThreshold } from './investment-metric-format';

/**
 * El bug que este módulo cierra: hasta PHASE-44.9 había UN solo formateador que
 * hacía `toLocaleString` a secas, así que un margen del 42 % se leía `0,42`.
 * Cincuenta y dos métricas con ocho escalas distintas se presentaban igual.
 */

describe('formatMetricValue', () => {
  it('un margen se lee como porcentaje, no como tanto por uno', () => {
    expect(formatMetricValue('0.42', 'percent')).toBe('42,0 %');
  });

  it('una cobertura se lee en veces', () => {
    expect(formatMetricValue('6.8', 'times')).toBe('6,80×');
  });

  it('un plazo de cobro se lee en días y sin decimales', () => {
    expect(formatMetricValue('45.3', 'days')).toBe('45 días');
  });

  it('los años de repago se leen en años', () => {
    expect(formatMetricValue('3.9', 'years')).toBe('3,9 años');
  });

  it('la dispersión de un margen se lee en puntos porcentuales, no en %', () => {
    // Es la distinción que importa: 2 pp es dispersión, no proporción.
    expect(formatMetricValue('2', 'pp')).toBe('2,00 pp');
  });

  it('un score sale desnudo: sólo significa algo contra sus propios cortes', () => {
    expect(formatMetricValue('-2.41', 'score')).toBe('-2,41');
  });

  it('un conteo de tests sale entero', () => {
    expect(formatMetricValue('7', 'count')).toBe('7');
  });

  it('un hueco es una raya, nunca un cero', () => {
    expect(formatMetricValue(null, 'percent')).toBe('—');
    expect(formatMetricValue(undefined, 'times')).toBe('—');
  });

  it('sin catálogo cargado cae a un formato neutro en vez de inventarse la escala', () => {
    expect(formatMetricValue('0.42', undefined)).toBe('0,42');
  });
});

function definition(partial: Partial<MetricDefinition>): MetricDefinition {
  return {
    key: 'X',
    label: 'X',
    family: 'test',
    unit: 'times',
    direction: null,
    low_alarm: null,
    low_ok: null,
    high_ok: null,
    high_alarm: null,
    model_variant: null,
    note: '',
    ...partial,
  };
}

describe('formatThreshold', () => {
  it('traduce un umbral "más es mejor" a lenguaje llano', () => {
    const spec = definition({ direction: 'higher_better', low_alarm: '3', low_ok: '6' });
    expect(formatThreshold(spec)).toBe('sano ≥ 6,00× · riesgo < 3,00×');
  });

  it('traduce un umbral "menos es mejor"', () => {
    const spec = definition({ direction: 'lower_better', high_ok: '2', high_alarm: '3.5' });
    expect(formatThreshold(spec)).toBe('sano ≤ 2,00× · riesgo > 3,50×');
  });

  it('respeta la unidad de la métrica al pintar el corte', () => {
    const spec = definition({
      direction: 'higher_better',
      unit: 'percent',
      low_alarm: '0.08',
      low_ok: '0.12',
    });
    expect(formatThreshold(spec)).toBe('sano ≥ 12,0 % · riesgo < 8,0 %');
  });

  it('una métrica sin dirección no tiene corte que enseñar', () => {
    // Y quien pinta DEBE decir "sin banda" — nunca dejar el hueco, porque un
    // `null` de banda no significa "sana".
    expect(formatThreshold(definition({}))).toBeNull();
    expect(formatThreshold(undefined)).toBeNull();
  });
});
