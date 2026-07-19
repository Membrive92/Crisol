import { describe, expect, it } from 'vitest';

import type {
  CategoryBreakdownItem,
  DashboardSummary,
  ExpenseStructureResponse,
} from '@crisol/types';

import { computeInsights } from './stitch-smart-insights';

function summary(expenses: string): DashboardSummary {
  return { expenses } as unknown as DashboardSummary;
}

function cat(name: string, total: string): CategoryBreakdownItem {
  return {
    category_id: name,
    category_name: name,
    category_kind: 'expense',
    category_color: null,
    category_icon: null,
    total,
    count: 1,
  };
}

function structure(gross: number | null, struct: number | null): ExpenseStructureResponse {
  return {
    savings_rate_gross: gross,
    savings_rate_structural: struct,
  } as unknown as ExpenseStructureResponse;
}

describe('computeInsights (Smart Insights v2)', () => {
  it('emite concentración cuando una categoría supera el 35% del gasto', () => {
    const out = computeInsights(summary('1000'), [cat('Alquiler', '400'), cat('Comida', '100')], undefined);
    expect(out).toHaveLength(1);
    expect(out[0]!.title).toContain('Alquiler');
    expect(out[0]!.title).toContain('40%');
  });

  it('no emite concentración por debajo del umbral', () => {
    const out = computeInsights(summary('1000'), [cat('Comida', '300')], undefined);
    expect(out).toHaveLength(0);
  });

  it('emite impacto de puntuales cuando el ahorro bruto es negativo pero el estructural positivo', () => {
    const out = computeInsights(undefined, [], structure(-0.1, 0.2));
    expect(out).toHaveLength(1);
    expect(out[0]!.title).toMatch(/variables/i);
    expect(out[0]!.body).toContain('+20%');
  });

  it('no emite impacto de puntuales si el estructural también es negativo', () => {
    const out = computeInsights(undefined, [], structure(-0.1, -0.05));
    expect(out).toHaveLength(0);
  });

  it('combina los generadores por prioridad (concentración → variables)', () => {
    const out = computeInsights(summary('1000'), [cat('Alquiler', '500')], structure(-0.1, 0.2));
    expect(out).toHaveLength(2);
    expect(out[0]!.title).toContain('Alquiler');
    expect(out[1]!.title).toMatch(/variables/i);
  });

  it('sin datos → sin insights (no placeholders vacíos)', () => {
    expect(computeInsights(undefined, [], undefined)).toEqual([]);
  });
});
