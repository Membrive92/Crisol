import { describe, expect, it } from 'vitest';

import type { MetricResult } from '@crisol/types';

import { sparklineOf } from './investment-sparkline';

/**
 * La serie de una fila (PHASE-44.24.D).
 *
 * El informe pintaba el NIVEL de cada año y no la dirección. Lo que estos tests
 * atan es lo que NO debe hacer: interpolar un hueco, dibujar con dos puntos, o
 * llamar «descendente» a una serie plana.
 */

function metric(value: number | null, status: MetricResult['status'] = 'ok'): MetricResult {
  return {
    key: 'S2',
    fiscal_year: 2020,
    value: value === null ? null : String(value),
    band: null,
    status,
    reason: null,
  } as MetricResult;
}

const YEARS = [2020, 2021, 2022, 2023, 2024];

describe('sparklineOf', () => {
  it('una serie completa produce un punto por ejercicio, normalizado a [0,1]', () => {
    const spark = sparklineOf(
      [1, 2, 3, 4, 5].map((v) => metric(v)),
      'times',
      YEARS,
    );
    expect(spark).not.toBeNull();
    expect(spark?.points).toHaveLength(5);
    expect(spark?.points[0]).toEqual({ x: 0, y: 0 });
    expect(spark?.points[4]).toEqual({ x: 1, y: 1 });
    expect(spark?.trend).toBe('up');
  });

  it('un hueco en medio se OMITE, no se interpola', () => {
    // Interpolar dibujaría una línea continua sobre un año que nadie midió, que
    // es exactamente la mentira que el motor evita con `not_computable`.
    const spark = sparklineOf(
      [metric(1), metric(null, 'not_computable'), metric(3), metric(4)],
      'times',
      YEARS,
    );
    expect(spark?.points).toHaveLength(3);
    // El punto que sigue al hueco conserva su posición REAL en el eje: si se
    // recolocara, la línea escondería que falta un año.
    expect(spark?.points[1]?.x).toBeCloseTo(2 / 3, 5);
    // Y la etiqueta NO nombra un rango continuo cuando falta uno en medio:
    // «serie 2020-2023» con tres valores sugiere un año que nadie midió.
    expect(spark?.ariaLabel).toBe('serie 2020, 2022, 2023: 1,00×; 3,00×; 4,00× — ascendente');
  });

  it('un ejercicio declarado NO APLICABLE no se dibuja, aunque traiga número', () => {
    // El filtro por ESTADO no es redundante con el de valor ausente. Hoy el
    // motor los empareja siempre (un `not_applicable` sale con `value: null`),
    // pero la calibración sectorial de PHASE-44.21 apaga 33 métricas dejándoles
    // su número: si un día ese apagado llega también al estado, dibujar la
    // línea afirmaría una serie que el propio informe declara inaplicable.
    // Un `AnalysisRun` es JSONB de todas las versiones, así que el tipo lo
    // admite y la guarda es lo único que lo impide.
    const spark = sparklineOf(
      [metric(1), metric(2), metric(3, 'not_applicable'), metric(4)],
      'times',
      YEARS,
    );
    expect(spark?.points).toHaveLength(3);
    expect(spark?.ariaLabel).toBe('serie 2020, 2021, 2023: 1,00×; 2,00×; 4,00× — ascendente');
  });

  it('un `not_computable` con valor rancio tampoco entra', () => {
    const spark = sparklineOf(
      [metric(1), metric(99, 'not_computable'), metric(3), metric(4)],
      'times',
      YEARS,
    );
    // Sin la guarda de estado, el 99 dispararía la escala entera y la línea
    // contaría un salto que el motor dice que no se pudo medir.
    expect(spark?.points).toHaveLength(3);
    expect(spark?.ariaLabel).not.toContain('99');
  });

  it('con menos de tres puntos devuelve null: dos puntos son una recta', () => {
    // `null` NO es «no hay datos». Quien pinta debe decir «serie corta» en vez
    // de dejar la celda en blanco, que se leería como «no calculable».
    expect(sparklineOf([metric(1), metric(2)], 'times', YEARS)).toBeNull();
    expect(sparklineOf([], 'times', YEARS)).toBeNull();
  });

  it('una serie constante se centra en vez de dividir por cero', () => {
    const spark = sparklineOf(
      [2, 2, 2].map((v) => metric(v)),
      'times',
      YEARS,
    );
    expect(spark?.points.every((p) => p.y === 0.5)).toBe(true);
    expect(spark?.trend).toBe('flat');
  });

  it('un movimiento por debajo del ruido es estable, no una tendencia', () => {
    // 1,00 → 1,01 es un 1 %: decir «ascendente» ahí afirma una tendencia que
    // nadie ha medido.
    expect(
      sparklineOf(
        [1, 1.005, 1.01].map((v) => metric(v)),
        'times',
        YEARS,
      )?.trend,
    ).toBe('flat');
    expect(
      sparklineOf(
        [1, 1.1, 1.2].map((v) => metric(v)),
        'times',
        YEARS,
      )?.trend,
    ).toBe('up');
    expect(
      sparklineOf(
        [1.2, 1.1, 1].map((v) => metric(v)),
        'times',
        YEARS,
      )?.trend,
    ).toBe('down');
  });

  it('la etiqueta lee los valores CON su unidad y nombra los ejercicios', () => {
    // Un dibujo sin texto alternativo es un dato que sólo existe para quien
    // puede verlo — y «0,42» leído en crudo es el bug que 44.13 arregló.
    const spark = sparklineOf(
      [0.4, 0.41, 0.42].map((v) => metric(v)),
      'percent',
      YEARS,
    );
    expect(spark?.ariaLabel).toBe('serie 2020-2022: 40,0 %; 41,0 %; 42,0 % — ascendente');
  });

  it('sin años no inventa un rango: dice cuántos ejercicios hay', () => {
    const spark = sparklineOf(
      [1, 2, 3].map((v) => metric(v)),
      'times',
      [],
    );
    expect(spark?.ariaLabel).toContain('3 ejercicios');
  });

  it('un valor no numérico no rompe la serie: se salta como un hueco', () => {
    const raro = { ...metric(1), value: 'n/d' } as MetricResult;
    expect(sparklineOf([raro, metric(2), metric(3)], 'times', YEARS)).toBeNull();
  });
});
