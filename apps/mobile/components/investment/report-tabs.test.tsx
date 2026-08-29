// @types/jest expone los globals (describe/it/expect) — sin import.
import { StyleSheet } from 'react-native';

import { fireEvent, render } from '@testing-library/react-native';

import {
  buildCatalogIndex,
  buildMetricIndex,
  colors,
  DUPONT_SECTIONS,
  RATIO_FAMILIES,
} from '@crisol/ui';
import type { AnalysisRun, MetricDefinition, MetricResult, QuestionSignal } from '@crisol/types';

import { TabEvolution, TabRatios, TabVerdict, type TabContext } from './report-tabs';

/**
 * Regresión de la brecha que cerró PHASE-44.8.
 *
 * El móvil se quedó en la vista resumida de PHASE-44.7 mientras la web pasaba a
 * seis pestañas: pintaba `[...red_signals, ...amber_signals].join(' · ')`, o
 * sea las CLAVES CRUDAS del motor, y los valores sin formato por unidad (un
 * margen del 42 % se leía `0,42`). Estos tests fijan las dos cosas.
 */

// Sin `as`: los objetos se construyen COMPLETOS. Un cast aquí sería justo lo
// que las reglas del proyecto prohíben, y además tapa el día que el contrato
// cambie — que es cuando este test tendría que avisar.
function metric(key: string, year: number, value: string): MetricResult {
  return {
    key,
    fiscal_year: year,
    value,
    status: 'ok',
    provenance: 'sourced',
    reason: null,
    band: 'healthy',
  };
}

function definition(key: string, label: string, unit: MetricDefinition['unit']): MetricDefinition {
  return {
    key,
    label,
    family: 'rentabilidad',
    unit,
    direction: null,
    low_alarm: null,
    low_ok: null,
    high_ok: null,
    high_alarm: null,
    model_variant: null,
    note: '',
  };
}

const YEARS = [2024, 2025];

const CATALOG = buildCatalogIndex([
  definition('R4', 'Margen neto', 'percent'),
  definition('L1', 'Ratio corriente', 'times'),
]);

function makeRun(signals: QuestionSignal[]): AnalysisRun {
  return {
    years_covered: YEARS,
    thresholds_used: {},
    engine_version: '1.3.0',
    data_completeness: { value: '1' },
    flags: [],
    evolution: { horizontal: [], vertical: [], metrics: [], flags: [] },
    dividend_analysis: { metrics: [], flags: [] },
    dividend_verdict: 'sustainable',
    scores_detail: {
      base_ratios: {
        metrics: [metric('R4', 2024, '0.42'), metric('R4', 2025, '0.44')],
        dupont: [],
      },
      forensic: { metrics: [], breakdowns: [] },
    },
    verdict: {
      safety_profile: { label: 'conservative' },
      questions: [
        {
          key: 'accounting',
          question: '¿Se puede fiar uno de sus cuentas?',
          verdict: 'healthy',
          red_signals: [],
          amber_signals: [],
          // Los tres campos de PHASE-44.9 viajan JUNTOS o no viajan: el motor
          // los emite a la vez. Un fixture con `signals` y sin contadores es
          // una forma que no existe en la BD, y como el objeto va casteado
          // (`as unknown as AnalysisRun`) TS no lo impide — hay que cuidarlo a
          // mano.
          signals,
          evaluated_count: signals.filter((s) => s.counted).length,
          unavailable_count: signals.filter((s) => !s.counted).length,
        },
      ],
    },
  } as unknown as AnalysisRun;
}

function makeCtx(run: AnalysisRun): TabContext {
  return {
    run,
    index: buildMetricIndex(
      [...run.scores_detail.base_ratios.metrics, ...run.evolution.metrics],
      YEARS,
    ),
    catalog: CATALOG,
    security: undefined,
  };
}

