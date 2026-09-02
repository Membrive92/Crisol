# Crisol — Guía maestra para entender y continuar el proyecto

> **Para quién**: un modelo (o una persona) que llega SIN el contexto de las
> conversaciones anteriores y tiene que entender el proyecto y seguir
> construyéndolo. Se lee en un cuarto de hora y dice dónde está cada cosa.
>
> **Es un documento VIVO**: describe el proyecto, no un momento. Por eso no
> lleva recuentos volátiles (tests, ficheros de mypy, heads de Alembic) — los
> vigila `scripts/check_docs.py`. Lo que cambia cada sesión (qué está sin
> probar, qué sigue) vive en [`HANDOFF.md`](HANDOFF.md).
>
> **Orden de lectura recomendado**: (1) esta guía · (2) `HANDOFF.md`, el estado
> de HOY · (3) [`lessons.md`](lessons.md) **entero** — es largo a propósito: cada
> entrada es un error real que costó horas y una regla que lo impide · (4) la
> phase doc más reciente del área que vayas a tocar (`phases/`).

---

## 0. En una página

**Qué es.** Aplicación de finanzas personales, _local-first_ y privada, con
web (Next.js) y móvil (Expo) sobre un mismo backend (FastAPI + PostgreSQL).
Dos dominios:

- **Finanzas domésticas**: cuentas, transacciones, importación de extractos
  bancarios (CSV/XLSX/PDF), tickets por visión local (Ollama), categorías con
  reglas y autoaprendizaje, presupuestos, gastos fijos, **deuda** (cuadros de
  amortización, tarjetas, recibos aplazados) y **análisis** (cuenta de
  resultados del mes, patrimonio, proyección).
- **Inversión**: análisis fundamental **forense** de empresas cotizadas a
  partir de sus 10-K de la SEC (motor puro de 6 capas, veredicto argumentado,
  informe con siete pestañas) y una cartera con FIFO, dividendos y precios.

**Para quién.** Hay un solo usuario real: el propietario del proyecto
(`membrij7@gmail.com`), que es también el único tester. Habla castellano; sus
datos reales (una cuenta y una tarjeta de BBVA, préstamos, unas pocas
acciones) son el _fixture_ de verdad y la mayoría de fases nacen de un «esto
no me cuadra» suyo sobre esos datos. **Las decisiones de producto las toma
él**: cuando una lectura cambie materialmente el trabajo, se le pregunta.

**Cómo se trabaja.** Por fases numeradas (`PHASE-X.Y`): plan en
`improvements/` → código → documento de fase en `phases/` → **prueba manual
del usuario** → commit → **push directo a `main`** (no hay PRs en la práctica).
Commits en inglés con `— Refs: PHASE-X.Y`; toda la documentación en español.
Los tests se verifican **rompiendo el código** y comprobando que la rotura
entró. Nada se da por hecho sin ejecutarlo.

**Reglas de oro** (las que rompen cosas si se ignoran; todas tienen su lección):

1. **La verdad del dinero vive en `transactions.flow`** (`IN` · `OUT` ·
   `TRANSFER_IN` · `TRANSFER_OUT`), nunca en la categoría. Saldo y cashflow se
   derivan de `flow` + `account.nature` ([ADR-0004](decisions/0004-transaction-level-money-truth.md)).
2. **El extracto manda.** La cadena `saldo ± importe` que imprime el banco
   gobierna la dirección de cada movimiento por encima de texto, categoría o
   convención (PHASE-47.G); el saldo anclado (`anchored_statement_balance`) es
   un testigo externo y se audita con `make audit-balances`.
3. **Una fecha de extracto es CIVIL**: se ancla en UTC en la frontera de
   entrada (`core/civil_dates.py`, tipo `CivilDatetime`). Un naive elige zona
   por accidente (PHASE-47.J).
4. **`Decimal` para todo lo monetario; `user_id` en toda query de dominio.**
   Sin excepciones.
5. **El motor de Inversión es PURO** (sin BD, red ni reloj; hay un test por
   AST). Un `AnalysisRun` es inmutable y versionado; el tipo que lo lee describe
   **la unión de todas las versiones escritas** (PHASE-44.16).
6. **El sistema propone, el usuario declara.** Nada se persiste sin
   confirmación: ni una extracción de IA, ni una traducción de un movimiento a
   un evento de deuda ([ADR-0011](decisions/0011-system-initiated-debt-event-translation.md)).
7. **Nunca dos `pytest` a la vez** — la suite comparte UNA base (`crisol_test`)
   y eso incluye los que lance un subagente. Intérprete:
   `backend/.venv/Scripts/python.exe` (3.12, el de CI); el `python` del PATH no
   vale.
8. **Un default numérico en un campo que describe un hecho es una afirmación
   dormida** (PHASE-44.11): `None` significa «no lo sé», y el valor se deriva
   de su fuente o se exige.
9. **No reutilices una columna por la que otro módulo FILTRA** (PHASE-45): la
   semántica está en los `WHERE` ajenos, no en el nombre.
