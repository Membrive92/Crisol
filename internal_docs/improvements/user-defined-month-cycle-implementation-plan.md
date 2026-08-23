# El mes lo define el usuario — Plan de implementación (V1)

**Estado**: ✅ **entregado, con un re-alcance del 2026-08-22 que este plan no
previó** — ver el aviso de abajo antes de leer nada más.

> ## Re-alcance (2026-08-22): el ciclo REEMPLAZA al mes, no convive con él
>
> Todo lo que sigue en este documento describe el ciclo como un **preset**: un
> chip «Mi ciclo» junto a «Mes», un `PeriodKey` con cuatro valores y un query
> param `cycle=true` que el cliente decide mandar. Se construyó así y el usuario
> lo probó. Su veredicto: *«sigue siendo raro e incómodo… que se cambie todo
> directamente»*.
>
> Tenía razón, y la causa es de diseño, no de implementación: el día de cobro no
> es una opción de visualización, es la respuesta a «¿qué es un mes para ti?» —
> una pregunta que el producto ya respondía por defecto. Ofrecer las dos a la vez
> obliga a mantenerlas sincronizadas, y no lo estaban: sólo CINCO endpoints
> entendían el ciclo.
>
> **Lo que cambió respecto a este plan**: `PeriodKey` pierde `cycle`; el chip
> desaparece de las dos familias de UI (el toggle y el `CycleModeChip` del
> `TimeSelector`); el período se llama por el mes que lo ABRE («Julio 2026», no
> «Ciclo del 12 jul» — decisión del usuario); en Ajustes hay un check «Modo
> predeterminado» en vez de una opción más del desplegable; y seis agregados del
> backend que derivaban su propio mes natural pasan a cortar por el del usuario.
>
> **Lo que sigue siendo válido de este plan**: toda la aritmética (§2.2), el
> invariante de presentación pura (§4.2), la previsualización de Ajustes, el
> bucketing por ciclo del backend y los criterios de aceptación de las paradas.
> Lo que caducó es la FORMA de exponerlo, no el cálculo.
>
> Detalle en [`lessons.md`](../lessons.md) y en la entrada del backlog.
Pendiente: **la prueba manual del usuario** (las dos paradas de §6). Nada está
commiteado. Escrito el 2026-08-20 contra el código real de `main`.

> **La regla del clamp, que costó dos bloqueadores.** El navegador de período lo
> usan dos clases de pantalla y la unidad de sus límites NO es la misma:
> Dashboard y Análisis piden con `cycle=true` y reciben `available_from/to` ya
> bucketizados en anclas de ciclo; **Deuda no**, porque su endpoint no tiene ese
> parámetro, así que los recibe en meses naturales. Aplicar el clamp mensual a
> los segundos deja **inalcanzable el ciclo que contiene el primer movimiento**
> (con D=14 y datos desde el 5 de marzo, ese pago vive en el ciclo que abre el
> 14 de febrero y la flecha ◀ salía deshabilitada). Ahora la unidad la **declara
> el consumidor** (`boundsAlreadyInCycles`), con default `false`: equivocarse
> hacia «traducir» enseña un período vacío de más, y hacia «no traducir»
> ESCONDE movimientos — entre las dos, la que oculta datos no puede ser el
> default. Test en los dos sentidos, en web y en móvil.

> **Hallazgo que no es de esta fase y sí está en producción.** La revisión
> adversarial de C4 destapó que `get_totals_by_month`,
> `get_totals_by_month_in_range`, `get_category_kpis` y
> `get_category_monthly_evolution` sumaban el importe en crudo bajo el predicado
> `_is_expense()`, sin el helper del signo que [PHASE-47.H] declaró obligatorio
> en el docstring de ese mismo predicado. Medido contra los datos reales del
> usuario: julio de 2026 daba **3.213,69 €** de gasto en el KPI y **3.485,79 €**
> en la barra del chart del mismo mes (272,10 €, las cuatro devoluciones sumadas
> en vez de restadas), y la categoría «Compras online» decía 1.267,06 € en el
> donut y 1.704,84 € en el drill-down para los MISMOS 56 movimientos. Corregido
> con un helper único (`bucketed_amount_expr`) y el test de conservación
> reforzado — era ciego a esto porque no sembraba ninguna devolución.
**Decisiones D1–D6: resueltas por el usuario el 2026-08-20** (§8); ninguna
queda abierta.
**Re-alcance (2026-08-20, decisión del usuario — D6)**: el histórico ENTERO
debe verse en ciclos — *«si el usuario define que el 13 es su fecha de inicio
de mes, debería ajustarse todo el histórico para ver los flujos de caja de
pérdidas y ganancias de todos los meses»*. Las series mensuales de P&G cortan
por ciclo dentro de esta misma entrega (entregable **C4**, absorbido de V2).
El resto de V2 (recurrencia, month-outlook, deuda, patrimonio) sigue fuera.
**Diseño que manda**: [user-defined-month-cycle.md](user-defined-month-cycle.md).
Este plan no reabre sus decisiones: las aterriza en entregables, corrige lo que
el diseño asume sobre el código y no es exacto (§1), fija la semántica única del
ciclo (§2) y deja marcadas las decisiones que siguen siendo del usuario (§8).
**Numeración**: sin fase asignada. A fecha del plan, PHASE-48 está reservada
([phase-48-debt-early-settlement.md](phase-48-debt-early-settlement.md)); el
siguiente número natural sería 49. Rama sugerida: `feat/phase-49-user-month-cycle`.

