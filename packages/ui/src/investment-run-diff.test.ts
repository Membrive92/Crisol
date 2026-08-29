import { describe, expect, it } from 'vitest';

import type { RunDiff } from '@crisol/types';

import { diffRows } from './investment-run-diff';

/**
 * Las filas del comparador (PHASE-44.24.F).
 *
 * Lo que ordena la lista NO es la severidad de la métrica sino la DIRECCIÓN del
 * cambio: lo que ha empeorado primero, porque es lo que hace mirar esta
 * pantalla.
 */

function diff(partial: Partial<RunDiff> = {}): RunDiff {
  return {
    comparable: true,
    base_id: 'a',
    target_id: 'b',
    base_date: '2026-01-01T00:00:00Z',
    target_date: '2026-06-01T00:00:00Z',
    method_changes: [],
    years_added: [],
    years_removed: [],
    safety_before: null,
    safety_after: null,
    dividend_before: null,
    dividend_after: null,
    questions: [],
    scores: [],
    bands: [],
    flags: [],
    restatements: [],
    caveat: null,
    ...partial,
  };
}

describe('diffRows', () => {
  it('sin comparación devuelve una vista vacía, no revienta', () => {
    const view = diffRows(undefined);
    expect(view.rows).toEqual([]);
    expect(view.unchanged).toBe(false);
  });

  it('con el método cambiado NO pinta ni una fila de empresa', () => {
    // El servidor ya las vacía; esto ata que la capa de presentación tampoco
    // las reconstruya por su cuenta si algún día llegaran.
    const view = diffRows(
      diff({
        comparable: false,
        method_changes: ['el motor pasó de 1.6.0 a 1.7.0'],
        bands: [
          {
            key: 'L1',
            band_before: 'healthy',
            band_after: 'stressed',
            value_before: '2',
            value_after: '1',
          },
        ],
      }),
    );
    expect(view.rows).toEqual([]);
    expect(view.comparable).toBe(false);
    expect(view.methodChanges).toHaveLength(1);
    expect(view.unchanged).toBe(false);
  });

  it('lo que EMPEORA va primero', () => {
    const view = diffRows(
      diff({
        bands: [
          {
            key: 'mejora',
            band_before: 'stressed',
            band_after: 'healthy',
            value_before: '1',
            value_after: '2',
          },
          {
            key: 'empeora',
            band_before: 'healthy',
            band_after: 'stressed',
            value_before: '2',
            value_after: '1',
          },
        ],
      }),
    );
    expect(view.rows.map((r) => r.key)).toEqual(['b:empeora', 'b:mejora']);
    expect(view.rows[0]?.direction).toBe('worse');
  });

  it('una bandera que se ENCIENDE empeora y una que se apaga mejora', () => {
    const view = diffRows(
      diff({
        flags: [
          { key: 'apagada', label: 'Dilución', severity: 'amber', appeared: false },
          { key: 'nueva', label: 'Accruals', severity: 'red', appeared: true },
        ],
      }),
    );
    expect(view.rows.map((r) => r.direction)).toEqual(['worse', 'better']);
  });

  it('perder EVIDENCIA sin cambiar de color se cuenta como empeorar', () => {
    // Un verde auditado y un verde sin evidencia se ven igual. Si la lista los
    // trata igual, la pérdida de respaldo desaparece.
    const view = diffRows(
      diff({
        questions: [
          {
            key: 'accounting',
            verdict_before: 'healthy',
            verdict_after: 'healthy',
            evidence_before: 'evaluated',
            evidence_after: 'no-evidence',
          },
        ],
      }),
    );
    expect(view.rows).toHaveLength(1);
    expect(view.rows[0]?.direction).toBe('worse');
    expect(view.rows[0]?.label).toContain('cambió la evidencia, no el color');
    expect(view.rows[0]?.after).toContain('sin evidencia');
  });

  it('sin uno de los dos extremos NO se afirma una dirección', () => {
    // Adivinar pondría una flecha roja sobre una comparación que no se ha hecho.
    const view = diffRows(
      diff({
        bands: [
          {
            key: 'nueva',
            band_before: null,
            band_after: 'stressed',
            value_before: null,
            value_after: '1',
          },
        ],
      }),
    );
    expect(view.rows[0]?.direction).toBe('flat');
    expect(view.rows[0]?.before).toBeNull();
  });

  it('«nada ha cambiado» sólo se afirma cuando SÍ se podía comparar', () => {
    expect(diffRows(diff()).unchanged).toBe(true);
    // Con el método cambiado no hay filas, pero eso no es «nada ha cambiado»:
    // es «no se ha podido mirar». Colapsarlos sería un falso todo-bien.
    expect(diffRows(diff({ comparable: false })).unchanged).toBe(false);
  });

  it('el perfil y el dividendo se leen con su etiqueta, no con la clave', () => {
    const view = diffRows(
      diff({
        safety_before: 'conservative',
        safety_after: 'avoid',
        dividend_before: 'healthy',
        dividend_after: 'stressed',
      }),
    );
    const perfil = view.rows.find((r) => r.key === 'safety');
    expect(perfil?.before).toBe('Conservador');
    expect(perfil?.after).toBe('Evitar');
    expect(perfil?.direction).toBe('worse');
    expect(view.rows.find((r) => r.key === 'dividend')?.after).toBe('Dividendo en riesgo');
  });

  it('una reexpresión se cuenta en una frase con su ejercicio', () => {
    const view = diffRows(
      diff({
        restatements: [
          { fiscal_year: 2023, filing_a: '10-K 2023', filing_b: '10-K 2024', item_count: 3 },
        ],
      }),
    );
    expect(view.restatements[0]).toContain('2023');
    expect(view.restatements[0]).toContain('3 partidas');
  });
});
