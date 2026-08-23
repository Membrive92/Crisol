/**
 * C0 (ciclo definido por el usuario) — Helpers de day-string `YYYY-MM-DD` para
 * los selectores de período, subidos desde
 * `apps/web/components/ui/date-picker.tsx` porque móvil los necesita para
 * clampar y no los tenía (su navegador de período no clampa nada hoy).
 *
 * ⚠️ Fichero SEPARADO de `calendar-period.ts` / `cycle-period.ts` a propósito:
 * aquellos son PUROS (el llamante trae el ancla; se pueden probar sin tocar el
 * reloj) y aquí conviven funciones que LEEN EL RELOJ. Mezclarlas haría que un
 * test de aritmética dependiera de la fecha en que se ejecuta, que es la bomba
 * de relojería de [AUDIT-2026-08].
 *
 * Reparto explícito:
 * - PURA: `dataMinDayStr`.
 * - IMPURAS (leen `new Date()`): `todayDayStr`, `dataMaxDayStr` (usa
 *   `todayDayStr`) y `currentMonthAnchor`.
 *
 * Las tres impuras responden «¿qué día/mes es hoy PARA EL USUARIO?» y por eso
 * las tres leen el reloj en hora LOCAL. No confundir con los BOUNDS de consulta
 * (`calendar-period.ts`, `cycle-period.ts`), que son UTC porque así corta el
 * backend: una cosa es dónde parte el mes y otra en qué mes vive el usuario.
 */

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

function pad4(n: number): string {
  return String(n).padStart(4, '0');
}

/* ---------- PURAS ---------- */

/**
 * Primer día SELECCIONABLE: inicio del primer mes con datos (`availableFrom`,
 * `YYYY-MM`). Sin datos → `null` (sin tope inferior).
 */
export function dataMinDayStr(availableFrom: string | null | undefined): string | null {
  return availableFrom ? `${availableFrom}-01` : null;
}

/* ---------- IMPURAS (leen el reloj) ---------- */

/**
 * IMPURA — Día de HOY como `YYYY-MM-DD` en hora LOCAL. Exportada para que
 * otros controles (navegador de período, seeds de rango) usen el mismo tope y
 * no dejen elegir fechas futuras.
 *
 * Local y no UTC a propósito: es el "hoy" que el usuario ve en su calendario,
 * y su único uso es marcar/limitar días en un date-picker. Los BOUNDS de
 * consulta sí son UTC (`calendar-period.ts`, `cycle-period.ts`), que es como
 * corta el backend.
 */
export function todayDayStr(): string {
  const now = new Date();
  return `${pad4(now.getFullYear())}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
}

/**
 * IMPURA (vía `todayDayStr`) — Último día SELECCIONABLE del rango
 * personalizado: fin del último mes con datos (`availableTo`, `YYYY-MM`),
 * nunca posterior a hoy. Sin datos → hoy. Así el calendario no deja elegir
 * días sin datos (p. ej. el mes en curso aún sin importar).
 */
export function dataMaxDayStr(availableTo: string | null | undefined): string {
  const today = todayDayStr();
  if (!availableTo) return today;
  const [y, m] = availableTo.split('-').map(Number);
  const lastDay = new Date(Date.UTC(y ?? 1970, m ?? 1, 0)).getUTCDate();
  const endOfMonth = `${availableTo}-${pad2(lastDay)}`;
  return endOfMonth < today ? endOfMonth : today;
}

/**
 * IMPURA — Ancla `YYYY-MM` del mes EN CURSO, en hora LOCAL.
 *
 * Existe para las pantallas que hoy no guardan ancla (el Análisis de móvil) y
 * llamaban a un `rangeForPeriod()` que leía el reloj por dentro. Aquí el reloj
 * se lee UNA vez, en el llamante, y la aritmética que recibe el ancla sigue
 * siendo pura.
 *
 * LOCAL, y esto NO es una inconsistencia con los bounds: son dos preguntas
 * distintas. «¿Dónde corta el mes?» es una convención de datos y se responde en
 * UTC, como corta el backend (`calendar-period.ts`, `cycle-period.ts`). «¿Qué
 * mes es el actual?» es una pregunta del calendario del USUARIO: el 1 de
 * septiembre a las 00:30 en Madrid, su mes es septiembre aunque en UTC aún sea
 * 31 de agosto. Devolverlo en UTC hacía que dos dispositivos del mismo usuario
 * abrieran en meses DISTINTOS en esa franja, y dejaba esta función en
 * desacuerdo con todo el resto de la app (`debt/index.tsx`,
 * `schedule-condensed.tsx`, `debt-monthly-evolution.tsx`, los forms de
 * presupuesto), que siempre ha resuelto el "hoy" en local — igual que
 * `todayDayStr`, tres funciones más arriba, con la que ahora sí concuerda.
 */
export function currentMonthAnchor(): string {
  const now = new Date();
  return `${pad4(now.getFullYear())}-${pad2(now.getMonth() + 1)}`;
}
