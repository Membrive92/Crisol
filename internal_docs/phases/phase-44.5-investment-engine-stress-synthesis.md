# PHASE-44.5 — Engine: capas 3.5 (stress) y 4 (síntesis)

**Estado**: ✅ código completo y verde (pendiente prueba manual del usuario)
**Rama**: trabajo directo sobre `main` (workflow del proyecto)
**Fecha**: 2026-07-20

## Objetivo

Las dos capas que **cierran el engine**: el stress paramétrico (¿aguanta un
golpe?) y la síntesis (el veredicto que la UI muestra primero). Con esto el
motor de análisis está completo: seis capas puras, sin I/O.

Fuente de verdad: DESIGN §5, capas 3.5 y 4.

## Qué se implementó

- **`engine/stress.py`** — Capa 3.5:
  - **ST1 shock de ingresos**: ventas −x%; el EBIT cae según el margen de
    contribución proxy (mediana de Δebit/Δrevenue de la serie), acotado a [0,1];
    el golpe se traslada a la caja neto de impuestos.
  - **ST2 shock de tipos**: +y pb sobre la fracción variable de la deuda.
  - **ST3 breakeven**: cuánto puede caer la caja libre antes de dejar de cubrir
    el dividendo (D3 = 1,0).
  - Parámetros editables (`StressParams`, defaults del DESIGN); cada escenario
    lleva la etiqueta fija "escenario hipotético" y su frase generada.
- **`engine/synthesis.py`** — Capa 4:
  - **Cuatro preguntas** (contabilidad / caja / dividendo / resiliencia), cada
    una con semáforo por regla explícita: rojo si ≥1 señal roja, ámbar si ≥2
    ámbar, verde el resto.
  - **Matriz de seguridad**: Conservador / Vigilar / Evitar por reglas booleanas
    sobre M-Score, Z'', X-Score, F-Score y B4.
  - **`dividend_verdict`** (healthy/caution/stressed/not_applicable).
  - **Confianza** = completitud núcleo × factor de frescura; los `imputed_zero`
    no cuentan como sourced y se listan aparte.
  - **Matriz de banderas**: recopila las flags de las cuatro capas anteriores.
- **`engine/conventions.py`** — extraído `median()` (lo usaban Q4 y ST1).
- **Tests** (`tests/test_investment_engine_synthesis.py`, 26 tests).

## Archivos clave

- `backend/app/modules/investment/analysis/engine/stress.py`
- `backend/app/modules/investment/analysis/engine/synthesis.py`
- `backend/tests/test_investment_engine_synthesis.py`

## Migraciones

Ninguna.

## Verificación

- [x] `ruff` · `black` · `mypy app/` (166 ficheros) verdes.
- [x] `pytest` stress+síntesis → **26 passed**; módulo Inversión completo →
      **188 passed** en 9,8 s.
- [x] Suite BE completa → **870 passed** (844 previos + 26 nuevos), 10m56s,
      excluyendo `test_ai_*` (requieren Ollama arrancado).
- [ ] Prueba manual del usuario: no procede (sin endpoints ni UI).

Los tests separan dos niveles: la **regla** (semáforo, matriz de seguridad,
confianza) se prueba con entradas construidas — deterministas, sin depender de
que un fixture dé por casualidad las bandas exactas; la **integración** encadena
las cinco capas reales sobre empresas sintéticas (sana coherente, en quiebra
técnica) y verifica el veredicto agregado.

## Decisiones tomadas

- **La síntesis recibe los resultados YA CALCULADOS de cada capa**, no recomputa.
  Firma `compute(series, base, evolution, forensic, dividend, stress)`. Así es
  pura y testeable sin reejecutar el engine, y el orquestador (servicio, fase
  futura) encadena. Esto también resuelve el follow-up de PHASE-44.4: B1/B2 ya
  tienen quién les inyecte las bandas S2/S4.
- **`FZ` (Zmijewski) se bandea en X, la probabilidad es de presentación** —
  heredado de 44.3; la síntesis usa la banda, no recalcula P.
- **La regla del semáforo NO es una media ponderada.** "Rojo si cualquiera de
  sus señales núcleo es roja; ámbar si ≥2 ámbar" — explícito y abrible, como pide
  el §5. Una señal `not_computable` no cuenta ni a favor ni en contra (se ignora,
  no se trata como roja ni como verde).
- **Perfil "Conservador" exige F-Score ≥ 7 por VALOR, no por banda.** El §5 lo
  fija en 7; si el usuario recalibrara el umbral de f_score, la matriz sigue
  usando el 7 del modelo de Piotroski. Un test lo verifica con value=5→watch.
- **El margen de contribución (ST1) se acota a [0, 1]** y se toma la MEDIANA (no
  la media): un euro de ventas no destruye más de un euro de EBIT ni lo aumenta,
  y un año atípico no debe dominar el apalancamiento operativo estimado.
- **El shock se traslada a la caja neto de impuestos** (× (1 − ETR)); sin ETR
  computable, sin escudo (golpe pre-impuestos, más conservador).
- **Frescura por días** (274 ≈ 9m, 548 ≈ 18m) en vez de aritmética de meses:
  el engine es puro y no tiene `relativedelta`; el umbral en días es explícito
  y determinista.

## Limitaciones conocidas / follow-ups

- **`restatements` no entra aún en la pregunta 1** (contabilidad): la señal
  proviene de `RestatementFlag`, que se puebla en la fase de ingesta. La síntesis
  la sumará cuando exista; hoy la pregunta 1 usa el resto de señales del §5.
- **La "tendencia FCF" (E1) en la pregunta 2** se reduce a "CAGR de fcf_cfo < 0
  → señal roja". Es una simplificación del "tendencia" del DESIGN; afinar
  (p. ej. pendiente de los últimos 3 años) es posible si la señal resulta tosca
  con datos reales.
- El golden test end-to-end (AnalysisRun serializado) sigue pendiente de
  fixtures reales de EDGAR (fase de ingesta).

## Estado del árbol de trabajo

**Sin commitear.** Las fases 44.1-44.3 están commiteadas (bcd9613, 62866f4,
dd842f5); 44.4 y 44.5 quedan encima sin commitear.

## Próxima fase

**El engine está COMPLETO** (6 capas). Lo siguiente sale del engine puro:

**PHASE-44.6 (ARCH 40.4)** — adapter EDGAR + cache + concept_map + normalización
+ validación + restatements + IngestionJob + endpoints de fundamentales. ⚠️ Aquí
hay que **PARAR y pedir al usuario** el cruzado de `validate_edgar.py` contra 3
empresas reales antes de fijar el `concept_map` (ARCH §8). Con datos reales
ingeridos llega también el golden test del engine.
