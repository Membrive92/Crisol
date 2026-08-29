import { describe, expect, it } from 'vitest';

import type { MetricResult, ScoreBreakdown } from '@crisol/types';

import { buildMetricIndex } from './investment-metric-index';
import { buildScoreHelpIndex } from './investment-score-help';
import { scoreBreakdownRows } from './investment-score-rows';

/**
 * El desglose de un score con su variación (PHASE-44.24.D).
 *
 * Un DSRI de 1,08 no dice nada suelto; que venga de 0,98 sí — es el movimiento
 * lo que Beneish detecta. Lo que estos tests atan es que la comparación no se
 * invente: sin ejercicio anterior no hay delta, y `null` no es «no ha cambiado».
 */

const YEARS = [2022, 2023, 2024];

function metric(year: number, value: number): MetricResult {
  return {
    key: 'm_score',
    fiscal_year: year,
    value: String(value),
    band: null,
    status: 'ok',
    reason: null,
  } as MetricResult;
}

const index = buildMetricIndex([metric(2022, -2.9), metric(2023, -2.7), metric(2024, -2.4)], YEARS);

function bd(year: number, components: Record<string, string>, checks = {}): ScoreBreakdown {
  return { key: 'm_score', fiscal_year: year, components, checks };
}

describe('scoreBreakdownRows', () => {
  it('la delta compara contra el ejercicio anterior, con signo', () => {
    const view = scoreBreakdownRows(
      'm_score',
      [bd(2023, { DSRI: '0.98', GMI: '1.20' }), bd(2024, { DSRI: '1.08', GMI: '1.10' })],
      2024,
      index,
      'score',
    );
    const dsri = view.rows.find((r) => r.key === 'DSRI');
    expect(dsri?.value).toBe('1,08');
    expect(dsri?.delta).toBe('+0,1');
    expect(dsri?.direction).toBe('up');
    const gmi = view.rows.find((r) => r.key === 'GMI');
    expect(gmi?.delta).toBe('−0,1');
    expect(gmi?.direction).toBe('down');
  });

  it('sin ejercicio anterior la delta es null, NO «=»', () => {
    // Un «=» afirmaría una comparación que no se ha hecho; `null` dice que no
    // se puede comparar, y quien pinta no dibuja nada.
    const view = scoreBreakdownRows('m_score', [bd(2024, { DSRI: '1.08' })], 2024, index, 'score');
    expect(view.rows[0]?.delta).toBeNull();
    expect(view.rows[0]?.direction).toBeNull();
  });

  it('un movimiento por debajo del ruido se dice estable', () => {
    const view = scoreBreakdownRows(
      'm_score',
      [bd(2023, { DSRI: '1.000' }), bd(2024, { DSRI: '1.002' })],
      2024,
      index,
      'score',
    );
    expect(view.rows[0]?.delta).toBe('=');
    expect(view.rows[0]?.direction).toBe('flat');
  });

  it('compara contra el ANTERIOR PRESENTE, no contra `year - 1`', () => {
    // Con un hueco, `year - 1` no existe y la comparación se perdería entera
    // aunque haya un ejercicio con el que comparar.
    const view = scoreBreakdownRows(
      'm_score',
      [bd(2022, { DSRI: '0.90' }), bd(2024, { DSRI: '1.00' })],
      2024,
      index,
      'score',
    );
    expect(view.rows[0]?.delta).toBe('+0,1');
  });

  it('una variable que sólo existe en el año nuevo no finge una delta', () => {
    const view = scoreBreakdownRows(
      'm_score',
      [bd(2023, { DSRI: '0.98' }), bd(2024, { DSRI: '1.08', TATA: '0.02' })],
      2024,
      index,
      'score',
    );
    expect(view.rows.find((r) => r.key === 'TATA')?.delta).toBeNull();
  });

  it('un check dice si CAMBIÓ, no una magnitud', () => {
    const view = scoreBreakdownRows(
      'f_score',
      [
        { key: 'f_score', fiscal_year: 2023, components: {}, checks: { P1: false, P2: true } },
        { key: 'f_score', fiscal_year: 2024, components: {}, checks: { P1: true, P2: true } },
      ],
      2024,
      index,
      'score',
    );
    const p1 = view.rows.find((r) => r.key === 'P1');
    expect(p1?.kind).toBe('check');
    expect(p1?.passed).toBe(true);
    expect(p1?.delta).toBe('nuevo');
    // Un check que no se movió no dice nada: repetirlo en cada fila es ruido.
    expect(view.rows.find((r) => r.key === 'P2')?.delta).toBeNull();
  });

  it('sin desglose para ese ejercicio devuelve filas vacías, pero SÍ la serie', () => {
    // La serie del score existe aunque el desglose falte: son dos datos
    // distintos y colapsarlos escondería el único que hay.
    const view = scoreBreakdownRows('m_score', [bd(2022, { DSRI: '1' })], 2024, index, 'score');
    expect(view.rows).toEqual([]);
    expect(view.spark).not.toBeNull();
  });

  it('sin fichas cae a la clave cruda del motor y no a un hueco', () => {
    const view = scoreBreakdownRows('m_score', [bd(2024, { DSRI: '1.08' })], 2024, index, 'score');
    expect(view.rows[0]?.label).toBe('DSRI');
    expect(view.rows[0]?.help).toBeUndefined();
  });

  it('con fichas usa el nombre humano de cada variable', () => {
    const help = buildScoreHelpIndex({
      engine_version: '1.7.0',
      scores: [
        {
          key: 'm_score',
          what: 'x',
          why: 'y',
          reading: 'z',
          components: [{ key: 'DSRI', label: 'Días de venta en cuentas a cobrar', what: 'w' }],
        },
      ],
      flags: [],
    });
    const view = scoreBreakdownRows(
      'm_score',
      [bd(2024, { DSRI: '1.08' })],
      2024,
      index,
      'score',
      help,
    );
    expect(view.rows[0]?.label).toBe('Días de venta en cuentas a cobrar');
    expect(view.rows[0]?.help).toBe('w');
  });
});
