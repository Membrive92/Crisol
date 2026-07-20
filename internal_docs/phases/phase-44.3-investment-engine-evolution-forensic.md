# PHASE-44.3 — Engine: capas 1.5 (evolutiva) y 2 (forense)

**Estado**: ✅ código completo y verde (pendiente prueba manual del usuario)
**Rama**: trabajo directo sobre `main` (workflow del proyecto)
**Fecha**: 2026-07-20

## Objetivo

Las dos capas que convierten los ratios de la Capa 1 en un diagnóstico: la
**evolutiva** (qué se mueve y qué se separa de qué) y la **forense** (modelos
académicos de manipulación contable y de quiebra). Sigue siendo engine PURO.

Fuente de verdad: DESIGN §5, capas 1.5 y 2; ARCHITECTURE §4.2 (reglas duras).

## Qué se implementó

- **`engine/metrics.py`** (infraestructura extraída de `base_ratios`):
  `MetricDefinition`, `thresholds_from()` y `to_metric_result()`. Las tres capas
  declaran su catálogo con el mismo mecanismo.
- **`engine/evolution.py`** — Capa 1.5:
  - **E1 horizontal**: YoY, CAGR y base 100 de las 7 magnitudes (ventas, EBIT
    limpio, resultado neto, CFO, caja libre, dividendos, acciones).
  - **E2 vertical (common-size)**: balance sobre activo total, P&L sobre ventas.
  - **E3** estabilidad del margen EBIT (σ en pp, banda <2 · 2-5 · >5) y **E4**
    tasa de crecimiento sostenible `g = ROE × (1 − payout)`.
  - **C1-C8**: los ocho cruces de coherencia, más la bandera
    `growth_externally_funded` (E4 vs CAGR de ventas).
- **`engine/forensic.py`** — Capa 2: **M-Score** de Beneish (8 variables),
  **Z''-Score** de Altman (1995, book-based), **F-Score** de Piotroski (9 tests),
  **accruals** de Sloan, **F5** (riesgo de fondo de comercio), **F6** (anomalía
  del circulante), **FZ** (X-Score de Zmijewski) y **F7** (C-Score de Montier).
  Cada score compuesto devuelve además su `ScoreBreakdown`.
- **`engine/catalog.py`** — agrega los tres catálogos: **37 métricas**
  (27 + 2 + 8) con claves únicas. Es lo que consumirá el seed de
  `scoring_thresholds`.
- **Tests** (`tests/test_investment_engine_layers.py`, 45 tests).

## Archivos clave

- `backend/app/modules/investment/analysis/engine/{metrics,evolution,forensic,catalog}.py`
- `backend/tests/test_investment_engine_layers.py`

## Migraciones

Ninguna.

## Verificación

- [x] `ruff` · `black` · `mypy app/` (163 ficheros) verdes.
- [x] `pytest` capas nuevas → **45 passed**; engine completo → **116 passed** en 6,3 s.
- [x] Suite BE completa → **809 passed** (764 previos + 45 nuevos), 10m48s,
      excluyendo `test_ai_*` (requieren Ollama arrancado).
- [ ] Prueba manual del usuario: no procede (sin endpoints ni UI todavía).

Los valores esperados se calculan a mano sobre una empresa sintética que crece
un 20% exacto con márgenes constantes — con eso 7 de las 8 variables de Beneish
valen 1,0 y el M-Score sale de una aritmética verificable a mano
(−2,561544). Cada bandera C1-C8 tiene su fixture roto a propósito, y varias
tienen además el caso que NO debe dispararlas (un año malo suelto, crecimiento
orgánico, compras que sí justifican el fondo de comercio).

## Decisiones tomadas

- **`FZ` devuelve X, no P.** El DESIGN pide bandar la probabilidad
  `P = Φ(X)` pero marca Φ como "solo en presentación". Como Φ es monótona,
  bandear X con los cuantiles normales de P=15% y P=40% (−1,036433 y −0,253347)
  da EXACTAMENTE el mismo resultado, y así el engine no sale de `Decimal`
  (Φ no tiene forma cerrada en decimal y obligaría a pasar por `float`). Un test
  verifica la equivalencia con `math.erf`.
- **El Z'' usa el EBIT reportado, no `ebit_clean`.** El modelo se calibró sobre
  EBIT contable; sustituirlo por la versión limpia movería la escala de los
  cortes originales de Altman. Hay test.
- **σ de E3 es poblacional (÷N), no muestral (÷N−1).** La serie no es una
  muestra de una población mayor: son TODOS los años con datos. Con 3-5 puntos
  la diferencia se ve, así que conviene que esté escrito.
- **E3 exige ≥3 ejercicios.** σ de dos puntos es media distancia entre ellos, no
  dispersión; E3 dice medir predictibilidad, así que con dos años sale
  `not_computable` en vez de un número que no significa lo que aparenta.
- **Un score con un test no evaluable es `not_computable`, no un score parcial.**
  Un F-Score sobre 7 de 9 tests no es comparable con la banda 0-9, y presentarlo
  como si lo fuera engaña más que no darlo.
- **`payout_ratio` vive en `evolution.py` y es la futura D1.** E4 lo necesita ya
  y la Capa 3 lo necesitará después; se define UNA vez para que las dos no
  acaben con payouts que divergen (lección PHASE-38 sobre predicados
  compartidos). Cuando llegue `dividend.py`, D1 debe importarlo, no reescribirlo.
- **La nota de REITs avisa pero no suprime.** El §5 pide `model_variant
  ='uncalibrated'` y nota ámbar para el Z'' de una socimi: se emite la bandera
  `z_score_uncalibrated_for_reit` y el score se sigue calculando — suprimirlo
  dejaría al usuario sin dato y sin explicación.
- **`accruals` se bandea en valor absoluto.** El §5 dice "|x| <5% verde"; un
  accrual muy negativo (caja muy por delante del beneficio) también es anomalía.

## Limitaciones conocidas / follow-ups

- **C2 usa un criterio estricto de "CFO plano o que cae"**: exige crecimiento de
  CFO ≤ 0 mientras el resultado neto sube. El DESIGN dice "NI crece y CFO
  plano/cae" sin fijar qué es "plano", y se eligió el corte estricto para no
  generar falsos positivos; si en datos reales resulta demasiado estrecho (un
  CFO que crece un 1% frente a un NI que crece un 30% no dispara), es un
  parámetro a calibrar en la fase de validación con empresas reales.
- **C5 no evalúa si `acquisitions` es un hueco**: sin el dato no se puede
  afirmar que no hubo compras. Con la política de imputación de §4.5
  `acquisitions` está en la lista blanca (ausente → 0), así que en la práctica
  llegará informado desde la ingesta.
- **Sin `evidence` numérica en algunas banderas de coherencia**: llevan los años
  implicados, que es lo que la UI necesita para enlazar, pero no la serie
  completa de soporte.
- Las capas 3 (dividendo), 3.5 (stress) y 4 (síntesis) siguen pendientes, y con
  ellas el golden test end-to-end (exige fixtures reales de EDGAR, fase 44.4).

## Estado del árbol de trabajo

**Sin commitear**, acumulado sobre PHASE-44.1 y 44.2.

## Próxima fase

**PHASE-44.4** — capas 3 (dividendo: D*, Q*, B*, T*), 3.5 (stress paramétrico) y
4 (síntesis: matriz de banderas, veredicto, confianza, staleness), que cierran
el engine. Después llega el adapter EDGAR, donde hay que **PARAR** y pedir al
usuario el cruzado de `validate_edgar.py` contra 3 empresas reales antes de
fijar el `concept_map` (ARCH §8).
