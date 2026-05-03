import { describe, expect, it } from 'vitest';

import {
  convertAmount,
  formatAmount,
  formatConverted,
  formatDate,
  formatMonthLabel,
  fromDateInputValue,
  toDateInputValue,
} from './format';

describe('formatAmount', () => {
  it('formatea enteros con 2 decimales', () => {
    expect(formatAmount('10')).toMatch(/10,00/);
  });

  it('respeta la moneda', () => {
    const result = formatAmount('10.50', 'USD', 'en-US');
    expect(result).toContain('$');
    expect(result).toContain('10.50');
  });

  it('devuelve la cadena original si no es numérica', () => {
    expect(formatAmount('abc')).toBe('abc');
  });
});

describe('formatDate', () => {
  it('formatea ISO → DD/MM/YYYY', () => {
    expect(formatDate('2026-04-16T10:30:00Z')).toMatch(/16\/04\/2026/);
  });

  it('devuelve la cadena si no es parseable', () => {
    expect(formatDate('not-a-date')).toBe('not-a-date');
  });
});

describe('toDateInputValue', () => {
  it('convierte ISO a YYYY-MM-DD', () => {
    const iso = new Date('2026-04-16T12:00:00Z').toISOString();
    const result = toDateInputValue(iso);
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('devuelve cadena vacía si no es parseable', () => {
    expect(toDateInputValue('not-a-date')).toBe('');
  });
});

describe('fromDateInputValue', () => {
  it('añade hora UTC 00:00 al valor YYYY-MM-DD', () => {
    const iso = fromDateInputValue('2026-04-16');
    expect(iso).toBe('2026-04-16T00:00:00.000Z');
  });

  it('devuelve un ISO válido si el input está vacío', () => {
    const iso = fromDateInputValue('');
    expect(new Date(iso).toString()).not.toBe('Invalid Date');
  });
});

describe('formatMonthLabel', () => {
  it('convierte YYYY-MM a una etiqueta legible capitalizada', () => {
    const result = formatMonthLabel('2026-04', 'es-ES');
    expect(result).toMatch(/^[A-Z]/);
    expect(result).toContain('2026');
  });

  it('devuelve el valor original si el formato no coincide', () => {
    expect(formatMonthLabel('not-a-month')).toBe('not-a-month');
  });

  it('soporta locales distintos', () => {
    const result = formatMonthLabel('2026-01', 'en-US');
    expect(result).toMatch(/Jan/i);
  });
});

describe('convertAmount', () => {
  const rates = { USD: 1.1, GBP: 0.85, JPY: 165 };

  it('devuelve igual cuando from === to', () => {
    const r = convertAmount(100, 'EUR', 'EUR', rates);
    expect(r).toEqual({ value: 100, rate: 1, missing: false });
  });

  it('convierte EUR → quote directo', () => {
    const r = convertAmount(100, 'EUR', 'USD', rates);
    expect(r.value).toBeCloseTo(110, 6);
    expect(r.rate).toBeCloseTo(1.1, 6);
    expect(r.missing).toBe(false);
  });

  it('invierte cuando to === EUR', () => {
    const r = convertAmount(110, 'USD', 'EUR', rates);
    expect(r.value).toBeCloseTo(100, 6);
    expect(r.rate).toBeCloseTo(1 / 1.1, 6);
  });

  it('compone non-EUR vía EUR', () => {
    const r = convertAmount(110, 'USD', 'GBP', rates);
    // 110 USD / 1.1 = 100 EUR ; 100 × 0.85 = 85 GBP
    expect(r.value).toBeCloseTo(85, 6);
  });

  it('marca missing cuando falta una pata', () => {
    const r = convertAmount(100, 'USD', 'CHF', rates);
    expect(r.missing).toBe(true);
    expect(r.value).toBe(100);
    expect(r.rate).toBe(1);
  });

  it('respeta NaN', () => {
    const r = convertAmount(Number.NaN, 'EUR', 'USD', rates);
    expect(r.missing).toBe(true);
  });
});

describe('formatConverted', () => {
  const rates = { USD: 1.1 };

  it('mismo currency: sin prefijo ni tooltip', () => {
    const r = formatConverted('100', 'EUR', 'EUR', rates);
    expect(r.isApprox).toBe(false);
    expect(r.isMissing).toBe(false);
    expect(r.tooltip).toBe('');
    expect(r.display).not.toMatch(/≈/);
  });

  it('conversión real: prefijo ≈ + tooltip', () => {
    const r = formatConverted('100', 'EUR', 'USD', rates);
    expect(r.isApprox).toBe(true);
    expect(r.display.startsWith('≈')).toBe(true);
    expect(r.display).toContain('110');
    expect(r.tooltip).toMatch(/100,00/);
    expect(r.tooltip).toContain('1.1');
    expect(r.tooltip).toContain('USD/EUR');
  });

  it('sin tasa: muestra original + flag missing', () => {
    const r = formatConverted('100', 'JPY', 'GBP', { USD: 1.1 });
    expect(r.isMissing).toBe(true);
    expect(r.isApprox).toBe(false);
    expect(r.display).not.toMatch(/≈/);
    expect(r.tooltip).toMatch(/Sin tasa/);
  });

  it('amount no numérico: missing pero devuelve string original', () => {
    const r = formatConverted('abc', 'EUR', 'USD', rates);
    expect(r.isMissing).toBe(true);
    expect(r.display).toBe('abc');
  });

  it('incluye la fecha en el tooltip cuando se pasa rateDate', () => {
    const r = formatConverted('100', 'EUR', 'USD', rates, undefined, '2026-04-15');
    expect(r.tooltip).toContain('el 2026-04-15');
  });
});
