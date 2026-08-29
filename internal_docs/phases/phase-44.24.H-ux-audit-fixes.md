# PHASE-44.24.H — Auditoría UX del módulo de Inversión

**Estado**: 🚧 pendiente prueba manual
**Rama**: `main` (push directo)
**Fecha**: 2026-08-29

## Origen

El usuario, probando 44.24 en la app viva: _«enlaces que no llevan a ningún
sitio, vistas y cards que no se ajustan a la pantalla como en el resto de la
app»_. Sin más detalle. Una auditoría de seis lentes (enlaces, layout, móvil,
estados vacíos, consistencia visual, responsive) más verificación a mano de lo
que los escépticos no llegaron a mirar dio **33 defectos reales de 41 brutos**.
Una parte importante era de la propia 44.24 —los enlaces de señal, la guía, el
dictamen imprimible, el histórico— y se dice sin rodeos.

## Lo que se veía

### «Enlaces que no llevan a ningún sitio»

| Qué pinchabas | Qué pasaba |
|---|---|
| Una **bandera** en el veredicto (las 20) y «Escenario de stress» | Recargaba la página entera, **cerraba el desglose** que estabas leyendo y te dejaba donde estabas, sin resaltar nada. `locateMetric` no las conocía y caía a `{veredicto, null}`; `hrefForSignal` lo convertía en un enlace a la MISMA pestaña |
| «Tendencia de la caja libre» | Llevaba a Evolución… donde ninguna fila tiene esa clave: aterrizabas arriba, sin marca |
| Cualquier señal | Era un `<a>` plano: cada clic, navegación COMPLETA con parpadeo y skeletons |
| «Cómo leer este informe» | Sin vuelta: «Análisis» en la barra mandaba al buscador vacío |
| «Dictamen imprimible» | Pestaña nueva y nada más. No imprimía, no decía qué hacer, y el sidebar y la cabecera de la app **se imprimían** (el shell no llevaba `data-print`) |
| «comparar ⚠» en el histórico | El motivo del aviso vivía sólo en un `title` (hover) |

### «Cards que no se ajustan como en el resto»

- **Prosa a ancho completo.** El resto acota la prosa dentro de las cards a
  480-520 px; en Inversión nada lo hacía. Las siete cards del Veredicto (la
  captura del usuario era «Alcance»), los ~15 `InlineNotice`/`DegradedPanel`
  que encabezan cada pestaña, el histórico, el comparador y el **hero**, que
  repartía cuatro preguntas con ~300 px de aire entre ellas.
- El **buscador de Análisis a 720 px** en el contenedor exterior: la única
  página índice de la app así. Pasar de Cartera (ancho completo) a Análisis
  encogía la pantalla a una columna.
- El **dumbbell de stress se recortaba** por debajo de ~700 px: SVG de 560 sin
  `viewBox` + `maxWidth: 100%` encoge la caja, no el dibujo.
- Siete pestañas a 390 px: **«Veredicto» quedaba oculta** sin ninguna señal.
- Heatmap sin columna fija; matriz con columna fija sin borde; tabla de señales
  con cinco columnas en 320 px y la columna «Distancia» entera en «—» cuando el
  backend no manda `report`; Evolución con el run 1.0.0 de MCD pintando una
  **tabla con cabecera y cero filas**.
- **18 botones a mano con tres estilos distintos**, ninguno igual al `Button`
  del resto de la app.

### Móvil

- La pestaña de aterrizaje (Veredicto) es la **séptima**: fuera de pantalla, con
  todos los chips visibles en gris y sin auto-scroll.
- Tocar un análisis del histórico **desmontaba la pantalla entera** mientras
  cargaba — el mismo defecto que se corrigió en web y aquí se me pasó.
- Las señales **no navegaban** y las banderas **no tenían ficha**.
- La guía, un `Modal` a pantalla completa **sin área segura**.
- El histórico decía «no hay dos análisis» fuera cual fuera el motivo, nada
  avisaba de que estabas viendo un análisis antiguo, y la etiqueta de la matriz
  se pisaba con la fila siguiente (2 líneas + 2 líneas en un alto fijo).

## Qué se hizo

**Enlaces.** `locateMetric` devuelve `null` para lo que no tiene sitio —sin
destino, sin enlace: la fila se pinta como texto—. Las derivadas dicen ADÓNDE
exactamente: `fcf_trend` resalta la fila `fcf_cfo`; `stress` es un **ancla**
(`#stress-scenarios`) que hace scroll sin recargar. La composición del href sale
de la página a `signalHrefFor` (pura, con tests) y `SignalTable` usa `Link`.

