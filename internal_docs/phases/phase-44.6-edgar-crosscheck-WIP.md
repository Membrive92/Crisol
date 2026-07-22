# PHASE-44.6 — Adapter EDGAR · CRUZADO + capa de ingesta pura (checkpoint)

**Estado**: 🚧 EN CURSO — cruzado COMPLETADO sobre 3 empresas reales y capa de
ingesta PURA (mapeo + normalización + cuadres) ya en el módulo. Falta el adapter
de red (`edgartools`, cache, `IngestionJob`, endpoints).
**Última sesión**: 2026-07-22.

## Dónde estamos en el módulo Inversión (fase 44)

| Fase | Qué | Commit |
|------|-----|--------|
| 44.1 | Cimientos (enums, modelos, migración, ADR-0007) | ✅ `bcd9613` |
| 44.2 | Engine Capa 1 (canonical + base_ratios) | ✅ `62866f4` |
| 44.3 | Engine capas 1.5 + 2 (evolution + forensic) | ✅ `dd842f5` |
| 44.4 | Engine Capa 3 (dividend) | ✅ `3b96bee` |
| 44.5 | Engine capas 3.5 + 4 (stress + synthesis) | ✅ `9870417` |
| 44.6 | Cruzado + `pretax_income` + ingesta pura | 🚧 sin commitear |

**El engine puro está COMPLETO y COMMITEADO** (6 capas).

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

1. ~~Resolver la decisión abierta (`pretax_income` como partida 49)~~ ✅
2. ~~Fijar el `concept_map` definitivo en el módulo~~ ✅
3. Pinear `edgartools` y montar el adapter real: descarga + cache por
   `(cik, accession)` + selección de datapoints anuales (mudar `_annual_points` /
   `_is_annual_duration` del script) + `RawFiling` por ejercicio + restatements +
   `IngestionJob` + endpoints de fundamentales.
4. Golden fixtures con estas 3 empresas → golden test end-to-end del engine.
