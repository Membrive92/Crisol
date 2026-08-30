import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { AnalysisRun, MetricDefinition, QuestionSignal, QuestionVerdict } from '@crisol/types';

import { buildCatalogIndex } from '@crisol/ui';
import { TabVerdict } from './tab-verdict';
import legacyRun from './__fixtures__/legacy-run-1.0.0.json';

/**
 * Lo que se prueba aquí es el requisito estrella del usuario: entender POR QUÉ
 * la empresa sale catalogada como sale.
 *
 * Las dos regresiones concretas que cierra:
 *  - la pantalla imprimía `M-Score · B4_dividend_funded_externally`, o sea la
 *    clave cruda de la bandera;
 *  - una financiera pintaba VERDE en «¿La contabilidad es de fiar?» por
 *    ausencia de prueba, sin que el cliente pudiera distinguirlo de la salud.
 */

const CATALOG: MetricDefinition[] = [
  {
    key: 'm_score',
    label: 'M-Score de Beneish',
    family: 'forense',
    unit: 'score',
    direction: 'lower_better',
    low_alarm: null,
    low_ok: null,
    high_ok: '-2.22',
    high_alarm: '-1.78',
    model_variant: null,
    note: '',
  },
];

function signal(partial: Partial<QuestionSignal>): QuestionSignal {
  return {
    key: 'm_score',
    label: 'M-Score de Beneish',
    kind: 'metric',
    band: 'healthy',
    value: '-2.41',
    status: 'ok',
    counted: true,
    reason: null,
    ...partial,
  };
}

function makeRun(overrides: Partial<AnalysisRun> = {}): AnalysisRun {
  const empty = { metrics: [], flags: [] };
  return {
    id: 'run-1',
    security_id: 'sec-1',
    run_date: '2026-07-30T18:04:00Z',
    engine_version: '1.1.0',
    thresholds_version: 'a'.repeat(64),
    thresholds_used: {},
    years_covered: [2023, 2024],
    m_score: '-2.41',
    z_score: '3.82',
    z_variant: "Z''(1995)",
    f_score: 7,
    accruals_ratio: '0.03',
    fcf_payout: '0.5',
    fcf_coverage: '1.9',
    dividend_verdict: 'healthy',
    confidence: '0.92',
    scores_detail: {
      forensic: { ...empty, breakdowns: [] },
      base_ratios: { ...empty, dupont: [] },
    },
    dividend_analysis: {
      ...empty,
      dps_series: [],
      trajectory: { streak_no_cut: 5, momentum_slowdown: false },
    },
    evolution: { ...empty, horizontal: [], vertical: [] },
    flags: [],
    verdict: {
      questions: [
        {
          key: 'accounting',
          question: '¿La contabilidad es de fiar?',
          verdict: 'healthy',
          red_signals: [],
          amber_signals: [],
          signals: [signal({})],
          evaluated_count: 1,
          unavailable_count: 0,
        },
      ],
      safety_profile: { label: 'conservative', blocking_reasons: [] },
      dividend_verdict: 'healthy',
      stress: {
        scenarios: [],
        contribution_margin: null,
        breakeven_fcf_drop: null,
        not_computable_reason: null,
      },
    },
    data_completeness: {
      value: '0.92',
      completeness_core: '0.92',
      staleness_factor: '1.0',
      imputed_core_count: 0,
      latest_fiscal_year_end: '2024-12-31',
      days_stale: 120,
    },
    ...overrides,
  };
}

function renderVerdict(run: AnalysisRun) {
  return render(
    <TabVerdict
      run={run}
      catalog={buildCatalogIndex(CATALOG)}
      statements={undefined}
      items={undefined}
      sub="dictamen"
      onSubChange={vi.fn()}
    />,
  );
}

/**
 * Un run del motor ≥ 1.8.0: sale «Evitar» por el X-Score, con el Z''-Score en
 * verde justo al lado. Es el caso que el usuario reportó.
 */
