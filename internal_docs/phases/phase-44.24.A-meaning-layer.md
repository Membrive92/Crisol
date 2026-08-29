# PHASE-44.24.A — La capa de significado del informe

**Estado**: 🚧 pendiente prueba manual
**Rama**: `main` (push directo)
**Fecha**: 2026-08-27
**Plan**: [`improvements/phase-44.24-report-legibility-implementation-plan.md`](../improvements/phase-44.24-report-legibility-implementation-plan.md)
**Alcance del usuario**: [`improvements/phase-44.24-report-legibility.md`](../improvements/phase-44.24-report-legibility.md)

## Objetivo

El informe demostraba todo y explicaba poco. PHASE-44.23 puso una definición por
fila; esto añade **por qué importa** y **cómo se lee** a las 64 métricas, la
ficha completa de los 8 scores forenses con sus 27 variables, y la de las 20
banderas con **dónde comprobarlas en las cuentas**.

## Lo que se veía antes

La tarjeta de desglose forense imprimía la clave del motor: en pantalla se leía
`DSRI`, `TATA`, `P4_cfo_supera_beneficio`. Es exactamente el defecto que
PHASE-44.9 cerró para las señales del veredicto —`B4_dividend_funded_externally`
a la cara del usuario— y se cierra con el mismo mecanismo: la etiqueta sale de un
catálogo del engine, no de un diccionario escrito en la pantalla.

## Qué entra

| Pieza | Dónde | Qué |
|---|---|---|
| 64 fichas de métrica | `engine/glossary.py` | `what` · `why` · `reading`, con `MetricDefinition.help` devolviendo `what` |
| 8 fichas de score + 27 variables | `engine/score_help.py` **(nuevo)** | La etiqueta legible de cada `DSRI`, `X1`, `P4_…`, `C3_…` |
| 20 fichas de bandera | `engine/flag_catalog.py` | `what` · `why` · `reading` · **`how_to_verify`** |
| Contrato | `analysis/schemas.py` · `router.py` | `why`/`reading` en el catálogo de métricas; `GET /investment/analysis/help` para scores y banderas |
| Capa compartida | `packages/ui` | `buildScoreHelpIndex`, `helpParagraphs` (orden y rótulos de los tres tramos) |
| Pantalla | web: matriz, tarjeta de score, lista de banderas · móvil: matriz | La `ⓘ` despliega los tres tramos; en la bandera, cuatro |

## Tres decisiones que conviene conocer

**`NamedTuple` y no `@dataclass`, en los tres contenedores.** El gate de
contrato (`_engine_shape`) enumera TODO dataclass definido en cualquier módulo
de `engine/`, así que uno aquí movería la huella del motor y exigiría subir
`ENGINE_VERSION` por un cambio de **metadatos** — que no es un cambio de
fórmula. Verificado empíricamente antes de elegir la forma: con `NamedTuple` el
gate da verde; convertido a `@dataclass` a propósito, se cae con otro hash. La
alternativa «definir el tipo en `presentation/`» queda descartada: crearía el
ciclo `catalog → base_ratios → metrics → glossary → presentation → catalog`.

**Las claves son claves del diccionario, nunca `key=`.** `_emitted_flag_keys()`
escanea `engine/*.py` buscando `key="..."`: escribir `ScoreComponentHelp(key=…)`
haría que las 27 variables se contaran como banderas emitidas sin nombre, y CI
fallaría con un mensaje que no se parece en nada a la causa.

**`help` devuelve `what`, no la concatenación.** El gate de longitud existe
porque el texto se despliega bajo la fila de una tabla y más largo tapa los
números que se venían a comparar. Medido: 33 de las 64 lecturas actuales tienen
menos de cuarenta caracteres —«Más alto, mejor.» es una lectura completa— así
que `reading` lleva un mínimo propio más bajo en vez de obligar a rellenar con
paja.

## Los gates

Ocho, en `test_investment_engine_contract.py`, **todos verificados
rompiéndolos**:

| Gate | Sonda que lo tumba |
|---|---|
| Toda métrica tiene ficha, en las dos direcciones | (de 44.23) |
| Las tres campos de una métrica son útiles y sin umbrales | un umbral con signo en un `why`; un `why` que copia su `what` |
| Todo score tiene ficha | quitar `F6` |
| Toda variable de un score tiene etiqueta, **por score** | quitar `SGAI` de la ficha; renombrar `SGAI` en el motor |
| Los scores sin desglose no declaran variables | dar componentes a `accruals` |
| Las fichas de score son útiles y sin umbrales | «holgado del corte −2,22» |
| Toda bandera tiene ficha | quitar `C6_dilution` |
| Las fichas de bandera son útiles y sin umbrales | «más de 15 puntos» en C1 |