10. **Documento vivo ≠ foto fechada.** Las phase docs envejecen bien; `HANDOFF`,
    `backlog` y esta guía no llevan números que cambian cada fase
    (`scripts/check_docs.py` lo impide).
11. **Commit sólo después de la prueba manual del usuario.** Verde en la suite
    no es «hecho».

---

## 1. Mapa del repositorio

```
TrackingFinance/
├── CLAUDE.md                  # reglas de código OBLIGATORIAS (se carga siempre)
├── dev.ps1                    # arranca TODO el entorno en Windows (ver §2)
├── Makefile                   # lint · typecheck · test · verify · audit-balances
├── docker-compose.yml         # postgres (pgvector) · minio · ollama
├── knip.config.ts             # código muerto FE (cada exclusión lleva su motivo)
├── scripts/check_docs.py      # podredumbre documental (enlaces, migraciones, números volátiles)
├── .github/workflows/ci.yml   # lint + typecheck + tests + knip + build (FE) · ruff/black/mypy/alembic/pytest (BE)
├── .claude/                   # skills y comandos para Claude Code
│   ├── skills/frontend-best-practices/   # LEER antes de tocar frontend
│   └── commands/ (implement · verify · status · new-module)
├── apps/
│   ├── web/                   # Next.js App Router · rutas en app/(app)/<módulo>/...
│   └── mobile/                # Expo Router · rutas en app/(modules)/<módulo>/...
├── packages/
│   ├── types/                 # modelos + DTOs + registro de módulos (sin deps internas)
│   ├── services/              # cliente API (axios) · endpoints · hooks TanStack Query · helpers de período
│   ├── store/                 # Zustand: auth · currency · toast (+ storage.native.ts para RN)
│   └── ui/                    # tokens de diseño + formatters + capas PURAS de presentación (sin componentes)
├── backend/
│   ├── app/core/              # config · database · deps · security · storage(MinIO) · scheduler · civil_dates · rate_limit
│   ├── app/modules/           # ver §3
│   ├── alembic/versions/      # migraciones (el padre sale de `alembic heads`, nunca del nombre)
│   ├── scripts/               # data-fix y seeds con --dry-run (ver §3.5)
│   ├── tests/                 # pytest, ficheros planos test_*.py
│   ├── data/edgar_cache/      # caché local de hechos XBRL de la SEC
│   └── .venv/                 # el intérprete del proyecto
└── internal_docs/             # TODA la documentación (índice en README.md; ver §10)
```

Reglas de imports del monorepo: `types` no importa nada interno; `ui` tampoco;
`services` y `store` sólo `types`; las apps, cualquier package. Los componentes
React viven en **cada app** (`apps/*/components/`), no en `packages/ui`
([ADR-0001](decisions/0001-ui-tokens-only.md)) — lo que sí se comparte es la
lógica pura de presentación (qué filas, en qué orden, con qué texto), porque
una lista duplicada diverge igual que una fórmula (lección PHASE-44.13).

---

## 2. Arrancar, verificar, commitear

### 2.1 Arrancar (Windows, el entorno real del usuario)

```powershell
.\dev.ps1            # contenedores + migraciones + backend + web, cada uno en su ventana
.\dev.ps1 -Stop      # para todo
```

Tres cosas que `dev.ps1` resuelve y hay que saber aunque no se use:

- **El puerto del backend en desarrollo es el de `apps/web/.env.local`
  (`BACKEND_ORIGIN`, hoy `8002`)**, no el del Makefile (8000) ni el default de
  `next.config.mjs` (8001). Arrancar uvicorn en otro puerto deja la web
  proxeando al vacío y «los cambios del backend no aparecen» sin ningún error.
- En Windows es fácil dejar un uvicorn **zombi** de otra sesión: el nuevo falla
  al bindear y la web sigue hablando con el viejo, que sirve código antiguo.
  Ante «esto no cambia», comprueba el proceso antes que el código.
- El proxy de Next en dev corta a 30 s por defecto; `experimental.proxyTimeout`
  está a 5 min porque la IA local tarda más (lección PHASE-5.2).

Servicios: web `:3000` · backend `:8002` (`/docs` para OpenAPI) · Postgres
`:5432` · MinIO `:9000`/`:9001` · Ollama `:11434`. Configuración por `.env`
(claves en `.env.example`; `backend/app/core/config.py` es la fuente).

### 2.2 Verificar

```bash
# Backend — SIEMPRE con el venv, y NUNCA dos pytest a la vez
cd backend
.venv/Scripts/python.exe -m pytest tests/ -q          # suite completa (larga: redirige a fichero, no a `| tail`)
.venv/Scripts/python.exe -m mypy app/ scripts/
.venv/Scripts/python.exe -m ruff check app tests scripts alembic
.venv/Scripts/python.exe -m black --check app tests scripts alembic
.venv/Scripts/python.exe -m alembic check               # paridad modelos ↔ migraciones (sin drift)

# Frontend
pnpm typecheck && pnpm lint && pnpm test && pnpm knip

# Documentación
python scripts/check_docs.py

# Todo junto
make verify
```

