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
> - 2026-07-24: alta de **UI-2026-07-24 — auditoría responsive** (aplicada, sin
>   commitear, pendiente de validación visual).
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

## AUDIT-2026-07-13 — integridad de datos (pendiente de verificar)

Hallazgos de la auditoría de integridad de datos sobre la BD del usuario
`membrij7@gmail.com`, disparada por una revisión manual del drill-down de
categoría. Inventario completo en
[`audits/2026-07-13-data-integrity-pending-check.md`](audits/2026-07-13-data-integrity-pending-check.md).
**Ninguno corregido todavía.**

- ✅ ~~🐛 **Selector temporal desincronizado (UTC vs local)** en el drill-down
  de categoría~~ **CORREGIDO 2026-07-13** (`analysis/category/[id]/page.tsx`
  ahora construye el rango con `Date.UTC`; typecheck+lint+test verdes).
  Pendiente verificación manual + commit.
- 💾 **Doble conteo de gasto** en compra financiada de Taxdown (239 € cuenta
  como gasto en "Impuestos" Y en las cuotas). Contradice el modelo PHASE-38.
- 🟡 **Pares de transferencia incoherentes** en operaciones financiadas.
  **4a CORREGIDO 2026-07-13** (pata BBVA de la compra financiada de 824,77 €
  volteada `TRANSFER_OUT`→`TRANSFER_IN`; BBVA −11.777,93 → −10.953,16 €). Queda
  **4b** (Western Union de 215,99 € con `TRANSFER_IN` de signo dudoso, pendiente
  extracto) + guardarraíl de código para forzar el par canónico OUT↔IN.
- 💾 **Saldos sin `opening_balance` real** (BBVA −11.322,94 € con apertura 0;
  Wise con apertura −5.000 € de apaño + 210 € de patas huérfanas).
- 🔍 **Verificar contra extracto**: hueco de tarjeta en abril 2026; posibles
  duplicados en BBVA (12/03 dos cargos de 900 €; 18/03 dos de 1.000 €).

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
- **[Ola 6] Reorg físico backend del módulo deuda (sin cambio de
  comportamiento)**. Quedan los items puramente cosméticos del epic de
  consolidación: mover `accounts/debt_health.py`→`debt/health.py` y
  `accounts/debt_history.py`→`debt/history.py` (reubicación + arreglar
  imports en `accounts/router.py` y `debt/service.py`), extraer los
  helpers de fecha duplicados a `core/dates.py` (`_today_utc`,
  `_start_of_month`, `_end_of_month`, `_add_month`, `_format_month`,
  `_month_start_utc`/`_end_utc`), y re-exportar `converted_amount_expr`
  desde `personal_finance/_shared/money.py`. Las **correcciones reales**
  del epic (orphan-unlink, invalidación `debt.all`, inversión de
  dependencias, lógica fuera de routers) ya están hechas (Ola 6a/6b); la
  consolidación de API/hooks/keys del **frontend** también (Ola 6b). Esto
  es relocalización mecánica sin beneficio de comportamiento — recipe
  exacto en el mapeo `ola6-mapping` del workflow. URL `/accounts/debt-*`
  se mantiene (cambiarla a `/debt/*` rompe contrato; migración versionada
  futura).
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
- **[PHASE-44.9] Informe sin charts**: el informe ya tiene siete pestañas con
  los estados financieros, las matrices de métricas multi-año, los desgloses
  forenses y el dictamen auditable — pero **todo en tablas**. Siguen diferidos
  los gráficos: evolución common-size, escenarios de stress y heatmap de Δ%.
- **[PHASE-44.9] Sin charts en ninguna de las dos pantallas.** Es lo único
  grande que sigue siendo «todo en tablas»: evolución common-size, escenarios de
  stress y heatmap de Δ%.
- **[PHASE-44.13] La pestaña del informe de móvil vive en estado local**, no en
  la URL. Expo Router no tiene aquí el query param de la web y forzarlo obligaría
  a una ruta por pestaña. Las CLAVES sí son las mismas (`veredicto`, `estados`…,
  en `REPORT_TABS`), así que habilitar enlaces profundos no exige renombrar nada.
- **[PHASE-44.9] La tabla de cartera sigue sin test de componente.** El informe
  sí tiene, en web y en móvil.
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

- **[PHASE-44.15] El combobox no hace auto-scroll de la opción activa.** Con el
  `limit=20` del buscador la lista es corta y no se ha visto necesario; con
  listas largas la opción activa podría quedar fuera de vista.
- **[PHASE-44.15] El alta de compra en móvil pide la fecha como texto**
  (`AAAA-MM-DD`, con validación) en vez del date-picker nativo que Finanzas
  Domésticas ya usa desde PHASE-14.3. Reutilizarlo es barato.
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
- **[PHASE-44.10] `S7` está calibrada sólo para negocios con activo tangible.**
  La banda 1-2 del cuaderno sale de que el pasivo financie entre la mitad y dos
  tercios del activo. En financieras se siembra `applies=False` (el número se ve,
  sin semáforo), pero en **intensivas en intangibles** —software, farmacia— el
  rango también se queda corto y ahí sí se aplica. La solución real es calibrar
  por sector: son filas de `scoring_thresholds`, no código.

### Calibración del engine (necesita empresas reales ingeridas)

- **[PHASE-44.3] Calibrar el corte de C2 ("beneficio sin caja")**. La regla
  del DESIGN §5 dice "NI crece y CFO plano/cae" sin definir **qué es plano**.
  Se implementó el criterio estricto (crecimiento de CFO ≤ 0) para no generar
  falsos positivos, con el efecto de que un CFO creciendo un 1% frente a un
  resultado neto creciendo un 30% **no dispara** la bandera — que es
  exactamente el patrón que la regla quiere cazar. Decidir el umbral real
  (¿diferencia de crecimientos > N pp?) cuando haya empresas reales ingeridas
  contra las que medir el ruido. Mismo tipo de calibración que pide C6.
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
