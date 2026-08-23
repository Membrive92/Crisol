# Backlog — deuda técnica, limitaciones y follow-ups

> Inventario consolidado de trabajo no hecho. Recopila las "Limitaciones
> conocidas" de cada fase + entradas `[tech-debt]` de `lessons.md` +
> follow-ups explícitos.
>
> Reglas:
>
> - Cada item lleva la fase origen entre corchetes (`[PHASE-X.Y]`) para
>   poder bajar al doc original.
> - Si una nueva fase resuelve algo de aquí, **se borra** del backlog
>   (no se tacha) — la phase doc deja la traza histórica.
> - Si un item se promueve a fase formal, se traslada a
>   `phases/phase-X.Y-*.md` y se borra de aquí.
> - Última actualización: 2026-07-23 (PHASE-44.7: módulo Inversión completo —
>   se borran los follow-ups resueltos (seed de umbrales, golden test, módulo
>   oculto en el frontend) y se alta la **prueba manual pendiente**, que bloquea
>   el commit).
> - 2026-08-20: **se borra la entrada del saldo de BBVA (−700,26 €)**, resuelta.
>   Verificado ejecutando `make audit-balances` contra la BD del usuario: las
>   cuatro cuentas de activo cuadran al céntimo con su extracto (BBVA
>   1.778,19 €) y no falta ningún tramo. Los residuos que la entrada citaba
>   aparte también están hechos: los cuatro adeudos de julio vuelven a ser gasto
>   (1.099,64 € en `flow=OUT`), las 19 marcas de aplazamiento siguen puestas y el
>   extracto de la tarjeta está reimportado en su cuenta. Traza en
>   [`phases/phase-47.F-borrowed-money-is-money.md`](phases/phase-47.F-borrowed-money-is-money.md).
>   Queda sólo el enlace declarativo del abono de 700,26 € con su pasivo — un
>   clic que no mueve ningún número (el saldo del pasivo sale del cuadro).
> - 2026-08-20 (2): **AUDIT-2026-07-13 se cierra**. Reverificada contra la BD:
>   los cinco puntos estaban resueltos o eran falsos, y dos lo eran por la misma
>   razón (leer filas repetidas sin reconstruir la cadena de saldos). El «doble
>   conteo de Taxdown» no existía —son siete compras distintas— y los «posibles
>   duplicados» de marzo encajan al céntimo en el extracto.
> - 2026-08-20 (3): **dos entradas se cierran con código.** Una declaración
>   manual ahora sobrevive a una reimportación (`transactions.flow_declared_at`
>   firma la dirección; el import la recupera de la papelera por `import_hash` y
>   lo dice en el resumen), y el cargo agregado de tarjeta se acota a SU tarjeta
>   —con `settlement_account_id`, que existía desde 47.A sin lector— en vez de
>   avanzar una cuota de todas.
> - 2026-08-22: **el desfase de zona horaria en las fechas de movimiento**, que
>   no estaba inventariado porque nadie lo había visto. `_parse_datetime`
>   devolvía un naive y asyncpg lo interpretaba en la zona DEL PROCESO, así que
>   «13/02/2026» se guardaba como `2026-02-12T23:00:00Z`: 469 de 491 filas
>   desplazadas un día y 14 de mes. Arreglado en la raíz (parser en UTC + tipo
>   `CivilDatetime` en los schemas de entrada) y en los datos
>   (`scripts/normalize_civil_dates.py`, 548 filas + 10 cuotas, con el
>   `import_hash` como testigo). Los saldos no se movieron y los 557 hashes
>   siguen válidos. Lo destapó el preset «Mi ciclo» con D=13, que puso el borde
>   del período en medio de datos densos. Detalle en `lessons.md`.
> - 2026-07-24: alta de **UI-2026-07-24 — auditoría responsive** (aplicada, sin
>   commitear, pendiente de validación visual).
> - 2026-08-09 (2): entran los tres charts del informe web (PHASE-44.22) y se
>   borran las dos entradas de «informe sin charts».
> - 2026-08-09: se borran seis entradas resueltas (knip en CI + `scripts/` en
>   ruff/black/mypy, refresco del sector al re-resolver, docstring de
>   `classify_sic`, test de la tabla de cartera, date-picker del alta móvil,
>   auto-scroll del combobox y el motivo por celda en móvil). Traza en
>   `phases/phase-44.17-honest-absences.md` y `phase-44.21-sector-calibration.md`.
> - 2026-08-01: puesta al día del bloque de Inversión con PHASE-44.8 y
>   PHASE-44.9. **Dos entradas de 44.7 habían caducado en silencio** (decían que
>   no había tests de componente FE y que el informe era «veredicto + tablas»);
>   corregidas en vez de tachadas. Es la lección [PHASE-43] aplicada a este
>   propio fichero: una premisa escrita deja de ser cierta sin que nadie lo note.

---

## UI-2026-07-24 — Auditoría responsive del frontend web (aplicada y commiteada, `8c2927c`)

Origen: un falso positivo de "cards con demasiado aire" que resultó ser **zoom
del navegador** (ver `lessons.md` → `[ui-diagnosis]`). A raíz de eso, auditoría
responsive completa de `apps/web` a 100% de zoom (resoluciones 1366→ultrawide),
**sin bajar `pageWide=2400`** (es el look aprobado por el usuario).

- **Auditoría**: 32 hallazgos (4 altos, 12 medios, 16 bajos) — grids de columnas
  fijas que no reflúyen, tablas sin scroll horizontal (se **cortan** en estrecho),
  toolbars sin `flexWrap`, y contenido que se dispersa en monitores grandes.