Detalles que muerden:

- `cmd | tail` enmascara el código de salida y rompe el `&&` — redirige a
  fichero y consulta después. Borra el fichero de log ANTES de lanzar: un log
  reutilizado convierte una no-ejecución en un verde.
- Formatea con `prettier --write <fichero>`, no con `pnpm format` (reformatea
  el repo entero).
- `jest-dom` no está en el proyecto: los tests web usan `toBeTruthy()`.
- `exactOptionalPropertyTypes` está activo: una prop que vaya a recibir
  `undefined` explícito se declara `prop?: T | undefined`.
- CI **no** ejecuta `make verify` como tal: cada gate es su propio paso. Un
  detector cableado sólo al Makefile no corre en un push — los detectores viven
  en `pytest`/`vitest`.
- `make audit-balances` compara cada saldo con el extracto del banco. Está
  **fuera** de `verify` a propósito: audita datos, no código.

### 2.3 Commitear

- **Sólo tras la prueba manual del usuario** (o su visto bueno explícito).
- Mensaje en inglés, conventional commits, `— Refs: PHASE-X.Y`; cuerpo que
  cuente el POR QUÉ (los commits de este repo son pequeños ensayos, y se leen).
- Push directo a `main`. Las ramas `feat/phase-*` del `development-spec` son el
  diseño original; la práctica real es push directo tras la prueba. Comprueba
  con `git log origin/main..HEAD` si hay commits locales sin subir.
- Antes de cerrar una fase: phase doc en `phases/`, fila en `README.md`,
  `api/endpoints.md` y `data-model/schema.md` si tocan, `lessons.md` si hubo
  error evitable, ADR si hubo decisión no obvia. `check_docs.py` en verde.

---

## 3. Arquitectura

### 3.1 Backend (`backend/app/modules/`)

Dos niveles: **módulos de dominio** (`personal_finance/`, `investment/`) que no
se importan entre sí, y **transversales** (`auth/`, `users/`, `currency/`,
`ai/`) que cualquiera consume **sólo por su `service.py`**. Cada sub-módulo:
`router.py → service.py → repository.py → models.py → schemas.py`. Todo async;
bind params siempre; `service` recibe `db` y `user_id`, nunca el `Request`.

```
modules/
├── auth/  (+ webauthn/)      JWT access 15 min + refresh rotado (cookie httpOnly en web, SecureStore en móvil),
│                             «recordarme» 30 d, argon2id, passkeys, rate limit en login
├── users/                    perfil y preferencias — incl. `cycle_start_day` (el día en que empieza TU mes)
├── currency/                 tipos del BCE vía Frankfurter → `exchange_rates`, ÚNICA fuente de FX de la app (ADR-0009);
│                             cron nocturno ESTRICTO (PHASE-44.13: el laxo llevaba desde 11.1 sin traer nada)
├── ai/                       cliente Ollama (qwen2.5-vl) · extract_receipt · extract_bank_statement_page · /ai/health
├── personal_finance/
│   ├── accounts/             cuentas (ASSET/LIABILITY), saldos, ancla del extracto, position_history (patrimonio a fecha)
│   ├── transactions/         CRUD, filtros, papelera (soft-delete atómico del par), `flow`, `import_hash`, recategorización
│   ├── transfers/            pares (`transfer_pair_id`), link/unlink, from-source/from-debt, y `classify_import_flow`
│   │                         — el clasificador de dirección/transfer-ness de cada fila importada
│   ├── imports/              parser CSV/XLSX/PDF (smart-parsers por rol de columna), huella de cabecera (guardarraíl
│   │                         «este fichero es de otra cuenta»), preview → confirm, dedup por hash
│   ├── receipts/             ticket → MinIO → Ollama → Pydantic → confirmación → UNA transacción
│   ├── categories/ · category_rules/ · bank_mappings/ · categorization.py
│   │                         kind (income/expense) · role (GENERIC/TRANSFER/DEBT_PAYMENT/DEBT_INTEREST) · is_transfer ·
│   │                         expense_nature (AUTO/STRUCTURAL/EXCEPTIONAL); cascada: override > mapping aprendido > regla > default
│   ├── budgets/              presupuesto mensual por categoría (mes del usuario), cross-currency opt-in, avisos
│   ├── fixed_expenses/       detector de recurrentes (comercio+importe), pausa/cancela, auto-post, reconciliación
│   ├── debt/                 health (DTI, bandas BdE 30/35 %), history, amortization (cuadro francés), installments,
│   │                         reconciliation (cuotas pagadas desde el extracto), deferral (recibo aplazado), attribution
│   ├── dashboard/ · analytics/   balance vs cuenta de resultados (ADR-0006), estructural vs puntual, runway, insights
│   ├── seed/                 categorías y ~30 reglas de bancos españoles
│   └── user_month.py         UNA declaración de «qué es un mes para este usuario» (PHASE-48)
└── investment/
    ├── catalog/              securities, plazas (`venues.py`, MIC ISO 10383), analizabilidad con motivo (`capabilities.py`),
    │                         buscador en 3 capas SIN red (catálogo · índice SEC en memoria · directorio FIRDS UE/UK)
    ├── fundamentals/         adapters/edgar (edgartools pineada): hechos XBRL → 49 partidas canónicas, anclaje por ejercicio,
    │                         corrección de escala con testigo, reexpresiones
    ├── analysis/
    │   ├── engine/           PURO. base_ratios → evolution → forensic → dividend → stress → synthesis (+ valuation fuera del run)
    │   │                     catálogo de métricas, glosario junto a la fórmula, perfiles sectoriales, `version.py` con gate de huella
    │   ├── presentation/     PURO. distancia al corte, orden por severidad, procedencia, evidencia, narrativa (frases del veredicto
    │   │                     compuestas en el SERVIDOR con plantillas-dato), diff entre runs, rehidratación de runs viejos
    │   └── service/repository/router   builder BD→engine, serialización JSONB, `AnalysisRun` inmutable
    ├── thresholds/           seed convergente de bandas por sector × norma (los cortes EFECTIVOS se persisten en cada run)
    ├── portfolio/            lotes, ventas FIFO, dividendos, acciones corporativas, resumen en EUR (FX del BCE por posición)
    └── pricing/              `PRICE_PROVIDER` (yfinance por defecto, finnhub opcional); la divisa la declara el proveedor
```

