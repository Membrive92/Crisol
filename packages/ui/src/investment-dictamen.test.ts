import { describe, expect, it } from 'vitest';

import type { AnalysisRun, QuestionSignal, QuestionVerdict } from '@crisol/types';

import { buildCatalogIndex } from './investment-metric-index';
import { dictamenLists, permanentlyUnauditable } from './investment-dictamen';

/**
 * Las listas del Dictamen (PHASE-44.26).
 *
 * Lo que se ata no es el render: son las REGLAS de selección — porque un
 * sumario que elige mal no se ve mal, se lee convincente y miente. Cada caso
 * cubre un defecto que la revisión adversarial del diseño encontró ANTES de
 * escribir el código.
 */

function signal(partial: Partial<QuestionSignal>): QuestionSignal {
  return {
    key: 'FZ',
    label: 'X-Score de Zmijewski',
    kind: 'metric',
    band: 'stressed',
    value: '0.87',
    status: 'ok',
    counted: true,
    reason: null,
    outcome: 'scored',
    ...partial,
  };
}

function question(partial: Partial<QuestionVerdict>): QuestionVerdict {
  return {
    key: 'resilience',
    question: '¿Aguanta un golpe?',
    verdict: 'stressed',
    red_signals: [],
    amber_signals: [],
    signals: [],
    evaluated_count: 1,
    unavailable_count: 0,
    audited: true,
    load_bearing: ['z_score'],
    ...partial,
  };
}

function runWith(questions: QuestionVerdict[], extra: Record<string, unknown> = {}): AnalysisRun {
  return {
    verdict: {
      questions,
      safety_profile: { label: 'watch', blocking_reasons: [] },
      dividend_verdict: 'healthy',
      stress: {
        scenarios: [],
        contribution_margin: null,
        breakeven_fcf_drop: null,
        not_computable_reason: null,
      },
      ...extra,
    },
    thresholds_used: {},
  } as unknown as AnalysisRun;
}

const catalog = buildCatalogIndex(undefined);

describe('permanentlyUnauditable', () => {
  it('no auditada Y sin portantes: la financiera', () => {
    expect(
      permanentlyUnauditable(question({ audited: false, load_bearing: [] })),
    ).toBe(true);
  });

  it('no auditada PERO con portantes declarados: temporal, sí participa', () => {
    expect(
      permanentlyUnauditable(question({ audited: false, load_bearing: ['m_score'] })),
    ).toBe(false);
  });
});

describe('dictamenLists · qué preocupa', () => {
  it('una señal roja bajo una pregunta permanentemente no auditable NO entra', () => {
    // El caso de la financiera: el escenario de stress rojo bajo la pregunta
    // gris. Es la regla 1 de next_checks (servidor), espejada — sin el espejo,
    // el sumario mostraría el riesgo que el propio motor declara no evaluable.
    const lists = dictamenLists(
      runWith([
        question({
          audited: false,
          load_bearing: [],
          signals: [signal({ key: 'stress', kind: 'derived', value: null })],
        }),
      ]),
      catalog,
    );
    expect(lists.concerns).toHaveLength(0);
  });

  it('el tope NUNCA recorta una roja', () => {
    // Ocho rojas: salen las ocho. El tope sólo protege del muro de ámbar.
    const rojas = Array.from({ length: 8 }, (_, i) =>
      signal({ key: `r${i}`, label: `Roja ${i}` }),
    );
    const lists = dictamenLists(
      runWith([question({ signals: rojas, evaluated_count: 8 })]),
      catalog,
    );
    expect(lists.concerns).toHaveLength(8);
    expect(lists.concernsOverflow).toBe(0);
  });

  it('las ámbar se recortan a partir del tope, con el resto contado', () => {
    const señales = [
      signal({ key: 'r1', label: 'Roja' }),
      ...Array.from({ length: 9 }, (_, i) =>
        signal({ key: `a${i}`, label: `Ámbar ${i}`, band: 'caution' }),
      ),
    ];
    const lists = dictamenLists(
      runWith([question({ signals: señales, evaluated_count: 10 })]),
      catalog,
    );
    expect(lists.concerns).toHaveLength(6);
    expect(lists.concernsOverflow).toBe(4);
    // Y la roja va la primera, venga de donde venga.
    expect(lists.concerns[0]?.key).toBe('r1');
  });

  it('una señal que NO puntúa no preocupa: no está en el semáforo', () => {
    const lists = dictamenLists(
      runWith([
        question({
          signals: [
            signal({ counted: false, outcome: 'unchecked', reason: 'no se pudo comprobar' }),
          ],
          evaluated_count: 0,
        }),
      ]),
      catalog,
    );
    expect(lists.concerns).toHaveLength(0);
  });
});

