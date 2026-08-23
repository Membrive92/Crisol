import type { CategoryKind } from '../models/category';

// `target_currency` (PHASE-8.3): convierte cada transacción a esta
// moneda con la tasa del día de su `occurred_at` antes de agregar.
// `currency` (legacy): filtra por esa moneda y agrega importes crudos.
// Si llegan ambos, gana `target_currency`.

/**
 * C4 (ciclo definido por el usuario) — `cycle=true` hace que el backend
 * bucketee y acote por el CICLO del usuario en vez de por mes natural.
 *
 * El día **nunca viaja del cliente**: lo lee el servidor de
 * `users.cycle_start_day` (`cycle=true` sin ajuste → 422). Por eso el flag es
 * un booleano pelado y no un número — un día enviado desde el cliente sería
 * una segunda fuente de verdad del mismo ajuste.
 *
 * Omitirlo deja el mes natural intacto: «Mes»/«Año» siguen respondiendo la
 * pregunta del calendario y «Mi ciclo» la de nómina-a-nómina.
 *
 * Consecuencia que gobierna al frontend: con `cycle=true`, los
 * `available_from`/`available_to` de la respuesta YA son ANCLAS DE CICLO, no
 * meses naturales (ver el clamp del `PeriodNavigator`).
 */
export interface DashboardSummaryQuery {
  currency?: string;
  target_currency?: string;
  date_from?: string;
  date_to?: string;
  cycle?: boolean;
}

export interface DashboardByCategoryQuery {
  currency?: string;
  target_currency?: string;
  date_from?: string;
  date_to?: string;
  kind?: CategoryKind;
}

export interface DashboardByMonthQuery {
  year?: number;
  currency?: string;
  target_currency?: string;
  /**
   * PHASE-41 — período custom: si vienen ambos (ISO), el backend devuelve un
   * bucket por mes del rango con los bordes PARCIALES (en vez de los 12 del
   * año), para que las barras cuadren con los KPIs de flujo del mismo rango.
   */
  date_from?: string;
  date_to?: string;
  /**
   * C4 — corta las barras por el CICLO del usuario en vez de por mes natural.
   * Con `year`, devuelve los 12 ciclos que ABREN en ese año. El día lo lee el
   * servidor del perfil; sin ajuste responde 422.
   */
  cycle?: boolean;
}

export interface DashboardTopExpensesQuery {
  currency?: string;
  target_currency?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
}

/** PHASE-25 — Query del drill-down de categoría. */
export interface DashboardCategoryDetailQuery {
  currency?: string;
  target_currency?: string;
  date_from?: string;
  date_to?: string;
  /** Cuántos meses de evolución incluir (1-36, default 12). */
  months_back?: number;
  /**
   * PHASE-47 — agrupa la serie por el mes del USUARIO en vez de por el natural.
   *
   * Sin este campo la pantalla no podía pedirlo, y el resultado era la peor
   * forma del fallo: el `TimeSelector` emitía un RANGO de ciclo mientras la
   * serie volvía en meses naturales, en la misma pantalla y sin aviso. El
   * soporte existía en el backend desde C4, con su test, e inalcanzable desde
   * la UI porque el tipo no lo declaraba.
   */
  cycle?: boolean;
}
