/**
 * PHASE-45 — capa PURA del panel "¿Es una amortización?".
 *
 * Aquí vive lo que las dos apps tienen que decir IGUAL: qué va a pasar con la
 * deuda, cómo se etiquetan las dos opciones y cómo se explica la sugerencia.
 * Sólo el renderizado es de cada plataforma.
 *
 * La partición va después del CONTENIDO, no antes (lección de PHASE-44.13): si
 * las frases vivieran en cada app, una podría acabar prometiendo que la deuda
 * baja por lo pagado y la otra por el capital, que es justo la distinción que
 * este panel existe para explicar.
 */

import { formatAmount } from './format';
import { withCount } from './plural';

export type AmortizationCopyMode = 'schedule' | 'movement';

export interface AmortizationEffectCopyInput {
  mode: AmortizationCopyMode;
  installmentsMarked: number;
  liabilityName: string;
  principalCovered: string;
  outstandingBefore: string;
  outstandingAfter: string;
  currency: string;
}

export interface AmortizationEffectCopy {
  /** Qué va a hacer el registro, en una frase. */
  headline: string;
  /** `warning` cuando el pago NO baja la deuda — no es un caso de error, pero
   * el usuario tiene que verlo antes de confirmar, no después. */
  tone: 'neutral' | 'warning';
  /** "Deuda: 824,77 € → 742,45 €". */
  balanceLine: string;
}

export function amortizationEffectCopy(
  input: AmortizationEffectCopyInput,
): AmortizationEffectCopy {
  const balanceLine =
    `Deuda: ${formatAmount(input.outstandingBefore, input.currency)}` +
    ` → ${formatAmount(input.outstandingAfter, input.currency)}`;

  if (input.mode === 'movement') {
    // Pagar más de lo que se debe deja la deuda en negativo. No es un error
    // (puede que falten compras por importar), pero el número se lee como un
    // fallo si nadie lo nombra antes de confirmar.
    if (Number(input.outstandingAfter) < 0) {
      return {
        headline:
          `Este importe es MAYOR que lo que debes en ${input.liabilityName}, así que la deuda ` +
          'quedaría en negativo. Suele significar que faltan compras por importar en esa ' +
          'cuenta.',
        tone: 'warning',
        balanceLine,
      };
    }
    return {
      headline: `Creará el movimiento contrario en ${input.liabilityName} por el importe entero.`,
      tone: 'neutral',
      balanceLine,
    };
  }
  if (input.installmentsMarked === 0) {
    return {
      headline:
        'Este pago no llega a completar la cuota pendiente más antigua, así que la deuda no ' +
        'bajará. Quedaría registrado, pero el saldo sigue igual.',
      tone: 'warning',
      balanceLine,
    };
  }
  return {
    headline:
      `Marcará ${withCount(input.installmentsMarked, 'cuota', 'cuotas')} del cuadro. ` +
      `La deuda baja por el capital de esas cuotas ` +
      `(${formatAmount(input.principalCovered, input.currency)}), no por lo pagado: ` +
      'los intereses no amortizan.',
    tone: 'neutral',
    balanceLine,
  };
}

/** Etiquetas de las dos opciones. Una sola redacción para las dos apps. */
export const AMORTIZATION_EXPENSE_LABEL = 'Sí, es gasto';
export const AMORTIZATION_NEUTRAL_LABEL = 'No, es neutro';

export function amortizationChoiceLabel(countsAsExpense: boolean): string {
  return countsAsExpense ? AMORTIZATION_EXPENSE_LABEL : AMORTIZATION_NEUTRAL_LABEL;
}

/**
 * El texto bajo las dos opciones.
 *
 * Cuando el usuario sigue la sugerencia se enseña el motivo a secas; cuando la
 * contradice se enseña QUÉ sugería la app y por qué, en vez de callarse — el
 * usuario manda, pero se merece saber contra qué está decidiendo.
 */
export function amortizationChoiceHint(
  chosen: boolean | null,
  suggested: boolean,
  reason: string,
): string {
  if (chosen === null || chosen === suggested) return reason;
  return `Lo cambias tú. La app sugería «${amortizationChoiceLabel(suggested)}»: ${reason}`;
}

export interface AmortizationRegisteredCopyInput {
  mode: AmortizationCopyMode;
  installmentsMarked: number;
  liabilityName: string;
}

/** Resumen de una amortización YA registrada (al reabrir el detalle). */
export function amortizationRegisteredCopy(
  input: AmortizationRegisteredCopyInput,
): string {
  const how =
    input.mode === 'schedule'
      ? ` Marcó ${withCount(input.installmentsMarked, 'cuota', 'cuotas')} del cuadro.`
      : ' La deuda bajó por el importe entero.';
  return `Este movimiento amortiza ${input.liabilityName}.${how}`;
}
