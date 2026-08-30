import { describe, expect, it } from 'vitest';

import type {
  CanonicalItemDefinition,
  FinancialStatement,
  SafetyCondition,
  SafetyProfile,
} from '@crisol/types';

import { REPORT_GUIDE, REPORT_SCOPE } from './investment-report-guide';
import {
  AVOID_RULES,
  blockingSummary,
  CONSERVATIVE_RULES,
  CORE_ITEMS,
  coreItemCoverage,
  DIVIDEND,
  SAFETY,
} from './investment-verdict-labels';
import { verdictWhyRows } from './investment-verdict-why';

/**
 * El view-model del veredicto (PHASE-44.24.E).
 *
 * `SAFETY` estaba duplicada en dos ficheros de web y las reglas del perfil
 * escritas a mano en uno. Lo que estos tests atan es la parte que NO es una
 * lista de constantes: cómo se evalúa cada regla contra `blocking_reasons`, que
 * es donde una copia por app se vuelve una divergencia.
 */

function profile(partial: Partial<SafetyProfile> = {}): SafetyProfile {
  return { label: 'watch', blocking_reasons: [], ...partial };
}

function condition(
  key: string,
  rule: 'avoid' | 'conservative',
  text: string,
  met: boolean | null,
  extra: Partial<SafetyCondition> = {},
): SafetyCondition {
  return { key, rule, text, met, inverse: `${key} cambiara`, signals: [], ...extra };
}

describe('verdictWhyRows con la matriz del motor', () => {
  it('un solo significado de «se cumple» en las dos listas', () => {
    // El diseño anterior usaba ✓/✕ con el sentido invertido entre listas: en
    // «Evitar», cumplir pintaba ✕, que junto a una proposición se lee como «no
    // es verdad» — la única línea que respondía a la pregunta salía negada.
    const why = verdictWhyRows(
      profile({
        label: 'avoid',
        conditions: [
          condition('avoid_bankruptcy', 'avoid', 'X-Score en rojo', true),
          condition('cons_fz', 'conservative', 'X-Score no está en verde', true),
        ],
      }),
      null,
    );
    const filas = why.sections.flatMap((s) => s.rows);
    expect(filas.every((row) => row.isBad === (row.state === 'holds'))).toBe(true);
    expect(filas.every((row) => row.stateLabel === 'se cumple')).toBe(true);
  });

  it('una condición sin comprobar NO se presenta como descartada', () => {
    const why = verdictWhyRows(
      profile({
        conditions: [
          condition('avoid_manipulation', 'avoid', 'M-Score y accruals en rojo', null, {
            reason: 'no se calculó en este ejercicio',
          }),
        ],
      }),
      null,
    );
    const fila = why.sections[0]?.rows[0];
    expect(fila?.state).toBe('unknown');
    expect(fila?.isBad).toBe(false);
    expect(fila?.reason).toBe('no se calculó en este ejercicio');
  });

  it('la condición que disparó el sello viene marcada', () => {
    const why = verdictWhyRows(
      profile({
        label: 'avoid',
        conditions: [
          condition('avoid_bankruptcy', 'avoid', 'X-Score en rojo', true),
          condition('avoid_insolvency', 'avoid', "Z''-Score en rojo", false),
        ],
      }),
      { decided_by: ['avoid_bankruptcy'], exit_sentence: 'Dejaría de ser «Evitar» si…' },
    );
    const porClave = new Map(why.sections.flatMap((s) => s.rows).map((r) => [r.key, r]));
    expect(porClave.get('avoid_bankruptcy')?.decided).toBe(true);
    expect(porClave.get('avoid_insolvency')?.decided).toBe(false);
    expect(why.exitSentence).toContain('Evitar');
  });

  it('la señal de la condición trae su lectura para no cruzarla por texto', () => {
    const why = verdictWhyRows(
      profile({
        label: 'avoid',
        conditions: [
          condition('avoid_bankruptcy', 'avoid', 'X-Score en rojo', true, {
            signals: [
              {
                key: 'FZ',
                label: 'X-Score de Zmijewski',
                kind: 'metric',
                band: 'stressed',
                value: '0.87',
              },
            ],
          }),
        ],
      }),
      null,
    );
    const señal = why.sections[0]?.rows[0]?.signals[0];
    expect(señal?.key).toBe('FZ');
    expect(señal?.reading).toContain('Riesgo');
    expect(señal?.isFlag).toBe(false);
  });
});

describe('verdictWhyRows con un run anterior', () => {
  it('NO afirma el estado de las condiciones que aquel motor no evaluó', () => {
    // El defecto: bajo «Evitar», `blocking_reasons` contiene los motivos de
    // EVITAR, no las negaciones de Conservador — y el motor de entonces
    // retornaba antes de evaluarlas. La checklist pintaba «F-Score ≥ 7 ✓».
    const why = verdictWhyRows(
      profile({
        label: 'avoid',
        blocking_reasons: ['X-Score en rojo (riesgo de quiebra)'],
      }),
      null,
    );
    const conservadoras = why.sections.find((s) => s.key === 'conservative');

    expect(why.legacy).toBe(true);
    expect(conservadoras?.rows.every((row) => row.state === 'unrecorded')).toBe(true);
    expect(conservadoras?.rows.some((row) => row.state === 'clear')).toBe(false);
  });

  it('las de «Evitar» sí se marcan: su texto es un dato del run', () => {
    const motivo = "Z''-Score en rojo (riesgo de insolvencia)";
    const why = verdictWhyRows(profile({ label: 'avoid', blocking_reasons: [motivo] }), null);
    const evitar = why.sections.find((s) => s.key === 'avoid');

    expect(evitar?.rows.filter((row) => row.state === 'holds')).toHaveLength(1);
    expect(evitar?.rows.find((row) => row.text === motivo)?.decided).toBe(true);
  });

  it('en «Vigilar» el motivo en negativo sí describe el run', () => {
    const why = verdictWhyRows(
      profile({ blocking_reasons: ['M-Score no está en verde', 'F-Score es 4'] }),
      null,
    );
    const porTexto = new Map(
      why.sections.find((s) => s.key === 'conservative')?.rows.map((r) => [r.key, r.state]) ?? [],
    );
    expect(porTexto.get('M-Score en verde')).toBe('holds');
    expect(porTexto.get('F-Score ≥ 7')).toBe('holds');
    expect(porTexto.get('Accruals en verde')).toBe('clear');
  });

  it('sin la matriz no se inventa un contrafactual', () => {
    const why = verdictWhyRows(profile({ label: 'avoid' }), null);
    expect(why.exitSentence).toBe('');
    expect(why.modelsDisagree).toBeNull();
  });
});

