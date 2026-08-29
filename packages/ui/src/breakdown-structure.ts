/**
 * El reparto fijo/variable del desglose por categorías — la parte PURA.
 *
 * Vivía duplicada palabra por palabra en `apps/web` y `apps/mobile`. Mientras
 * las dos copias sólo repartían el total daba igual; en cuanto hubo que
 * repartir también **lo aplazado** (PHASE-47.E4) pasó a ser el mecanismo por
 * el que dos pantallas que deben decir lo mismo dejan de hacerlo — la lección
 * [PHASE-44.13]: compartir el cálculo no basta si cada app se guarda su copia.
 *
 * Lógica pura, sin dependencias de plataforma (ADR 0001). Los tipos se
 * declaran aquí en su forma estructural mínima para no crear la dependencia
 * circular con `@crisol/types` que prohíbe el ADR.
 */

/** La forma de una fila del desglose que a este módulo le importa. */
export interface BreakdownRow {
  category_id: string | null;
  category_name: string;
  category_kind: 'income' | 'expense' | null;
  category_color: string | null;
  category_icon: string | null;
  total: string;
  count: number;
  deferred_total?: string | null | undefined;
}

/** La forma de una fila de «gasto puntual por categoría». */
export interface ExceptionalRow {
  category_id: string | null;
  category_name: string | null;
  color: string | null;
  icon: string | null;
  total: string;
  deferred_total?: string | null | undefined;
}

/** Clave estable de agrupación: el bucket «sin categoría» tiene `id = null`. */
function categoryKey(id: string | null): string {
  return id ?? '_none';
}

/** Una fila de gasto puntual, en la forma que pinta el desglose. */
export function toBreakdownRow(c: ExceptionalRow): BreakdownRow {
  return {
    category_id: c.category_id,
    category_name: c.category_name ?? 'Sin categoría',
    category_kind: 'expense',
    category_color: c.color,
    category_icon: c.icon,
    total: c.total,
    count: 0,
    // PHASE-47.E4 — lo aplazado viaja con la fila para que el aviso pueda
    // derivarse de lo que se está MOSTRANDO, también bajo el filtro.
    deferred_total: c.deferred_total,
  };
}

/**
 * Estructural por categoría = total − puntual (descarta lo que queda ~0).
 *
 * Lo aplazado se parte por la MISMA resta. Si la fila no declara el campo
 * —backend anterior— se propaga la AUSENCIA y no un cero: `deferredInView`
 * distingue las dos cosas, y un cero afirmaría que aquí no hay nada aplazado.
 * El `max(0, …)` es una guarda de aritmética, no una regla: la parte no puede
 * salir negativa aunque el reparto llegue descuadrado.
 */
export function deriveStructural(
  all: readonly BreakdownRow[],
  exceptional: readonly ExceptionalRow[],
): BreakdownRow[] {
  const excByKey = new Map<string, ExceptionalRow>();
  for (const e of exceptional) excByKey.set(categoryKey(e.category_id), e);
  const out: BreakdownRow[] = [];
  for (const it of all) {
    const exc = excByKey.get(categoryKey(it.category_id));
    const structural = Number(it.total) - Number(exc?.total ?? 0);
    if (structural <= 0.005) continue;
    const deferred =
      it.deferred_total == null
        ? it.deferred_total
        : Math.max(0, Number(it.deferred_total) - Number(exc?.deferred_total ?? 0)).toFixed(2);
    out.push({ ...it, total: structural.toFixed(2), deferred_total: deferred });
  }
  return out;
}