**Invariante innegociable** (del diseño, §Invariante): presentación pura.
`flow`, saldos, anclas de extracto, cuadro de deuda y recibo aplazado no se
tocan. El guardarraíl se escribe como test en el PRIMER entregable de backend
(§4.2), no al final.

---

## 0. Resumen ejecutivo

| Entregable | Qué | Dónde | Estado |
|---|---|---|---|
| **C0** | Unificar la aritmética de períodos (hoy divergida web/móvil) y crear la del ciclo, compartida y pura | `packages/services/src/period/` + copy en `packages/ui` | ✅ |
| **C1** | `users.cycle_start_day` (1–28, NULL = mes natural) + `PATCH /users/me` + guardarraíl «ni un céntimo» | backend (1 migración aditiva) | ✅ |
| **C2** | Ajustes con previsualización del corte (web; móvil según D4) + primer hook reactivo de perfil | web + `packages/services` | ✅ |
| **C3a** | Preset «Mi ciclo» en los navegadores de período (Análisis, Dashboard, Deuda — web y móvil) | apps | ✅ |
| **C4** | **El histórico entero en ciclos**: las series mensuales de P&G, los bounds de flechas, los chips de períodos y el «período anterior» cortan por ciclo (`cycle=true`, D leído del perfil en servidor) | backend + apps | ✅ |
| **C3b** | Preset «Mi ciclo» en el TimeSelector (transacciones + drill-down de categoría) | web | ✅ |

El resto de V2 (recurrencia, month-outlook, series de deuda, evolución de
patrimonio) y V3 (presupuestos) **no entran**; §9 los deja dimensionados para
que el día que entren no haya que redescubrir el inventario.

---

## 1. Lo que el diseño asume y el código dice (verificado)

### 1.1 · «Cero SQL nuevo» es cierto; «solo frontend» no

El módulo `users` está casi vacío:
[`users/router.py`](../../backend/app/modules/users/router.py) es un docstring
sin `APIRouter` (y no está registrado en
[`main.py`](../../backend/app/main.py)), no existe ningún endpoint de
escritura de perfil, y la tabla
[`users`](../../backend/app/modules/users/models.py) no tiene columna de
preferencias. **`cycle_start_day` sería la primera preferencia de usuario del
sistema**: V1 necesita una migración, un `PATCH /users/me` y el registro del
router. La parte buena:
[`core/deps.py`](../../backend/app/core/deps.py) (`get_current_user`,
`CurrentUser`) ya carga el objeto `User` completo en cada request, así que
cuando V2 necesite leer el ajuste en dashboard/analytics/debt no costará ni
una query.