### 3.2 Frontend

- **Shell de módulos**: `packages/types/src/registry/modules.ts` declara
  `dashboard`, `personal-finance`, `debt` e `investments` (activos) y
  `crypto`, `real-estate` (apagados). Web: `apps/web/app/(app)/<módulo>/…`;
  móvil: `apps/mobile/app/(modules)/<módulo>/…`. Ajustes es transversal.
- **Estado**: servidor → TanStack Query (`packages/services/src/query/hooks`,
  claves centralizadas en `keys.ts`); cliente global → Zustand
  (`packages/store`). Estilos inline/tokens (web) y RN (móvil); nunca
  `StyleSheet.create` en `packages/`.
- **Período**: `packages/services/src/period/` — `user-month.ts` es la
  contraparte del `user_month.py` del backend (hay un test que ata las dos
  aritméticas). Los filtros viajan en la URL en web.
- **Capa pura compartida** (`packages/ui/src/*.ts`): formato de importes y
  fechas civiles, textos de ciclo/aplazamiento/amortización, y TODO el
  view-model del informe de Inversión (`investment-*.ts`: pestañas, familias
  de métricas, filas, marcas, dictamen, diff, versión del run). Web y móvil
  renderizan lo mismo porque leen la misma lista.
- **Tests**: Vitest (web, packages) y `jest-expo` (móvil). Hay gates
  estáticos que recorren ficheros (ancho de página, cableado de período,
  cobertura de pantalla de las métricas) — leen código, no lo ejecutan; ver
  lección «un guardarraíl que comprueba PRESENCIA no comprueba EFECTO».

### 3.3 Infraestructura

`docker compose up -d` levanta `crisol-postgres` (pgvector/pg16),
`crisol-minio` y `crisol-ollama`. El backend corre en el host. Cron interno
con APScheduler ([ADR-0002](decisions/0002-apscheduler.md)): tasas de cambio
y auto-post de gastos fijos. Sin Dockerfile del backend ni despliegue todavía.

### 3.4 Privacidad

Ningún dato del usuario sale de la máquina. Lo único que sale: la descarga de
10-K públicos (`data.sec.gov`), tasas del BCE (Frankfurter), cotizaciones
(yfinance/Finnhub) y, si se usa, la resolución ISIN→símbolo en el alta
europea. Los tickets se guardan en MinIO local y se leen con Ollama local.

### 3.5 Scripts de datos (`backend/scripts/`)

Todos con `--dry-run`, y la lección: **un dry-run prueba la consulta, no la
escritura** — se ejecutan con `--apply` contra una fila de prueba antes de
fiarse. Los importantes: `audit_balances_vs_statement.py` (saldos vs extracto),
`normalize_civil_dates.py` (arreglo de 47.J), `backfill_header_fingerprint.py`
(sin él el guardarraíl del import nace ciego), `move_import_to_account.py` /
`undo_card_statement_into_bank.py` (un extracto en la cuenta equivocada),
`seed_listing_directory.py` (FIRDS), `seed_investment_thresholds.py`,
`reingest_security.py` / `reclassify_securities.py`, `edgar_smoke.py` y
`pricing_smoke.py` (pruebas en vivo).

---

## 4. El modelo del dinero (Finanzas domésticas)

Es la parte más curada del proyecto y donde más lecciones hay. Léelo como un
conjunto de invariantes:

