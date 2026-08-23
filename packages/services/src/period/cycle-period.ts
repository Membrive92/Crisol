/**
 * C0 (ciclo definido por el usuario) — Aritmética PURA del «mes» que define el
 * usuario, compartida por web y móvil.
 *
 * El usuario declara en Ajustes el día en que empieza su mes
 * (`users.cycle_start_day`, 1–28). El ciclo con ancla `M` (`YYYY-MM`) es el
 * intervalo semiabierto `[día D del mes M, día D del mes M+1)` — y el ancla es
 * SIEMPRE el mes que lo ABRE, no el que aporta más días.
 *
 * Tres invariantes que gobiernan todo lo de abajo:
 *
 * 1. **El intervalo del backend es CERRADO en ambos extremos**
 *    (`>= date_from AND <= date_to`, `dashboard/repository._apply_scope` y
 *    `transactions/repository`). Por eso el ciclo se emite con
 *    `toDay = día (D−1) del mes M+1` y `dateTo` a las 23:59:59, la misma
 *    convención que `boundsForCustomRange`. Emitir `date_to = D del mes M+1`
 *    contaría el primer día del ciclo siguiente DOS VECES.
 * 2. **`D = 1` degenera EXACTAMENTE en el mes natural**: para todo ancla,
 *    `cycleBoundsForAnchor(1, a)` es idéntico byte a byte a
 *    `boundsForAnchor('month', a)`. Si no lo es, la aritmética está mal
 *    (test dedicado).
 * 3. **Con `D ≤ 28` no hay clamping de fin de mes JAMÁS**. Por eso 29–31 no se
 *    ofrecen: el clamp de febrero convierte el ciclo en una charca de bugs.
 *    Aquí no hay ni una línea de clamp de día, y `isValidCycleStartDay` es el
 *    portero que lo garantiza.
 *
 * Todo es puro (sin `Date.now()`, sin reloj, sin efectos): el llamante trae el
 * ancla. Los helpers que SÍ leen el reloj viven aparte, en `day-strings.ts`.
 */

import {
  boundsForCustomRange,
  formatAnchor,
  fromIndex,
  parseAnchor,
  stepAnchor,
  toIndex,
} from './debt-period';

/** Primer día del mes admitido como inicio de ciclo. */
export const MIN_CYCLE_START_DAY = 1;
/**
 * Último día admitido. 28 y no 31: a partir de 29 el ciclo tendría que
 * "clampar" en febrero y dejaría de ser una traslación limpia del mes.
 */
export const MAX_CYCLE_START_DAY = 28;

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

function pad4(n: number): string {
  return String(n).padStart(4, '0');
}

/** `Date` (interpretada en UTC) → day-string `YYYY-MM-DD`. */
function dayString(d: Date): string {
  return `${pad4(d.getUTCFullYear())}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())}`;
}

/** Último día natural del mes `anchor` (`YYYY-MM`), como day-string. */
function lastDayOfMonth(anchor: string): string {
  const { year, month } = parseAnchor(anchor);
  // `Date.UTC(y, month, 0)`: día 0 del mes SIGUIENTE = último del actual.
  return dayString(new Date(Date.UTC(year, month, 0)));
}

/**
 * ¿Es `value` un día de inicio de ciclo válido? Entero en `[1, 28]`.
 *
 * Guarda por VERDAD y no por `!== null` a propósito (lección [PHASE-47.E]):
 * mientras exista un backend anterior a la columna, `cycle_start_day` llega
 * AUSENTE, y `undefined !== null` es cierto — el preset se ofrecería sin
 * ajuste. Aquí `undefined`, `null`, `0`, `29`, `14.5` y `'14'` son todos
 * inválidos por la misma puerta.
 */
export function isValidCycleStartDay(value: unknown): value is number {
  return (
    typeof value === 'number' &&
    Number.isInteger(value) &&
    value >= MIN_CYCLE_START_DAY &&
    value <= MAX_CYCLE_START_DAY
  );
}

/**
 * Day-strings `YYYY-MM-DD` del ciclo que ABRE en `anchor` (`YYYY-MM`):
 * `fromDay` = día `D` de `anchor`; `toDay` = día `D−1` del mes siguiente.
 *
 * El `−1` es el invariante 1 (intervalo cerrado), no un adorno. Con `D = 1`,
 * `Date.UTC(y, mesSiguiente−1, 0)` cae en el último día de `anchor`, que es
 * justo lo que hace que el ciclo degenere en el mes natural (invariante 2).
 */
export function cycleDaysForAnchor(
  cycleStartDay: number,
  anchor: string,
): { fromDay: string; toDay: string } {
  const { year, month } = parseAnchor(anchor);
  const next = fromIndex(toIndex({ year, month }) + 1);
  const fromDay = `${pad4(year)}-${pad2(month)}-${pad2(cycleStartDay)}`;
  const toDay = dayString(new Date(Date.UTC(next.year, next.month - 1, cycleStartDay - 1)));
  return { fromDay, toDay };
}

/**
 * Bounds ISO `[00:00:00Z, 23:59:59Z]` del ciclo que ABRE en `anchor`.
 *
 * Se DERIVA de `cycleDaysForAnchor` + `boundsForCustomRange`: cero duplicación
 * de aritmética. La conversión day-string → ISO ya existe y ya está probada
 * (es la del rango libre de PHASE-42); repetirla aquí sería una segunda
 * definición de la misma convención de bordes, que es exactamente lo que se
 * acaba divergiendo.
 */