function runConMatriz(): AnalysisRun {
  const base = makeRun();
  return {
    ...base,
    report: {
      threshold_profile: {
        effective: 'generic',
        sector: 'consumer_discretionary',
        is_financial: false,
        is_reit: false,
      },
      questions: [],
      why: {
        decided_by: ['avoid_bankruptcy'],
        exit_sentence: 'Dejaría de ser «Evitar» si el X-Score saliera del rojo.',
        models_disagree: 'Los dos modelos de insolvencia no coinciden.',
        signals: [],
      },
    } as AnalysisRun['report'],
    verdict: {
      ...base.verdict,
      safety_profile: {
        label: 'avoid',
        blocking_reasons: ['X-Score en rojo (riesgo de quiebra)'],
        conditions: [
          {
            key: 'avoid_bankruptcy',
            rule: 'avoid',
            text: 'X-Score en rojo (riesgo de quiebra)',
            met: true,
            inverse: 'el X-Score saliera del rojo',
            signals: [
              {
                key: 'FZ',
                label: 'X-Score de Zmijewski',
                kind: 'metric',
                band: 'stressed',
                value: '0.87',
              },
            ],
          },
          {
            key: 'avoid_insolvency',
            rule: 'avoid',
            text: "Z''-Score en rojo (riesgo de insolvencia)",
            met: false,
            inverse: "el Z''-Score saliera del rojo",
            signals: [
              {
                key: 'z_score',
                label: "Z''-Score de Altman",
                kind: 'metric',
                band: 'healthy',
                value: '5.20',
              },
            ],
          },
          {
            key: 'cons_m_score',
            rule: 'conservative',
            text: 'M-Score no está en verde',
            met: null,
            reason: 'no se calculó en este ejercicio',
            inverse: 'el M-Score se pusiera en verde',
            signals: [],
          },
        ],
      },
    },
  };
}

/**
 * Abre la auditoría del sello (PHASE-44.26).
 *
 * La matriz de reglas nace PLEGADA: el Dictamen se lee de arriba abajo y la
 * auditoría lo sostiene desde detrás. Los tests que afirman su contenido la
 * abren primero — el mismo gesto que el usuario.
 */
async function openAudit() {
  await userEvent.click(screen.getByRole('button', { name: /auditoría del sello/i }));
}

describe('TabVerdict · el dictamen como sumario (PHASE-44.26)', () => {
  it('la auditoría nace PLEGADA: la matriz no es lo primero que se lee', async () => {
    // El feedback literal: «apuntes técnicos que hacen inviable su
    // entendimiento de forma rápida». La matriz no desaparece — se abre.
    renderVerdict(runConMatriz());
    expect(screen.queryByText(/Se evita si se cumple/i)).toBeNull();
    await openAudit();
    expect(screen.getByText(/Se evita si se cumple/i)).toBeTruthy();
  });

  it('las tres partes van EN HORIZONTAL, no apiladas', () => {
    // La petición literal fue «en una misma card PARA APROVECHAR EL ESPACIO»:
    // meterlas en una card apilándolas es justo lo contrario, porque la card
    // mide 2.400 px y el contenido bajaba en una columna de 640.
    renderVerdict(runConMatriz());
    const seccion = screen.getByText('Qué preocupa').closest('section');
    const grid = seccion?.parentElement;

    expect(grid?.style.display).toBe('grid');
    expect(grid?.style.gridTemplateColumns).toContain('auto-fit');
    // Las tres —lo malo, lo bueno y el stress— son hermanas en el mismo grid.
    expect(grid?.querySelectorAll(':scope > section')).toHaveLength(3);
    expect(grid?.textContent).toContain('Escenarios de stress');
  });

  it('en el dictamen imprimible la auditoría va abierta y SIN control', () => {
    // Un dictamen impreso sin sus reglas no es auditable; y un modo que ignora
    // un control no lo esconde: no lo renderiza (PHASE-44.24.H).
    render(
      <TabVerdict
        run={runConMatriz()}
        catalog={buildCatalogIndex(CATALOG)}
        statements={undefined}
        items={undefined}
        sub="dictamen"
        onSubChange={vi.fn()}
        printMode
      />,
    );
    expect(screen.getByText(/Se evita si se cumple/i)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /auditoría del sello/i })).toBeNull();
  });

  it('«Qué preocupa» lista la señal roja con su valor y su banda', () => {
    const base = makeRun();
    renderVerdict({
      ...base,
      verdict: {
        ...base.verdict,
        questions: [
          {
            ...base.verdict.questions[0]!,
            verdict: 'stressed',
            signals: [
              signal({}),
              signal({ key: 'FZ', label: 'X-Score de Zmijewski', band: 'stressed', value: '0.87' }),
            ],
            evaluated_count: 2,
          },
        ],
      },
    });
    // Todo vive en UNA card desde la fusión: lo que se acota es la LISTA.
    // La etiqueta comparte nodo con el valor y la banda: matcher por regex.
    const lista = screen.getAllByText(/X-Score de Zmijewski/)[0]!.closest('ul');
    expect(lista?.textContent).toContain('0,87');
    // Y el verde de la misma pregunta va a la otra lista, no a ésta.
    expect(lista?.textContent ?? '').not.toContain('M-Score de Beneish');
  });

  it('«Qué está bien» sólo lista lo comprobado, y lo dice', () => {
    renderVerdict(makeRun());
    const card = screen.getByText(/Qué está bien/).closest('div');
    expect(card?.textContent).toContain('M-Score de Beneish');
    expect(card?.textContent).toContain('sólo cuenta lo auditado');
  });
});