| Invariante | Dónde vive | Fase / ADR |
| --- | --- | --- |
| La dirección y la transfer-ness de un movimiento están en `flow`; la categoría es descriptiva | `transactions.flow`, `signed_amount_expr` | 34 · ADR-0004 |
| Saldo = Σ signo(`flow`, `account.nature`); cashflow = Σ por `flow`; una transferencia no es ni ingreso ni gasto | `accounts/repository`, `dashboard/repository` | 34 |
| El extracto manda: el salto `saldo_i − saldo_{i−1}` gobierna la dirección; la convención de signos es del FICHERO | `transfers/service.classify_import_flow` + pasada por cadena de saldos | 46 · 47.G |
| El saldo anclado del extracto es un testigo externo; se re-deriva `opening_balance` al importar historia | `accounts.anchored_statement_balance`, `opening_balance_date` | 39 · 47.G |
| Una fecha civil se ancla en UTC; el `import_hash` se calcula sobre la fecha SIN zona | `core/civil_dates.py`, parser | 47.J |
| Una declaración manual de dirección lleva firma y sobrevive a la reimportación | `transactions.flow_declared_at` | 47.I |
| Una devolución (entrada en categoría de gasto) es gasto NEGATIVO, no ingreso — el neto no se mueve | `expense_amount_expr` (los sitios que SUMAN) | 47.H |
| Dashboard = balance (stocks); Análisis = cuenta de resultados (flujos) | `dashboard/` vs `analytics/` | 43 · ADR-0006 |
| Estructural vs puntual: `tx.is_exceptional` > `category.expense_nature` > heurística de recurrencia | `analytics/` | 37.3 · 43.2 |
| El mes lo define el usuario: `cycle_start_day` REDEFINE «mes» y «año» en toda la app (no es un preset) | `user_month.py` / `user-month.ts` | 48 |
| «¿Qué período CONTIENE este día?» y «¿cuál EMPIEZA en este mes?» son dos funciones distintas | `user_month_bounds` vs `user_month_bounds_for_anchor` | 48 |

**Deuda**, en concreto:

- Un pasivo es una cuenta `nature=LIABILITY` (`CREDIT_CARD`/`LOAN`/`MORTGAGE`).
  Con TIN + plazo + fecha se genera un **cuadro francés** persistido
  (`liability_installments`), editable, con «marcar pagada».
- **El cuadro manda** (PHASE-36): el saldo vivo de una deuda con cuadro es la
  suma del capital de las cuotas no pagadas (`resolve_liability_outstanding`),
  no lo que digan las transacciones. Una deuda sin cuadro vive de sus
  movimientos. Nunca se suman las dos fuentes (MUX por pasivo).
- La **reconciliación** marca cuotas pagadas desde los movimientos reales del
  extracto (amortización de préstamo FIFO; cargo agregado de tarjeta acotado a
  SU tarjeta vía `settlement_account_id`). Si no puede decidir, no marca y lo
  dice.
- **Compras a plazos bajo una tarjeta** (`parent_account_id`, 35): cada compra
  financiada tiene su cuadro; su CUOTA sí es gasto de caja (38); el ADEUDO
  mensual de la tarjeta y la creación de la deuda son neutros.
- **Recibo aplazado** (47.E): cuando el banco financia el recibo de la tarjeta,
  las compras del ciclo se marcan `deferred_by_account_id`. El resultado del
  mes (caja) las excluye; el desglose por categorías (gasto) las mantiene, y
  la diferencia se dice en pantalla. El ciclo se DERIVA (las compras que suman
  exacto el recibo); si no cierra al céntimo, no se marca nada.
- **«Es una amortización»** (45): un cargo del banco se enlaza a la deuda que
  paga con `amortization_source_id` (columna propia, no `transfer_pair_id`,
  porque por ésta filtran presupuestos y deuda). Si cuenta como gasto lo
  declara el usuario.
- **La financiación entrante nunca es ingreso** (46/47.F): el dinero prestado
  entra al saldo (+caja, +deuda, patrimonio igual) como `TRANSFER_IN`; a qué
  deuda pertenece lo decide el capital del cuadro, no el texto.
- `counts_as_debt=false` (40) saca del módulo de deuda una tarjeta que se paga
  íntegra cada mes sin sacarla del patrimonio.

Vocabulario del banco del usuario (BBVA) que aparece en el código: `ADEUDO
MENSUAL DE TARJETA` (liquidación, neutra) · `Operación financiada` / `Recibo
anterior … Otras financiaciones` (el banco financia el recibo: abono + cargo
espejo, neto 0, nace una deuda) · `OPERACIÓN FINANCIADA CON TARJETA` (la cuota
de una compra a plazos: gasto real) · `BIZUM`, `TRASPASO` (transferencias).
Las redacciones se declaran UNA vez y cada consumidor deriva su forma (46).

---

## 5. Módulo Inversión