- **Aplicado** (24 ficheros, **sin commitear**): grids colapsables
  (`repeat(auto-fit, minmax(min(100%, N), 1fr))`, o media query `<style>` donde
  el ratio no es equitativo — p. ej. el donut+gráfica **1:1.6** de Deuda, que el
  `auto-fit` habría igualado alterando la vista a 2360px), wrappers `overflowX:
  auto` en el `DataTable` compartido + tablas de cartera/cuadro, `flexWrap` en
  toolbars, y caps de anchura (`pageNarrow` / valores fijos) en formularios y
  listas de pocas columnas.
- **Verde**: `tsc --noEmit` · `eslint` · las rutas editadas compilan y sirven 200.
- **Revisión adversarial de diffs completada**: revirtió 3 caps de Grupo-2
  **contraproducentes** (donut, gráfica Ingresos/Gastos, gráfica de evolución de
  categoría) que capaban contenido que ya llenaba el ancho y creaban hueco vacío
  nuevo. El resto de Grupo-2 (que sí reduce el aire pero **cambia la vista a
  2360px**) queda **pendiente de validación visual del usuario** antes de commitear.
- **Diferido a propósito** (no aplicado): altura fija de las **gráficas**
  (Recharts: `debt-daily-evolution`, `debt-monthly-evolution`, `debt-trend-chart`,
  `networth-evolution-card`) → sólo se aplanan por encima de 2400px (fuera del
  monitor del usuario) y pasarlas a `aspect`/`clamp` a ciegas es arriesgado; más
  un par de caps cosméticos redundantes (`transaction-list` maxWidth,
  `budget-form` ya cubierto por el cap de la página de presupuestos).
- **Nota estructural**: los estilos son inline y **no admiten `@media`**; la
  adaptación se hace con grids intrínsecos (`auto-fit`/`minmax`) y, donde hay que
  preservar un ratio, con bloques `<style>` + clase (mismo mecanismo que el
  breakpoint móvil de `app/(app)/layout.tsx`).

---

## Refactor propuesto — Simplificar transferencias (ADR-0005)

Modelo simple dirigido por `flow`: el emparejado (`transfer_pair_id`) pasa a
metadato opcional de display, los 3 estados colapsan a 1, y la deuda deja de
depender del par. Habilitado por "todas las cuentas importadas". Plan
incremental en 5 fases (T1–T5), sin migración destructiva, en
[`decisions/0005-simplify-transfers-flow-driven.md`](decisions/0005-simplify-transfers-flow-driven.md).
**Propuesta — no implementada.** Riesgo: refactor de zona muy curada
(PHASE-23→34); mitigado con golden tests de equivalencia por fase.

---

## AUDIT-2026-07-13 — integridad de datos (**cerrada el 2026-08-20**)

Hallazgos de la auditoría de integridad de datos sobre la BD del usuario
`membrij7@gmail.com`, disparada por una revisión manual del drill-down de
categoría. Inventario completo en
[`audits/2026-07-13-data-integrity-pending-check.md`](audits/2026-07-13-data-integrity-pending-check.md).

**Reverificada consultando la BD el 2026-08-20: los cinco puntos están
resueltos o eran falsos.** Se conserva la entrada porque dos de ellos eran
falsos por la MISMA razón —se leyeron las filas sin reconstruir la cadena de
saldos— y ese es el mecanismo que [PHASE-47.G] convirtió en regla.

- **Doble conteo de Taxdown: NO EXISTÍA.** Hay siete filas «Taxdown» y son
  compras distintas (150 · 300 · 150 · 957,71 · 2.601,90 · 33,29 en abril,
  más la de 239 € de marzo). La de 239 € está en la papelera y el cuadro de
  `Compra financiada mar-2026` suma exactamente 239,00 € de capital en sus 9
  cuotas, todas pagadas: el gasto entra **una sola vez**, por las cuotas, que
  es lo que manda PHASE-38 y no lo que lo contradice.
- **«Posibles duplicados» del 12/03 y el 18/03: NO LO ERAN.** Las cuatro filas
  encajan al céntimo en la cadena del extracto: 3.411,87 −900 → 2.511,87 +1200
  → 3.711,87 −900 → 2.811,87 −300 → 2.511,87 −18,49 → 2.493,38, que enlaza con
  el 15/03. Ídem las dos de 1.000 € el 18/03. La sospecha salió de mirar
  importes repetidos sin reconstruir el saldo.
- **Pares de transferencia incoherentes (4b)**: resuelto. Las dos Western Union
  de 215,99 € están borradas y absorbidas; no queda ninguna pata viva con
  dirección dudosa.
- **Saldos sin `opening_balance` real**: resuelto. BBVA 2.109,78 € de apertura
  con ancla 1.778,19 € (y `make audit-balances` da diferencia 0,00); Wise a
  0,00, ya sin el −5.000 € de apaño.
- **Selector temporal UTC vs local**: corregido el 2026-07-13 y commiteado.

**Lo único no verificable al céntimo**: el supuesto hueco de la tarjeta en
abril. `Tarjeta BBVA credito` no tiene `anchored_statement_balance`, así que la
auditoría no la cubre; el recuento de abril (11 movimientos) está en línea con
marzo (10) y no hay evidencia de hueco, pero tampoco prueba aritmética.

---

## AUDIT-2026-05 — follow-ups diferidos

