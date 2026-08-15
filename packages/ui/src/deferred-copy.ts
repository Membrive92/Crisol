/**
 * PHASE-47.E2/E3 — Cómo se cuenta un gasto aplazado.
 *
 * Cuando el banco financia el recibo de una tarjeta, las compras de ese ciclo
 * se hicieron pero el dinero no salió: sale como cuota, durante los años
 * siguientes. De ahí las dos lecturas — el resultado del mes las excluye
 * (mide caja) y el desglose por categorías las mantiene (mide gasto).
 *
 * Consecuencia deliberada: los meses con aplazamiento las dos cifras dejan de
 * cuadrar. Este módulo existe para que la pantalla lo DIGA. Es puro y vive en
 * `@crisol/ui` para que web y móvil no acaben con dos redacciones distintas de
 * la misma explicación, que es como se separan dos pantallas que deberían
 * decir lo mismo (lección PHASE-44.13).
 */

import { formatAmount } from './format';

/**
 * El aviso que acompaña al desglose por categorías cuando parte del gasto está
 * aplazado. `null` cuando no hay nada aplazado — el caso de casi todos los
 * meses — para que la pantalla no pinte una fila vacía.
 *
 * @param deferred Importe aplazado del periodo (serializado, como llega del API).
 * @param currency ISO 4217 en el que se están mostrando los importes.
 */
export function deferredBreakdownNotice(
  deferred: string | null | undefined,
  currency: string,
): string | null {
  const amount = Number(deferred ?? 0);
  if (!Number.isFinite(amount) || amount <= 0) return null;
  return `De este gasto, ${formatAmount(String(amount), currency)} están aplazados: los compraste en este periodo, pero el banco financió el recibo y no salieron de tu cuenta. Por eso el resultado del mes no los cuenta.`;
}

/**
 * El texto del asterisco de una compra concreta, para el hover de la fila.
 *
 * Se nombra el pasivo porque es lo que el usuario reconoce («Recibo junio
 * aplazado»), y se dice explícitamente que el gasto SÍ cuenta en su categoría:
 * sin esa frase, la marca se lee como «esto no cuenta», que es justo lo que no
 * queremos que entienda.
 */
export function deferredPurchaseNotice(liabilityName: string | null | undefined): string {
  const name = liabilityName?.trim();
  return name
    ? `Forma parte de «${name}», un recibo que aplazaste. El gasto cuenta en su categoría, pero no salió de tu cuenta este mes: lo pagas en cuotas.`
    : 'Forma parte de un recibo que aplazaste. El gasto cuenta en su categoría, pero no salió de tu cuenta este mes: lo pagas en cuotas.';
}
