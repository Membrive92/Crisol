/**
 * PHASE-47.H (UI) — el signo con el que una fila cuenta en su categoría.
 *
 * El invariante que defienden estos tests no es «pinta un menos»: es que la
 * columna de importes SUME el total que preside la pantalla. Mientras el
 * importe viajaba sin dirección, «Suscripciones» de julio pintaba seis filas
 * que sumaban 187,95 € bajo un total de 184,95 €, y la diferencia —un
 * reembolso de Netflix de 1,50 €— no era identificable desde la pantalla.
 */

import { describe, expect, it } from 'vitest';

import { categoryRowAmount, isRefundInExpenseList, isRefundRow } from './refund-sign';

describe('isRefundRow', () => {
  it('una entrada en una categoría de gasto es una devolución', () => {
    expect(isRefundRow('IN', 'expense')).toBe(true);
  });

  it('una salida en una categoría de gasto es un gasto normal', () => {
    expect(isRefundRow('OUT', 'expense')).toBe(false);
  });

  it('una entrada en una categoría de ingreso es un ingreso, no una devolución', () => {
    // La nómina. Marcarla restaría el ingreso de su propia categoría.
    expect(isRefundRow('IN', 'income')).toBe(false);
  });

  it('sin dirección probada no se adivina desde la categoría', () => {
    // Igual que el backend: `_is_refund` exige `flow` explícito. Una fila
    // heredada sin flow cuenta como gasto normal en su categoría.
    expect(isRefundRow(null, 'expense')).toBe(false);
  });

  it('un servidor que todavía no manda el campo no marca NADA', () => {
    // [PHASE-47.E] `campo !== null` habría marcado TODAS las filas cuando el
    // backend en marcha es anterior a la columna: `undefined !== null`. Este
    // caso se escribe OMITIENDO el valor, no poniéndolo a null.
    const fila: { amount: string; flow?: 'IN' | 'OUT' } = { amount: '10.00' };
    expect(isRefundRow(fila.flow, 'expense')).toBe(false);
    expect(categoryRowAmount(fila.amount, fila.flow, 'expense')).toBe('10.00');
  });

  it('sin kind de categoría tampoco marca', () => {
    expect(isRefundRow('IN', null)).toBe(false);
    expect(isRefundRow('IN', undefined)).toBe(false);
  });

  it('las transferencias nunca son devoluciones', () => {
    expect(isRefundRow('TRANSFER_IN', 'expense')).toBe(false);
    expect(isRefundRow('TRANSFER_OUT', 'expense')).toBe(false);
  });
});

describe('isRefundInExpenseList', () => {
  it('en una lista acotada al cubo de gasto, una entrada es una devolución', () => {
    // `/dashboard/top-expenses` filtra por `_is_expense()`, que INCLUYE las
    // devoluciones; el item no trae el kind de su categoría.
    expect(isRefundInExpenseList('IN')).toBe(true);
    expect(isRefundInExpenseList('OUT')).toBe(false);
    expect(isRefundInExpenseList(undefined)).toBe(false);
  });
});

describe('categoryRowAmount', () => {
  it('niega el importe de una devolución', () => {
    expect(categoryRowAmount('1.50', 'IN', 'expense')).toBe('-1.50');
  });

  it('deja intacto todo lo demás', () => {
    expect(categoryRowAmount('134.99', 'OUT', 'expense')).toBe('134.99');
    expect(categoryRowAmount('2520.68', 'IN', 'income')).toBe('2520.68');
  });

  it('no introduce redondeo de coma flotante', () => {
    // Se manipula la cadena a propósito: `-Number('0.1')` produce importes que
    // luego no suman el total al céntimo.
    expect(categoryRowAmount('0.10', 'IN', 'expense')).toBe('-0.10');
    expect(categoryRowAmount('1234567.89', 'IN', 'expense')).toBe('-1234567.89');
  });

  it('es idempotente sobre un importe que ya viene negativo', () => {
    // Hoy el backend manda el importe sin signo, pero si algún día lo mandara
    // firmado, anteponer otro `-` daría `--1.50` y `formatAmount` lo devolvería
    // crudo (`Number('--1.50')` es NaN).
    expect(categoryRowAmount('-1.50', 'IN', 'expense')).toBe('1.50');
  });

  it('la columna suma el total de la pantalla', () => {
    // Los datos reales de «Suscripciones» en el periodo del usuario (12-jul a
    // 11-ago de 2026), donde se vio el defecto.
    const filas = [
      { amount: '134.99', flow: 'OUT' as const },
      { amount: '20.99', flow: 'OUT' as const },
      { amount: '14.99', flow: 'OUT' as const },
      { amount: '9.99', flow: 'OUT' as const },
      { amount: '5.49', flow: 'OUT' as const },
      { amount: '1.50', flow: 'IN' as const },
    ];
    const enCentimos = filas
      .map((f) => Math.round(Number(categoryRowAmount(f.amount, f.flow, 'expense')) * 100))
      .reduce((a, b) => a + b, 0);
    expect(enCentimos).toBe(18495);
    // Y sin el signo, lo que el usuario tenía delante: 3,00 € de más.
    const sinSigno = filas
      .map((f) => Math.round(Number(f.amount) * 100))
      .reduce((a, b) => a + b, 0);
    expect(sinSigno).toBe(18795);
  });
});