export function cycleBoundsForAnchor(
  cycleStartDay: number,
  anchor: string,
): { dateFrom: string; dateTo: string } {
  const { fromDay, toDay } = cycleDaysForAnchor(cycleStartDay, anchor);
  return boundsForCustomRange(fromDay, toDay);
}

/**
 * Ancla (`YYYY-MM`) del ciclo que CONTIENE el día `day`.
 *
 * Regla única: si el día del mes es `>= D`, el ciclo lo abre ese mismo mes; si
 * no, lo abrió el mes anterior. El caso motivador de la feature: la nómina se
 * fecha el 14, así que con `D = 14` el `2026-08-14` pertenece al ciclo con
 * ancla `2026-08` — y un corte 15→15 la dejaría fuera.
 *
 * Acepta un day-string `YYYY-MM-DD` o un ISO datetime completo
 * (`2026-08-14T10:00:00.000Z`), del que toma la parte de FECHA. Lo segundo no es
 * comodidad: la pregunta natural de un llamante es «¿a qué ciclo pertenece esta
 * transacción?», y un `occurred_at` es un ISO. Antes, la `T` se colaba en el
 * `Number('14T10:00:00.000Z')` → `NaN`, y como `NaN >= D` es `false`, la
 * respuesta era el ciclo ANTERIOR: el caso motivador resuelto justo al revés, en
 * silencio y sin que el `?? 1` de al lado defendiera nada (`??` no dispara con
 * `NaN`). Un ISO se interpreta como UTC, que es la convención de estos bounds.
 *
 * Con una entrada que no sea una fecha lanza en vez de devolver un ancla
 * inventada: esta función decide en qué período cae el dinero, y un `0NaN-NaN`
 * corriente abajo es peor que un fallo ruidoso aquí.
 */
export function cycleAnchorContaining(day: string, cycleStartDay: number): string {
  const datePart = day.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(datePart)) {
    throw new Error(
      `cycleAnchorContaining: se esperaba YYYY-MM-DD o un ISO datetime, se recibió "${day}"`,
    );
  }
  const [y, m, d] = datePart.split('-').map(Number);
  const idx = toIndex({ year: y ?? 1970, month: m ?? 1 });
  return formatAnchor(fromIndex((d ?? 1) >= cycleStartDay ? idx : idx - 1));
}

/**
 * Avanza (`+1`) o retrocede (`-1`) un ciclo. Un ciclo es exactamente un mes
 * de ancla, así que reutiliza el paso mensual de `debt-period` en vez de
 * reimplementarlo.
 */
export function stepCycleAnchor(anchor: string, direction: 1 | -1): string {
  return stepAnchor('month', anchor, direction);
}

/*
 * Los bounds que llegan del backend (`available_from` / `available_to`) son
 * MESES NATURALES con datos (`get_transaction_month_bounds`, `YYYY-MM`) — no
 * ciclos. Traducirlos es la misma regla en los dos extremos: el ciclo que
 * contiene el PRIMER día con datos posible y el que contiene el ÚLTIMO.
 *
 * La asimetría aparente (abajo se retrocede un mes con `D > 1`, arriba nunca)
 * NO es una excepción: el último día de cualquier mes es 28-31, siempre
 * `>= D` porque `D <= 28`, así que el extremo superior se queda donde está por
 * aritmética, no por decisión. Escribirlo así evita tener dos reglas que
 * puedan divergir.
 */

/** Ancla del PRIMER ciclo navegable: el que contiene el día 1 de `availableFrom`. */
function firstCycleIndex(availableFrom: string, cycleStartDay: number): number {
  return toIndex(parseAnchor(cycleAnchorContaining(`${availableFrom}-01`, cycleStartDay)));
}

/** Ancla del ÚLTIMO ciclo navegable: el que contiene el último día de `availableTo`. */
function lastCycleIndex(availableTo: string, cycleStartDay: number): number {
  return toIndex(parseAnchor(cycleAnchorContaining(lastDayOfMonth(availableTo), cycleStartDay)));
}

/**
 * Recorta `anchor` al rango de ciclos con datos, derivado de los meses
 * naturales `[availableFrom, availableTo]` (ambos `YYYY-MM | null`). Sin
 * límites, devuelve el ancla tal cual.
 *
 * Con el ciclo, un ancla fuera de datos ya no es cosmética: pinta un período
 * VACÍO (con meses naturales el navegador aterrizaba, como mucho, en un mes
 * flojo).
 */
export function clampCycleAnchor(
  anchor: string,
  availableFrom: string | null,
  availableTo: string | null,
  cycleStartDay: number,
): string {
  let idx = toIndex(parseAnchor(anchor));
  // Orden igual que `clampAnchor`: el tope inferior se aplica el último, así
  // que si los límites llegan cruzados manda `availableFrom`.
  if (availableTo) idx = Math.min(idx, lastCycleIndex(availableTo, cycleStartDay));
  if (availableFrom) idx = Math.max(idx, firstCycleIndex(availableFrom, cycleStartDay));
  return formatAnchor(fromIndex(idx));
}

/** ¿Hay un ciclo anterior con datos? (flecha ◀ habilitada). */
export function canStepCyclePrev(
  anchor: string,
  availableFrom: string | null,
  cycleStartDay: number,
): boolean {
  if (!availableFrom) return false;
  return toIndex(parseAnchor(anchor)) > firstCycleIndex(availableFrom, cycleStartDay);
}

/** ¿Hay un ciclo posterior con datos? (flecha ▶ habilitada). */
export function canStepCycleNext(
  anchor: string,
  availableTo: string | null,
  cycleStartDay: number,
): boolean {
  if (!availableTo) return false;
  return toIndex(parseAnchor(anchor)) < lastCycleIndex(availableTo, cycleStartDay);
}
