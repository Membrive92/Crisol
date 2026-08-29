import { describe, expect, it } from 'vitest';

import type { CanonicalItemDefinition, FinancialStatement, SafetyProfile } from '@crisol/types';

import { REPORT_GUIDE, REPORT_SCOPE } from './investment-report-guide';
import {
  AVOID_RULES,
  CONSERVATIVE_RULES,
  CORE_ITEMS,
  coreItemCoverage,
  DIVIDEND,
  SAFETY,
  safetyRules,
} from './investment-verdict-labels';

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

describe('safetyRules', () => {
  it('un perfil conservador cumple LAS CINCO, sin excepción', () => {
    const checklist = safetyRules(profile({ label: 'conservative' }));
    expect(checklist.conservative.rules.every((rule) => rule.met)).toBe(true);
    expect(checklist.conservative.rules).toHaveLength(CONSERVATIVE_RULES.length);
  });

  it('en «Evitar», cumplir una regla es la MALA noticia', () => {
    // `metIsBad` no es cosmético: sin él, la pantalla pintaría en verde la
    // condición que fuerza «Evitar».
    const motivo = "Z''-Score en rojo (riesgo de insolvencia)";
    const checklist = safetyRules(profile({ label: 'avoid', blocking_reasons: [motivo] }));
    expect(checklist.avoid.metIsBad).toBe(true);
    expect(checklist.avoid.rules.find((r) => r.text === motivo)?.met).toBe(true);
    expect(checklist.avoid.rules.filter((r) => r.met)).toHaveLength(1);
  });

  it('un motivo en NEGATIVO apaga su regla de Conservador', () => {
    // `blocking_reasons` de un perfil «watch» viene redactado al revés
    // («M-Score no está en verde»), así que no se puede comparar por igualdad.
    const checklist = safetyRules(
      profile({ blocking_reasons: ['M-Score no está en verde', 'F-Score es 4'] }),
    );
    const porRegla = new Map(checklist.conservative.rules.map((r) => [r.text, r.met]));
    expect(porRegla.get('M-Score en verde')).toBe(false);
    expect(porRegla.get('F-Score ≥ 7')).toBe(false);
    expect(porRegla.get('Accruals en verde')).toBe(true);
  });

  it('el rótulo de los motivos cambia con el perfil', () => {
    expect(safetyRules(profile({ label: 'avoid' })).blockingLabel).toContain('Motivos');
    expect(safetyRules(profile({ label: 'watch' })).blockingLabel).toContain('Conservador');
  });

  it('las dos listas cubren los cuatro y los cinco criterios del motor', () => {
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
