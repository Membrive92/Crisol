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
- 1.4.0 — PHASE-44.17: un `MetricResult` gana un cuarto estado,
  **`not_applicable`** («la pregunta que hace la métrica no se plantea aquí»),
  distinto de `not_computable` («se intentó y no se pudo»). Lo estrena **L4**: no
  tener deuda venciendo a doce meses salía como «denominador cero», que la
  pantalla presenta igual que un dato ausente — así que una empresa con todo
  pagado perdía una señal de resiliencia por tenerlo pagado. Ahora sale verde si
  el cero lo PUBLICA la empresa y sin banda si lo supone la ingesta (§4.5): el
  verde se gana, no se hereda de que el emisor no etiquete un concepto.

  Ningún otro valor cambia, pero el significado de la salida sí, y por eso se
  mueve la versión: el gate de la huella no lo habría exigido —cambia un
  `Literal`, no la lista de campos de una dataclass—, que es precisamente el
  hueco que conviene conocer del gate.

  Va con dos invariantes nuevos en `MetricResult`: un estado sin número exige
  razón (ya valía para `not_computable`) y un `not_computable` **no puede llevar
  banda**, porque un color sobre algo que no se ha comprobado es un color
  inventado.
- 1.5.0 — PHASE-44.17: las **reglas de bandera publican si se pudieron
  evaluar** (`FlagEvaluation`, `flag_rules.py`). Una `Flag` sólo existe cuando
  salta, así que la síntesis preguntaba «¿hay bandera?» y traducía el no a **«no
  se ha encendido»** — la misma frase para una regla comprobada y limpia y para
  una que no llegó a ejecutarse (sin coste de ventas, C3 no corre ni un año).

  Tres piezas que sostienen el arreglo:

  1. **Default pesimista** en `_flag_signal`: sin evaluación, «no se ha podido
     comprobar». Con el optimista, olvidar publicar una evaluación pinta verde.
  2. **Gate de cobertura** simétrico: toda clave de `QUESTION_FLAG_KEYS` tiene
     evaluación publicada. Sin él, el default pesimista cambiaría un falso verde
     por un falso gris universal.
  3. El criterio de «suficientes ejercicios» es una **racha consecutiva**, no un
     cardinal: con años evaluables {2016, 2018, 2020} y `sustained=2` la regla
     no puede encenderse jamás.

  Además: `QuestionSignal.outcome` y los contadores `clear_count` /
  `unchecked_count` separan «comprobado y limpio» —que es evidencia positiva—
  de «no se pudo». Y `_safety_profile` deja de leer una B4 no evaluable como «no
  está en rojo»: es una de las cuatro condiciones de «Evitar», así que sin
  comprobarla no se concede el sello de «Conservador».

  El motivo de un hueco distingue por fin los TRES modos de ausencia
  (`growth_of`): falta la partida, valía cero, o el filing no la publica y la
  ingesta la supone cero — redactarlo sin mirar la procedencia produce una frase
  falsa.
- 1.6.0 — PHASE-44.21: **calibración sectorial**. Los umbrales dejan de ser una
  vara única (`sector_profiles.py`): doce perfiles de deltas sobre el genérico,
  con la aplicabilidad —qué métricas NO significan nada en ese negocio— en el
  ENGINE y no sólo en la tabla, para que una base sin sembrar se comporte igual
  que una sembrada.

  Lo que cambia de verdad para quien lee un informe:

  - Una eléctrica con deuda neta 4,8× EBITDA sale **ámbar**, no roja: la mediana
    de grado de inversión del sector es 5,1×. Un rojo permanente se aprende a
    ignorar, y entonces tampoco informa el que sí importa.
  - Un banco ve apagadas las 33 métricas que no describen su negocio, **cada una
    con su motivo** (`ThresholdSpec.not_applicable_reason`), y re-bandeadas las
    tres que sí: ROA en banda bancaria (1% es un buen banco), ROE y patrimonio
    sobre activo como proxy de capital — declarado como proxy, que no es CET1.
  - Un retail que cobra antes de pagar deja de salir en rojo de liquidez (RC-1),
    y una regulada con payout alto recibe la pregunta que decide: quién financia
    el exceso (RC-2, que enlaza C7 y B4 — ésas no se relajan por sector).
  - F7 deja de perderse entero por un check que no aplica: el de inventario sale
    del cómputo donde no hay inventario, con un mínimo de 4 checks aplicables.

  Y las **preguntas declaran sus portantes** (`load_bearing`, `audited`): el
  veredicto de «¿la contabilidad es de fiar?» se sostiene en el M-Score y en los
  accruals, no en el peso de los extraordinarios. Si falta un portante, la
  pregunta sale **no auditada** —el cuarto estado, en gris— en vez de verde. No
  es una proporción a propósito: un ratio trataría igual una señal cualquiera
  que el M-Score. En una financiera, «¿aguanta un golpe?» es no auditable de
  forma permanente: la resiliencia bancaria es capital regulatorio y no está en
  un 10-K.

  Sube la versión porque cambia la FORMA (tres campos nuevos en `QuestionVerdict`
  y uno en `ThresholdSpec`) y porque el veredicto de la misma empresa puede
  cambiar. Los `thresholds_version` de los runs futuros también cambian, que es
  lo correcto: la calibración es otra.
- 1.7.0 — PHASE-44.24.M: **la procedencia del corte se persiste** y el escenario
  de stress deja de puntuar en financieras.

  1. `ThresholdSpec.origin` (`generic` | `sector` | `financial` | `table`) viaja
     a `thresholds_used` de cada run. No se puede reconstruir después:
     compararlo con el catálogo de HOY etiqueta como «sectorial» cualquier
     recalibración genérica posterior al run, y no distingue en absoluto un
     ajuste manual de la tabla — que es justo para lo que la tabla existe. Lo
     fija quien resuelve: el perfil en `resolve_thresholds`, y la fila
     recalibrada en `load_thresholds`, comparando como NÚMERO y no como cadena
     (la columna es `Numeric(12, 6)` y el motor tiene `Decimal('0.6')`).

  2. En una financiera, la señal de stress sale **no comprobada** con el motivo
     de `NOT_AUDITABLE`. El motor ya declaraba «¿aguanta un golpe?»
     permanentemente no auditable en banca —la resiliencia de una entidad
     financiera es capital regulatorio, no está en un 10-K— y sin embargo
     seguía calculando el escenario y podía pintarlo ROJO dentro de esa misma
     pregunta: un chip gris de «no auditada» con una señal roja debajo, en la
     misma pantalla.

  Ninguna métrica cambia de valor. La huella del contrato SÍ se mueve —campo y
  `Literal` nuevos— y por eso sube la versión.

  El `thresholds_version`, en cambio, **NO cambia**, y es deliberado:
  `thresholds_hash` no incluye `origin`. La procedencia es metadato derivado de
  los mismos `(sector × norma × is_financial)` que ya determinan los cortes, así
  que meterla en el hash movería la versión de umbrales de TODOS los runs
  futuros sin que la calibración se haya movido un céntimo — y ese hash existe
  precisamente para responder «¿se midió a estas dos empresas con la misma
  vara?». El único caso en que la procedencia cambia sin que cambien los cortes
  es imposible por construcción: `table` sólo se marca cuando la fila DIFIERE, y
  entonces los cortes ya son otros y el hash ya se mueve.

  Los runs guardados conservan su `thresholds_version` y no traen `origin`, así
  que la pantalla lo deriva para ellos y lo declara como derivado.
"""

from __future__ import annotations

ENGINE_VERSION = "1.7.0"
