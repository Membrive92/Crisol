/**
 * PHASE-47.E2/E3 — El aviso que impide que la pantalla mienta por omisión.
 *
 * Los meses con aplazamiento, el resultado del mes y la suma del desglose no
 * cuadran a propósito. Si nadie dice por qué, quien intente cuadrarlos a mano
 * concluirá que la app está mal — que es peor que no enseñar el número.
 */

import { describe, expect, it } from 'vitest';

import { deferredBreakdownNotice, deferredPurchaseNotice } from './deferred-copy';

describe('deferredBreakdownNotice', () => {
  it('no dice nada cuando no hay nada aplazado', () => {
    // El caso de casi todos los meses: sin esto la pantalla pintaría una fila
    // vacía debajo del desglose, todo el rato.
    expect(deferredBreakdownNotice('0', 'EUR')).toBeNull();
    expect(deferredBreakdownNotice(null, 'EUR')).toBeNull();
    expect(deferredBreakdownNotice(undefined, 'EUR')).toBeNull();
  });

  it('nombra el importe y explica por qué el resultado del mes no lo cuenta', () => {
    const notice = deferredBreakdownNotice('700.26', 'EUR');

    expect(notice).toContain('700,26');
    // Las dos mitades de la explicación: que el gasto se hizo y que el dinero
    // no salió. Sin la segunda, el número parece un error.
    expect(notice).toContain('no salieron de tu cuenta');
    expect(notice).toContain('resultado del mes');
  });

  it('ignora un importe que no es un número en vez de pintar NaN', () => {
    // Un `NaN €` en pantalla acusa a los datos del usuario de un problema que
    // no tienen (lección PHASE-44.16).
    expect(deferredBreakdownNotice('no-soy-un-numero', 'EUR')).toBeNull();
  });
});

describe('deferredPurchaseNotice', () => {
  it('dice que el gasto SÍ cuenta en su categoría', () => {
    // Es la frase que evita el malentendido: la marca no significa «esto no
    // cuenta», significa «esto no ha salido todavía».
    expect(deferredPurchaseNotice('Recibo junio aplazado')).toContain(
      'cuenta en su categoría',
    );
    expect(deferredPurchaseNotice('Recibo junio aplazado')).toContain(
      'Recibo junio aplazado',
    );
  });

  it('sigue explicándose sin nombre del pasivo', () => {
    const notice = deferredPurchaseNotice(null);

    expect(notice).toContain('cuenta en su categoría');
    expect(notice).not.toContain('«»');
  });
});