No hay patrón previo de «ajuste de usuario»; el precedente de FORMA más
cercano es el flag por-presupuesto de PHASE-16
([`budgets/models.py:52-54`](../../backend/app/modules/personal_finance/budgets/models.py#L52),
migración `c54e9b3a7d18`): columna aditiva + schema create/update + toggle en
las dos apps. El store de moneda (`packages/store/src/currency.ts`) NO es el
modelo: eso es preferencia de dispositivo (client-only); esto es dato de
servidor.

### 1.2 · El intervalo del backend es CERRADO en ambos extremos

[`dashboard/repository.py:206-209`](../../backend/app/modules/personal_finance/dashboard/repository.py#L206)
(`_apply_scope`) y
[`transactions/repository.py:98-101`](../../backend/app/modules/personal_finance/transactions/repository.py#L98)
aplican `>= date_from AND <= date_to`. La trampa está documentada en
[`test_audit_fix_currency.py:364-396`](../../backend/tests/test_audit_fix_currency.py#L364).
**Consecuencia**: el ciclo `[día D del mes M, día D del mes M+1)` se emite como
`date_from = D de M a las 00:00:00.000Z` y `date_to = D−1 de M+1 a las
23:59:59.000Z` — la MISMA convención que ya usa `boundsForCustomRange`
([`packages/services/src/period/debt-period.ts:139-148`](../../packages/services/src/period/debt-period.ts#L139)).
Emitir `date_to = D de M+1` contaría el primer día del ciclo siguiente dos
veces. Test dedicado en §4.1.

### 1.3 · `month-outlook` no acepta rango, y la recurrencia ignora el que recibe

[`analytics/router.py:85-94`](../../backend/app/modules/personal_finance/analytics/router.py#L85)
sólo toma monedas y el service ancla al mes natural en curso
([`analytics/service.py:395-400`](../../backend/app/modules/personal_finance/analytics/service.py#L395)).
Además, dentro de `expense-structure` la CLASIFICACIÓN
estructural-vs-puntual no usa el rango pedido: `_recurrence_window`
([`analytics/service.py:59-99`](../../backend/app/modules/personal_finance/analytics/service.py#L59))
reconstruye una ventana de 6 meses naturales completos. El diseño ya relega
ambos a V2; lo que V1 SÍ debe hacer es **decirlo en pantalla** cuando el preset
esté activo (aviso compartido, §2.3).

### 1.4 · `_previous_period` no reconocerá un ciclo

[`dashboard/service.py:115-169`](../../backend/app/modules/personal_finance/dashboard/service.py#L115)
detecta «mes natural completo» y «año natural completo»; cualquier otra cosa
cae a «ventana de igual longitud con tope exclusivo». Un ciclo 14→13 caerá
siempre ahí: la comparativa «vs período anterior» será aproximada (una ventana
de la misma longitud, no el ciclo anterior exacto — difieren cuando los meses
tienen distinta duración). **Aceptable como estado intermedio y se declara**:
entre C3a y C4 la comparativa en ciclo es de igual-longitud y el aviso del
selector lo dice; **C4 la vuelve ciclo-exacta** (§3, C4.5: con `cycle=true` el
backend conoce D y compara con el ciclo anterior de verdad). La decisión D2
(§8, resuelta: re-corte total) asume este camino.

### 1.5 · Los bounds de las flechas son meses naturales `YYYY-MM`

`get_transaction_month_bounds`
([`dashboard/repository.py:155-179`](../../backend/app/modules/personal_finance/dashboard/repository.py#L155))
y `debt_movement_bounds`
([`debt/repository.py:383-448`](../../backend/app/modules/personal_finance/debt/repository.py#L383))
devuelven meses naturales y así viajan en `available_from/available_to`. En V1
el frontend los traduce a ciclos con una función compartida (§2.2, `clamp`):
con `D > 1`, el primer ciclo navegable es el que ABRE en el mes anterior a
`available_from` (su tramo final pisa el primer mes con datos). En V2 las
queries de bounds se desplazan igual que el resto del bucketing.

### 1.6 · La aritmética de períodos web/móvil ya está divergida — el ciclo la amplificaría

`boundsForAnchor` (web,
[`stitch-period-toggle.tsx:81-93`](../../apps/web/components/analysis/stitch-period-toggle.tsx#L81))
trabaja en **UTC con ancla**; `rangeForPeriod` (móvil,
[`period-toggle.tsx:55-67`](../../apps/mobile/components/dashboard/period-toggle.tsx#L55))
trabaja en **hora local y siempre «ahora»**. Con meses enteros la divergencia
casi no asoma; con un corte día-exacto, web y móvil cortarían el ciclo en
instantes distintos. **C0 unifica antes de construir encima** (a UTC, que es
como persiste `occurred_at` y como corta el backend). Es la lección
[PHASE-44.13] aplicada a tiempo: compartir el cálculo Y el contenido.

### 1.7 · El TimeSelector infiere el modo desde el rango, y un ciclo no casa

`inferActiveRange`
([`time-selector.tsx:327-367`](../../apps/web/components/ui/time-selector.tsx#L327))
hace reverse-engineering del rango (`isFullMonth`/`isFullYear`); un 14-ago→13-sep
caería al literal «rango personalizado». C3b le enseña a reconocer el ciclo
(recibe `cycleStartDay` como prop y añade `isFullCycle`), en vez de duplicar
un selector.

### 1.8 · No hay lectura reactiva del perfil, y móvil no tiene Ajustes

`queryKeys.auth.me` existe **sin ningún consumidor**
([`keys.ts:18-20`](../../packages/services/src/query/keys.ts#L18)); el perfil
se lee imperativamente (`authApi.getMe()` desde login/layout) y vive en
`useAuthStore`. C2 estrena el hook (`useMe`) y la mutación sincroniza query +
store. En móvil no existe pantalla de Ajustes (los links a
Categorías/Cuentas cuelgan de la cabecera de Análisis,
[`analysis.tsx:247-269`](../../apps/mobile/app/(modules)/personal-finance/(tabs)/analysis.tsx#L247))
— decisión D4.

### 1.9 · El tipo `User` del FE debe tratar el campo como POSIBLEMENTE AUSENTE

Lección [PHASE-47.E] (`campo !== null` con servidor viejo): mientras exista un
backend en marcha anterior a C1, `cycle_start_day` llegará ausente. El tipo se
declara `cycle_start_day?: number | null`, toda guarda es por verdad
(`user.cycle_start_day ? … : …`), y el preset simplemente no se ofrece si el
campo no llega. El test del caso ausente se escribe **omitiendo la clave**, no
poniéndola a `null`.

---

## 2. Semántica del ciclo — la definición única

### 2.1 · El dato

`users.cycle_start_day SMALLINT NULL` + `CHECK (cycle_start_day BETWEEN 1 AND 28)`.

- `NULL` = mes natural = comportamiento actual, sin cambios en ninguna pantalla.
- 1–28 **sin excepción**: el diseño ya excluye 29-31 (el clamp de febrero es
  una charca de bugs). Con `D ≤ 28` no hay clamping de fin de mes jamás.
- `D = 1` degenera exactamente en el mes natural — propiedad con test (§4.1):
  si no da idéntico, la aritmética está mal.

### 2.2 · La aritmética (pura, compartida — `packages/services/src/period/cycle-period.ts`)

El ancla de un ciclo es el `YYYY-MM` del mes que lo ABRE (reutiliza
`parseAnchor`/`formatAnchor`/`stepAnchor` de
[`debt-period.ts`](../../packages/services/src/period/debt-period.ts)):

| Función | Contrato |
|---|---|
| `cycleBoundsForAnchor(day, anchor)` | `[D de M 00:00:00.000Z, D−1 de M+1 23:59:59.000Z]` (§1.2) |
| `cycleAnchorContaining(dayStr, day)` | `día(x) ≥ D → mes(x)`; si no, mes anterior |
| `stepCycleAnchor(anchor, ±1)` | idéntico a `stepAnchor` mensual |
| `clampCycleAnchor(anchor, availableFrom, availableTo, day)` | anclas permitidas: `[D > 1 ? mesAnterior(availableFrom) : availableFrom, availableTo]` (§1.5) |
| `canStepCyclePrev/Next(...)` | derivadas del clamp, como en `debt-period.ts` |

C0 sube al mismo módulo lo que hoy está atrapado o duplicado en las apps:
`boundsForAnchor` (web), `rangeForPeriod` (móvil, divergida — §1.6), el tipo
`PeriodKey` (declarado dos veces: web
[`stitch-period-toggle.tsx:7`](../../apps/web/components/analysis/stitch-period-toggle.tsx#L7)
y móvil
[`period-toggle.tsx:7`](../../apps/mobile/components/dashboard/period-toggle.tsx#L7)),
y `todayDayStr`/`dataMinDayStr`/`dataMaxDayStr`
([`date-picker.tsx:61-85`](../../apps/web/components/ui/date-picker.tsx#L61)),
que móvil no tiene y necesitará para clampar.

### 2.3 · El contenido (etiquetas y avisos — `packages/ui/src/cycle-copy.ts`)

Lección [PHASE-44.13]: la línea entre «puro» y «render» va DESPUÉS del
contenido. Un solo módulo con:

- `cycleLabel(day, anchor)` → **«Ciclo del 14 ago 2026»** — la etiqueta nombra
  el DÍA DE COBRO que abre el ciclo (decisión D1, resuelta: ni «Agosto» a
  secas, que miente el 2 de septiembre, ni solo el rango).
- `cycleRangeLabel(day, anchor)` → «14 ago – 13 sep 2026», para los displays
  que son intrínsecamente de rango (el `RangeDisplay` del TimeSelector, el
  subtítulo del navegador): el titular identifica el ciclo por su cobro y el
  rango completo queda a la vista donde ya había un rango.
- `CYCLE_PRESET_LABEL` → «Mi ciclo» (el chip del toggle, idéntico en web y móvil).
- `NATURAL_MONTH_NOTICE` → el aviso «esta serie corta por mes natural» que
  llevan las cards que la fase no convierte (month-outlook, insights, la serie
  mensual de Deuda, la evolución de patrimonio — y el chart by-month sólo en
  el estado intermedio entre C3a y C4), visible sólo con el preset activo
  (§1.3). Si este texto se escribe dos veces, divergirá.

Los tests de paridad web/móvil importan de aquí (molde:
[`report-tabs.test.tsx`](../../apps/mobile/components/investment/report-tabs.test.tsx)).

---

## 3. Entregables

### C0 — Unificación previa de la aritmética de períodos

Refactor sin comportamiento nuevo **salvo uno, declarado**: móvil pasa de hora
local a UTC en los bounds de período (§1.6). Es un cambio visible en bordes de
mes para husos ≠ UTC y es deseable — alinea móvil con web y con cómo corta el
backend.

1. Crear `packages/services/src/period/cycle-period.ts` (§2.2) con sus tests
   (molde: [`debt-period.test.ts`](../../packages/services/src/period/debt-period.test.ts),
   incluido su caso «UTC vs Europe/Madrid»).
2. Subir `boundsForAnchor` a `packages/services` y reexportarla desde
   `stitch-period-toggle.tsx` (mismo movimiento que hizo PHASE-41/42 con
   `boundsForCustomRange`); hacer que el `period-toggle` móvil la consuma y
   retirar `rangeForPeriod`.
3. Unificar `PeriodKey` en el módulo compartido; ambos toggles lo importan.
4. Subir los helpers de day-string de `date-picker.tsx`.
5. Crear `packages/ui/src/cycle-copy.ts` (§2.3) — todavía sin consumidores de
   app; sus tests de contenido sí.

**Verde exigido**: `make verify` completo. Ningún snapshot de pantalla cambia
en web; en móvil sólo puede cambiar el instante exacto de corte (documentado
en el commit).

### C1 — Backend: la columna, el PATCH y el guardarraíl

1. **Migración aditiva y reversible**: `add_column users.cycle_start_day` +
   CHECK 1–28. El `down_revision` se toma de **`alembic heads` en el momento
   de crearla**, nunca del listado de ficheros (lección [PHASE-44.1]); tras
   crearla, `alembic heads` debe devolver UNA línea y `alembic check` quedar
   limpio (CI lo exige). Patrón de CHECK defensivo/idempotente si se quiere
   espejo de la casa: `x1n36p8ml0o9n5` (exchange-rate positive check).
2. **Modelo y schemas**: columna en
   [`users/models.py`](../../backend/app/modules/users/models.py);
   `UserResponse` gana `cycle_start_day: int | None` → aparece gratis en
   `GET /auth/me`
   ([`auth/router.py:193-196`](../../backend/app/modules/auth/router.py#L193));
   nuevo `UserUpdate` con `cycle_start_day: int | None = Field(ge=1, le=28)`
   — el campo es **requerido en el body** (enviar `null` = volver a mes
   natural; así no hace falta tri-estado ausente/None).
3. **Endpoint**: estrenar el `APIRouter` de
   [`users/router.py`](../../backend/app/modules/users/router.py) con
   `PATCH /users/me` (`service.update_me` → `repository.update_user`),
   registrarlo en `main.py`. Recordar la lección [PHASE-4.1]: tras el flush
   que muta un objeto con `onupdate`, `await db.refresh(user)` antes de
   serializar.
4. **El guardarraíl, ya**: `test_el_ciclo_no_mueve_ni_un_centimo` (§4.2). Hoy
   es estructural (nada del dinero lee la columna) — ese es el punto: existe
   para que V2 no pueda romper el invariante en silencio.
5. **Micro-cambio para C2**: `order: Literal["asc","desc"] = "desc"` en
   `GET /transactions`
   ([`router.py:145-159`](../../backend/app/modules/personal_finance/transactions/router.py#L145);
   el `ORDER BY` está hardcodeado en
   [`repository.py:224`](../../backend/app/modules/personal_finance/transactions/repository.py#L224)).
   Sin él, la previsualización no puede enseñar «las primeras filas del ciclo
   nuevo». ~4 líneas + test.
6. **Docs**: [`data-model/schema.md`](../data-model/schema.md) (sección
   `users`) y [`api/endpoints.md`](../api/endpoints.md) (`PATCH /users/me` +
   el parámetro `order`). `scripts/check_docs.py` corre en CI.

### C2 — Ajustes con previsualización

La previsualización ES la feature en V1: resuelve la trampa del 14-vs-15 (la
nómina se fecha el 14) sin teoría — el usuario VE qué filas caen dentro.

1. **Capa compartida**: `User.cycle_start_day?: number | null` en
   [`packages/types/src/models/user.ts`](../../packages/types/src/models/user.ts)
   (opcional — §1.9); `dto/user.dto.ts` con `UpdateMeRequest`; `usersApi.updateMe`
   en `packages/services/src/api/endpoints/`; hook `useMe` (primer consumidor
   de `queryKeys.auth.me`) + `useUpdateMe` que invalida la key **y** sincroniza
   `useAuthStore.setUser` (las pantallas leen el user del store hoy).
2. **Web**: sub-página `/settings/cycle` siguiendo el patrón de
   [`settings/categories/page.tsx`](../../apps/web/app/(app)/settings/categories/page.tsx)
   + card-link en el hub. Contenido: selector de día (1–28), y la
   previsualización con **dos llamadas** al listado real:
   - últimos movimientos del ciclo saliente: `date_to = corte − 1s, order=desc, limit=5`;
   - primeros del ciclo entrante: `date_from = corte, order=asc, limit=5`;
   con el `total` de cada una («N movimientos caen en este ciclo» sale gratis:
   el endpoint devuelve `total` sin paginar). El listado NO excluye
   transferencias — correcto para un preview: es lo que el usuario ve en su
   lista.
3. **Móvil** (decisión D4, resuelta: entra): ruta mínima
   `personal-finance/settings.tsx` con el mismo bloque, enlazada desde la
   cabecera de Análisis. Sin campo nuevo de estado local: mismo hook.

### C3a — El preset «Mi ciclo» en los navegadores de período

1. `PeriodKey` y `DebtTimeRange`
   ([`models/debt.ts:138`](../../packages/types/src/models/debt.ts#L138))
   ganan `'cycle'`. El toggle
   ([`stitch-period-toggle.tsx`](../../apps/web/components/analysis/stitch-period-toggle.tsx)
   y su gemelo móvil) ofrece el chip «Mi ciclo» **sólo si**
   `user.cycle_start_day` es truthy (§1.9).
2. En cada pantalla que hoy monta el toggle (web: Análisis, Dashboard, Deuda;
   móvil: Análisis, Deuda), la rama del `useMemo` de traducción añade:
   `period === 'cycle' → cycleBoundsForAnchor(day, anchorMonth)`. Las flechas
   usan `stepCycleAnchor` y el clamp `clampCycleAnchor` sobre los
   `available_from/to` que ya llegan (§1.5). La etiqueta sale de `cycleLabel`.
3. **Deuda no necesita enum nuevo en el backend**: con el preset activo, el
   frontend llama a `category-summary` con `range=custom&date_from&date_to`
   (day-exact desde PHASE-42, validado en el router). Dashboard y Analytics
   sólo reciben `date_from/date_to`, que ya aceptan.
4. **URL** (sólo Análisis web persiste período en URL): `?period=cycle&anchor=YYYY-MM`
   — extender `parsePeriod` y el serializador `analysisQuery()`
   ([`analysis/page.tsx:59-79`](../../apps/web/app/(app)/personal-finance/analysis/page.tsx#L59)).
5. **Avisos**: las cards que siguen en mes natural muestran
   `NATURAL_MONTH_NOTICE` cuando `period === 'cycle'`. En el estado intermedio
   (C3a entregada, C4 no) eso incluye el chart by-month, que con rango de
   ciclo se comporta como cualquier custom de PHASE-42 (meses de borde
   parciales,
   [`get_totals_by_month_in_range`](../../backend/app/modules/personal_finance/dashboard/repository.py#L518));
   **C4 lo convierte a barras por ciclo** y el aviso queda solo en
   month-outlook, insights, serie de Deuda y evolución de patrimonio.
6. **Clamp en móvil**: el navegador móvil no tiene los dos efectos de clamp
   del web
   ([`period-navigator.tsx:86-105`](../../apps/web/components/debt/period-navigator.tsx#L86)
   web vs móvil sin ellos). Se replican consumiendo los helpers compartidos de
   C0 — con el ciclo, un ancla fuera de datos ya no es cosmética: pinta un
   período vacío.

### C3b — El preset en el TimeSelector (transacciones + drill-down)

1. `TimeSelector` gana la prop opcional `cycleStartDay?: number`. Con ella:
   chip «Mi ciclo»; en ese modo, elegir el mes `M` de la barra selecciona el
   ciclo que ABRE en `M`; `inferActiveRange` aprende `isFullCycle` y
   `formatRangeDisplay` usa `cycleLabel` (§1.7).
2. Consumidores: la toolbar de transacciones
   ([`stitch-search-toolbar.tsx:93-97`](../../apps/web/components/transactions/stitch-search-toolbar.tsx#L93))
   y el drill-down de categoría pasan `user.cycle_start_day` desde `useMe`.
3. Decisión D5, resuelta: entra en V1, al final y recortable a fase de cola si
   V1 se alarga — los navegadores de C3a cubren el caso motivador (el
   resultado del mes).

### C4 — El histórico entero en ciclos (series de P&G) — decisión D6

**Se ejecuta entre C3a y C3b** (§6). Absorbe de V2 la parte de cuenta de
resultados: con el preset activo, las series mensuales dejan de ser meses
naturales con aviso y pasan a ser **barras de ciclo, para todo el histórico**.

1. **Una sola expresión de desplazamiento** (lección [PHASE-46]: una
   declaración, N consumidores): helper SQL `cycle_bucket(occurred_at, day)` ≡
   `date_trunc('month', occurred_at − (day − 1) * interval '1 day')` — cada
   ciclo se etiqueta por el `YYYY-MM` del mes que lo ABRE (convención del
   diseño §V2). El mismo helper cubre las variantes `to_char`/`extract` de las
   queries afectadas; prohibido repetir la aritmética en cada una (gate de
   test si hace falta).
2. **Opt-in por request, D del servidor**: query param `cycle=true` en
   `GET /dashboard/by-month`, `GET /dashboard/summary`,
   `GET /dashboard/category/{id}` (+ sus available-periods) y
   `GET /transactions/available-periods`. El día D **nunca viaja del
   cliente**: se lee de `user.cycle_start_day` (`CurrentUser` ya lo trae —
   §1.1); `cycle=true` sin ajuste configurado → 422. Así «Mes»/«Año» siguen
   respondiendo la pregunta del calendario y «Mi ciclo» la de nómina-a-nómina
   — las «dos preguntas distintas» del diseño conservan cada una su vista.
3. **Queries que aplican el helper** (el subconjunto P&G del inventario §9):
   `get_totals_by_month` (vista año = los 12 ciclos que abren en ese año),
   `get_totals_by_month_in_range`, `get_category_monthly_evolution` (drill-down),
   `get_transaction_month_bounds` y los dos `available-periods` — bounds y
   chips desplazados igual que los datos, para que flechas y selector
   aterricen en ciclos con datos reales.
4. **FE**: cuando `period === 'cycle'`, los hooks añaden `cycle: true` a la
   query (entra en las query keys vía `normalizeQuery` — regresión en
   `keys.test.ts`) y el eje del chart pinta `cycleLabel` por bucket
   («Ciclo del 14 mar», «Ciclo del 14 abr», …). Web y móvil comparten qué se
   pinta (lección [PHASE-44.13]).
5. **`_previous_period` gana la rama ciclo-exacta**: con `cycle=true`,
   «período anterior» = el ciclo anterior de verdad (ancla − 1), retirando la
   aproximación de igual-longitud de §1.4 para este modo.
6. **Lo que C4 NO toca, dicho en voz alta**: ninguna query de SALDO (el
   desplazamiento vive solo en el bucketing de flujos — el guardarraíl de C1
   lo vigila), y las zonas de V2-restante: recurrencia y clasificación
   estructural, month-outlook, insights, series mensuales de Deuda y DTI,
   evolución de patrimonio, presupuestos (V3). Todas conservan
   `NATURAL_MONTH_NOTICE` con el preset activo.

---

## 4. Tests

Método de la casa, sin excepciones: **cada test nuevo se verifica rompiendo la
línea concreta que dice proteger**, y la sonda de rotura se afirma antes de
correr nada (lecciones [PHASE-47.A] y [PHASE-47.E]: una sonda que no aplica se
lee igual que un test que protege; una edición programática exige ancla única).

### 4.1 · Aritmética pura (C0 — `cycle-period.test.ts`)

- `test_la_nomina_del_14_entra_en_el_ciclo_del_14` — **la regresión del caso
  motivador, con nombre**: una tx fechada `2026-08-14T10:00Z` cae en el ciclo
  con ancla `2026-08` y D=14; y un filtro manual 15→15 la dejaría fuera
  (documenta por qué existe la feature).
- Intervalo cerrado: tx en `D 00:00:00Z` cuenta SOLO en el ciclo nuevo; tx en
  `D−1 23:59:59Z` SOLO en el saliente (réplica de
  [`test_audit_fix_currency.py:364`](../../backend/tests/test_audit_fix_currency.py#L364)
  para el ciclo).
- `D=1` ≡ mes natural (idéntico a `boundsForAnchor` mensual, byte a byte).
- Febrero (D=28 → ciclo 28-ene→27-feb), cruce de año, `clampCycleAnchor` por
  los DOS lados (lección [PHASE-44.14]: un umbral se prueba a ambos lados) y
  el caso «UTC vs Europe/Madrid» heredado de `debt-period.test.ts`.
- Paridad web/móvil vía módulo compartido (molde `report-tabs.test.tsx`):
  ambos toggles etiquetan y cortan igual para el mismo `(day, anchor)`.

### 4.2 · Backend (C1)

- **El guardarraíl del diseño** — `test_el_ciclo_no_mueve_ni_un_centimo`
  (molde exacto:
  [`test_flow_money_model.py:287`](../../backend/tests/test_flow_money_model.py#L287)
  `test_a_refund_does_not_move_the_account_balance`): mismas transacciones
  sembradas, `get_balances` + `position-as-of` + `debt-health` con
  `cycle_start_day = NULL` y `= 14` → resultados idénticos al céntimo. El
  docstring lleva el motivo dentro (lección [PHASE-44.21]).
- `PATCH /users/me`: 422 con 0, 29 y 31; `null` limpia; el valor aparece en
  `GET /auth/me`; `updated_at` se refresca sin `MissingGreenlet`.
- `order=asc` en `GET /transactions` (y que `desc` sigue siendo el default).

### 4.3 · Frontend (C2, C3)

- Ajustes web: sólo ofrece 1–28; la previsualización pinta las dos listas y el
  corte con datos mockeados (molde de mocks:
  [`stitch-search-toolbar.test.tsx`](../../apps/web/components/transactions/stitch-search-toolbar.test.tsx));
  la mutación invalida `auth.me` Y llama a `setUser`.
- **Campo ausente** (§1.9): render con la clave `cycle_start_day` OMITIDA del
  user → ni chip ni asteriscos ni preset. Omitida, no a `null` — con `null` el
  test pasa igual y no prueba nada (lección [PHASE-47.E], literal).
- Toggle: el chip «Mi ciclo» no existe con el ajuste vacío; con D=14, la URL
  de Análisis hace round-trip `?period=cycle&anchor=2026-07` → mismo rango.
- Avisos: `NATURAL_MONTH_NOTICE` presente en by-month/month-outlook sólo con
  el preset activo.
- TimeSelector (C3b): `inferActiveRange` reconoce 14-ago→13-sep como ciclo
  cuando recibe `cycleStartDay=14`, y como «rango personalizado» cuando no.

### 4.4 · Series por ciclo (C4)

- **Conservación** — el test que caza un off-by-one del desplazamiento: para
  el mismo rango, `Σ(buckets de ciclo) == Σ(buckets naturales) == total`.
  Desplazar el bucketing no puede perder ni duplicar una sola transacción.
- **Frontera SQL** (réplica en BD del test puro de §4.1): tx el día D a las
  00:00Z cae en el bucket del ciclo que ABRE; el D−1 a las 23:59:59Z, en el
  anterior.
- **`D=1` ≡ natural, byte a byte**: con `cycle=true` y ajuste a 1, la
  respuesta de `by-month` es idéntica a la de hoy sin `cycle` — si no lo es,
  la aritmética del helper está mal.
- `cycle=true` sin ajuste configurado → 422 (y `cycle` ausente ignora el
  ajuste: mes natural intacto).
- **`_previous_period` ciclo-exacto**: para «Ciclo del 14 ago», el comparable
  es el ciclo del 14 jul completo — no una ventana de 31 días — verificado con
  meses de longitudes distintas.
- Bounds y chips desplazados: una tx el 3-feb con D=14 hace navegable el
  «Ciclo del 14 ene» (que la contiene) y NO el del 14 feb si no hay más datos.
- El guardarraíl de C1 (§4.2) sigue siendo la red: saldos idénticos con y sin
  ajuste, con y sin `cycle=true`.

---

## 5. Migración

Una sola, aditiva y reversible: `add_column users.cycle_start_day SMALLINT
NULL` + CHECK 1–28. Sin backfill — `NULL` **es** el estado correcto de todo el
mundo (mes natural), no un hueco por rellenar; no hay default numérico que
pueda convertirse en afirmación dormida (lección [PHASE-44.11]). `upgrade` /
`downgrade` simétricos, `alembic check` limpio, un solo head.

---

## 6. Orden de ejecución y paradas

```
C0 (verde solo) → C1 → C2 ──▶ PARADA 1 ──▶ C3a → C4 ──▶ PARADA 2 ──▶ C3b → docs de fase
```

- **PARADA 1 (prueba manual con datos reales)**: el usuario configura D=14 y
  la previsualización debe enseñar su nómina (fechada el 14) DENTRO del ciclo
  entrante. Esta parada responde con datos la pregunta 3 del diseño
  (fecha-valor vs contable) — para eso existe la previsualización.
- **PARADA 2 (criterio de aceptación medido)**: en Análisis con el preset, el
  ciclo 14-jul→13-ago debe reproducir la cifra nómina-a-nómina que se midió a
  mano el 2026-08-18 (≈ +300/600 €, contra ≈ +1.200 € del agosto natural
  1→15). El número exacto vive en la medición de
  [HANDOFF.md](../HANDOFF.md). Además, tras C4, el chart de Ingresos vs
  Gastos debe pintar **el histórico entero en barras de ciclo** («Ciclo del
  14 mar», «Ciclo del 14 abr», …) y la suma de las barras debe cuadrar con la
  vista natural (la conservación de §4.4, ahora a ojo del usuario). Si algo no
  cuadra, la fase no avanza a C3b.

Una fase, una rama; entrega por push directo a `main` como el resto del
proyecto. Al cerrar: doc en `internal_docs/phases/`, tabla del README,
`lessons.md` si tocó.

## 7. Verificación

- `make verify` completo en cada entregable (nunca dos `pytest` a la vez;
  ningún agente en segundo plano vivo — lección [PHASE-44.10]).
- `pnpm knip` limpio tras C0 (mueve símbolos entre paquetes: es justo donde
  knip caza exports huérfanos).
- `scripts/check_docs.py` tras tocar `schema.md` / `endpoints.md`.
- Los tests nuevos, verificados rompiendo el código (§4, método).

---

## 8. Decisiones — resueltas por el usuario (2026-08-20)

Ninguna queda abierta. Las respuestas de las preguntas 1–3 del documento de
diseño están también anotadas allí, junto a cada pregunta.

| # | Pregunta | Respuesta del usuario |
|---|---|---|
| D1 | Etiqueta del ciclo | **«El día de cobro de la nómina»**: la etiqueta ancla el ciclo a su día de cobro — «Ciclo del 14 ago» — con el rango explícito «14 ago – 13 sep» en los displays de rango (§2.3). Descartados «Agosto» a secas y el rango como único titular |
| D2 | ¿Cambiar el ajuste re-corta la historia entera? | **Sí, todo** — presentación pura, recalcular es gratis. El selector avisa de que «vs período anterior» cambia de base (y en ciclo esa comparativa es de igual-longitud, no ciclo-exacta — §1.4) |
| D3 | ¿Corte por fecha-valor o contable? | No se decide en teoría (ya lo decía el diseño): la previsualización de C2 existe para responderla mirando las filas (PARADA 1) |
| D4 | ¿Alta del ajuste en móvil en V1? | **Sí** — pantalla mínima `personal-finance/settings.tsx` (el preset móvil entra igual en C3a: el ajuste se lee de `/auth/me`) |
| D5 | ¿C3b (TimeSelector) dentro de V1? | **Sí, al final y recortable** — cierra la fase tras la PARADA 2; si la fase se alarga, se recorta a fase de cola sin bloquear nada |
| D6 | ¿El histórico entero en ciclos entra en la fase? | **Sí — es el requisito, no una opción**: *«si el usuario define que el 13 es su fecha de inicio de mes, debería ajustarse todo el histórico para ver los flujos de caja de pérdidas y ganancias de todos los meses»*. Absorbe de V2 la cuenta de resultados (entregable C4); recurrencia, outlook, deuda y patrimonio siguen fuera |

---

## 9. El inventario de bucketing mensual — qué absorbe C4 y qué sigue fuera

Inventario verificado el 2026-08-20 (el concepto, no la query — lección
[PHASE-47.E]). La técnica es la misma en todos: el bucket pasa a
`date_trunc('month', occurred_at − (cycle_start_day − 1) * interval '1 day')`
vía el helper único de C4.1.

**Absorbido por C4 (entra en esta fase — la cuenta de resultados):**

| Sitio | Qué es |
|---|---|
| `dashboard/repository.get_totals_by_month` + `get_totals_by_month_in_range` | las series Ingresos vs Gastos (vista año y rango) |
| `dashboard/repository.get_category_monthly_evolution` | la serie mensual del drill-down de categoría |
| `dashboard/repository.get_transaction_month_bounds` | los bounds de las flechas ◀▶ |
| `dashboard/service.get_category_available_periods` · `transactions/service.list_available_periods` | los chips de períodos con datos |
| `dashboard/service._previous_period` | rama ciclo-exacta (C4.5) |

**V2 restante (sigue fuera, con `NATURAL_MONTH_NOTICE` donde conviva con el
preset):**

| Grupo | Sitios |
|---|---|
| Analytics | `analytics/repository.py` (`monthly_expense_by_category`, `count_expense_months_in_window`, `structural_monthly_avg`) · `analytics/service._recurrence_window` + `get_month_outlook` |
| Deuda | `debt/history.py` (serie de deuda) · `debt/health.py` (`monthly_income_avg` → DTI) · `debt/repository.monthly_debt_series` + `_month_start/_end_utc` · `debt/service._period_bounds`/`_resolve_range`/helpers UTC, meses-cerrados del ratio de esfuerzo y `displayed_month` de la serie diaria |
| Patrimonio | `accounts/position_history._historical_points` (+ helpers de `debt/history` que reexporta) |
| Dashboard | `dashboard/service._latest_month_bounds` (fallback del module-summary sin rango) |
| Presupuestos (**V3**) | `budgets/service._month_bounds_utc` |
| **Zona prohibida** (dinero, no presentación) | `debt/amortization._add_month` (cuadro francés) · `fixed_expenses/service._add_months`/`anchor_day` (next_due real) |

Cuidados ya conocidos que el V2 restante debe releer antes de tocar nada:

- **[AUDIT-2026-08]**: toda media sobre «meses observados» recalcula su
  ventana en ciclos observados, o el término que no se diluye domina la
  fórmula (DTI, runway).
- **Recurrencia**: `classify_recurring_categories` agrupa por estabilidad
  mensual; migrarla exige demostrar equivalencia numérica o dejarla en mes
  natural a propósito y documentado (lección [PHASE-41], los dos motores).
- **month-outlook**: proyecta a fin de CICLO y su `days_remaining` cambia de
  denominador.
- **Presupuestos**: V3, decisión aparte del usuario — los declaró zona no
  probada ([PHASE-47.H]) y este plan no los toca ni en V2.

---

## 10. Qué NO resuelve esta fase, dicho en voz alta

- El month-outlook, los insights, la clasificación estructural/recurrencia,
  las series mensuales de Deuda (y el DTI) y la evolución de patrimonio
  siguen cortando por mes natural — **con el aviso en pantalla** cuando el
  preset está activo. Convertirlas es el V2 restante (§9). Las series de P&G
  SÍ entran (C4, decisión D6).
- Entre C3a y C4, la comparativa «vs período anterior» en ciclo es de
  igual-longitud; C4 la deja ciclo-exacta (§1.4).
- Presupuestos: intactos (V3, decisión del usuario).
- No cambia cuándo cuenta el gasto de tarjeta (PHASE-38) ni el modelo del
  recibo aplazado (PHASE-47.E) — ya lo dice el diseño; el guardarraíl de §4.2
  lo convierte en test.

### Hallazgos colaterales de la exploración (no bloquean; candidatos a backlog)

- El navegador de período móvil no clampa ancla ni rango custom a datos (web
  sí) — C3a lo arregla de paso para el ciclo.
- `apps/mobile/jest.config.js` (`transformIgnorePatterns`) aún lista el scope
  antiguo `@finanzas` en vez de `@crisol` — inerte hoy, mina si algún paquete
  `@crisol/*` necesita transformación.
- El drill-down de categoría lee `?from&to` al montar pero no escribe la URL
  de vuelta (asimetría con transacciones).
- `queryKeys.auth.me` llevaba declarada sin consumidores; C2 la estrena.
