import { describe, expect, it } from 'vitest';

import {
  amortizationChoiceHint,
  amortizationEffectCopy,
  amortizationRegisteredCopy,
} from './amortization-copy';

const BASE = {
  liabilityName: 'Tarjeta BBVA',
  principalCovered: '82.32',
  outstandingBefore: '1000.00',
  outstandingAfter: '917.68',
  currency: 'EUR',
};

describe('amortizationEffectCopy', () => {
  it('con cuadro dice que la deuda baja por el CAPITAL, no por lo pagado', () => {
    const copy = amortizationEffectCopy({
      ...BASE,
      mode: 'schedule',
      installmentsMarked: 1,
    });
    // La distinción que este panel existe para explicar: si desaparece de la
    // frase, el usuario lee "pagué 232 € luego debo 232 € menos" y no cuadra.
    expect(copy.headline).toContain('capital');
    expect(copy.headline).toContain('los intereses no amortizan');
    expect(copy.headline).toContain('1 cuota');
    expect(copy.tone).toBe('neutral');
  });

  it('pluraliza las cuotas', () => {
    const copy = amortizationEffectCopy({
      ...BASE,
      mode: 'schedule',
      installmentsMarked: 3,
    });
    expect(copy.headline).toContain('3 cuotas');
  });

  it('avisa (tone warning) cuando el pago no cubre ninguna cuota', () => {
    const copy = amortizationEffectCopy({
      ...BASE,
      mode: 'schedule',
      installmentsMarked: 0,
      principalCovered: '0.00',
      outstandingAfter: '1000.00',
    });
    expect(copy.tone).toBe('warning');
    expect(copy.headline).toContain('no bajará');
  });

  it('avisa si el pago deja la deuda en negativo, en vez de enseñar un número raro', () => {
    const copy = amortizationEffectCopy({
      ...BASE,
      mode: 'movement',
      installmentsMarked: 0,
      outstandingBefore: '600.00',
      outstandingAfter: '-499.64',
      principalCovered: '1099.64',
    });
    expect(copy.tone).toBe('warning');
    expect(copy.headline).toContain('negativo');
    expect(copy.headline).toContain('faltan compras por importar');
  });

  it('sin cuadro habla del movimiento contrario, no de cuotas', () => {
    const copy = amortizationEffectCopy({
      ...BASE,
      mode: 'movement',
      installmentsMarked: 0,
    });
    expect(copy.headline).toContain('Tarjeta BBVA');
    expect(copy.headline).not.toContain('cuota');
    expect(copy.tone).toBe('neutral');
  });

  it('la línea de saldo lleva las dos cifras formateadas', () => {
    const copy = amortizationEffectCopy({
      ...BASE,
      mode: 'movement',
      installmentsMarked: 0,
    });
    expect(copy.balanceLine).toContain('→');
    // Formato es-ES: coma decimal y símbolo, no "1000.00".
    expect(copy.balanceLine).not.toContain('1000.00');
  });
});

describe('amortizationChoiceHint', () => {
  const reason = 'Esta deuda tiene cuadro de cuotas.';

  it('siguiendo la sugerencia enseña el motivo a secas', () => {
    expect(amortizationChoiceHint(true, true, reason)).toBe(reason);
    expect(amortizationChoiceHint(null, true, reason)).toBe(reason);
  });

  it('contradiciéndola dice qué sugería la app, sin callárselo', () => {
    const hint = amortizationChoiceHint(false, true, reason);
    expect(hint).toContain('sugería');
    expect(hint).toContain('Sí, es gasto');
    expect(hint).toContain(reason);
  });
});

describe('amortizationRegisteredCopy', () => {
  it('con cuadro nombra las cuotas marcadas', () => {
    expect(
      amortizationRegisteredCopy({
        mode: 'schedule',
        installmentsMarked: 2,
        liabilityName: 'Prestamo',
      }),
    ).toBe('Este movimiento amortiza Prestamo. Marcó 2 cuotas del cuadro.');
  });

  it('sin cuadro dice que bajó por el importe entero', () => {
    expect(
      amortizationRegisteredCopy({
        mode: 'movement',
        installmentsMarked: 0,
        liabilityName: 'Tarjeta BBVA',
      }),
    ).toBe('Este movimiento amortiza Tarjeta BBVA. La deuda bajó por el importe entero.');
  });
});
