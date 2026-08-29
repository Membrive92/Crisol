# PHASE-44.23 — Qué es cada fila del informe

**Estado**: 🚧 pendiente prueba manual
**Rama**: `main` (push directo)
**Fecha**: 2026-08-23

## Objetivo

Que el usuario pueda estar seguro de qué está leyendo en cada fila del informe
de análisis, sin salir de la pantalla. Lo pidió así: _«quiero añadir en todas
las pestañas del análisis una i de información de qué es cada métrica para que
un usuario esté seguro de lo que está leyendo»_.

## El problema

El informe pinta **64 métricas y 49 partidas** con su valor, su unidad y su
banda, y la única pista de qué eran era la etiqueta. Una etiqueta no basta:
«Prueba ácida» y «Ratio de caja» son cosas distintas y quien no las conozca no
puede saber cuál está mirando, ni si el número es bueno porque sube o porque
baja. Y hay decisiones del motor que **sólo se pueden saber leyendo el código**:
que varios ratios usan la media de dos ejercicios, que S4 parte del EBIT
reportado mientras S2 y S4b usan el limpio, que «Total pasivo» a menudo no viene
en el filing y se deduce restando.

## Dónde vive el texto, y por qué ahí

En el **engine**, junto a la fórmula: `analysis/engine/glossary.py` (64) y
`fundamentals/glossary.py` (49). Viaja por la API en el mismo catálogo que ya
llevaba la etiqueta y la unidad, así que web y móvil lo reciben sin escribir un
literal.

La alternativa —un diccionario en la interfaz— es exactamente el mecanismo que
produjo tres rótulos mentirosos en PHASE-44.9 (F5, F6 y D8 anunciaban una cosa y
enseñaban otra). Una definición miente igual de fácil y es **más difícil de
detectar**, porque nadie la contrasta con la fórmula y porque tres frases se
creen más que un rótulo.

## Los cuatro gates

En `test_investment_engine_contract.py`, junto a la huella del motor:

1. **Toda métrica del catálogo tiene definición** — y en las dos direcciones:
   falta una (métrica nueva sin documentar) y sobra una (definición huérfana de
   una métrica renombrada).
2. **Toda partida canónica tiene definición**, igual.
3. **Ninguna es tautológica ni impresentable** — ni repite la etiqueta, ni baja
   de 40 caracteres, ni pasa de 320 (el texto se despliega bajo la fila de una
   tabla; más largo tapa los números que se venían a comparar).
4. **Ninguna escribe un umbral a mano.** Las bandas se calibran por sector desde
   PHASE-44.21 y viajan en el propio run; un corte en prosa caduca en silencio y
   acaba contradiciendo al semáforo que tiene al lado. El gate caza las cuatro
   formas de escribirlo en español («por encima de 1,5», «superior al 30 %»,
   «> 2», «baja de 0,8») y deja pasar los números legítimos («media de dos
   ejercicios», «sobre 9 puntos», «vence en 12 meses»).

Los cuatro **verificados rompiéndolos**, uno a uno.

## El afordance

**Web**: un botón `ⓘ` junto a la etiqueta que despliega el texto en una fila
bajo la suya. No es un `title=` a secas por tres razones concretas: la tabla vive
dentro de un `overflow-x: auto` y un flotante se recorta en el borde; un tooltip
nativo no lo abre el teclado; y dos o tres frases taparían la tabla. El `title`
se pone igualmente, porque con ratón leerlo al pasar por encima es más rápido
que pulsar. Una sola definición abierta a la vez — con 49 partidas en pantalla,
varias abiertas convierten la tabla en un muro de texto.

**Móvil**: se abre **tocando la etiqueta**, y el texto sale en el panel que ya
existía para explicar el motivo de una celda. En táctil no hay hover, así que un
`title` no existiría (la lección de PHASE-44.15, que ya obligó a sacar un motivo
de un `title` en el buscador).

Cubre las cinco pestañas que son matriz (Estados, Ratios, Evolución, Forense,
Dividendo) más **Valoración**, que no lo es —un múltiplo no tiene serie: se
calcula contra la cotización de hoy— y por eso se cableó aparte con el mismo
botón compartido. Veredicto ya explicaba cada pregunta desplegando sus señales
con valor, banda y motivo.

## Cómo se escribieron las 113

Dos workflows de agentes en paralelo, **cada bloque leyendo el código que
calcula lo suyo** y con un auditor independiente por bloque que contrasta la
definición contra la fórmula. 8/8 bloques de métricas y 3/3 de partidas
devolvieron resultado —se reporta a propósito: un resultado vacío por agentes
muertos es indistinguible de uno limpio (lección PHASE-44.14)—.

El resultado cita cosas que no están en ningún nombre: que A2 y A3 comparten
denominador y difieren en el numerador, que S1 **no** es el apalancamiento del
DuPont, que S3 y S1 dejan de ser pruebas independientes cuando el pasivo total se
deriva, que el capex se guarda en positivo aunque sea una salida de caja.

## Archivos clave

- `backend/app/modules/investment/analysis/engine/glossary.py` — las 64.
- `backend/app/modules/investment/fundamentals/glossary.py` — las 49.
- `backend/tests/test_investment_engine_contract.py` — los cuatro gates.
- `apps/web/components/investment/help-toggle.tsx` — el botón compartido.
- `apps/web/components/investment/year-matrix.test.tsx` — el afordance.

## Migraciones

Ninguna. El texto es estático y no toca la base.

## Limitaciones conocidas

- **El texto no está versionado con el motor.** Si una fórmula cambia sin que
  nadie toque su definición, el gate no lo ve: sabe que hay definición, no que
  siga siendo cierta. La huella de `ENGINE_VERSION` obliga a pasar por el
  contrato al cambiar la forma, pero no al cambiar un numerador.
- Móvil abre la definición tocando la etiqueta, sin icono propio más allá del
  `ⓘ` al final del texto; en etiquetas de dos líneas queda al final de la
  segunda.