Items de la auditoría conscientemente diferidos durante la remediación
(ver `audits/2026-05-30-full-app-audit.md`):

- **[Ola 4] Focus-trap del drawer mobile** (`(app)/layout.tsx`). El
  modal principal (`confirm-dialog.tsx`) ya atrapa el foco; el drawer
  lateral (chrome sólo-mobile) se cierra con ESC + backdrop pero no
  atrapa el `Tab`. Menor: la experiencia móvil real es la app RN.
- **[Ola 4] Bentos no responsive en web** (`analysis/page.tsx`,
  `debt/page.tsx`). Los grids 8fr/4fr y 7fr/5fr son ratios de diseño
  deliberados; en viewport < ~660px se comprimen. No se convierten a
  `auto-fit` para no regresar el diseño desktop (la web es
  desktop-first). `budgets` y el panel de filtros ya usan `auto-fit`.
- **[Ola 4→7] Test del interceptor `api/client.ts`** (cola de 401
  concurrentes + reintento con `FormData`). Trasladado a la ola de
  cobertura de tests (Ola 7), donde encaja con los endpoint-client
  tests.
- **Cola/worker real para imports/receipts largos**. La Ola 3 los
  saca del event loop vía threadpool; una cola de jobs persistente es
  cambio de infra mayor sin beneficio claro en un único host de dev.
- **[Ola 6] Reorg físico backend del módulo deuda — HECHO en PHASE-47.A**
  salvo dos residuos. Los seis módulos ya viven en `debt/` (`health`,
  `history`, `reconciliation`, `amortization`, `installments_model`,
  `installments_repository`) con sus 13 schemas, y un test de capas por AST
  impide que el ciclo vuelva. Las URLs `/accounts/debt-*` se mantienen tal
  como decidía esta entrada (cambiarlas rompe contrato). **Queda**: extraer
  los helpers de fecha duplicados a `core/dates.py` (`_today_utc`,
  `_start_of_month`, `_end_of_month`, `_add_month`, `_format_month`,
  `_month_start_utc`/`_end_utc`) y re-exportar `converted_amount_expr` desde
  `personal_finance/_shared/money.py`. Los dos son deduplicación pura, sin
  beneficio de comportamiento.
- **[Ola 6b] Dedup cosmético del navegador de período + filtro de
  liabilities (web/mobile)**. Diferido: `DEBT_PERIOD_OPTIONS` compartido
  (web usa 'Trimestre', mobile 'Trim.') y un `useDebtLiabilities`
  memoizado (web memoiza, mobile filtra inline). Sin cambio de
  comportamiento — pura deduplicación. Recipe en `ola6-mapping`.
- **[Ola 6] Nuevo endpoint agregado `GET /debt/overview`**. Diferido:
  reduciría las 3 cargas de account-list/balances de la página `/debt` a
  1. Es una mejora de rendimiento aditiva; la página funciona sin él y
  el índice de Ola 5 ya alivia esas queries. Recipe en `ola6-mapping`.
- **[Ola 5] Cache de tasas FX "de hoy" en debt-health**. Cachear el
  factor `EUR→X` por divisa dentro de `compute_debt_health` ahorraría
  un puñado de lookups en usuarios multi-divisa. NO se hizo: los
  usuarios mono-divisa (mayoría) nunca llaman `_convert_at_today`
  (la cuenta ya está en `effective_currency`), y cachear el factor de
  `convert(1, …)` arrastra el riesgo de divergencia por
  cuantización frente a `convert(x, …)`. Bajo beneficio / riesgo en
  el camino monetario → diferido. El índice (Ola 5) y el rewrite
  agrupado de `debt_history` son los wins reales de rendimiento.

---

## Top candidatos prácticos

Si quieres atacar trabajo real, por orden de valor:

1. **Captura por ticket en mobile** (`expo-camera` /
   `expo-image-picker`) — el backend de receipts ya lo soporta; falta
   la pantalla de captura. Es el hueco funcional más grande de mobile.
2. **Materializar `line_items` de tickets en transacciones** — hoy un
   ticket crea **una** sola tx con el total; desglosar por línea daría
   gasto por categoría real desde el ticket.
3. **Endurecer auth** — **reset / forgot password** + **rate-limit en
   `/auth/login`**. Lo mínimo antes de cualquier despliegue.

---

## Multimoneda — follow-ups de fase 8

- **[PHASE-8.4]** `StitchRecentActivity` (sidebar del dashboard) sigue
  mostrando los 4 últimos movimientos en su moneda original. Para
  alinearlo con el toggle global, basta exponer `target_currency` en
  la query con `limit=4` y consumir `tx.converted_amount` en el
  componente. Decidido fuera de PHASE-8.4 para no convertir vistas
  compactas.
- **[PHASE-8.x]** JPY (y otras monedas sin decimales) redondea a 2.
  La política `quantize` per-currency vive en `currency.service` —
  habrá que añadirla cuando entren datos JPY reales.
- **[PHASE-8.3]** `ensure_rates_for_dates` hace una llamada a
  frankfurter por fecha (serial). Para 50 fechas distintas en frío
  son 50 round-trips. Paralelizar con `asyncio.gather` si la primera
  carga molesta.
- **[PHASE-8.4]** `previous_period_*` aún hace una segunda query
  contra `get_totals_by_kind`. Consolidar al 100% requeriría un
  SELECT con doble scope; no compensa la complejidad por ahora.

---

## Módulo Inversión — follow-ups (fase 44)

