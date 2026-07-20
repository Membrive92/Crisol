# PHASE-44.2 — Engine de análisis, Capa 1 (métricas base)

**Estado**: ✅ código completo y verde (pendiente prueba manual del usuario)
**Rama**: trabajo directo sobre `main` (workflow del proyecto)
**Fecha**: 2026-07-20

## Objetivo

El **engine puro** del módulo Inversión (ARCH fase 40.2): modelo canónico,
convenciones de cálculo, derivaciones §4.4 y las métricas base de la Capa 1.
Sin BD, sin red, sin reloj — determinista y testeable con sintéticos.

Fuente de verdad: [`improvements/DESIGN-v2-investment-module.md`](../improvements/DESIGN-v2-investment-module.md)
§4 (canónico, derivaciones, convenciones) y §5 (catálogo de métricas);
[`improvements/ARCHITECTURE-investment-module.md`](../improvements/ARCHITECTURE-investment-module.md)
§4 (tipos, orquestación, versionado) y §7 (testing).

## Qué se implementó

- **`fundamentals/canonical.py`** — `CanonicalStatement` (frozen dataclass con
  las 48 partidas, todas `Decimal | None`), enum `Provenance`
  (`sourced`/`derived`/`imputed_zero`/`estimated`) con `combine_provenance()` (gana el más
  degradado), y `CANONICAL_ITEMS` como catálogo único de nombres de partida.
  `get()` valida el nombre: un typo revienta en vez de devolver un `None`
  silencioso que convertiría la métrica en `not_computable` sin que nadie lo note.
- **`analysis/engine/version.py`** — `ENGINE_VERSION = "1.0.0"` [Dec.7].
- **`analysis/engine/types.py`** — `SecuritySnapshot`, `StatementSeries`
  (valida orden ascendente y años únicos; `prior()` NO salta huecos),
  `Amount` (importe en tránsito que arrastra QUÉ partida falta), `MetricResult`
  (invariante: `value is None` ⟺ `status == "not_computable"`, y entonces
  `reason` obligatoria), `Flag`, `Verdict` (declarado para la capa 4),
  `ThresholdSpec` con `band_for()`.
- **`analysis/engine/conventions.py`** — `DAY_COUNT=365`; aritmética que propaga
  huecos (`add`/`subtract`/`multiply`/`divide`); guardas de denominador (cero
  siempre, no-positivo donde el ratio engaña); `avg_balance` y `avg_derived`
  con la regla del primer año → `approximation` [Dec.3].
- **`analysis/engine/derivations.py`** — las 17 derivadas del §4.4:
  `total_debt` (+ variante con leases), `net_debt`, `ebitda`, `ebit_clean`,
  `ebt`, `effective_tax_rate`, `nopat`, `invested_capital`, WC dual
  (`wc_total`/`wc_operating`), `fcf_cfo`, `fcf_ebitda`, `maintenance_capex`
  (siempre `estimated`), `ffo`, `dividend_per_share`, más las banderas
  `ebt_divergence` y `fcf_divergence`.
- **`analysis/engine/base_ratios.py`** — `METRIC_CATALOG` (fuente única de las
  `metric_key` y sus bandas por defecto) + `compute(series, thresholds=None)`
  que calcula las **27 métricas** para CADA ejercicio, más la descomposición
  DuPont del ROE.
- **Tests** (`tests/test_investment_engine.py`, 71 tests, 4,0 s sin BD).

## Flujo técnico

```
CanonicalStatement (×N años)  ─┐
SecuritySnapshot              ─┼─→ StatementSeries ─→ base_ratios.compute()
as_of                         ─┘                            │
                                                            ├─ derivations §4.4
                     ThresholdSpec (BD o defaults) ────────→┤
                                                            ▼
                                          BaseRatiosResult(metrics, flags, dupont)
```

El contrato clave: **una métrica nunca desaparece y nunca miente**. Si falta un
input sale `not_computable` con la razón en español nombrando la partida; si el
denominador va degradado (primer año sin t−1) sale `approximation`. Jamás un 0
implícito, jamás una excepción, jamás una clave ausente (§4.5).

## Archivos clave

- `backend/app/modules/investment/fundamentals/canonical.py`
- `backend/app/modules/investment/analysis/engine/{__init__,version,types,conventions,derivations,base_ratios}.py`
- `backend/tests/test_investment_engine.py`

## Migraciones

Ninguna. Esta fase no toca el schema.

## Verificación

- [x] `ruff check app/ tests/` · `black --check` · `mypy app/` (159 ficheros) verdes.
- [x] `pytest tests/test_investment_engine.py` → **71 passed** en 4,0 s (sin BD:
      el engine es puro).
- [x] Suite BE completa → **764 passed** (693 previos + 71 nuevos), 14m14s,
      excluyendo `test_ai_*` (requieren Ollama arrancado).
- [ ] Prueba manual del usuario: no procede todavía (sin endpoints ni UI; el
      engine no es alcanzable desde la app hasta la fase de ingesta + servicio).

