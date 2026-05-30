import { describe, expect, it } from 'vitest';

import {
  canStepNext,
  canStepPrev,
  clampAnchor,
  periodLabel,
  stepAnchor,
} from './debt-period';

describe('periodLabel', () => {
  it('mes → nombre + año', () => {
    expect(periodLabel('month', '2025-04')).toBe('Abril 2025');
    expect(periodLabel('month', '2025-12')).toBe('Diciembre 2025');
  });

  it('trimestre → Q + año (ignora el mes concreto dentro del trimestre)', () => {
    expect(periodLabel('quarter', '2025-04')).toBe('Q2 2025');
    expect(periodLabel('quarter', '2025-06')).toBe('Q2 2025');
    expect(periodLabel('quarter', '2025-01')).toBe('Q1 2025');
    expect(periodLabel('quarter', '2025-12')).toBe('Q4 2025');
  });

  it('año → año', () => {
    expect(periodLabel('year', '2025-07')).toBe('2025');
  });
});

describe('stepAnchor', () => {
  it('mes ±1 mes, cruzando año', () => {
    expect(stepAnchor('month', '2025-04', -1)).toBe('2025-03');
    expect(stepAnchor('month', '2025-12', 1)).toBe('2026-01');
    expect(stepAnchor('month', '2025-01', -1)).toBe('2024-12');
  });

  it('trimestre ±3 meses, snapeado al inicio del trimestre', () => {
    // Q2 (abril) → Q1 (enero) hacia atrás, Q3 (julio) hacia delante.
    expect(stepAnchor('quarter', '2025-05', -1)).toBe('2025-01');
    expect(stepAnchor('quarter', '2025-05', 1)).toBe('2025-07');
    // Q1 → Q4 del año anterior.
    expect(stepAnchor('quarter', '2025-02', -1)).toBe('2024-10');
  });

  it('año ±12 meses, snapeado a enero', () => {
    expect(stepAnchor('year', '2025-07', -1)).toBe('2024-01');
    expect(stepAnchor('year', '2025-07', 1)).toBe('2026-01');
  });
});

describe('clampAnchor', () => {
  it('sin límites, normaliza al inicio del período', () => {
    expect(clampAnchor('year', '2025-07', null, null)).toBe('2025-01');
    expect(clampAnchor('quarter', '2025-05', null, null)).toBe('2025-04');
    expect(clampAnchor('month', '2025-05', null, null)).toBe('2025-05');
  });

  it('recorta al período que contiene availableTo (límite superior)', () => {
    // year: anchor 2026 pero datos hasta 2025-05 → clamp a 2025.
    expect(clampAnchor('year', '2026-03', '2023-01', '2025-05')).toBe('2025-01');
    // month: anchor mayo-2026 pero tope marzo-2025 → marzo-2025.
    expect(clampAnchor('month', '2026-05', '2023-01', '2025-03')).toBe('2025-03');
  });

  it('recorta al período que contiene availableFrom (límite inferior)', () => {
    expect(clampAnchor('year', '2020-06', '2023-01', '2025-05')).toBe('2023-01');
    expect(clampAnchor('quarter', '2022-11', '2023-04', '2025-05')).toBe('2023-04');
  });
});

describe('canStepPrev / canStepNext', () => {
  it('sin datos (límites null) ambas deshabilitadas', () => {
    expect(canStepPrev('year', '2025-05', null)).toBe(false);
    expect(canStepNext('year', '2025-05', null)).toBe(false);
  });

  it('prev habilitado mientras haya un período anterior con datos', () => {
    expect(canStepPrev('year', '2025-05', '2023-01')).toBe(true);
    expect(canStepPrev('year', '2023-05', '2023-01')).toBe(false); // ya en el primer año
    expect(canStepPrev('month', '2025-02', '2025-01')).toBe(true);
    expect(canStepPrev('month', '2025-01', '2025-01')).toBe(false);
  });

  it('next habilitado mientras haya un período posterior con datos', () => {
    expect(canStepNext('year', '2023-05', '2025-12')).toBe(true);
    expect(canStepNext('year', '2025-05', '2025-12')).toBe(false); // ya en el último año
    expect(canStepNext('quarter', '2025-01', '2025-12')).toBe(true); // Q1 < Q4
    expect(canStepNext('quarter', '2025-11', '2025-12')).toBe(false); // ambos Q4
  });
});