Limitaciones conscientes del módulo. El engine (6 capas, 57 métricas), el adapter
EDGAR, la persistencia, la API (28 endpoints) y el informe con siete pestañas
están **construidos** (44.7, 44.8 E1 y 44.9); lo de aquí es lo que queda.

> **Este fichero es el sitio DURABLE de la deuda del módulo.** `HANDOFF.md` la
> repite para la sesión en curso, pero se reescribe entero cada vez — lo que sólo
> viva allí se pierde. Si detectas deuda nueva, escríbela aquí.

### Validación manual pendiente

El flujo Análisis con MCD se validó a mano el 2026-07-26 (y el smoke en vivo
cazó el bug del `getattr` sobre un método). Lo que **sigue sin recorrerse**:

- **[PHASE-44.9] El informe con siete pestañas, entero.** Recorrido: MCD (le falta
  `cogs` → varias métricas no calculables con motivo), Realty Income (socimi:
  balance no clasificado, la liquidez casi entera cae) y JNJ. En cada uno, las
  siete pestañas y **recargar en cada una**. Los análisis guardados antes de 44.9
  hay que reejecutarlos.
- **[PHASE-44.13] El buscador con índice y el informe en móvil.** Consultas de
  prueba y qué debe pasar, en la phase doc.
- **[PHASE-44.11] Los precios contra el bróker del usuario.** No delegable.
- **[PHASE-44.7] Flujo Cartera completo**: alta de compra, posición con coste
  base, badge «sin cotización», venta con FIFO (409 al vender de más), split
  aplicado.

Playbook paso a paso en
[`investment-module-guide.md` §9](investment-module-guide.md).

### Follow-ups funcionales

- **[PHASE-44.7] Sin `FINNHUB_API_KEY`**: cotizaciones y búsqueda externa
  desactivadas. El adapter está construido y probado con fixtures; en cuanto haya
  key, la cartera muestra valor de mercado, P&L latente y peso sin tocar código.
- **[PHASE-44.7] Summary en divisa nativa**: los totales mezclan divisas si la
  cartera es multi-moneda. Falta integrar un feed de FX vivo para convertir a una
  divisa base — la fórmula del P&L (opción A) ya reparte precio/divisa cuando
  `fx_actual` exista (hoy cae a `fx_compra` → `fx_effect = 0`).
- **[PHASE-44.7] `spinoff` y `return_of_capital`**: se registran pero aplicarlas
  devuelve 400. El modelo `CorporateAction` (un `ratio` escalar) no expresa el
  security destino ni la fracción de base; exige ampliar el modelo + migración.
- **[PHASE-44.22] Los tres charts existen en WEB, no en móvil.** El heatmap de
  Δ%, la deriva common-size y el dumbbell de stress están en el informe web;
  móvil sigue con las tablas. El heatmap y el dumbbell son SVG/rejilla y se
  portan sin librería (la escala divergente ya vive en `packages/ui`); la deriva
  usa Recharts, que en RN sería `react-native-gifted-charts` — otra
  implementación, no un port.
- **[PHASE-44.22] Los seis charts anteriores llevan la rejilla discontinua.**
  Los nuevos la estrenan sólida (una discontinua se lee como umbral cuando sólo
  es una guía). Alinear los de Análisis y Deuda es una pasada cosmética aparte.
- **[PHASE-44.13] La pestaña del informe de móvil vive en estado local**, no en
  la URL. Expo Router no tiene aquí el query param de la web y forzarlo obligaría
  a una ruta por pestaña. Las CLAVES sí son las mismas (`veredicto`, `estados`…,
  en `REPORT_TABS`), así que habilitar enlaces profundos no exige renombrar nada.
- **[PHASE-44.7] Reconciliación con el patrimonio (ARCH §9, fase 40.9)**: decidido
  dejar Inversión como espacio SEPARADO (no entra en el patrimonio neto del
  Dashboard) y eximir `/investments` del `AccountsGuard`. Integrarlo exige decidir
  la política de exclusión/inclusión de brokerage (PHASE-31.4).
- **[PHASE-44.7] Split sobre lote parcialmente vendido**: aplicar el ratio escala
  la cantidad completa del lote, incluida la parte ya consumida por ventas
  anteriores (cuyas allocations quedan congeladas a precios pre-split). Caso
  borde; el ajuste es auditado y reversible vía `inv_lot_adjustments`.
- **[PHASE-44.1] Sin `registry.py` del módulo backend** (la ARCH §1 lo lista como
  metadatos del módulo). El enrutado sí existe (`investment/router.py` agrega los
  5 sub-routers); falta sólo el fichero de metadatos, sin precedente en otros
  módulos.

### Deuda del buscador (fase 44.8)

- **[PHASE-44.14] Suiza es frontera documentada**: SIX no reporta ni a ESMA ni
  a la FCA, así que Nestlé, Roche y Novartis sólo entran por alta manual o por
  su ADR estadounidense. Si algún día pesa, SIX publica listados propios y
  sería un tercer seed sin tocar nada más.
- **[PHASE-44.14] Los mercados SME/growth no se siembran** (AIM, Euronext
  Growth, First North, Xetra Scale, BME Growth). Decisión de alcance, no
  técnica: se amplía añadiendo filas a `SEED_SEGMENT_TO_OPERATING`.
- **[PHASE-44.14] El alta `ext:` exige red** (resolución ISIN→símbolo +
  validación por cotización). Deliberado —nada se persiste sin ver una
  cotización— pero significa que sin conexión no hay alta europea, mientras que
  la búsqueda sí funciona offline.