**Flujo Análisis**: buscar (`/investment/securities/search`, tres capas sin
red) → adoptar (`/adopt` con `listing_key` opaca; para valores UE/UK alta
validada con cotización real) → ingerir (`/fundamentals/{id}/ingest`, job
síncrono: EDGAR → 49 partidas canónicas por ejercicio, `is_latest_view`) →
correr (`/analysis/{id}/run`: 6 capas → `AnalysisRun` inmutable con
`engine_version`, `thresholds_version` y `thresholds_used`) → informe
(`/runs/latest`, `/runs/{id}`, `/runs/compare`, `/metrics`, `/help`).

**El motor** (`analysis/engine/`), todo puro y con catálogo único de claves
(`catalog.py` es la fuente del seed de umbrales):

- Capa 1 `base_ratios` — liquidez, solvencia (S1-S8), rentabilidad, DuPont de
  5 factores con fila de comprobación. Convenciones §4.5 del DESIGN: media
  t/t−1, hueco ≠ 0 (`imputed_zero` es un tercer estado).
- Capa 1.5 `evolution` — horizontal, common-size, σ de márgenes, crecimiento
  sostenible, cruces C1-C8 (publican si se PUDIERON evaluar, 44.17).
- Capa 2 `forensic` — Beneish M, Altman Z'', Piotroski F, Zmijewski FZ (+
  `FZ_P`), accruals, Montier. En financieras salen `not_computable` con razón.
- Capa 3 `dividend` — cobertura D1-D8, calidad de caja Q1-Q5, soporte B1-B4,
  trayectoria T1-T4; ajuste REIT sobre FFO.
- Capa 3.5 `stress` — shock de ingresos, de tipos, breakeven (ST1-ST3).
- Capa 4 `synthesis` — cuatro preguntas (¿contabilidad de fiar? ¿genera caja?
  ¿cabe el dividendo? ¿aguanta un golpe?) con **portantes declarados** (sin
  uno, la pregunta sale «no auditada», gris), `SAFETY_MATRIX` →
  Conservador / Vigilar / Evitar con las diez condiciones evaluadas y
  persistidas (`met` tri-estado), confianza = completitud × frescura.
- `valuation.py` — múltiplos con la cotización viva, **fuera** del run (un
  múltiplo se mueve con el precio; el run tiene que reejecutarse igual).
- `sector_profiles.py` — calibración por sector (44.21): deltas sobre la
  banda genérica y métricas apagadas **con motivo**. Un banco ve apagadas 33.
- `glossary.py`, `score_help.py`, `flag_catalog.py` — las definiciones viven
  JUNTO a la fórmula y viajan por el catálogo, nunca se escriben en pantalla.
- `version.py` — `ENGINE_VERSION` + huella del contrato (campos, claves,
  dominios de los `Literal`): cambiar el contrato sin subir la versión falla.

**Presentación** (`analysis/presentation/`): distancia al corte y vara usada
(`origin`), orden por severidad, evidencia por bandas, **frases del veredicto
compuestas en el servidor** con plantillas-dato (`narrative.py`,
`NARRATIVE_VERSION`, goldens de texto exacto, gate «sin dígitos en una
plantilla»), `diff.py` (comparar runs: `comparable` es precondición — con
motor distinto no se emite ni un cambio de la empresa), `rehydrate.py`
(tolerar runs de motores anteriores).

**Informe** (web `investments/analysis/[securityId]`, móvil paridad): siete
pestañas en la URL (`REPORT_TABS` en `packages/ui`): Estados · Ratios ·
Evolución · Forense · Dividendo · Valoración · Veredicto. `ⓘ` por fila,
tendencia, tres charts (heatmap, deriva, dumbbell de stress; sólo web),
comparador de runs, «Cómo leer este informe», dictamen imprimible
(`?print=1`), aviso de run viejo.

**Cartera**: lotes → ventas FIFO (pool global por valor, 409 si vendes de
más) → posiciones derivadas (lotes − allocations) → resumen en divisa nativa
**y en EUR** con `fx_as_of` por posición; una posición sin cotización o sin
tasa queda fuera con su motivo, nunca se estima. `fx_rate_at_trade` se deriva
del BCE a la fecha de compra (era un `1` por defecto: dato ficticio).

**Decisiones de producto que NO se reabren** (están escritas con su motivo):
manda el motor sobre el cuaderno del usuario
([`investment-threshold-divergences.md`](investment-threshold-divergences.md));
el escenario de stress y `B3` **informan pero no puntúan** (plan 44.27, D1/D2);
«Evitar» por insolvencia exige que Altman y Zmijewski coincidan (plan 44.28,
1B); no se afloja ningún corte para que MCD salga mejor — su rojo está
sobredeterminado por tres mecanismos (auditoría del 30-ago).

Guía detallada, playbook manual y scripts:
[`investment-module-guide.md`](investment-module-guide.md). Diseño lógico:
[`improvements/DESIGN-v2-investment-module.md`](improvements/DESIGN-v2-investment-module.md).

---

## 6. Modelo de datos

Fuente de verdad: [`data-model/schema.md`](data-model/schema.md) (tabla de
migraciones con su fase + columnas comentadas). El head **se consulta con
`alembic heads`**, no se escribe. Cómo pensar las tablas:

- **Por usuario** (`user_id` + `ON DELETE CASCADE`): `accounts`,
  `transactions`, `categories`, `category_rules`, `bank_category_mappings`,
  `budgets`, `fixed_expenses`, `import_jobs`, `receipts`,
  `liability_installments`, y en Inversión `analysis_runs`, `ingestion_jobs`,
  `inv_lots` / `inv_sales` / `inv_sale_allocations` / `inv_dividends_received`
  / `inv_corporate_actions` / `inv_lot_adjustments`.
- **Globales** (sin `user_id`, [ADR-0007](decisions/0007-investment-global-tables.md)):
  `exchange_rates`, `securities`, `financial_statements`, `restatement_flags`,
  `scoring_thresholds`, `price_quotes`, `listing_directory`.
- **Auth**: `users`, `refresh_tokens` (familias rotadas), `webauthn_*`.

Columnas de `transactions` que explican medio proyecto: `flow`,
`transfer_pair_id`, `amortization_source_id`, `deferred_by_account_id`,
`statement_balance`, `flow_declared_at`, `is_exceptional`, `import_hash`,
`absorbed_as_mirror`, `deleted_at`. De `accounts`: `nature`, `opening_balance`
+ `opening_balance_date` + `anchored_statement_balance`, `apr`/`tae`/
`term_months`/`start_date`, `parent_account_id`, `settlement_account_id`,
`category_id`, `is_default`, `counts_as_debt`.

Migraciones: aditivas y reversibles; **un backfill reproduce el comportamiento
previo, nunca corrige datos** (la corrección va en un script auditado con
dry-run — lección PHASE-34). Un `default` numérico en una columna que describe
un hecho está prohibido por la lección 44.11.

---

## 7. Método de trabajo (lo que hace que este repo sea así)

1. **Todo empieza por un dato que no cuadra.** La mayoría de fases nacen de una
   captura o una cifra del usuario. Antes de tocar código se ejecuta la
   consulta contra la BD real y se cita fila a fila; «leer las filas» sin
   reconstruir la cadena de saldos ha producido dos auditorías falsas.
2. **Plan → revisión adversarial → código.** Los planes viven en
   `improvements/` (fotos fechadas). Una revisión adversarial (workflow de
   varios agentes) se lee **empezando por cuántos verificadores murieron**:
   un resultado vacío o pequeño es indistinguible de una revisión limpia.
3. **Tests que muerden.** Cada test nuevo se verifica rompiendo LA LÍNEA que
   dice proteger y comprobando que la rotura ENTRÓ (una sonda que no encuentra
   su objetivo devuelve verde). Si un test pasa con el código roto, hay otro
   camino al verde y hay que quitarlo. Cuando un umbral parte el
   comportamiento, el test cae a los DOS lados. Cuando una serie cambia de
   unidad, el primer test es el de **conservación** (la suma no se mueve).
4. **Fuente única.** Si arreglas la misma raíz dos veces, mueve la fuente de
   verdad en vez de añadir otro guardarraíl. Si dos módulos deben coincidir
   en «qué es X», UNA declaración y un gate que ate a los consumidores.
5. **Honestidad en pantalla.** Una pantalla que no puede afirmar un dato lo
   DICE («sin registro en este análisis»); inferirlo de cadenas es afirmar
   comprobaciones que nadie hizo. Ausente ≠ vacío ≠ cero. Un default
   pesimista sólo es honesto con gate de cobertura.
6. **Documentar mientras se hace.** Phase doc con la plantilla de
   `development-spec.md` §4, `lessons.md` en el mismo commit que el error,
   ADR para decisiones no obvias, `audits/` para revisiones. Lo que sólo vive
   en `HANDOFF.md` se pierde: la deuda durable va a `backlog.md`.
7. **Mismo defecto, otra app.** Web y móvil se escribieron copiando la misma
   idea; un arreglo de cableado en una se busca en la otra antes de cerrar.

---

## 8. Estado y qué sigue

El estado de HOY —qué está verde y sin probar, qué está planificado, qué
decisiones esperan al usuario, qué se verificó contra la BD— vive en
[`HANDOFF.md`](HANDOFF.md) y se reescribe cada sesión. La tabla de fases con
su estado está en [`README.md`](README.md). A grandes rasgos, el proyecto
lleva ~cincuenta fases desde abril de 2026: Finanzas domésticas está en la
recomposición del módulo de deuda (PHASE-47.x, bandeja pendiente de datos del
usuario) y en la prueba manual del mes definido por el usuario (48);
Inversión está en la tercera iteración del Veredicto (44.28, plan aprobado y
auditado, sin código) con un bug de datos por delante (44.27-E1).

---

## 9. Glosario (dominio + jerga del repo)

- **flow** — dirección del dinero de una transacción: `IN`, `OUT`,
  `TRANSFER_IN`, `TRANSFER_OUT`. La única verdad del signo.
- **par (transfer pair)** — dos patas de una transferencia interna unidas por
  `transfer_pair_id`; borrar una arrastra la otra.
