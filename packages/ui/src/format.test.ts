import { describe, expect, it } from 'vitest';

import {
  formatAmount,
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

  it('respeta los decimales canónicos: JPY sin decimales', () => {
    // ISO 4217: JPY tiene 0 dígitos fraccionarios → NO debe aparecer una
    // parte decimal de 2 dígitos al final (",00" en es-ES). Comparamos
    // contra un EUR equivalente, que SÍ la lleva, para no depender del
    // separador de millares ni del símbolo del build ICU de Node.
    const jpy = formatAmount('1234', 'JPY', 'es-ES');
    const eur = formatAmount('1234', 'EUR', 'es-ES');
    expect(jpy).not.toMatch(/,00/);
    expect(eur).toMatch(/,00/);
  });

  it('mantiene 2 decimales con coma para EUR (es-ES)', () => {
    // EUR conserva 2 decimales con coma decimal es-ES.
    expect(formatAmount('1234.5', 'EUR', 'es-ES')).toMatch(/,50/);
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