**Prosa.** Un token, `layout.prose = 640`, aplicado en `InlineNotice`,
`DegradedPanel`, las cards del veredicto, el histórico, el comparador y el hero
(cuyo grid de preguntas se acota a `minmax(220px, 320px)`).

**Navegación.** El buscador a `pageWide` fuera y `pageNarrow` dentro. La guía
recibe `?back=` (validado: sólo rutas internas del informe) y pinta «← Volver
al informe». El modo dictamen: el shell se esconde por `[data-app-sidebar]`
/`[data-app-header]` en `@media print`, una barra dice qué es esto con
«Imprimir» y «Cerrar», y **el diálogo se abre solo** cuando el informe ha
cargado, una vez.

**Móvil.** `TabBar` hace scroll a la pestaña activa (`onLayout` + `scrollTo`).
`RunHistory` sale del bloque que exige `ctx` y gana tres estados (cargando ·
no existe · «estás viendo el análisis del X — Volver al último») y el motivo
real del servidor. `GuideSheet` bajo `SafeAreaView`. `TabContext` gana
`goTo(tab, highlight)` y `highlightKey`: las señales navegan con el MISMO
registro que web, las 10 matrices resaltan la fila, y las banderas se abren
con su ficha (`FlagCard`). La pista de la matriz a una línea.

**El resto.** Dumbbell con `viewBox`. `Tabs` con un degradado a la derecha
cuando hay más pestañas. Columna fija con borde en matriz y heatmap. Tabla de
señales a 560 px y sin columna «Distancia» cuando no hay capa de lectura.
Evolución con run viejo → `DegradedPanel` que dice qué motor no la producía
(web y móvil; `EvolutionBlock.horizontal` pasa a opcional por la regla de
PHASE-44.16). Nueve botones migrados a `<Button>` y tres estilos locales
retirados; las dos acciones del hero envueltas como una unidad.

## Lo que NO se hizo, y por qué

- **Tablas → `DataTable`**: la matriz y la tabla de señales tienen celdas fijas
  y agrupadas que `DataTable` no modela; migrar sólo la de cartera dejaría dos
  patrones en el mismo módulo. Follow-up.
- **Elegir la base de la comparación en móvil**: dos selectores para la misma
  pregunta no caben en un teléfono. Se compara contra el anterior, y se dice.
- **`security-search.tsx`**: sus dos botones viven dentro de un formulario de
  búsqueda con su propio estilo; se dejan para la revisión del buscador.
- **Enlace desde una posición de la cartera a su análisis** y **tarjeta de
  Inversión en el dashboard**: son navegación NUEVA, no un enlace roto. Van al
  backlog con su motivo.

## Verificación

- typecheck · lint · knip · web **287** · ui **211** · móvil **90**.
- Tests de EFECTO nuevos: `signalHrefFor` (7), la guía y su vuelta (2 puras +
  1 del hero), la prosa acotada (2), la columna Distancia (2), Evolución con
  run viejo (2 web + 1 móvil), las señales que navegan en móvil (4), la fila
  resaltada en móvil (2).
- **Once sondas, las once muerden.** Tres no mordían a la primera y las tres
  por lo mismo: el arreglo estaba y ningún test miraba ESE efecto — el `href`
  de la guía (el test del hero sólo miraba el del dictamen), la tocabilidad de
  una bandera en móvil (el test miraba que `goTo` no se llamara, y con una
  bandera no se llama de todas formas: había que comprobar `disabled`), y
  Evolución móvil con run viejo (sin test). Se escribieron los tres.

## Dos cosas que salieron de revisar mis propios arreglos

- **Un `Button` migrado perdió su `type="button"` dentro de un `<form>`**: el
  de «limpiar» del simulador de valoración habría hecho submit al pulsarlo. El
  `Button` compartido no fija `type` por defecto, así que dentro de un
  formulario el navegador lo trata como `submit`. Repuesto el `type` en ese
  sitio; los otros ocho migrados no viven en formularios (comprobado).