describe('dictamenLists · el sumario del servidor manda (PHASE-44.26)', () => {
  it('con report.summary, las filas salen de SUS claves y en SU orden', () => {
    const run = runWith([
      question({
        signals: [
          signal({ key: 'a', label: 'A', band: 'healthy' }),
          signal({ key: 'b', label: 'B', band: 'stressed' }),
          signal({ key: 'c', label: 'C', band: 'caution' }),
        ],
        evaluated_count: 3,
      }),
    ]);
    (run as { report?: unknown }).report = {
      threshold_profile: {
        effective: 'generic',
        sector: 'consumer_discretionary',
        is_financial: false,
        is_reit: false,
      },
      questions: [],
      summary: {
        concerns_intro: 'Lo que más pesa en contra: B y C.',
        concern_keys: ['b', 'c'],
        concerns_overflow: 0,
        strengths_intro: 'Del lado bueno, con la comprobación superada: A.',
        strength_keys: ['a'],
        strengths_overflow: 2,
        stress_sentences: ['Con las ventas cayendo, la cobertura pasa de 1,4 a 1,1.'],
        stress_margin: 'La caja libre podría caer un 7 % antes de dejar de cubrir el dividendo.',
      },
    };
    const lists = dictamenLists(run, catalog);

    // El cliente NO reselecciona: busca por clave y formatea.
    expect(lists.concerns.map((row) => row.key)).toEqual(['b', 'c']);
    expect(lists.strengths.map((row) => row.key)).toEqual(['a']);
    expect(lists.strengthsOverflow).toBe(2);
    expect(lists.concernsIntro).toContain('Lo que más pesa');
    expect(lists.stressSentences).toHaveLength(1);
    expect(lists.stressMargin).toContain('7 %');
  });

  it('sin summary (backend anterior), el fallback selecciona y las frases van VACÍAS', () => {
    const lists = dictamenLists(
      runWith([question({ signals: [signal({})], evaluated_count: 1 })]),
      catalog,
    );
    expect(lists.concerns.map((row) => row.key)).toEqual(['FZ']);
    // El cliente nunca redacta una entrada: sin servidor, sin frase.
    expect(lists.concernsIntro).toBe('');
    expect(lists.strengthsIntro).toBe('');
  });
});