describe('TabVerdict · por qué este veredicto', () => {
  it('dice qué condición decidió el sello, con su número al lado', async () => {
    renderVerdict(runConMatriz());
    await openAudit();
    expect(screen.getByText('X-Score en rojo (riesgo de quiebra)')).toBeTruthy();
    expect(screen.getByText('decidió el veredicto')).toBeTruthy();
    expect(screen.getByText(/X-Score de Zmijewski · 0,87 · Riesgo/)).toBeTruthy();
  });

  it('el estado se dice con PALABRAS, no con un glifo bimodal', async () => {
    renderVerdict(runConMatriz());
    await openAudit();
    // La condición cumplida (la causa del «Evitar») ya no se pinta con «✕»,
    // que junto a una proposición se lee como «no es verdad».
    expect(screen.getAllByText('se cumple').length).toBeGreaterThan(0);
    expect(screen.getByText('no se cumple')).toBeTruthy();
    expect(screen.getByText('sin poder comprobar')).toBeTruthy();
  });

  it('una condición sin comprobar dice POR QUÉ', async () => {
    renderVerdict(runConMatriz());
    await openAudit();
    expect(screen.getByText('no se calculó en este ejercicio')).toBeTruthy();
  });

  it('el contrafactual y la discrepancia se pintan', () => {
    renderVerdict(runConMatriz());
    expect(screen.getByText(/Dejaría de ser «Evitar»/)).toBeTruthy();
    expect(screen.getByText(/Los dos modelos de insolvencia no coinciden/)).toBeTruthy();
  });

  it('el Z\'\'-Score sano se enseña JUNTO al X-Score rojo', async () => {
    // La contradicción que el lector no podía resolver: los dos scores de
    // quiebra en la misma card, uno al lado del otro.
    renderVerdict(runConMatriz());
    await openAudit();
    expect(screen.getByText(/Z''-Score de Altman · 5,20 · Sano/)).toBeTruthy();
  });

  it('un run anterior lo DICE en vez de rellenarlo con marcas inventadas', async () => {
    const base = makeRun();
    renderVerdict({
      ...base,
      verdict: {
        ...base.verdict,
        safety_profile: {
          label: 'avoid',
          blocking_reasons: ['X-Score en rojo (riesgo de quiebra)'],
        },
      },
    });
    await openAudit();
    // Cinco y no seis: el fallback sólo conoce las que la UI tenía escritas a
    // mano. La sexta (que B4 se pudiera comprobar) sólo aparece cuando la trae
    // la matriz del motor — y el aviso de abajo dice que falta detalle.
    expect(screen.getAllByText('sin registro en este análisis').length).toBe(5);
    expect(screen.getByText(/motor anterior/i)).toBeTruthy();
  });
});