describe('TabVerdict (móvil)', () => {
  it('pinta la ETIQUETA de la señal, no su clave interna', () => {
    const run = makeRun([
      {
        key: 'B4_dividend_funded_externally',
        label: 'El dividendo se financia con deuda',
        kind: 'flag',
        value: null,
        band: 'stressed',
        counted: true,
        reason: null,
      } as QuestionSignal,
    ]);

    const { queryByText, getByText } = render(<TabVerdict ctx={makeCtx(run)} />);

    expect(getByText('El dividendo se financia con deuda')).toBeTruthy();
    expect(queryByText(/B4_dividend_funded_externally/)).toBeNull();
  });

  it('enseña también las señales que NO puntúan, con su motivo', () => {
    // Saber qué se comprobó y salió bien es la otra mitad del porqué; ocultarlo
    // permitía que una financiera pintara verde por AUSENCIA de prueba.
    const run = makeRun([
      {
        key: 'm_score',
        label: 'Beneish M-Score',
        kind: 'metric',
        value: null,
        band: null,
        counted: false,
        reason: 'no aplica a financieras',
      } as QuestionSignal,
    ]);

    const { getByText } = render(<TabVerdict ctx={makeCtx(run)} />);

    expect(getByText(/no puntúa · no aplica a financieras/)).toBeTruthy();
  });

  it('una pregunta sin señales candidatas lo dice, en vez de fingir un desglose', () => {
    const { getByText } = render(<TabVerdict ctx={makeCtx(makeRun([]))} />);
    expect(getByText(/no evaluó ninguna señal/)).toBeTruthy();
  });

  /**
   * Un `AnalysisRun` es JSONB persistido y la tabla guarda runs de TODAS las
   * versiones del motor. En web esta forma provocaba un `TypeError` al desplegar
   * una pregunta (el usuario lo leía como un 404); móvil no reventaba porque
   * hacía `signals ?? []`, pero por eso mismo presentaba el veredicto como si
   * estuviera auditado.
   */
  it('un análisis de un motor anterior no presume de veredicto auditado', () => {
    const run = makeRun([]);
    const question = run.verdict.questions[0]!;
    delete question.signals;
    delete question.evaluated_count;
    delete question.unavailable_count;

    const { getByText, queryByText } = render(<TabVerdict ctx={makeCtx(run)} />);

    expect(getByText('No auditable')).toBeTruthy();
    expect(getByText(/no registraba qué señales se evaluaron/)).toBeTruthy();
    expect(queryByText(/no evaluó ninguna señal/)).toBeNull();
  });
});

describe('TabRatios (móvil)', () => {
  it('formatea por unidad: un margen del 42 % no se lee «0,42»', () => {
    // Se afirma en POSITIVO el texto esperado, no sólo la ausencia del crudo:
    // un `queryByText(...) === null` también pasa si no se renderiza nada, que
    // es la forma más fácil de tener un test verde que no comprueba nada.
    const { queryByText, getByText } = render(<TabRatios ctx={makeCtx(makeRun([]))} />);

    expect(getByText('Margen neto')).toBeTruthy();
    expect(getByText('42,0 %')).toBeTruthy();
    expect(getByText('44,0 %')).toBeTruthy();
    expect(queryByText('0,42')).toBeNull();
  });

  it('lista TODOS los bloques de ratios compartidos, no una lista escrita a mano', () => {
    // Este test era ciego (PHASE-44.20): comprobaba cuatro etiquetas escritas a
    // mano aquí, que casualmente eran las de `RATIO_FAMILIES`. Web tenía un
    // QUINTO bloque —el DuPont— escrito en su propio tab, así que móvil no lo
    // pintaba y el test pasaba en verde. Su comentario describía el modo de
    // fallo CONTRARIO al que ocurrió: no fue una duplicación en móvil, fue una
    // sección de web que nunca subió a la capa compartida.
    //
    // Ahora se deriva de la fuente compartida, así que añadir un bloque allí y
    // no pintarlo aquí falla.
    const { getByText } = render(<TabRatios ctx={makeCtx(makeRun([]))} />);
    for (const family of RATIO_FAMILIES) {
      expect(getByText(family.label)).toBeTruthy();
    }
    for (const section of DUPONT_SECTIONS) {
      expect(getByText(section.label)).toBeTruthy();
    }
  });
});

/**
 * Las señales del veredicto NAVEGAN (PHASE-44.24, auditoría UX).
 *
 * En móvil tocar «Deuda neta / EBITDA» no hacía nada; web llevaba a Ratios con
 * la fila resaltada. Mismo registro de destinos (`locateMetric`): una métrica
 * con fila navega, una bandera no — y no se pinta como algo que se pueda tocar.
 */
