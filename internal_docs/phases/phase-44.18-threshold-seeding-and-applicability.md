# PHASE-44.18 — La banda que no llega

**Estado**: ✅ código completo y verde · ⏳ pendiente prueba manual del usuario
**Fecha**: 2026-08-09
**Plan**: [`improvements/phase-44.17-metric-honesty-and-parity.md`](../improvements/phase-44.17-metric-honesty-and-parity.md) §4
**Motor**: sin cambio de versión (sigue 1.3.0) — la huella de salida no se mueve.

## Objetivo

Que la diferenciación de umbrales por `(sector × norma)` —lo único que la tabla
`scoring_thresholds` aporta sobre el catálogo del motor— llegue de verdad hasta
la pantalla. Hoy no llegaba por **dos** cortes independientes, uno en cada
extremo.

---

## 1. El sembrado se cerraba para siempre

`seed_if_empty` hacía `if count > 0: return 0`. Siembra una vez y **toda métrica
añadida al catálogo después queda fuera**. Medido en la BD del usuario: **1440
filas, 40 métricas sembradas frente a 42 con banda** — S7 y S8, que llegaron en
PHASE-44.10, nunca entraron.

Ahora el arranque llama a `seed_missing_thresholds`, que **inserta lo que falta y
no toca ni una fila existente**. La distinción importa: `seed_scoring_thresholds`
también actualiza, lo cual es correcto al resembrar a propósito pero inaceptable
como paso de arranque — `AnalysisRun.thresholds_version` es un hash irreversible
de los cortes efectivos, y por eso PHASE-44.9 tuvo que persistir
`thresholds_used`. Si el arranque reescribiera filas, los runs viejos dejarían de
poder explicarse.

Una sola consulta (`repo.existing_keys`) y el resto es diferencia en memoria; la
clave es el triplete `(sector, norma, métrica)` y no sólo la métrica, porque el
día que se añada un sector las filas nuevas de una métrica ya sembrada también
harán falta.

## 2. Una exención razonada que nunca se ejecutó

`seed.py` declaraba `NOT_FOR_FINANCIALS = {"S7"}` con un docstring que explica
que aplicar la banda 1-2 a un banco *«pintaría un rojo permanente que no informa
de nada»*. Era **inerte**: dependía de que existiera una fila,
`ThresholdSpec.applies` vale `True` por defecto, y S7 no tenía fila.

Corregir sólo el sembrado no bastaba, porque `load_thresholds` cae a
`ALL_DEFAULT_THRESHOLDS` cuando falta la fila: **una BD recién creada
reintroduciría el bug**. Así que la aplicabilidad se muda al **engine**
(`base_ratios.NOT_CALIBRATED_FOR_FINANCIALS`), que es donde ya viven las
exenciones de los forenses, y el seed la importa de ahí. Ahora no depende de la
BD y una base nueva se comporta igual que una sembrada.

Es aplicabilidad, no calibración: **el número se sigue viendo, sin semáforo**.

## 3. Y en el otro extremo, se descartaba al llegar al cliente

`effectiveThreshold` copiaba de `thresholds_used` la dirección y los cuatro
cortes… y tiraba `applies` y `model_variant`, que son **los dos únicos atributos
por los que la tabla se diferencia del catálogo**. O sea que §1 y §2 sin esto no
se habrían notado en pantalla.

Consecuencias que ahora sí se ven:

- Una métrica sin banda **por falta de calibración** dice por qué, en vez de ser
  indistinguible de «no se pudo colorear». Y su fila **deja de enseñar el corte**:
  pintar 1-2 junto al número invitaría a comparar contra una vara que el motor
  descartó a propósito. Con el bug reintroducido, el test falla enseñando
  literalmente lo que un banco habría visto: `sano entre 1,00× y 2,00×`.
- Unas cuentas IFRS/PGC llevan la marca `≠` con el motivo: los cortes son
  US-GAAP y se aplican **sin recalibrar**. Es la deuda que PHASE-44.15 cerró en
  el backend y que se perdía en el último tramo.

## Archivos clave

- `engine/base_ratios.py` — `NOT_CALIBRATED_FOR_FINANCIALS` + `_drop_bands_for_financials`
- `thresholds/seed.py` — la lista pasa a ser un reflejo de la del engine
- `thresholds/service.py` — `seed_missing_thresholds` / `seed_on_startup`
- `thresholds/repository.py` — `existing_keys`
- `app/main.py` — el arranque completa en vez de rendirse
- `packages/ui/src/investment-metric-index.ts` — `EffectiveThreshold` con `applies`
- `packages/ui/src/investment-metric-rows.ts` — el motivo y la marca en pantalla

## Verificación

- Backend: `ruff` · `black` · `mypy` (219 ficheros) · suite completa.
- Frontend: `typecheck` · `lint` · 44 tests de `@crisol/ui` (de 41) · 144 web ·
  28 móvil · 60 services · 3 store.
- La huella del motor **no se mueve**: `test_investment_engine_contract.py` en
  verde sin tocar `ENGINE_VERSION`. El cambio afecta a los valores de banda de
  una financiera, no a la forma de salida.

### Los detectores, probados rompiéndolos

Cuatro tests nuevos, y los cuatro se validaron reintroduciendo el bug:

| Detector | Con el bug dentro |
|---|---|
| Una métrica añadida tras el primer seed SÍ entra | falla |
| El sembrado de arranque no reescribe filas existentes | (guarda) |
| Toda métrica con banda del catálogo se siembra | (gate sin BD) |
| S7 pierde el semáforo en una financiera **sin depender de la BD** | falla |
| El corte efectivo llega entero al cliente (3 casos) | fallan 2 |

**Por qué la suite anterior no podía cazarlo**, y es la parte que más importa:
los tests **siembran siempre una base limpia**, donde el catálogo entero entra de
una vez. El defecto sólo existe en una tabla **con historia**, de un catálogo
anterior. El detector tiene que fabricar esa situación a mano — es la lección de
[PHASE-44.14] sobre fixtures que viven todos del mismo lado del umbral.

## Efecto sobre los datos del usuario

**Ninguna migración y ningún data-fix.** Al reiniciar el backend, el arranque
insertará las filas de S7 y S8 que faltan (2 métricas × sectores × normas). Las
1440 existentes no se tocan, así que `thresholds_version` de los runs ya
guardados sigue siendo explicable.

## Limitaciones conocidas

- El efecto en pantalla **no se ve con JNJ ni con MCD**: ninguna es financiera ni
  presenta bajo IFRS. Se activa al analizar un banco (Santander es alcanzable
  desde PHASE-44.15) o un emisor europeo.
- `applies` se asume `true` cuando el run no trae `thresholds_used` (anteriores a
  PHASE-44.9). Es lo que el catálogo significa, pero es una asunción: en un run
  viejo no hay forma de saber qué vara se aplicó.

## Próxima fase

PHASE-44.19 — el gate del dividendo, que esconde ocho métricas ya calculadas.
