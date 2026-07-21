# PHASE-44.4 — Engine: Capa 3 (dividendo)

**Estado**: ✅ código completo y verde (pendiente prueba manual del usuario)
**Rama**: trabajo directo sobre `main` (workflow del proyecto)
**Fecha**: 2026-07-20

## Objetivo

La Capa 3, el **target** del módulo: todo el análisis existe para responder si un
dividendo es sostenible. Sigue siendo engine PURO.

Fuente de verdad: DESIGN §5, Capa 3 (bloques D, Q, B, T).

## Qué se implementó

- **`engine/dividend.py`** — Capa 3:
  - **Cobertura (D1-D8)**: payout sobre beneficio/FCF, cobertura FCF, ajuste SBC,
    retorno total, payout REIT, margen de seguridad. D7 (serie de DPS) sin banda.
  - **Calidad de la caja (Q1-Q5)**: conversión CFO/beneficio y FCF/EBITDA,
    divergencia FCF dual, peso de extraordinarios; **Q4** (anomalía fiscal) como
    flag por serie contra la mediana.
  - **Soporte del balance (B1-B4)**: B3 (años de dividendo en caja) con banda;
    **B1/B2** como cruces compuestos que leen las bandas S4/S2 de la Capa 1; B4
    (dividendo financiado con deuda/emisión) como flag rojo con evidencia
    cuantificada.
  - **Trayectoria (T1-T4)**: T2 (CAGR del DPS) y T3 (σ del payout) con banda;
    T1 (racha sin recorte, cota inferior) y T4 (desaceleración) en
    `DividendTrajectory`.
  - **Ajuste REIT**: para `is_reit`, D1/D2/D3/D8 se calculan sobre FFO; D6 es el
    payout REIT canónico y en no-REIT sale `not_computable`.
- **`engine/conventions.py`** — extraídos dos helpers puros compartidos:
  `population_stdev()` y `cagr()`. `evolution.py` se refactorizó para usarlos
  (elimina la σ y el CAGR que tenía inline — una sola implementación).
- **`engine/catalog.py`** — ahora agrega **51 métricas** (27+2+8+14).
- **Tests** (`tests/test_investment_engine_dividend.py`, 35 tests).

## Archivos clave

- `backend/app/modules/investment/analysis/engine/dividend.py`
- `backend/app/modules/investment/analysis/engine/conventions.py` (helpers compartidos)
- `backend/app/modules/investment/analysis/engine/evolution.py` (refactor a los helpers)
- `backend/tests/test_investment_engine_dividend.py`

## Migraciones

Ninguna.

## Verificación

- [x] `ruff` · `black` · `mypy app/` (164 ficheros) verdes.
- [x] `pytest` dividendo → **35 passed**; módulo Inversión completo → **162
      passed** en 8,6 s.
- [x] Suite BE completa → **844 passed** (809 previos + 35 nuevos), 10m56s,
      excluyendo `test_ai_*` (requieren Ollama arrancado).
- [ ] Prueba manual del usuario: no procede (sin endpoints ni UI).

Valores calculados a mano sobre una empresa con dividendo holgadamente cubierto;
casos de riesgo con fixtures propios (dividendo pagado con deuda → B4 rojo;
payout errático; anomalía fiscal; ajuste REIT sobre FFO). Dos errores de mis
cálculos a mano (σ de T3, y Q3 asumiendo circulante 0 donde había `None`) los
cazaron los tests — el engine tenía razón en ambos.

## Decisiones tomadas

- **La Capa 3 calcula aunque no haya dividendo.** Payout 0% → verde, cobertura
  → `not_computable` (÷0). La decisión de marcar el análisis como
  `not_applicable` (empresa que no reparte) es de la Capa 4 (síntesis), no de
  aquí — separación limpia que evita que la Capa 3 tenga que "saber" del
  veredicto.
- **B1/B2 leen bandas, no recalculan.** Son la lectura CONJUNTA de S4/S2
  (Capa 1) con D2 (aquí). Se pasan las bandas por parámetro (`forensic_bands`)
  para que el cruce hable exactamente del mismo número que el usuario ve en su
  métrica, no de una recalculada que podría diferir por redondeo o umbral.
- **Helpers estadísticos compartidos** (`population_stdev`, `cagr`) en
  `conventions.py`, usados por evolution Y dividend. Antes evolution los tenía
  inline; ahora hay UNA implementación (lección PHASE-38 sobre predicados
  compartidos). El refactor está protegido por los 45 tests de 44.3.
- **REIT: solo D1/D2/D3/D8 cambian a FFO**, no D4/D5. Es lo que dice el §5 al
  pie de la letra; D4/D5 se quedan sobre FCF incluso en socimis.
- **Q4 emite dos banderas distintas**: caída puntual >10 pp vs la mediana, y
  nivel <10% sostenido 2 años. Son señales diferentes (un año raro vs una
  estructura fiscal permanente) y conviene que el informe las distinga.

## Limitaciones conocidas / follow-ups

- **B1/B2 dependen de que el servicio inyecte `forensic_bands`**. Sin ellas, los
  cruces no se evalúan (no se inventan). El orquestador de la Capa 4 debe pasar
  las bandas S2/S4 del último ejercicio; hasta que exista ese orquestador, B1/B2
  solo se ejercitan en tests.
- **T1 es una cota inferior** por construcción (la serie ingerida no es la
  histórica completa). La UI debe decirlo ("≥ N años en los datos disponibles").
- El umbral de C2 (PHASE-44.3) sigue pendiente de calibrar; sin relación con
  esta fase.

## Estado del árbol de trabajo

**Sin commitear.** Las fases 44.1-44.3 sí están commiteadas (bcd9613, 62866f4,
dd842f5); esta 44.4 queda encima sin commitear.

## Próxima fase

**PHASE-44.5** — Capa 3.5 (stress paramétrico: ST1 shock de ingresos, ST2 shock
de tipos, ST3 breakeven del dividendo) y Capa 4 (síntesis: las 4 preguntas, la
matriz de seguridad Conservador/Vigilar/Evitar, `dividend_verdict`). Cierran el
engine y desbloquean el golden test end-to-end. Después, el adapter EDGAR (parada
para el cruzado con empresas reales).