- **[PHASE-44.14] `MIN_ROWS_TO_PRUNE = 100` es un número elegido, no medido.**
  Protege de un fichero truncado; si algún día un registro real encogiera por
  debajo de 100 filas legítimas, el borrado degradaría a upsert y las
  deslistadas sobrevivirían (el script lo avisa por consola).

### Deuda del informe (fase 44.9)

- **[PHASE-44.10] `total_debt_incl_leases` sigue sin consumidor, a propósito.**
  Existe para comparabilidad IFRS16/ASC842 y el cuaderno del usuario no la pide.
  Las otras tres piezas huérfanas (`maintenance_capex`, `wc_operating`,
  `wc_total`) ya se cablearon como series de la capa evolutiva.
- **[PHASE-44.9] El «% común» no cubre el flujo de caja ni 4 partidas del P&L**
  (`pretax_income` y los tres recuentos de acciones). La pantalla lo avisa, pero
  la cobertura real está en `evolution.VERTICAL_INCOME_ITEMS`.
- **[PHASE-44.9] Los runs anteriores a esta fase no se pueden explicar.**
  Tienen `thresholds_used = {}` y `signals = []`: se ejecutaron antes de que el
  motor los publicara. La pantalla lo declara y basta con reejecutar el análisis;
  no se inventa la calibración retroactivamente.
- **[PHASE-44.10 · sin evidencia que lo sostenga] `S7` en intensivas en
  intangibles.** La banda 1-2 es **del cuaderno del usuario**, no del motor, y la
  advertencia de que «en software y farmacia el rango se queda corto» venía de
  esa misma nota, sin ningún caso detrás. Comprobado contra la BD real
  (2026-08-09): **JNJ sale 1,44 · 1,44 · 1,52 · 1,44 — verde, dentro de banda los
  cinco ejercicios**, y MCD ni llega a bandearse porque su patrimonio es negativo
  y S7 exige denominador positivo (la guarda ya está puesta, igual que en R5).

  O sea que la premisa no muerde en nada del catálogo. **No se le pone delta**:
  mover una banda del cuaderno sin un solo caso que lo pida exige un ADR y no
  habría qué escribir en él. Se reabre con la primera empresa de software con
  intangibles pesados. La calibración sectorial (PHASE-44.21) ya tiene el sitio
  preparado (`sector_profiles.SECTOR_PROFILES`) el día que haya un número.

### Deuda de la calibración sectorial (fase 44.21)

- **[PHASE-44.21] El SIC no se persiste**, así que reclasificar un valor exige
  volver a preguntárselo a EDGAR (`scripts/reclassify_securities.py`). Es
  suficiente para un catálogo de cuatro valores y la cache del adapter absorbe
  las repeticiones; persistirlo lo convertiría en un recálculo local, pero es una
  columna más para un problema que hoy no aprieta.
- **[PHASE-44.21] Un valor europeo no tiene SIC**, así que el alta `ext:` llama
  a `sic_to_sector(None)` → `UNKNOWN` → perfil genérico siempre. Inocuo mientras
  sin CIK no haya análisis; el día que entre un adapter europeo, Iberdrola sería
  genérica en vez de utility.
- **[PHASE-44.21] La calibración es v1: anclas editoriales, no un backtest.**
  Y es casi toda **latente** — sin ninguna financiera ni ninguna eléctrica en el
  catálogo, la parte más trabajada (la whitelist bancaria, 33 métricas apagadas)
  no se ejercita fuera de los goldens sintéticos. La revisión con runs reales
  sigue pendiente, con la regla anti-tuning delante.
- **[PHASE-44.17] Sólo publican evaluación las 8 banderas que la síntesis usa
  como señal.** C4-C8 no la publican: no hace falta hoy y el gate sólo exige las
  usadas, pero si alguna pasa a ser señal habrá que acordarse — el gate lo dirá.

### Calibración del engine (necesita empresas reales ingeridas)

- **[PHASE-44.3] Calibrar el corte de C2 ("beneficio sin caja")**. La regla del
  DESIGN §5 dice "NI crece y CFO plano/cae" sin definir **qué es plano**. Se
  implementó el criterio estricto (crecimiento de CFO ≤ 0) para no generar falsos
  positivos, con el efecto de que un CFO creciendo un 1% frente a un resultado
  neto creciendo un 90% **no dispara** — que es exactamente el patrón que la
  regla quiere cazar.

  **Medido en la BD real (2026-08-09), el primer caso concreto en cinco fases**:

  | JNJ | Beneficio | Flujo de explotación |
  |---|---|---|
  | 2023 | **+95,9%** | +7,5% |
  | 2024 | −60,0% | +6,5% |
  | 2025 | **+90,6%** | +1,1% |

  2023 y 2025 son el patrón, y la regla calla. Pero el contraargumento vive en la
  misma tabla: esos vaivenes son **cargos extraordinarios** (litigios del talco)
  que hunden un ejercicio y hacen que el siguiente parezca un cohete, no un
  beneficio que se escapa de la caja.

  Lo que inclina la balanza: con un corte por diferencia de crecimientos de 15 pp
  **y la exigencia de dos años seguidos**, en estos datos no saltaría nada — 2023
  y 2025 no son consecutivos y 2024 no crece. La racha ya filtra el ruido de los
  extraordinarios, así que el corte por diferencia no sería tan ruidoso como se
  temía. **Sigue haciendo falta más de una empresa** para distinguir «el corte es
  bueno» de «no hay casos». Mismo tipo de calibración que pide C6.
