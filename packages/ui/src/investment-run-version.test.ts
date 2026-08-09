import { describe, expect, it } from 'vitest';

import type { QuestionVerdict } from '@crisol/types';

import { compareEngineVersions, isRunOutdated, questionEvidence } from './investment-run-version';

/**
 * Un `AnalysisRun` es JSONB persistido: la tabla guarda runs de todas las
 * versiones del motor que han existido, así que leer uno viejo con el código de
 * hoy es lo NORMAL, no un caso raro.
 */

function question(partial: Partial<QuestionVerdict> = {}): QuestionVerdict {
  return {
    key: 'accounting',
    question: '¿La contabilidad es de fiar?',
    verdict: 'healthy',
    red_signals: [],
    amber_signals: [],
    signals: [],
    evaluated_count: 0,
    unavailable_count: 0,
    ...partial,
  };
}

describe('compareEngineVersions', () => {
  it('compara por número y no como cadena: 1.10.0 es posterior a 1.9.0', () => {
    // Lexicográficamente '1.10.0' < '1.9.0'. El motor ya va por 1.3.0, así que
    // llegar a las dos cifras es cuestión de tiempo.
    expect(compareEngineVersions('1.10.0', '1.9.0')).toBeGreaterThan(0);
    expect(compareEngineVersions('1.0.0', '1.3.0')).toBeLessThan(0);
    expect(compareEngineVersions('1.3.0', '1.3.0')).toBe(0);
  });
});

describe('isRunOutdated', () => {
  it('marca caducado el run del usuario (1.0.0) frente al motor de hoy', () => {
    expect(isRunOutdated('1.0.0', '1.3.0')).toBe(true);
  });

  it('no marca nada si falta cualquiera de las dos versiones', () => {
    // Sin saber contra qué comparar, declarar caducado sería inventárselo.
    expect(isRunOutdated(undefined, '1.3.0')).toBe(false);
    expect(isRunOutdated('1.0.0', undefined)).toBe(false);
  });

  it('un run MÁS NUEVO que el catálogo no es un run caducado', () => {
    // Es un frontend servido de caché vieja. Mandar a reejecutar un análisis
    // sano sería el consejo equivocado.
    expect(isRunOutdated('1.4.0', '1.3.0')).toBe(false);
  });
});

describe('questionEvidence', () => {
  it('«no registrado» no se puede colapsar en «sin evidencia»', () => {
    // El fallo original: `undefined === 0` es false, así que la comprobación
    // vieja fallaba EN ABIERTO y pintaba estos casos como verde verificado.
    const legacy = question();
    delete legacy.signals;
    delete legacy.evaluated_count;
    expect(questionEvidence(legacy)).toBe('not-recorded');
  });

  it('con señales candidatas y ninguna contada, el verde es ausencia de prueba', () => {
    expect(
      questionEvidence(
        question({
          evaluated_count: 0,
          signals: [
            {
              key: 'm_score',
              label: 'M-Score',
              kind: 'metric',
              band: null,
              value: null,
              status: 'not_computable',
              counted: false,
              reason: 'no aplica a financieras',
            },
          ],
        }),
      ),
    ).toBe('no-evidence');
  });

  it('con señales evaluadas, el veredicto se sostiene', () => {
    expect(questionEvidence(question({ evaluated_count: 3, signals: [] }))).toBe('evaluated');
  });
});
