import { describe, expect, it } from 'vitest';

import type { QuestionVerdict } from '@crisol/types';

import {
  compareEngineVersions,
  evidenceBreakdown,
  isRunOutdated,
  questionEvidence,
} from './investment-run-version';

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

  it('sin un PORTANTE, la pregunta no está auditada aunque haya señales', () => {
    // El cuarto estado (PHASE-44.21). McDonald's salía verde confiado con 3
    // señales de 10 y las dos que responden la pregunta —M-Score y accruals—
    // muertas: lo que decide no es cuántas, es cuáles.
    expect(
      questionEvidence(question({ evaluated_count: 3, signals: [], audited: false })),
    ).toBe('not-audited');
  });

  it('un run anterior a 1.6.0 no se declara no auditado: ausente no es false', () => {
    const legacy = question({ evaluated_count: 3, signals: [] });
    delete legacy.audited;
    expect(questionEvidence(legacy)).toBe('evaluated');
  });
});

/**
 * PHASE-44.17 — `unavailable_count` metía en un cubo cuatro cosas: no se pudo
 * calcular, la bandera no saltó (buena noticia), es informativa por diseño, y no
 * aplica. La frase tiene que decir la verdad sobre los tres formatos de run que
 * puede haber en la tabla.
 */
describe('evidenceBreakdown', () => {
  it('separa lo comprobado y limpio de lo que no se pudo comprobar', () => {
    const frase = evidenceBreakdown(
      question({ evaluated_count: 3, unavailable_count: 7, clear_count: 5, unchecked_count: 2 }),
    );
    expect(frase).toBe('3 señales evaluadas · 5 comprobadas y limpias · 2 sin poder comprobar');
  });

  it('un run anterior a 1.5.0 dice lo que sabe, sin inventarse el desglose', () => {
    const frase = evidenceBreakdown(question({ evaluated_count: 3, unavailable_count: 7 }));
    expect(frase).toBe('3 señales evaluadas · 7 sin poder evaluar');
    expect(frase).not.toMatch(/comprobadas y limpias/);
  });

  it('un run que no registraba contadores no produce frase', () => {
    const legacy = question();
    delete legacy.evaluated_count;
    expect(evidenceBreakdown(legacy)).toBe('');
  });
});