- **[PHASE-44.3] C6 (dilución) está DORMIDA en el catálogo actual.** La regla
  exige que las acciones CREZCAN más de un 2% sin recompras; las dos empresas
  ingeridas recompran (JNJ −3,5% y −5,0%; MCD ≈ −1,2% cada año), así que no puede
  dispararse ni por acierto ni por error. Calibrar el 2% exige una empresa que
  EMITA — una tecnológica joven, una biotecnológica—, y hasta entonces cualquier
  ajuste sería a ciegas.
- **[PHASE-44.3] C5 no distingue "sin compras" de "sin dato"**. Si
  `acquisitions` es un hueco, la regla se salta el año en vez de afirmar que
  el fondo de comercio apareció solo. Con la política de imputación del §4.5
  (`acquisitions` está en la lista blanca ausente→0) debería llegar siempre
  informado desde la ingesta; verificar ahora que el adapter EDGAR está vivo.

---

## Backend y dominio

### Auth

- **[PHASE-1.1]** Sin reset / "forgot password" ni verificación por
  email.
- **[PHASE-1.1]** Sin RBAC. No hace falta aún (single-user).
- **[PHASE-1.1]** Sin rate limiting en `/auth/login` —
  protección bruteforce pendiente.

### Transactions / categories

- **[PHASE-10.1]** Sin TTL / auto-purge nocturno de papelera. Si
  crece de forma indefinida, añadir cron en una fase futura.
- **[PHASE-10.1]** Receipts no soft-delete. Sólo transactions. Si
  hace falta, replicar el patrón.
- **[PHASE-2.1]** Search es `ILIKE` simple — sin full-text ni semántico.
- **[PHASE-2.1]** Sin idempotencia en `POST` (irrelevante hasta que
  haya bulk-create vía API).

### Dashboard

- **[PHASE-3.1]** Sin caching de agregaciones — cada request reejecuta
  `SUM`/`GROUP BY`. Aceptable para volúmenes personales; meter TTL
  cache si regresa la performance.

### Imports

- **[PHASE-4.1]** El fichero importado no se persiste. Para re-auditar
  hay que volver a subirlo.
- **[PHASE-4.1]** Sin endpoint de preview previo al import — el pipeline
  es síncrono y va a completion en el mismo request.
- **[PHASE-4.3]** PDFs sin texto extraíble (escaneados) terminan en
  `failed`. Fallback OCR vía Ollama documentado como branch
  `feat/pdf-vision-fallback` (no abierto).

### Receipts

- **[PHASE-5.1]** `ReceiptExtraction.line_items` se persiste pero no
  se materializa en transacciones individuales — el MVP crea **una**
  sola transacción con el total.
- **[PHASE-5.1]** Sin endpoint de descarga de blob ni presigned URL
  (`GET /receipts/{id}/blob` con presigned URL pendiente si la UI lo
  necesita).
- **[PHASE-5.1]** No hay smoke real de extracción end-to-end con un
  ticket de verdad — requiere `qwen2.5-vl:7b` descargado.

### IA local (módulo `ai`)

- **[PHASE-7.1 → 37.5]** Smart Insights v2 (PHASE-37.5) ya genera
  insights **derivados** no-redundantes (sin IA). Queda pendiente el
  consejo **generativo** real (LLM sobre el histórico) — requiere
  madurar el módulo `ai` para texto, no sólo visión.

---

## Frontend web

- **[PHASE-4.2]** Mapping de columnas es free-text — sin validar
  contra cabeceras del fichero antes del upload. Si el usuario teclea
  un nombre que no está, el job termina con `rows_failed`.
- **[PHASE-4.2]** Jobs inmutables — sin retry/edit desde UI; re-subir
  el fichero es la única vía.
- **[PHASE-5.2]** Sin botón "re-invocar IA" si la extracción de un
  ticket es mala — toca editar manualmente o rechazar y resubir.
- **[PHASE-7.2]** Description en tabla truncada a 280px — sólo en el
  detalle se ve completo.

---

## Mobile (área más débil)

- **[PHASE-5.2]** Sin captura por cámara. El backend ya lo soporta —
  falta integrar `expo-camera` / `expo-image-picker`.
- **[PHASE-9.2]** `MonthlyChart` ligado a año en curso (la query
  `useDashboardByMonth` sólo acepta `year`). Si se quiere "últimos
  12 meses rolling" o rango libre, requiere cambio en backend.
- **[PHASE-9.2]** `rangeForPeriod` duplicada entre web y mobile (15
  líneas puras). Mover a `packages/ui` cuando aparezca un tercer caller.
- **[PHASE-9.2]** `apps/mobile/components/dashboard/dashboard-filters.tsx`
  quedó sin callers tras PHASE-9.2 (lo reemplazó `currency-picker.tsx`).
  Eliminar si no resurge necesidad de year picker.
- **[PHASE-11.6]** Cobertura UI mobile mínima — `jest-expo` ya
  configurado y un test smoke (Toaster), pero pantallas
  (`analysis`, `transactions`, `trash`, `receipt/new`) sin tests.
- **[PHASE-2.2]** Pull-to-refresh: web no tiene equivalente — depende
  de `staleTime` para revalidar.

---

## Infra / despliegue / seguridad

- **[PHASE-0.2]** Sin Dockerfile del backend — desarrollo corre uvicorn
  en host. Empaquetado deferido a fase de despliegue.
