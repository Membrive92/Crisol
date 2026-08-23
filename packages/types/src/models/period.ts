/**
 * C0 (ciclo definido por el usuario) — Vocabulario ÚNICO de los selectores de
 * período de la app.
 *
 * Hasta C0 este tipo estaba declarado DOS VECES, una por app
 * (`apps/web/components/analysis/stitch-period-toggle.tsx` y
 * `apps/mobile/components/dashboard/period-toggle.tsx`). Ambos toggles lo
 * importan ahora de aquí y lo reexportan, para no romper los imports de sus
 * consumidores. Es la lección [PHASE-44.13] aplicada al vocabulario: compartir
 * el cálculo no basta si cada app se guarda su propia lista.
 *
 * Los tres valores NO son intercambiables:
 *
 * - `month` — EL MES DEL USUARIO. Por defecto el natural (del 1 al último),
 *   y si ha declarado un día de inicio (`users.cycle_start_day`), del día D al
 *   D−1 del siguiente. Es la misma pregunta —«¿qué llevo este mes?»— con dos
 *   aritméticas: `boundsForAnchor` cuando no hay día, `cycleBoundsForAnchor`
 *   cuando lo hay.
 * - `year` — período de CALENDARIO, navega por ancla `YYYY-MM`.
 * - `custom` — rango libre `from/to` (PHASE-42). No navega: sin ancla y sin
 *   flechas; su aritmética es `boundsForCustomRange`.
 *
 * **Aquí hubo un cuarto valor, `cycle`, y quitarlo es el cambio.** El ciclo del
 * usuario se ofrecía como un PRESET más, al lado de «Mes»: dos vocabularios
 * para el mismo concepto, con un chip que había que recordar pulsar y una
 * pantalla que podía enseñar el mes natural mientras el usuario creía estar
 * viendo el suyo. Ahora el día de inicio REDEFINE qué es un mes en toda la
 * app, y el toggle vuelve a ser «Mes / Año / Personalizado».
 *
 * La aritmética de `cycle-period.ts` no se toca: sigue entera y sigue siendo
 * la fuente única del corte. Lo que cambia es QUIÉN la dispara — antes un clic
 * del usuario, ahora su perfil.
 *
 * OJO: `DebtTimeRange` (`models/debt.ts`) sigue siendo `month|year|custom`,
 * que es el contrato con la API de deuda. El corte por ciclo viaja como
 * `range=custom` + `date_from`/`date_to` (día-exacto desde PHASE-42).
 */
export type PeriodKey = 'month' | 'year' | 'custom';