describe('dictamenLists · qué está bien', () => {
  it('un verde de una pregunta SIN evidencia no es una fortaleza', () => {
    // `evaluated_count: 0` con señales candidatas = verde por ausencia de
    // prueba (PHASE-44.9). Meterlo en «qué está bien» venderla como salud.
    const lists = dictamenLists(
      runWith([
        question({
          verdict: 'healthy',
          evaluated_count: 0,
          signals: [
            signal({ band: 'healthy', counted: false, outcome: 'unchecked', reason: 'sin datos' }),
          ],
        }),
      ]),
      catalog,
    );
    expect(lists.strengths).toHaveLength(0);
  });

  it('un verde bajo una pregunta NO AUDITADA tampoco lo es — aunque puntúe', () => {
    // El caso que de verdad ejercita la guarda: la pregunta tiene portantes
    // declarados (no es la financiera) pero le falta uno, así que su veredicto
    // no está auditado. Sus señales verdes puntuaron — y aun así no pueden
    // venderse como fortaleza, porque el conjunto que las sostiene está gris.
    // OJO: «qué preocupa» SÍ las listaría en rojo — callar un riesgo por un
    // tecnicismo es peor que decirlo con su matiz (regla 2 de next_checks).
    const lists = dictamenLists(
      runWith([
        question({
          audited: false,
          load_bearing: ['m_score'],
          verdict: 'healthy',
          evaluated_count: 3,
          signals: [signal({ key: 'v1', label: 'Verde', band: 'healthy' })],
        }),
      ]),
      catalog,
    );
    expect(lists.strengths).toHaveLength(0);
  });

  it('los verdes de preguntas evaluadas entran, con tope y resto contado', () => {
    const verdes = Array.from({ length: 8 }, (_, i) =>
      signal({ key: `v${i}`, label: `Verde ${i}`, band: 'healthy' }),
    );
    const lists = dictamenLists(
      runWith([question({ verdict: 'healthy', signals: verdes, evaluated_count: 8 })]),
      catalog,
    );
    expect(lists.strengths).toHaveLength(6);
    expect(lists.strengthsOverflow).toBe(2);
  });

  it('un escenario que sigue cubriendo sólo aparece si la resistencia está evaluada', () => {
    const escenarios = {
      scenarios: [
        {
          key: 'ST2',
          parameter: 'tipos',
          coverage_before: '1.08',
          coverage_after: '1.05',
          sentence: 'Con los tipos subiendo, la cobertura pasa de 1,08 a 1,05.',
          label: 'escenario hipotético',
        },
        {
          key: 'ST1',
          parameter: 'ventas',
          coverage_before: '1.08',
          coverage_after: '0.92',
          sentence: 'Con las ventas cayendo, deja de cubrir.',
          label: 'escenario hipotético',
        },
      ],
      contribution_margin: null,
      breakeven_fcf_drop: null,
      not_computable_reason: null,
    };

    const evaluada = dictamenLists(
      runWith([question({ signals: [signal({})], evaluated_count: 1 })], { stress: escenarios }),
      catalog,
    );
    // Sólo el que cubre (≥1), nunca el que falla — ese va en «qué preocupa».
    expect(evaluada.scenariosHolding).toEqual([
      'Con los tipos subiendo, la cobertura pasa de 1,08 a 1,05.',
    ]);

    // En una financiera (resistencia permanentemente no auditable), nada:
    // «aguanta el golpe» bajo una pregunta gris sería un verde inventado.
    const financiera = dictamenLists(
      runWith(
        [question({ audited: false, load_bearing: [], signals: [signal({})] })],
        { stress: escenarios },
      ),
      catalog,
    );
    expect(financiera.scenariosHolding).toHaveLength(0);
  });

  it('lo comprobado y limpio sale con su razón PERSISTIDA, no redactada aquí', () => {
    const lists = dictamenLists(
      runWith([
        question({
          signals: [
            signal({
              key: 'C7',
              label: 'Retorno financiado con deuda',
              kind: 'flag',
              band: null,
              value: null,
              counted: false,
              outcome: 'clear',
              reason: 'se comprobó y no se encendió',
            }),
          ],
          evaluated_count: 1,
        }),
      ]),
      catalog,
    );
    expect(lists.clean).toEqual([
      { label: 'Retorno financiado con deuda', reason: 'se comprobó y no se encendió' },
    ]);
  });

  it('las condiciones de «Evitar» descartadas salen del run, jamás se infieren', () => {
    const conMatriz = dictamenLists(
      runWith([question({ signals: [signal({})] })], {
        safety_profile: {
          label: 'avoid',
          blocking_reasons: ['X-Score en rojo (riesgo de quiebra)'],
          conditions: [
            {
              key: 'avoid_insolvency',
              rule: 'avoid',
              text: "Z''-Score en rojo (riesgo de insolvencia)",
              met: false,
            },
            {
              key: 'avoid_bankruptcy',
              rule: 'avoid',
              text: 'X-Score en rojo (riesgo de quiebra)',
              met: true,
            },
            // Sin comprobar ≠ descartada: no puede venderse como limpia.
            {
              key: 'avoid_manipulation',
              rule: 'avoid',
              text: 'M-Score y accruals ambos en rojo',
              met: null,
              reason: 'no se calculó',
            },
          ],
        },
      }),
      catalog,
    );
    expect(conMatriz.discarded).toEqual(["Z''-Score en rojo (riesgo de insolvencia)"]);

    // Un run viejo no trae la matriz: cero filas, cero inferencia.
    const legacy = dictamenLists(runWith([question({ signals: [signal({})] })]), catalog);
    expect(legacy.discarded).toHaveLength(0);
  });
});
