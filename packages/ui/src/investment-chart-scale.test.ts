import { describe, expect, it } from 'vitest';

import { DELTA_BREAKS, deltaLegend, deltaStep, NO_DATA_STEP } from './investment-chart-scale';

/**
 * La escala del heatmap. Lo que se prueba no es que devuelva colores, sino las
 * tres decisiones que puede equivocar: qué es ruido, qué es un movimiento, y
 * qué NO es un dato.
 */
describe('deltaStep', () => {
  it('un hueco no cae al neutro: «no se midió» no es «no se movió»', () => {
    expect(deltaStep(null)).toBe(NO_DATA_STEP);
    expect(deltaStep(Number.NaN)).toBe(NO_DATA_STEP);
    expect(deltaStep(0).background).not.toBe(NO_DATA_STEP.background);
  });

  it('el ruido contable no se pinta como un movimiento', () => {
    const neutro = deltaStep(0);
    expect(deltaStep(0.019)).toEqual(neutro);
    expect(deltaStep(-0.019)).toEqual(neutro);
    expect(deltaStep(0.021)).not.toEqual(neutro);
  });

  it('la escala es simétrica: un lado más ancho sería una conclusión inventada', () => {
    const subeFuerte = deltaStep(DELTA_BREAKS.strong);
    const bajaFuerte = deltaStep(-DELTA_BREAKS.strong);
    expect(deltaStep(0.5)).toEqual(subeFuerte);
    expect(deltaStep(-0.5)).toEqual(bajaFuerte);
    expect(subeFuerte.background).not.toBe(bajaFuerte.background);
  });

  it('el fondo oscuro lleva tinta clara y al revés', () => {
    expect(deltaStep(0.5).foreground).toBe('#ffffff');
    expect(deltaStep(0.05).foreground).toBe('#1f1f1f');
  });

  it('las TRES bandas de cada lado son alcanzables', () => {
    // Con dos cortes, el paso más claro de cada rampa no salía nunca: un color
    // declarado y muerto. Tres bandas exigen tres cortes.
    const arriba = new Set([0.05, 0.18, 0.6].map((v) => deltaStep(v).background));
    const abajo = new Set([-0.05, -0.18, -0.6].map((v) => deltaStep(v).background));
    expect(arriba.size).toBe(3);
    expect(abajo.size).toBe(3);
  });
});

describe('deltaLegend', () => {
  it('se deriva de los mismos cortes que pintan las celdas', () => {
    const legend = deltaLegend();
    expect(legend).toHaveLength(7);
    expect(legend[0]?.label).toContain(String(Math.round(DELTA_BREAKS.strong * 100)));
    expect(legend[0]?.step).toEqual(deltaStep(-DELTA_BREAKS.strong));
    expect(legend[6]?.step).toEqual(deltaStep(DELTA_BREAKS.strong));
  });
});
