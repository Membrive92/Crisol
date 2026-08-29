import { describe, expect, it } from 'vitest';

import type { ReportSignal, SignalDistance } from '@crisol/types';

import { distanceSentence, orderedSignals, originSentence } from './investment-signal-read';

/**
 * La lectura de una señal enriquecida (PHASE-44.24.C).
 *
 * Lo que se prueba aquí no es que devuelva cadenas: es que la MISMA distancia
 * se diga en la escala en que esa métrica se lee. Un margen que está a 0,03 del
 * corte está «a 3 pp», y decir «a 0,08× del verde» es aritméticamente correcto
 * y no se parece a nada que nadie diga en voz alta.
 */

function distance(partial: Partial<SignalDistance>): SignalDistance {
  return {
    cut: '1',
    absolute: '0.03',
    relative: '0.03',
    side: 'inside',
    next_band: 'caution',
    ...partial,
  };
}

describe('distanceSentence', () => {
  it('un margen se lee en PUNTOS, no en múltiplos', () => {
    const frase = distanceSentence(distance({ absolute: '0.03', relative: '0.1' }), 'percent');
    expect(frase).toBe('a 3 pp del ámbar');
  });

  it('una cobertura se lee en múltiplos del corte', () => {
    const frase = distanceSentence(
      distance({ absolute: '2.1', relative: '2.1', side: 'outside', next_band: 'stressed' }),
      'times',
    );
    expect(frase).toBe('2,1× dentro del rojo');
  });

  it('sin corte hacia donde medir dice el motivo, no un número inventado', () => {
    // S7 por debajo de su banda: no hay corte de alarma por ese lado.
    const frase = distanceSentence(
      distance({ cut: null, absolute: null, relative: null, missing_reason: 'no hay corte' }),
      'times',
    );
    expect(frase).toBe('no hay corte');
  });

  it('sin distancia relativa cae a la absoluta en vez de callarse', () => {
    // Es el caso de una puntuación: sus cortes son negativos y muy juntos, así
    // que la relativa no informa — pero la absoluta sí.
    const frase = distanceSentence(
      distance({ absolute: '0.4', relative: null, side: 'outside', next_band: 'stressed' }),
      'score',
    );
    expect(frase).toBe('0,40 dentro del rojo');
  });

  it('sin capa de lectura no dice nada', () => {
    expect(distanceSentence(null, 'times')).toBeNull();
    expect(distanceSentence(undefined, 'times')).toBeNull();
  });
});

describe('originSentence', () => {
  it('nombra el perfil cuando lo conoce, y no lo inventa cuando no', () => {
    expect(originSentence('sector', 'utilities')).toBe('banda de utilities');
    expect(originSentence('sector', undefined)).toBe('banda sectorial');
  });

  it('una entidad financiera no se describe como su sector', () => {
    // El perfil financiero se fusiona ENCIMA del sectorial: decir «banda de
    // industriales» de un corte que puso la banca sería falso.
    expect(originSentence('financial', 'industrials')).toBe('banda de entidades financieras');
  });

  it('una calibración anterior se declara en vez de pasar por sectorial', () => {
    expect(originSentence('earlier_calibration', 'utilities')).toContain('calibración anterior');
  });

  it('un corte que el run no registró dice que se enseña el de hoy', () => {
    expect(originSentence('not_recorded', undefined)).toContain('catálogo de hoy');
  });

  it('cuando la vara no aplica no dice nada: la fila ya lo explica', () => {
    expect(originSentence('not_applicable', 'financials')).toBeNull();
  });
});

describe('orderedSignals', () => {
  const report = (pairs: [string, number][]): ReportSignal[] =>
    pairs.map(([key, severity_rank]) => ({ key, severity_rank, threshold_origin: 'generic' }));

  it('ordena por el rango que manda el servidor', () => {
    const signals = [{ key: 'a' }, { key: 'b' }, { key: 'c' }];
    const ordenadas = orderedSignals(
      signals,
      report([
        ['c', 0],
        ['a', 1],
        ['b', 2],
      ]),
    );
    expect(ordenadas.map((s) => s.key)).toEqual(['c', 'a', 'b']);
  });

  it('sin capa de lectura conserva el orden original', () => {
    const signals = [{ key: 'a' }, { key: 'b' }];
    expect(orderedSignals(signals, undefined).map((s) => s.key)).toEqual(['a', 'b']);
    expect(orderedSignals(signals, []).map((s) => s.key)).toEqual(['a', 'b']);
  });

  it('lo que el servidor no clasifica va al FINAL, no al principio', () => {
    // Con `?? 0` una señal desconocida se colaría por delante de la peor, que
    // es justo la que hay que ver primero.
    const signals = [{ key: 'desconocida' }, { key: 'peor' }];
    const ordenadas = orderedSignals(signals, report([['peor', 0]]));
    expect(ordenadas.map((s) => s.key)).toEqual(['peor', 'desconocida']);
  });

  it('no muta la lista que recibe', () => {
    const signals = [{ key: 'b' }, { key: 'a' }];
    orderedSignals(
      signals,
      report([
        ['a', 0],
        ['b', 1],
      ]),
    );
    expect(signals.map((s) => s.key)).toEqual(['b', 'a']);
  });
});