- **`useSearchParams` en la guía, una ruta estática.** CI hace `next build`, y
  en Next 15 un `useSearchParams` sin límite de suspensión en una página
  prerenderizada es un fallo de build. La página de Análisis de Finanzas ya lo
  hacía así y CI pasa, pero no se apuesta el build a un precedente: el enlace
  de vuelta va en su componente bajo `<Suspense>`. No se ejecutó `next build`
  en local a propósito — comparte `.next` con el dev server en marcha y lo
  tiraría.

## La revisión adversarial de estos arreglos

Cinco lentes sobre el diff (enlaces · dictamen y guía · móvil · layout · los
tests nuevos) con un escéptico por hallazgo. **23/23 agentes vivos, 18
hallazgos, 15 confirmados, 0 sin verificar** — la primera vez en esta familia
de fases que la revisión llega entera y su `confirmados` significa lo que
dice. Los 15 se arreglaron. Los tres refutados: un `type="button"` que la
lente creía perdido y estaba puesto, la robustez del helper `fila()` del test
móvil (RN siempre emite `accessibilityState` cuando `disabled` no es null), y
una sugerencia de cobertura sin defecto detrás.

**Lo que encontró, agrupado por lo que enseña:**

*El modo dictamen no era un modo, era una pestaña forzada.* El selector
«Dictamen · Confianza y datos · Qué ha cambiado» seguía **vivo en pantalla** y
salía en el papel: pulsarlo escribía un `sub` que `printMode` descartaba
después. Las señales seguían siendo enlaces con `tab` forzado, con el mismo
resultado. Y el aviso «el catálogo no se ha podido cargar» se imprimía. Es
exactamente la lección que la fase anterior ya había escrito para las
pestañas —*si un modo IGNORA un control, no lo escondas: no lo renderices*— sin
aplicarla a los otros tres controles de la misma pantalla.

*«Cargado» era el run, no el informe.* El diálogo de impresión se abría 400 ms
después de llegar el run, mientras catálogo de métricas, fichas y partidas
seguían en vuelo: con el backend en frío se imprimía un dictamen con las filas
rotuladas por su clave técnica. Ahora espera a que las cuatro queries hayan
resuelto.

*`window.close()` no cierra lo que no abrió por script.* El enlace del hero
lleva `rel="noreferrer"`, así que la pestaña nace sin opener: Chrome la cerraba
por tener una sola entrada de historial, Firefox no, y con la URL pegada a mano
tampoco. Sustituido por «Volver al informe» (`reportHrefFor`), que funciona
siempre.

*Móvil arrastraba dos defectos que web ya había arreglado.* «Volver a
analizar» con un run viejo seleccionado no borraba la selección —el comentario
de `activeRun` **prometía** que lo hacía— así que el análisis nuevo quedaba
escondido detrás del viejo. Y tocar una señal cambiaba de pestaña sin mover el
`ScrollView`: desde la tercera pregunta del veredicto se aterrizaba a ~1.500 px
de scroll, sin barra de pestañas y sin la fila resaltada a la vista.

*Mi arreglo del dumbbell era peor que el defecto.* Puse `viewBox` para que
escalara, y con él escalaban los rótulos: a 390 px quedaban en 5-6 px,
ilegibles. Vuelto a ancho fijo con scroll en el contenedor, como la heatmap —
que es lo que ya funcionaba a dos ficheros de distancia.

*Y cuatro tests míos que no probaban lo que decían.* El de «la fila que resalta
una derivada EXISTE» comparaba el registro **consigo mismo**: una tautología.
El de «una bandera no tiene destino» miraba dos claves concretas, así que nada
impedía que una bandera entrara en `SECTION_PLACEMENT`. El de «una serie vacía
se pinta» sólo negaba (pasaba por vacuidad). Y el cableado de `highlightKey`
—diez llamadas en móvil, cinco en web— no tenía ningún test: sólo `YearMatrix`
aislada. Los gates que ATAN claves reales se movieron al backend
(`tests/test_investment_report_links.py`): que la serie `fcf_cfo` existe en
`HORIZONTAL_ITEMS`, y que ninguna clave de `FLAG_LABELS` es también una
métrica. Allí es donde viven las claves; en el frontend sólo se puede comparar
el registro consigo mismo.

## Limitaciones conocidas

- El degradado de «hay más pestañas» y el auto-scroll del `TabBar` móvil
  dependen de medidas de layout que jsdom y jest-expo no producen: no tienen
  test automático. Se declara en vez de fingir cobertura.
- El `selectedPending` de móvil tampoco: renderizar la pantalla entera exige
  el router de Expo. Se verifica a mano.