- **cargo espejo** — el cargo que compensa un abono del mismo importe cuando el
  banco financia un recibo; ya no se absorbe (47.F): cada línea aporta su signo.
- **ancla / cuadrar saldo** — declarar el saldo real a una fecha; re-deriva
  `opening_balance`. El extracto lo hace solo al importar (39).
- **cadena de saldos** — la secuencia `saldo_i = saldo_{i−1} ± importe_i` del
  extracto; prueba aritmética de la dirección de cada fila.
- **ADEUDO mensual de tarjeta** — liquidación de la tarjeta contra la cuenta:
  neutra (las compras ya son gasto).
- **recibo aplazado / financiado** — el banco presta el importe del recibo y
  lo cobra en cuotas; nace una deuda y las compras del ciclo quedan
  `deferred`.
- **compra a plazos** — una compra financiada bajo una tarjeta
  (`parent_account_id`) con su propio cuadro; su cuota es gasto real.
- **cuadro (de amortización)** — tabla de cuotas (capital + interés) de un
  pasivo; «el cuadro manda» sobre las transacciones para el saldo vivo.
- **DTI / tasa de esfuerzo** — cuota de deuda ÷ ingreso; bandas del Banco de
  España 30 % / 35 %.
- **gasto estructural vs puntual** — fijo/recurrente vs excepcional; decide la
  tasa de ahorro dual y el runway.
- **mes del usuario / ciclo** — el mes empieza el `cycle_start_day` (día de
  cobro); «Mes» y «Año» en toda la app son los suyos.
- **10-K · CIK · XBRL · EDGAR** — informe anual de la SEC, identificador del
  emisor, formato de los hechos, el repositorio público.
- **FIRDS · MIC · ISIN** — registros oficiales de ESMA/FCA, código de plaza
  (ISO 10383, ojo: de segmento vs operativo), identificador del valor.
- **partida canónica** — una de las 49 líneas del `CanonicalStatement` a las
  que se normaliza cualquier filing.
- **run** — una ejecución del motor persistida (`AnalysisRun`), inmutable,
  con su versión de motor y sus cortes efectivos.
- **banda / semáforo** — verde · ámbar · rojo de una métrica según su umbral
  (por sector); `not_computable` y `not_applicable` son estados, no huecos.
- **las cuatro preguntas** — contabilidad · caja · dividendo · resistencia; la
  síntesis del run.
- **sello** — Conservador / Vigilar / Evitar (`SAFETY_MATRIX`).
- **contrafactual** — qué haría falta para salir de «Evitar»: las condiciones
  de Conservador evaluadas, no inferidas.
- **foto fechada vs documento vivo** — una phase doc o un plan vs `HANDOFF`,
  `backlog`, esta guía.
- **sonda** — la rotura deliberada de una línea para comprobar que un test la
  protege; «no mordió» significa que hay otro camino al verde.

---

## 10. Índice de documentos (qué es cada uno)

| Documento | Para qué sirve |
| --- | --- |
| [`README.md`](README.md) | Índice + **tabla de estado de todas las fases** (con enlaces a cada phase doc) |
| [`HANDOFF.md`](HANDOFF.md) | Dónde estamos HOY; se reescribe cada sesión |
| [`architecture.md`](architecture.md) | Arquitectura del sistema: módulos, invariantes, topología |
| [`development-spec.md`](development-spec.md) | Metodología, plantilla de phase doc, _definition of done_ |
| [`lessons.md`](lessons.md) | Errores reales y la regla que los impide. Leer entero |
| [`backlog.md`](backlog.md) | Deuda técnica durable y follow-ups, por área |
| [`api/endpoints.md`](api/endpoints.md) | Catálogo de endpoints por módulo |
| [`data-model/schema.md`](data-model/schema.md) | Migraciones y tablas comentadas |
| [`decisions/`](decisions/) | ADRs 0001-0011 |
| [`phases/`](phases/) | Un documento por fase entregada (as-built, foto fechada) |
| [`improvements/`](improvements/) | Planes y diseños (foto fechada); algunos ya entregados llevan aviso de re-alcance |
| [`audits/`](audits/) | Auditorías (app completa 2026-05, integridad de datos 2026-07, plan 44.28 2026-08) |
| [`investment-module-guide.md`](investment-module-guide.md) | Guía y playbook manual del módulo Inversión |
| [`investment-threshold-divergences.md`](investment-threshold-divergences.md) | Cuaderno del usuario vs motor: qué tocar si se cambia un corte |
| [`ai-context/`](ai-context/) | Contexto bajo demanda: la transcripción del cuaderno de análisis del usuario |
| [`design-explorations/`](design-explorations/) | Wireframes y exports de Stitch (referencia visual) |
| [`../DESIGN.md`](../DESIGN.md) | Tokens de diseño (cobre sobre oscuro) |
| [`../CLAUDE.md`](../CLAUDE.md) | Reglas de código obligatorias (se cargan en cada sesión) |