describe('TabVerdict', () => {
  it('imprime las condiciones de Conservador, no sólo el sello', async () => {
    renderVerdict(makeRun());
    await openAudit();
    expect(screen.getByText('F-Score ≥ 7')).toBeTruthy();
    expect(screen.getByText('Accruals en verde')).toBeTruthy();
    expect(screen.getByText(/Se evita si se cumple/i)).toBeTruthy();
  });

  it('enseña la regla del semáforo, no sólo su resultado', async () => {
    renderVerdict(makeRun());
    await openAudit();
    expect(screen.getByText(/si hay ≥1 señal roja/)).toBeTruthy();
  });

  it('al abrir una pregunta muestra el valor de cada señal con su unidad', async () => {
    const user = userEvent.setup();
    renderVerdict(makeRun());
    await user.click(screen.getByRole('button', { name: /¿La contabilidad es de fiar\?/ }));
    expect(screen.getByText('M-Score de Beneish')).toBeTruthy();
    expect(screen.getByText('-2,41')).toBeTruthy();
    expect(screen.getByText('sano ≤ -2,22 · riesgo > -1,78')).toBeTruthy();
  });

  it('ninguna señal se imprime como clave cruda', async () => {
    const user = userEvent.setup();
    const run = makeRun();
    const question = run.verdict.questions[0];
    if (question) {
      question.signals = [
        signal({
          key: 'B4_dividend_funded_externally',
          label: 'Dividendo financiado con deuda o emisión',
          kind: 'flag',
          band: null,
          value: null,
          status: null,
          counted: false,
          reason: 'no se ha encendido',
        }),
      ];
    }
    renderVerdict(run);
    await user.click(screen.getByRole('button', { name: /¿La contabilidad es de fiar\?/ }));
    expect(screen.queryByText(/B4_dividend_funded_externally/)).toBeNull();
    expect(screen.getByText('Dividendo financiado con deuda o emisión')).toBeTruthy();
  });

  it('una pregunta sin señales evaluadas se marca «Sin evidencia», no verde', () => {
    const run = makeRun();
    const question = run.verdict.questions[0];
    if (question) {
      question.evaluated_count = 0;
      question.unavailable_count = 1;
      question.signals = [
        signal({
          band: null,
          value: null,
          status: 'not_computable',
          counted: false,
          reason: 'modelo no aplicable a financieras',
        }),
      ];
    }
    renderVerdict(run);
    expect(screen.getByText('Sin evidencia')).toBeTruthy();
    expect(screen.getByText(/por ausencia de prueba/)).toBeTruthy();
  });

  it('declara que la valoración no entra y por qué', () => {
    renderVerdict(makeRun());
    expect(screen.getByText(/necesitan precio de mercado/)).toBeTruthy();
  });

  it('imprime el hash de umbrales completo, no truncado', () => {
    renderVerdict(makeRun());
    expect(screen.getByText(new RegExp('a'.repeat(64)))).toBeTruthy();
  });

  it('cuando faltan escenarios de stress dice por qué en vez de callarse', () => {
    const run = makeRun();
    run.verdict.stress.not_computable_reason =
      'no se pudo estimar el apalancamiento operativo con esta serie';
    renderVerdict(run);
    expect(screen.getByText(/Faltan escenarios/)).toBeTruthy();
    expect(screen.getByText(/no se pudo estimar el apalancamiento operativo/)).toBeTruthy();
  });

  it('avisa de que el stress mide sobre caja libre y no sobre FFO', () => {
    renderVerdict(makeRun());
    expect(screen.getByText(/no sobre el FFO/)).toBeTruthy();
  });
});

/**
 * Un `AnalysisRun` es JSONB persistido: la tabla contiene runs de TODAS las
 * versiones del motor que han existido. Estas regresiones cierran el fallo que
 * reportó el usuario — desplegar una pregunta de un análisis viejo desmontaba
 * el árbol de React y la pantalla se leía como un 404.
 *
 * La fixture NO está escrita a mano: se extrajo de la BD del usuario (MCD,
 * motor 1.0.0, 2026-07-26). Una fixture inventada hoy llevaría la forma de hoy
 * y no probaría nada — que es exactamente por qué el bug llegó a producción con
 * la suite en verde.
 */