### El escaneo de componentes es ESTÁTICO, y eso no es un detalle

El plan decía «ejecuta `forensic.compute` y compara las claves emitidas». Se
cambió a un escaneo por AST **acotado por función**, por el mismo motivo que el
contrato ya había elegido para las banderas: una ejecución sólo destapa lo que
la fixture del test da la casualidad de ejercitar, y aquí hay una rama viva —el
check de inventario sale del cómputo en los sectores sin inventario material
(PHASE-44.21)—, así que una fixture de una eléctrica habría dejado `C3` fuera
del conjunto emitido **y** fuera de la ficha, con el test en verde y la variable
sin documentar. Acotar por función tampoco es opcional: `forensic.py` construye
otros diccionarios con claves de cadena y un escaneo del módulo entero los
recogería como componentes.

### La regex de umbrales no cazaba un corte con signo

El gate de 44.23 exigía un dígito **sin signo** justo tras la pista, así que
«holgado del corte −2,22» —el ejemplo del propio documento de alcance— la pasaba
entera. Ampliada con el signo y con las pistas «del corte», «corte de», «umbral
de», y subida a nivel de módulo para que los tres glosarios compartan UNA
versión: con una copia por gate, endurecer uno deja los otros con la débil. Las
113 definiciones existentes siguen pasando — sin falsos positivos.

## Cómo se escribieron las 64

Diez redactores en paralelo, uno por familia, **cada uno leyendo el código que
calcula lo suyo** más el texto anterior como materia prima, y un auditor
independiente por bloque que contrasta cada ficha contra la fórmula y devuelve
el texto corregido, no una sugerencia. **20/20 agentes devolvieron resultado** y
los diez auditores encontraron algo: **41 correcciones aplicadas**. Se reporta a
propósito — un resultado vacío por agentes muertos es indistinguible de uno
limpio (lección PHASE-44.14).

Comprobado después: ninguna ficha pierde un matiz que el texto anterior sí
tenía (medias de dos ejercicios, no aplica a financieras, primer año degradado,
sin banda absoluta). Los dos casos que un detector automático señaló resultaron
ser falsos positivos suyos.

## Archivos clave

- `backend/app/modules/investment/analysis/engine/glossary.py` — las 64, con `MetricHelp`.
- `backend/app/modules/investment/analysis/engine/score_help.py` — **nuevo**: 8 scores, 27 variables.
- `backend/app/modules/investment/analysis/engine/flag_catalog.py` — `FLAG_HELP`, 20 banderas.
- `backend/app/modules/investment/analysis/router.py` — `GET /analysis/help`.
- `packages/ui/src/investment-score-help.ts` — **nuevo**: el índice puro.
- `packages/ui/src/investment-matrix.ts` — `helpParagraphs`: el orden y los rótulos, compartidos.

## Endpoints añadidos

- `GET /investment/analysis/help` — fichas de scores (con sus variables) y de
  banderas. Estático, como `/metrics`: es definición del engine, no datos del
  usuario, así que cuelga de la raíz de caché hermana y no se vuelve a pedir al
  invalidar el módulo.

## Migraciones

Ninguna. `ENGINE_VERSION` **no se mueve**: es metadato, no fórmula.

## Verificación

- [x] Backend: ruff · black · mypy 230 ficheros · 636 tests de inversión
- [x] Frontend: typecheck · lint · knip · 126 en `@crisol/ui` (+5), 238 web, 106 services, 83 móvil
- [x] Los ocho gates verificados rompiéndolos, uno a uno
- [x] Los dos tests nuevos de la capa compartida, verificados rompiéndolos
- [ ] **Prueba manual**: Inversión → Análisis → Forense (las tarjetas ya no dicen `DSRI`), y la `ⓘ` de cualquier fila en Ratios/Estados

## Limitaciones conocidas

- **El texto no está versionado con el motor.** Si una fórmula cambia sin que
  nadie toque su ficha, el gate no lo ve: sabe que hay ficha, no que siga siendo
  cierta. Es la misma limitación que declaró 44.23 y sigue abierta.
- **La ficha de bandera no llega a móvil todavía**: la lista de banderas de
  `report-tabs.tsx` no ofrece la `ⓘ`. Va en la entrega E, que es la que cierra
  las ocho piezas de paridad medidas en el plan.
- **`why` y `reading` no se pintan en Valoración**: esa pestaña no es una
  matriz y usa el botón compartido con un solo texto.

## Próxima entrega

**44.24.M** — motor 1.7.0: `ThresholdSpec.origin` persistido (Dec.B) y la señal
de stress de las financieras (Dec.G). Va antes de C y B para que la capa de
presentación lea el campo en vez de inferirlo.