- **[PHASE-0.2]** Sin headers de seguridad (HSTS, CSP, X-Frame-Options).
  Pendiente reverse proxy (Caddy/Traefik) en despliegue.
- **[PHASE-0.3]** Modelo de visión no se descarga automático — `docker
  exec ollama pull qwen2.5-vl:7b` es manual. Automatizar en compose
  con `entrypoint` script.
- **[PHASE-1.1]** JWT secret de tests es corto — produce
  `InsecureKeyLengthWarning`. Producción usa ≥32 bytes (irrelevante
  pero ruido en logs de pytest).
- **[PHASE-43] CI no ejecuta `make verify` como tal.** `knip`, `ruff`, `black`,
  `mypy`, los tests y `check_docs.py` sí corren (cada uno como su propio paso),
  pero un gate nuevo que se cablee ÚNICAMENTE al Makefile seguirá sin correr en
  un push. La regla práctica, ya aplicada en 44.17 y 44.21: los detectores viven
  en `pytest` o en `vitest`, no en el Makefile.

---

## Tests

- **[PHASE-2.2]** Mobile component tests pospuestos — requieren
  `jest-expo` setup.
- **[PHASE-5.1]** Sin smoke real de extracción de ticket (requiere
  modelo descargado).
- **[PHASE-5.2]** Sin E2E de UI — la cobertura vive en lógica pura
  (formatters, query keys, endpoints).
- **[PHASE-8.1]** Sin smoke contra frankfurter real — todo mock.
  Periódicamente revisar contrato; si frankfurter cambia, lo veremos
  en producción antes que en CI.

---

## UX / polish menor

- **[PHASE-7.1]** `KpiDelta` con `previous=0` y `current!=0` no puede
  dividir por cero — muestra signo sin %. Caption "Nuevo" como mejora
  futura.
- **[PHASE-7.5]** Footer del "Flujo de caja neto" en Análisis muestra
  texto estático cuando no hay periodo previo, no flecha + % como en
  Dashboard. Consciente.
- **[PHASE-7.2]** Pagination con `maxButtons=5` puede pintar 6 en
  bordes (cosmético, raro).
- **[PHASE-8.2 / 8.3]** "≈ —" cuando falta tasa — aceptable como señal
  UX, pero un tooltip explicativo sería mejor.

---

## Tech debt resuelto — patrones a recordar

Estos son aprendizajes ya **aplicados** que conviene mantener en mente
al tocar zonas afines (la fuente canónica es `lessons.md`):

- Detección RN vs SSR vs browser → `navigator?.product === 'ReactNative'`.
- 204 con cookie en FastAPI: construir la `Response` final dentro del
  handler, no inyectarla.
- Cookies tras rewrite Next.js: `Path=/`.
- `exactOptionalPropertyTypes`: declarar `prop?: T | undefined` cuando
  el padre puede pasar `undefined` explícito.
- Vitest+JSX: `esbuild.jsx: 'automatic'` en cada `vitest.config`.
- Axios: NO fijar `Content-Type` por defecto; al reintentar tras
  refresh con `FormData`, borrar el header (boundary).
- Next.js dev: `experimental.proxyTimeout` ≥ 300s para endpoints
  lentos (IA local).
- FastAPI ≥ 0.116 con `status_code=204`: declarar
  `response_class=Response` explícito y devolver `Response(status_code=204)`.
- `model_validate` post-`flush()` con `onupdate=func.now()`: hacer
  `await db.refresh(obj)` antes de serializar.
- jsdom no implementa `Blob.text()` — usar `FileReader` para tests de
  parsers de ficheros.

## Extracto sin signos: una devolución de recibo se lee como el recibo (PHASE-47.E)

`classify_import_flow` deduce la dirección del TEXTO cuando el fichero no trae
signo, y para una liquidación de tarjeta elige salida. La segunda pasada de
PHASE-46 (`resolve_flows_from_balance_chain`) sólo rellena las direcciones
AUSENTES, así que no corrige esa deducción: un `DEVOLUCION ADEUDO MENSUAL DE
TARJETA` entra como `TRANSFER_OUT`.

Consecuencias, de menor a mayor: el signo de esa fila es falso; y el dedup de
liquidaciones (PHASE-47.E1), que compara dirección precisamente para no
confundirlas, no puede distinguirlas y descartaría la devolución.

**Por qué no se arregló aquí**: el arreglo es permitir que el salto del saldo
CORRIJA una dirección deducida del texto, no sólo que la rellene. Eso toca el
invariante duro de PHASE-34 («el signo del extracto manda») desde el otro
extremo y afecta a todo lo importado, no sólo a las liquidaciones. Merece su
fase, con su golden de equivalencia.

**Mitigación vigente**: con un extracto que sí trae signos —el caso común— la
guarda de dirección funciona y hay test de regresión
(`test_a_refund_of_the_receipt_is_not_a_duplicate_of_it`).

## El cargo agregado de tarjeta: resuelto por señal, y si no la hay lo dice (PHASE-36 → PHASE-47)

> **Resuelto.** `_plans_of_charge` acota el reparto a la tarjeta del cargo con
> una cascada: una sola tarjeta con plan → esa; `settlement_account_id`
> (PHASE-47.A) → la que cobra de esa cuenta; vínculo por categoría
> (PHASE-30.4). Si tras las tres sigue habiendo varias candidatas **no se marca
> ninguna cuota** y el motivo llega a `skipped_payments`. Se conserva el
> registro porque el diagnóstico enseña el mecanismo.

