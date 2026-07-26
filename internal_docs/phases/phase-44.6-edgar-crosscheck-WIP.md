# PHASE-44.6 — Adapter EDGAR · cruzado + ingesta pura + adapter (checkpoint)

**Estado**: 🚧 EN CURSO — cruzado completado, ingesta pura y adapter EDGAR
escritos y verdes. Falta la PERSISTENCIA (restatements, `IngestionJob`,
endpoints) y la prueba en vivo contra las 3 empresas.
**Última sesión**: 2026-07-22.

## Dónde estamos en el módulo Inversión (fase 44)

| Fase | Qué | Commit |
|------|-----|--------|
| 44.1 | Cimientos (enums, modelos, migración, ADR-0007) | ✅ `bcd9613` |
| 44.2 | Engine Capa 1 (canonical + base_ratios) | ✅ `62866f4` |
| 44.3 | Engine capas 1.5 + 2 (evolution + forensic) | ✅ `dd842f5` |
| 44.4 | Engine Capa 3 (dividend) | ✅ `3b96bee` |
| 44.5 | Engine capas 3.5 + 4 (stress + synthesis) | ✅ `9870417` |
| 44.6a | `pretax_income` como partida canónica 49 | ✅ `7c0558f` |
| 44.6b | Ingesta pura (concept_map + normalización + cuadres) | ✅ `2ed5b64` |
| 44.6c | Adapter EDGAR (`edgartools` + cache + anclaje anual) | 🚧 **sin commitear** |

**El engine puro está COMPLETO y COMMITEADO** (6 capas).

---

## Sesión 2026-07-23 — prueba en vivo hecha, un bug cazado

Se cerró la verificación que faltaba del checkpoint anterior: la **prueba en vivo**
contra MCD/O/JNJ (`edgar_smoke.py`), con `EDGAR_IDENTITY` ya persistida en el
`.env` del backend. El pipeline nuevo se ejecutó por primera vez contra las tres
empresas reales y **cruza con la tabla esperada** (márgenes FY2025 31,9% / 18,4% /
28,5%, EBIT `sourced` en MCD y `derived` en O y JNJ, `total_liabilities` derivado
+ balance NO VERIFICABLE en MCD, huecos = ausencias reales).

En la PRIMERA ejecución en vivo saltó un **bug real** que los tests sintéticos no
podían ver:

- **`is_financial_institution` es un MÉTODO en edgartools, no un atributo.**
  `resolve()` lo leía con `getattr(company, "is_financial_institution", False)`
  sin llamarlo → el bound method es siempre truthy → **TODA** empresa salía
  `financiera=True` (MCD y JNJ incluidas), lo que apagaba la capa forense entera.
  Arreglado en `adapters/edgar.py` con guarda `callable` + 2 regresiones que usan
  un `Company` falso con el método (la forma real). Lección en `lessons.md`.
- **Crash de encoding cp1252** del smoke en la consola de Windows (no sabe escribir
  `─ · → ⚑`). Arreglado con `sys.stdout.reconfigure(encoding="utf-8")`.

Estado de verificación tras la sesión: `edgar_smoke.py` ✅ verde contra las 3
reales · `test_investment_edgar_adapter.py` **36 passed** (34 + 2 nuevas) ·
**suite completa (985) relanzándose en `backend/.venv`** (lenta con BD en Windows;
pendiente de confirmar antes del commit). El commit de 44.6c sigue SIN hacer.

> Requisito de infra: la suite necesita Postgres arriba (`docker compose up -d
> postgres`). Docker Desktop estaba caído al empezar la sesión; una vez levantado,
> `crisol_test` ya existía en el volumen y los tests conectan.

---

## ⚠️ ESTADO AL DEJARLO (2026-07-22) — leer esto primero

### Lo que está sin commitear

El árbol de trabajo tiene el adapter EDGAR entero, verde pero **sin commit**:

```
?? backend/app/modules/investment/fundamentals/adapters/annual.py
?? backend/app/modules/investment/fundamentals/adapters/base.py
?? backend/app/modules/investment/fundamentals/adapters/edgar.py
?? backend/app/modules/investment/fundamentals/cache.py
?? backend/scripts/edgar_smoke.py
?? backend/tests/test_investment_edgar_adapter.py
 M backend/pyproject.toml        (edgartools==5.43.0 + override mypy)
 M backend/constraints.txt       (regenerado desde backend/.venv)
 M backend/app/core/config.py    (4 settings EDGAR_*)
 M .env.example                  (las mismas 4)
 M internal_docs/{README,lessons}.md + este documento
 M .claude/settings.json          ← AJENO a la fase (permisos de una sesión previa)
```

El mensaje de commit está redactado y guardado en `.git/PHASE-44.6c-commit-msg.txt`
(fuera del árbol versionado, pero justo donde se commitea):

```bash
git add backend/app/modules/investment/fundamentals/adapters \
        backend/app/modules/investment/fundamentals/cache.py \
        backend/scripts/edgar_smoke.py backend/tests/test_investment_edgar_adapter.py \
        backend/pyproject.toml backend/constraints.txt backend/app/core/config.py \
        .env.example internal_docs/
git commit -F .git/PHASE-44.6c-commit-msg.txt
```

Ojo: **no incluir `.claude/settings.json`**, que es de otra sesión y no tiene que
ver con la fase.

### Verificación: qué está confirmado y qué no

| Check | Estado |
|-------|--------|
| `ruff` · `black` · `mypy` (174 ficheros) | ✅ verde en `backend/.venv` |
| `pytest` módulo inversión (170 tests) | ✅ verde |
| `pytest` suite completa (984) | ✅ verde **antes** del último refactor |
| `pytest` suite completa tras el refactor de identidad | ⏳ **relanzada, sin confirmar** |
| Prueba en vivo contra MCD/O/JNJ | ❌ **no hecha** (ver abajo) |

