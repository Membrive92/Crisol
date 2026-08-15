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
    // El desglose suma 1000, igual que el resumen: el ratio sale del MISMO
    // universo. Antes las categorías sumaban 500 y el denominador venía del
    // resumen, así que el test verde describía una mezcla imposible.
    const out = computeInsights(
      summary('1000'),
      [cat('Alquiler', '400'), cat('Comida', '300'), cat('Ocio', '300')],
      undefined,
    );
    expect(out).toHaveLength(1);
    expect(out[0]!.title).toContain('Alquiler');
    expect(out[0]!.title).toContain('40%');
  });

  it('no emite concentración por debajo del umbral', () => {
    const out = computeInsights(
      summary('1000'),
      [cat('Comida', '300'), cat('Resto', '300'), cat('Ocio', '200'), cat('Casa', '200')],
      undefined,
    );
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
    const out = computeInsights(
      summary('1000'),
      [cat('Alquiler', '500'), cat('Comida', '500')],
      structure(-0.1, 0.2),
    );
    expect(out).toHaveLength(2);
    expect(out[0]!.title).toContain('Alquiler');
    expect(out[1]!.title).toMatch(/variables/i);
  });

  it('sin datos → sin insights (no placeholders vacíos)', () => {
    expect(computeInsights(undefined, [], undefined)).toEqual([]);
  });
  it('el porcentaje no puede pasar del 100 aunque el mes tenga gasto aplazado', () => {
    // PHASE-47.E — desde que el resultado del mes EXCLUYE las compras
    // aplazadas y el desglose las MANTIENE, las dos cifras difieren a
    // propósito. Tomando el numerador de una y el denominador de la otra salía
    // «Compras concentra el 220% de tus gastos»: un porcentaje imposible
    // impreso como si fuera un dato.
    const out = computeInsights(
      summary('300'), // caja del mes: 609,14 aplazados no salieron
      [cat('Compras', '659.14'), cat('Comida', '250')],
      undefined,
    );

    expect(out).toHaveLength(1);
    const pct = Number(out[0]!.title.match(/(\d+)%/)![1]);
    expect(pct).toBeLessThanOrEqual(100);
    expect(pct).toBe(73); // 659,14 / 909,14
  });
});
