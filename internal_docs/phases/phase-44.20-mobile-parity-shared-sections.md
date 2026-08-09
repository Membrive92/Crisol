# PHASE-44.20 — Paridad móvil real

**Estado**: ✅ código completo y verde · ⏳ pendiente prueba manual del usuario
**Fecha**: 2026-08-09
**Plan**: [`improvements/phase-44.17-metric-honesty-and-parity.md`](../improvements/phase-44.17-metric-honesty-and-parity.md) §6

## Objetivo

Que las 64 métricas del catálogo tengan sitio en **las dos** apps, y que añadir
una al motor sin dárselo **falle en CI** en vez de pasar desapercibido.

---

## 1. La capa compartida cubría 57 de 64

Las otras siete —`DUPONT_OM`, `DUPONT_TAX`, `DUPONT_FIN`, `E3`, `E4`, `T2`,
`T3`— estaban escritas **a mano en tres ficheros de web**. Móvil renderiza
estrictamente desde `investment-report-sections.ts`, así que no las pintaba
nunca. Es literalmente lo que el docstring de ese fichero dice prevenir —*«una
pantalla enseñando ocho scores forenses y la otra seis, sin que nada avise»*—
reintroducido por la puerta de las claves escritas en los tabs.

Ahora el fichero declara tres secciones más:

- **`DUPONT_SECTIONS`** — las dos descomposiciones del ROE. No caben en
  `ReportSection` porque además de métricas llevan una fila de **comprobación**
  que no es una métrica del catálogo, así que el tipo la declara aparte.
- **`EVOLUTION_METRICS`** — E3 y E4, las dos métricas con banda de la capa
  evolutiva.
- **`TRAJECTORY_SECTION`** — T2 y T3.

**Una premisa mía era falsa y ahorró trabajo**: creía que el DuPont necesitaba un
índice propio porque sus `MetricResult` vivían sólo en `dupont[]`. No: los tres
factores están también en `metrics[]` (`base_ratios.py:425-427`, confirmado con
el run real de JNJ). Así que el índice global sirve y toda la maquinaria de
`MetricSource` que el plan preveía **sobra**. Lo único exclusivo de `dupont[]`
son `check_three` y `check_five`.

## 2. `checkRow` sube a la capa compartida

Era lógica pura viviendo en un tab de web, y devuelve un `MatrixRow`, que ya es
un tipo compartido. Ahora es `dupontCheckRow` en `@crisol/ui` y la usan las dos
apps — con sus tres estados intactos, incluido el `undefined` que en PHASE-44.16
pintaba «NaN» en rojo acusando a las cuentas de un descuadre inexistente.

## 3. Lo que móvil ha ganado

El DuPont completo (las dos tarjetas con sus cuadres), las dos métricas de
Evolución —esa pestaña no pintaba **ninguna**— y la Trayectoria del dividendo,
que incluye el **dividendo por acción año a año**: el dato más elemental de esa
pestaña, y no estaba.

Además hereda de PHASE-44.19 el arreglo del gate: una empresa que no reparte
conserva la calidad de la caja, y una financiera ya no pierde la pestaña.

## 4. El gate, y por qué vive en el backend

`backend/tests/test_investment_screen_coverage.py` afirma que **toda métrica del
catálogo aparece en el fichero compartido**, y el sentido contrario (que la
pantalla no referencie claves que el motor no calcula, que saldrían como filas
siempre vacías).

Tres decisiones que conviene dejar escritas:

- **En el backend y no en `vitest`** porque hacen falta las dos puntas: las 64
  claves sólo las conoce el engine (Python). Ponerlo en el frontend obligaría a
  duplicar las 64 en un fichero TS — justo la lista escrita a mano que el gate
  viene a evitar.
- **Búsqueda de texto y no parseo de TS**, porque no hay intérprete de TS en el
  backend. Es tosco pero no puede derivar, y se acota a lo que aparece dentro de
  un array (una clave nombrada en una nota no cuenta como «tiene sitio»).
- **No en `make verify`**: verificado en `.github/workflows/ci.yml` — **CI no
  ejecuta `make verify`**. Corre `pytest`, así que un gate escrito aquí sí muerde
  en cada push. (Corolario incómodo: `knip` tampoco corre en CI, aunque la
  lección de PHASE-43 lo dé por cableado. Las dos cosas son ciertas;
  `make verify` no es CI.)

## 5. El test de paridad que era ciego

`report-tabs.test.tsx` comprobaba que móvil lista *«las mismas familias de ratios
que la web»*… contra cuatro etiquetas escritas a mano que casualmente eran las de
`RATIO_FAMILIES`. Web tenía un **quinto** bloque en su propio tab, así que el
test pasaba en verde con el DuPont ausente. Su comentario describía el modo de
fallo **contrario** al que ocurrió: no hubo duplicación en móvil, hubo una
sección de web que nunca subió a la capa compartida.

Ahora se deriva de la fuente compartida y recorre también `DUPONT_SECTIONS`.
Al cablearlo destapó una omisión mía en el mismo commit: con `dupont` vacío yo no
pintaba nada, y web sí pinta un panel degradado. Corregido — la regla 6 dice que
un hueco silencioso se lee como «no aplica».

## Verificación

- Frontend: `typecheck` · `lint` · `knip` · **282 tests** (147 web · 44
  `@crisol/ui` · 28 móvil · 60 services · 3 store).
- Backend: el gate nuevo, con 4 tests (existencia del fichero, cobertura en los
  dos sentidos y una regresión nominal de las siete que faltaban).

## Limitaciones conocidas

Del inventario de la auditoría quedan fuera de esta fase, y siguen abiertos:

- La Valoración de móvil pierde `notes[]`, el `reason` de cada múltiplo no
  computable, la capitalización y el tipo de cambio aplicado.
- El mensaje «puedes introducir un precio a mano» en móvil **sin campo** para
  hacerlo.
- Móvil no tiene el aviso de run caducado de PHASE-44.16 ni los
  `blocking_reasons` del perfil ni la sub-pestaña de confianza.
- El buscador de móvil sigue sin la prop `intent`.
- `apps/mobile/.../year-matrix.tsx` **nunca pinta `cell.title`**, así que ningún
  motivo por celda se ve en móvil. Sin tooltips en táctil hace falta otro
  afordance; va con PHASE-44.17, que es donde se decide qué motivo se enseña.

## Próxima fase

PHASE-44.17, la única que queda del plan, y necesita rediseño: su crítica
adversarial encontró ocho problemas de severidad alta (§3.1.b del plan).