`_load_aportaciones` recogía toda transacción cuya descripción case
`is_card_financed_op`, y el reparto recorría **todos** los planes con cuadro
que cuelgan de una tarjeta. Con dos tarjetas, cada cargo mensual avanzaba una
cuota de **ambas**: dos cargos → cuatro cuotas, y la deuda bajaba el doble de
lo pagado, en silencio.

Lo que desbloqueó el arreglo: la señal ya existía y no la leía nadie.
`settlement_account_id` se creó en PHASE-47.A —«qué cuenta de activo cobra cada
pasivo»— exactamente para poder saber qué cargo cierra el ciclo de qué tarjeta,
y la reconciliación seguía sin consultarla.

**Limitación que queda dicha**: un plan sólo declara de qué tarjeta cuelga
desde PHASE-35 (`parent_account_id`). Los que no lo declaran comparten un único
grupo y se reparten entre sí, que es el comportamiento previo — así el acotado
sólo muerde cuando el usuario SÍ ha declarado la pertenencia. Una tarjeta con
cuadro propio y sin hijas cae en ese grupo común: distinguirla exigiría separar
«tarjeta» de «compra a plazos», y ambas son `CREDIT_CARD`.

## Re-colgar un pasivo de una tarjeta no revisa las cuotas ya marcadas (PHASE-47.E4)

`update_account` valida el padre nuevo pero no toca el cuadro, y la guarda de
idempotencia de la reconciliación sólo mira las cuotas del pasivo DESTINO. Una
cuota marcada como pagada por un cargo que ya no le corresponde queda ahí.

Cerrarlo bien pide desmarcar las cuotas cuyo `paid_transaction_id` proceda del
pool antiguo al cambiar de padre — reversible y auditable, con su test.

## Dos ciclos que no cierran por menos de un euro (PHASE-47.E)

Medido el 2026-08-16 sobre los datos reales, con las devoluciones ya netadas:
el recibo del 4-may y el del 1-abr **cierran al céntimo**; el del 4-jun se
queda a 1,41 € y el aplazamiento de junio a 0,88 € del mejor tramo contiguo.

Sobre una ventana estricta 26→25 la diferencia es mayor (170,75 € y 39,11 €),
lo que dice que el corte del banco no cae siempre el mismo día — de ahí que la
derivación busque el tramo que cuadra en vez de recortar por fecha.

Un sospechoso concreto: `Parking aeropuerto alicante` 38,00 € del 10-jun está
en la papelera, borrada a mano por parecerse a otra idéntica del 17-may que
sigue viva. Si eran dos viajes distintos, restaurarla deja el ciclo de junio a
1,11 € de cerrar. Requiere que el usuario mire su extracto: es una pregunta
sobre su vida, no sobre sus datos.

## ~~El abono de financiación entra como INGRESO desde el extracto de la tarjeta~~ (PHASE-47.E → resuelto en 47.F)

> **Resuelto**: la regla mira ahora la DIRECCIÓN ya resuelta, no el signo crudo
> del fichero. Test verificado rompiendo la línea. Queda por lo que sigue el
> registro de cómo se diagnosticó.

`classify_import_flow` exigía `bank_sign > 0` para reconocer una financiación
entrante (`transfers/service.py`, ~línea 512). El extracto de la tarjeta **no
trae signos**, así que `bank_sign` es 0, la regla no dispara y la fila entra
como `IN` — ingreso que nadie cobró. En julio de 2026 eran 700,26 €: la app
mostraba +177,99 € de ahorro cuando lo real era −522,27 €.

La condición del signo NO es un descuido: el mismo producto aparece con signo
contrario cuando llega la cuota, y ésa sí es gasto real (PHASE-38). Lo que
falta es distinguir **dirección** de **signo**: la regla debería mirar la
dirección ya resuelta, no el signo crudo del fichero.

Corregido a mano en los datos del usuario (esa fila es ahora `TRANSFER_IN`); el
clasificador sigue igual.

## ~~Feature propuesta — el mes lo define el usuario~~ (IMPLEMENTADA, PHASE-47)

> **Hecha, y con un alcance mayor que el propuesto.** El diseño original la
> planteaba como un PRESET («Mi ciclo» junto a «Mes»), y así se construyó. El
> usuario la probó y dio el veredicto que reorientó todo: *«sigue siendo raro e
> incómodo»* — el ajuste estaba puesto y media app le seguía enseñando el mes
> natural. Ahora el día **redefine** qué es un mes: el chip desaparece, «Mes» es
> su mes en toda la app, y en Ajustes hay un check «Modo predeterminado» que
> nombra el comportamiento por defecto.
>
> Alcance final: los dos toggles, los dos navegadores, el `TimeSelector`, y las
> pantallas de Dashboard, Análisis y Deuda de web y móvil; en backend, la
> proyección de fin de mes, el runway, los presupuestos, la ventana de gasto
> estructural, el DTI, la tarjeta del dashboard y la serie mensual de deuda.
> Una declaración por capa (`packages/services/src/period/user-month.ts` y
> `backend/app/modules/personal_finance/user_month.py`) en vez de un ternario
> repetido en seis pantallas y un mes natural derivado a mano en seis agregados.
>
> Lecciones en [`lessons.md`](lessons.md): por qué un ajuste que redefine un
> concepto no debe ofrecerse además como preset, y por qué el primer test de un
> reemplazo así es el de conservación.

