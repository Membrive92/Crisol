# PHASE-44.24.M — Motor 1.7.0: de dónde salió el corte, y el stress que se contradecía

**Estado**: 🚧 pendiente prueba manual
**Rama**: `main` (push directo)
**Fecha**: 2026-08-27
**Plan**: [`improvements/phase-44.24-report-legibility-implementation-plan.md`](../improvements/phase-44.24-report-legibility-implementation-plan.md) §2.M
**Decisiones del usuario**: Dec.B (persistir la procedencia) · Dec.G (arreglar el stress en el motor)

## Objetivo

Dos cambios de motor que la capa de presentación necesita **antes** de
construirse, para leer un dato en vez de inferirlo, y para no tener que tapar en
la narrativa una contradicción que el propio motor produce.

## 1. `ThresholdSpec.origin` — la procedencia se persiste

Cuatro valores: `generic` (la vara del catálogo), `sector` (el perfil del sector
la sobrescribió), `financial` (la sobrescribió el perfil financiero, que se
fusiona **encima** del sectorial cuando el valor es una entidad financiera
aunque esté clasificado en otro sitio) y `table` (una fila de
`scoring_thresholds` difiere de lo que el motor resuelve: alguien recalibró a
mano, que es para lo que la tabla existe).

### Por qué persistirlo y no derivarlo

El plan contemplaba derivarlo al leer, comparando los cortes guardados con el
catálogo de hoy. La revisión adversarial de ese plan lo tumbó con tres casos, y
la decisión del usuario fue persistir:

- Una **recalibración genérica posterior al run** hace que los cortes guardados
  difieran del genérico de hoy, y la derivación los etiquetaría «sectoriales» —
  para una empresa sin perfil, «banda sectorial (perfil actual: unknown)».
- Un **ajuste manual de la tabla** es indistinguible de un delta de perfil: los
  dos son «distinto del genérico».
- Y el `sector` no basta para la etiqueta: `profile_for` fusiona el perfil
  financiero por encima, así que para un holding en INDUSTRIALS marcado como
  entidad financiera los cortes vienen de la banca. Por el prefijo SIC 67 ése es
  además el estado normal de las socimis del catálogo, no un caso de
  laboratorio.

Un run es un documento que se lee meses más tarde. Lo que no viaja dentro se
pierde.

### Dónde se fija, y una trampa concreta

`resolve_thresholds` marca `sector`/`financial` —comprobando el perfil
financiero **primero**, porque es el que se fusiona encima— y las métricas
derivadas (`RELATIVE_CUTS`: L2 desde L1, S6 desde S2) heredan la procedencia de
su fuente: decir `generic` de un corte calculado a partir de un delta sectorial
sería falso, porque el número no es el del catálogo.

`load_thresholds` marca `table`, y la comparación es **numérica**, no textual.
La columna es `Numeric(12, 6)`, así que una fila sembrada trae
`Decimal('0.600000')` donde el motor tiene `Decimal('0.6')`: iguales como número
y distintas como cadena. Compararlas como texto habría marcado **toda** fila
sembrada como recalibrada a mano — lo contrario exacto de lo que el campo dice.
Hay un test para cada lado, y la sonda que cambia la comparación a textual lo
tumba.

### Qué NO se movió, y por qué

`thresholds_hash` **no incluye `origin`**, así que el `thresholds_version` de
los runs futuros no cambia. Es deliberado y contradice al plan, que decía lo
contrario: la procedencia es metadato derivado de los mismos
`(sector × norma × is_financial)` que ya determinan los cortes, y meterla en el
hash movería la versión de umbrales de todos los runs sin que la calibración se
haya movido — cuando ese hash existe precisamente para responder «¿se midió a
estas dos empresas con la misma vara?». El único caso en que la procedencia
cambiaría sin cambiar los cortes es imposible por construcción: `table` sólo se
marca cuando la fila DIFIERE, y entonces el hash ya se mueve.