describe('TabVerdict (móvil): las señales navegan', () => {
  const metrica: QuestionSignal = {
    key: 'S2',
    label: 'Cobertura de intereses',
    kind: 'metric',
    value: '3.2',
    band: 'caution',
    counted: true,
    reason: null,
  } as QuestionSignal;
  const bandera: QuestionSignal = {
    key: 'B4_dividend_funded_externally',
    label: 'El dividendo se financia con deuda',
    kind: 'flag',
    value: null,
    band: 'stressed',
    counted: true,
    reason: null,
  } as QuestionSignal;

  it('tocar una métrica lleva a su pestaña con la fila resaltada', () => {
    const goTo = jest.fn();
    const { getByText } = render(<TabVerdict ctx={{ ...makeCtx(makeRun([metrica])), goTo }} />);
    fireEvent.press(getByText(/Cobertura de intereses/));
    expect(goTo).toHaveBeenCalledWith('ratios', 'S2');
  });

  /**
   * El `Pressable` que envuelve la fila, subiendo desde el texto.
   *
   * Lo que se comprueba es que esté DESHABILITADO, no que `goTo` no se llame:
   * con una bandera `goTo` no se llama de todas formas (no tiene destino), así
   * que una fila tocable-que-no-hace-nada —el defecto exacto que se arregla—
   * pasaría un test que sólo mirara la llamada.
   */
  // El tipo del nodo que devuelve `getByText`, sin importar
  // `react-test-renderer` (no tiene declaraciones instaladas).
  type Instance = ReturnType<ReturnType<typeof render>['getByText']>;

  function fila(node: Instance): Instance | null {
    let actual: Instance | null = node;
    for (let i = 0; i < 6 && actual; i += 1) {
      if (actual.props.accessibilityState !== undefined || actual.props.onPress !== undefined) {
        return actual;
      }
      actual = actual.parent;
    }
    return null;
  }

  it('tocar una bandera no hace nada, y la fila está DESHABILITADA', () => {
    const goTo = jest.fn();
    const { getByText, queryByRole } = render(
      <TabVerdict ctx={{ ...makeCtx(makeRun([bandera])), goTo }} />,
    );
    const texto = getByText(/El dividendo se financia con deuda/);
    fireEvent.press(texto);
    expect(goTo).not.toHaveBeenCalled();
    expect(queryByRole('button', { name: /El dividendo se financia/ })).toBeNull();
    const presionable = fila(texto);
    expect(presionable).not.toBeNull();
    expect((presionable!.props.accessibilityState as { disabled?: boolean }).disabled).toBe(true);
  });

  it('una métrica con destino está HABILITADA', () => {
    const { getByText } = render(
      <TabVerdict ctx={{ ...makeCtx(makeRun([metrica])), goTo: jest.fn() }} />,
    );
    const presionable = fila(getByText(/Cobertura de intereses/));
    expect(presionable).not.toBeNull();
    expect(
      (presionable!.props.accessibilityState as { disabled?: boolean } | undefined)?.disabled,
    ).not.toBe(true);
  });

  it('sin `goTo` (una pantalla que no navega) nada es tocable', () => {
    const { queryByRole } = render(<TabVerdict ctx={makeCtx(makeRun([metrica]))} />);
    expect(queryByRole('button', { name: /Cobertura de intereses/ })).toBeNull();
  });
});

/**
 * Evolución con un run de motor anterior (móvil, paridad con web).
 *
 * `horizontal` AUSENTE es «ese motor no la producía», no «no hay magnitudes».
 * Se escribe OMITIENDO la clave: con `[]` el test pasaría por otra razón.
 */
describe('TabEvolution (móvil) con un run viejo', () => {
  it('dice que la sección no existe en ese motor', () => {
    const base = makeRun([]);
    const run = {
      ...base,
      engine_version: '1.0.0',
      evolution: { metrics: [], vertical: [], flags: [] },
    } as unknown as AnalysisRun;
    const { getByText, queryByText } = render(<TabEvolution ctx={{ ...makeCtx(base), run }} />);
    expect(getByText(/no tiene serie de evolución/)).toBeTruthy();
    expect(getByText(/motor 1\.0\.0/)).toBeTruthy();
    expect(queryByText('Magnitud')).toBeNull();
  });
});

/**
 * El CABLEADO de `highlightKey` hasta una pestaña real (revisión adversarial).
 *
 * `YearMatrix` aislada ya se probaba; lo que nadie miraba es que la pestaña
 * pase el valor del contexto a sus matrices. Diez llamadas, ninguna con test.
 */
describe('las pestañas móviles resaltan la fila del contexto', () => {
  it('Ratios marca la fila de `highlightKey`', () => {
    const ctx = { ...makeCtx(makeRun([])), highlightKey: 'L1' };
    const label = ctx.catalog.definition('L1')?.label ?? 'L1';
    const { getAllByText } = render(<TabRatios ctx={ctx} />);
    const marcadas = getAllByText(label).filter(
      (node) => StyleSheet.flatten(node.props.style).color === colors.primary,
    );
    expect(marcadas.length).toBeGreaterThan(0);
  });
});