describe('el resto del view-model', () => {
  it('el rótulo de los motivos cambia con el perfil', () => {
    expect(blockingSummary(profile({ label: 'avoid' })).blockingLabel).toContain('Motivos');
    expect(blockingSummary(profile({ label: 'watch' })).blockingLabel).toContain('Conservador');
  });

  it('las dos listas de fallback cubren los criterios del motor', () => {
    expect(AVOID_RULES).toHaveLength(4);
    expect(CONSERVATIVE_RULES).toHaveLength(5);
  });

  it('los tres perfiles y los cuatro veredictos de dividendo tienen etiqueta', () => {
    expect(Object.keys(SAFETY).sort()).toEqual(['avoid', 'conservative', 'watch']);
    expect(Object.keys(DIVIDEND).sort()).toEqual([
      'caution',
      'healthy',
      'not_applicable',
      'stressed',
    ]);
  });
});

describe('coreItemCoverage', () => {
  function statement(year: number, overrides: Record<string, unknown> = {}): FinancialStatement {
    const base: Record<string, unknown> = { fiscal_year: year };
    for (const key of CORE_ITEMS) base[key] = '100';
    return { ...base, ...overrides } as unknown as FinancialStatement;
  }

  const items = [
    { key: 'revenue', label: 'Ingresos' },
    { key: 'capex', label: 'Inversión' },
  ] as CanonicalItemDefinition[];

  it('un CERO publicado cuenta como publicado', () => {
    // Una empresa que no reparte declara dividendo cero: eso es un dato, no un
    // hueco. Comparar por verdad haría desaparecer la partida.
    const coverage = coreItemCoverage([statement(2024, { dividends_paid: '0' })], items, [2024]);
    expect(coverage.rows.find((r) => r.key === 'dividends_paid')?.present).toEqual([true]);
  });

  it('un `null` es ausencia en el filing', () => {
    const coverage = coreItemCoverage([statement(2024, { current_assets: null })], items, [2024]);
    expect(coverage.rows.find((r) => r.key === 'current_assets')?.present).toEqual([false]);
  });

  it('sin catálogo cae a la clave del motor y no a un hueco', () => {
    const coverage = coreItemCoverage([statement(2024)], undefined, [2024]);
    expect(coverage.rows[0]?.label).toBe('revenue');
    expect(coreItemCoverage([statement(2024)], items, [2024]).rows[0]?.label).toBe('Ingresos');
  });

  it('detecta que los estados en pantalla no son los que se juzgaron', () => {
    // Pasa al reingerir DESPUÉS de analizar: la tabla enseñaría una cobertura
    // que no produjo este veredicto.
    expect(coreItemCoverage([statement(2023), statement(2024)], items, [2023, 2024]).mismatch).toBe(
      false,
    );
    expect(coreItemCoverage([statement(2023), statement(2025)], items, [2023, 2024]).mismatch).toBe(
      true,
    );
  });

  it('sin estados no inventa filas ni declara descuadre', () => {
    const vacio = coreItemCoverage(undefined, items, [2024]);
    expect(vacio.rows).toEqual([]);
    expect(vacio.mismatch).toBe(false);
  });
});

describe('la guía del informe', () => {
  it('las etiquetas de estado se IMPORTAN de donde se pintan', () => {
    // La guía no puede tener su propio vocabulario: si `bandLabel` cambia
    // «Riesgo» por otra palabra, la guía tiene que cambiar con ella o pasa a
    // describir una pantalla que ya no existe.
    const colores = REPORT_GUIDE.find((s) => s.key === 'colors');
    expect(colores?.entries.map((e) => e.term)).toEqual(['Sano', 'Vigilar', 'Riesgo', 'Sin banda']);
  });

  it('cada sección tiene entrada y ninguna se queda sin texto', () => {
    expect(REPORT_GUIDE.length).toBeGreaterThanOrEqual(6);
    for (const section of REPORT_GUIDE) {
      expect(section.intro.length, section.key).toBeGreaterThan(60);
      expect(section.entries.length, section.key).toBeGreaterThan(0);
      for (const entry of section.entries) {
        expect(entry.term.length, `${section.key}/${entry.term}`).toBeGreaterThan(0);
        expect(entry.meaning.length, `${section.key}/${entry.term}`).toBeGreaterThan(40);
      }
    }
  });

  it('el alcance declara las cuatro cosas que el informe NO cubre', () => {
    expect(REPORT_SCOPE).toHaveLength(4);
    expect(REPORT_SCOPE.map((e) => e.term)).toContain('Valoración');
  });
});