describe('TabVerdict con un análisis de un motor anterior', () => {
  // Frontera de datos: la fixture es JSON crudo de la BD, sin tipar.
  const legacyQuestions = legacyRun.questions as unknown as QuestionVerdict[];

  function legacyRunFixture(): AnalysisRun {
    const run = makeRun();
    run.engine_version = legacyRun.engine_version;
    run.verdict.questions = legacyQuestions;
    return run;
  }

  it('la fixture no trae las claves de PHASE-44.9 (si las trae, ya no prueba nada)', () => {
    const question = legacyQuestions[0]!;
    expect(question.signals).toBeUndefined();
    expect(question.evaluated_count).toBeUndefined();
  });

  it('no revienta al pintar una pregunta sin desglose de señales', () => {
    expect(() => renderVerdict(legacyRunFixture())).not.toThrow();
    expect(screen.getAllByText(/¿/).length).toBeGreaterThan(0);
  });

  it('no ofrece desplegar lo que no existe: sin flecha no hay trampa', () => {
    renderVerdict(legacyRunFixture());
    // El crash sólo se alcanzaba al desplegar. La cura no es capturar el error,
    // es no ofrecer un botón que abre a un mensaje de fallo. El ÚNICO
    // desplegable legítimo es la auditoría del sello (PHASE-44.26), que abre a
    // contenido que un run legacy sí tiene.
    const plegados = screen.queryAllByRole('button', { expanded: false });
    expect(plegados).toHaveLength(1);
    expect(plegados[0]?.textContent).toContain('auditoría del sello');
  });

  it('pulsar donde el usuario pulsó no desmonta el árbol', async () => {
    renderVerdict(legacyRunFixture());
    // La acción literal del informe: «cuando hago click en una de estas áreas,
    // me lleva a un 404». Cualquier botón que la pantalla ofrezca tiene que
    // sobrevivir al clic; el crash vivía en `signals.length` sobre `undefined`.
    for (const button of screen.queryAllByRole('button')) {
      await userEvent.click(button);
    }
    expect(screen.getAllByText(/no registraba qué señales se evaluaron/).length).toBeGreaterThan(0);
  });

  it('no inventa contadores: sin dato no se escribe « señales evaluadas»', () => {
    renderVerdict(legacyRunFixture());
    expect(screen.queryByText(/señales evaluadas/)).toBeNull();
    expect(screen.getAllByText(/no registraba qué señales se evaluaron/).length).toBeGreaterThan(0);
  });

  it('no presume de veredicto verificado cuando no puede auditarlo', () => {
    renderVerdict(legacyRunFixture());
    expect(screen.getAllByText('No auditable').length).toBe(legacyQuestions.length);
  });

  it('rescata las claves crudas que el run SÍ tiene, traducidas por el catálogo', () => {
    const run = makeRun();
    run.engine_version = '1.0.0';
    run.verdict.questions = [
      {
        ...legacyQuestions[0]!,
        red_signals: ['m_score'],
        amber_signals: [],
      },
    ];
    renderVerdict(run);
    // Etiqueta del catálogo, nunca la clave cruda.
    expect(screen.getByText(/M-Score de Beneish/)).toBeTruthy();
  });
});

/**
 * Modo dictamen (revisión adversarial de 44.24.H).
 *
 * Esconder el selector de secciones con CSS de impresión lo dejaba VIVO en
 * pantalla —pulsarlo escribía un `sub` que la página descartaba— y encima
 * salía en el papel. Y las señales seguían siendo enlaces con `tab` forzado.
 */
describe('TabVerdict en modo dictamen', () => {
  it('no renderiza el selector de secciones', () => {
    render(
      <TabVerdict
        run={makeRun()}
        catalog={buildCatalogIndex(undefined)}
        statements={undefined}
        items={undefined}
        sub="dictamen"
        onSubChange={vi.fn()}
        printMode
      />,
    );
    expect(screen.queryByRole('radiogroup', { name: 'Secciones del veredicto' })).toBeNull();
    expect(screen.queryByText('Confianza y datos')).toBeNull();
  });

  it('fuera del modo dictamen sí está', () => {
    render(
      <TabVerdict
        run={makeRun()}
        catalog={buildCatalogIndex(undefined)}
        statements={undefined}
        items={undefined}
        sub="dictamen"
        onSubChange={vi.fn()}
      />,
    );
    expect(screen.getByText('Confianza y datos')).toBeTruthy();
  });
});
