"""Versión del engine (PHASE-44.2, ARCHITECTURE §4.3, [Dec.7]).

`ENGINE_VERSION` es semver y se incrementa con **cualquier cambio de fórmula o
incorporación de métrica**. Viaja a cada `AnalysisRun` para que un informe
guardado sepa con qué matemática se calculó — sin eso, comparar dos runs de
fechas distintas es comparar peras con manzanas.

El golden test (`tests/test_investment_engine_golden.py`) falla si la FORMA del
output del engine cambia sin que esta constante se mueva: es el gate que impide
tocar una fórmula en silencio. Hasta PHASE-44.9 ese gate estaba sólo declarado
aquí y no existía — el único test que tocaba la constante comprobaba que fuese
semver.

Historial:
- 1.0.0 — PHASE-44.2: Capa 1 (derivaciones §4.4 + 27 métricas base §5).
  Las capas 1.5, 2, 3, 3.5 y 4 (PHASE-44.3 a 44.5) entraron SIN mover la
  constante, que es justo lo que el gate ausente permitía.
- 1.1.0 — PHASE-44.9: `DUPONT_EM` pasa a ser una métrica catalogada (28 en la
  capa 1, 52 en total) y `QuestionVerdict` publica sus señales estructuradas
  (`signals`, `evaluated_count`, `unavailable_count`). Cambia la FORMA de la
  salida, no el valor de ninguna métrica ya existente.
- 1.2.0 — PHASE-44.10: cinco métricas nuevas (33 en la capa 1, 57 en total) —
  `S7` endeudamiento, `S8` calidad de la deuda y los tres factores que faltaban
  del DuPont extendido (`DUPONT_OM`, `DUPONT_TAX`, `DUPONT_FIN`)—, la
  descomposición DuPont gana sus dos filas de comprobación, y la capa evolutiva
  pasa de 7 a 10 series al cablear `fcf_maintenance`, `wc_operating` y
  `wc_total`. Ninguna métrica existente cambia de valor. `S7` y `S8` sí llevan
  banda, así que el `thresholds_version` de los runs futuros cambia: es correcto
  —la calibración es otra— y los runs guardados conservan el suyo.
- 1.3.0 — PHASE-44.12: capa de valoración por múltiplos (`valuation.py`), 7
  métricas nuevas (64 en total): `V1` PER, `V2` precio/ventas, `V3` precio/valor
  contable, `V4` precio/caja libre, `V5` EV/EBITDA, `V6` valor contable por
  acción y `V7` rentabilidad de la caja libre.

  **No cambia ningún `AnalysisRun`**: la valoración se calcula al vuelo y no se
  persiste, porque depende del precio y un run tiene que poder reejecutarse
  dando lo mismo. Las siete están catalogadas (para que la UI lea su etiqueta y
  su unidad de una sola fuente) y NINGUNA lleva banda, así que el
  `thresholds_version` no se mueve: sin comparables de sector, un semáforo sería
  una opinión disfrazada de dato.

  `ValuationInputs`/`ValuationResult` llevan `provider_status`
  (`live`/`cached`/`unreachable`): el semáforo de la pantalla necesita
  distinguir «se le ha pedido al proveedor y ha respondido» de «no se le ha
  pedido nada porque la cotización seguía fresca». Pintar verde en el segundo
  caso afirmaría una comprobación que no se ha hecho.

  Los cortes de antigüedad (`STALENESS_*`) se mudan de `synthesis` a
  `conventions`: los usan la síntesis y la valoración, y `conventions` es hoja
  del grafo de imports — sin eso, registrar el catálogo de valoración creaba el
  ciclo `catalog → valuation → synthesis → catalog`.
"""

from __future__ import annotations

ENGINE_VERSION = "1.3.0"
