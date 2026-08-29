/**
 * PHASE-47.H (UI) — el signo con el que una fila cuenta EN SU CATEGORÍA.
 *
 * Gemelo de `expense_amount_expr` / `_is_refund` del backend
 * (`dashboard/repository.py`). Una devolución es una entrada (`flow=IN`) en
 * una categoría de GASTO, y **resta** de su propia categoría. El backend ya
 * lo suma así desde PHASE-47.H, pero el importe viaja SIN signo —es el que
 * ordena el ranking—, así que la lista pintaba seis importes positivos cuya
 * suma no daba el total de arriba y no había forma de saber qué fila lo
 * explicaba: la de julio sumaba 187,95 € bajo un total de 184,95 €, y la
 * diferencia era un reembolso de Netflix de 1,50 € contado dos veces (una de
 * más arriba, otra de menos abajo).
 *
 * **Y NO contradice la lista de transacciones**, aunque el mismo movimiento
 * salga ahí con un `+` y aquí con un `−`. Son dos preguntas distintas: la lista
 * es el libro de caja de una cuenta —ese dinero ENTRÓ, y así cuenta en el
 * saldo— y esto es cuánto pesa la fila DENTRO de su categoría, donde deshace
 * una compra. Las dos derivan del mismo `flow`; lo que cambia es la pregunta.
 * Unificarlas movería el saldo, que es lo único que en esta app no puede
 * moverse por una cuestión de etiquetas.
 *
 * Lógica pura, sin dependencias de plataforma (ADR 0001). Acepta `string`
 * para el kind en vez de `CategoryKind` por la misma razón que
 * `formatCategoryKind`: evitar la dependencia circular con `@crisol/types`.
 */

/** Dirección del movimiento tal y como la publica la API (`transactions.flow`). */
export type RowFlow = 'IN' | 'OUT' | 'TRANSFER_IN' | 'TRANSFER_OUT';

/**
 * ¿Esta fila es una DEVOLUCIÓN dentro de su categoría?
 *
 * Sólo con `flow` explícito, igual que el backend: una fila heredada sin
 * dirección probada no se adivina desde la categoría.
 *
 * La comprobación es por VERDAD y no contra `null` a propósito ([PHASE-47.E]):
 * un servidor anterior a este campo no lo manda, y `undefined !== null` habría
 * marcado todas las filas.
 */
export function isRefundRow(
  flow: RowFlow | null | undefined,
  categoryKind: string | null | undefined,
): boolean {
  return flow === 'IN' && categoryKind === 'expense';
}

/**
 * Igual que `isRefundRow` para listas que YA vienen acotadas al cubo de gasto
 * — hoy `/dashboard/top-expenses`, que filtra por `_is_expense()` y por tanto
 * incluye las devoluciones. Ahí una fila con `flow=IN` es una devolución por
 * construcción, y el item no trae el `kind` de su categoría.
 */
export function isRefundInExpenseList(flow: RowFlow | null | undefined): boolean {
  return isRefundRow(flow, 'expense');
}

/**
 * El importe de la fila con el signo con el que cuenta en su categoría.
 *
 * Devuelve el mismo `string` decimal que llegó, con un `-` delante cuando es
 * devolución. Se manipula la cadena en vez de parsear a `number` para no meter
 * un redondeo de coma flotante en un importe que después se formatea: la
 * columna tiene que sumar EXACTAMENTE el total que preside la pantalla.
 */
export function categoryRowAmount(
  amount: string,
  flow: RowFlow | null | undefined,
  categoryKind: string | null | undefined,
): string {
  if (!isRefundRow(flow, categoryKind)) return amount;
  const trimmed = amount.trim();
  return trimmed.startsWith('-') ? trimmed.slice(1) : `-${trimmed}`;
}
