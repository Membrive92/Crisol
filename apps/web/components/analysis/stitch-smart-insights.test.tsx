import { describe, expect, it } from 'vitest';

import type {
  CategoryBreakdownItem,
  DashboardSummary,
  ExpenseStructureResponse,
  MonthOutlookResponse,
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

function inDays(n: number): string {
  return new Date(Date.now() + n * 86_400_000).toISOString().slice(0, 10);
}

function outlook(committed: string, items: MonthOutlookResponse['committed_items']): MonthOutlookResponse {
  return { committed_remaining: committed, committed_items: items } as unknown as MonthOutlookResponse;
}

describe('computeInsights (Smart Insights v2)', () => {
  it('emite concentración cuando una categoría supera el 35% del gasto', () => {
    const out = computeInsights(
      summary('1000'),
      [cat('Alquiler', '400'), cat('Comida', '100')],
      undefined,
      undefined,
      'EUR',
    );
    expect(out).toHaveLength(1);
    expect(out[0]!.title).toContain('Alquiler');
    expect(out[0]!.title).toContain('40%');
  });

  it('no emite concentración por debajo del umbral', () => {
    const out = computeInsights(summary('1000'), [cat('Comida', '300')], undefined, undefined, 'EUR');
    expect(out).toHaveLength(0);
  });

  it('emite impacto de puntuales cuando el ahorro bruto es negativo pero el estructural positivo', () => {
    const out = computeInsights(undefined, [], structure(-0.1, 0.2), undefined, 'EUR');
    expect(out).toHaveLength(1);
    expect(out[0]!.title).toMatch(/variables/i);
    expect(out[0]!.body).toContain('+20%');
  });

  it('no emite impacto de puntuales si el estructural también es negativo', () => {
    const out = computeInsights(undefined, [], structure(-0.1, -0.05), undefined, 'EUR');
    expect(out).toHaveLength(0);
  });

  it('emite cargo próximo cuando el mayor de los próximos 7 días domina lo comprometido', () => {
    const items: MonthOutlookResponse['committed_items'] = [
      { name: 'Préstamo', amount: '232', expected_date: inDays(2), overdue: false, kind: 'installment' },
      { name: 'Netflix', amount: '14', expected_date: inDays(3), overdue: false, kind: 'fixed' },
    ];
    const out = computeInsights(undefined, [], undefined, outlook('400', items), 'EUR');
    expect(out).toHaveLength(1);
    expect(out[0]!.title).toContain('Préstamo');
  });

  it('ignora cargos fuera de la ventana de 7 días', () => {
    const items: MonthOutlookResponse['committed_items'] = [
      { name: 'Préstamo', amount: '232', expected_date: inDays(20), overdue: false, kind: 'installment' },
    ];
    const out = computeInsights(undefined, [], undefined, outlook('400', items), 'EUR');
    expect(out).toHaveLength(0);
  });

  it('topa a 3 insights ordenados por prioridad', () => {
    const items: MonthOutlookResponse['committed_items'] = [
      { name: 'Préstamo', amount: '300', expected_date: inDays(1), overdue: false, kind: 'installment' },
    ];
    const out = computeInsights(
      summary('1000'),
      [cat('Alquiler', '500')],
      structure(-0.1, 0.2),
      outlook('300', items),
      'EUR',
    );
    expect(out).toHaveLength(3);
    // Prioridad: concentración (1) → variables (2) → cargo próximo (3).
    expect(out[0]!.title).toContain('Alquiler');
    expect(out[1]!.title).toMatch(/variables/i);
    expect(out[2]!.title).toContain('Préstamo');
  });

  it('sin datos → sin insights (no placeholders vacíos)', () => {
    expect(computeInsights(undefined, [], undefined, undefined, 'EUR')).toEqual([]);
  });
});