**La afirmación errónea llegó a estar escrita en `version.py`** antes de
comprobarla; se detectó ejecutando `thresholds_hash` en vez de razonarlo.

## 2. En una financiera, el escenario de stress no puntúa

El motor declara «¿aguanta un golpe?» **permanentemente no auditable** en banca
—`NOT_AUDITABLE`: la resiliencia de una entidad financiera es capital
regulatorio y no está en un 10-K— y sin embargo seguía calculando el escenario
de stress y podía pintarlo **rojo dentro de esa misma pregunta**. En pantalla:
un chip gris de «no auditada» con una señal roja debajo, y en cuanto la
narrativa de la entrega B proponga qué vigilar, ese rojo habría sido el titular.

Ahora sale como **no comprobada** con el motivo de `NOT_AUDITABLE`:
`counted=False` y sin banda, así que no puede llegar ni a la tabla de señales ni
a lo que la pantalla proponga.

La regla defensiva prevista en la entrega B se conserva igualmente: los runs
anteriores a 1.7.0 siguen llevando la señal roja, y la narrativa se calcula
también para ellos.

## Los tests, y el hueco que revelaron

Seis nuevos. **Ninguno de los 636 tests de inversión existentes se rompió con el
cambio de Dec.G** — y eso no era una buena señal, sino la prueba de que ningún
test cubría una financiera con un escenario de stress fallido. Ahí estaba el
hueco por el que el defecto llevaba vivo desde PHASE-44.21.

Los cinco probados rompiendo el código, y cada uno cae en el test que lo cubre,
no en un vecino:

| Sonda | Test que cae |
|---|---|
| El perfil financiero deja de comprobarse primero | `…holding_financiero_fuera_del_sector…` |
| Las derivadas dejan de heredar la procedencia | `…metrica_derivada_hereda…` |
| La comparación de la fila pasa a ser TEXTUAL | `…fila_igual_al_motor_no_se_declara_recalibrada` |
| La guarda de financieras desaparece | `…financiera_el_escenario_de_stress_no_puntua_en_rojo` |
| La guarda se aplica a TODAS las empresas | `…no_financiera_el_escenario_de_stress_sigue_puntuando` |

El último existe por lo de siempre: sin él, sustituir la señal por un
`unchecked` incondicional pasaría el primero y nadie se enteraría de que el
motor ha dejado de mirar los escenarios en todas las empresas. Y en el test de
la métrica derivada se quitó un `if` que lo habría hecho pasar en vacío el día
que el perfil dejara de mover L1.

## Archivos clave

- `engine/types.py` — `ThresholdOrigin` y el campo en `ThresholdSpec`.
- `engine/sector_profiles.py` — `threshold_origin_for` y `_contributes`.
- `engine/synthesis.py` — `_stress_signal` recibe el `SecuritySnapshot`.
- `thresholds/service.py` — `_differs` y la marca `table`.
- `engine/version.py` — 1.7.0 con su historial.

## Migraciones

Ninguna. `origin` no es una columna: se resuelve en el motor y viaja dentro del
JSONB del run.

## Verificación

- [x] ruff · black · mypy 230 ficheros
- [x] Huella del contrato registrada para 1.7.0 (el gate la exigió, como debe)
- [x] Los cinco comportamientos verificados rompiendo el código
- [x] `thresholds_version` comprobado por ejecución, no por razonamiento
- [ ] **Prueba manual**: reejecutar MCD/JNJ (saldrán con el aviso «motor
      anterior», que aquí es verdad) y comprobar que el informe sigue igual

## Limitaciones conocidas

- **La pantalla todavía no usa `origin`**: lo consume la entrega C, que es la
  que pinta la procedencia junto al corte. Hasta entonces el dato viaja y no se
  ve.
- **Los runs guardados no lo traen**, y ausente no es `generic`: la entrega C
  deriva para ellos y declara que es una derivación.

## Próxima entrega

**44.24.C** — distancia al corte, orden por severidad, procedencia en pantalla y
cross-links.