Cobertura de los tests (ARCHITECTURE §7): valor esperado con importes conocidos
sobre una empresa sintética cuadrada; `None` en input → `not_computable` con la
partida nombrada; primer año → `approximation`; guardas (patrimonio ≤ 0,
denominador 0); bordes de banda; casos especiales de S5; propagación de
procedencia; invariantes de los tipos; y un test de **pureza** que parsea el AST
de cada módulo del engine y falla si aparece un import de `sqlalchemy`, `httpx`,
`requests`, `asyncpg` o `app.core.database`.

## Decisiones tomadas

- **El catálogo de métricas vive en el engine**, no en el seed. `METRIC_CATALOG`
  es la fuente única de las `metric_key` y de las bandas por defecto de §5; el
  seed de `scoring_thresholds` se construirá a partir de él. Esto es lo que hace
  seguro el diferido acordado en PHASE-44.1: las claves sembradas no pueden
  divergir de las que el engine calcula porque son las mismas.
- **`Amount` como tipo intermedio.** Existe para que un hueco viaje con el
  NOMBRE de lo que falta desde la partida hasta el `MetricResult`. Sin él, la
  razón de un `not_computable` sería "falta algún input", que no es accionable.
- **Severidad `info` para `ebt_divergence`.** El DESIGN §4.4 pide "flag" sin
  fijar severidad. Es una señal sobre la CALIDAD DE LOS DATOS (partidas no
  modeladas), no sobre la salud de la empresa: mezclarla con las alarmas de
  negocio daría rojo por un mapeo incompleto. `fcf_divergence` sí es `amber`
  porque lo fija la ARCHITECTURE §4.2.
- **S5 con caja neta devuelve 0 años**, no el cociente negativo: el §5 pide
  "verde 'caja neta'", y un `lower_better` sobre 0 lo pinta verde de forma
  natural sin caso especial en la capa de presentación.
- **`prior()` no salta huecos.** Con 2020 y 2024 en la serie, el "anterior" de
  2024 es `None`, no 2020: una media (t, t−4) no es una media. Cae a
  `approximation` con su razón.
- **Bandas como ratios, no porcentajes.** R5/R6/R7/R9/R9b se calculan y umbralan
  en tanto por uno (0,12 y no 12); el ×100 es de presentación.
- **Cuarta procedencia `imputed_zero`** (DESIGN §4.5, revisión del 2026-07-20).
  En XBRL las empresas omiten los conceptos que valen cero, así que tratar toda
  ausencia como hueco dejaría `total_debt` sin calcular en compañías sanas. La
  política de imputación (lista blanca) **vive en la ingesta**, no en el engine:
  aquí solo se declara el valor del enum y se propaga vía
  `CanonicalStatement.item_provenance`, que ya existía. Orden de degradación
  elegido: `sourced < derived < imputed_zero < estimated` — `derived` aplica una
  identidad exacta (no añade supuestos), `imputed_zero` supone un dato ausente
  (supuesto fuerte con prior alta) y `estimated` es un proxy con fórmula propia.
  Que esté por encima de `sourced` es lo que garantiza el requisito del §4.5 de
  que una imputación no cuente como dato sourced en la completitud.

## Limitaciones conocidas / follow-ups

- **Recuento de métricas** (cerrado 2026-07-20): el §5 decía "28" con filas que
  sumaban 27. El DESIGN se corrigió a **27** (16 plantilla + 4 `[+]` + 7 `[++]`)
  y añade la nota de que la descomposición DuPont NO cuenta como métrica (es
  salida explicativa, sin `metric_key` umbralable). El código ya implementaba
  las 27; no hubo cambio de código. Se aplicó además el ajuste textual que el
  DESIGN reclamaba al ARCHITECTURE §9 (fila 40.2: "20 métricas base" → 27).
- **Ausencia vs cero** (cerrado 2026-07-20): resuelto en el DESIGN §4.5 +
  ARCHITECTURE §3.3 con una política de imputación. Ver "Decisiones tomadas".
- Sin `evolution.py` (capa 1.5): las métricas de actividad (A1-A5) y los
  márgenes (R1-R4) salen sin banda a propósito — se juzgan por deriva, y la
  deriva es capa 1.5.
- Sin golden test todavía: exige fixtures de EDGAR reales (§7), que llegan con
  el adapter en 44.4.

## Estado del árbol de trabajo

**Sin commitear**, acumulado sobre PHASE-44.1 (que también sigue sin commitear
por decisión del usuario del 2026-07-20).

## Próxima fase

**PHASE-44.3 (ARCH 40.3)** — capas 1.5 y 2: `evolution.py` (horizontal, vertical
common-size, reglas de coherencia C1-C6) y `forensic.py` (M-score de Beneish,
Z''-score de Altman, F-score de Piotroski, accruals). Con dos reglas duras ya
fijadas: `is_financial=True` → M/Z salen `not_computable` con
`reason="modelo no aplicable a financieras"` (nunca se omite la clave), y los
umbrales respetan `applies`/`model_variant`.

Al llegar a **44.4** (adapter EDGAR) hay que PARAR y pedir al usuario el cruzado
de `validate_edgar.py` contra 3 empresas reales antes de fijar el `concept_map`
(ARCH §8).
