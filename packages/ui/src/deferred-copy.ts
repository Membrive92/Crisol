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
 * Lo aplazado de las filas que se están MOSTRANDO.
 *
 * PHASE-47.E4. El aviso citaba el total del periodo, que es correcto sin
 * filtro y **falso en cuanto el usuario pulsa Fijo o Variable**: en junio de
 * 2026 decía «496,67 € aplazados» mientras la vista de Fijo sólo contenía
 * 245,53 € de ellos (los otros 251,14 € viven en categorías variables — Ropa y
 * Juegos). Derivarlo de las filas visibles hace que el número no pueda
 * describir otra cosa que lo que hay en pantalla.
 *
 * Devuelve `null` cuando NINGUNA fila declara el campo: eso es un backend
 * anterior a `deferred_total`, y sumar cero anunciaría «no hay nada aplazado»
 * —una afirmación— en vez de callar. Comprobación por VERDAD y no contra
 * `null`, por la misma razón que el asterisco de la lista de transacciones.
 */
export function deferredInView(
  rows: readonly { deferred_total?: string | null | undefined }[],
): string | null {
  let alguna = false;
  let centimos = 0;
  for (const r of rows) {
    if (r.deferred_total == null) continue;
    const n = Number(r.deferred_total);
    if (!Number.isFinite(n)) continue;
    alguna = true;
    centimos += Math.round(n * 100);
  }
  if (!alguna) return null;
  return (centimos / 100).toFixed(2);
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

/**
 * El texto del asterisco de una CATEGORÍA del desglose, para el hover.
 *
 * Dice el importe porque la fila enseña el total y el usuario necesita saber
 * qué parte de él no salió de su cuenta — sin eso, la marca sólo plantea la
 * pregunta.
 */
export function deferredCategoryNotice(deferred: string, currency: string): string {
  return `${formatAmount(deferred, currency)} de esta categoría están aplazados: los compraste en el periodo, pero salen de tu cuenta como cuotas del recibo financiado.`;
}