El refactor pendiente de confirmar es acotado: mover la exigencia de
`EDGAR_IDENTITY` del constructor al momento de salir a la red. Toca
`adapters/edgar.py` y sus dos tests, que **sí** se re-ejecutaron a mano (34
verdes). Total colectado ahora: **985**. Relanzar para cerrar:

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q
```

### ⚠️ Usar el venv, no el `python` del PATH

`backend/.venv` es Python **3.12** (el de CI) y tiene los pines de
`constraints.txt`. El `python` global de esta máquina es 3.13 y arrastra
paquetes de otros proyectos. Verificar con el global da un verde que no vale, y
regenerar `constraints.txt` desde ahí **retrocedería** los pines de fastapi,
SQLAlchemy y pydantic. Ver la lección en `lessons.md`.

### Lo primero al retomar: la prueba en vivo

La cache del cruzado (`backend/data/edgar_cache`) **ya no está en la máquina**
—es `.gitignore`—, así que el pipeline nuevo está validado contra hechos
sintéticos con la forma real de la SEC, pero **nunca se ha ejecutado contra las
3 empresas reales**. Es el hueco de verificación más grande que queda:

```bash
cd backend
EDGAR_IDENTITY="Nombre email" .venv/Scripts/python.exe scripts/edgar_smoke.py MCD O JNJ
```

Contrastar la salida con la tabla "Resultado del cruzado" de más abajo: EBIT
`derived` en O y JNJ, cuadre de balance NO VERIFICABLE en MCD, márgenes 31,9% /
18,4% / 28,5%, y los huecos como ausencias reales (sin COGS en MCD y O, sin
activo corriente en O). La primera ejecución descarga y repuebla la cache; a
partir de ahí corre offline y sin identidad.

---

## Qué es el cruzado

Valida el mapeo `partida canónica → concepto us-gaap` contra empresas reales
ANTES de fijar el `concept_map` (ARCHITECTURE §8, punto de parada (a)).

- **Script**: `backend/scripts/validate_edgar.py` (manual, no engine, no CI).
- **`edgartools` sigue SIN instalar** — se pinea para el adapter de producción.
- **Modo offline**: `validate_edgar.py MCD:63908 O:726728 JNJ:200406` corre
  entero contra la cache local, sin `EDGAR_IDENTITY` y sin tocar la SEC.
  Con el ticker a secas (`MCD`) resuelve el CIK por red y sí exige identidad.
- **Cache**: `EDGAR_CACHE_DIR` (por defecto `backend/data/edgar_cache`, en
  `.gitignore` — los JSON pesan 3-4 MB cada uno).
- **`EDGAR_IDENTITY`**: no se persiste en ningún fichero, sólo viaja en el
  `User-Agent`. Sólo hace falta para descargar por primera vez.

### Empresas del cruzado

| Ticker | CIK | Qué valida |
|--------|-----|-----------|
| MCD | 0000063908 | Deuda + leases; equity NEGATIVO (−1.791 M$ por buybacks) |
| O (Realty Income) | 0000726728 | **REIT** → rama FFO/D6; balance NO clasificado |
| JNJ | 0000200406 | Impairments/venta de negocios → `ebit_clean` |

## Decisiones CERRADAS por el usuario (2026-07-21)

1. **EBIT derivado** = pretax + `interest_expense`. Se aplica sólo si
   `OperatingIncomeLoss` sale hueco. **Provenance = `derived`.**
2. **`total_liabilities` derivado** = `total_assets − equity` cuando falta
   `Liabilities`. **Provenance = `derived`.**
3. **Política REIT**: liquidez, COGS y demás métricas que exigen balance
   clasificado salen `not_computable` con razón — nunca imputadas. El análisis
   del REIT se apoya en la rama FFO/D6 de la Capa 3.
4. **`pretax_income` entra como partida canónica 49** (era la decisión abierta
   del checkpoint anterior; cerrada con un SÍ e implementada).

### Efectos colaterales de (1) y (2), ya implementados

- **(1) mataría la bandera `ebt_divergence`**: con el EBIT derivado,
  `ebit − interest_expense ≡ ebt` por construcción. `ebt_divergence_flag` ahora
  **no se evalúa** si `ebit` no es `SOURCED`, en vez de emitir un falso "cuadra".
- **(2) mata el cuadre de balance**: activo ≡ pasivo + patrimonio por
  construcción. `validation.py` informa `balance_identity_unverifiable`, no OK.

## Lo hecho en esta sesión

### a) `pretax_income`, la partida canónica 49

Con el pretax REPORTADO, el EBIT se deriva de un dato *sourced* en vez de
reconstruirlo con `net_income + taxes` —que ignora minoritarios y actividades
discontinuadas (en Realty Income, 11,2 M$)— y `ebt_divergence` recupera dos
fuentes independientes que comparar.

- `canonical.py` + `models.py` + migración `bb2c58d0e3f7a1` (aditiva, nullable).
- `derivations.ebt` prefiere el reportado y cae a la reconstrucción.
- Bandera nueva `ebt_reconstruction_divergence` (severidad `info`): salta si el
  pretax publicado se aparta >2% de `net_income + taxes`, que es justo lo que
  delata minoritarios o discontinuadas fuera del modelo.

### b) La capa de ingesta PURA (paso 2 del plan)

El `concept_map` deja de vivir en el script y pasa al módulo, con los mecanismos
que destapó el cruzado:

| Fichero | Qué |
|---------|-----|
| `fundamentals/adapters/concept_map.py` | Los 4 mecanismos + lista blanca de ceros. Se auto-audita al importar |
| `fundamentals/normalization.py` | Hechos XBRL → `CanonicalStatement` con procedencia y traza |
| `fundamentals/validation.py` | Cuadres → `QualityFlag` (nunca abortan la ingesta) |
| `tests/test_investment_ingestion.py` | 59 tests, sin red ni BD |

Orden de resolución: **mapeo** (candidatos us-gaap → combinación → `dei`) →
**líneas netas** → **ceros por ausencia** → **derivaciones**. Los ceros van antes
que las derivaciones porque una derivación puede necesitar un cero legítimo (sin
deuda no se publica el gasto financiero, y el EBIT derivado lo necesita).

Hallazgo de esta sesión: **la imputación condicional de `interest_expense` es más
estrecha de lo que parecía**. Como `long_term_debt` NO está en la lista blanca (a
propósito: un cero por ausencia ahí no daría un hueco visible sino una empresa
*sin deuda* con el bloque de apalancamiento impecable), un condicionante
desconocido no cuenta como cero. Sólo se imputa si el emisor publica su deuda a
largo explícitamente en cero. Encadenar ausencias —no publica deuda, luego no
tiene, luego no paga intereses— es justo como se fabrica una empresa impecable
que no lo es.

### c) El adapter EDGAR (paso 3 del plan)

`edgartools==5.43.0` **pineada** (decisión del usuario, 2026-07-22). El reparto
de responsabilidades es explícito:

| Quién | Qué |
|-------|-----|
| `edgartools` | resuelve el ticker (SIC, REIT, financiera) y parsea el JSON de la SEC en hechos con periodo, unidad y `accession` |
| Nosotros | descargamos y guardamos el CRUDO (`cache.py`, evidencia de auditoría Dec.18 — la librería no lo devuelve) |
| Nosotros | anclamos los hechos a ejercicios (`adapters/annual.py`) |

| Fichero | Qué |
|---------|-----|
| `adapters/base.py` | `SecurityIdentity`, `XbrlFact`, `FilingRef` + Protocol |
| `adapters/annual.py` | PURO: hechos → `RawFiling` por ejercicio |
| `adapters/edgar.py` | descarga, identidad, conversión desde el modelo de la librería |
| `cache.py` | payloads crudos por CIK, escritura atómica |
| `scripts/edgar_smoke.py` | verificación en vivo del pipeline completo |
| `tests/test_investment_edgar_adapter.py` | 34 tests, sin red |

**Por qué el anclaje no lo hace la librería.** `get_annual_fact(concept,
fiscal_year=N)` parece justo esto y no lo es: su `fiscal_year` sale del campo
`fy` de `companyfacts`, que es el ejercicio del INFORME, no el del dato. En el
10-K de 2024 las tres columnas comparativas viajan con `fy=2024`, así que pedir
2023 devuelve la cifra ORIGINAL de 2023 y nunca la reexpresada — que es
justamente la que el análisis quiere. Nuestro anclaje usa la fecha de cierre
(`period_end`), las reglas validadas en el cruzado (10-K + `fp=FY`, flujos de
350-380 días para no dejar fuera los años de 52/53 semanas) y da la vista
vigente: gana el filing más reciente.

**Dos trampas que destapó probar la librería en vez de suponerla:**

1. `edgartools` devuelve el concepto YA cualificado (`'us-gaap:Assets'`) pero
   expone `taxonomy` por separado. Componerlo otra vez daba
   `'us-gaap:us-gaap:Assets'`: ninguna partida habría encontrado su concepto y el
   resultado no habría sido un error, sino **una empresa entera en blanco**.
2. La unidad por acción no es `USD/shares` (como la escribe la SEC) sino
   `USD per share` (como la reetiqueta la librería). El filtro por lista literal
   no cazaba nada; ahora se detecta por forma.

Ambas están fijadas con un test que recorre el pipeline COMPLETO desde un
payload con la forma real de la SEC, pasando por el parser de verdad.

**Un tercer agujero, propio:** el fin de ejercicio se decidía con el hecho de
fecha más reciente del filing. Un 10-K puede traer saldos POSTERIORES al cierre
(deuda emitida en enero), que habrían creado un ejercicio fantasma sin partidas
y hecho desaparecer el de verdad. Ahora lo deciden los FLUJOS, que no pueden
terminar después del cierre.

**Identidad SEC**: si falta, `edgartools` la pide por consola con `input()`. En
un backend eso no es un error visible, es una petición colgada para siempre. El
adapter la fija él mismo y falla con un mensaje accionable — pero **al salir a la
red, no al construirse**: con el crudo ya cacheado se puede reingerir entero sin
identidad, que es justo para lo que sirve guardarlo (re-derivar tras cambiar el
mapeo, montar fixtures, reproducir un análisis viejo).

**Dependencias**: `edgartools` arrastra pandas, pyarrow, numpy, lxml y ~25 más.
`constraints.txt` regenerado desde `backend/.venv` (Python 3.12, el de CI) — el
diff es sólo adiciones, ningún pin existente se movió. `edgar` no se importa en
el arranque de la app: el adapter lo carga dentro de sus métodos, así que el
backend sigue levantando aunque la librería falle.

## Los cuatro mecanismos (por qué "una lista de candidatos" no bastaba)

1. **Combinación** (`COMBINED_MAP`): `debt_change` no lo reporta NINGUNA con una
   sola etiqueta — hay que sumar emisiones y restar amortizaciones. MCD −72 M$ ·
   O +1.064,6 M$ · JNJ +9.637 M$. También el pretax de MCD (Domestic + Foreign,
   `sourced`: es el total que la empresa no publica agregado) y
   `lease_liabilities_noncurrent` con el balance sin clasificar (`derived`: la
   parte corriente es un supuesto, no una identidad).
   ⚠️ Trampa: `LongTermDebtMaturitiesRepaymentsOfPrincipal*` **no** es un flujo
   de caja, es el calendario de vencimientos de la memoria. Hay un test que
   impide que vuelva a colarse.
2. **Namespace `dei`** (`DEI_MAP`): `shares_outstanding_eop` no está en us-gaap
   para MCD ni JNJ; vive en `dei:EntityCommonStockSharesOutstanding` (portada).
   Su `end` es la fecha de cubierta, POSTERIOR al cierre fiscal.
3. **Normalización de signo** (`SIGN_FLIP`): O reporta
   `AccumulatedDistributionsInExcessOfNetIncome` en positivo (10.528 M$) siendo
   un saldo DEUDOR del patrimonio.
4. **Líneas netas** (`NET_LINE_FALLBACKS`): JNJ publica
   `GainLossOnSalesOfAssetsAndAssetImpairmentCharges` (263 M$), una línea NETA
   que mezcla plusvalías y deterioros. Como `ebit_clean = ebit + impairments −
   gains`, alimentar las dos partidas con ella doblaría el ajuste: se prefieren
   las etiquetas partidas y, si sólo está la neta, alimenta `impairments` y deja
   `gains` a cero con aviso.

## Resultado del cruzado

Partidas con hueco: **26 → 20**. Cuadres:

| | MCD | O | JNJ |
|---|---|---|---|
| cuadre balance | NO VERIFICABLE (pasivo derivado) | 0,94% OK | 0,00% OK |
| margen neto | 31,9% OK | 18,4% OK | 28,5% OK |
| `ebit` | `OperatingIncomeLoss` 12.393 M$ | DERIVADA 2.278,8 M$ | DERIVADA 33.552 M$ |

Los 20 huecos restantes son **ausencias reales**, no fallos de mapeo: balance no
clasificado del REIT (`current_assets`, `current_liabilities`, `inventory`,
`ltd_current_portion`, `deferred_tax_liabilities`), servicios sin COGS (MCD, O),
sin I+D (MCD, O), sin autocartera ni recompras (O), y JNJ sin línea de prima de
emisión en balance.

### Cabos sueltos del cruzado — RESUELTOS

Eran **ausencia real del dato, no un filtro demasiado estricto**:

- **JNJ `OperatingIncomeLoss`**: existe con 12 puntos 10-K/FY, pero el último
  cierra en **2015**. JNJ dejó de publicar línea de resultado operativo.
- **O `InterestExpense`**: 215 datapoints, el último 10-K/FY es **FY2023**.
  Realty Income migró a **`InterestExpenseOperating`** (1.134,9 M$ en FY2025).

`_annual_points` (form 10-K + fp FY) y `_is_annual_duration` (350-380 días)
quedan **validados**: los años fiscales de 52/53 semanas (JNJ cierra el 28-dic,
363 días) entran sin problema. Esa lógica todavía vive en el script y hay que
mudarla al adapter.

## Cómo seguir

Hecho: 1-3. Pendiente: 4-8.

1. ~~Resolver la decisión abierta (`pretax_income` como partida 49)~~ ✅ `7c0558f`
2. ~~Fijar el `concept_map` definitivo en el módulo~~ ✅ `2ed5b64`
3. ~~Pinear `edgartools` y montar el adapter (descarga + cache + anclaje anual)~~ ✅ sin commitear

4. **Cerrar la verificación** (bloquea el commit): relanzar la suite completa en
   `backend/.venv` y hacer la prueba en vivo con `edgar_smoke.py` (ver "ESTADO AL
   DEJARLO"). Si el smoke destapa algo, se arregla antes de commitear.

5. **`restatements.py`** (Dec.6). La mitad difícil ya está:
   `annual.restated_periods(facts)` devuelve qué ejercicios reportó más de un
   10-K, que es DÓNDE mirar. Falta comparar los valores entre accessions y
   persistir `RestatementFlag` (el modelo existe desde 44.1). Ojo: el criterio
   no puede ser "cambió el número" a secas — un redondeo distinto no es una
   reexpresión; hace falta un umbral relativo, como el 2% de las otras banderas.

6. **Persistencia e ingesta**: repository/service/router de `fundamentals`,
   `IngestionJob` (el modelo existe desde 44.1) y endpoints. Aquí entra la
   decisión de qué es `is_latest_view` en BD — `annual.build_raw_filings` ya
   resuelve la vista vigente en memoria, así que la BD debe reflejar ESA
   decisión y no reimplementarla.

7. **Golden fixtures** con MCD/O/JNJ → golden test end-to-end del engine
   (ARCHITECTURE §7). Ojo al tamaño: el `companyfacts` crudo pesa 3-4 MB por
   empresa, así que la fixture debe podarse a los conceptos mapeados antes de
   commitearla. El `AnalysisRun` serializado es el golden; un cambio de output
   sin bump de `ENGINE_VERSION` debe romper el test.

8. **Seed de `scoring_thresholds`**, diferido desde 44.1 y todavía sin hacer.
   `catalog.py` agrega las métricas de las 6 capas y es la fuente única de las
   `metric_key`, así que el seed sale de ahí — no de una lista escrita a mano.

### Cabos sueltos conocidos (no bloquean, pero conviene no olvidarlos)

- **Enmiendas `10-K/A`**: `ANNUAL_FORMS` sólo acepta `10-K`. Una reexpresión
  entra igual por la comparativa del 10-K siguiente, pero una enmienda que no
  llegue a repetirse en el informe posterior se pierde. Decidido así a
  propósito (mezclarlas exige saber qué partidas toca cada una).
- **Ejercicios sin 10-K propio**: los años que sólo aparecen como comparativa se
  descartan (no tienen portada ni `accession` propio). Con `limit=5` no duele,
  pero acorta la serie disponible para las ventanas largas de la capa evolutiva.
- **`edgartools` en memoria**: su cache interna de `EntityFacts` es de tamaño 1 y
  cada empresa grande ocupa 40-80 MB. Nosotros no la usamos (parseamos con
  `EntityFactsParser` directamente), pero si algún día se usa `get_company_facts`
  hay que llamar a `clear_company_facts_cache()` en un proceso largo.
- **Rate limit SEC** (~10 req/s): el adapter hace una sola descarga por empresa,
  así que hoy no aplica. Al ingerir varias empresas seguidas hay que serializar
  (Dec.18).
