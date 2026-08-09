# PHASE-44.15 — Entregas 3 y 4 del buscador, y cuatro deudas cerradas

**Estado**: ✅ código completo y verde · ⏳ pendiente prueba manual del usuario
**Fecha**: 2026-08-07
**Cierra**: la [PHASE-44.8](../improvements/phase-44.8-investment-search-hybrid.md)
entera (E1→E5) y cuatro entradas del backlog.

## Objetivo

Terminar el buscador y quitar de en medio la deuda que ya no era teórica —
señaladamente una mina que llevaba tres fases documentada como «arréglalo el día
que alguien toque X».

---

## 1. La mina: `accounting_std` fijo a GAAP

`resolve_security` escribía `accounting_std=GAAP` para **todo**, ADR europeos
incluidos, con esta nota: «quien toque `ANNUAL_FORMS` arregla esto en el mismo
commit». Un recordatorio escrito a mano que nadie recalcula — el mecanismo que
`lessons.md` documenta siete veces.

**Por qué se podía arreglar ahora y no antes.** Hacían falta dos piezas que ya
existen: la evidencia (`analysis_status`, PHASE-44.8 — SAN: 0 diez-kás y 25
veintiefes → `non_gaap`) y la reproducibilidad de los runs viejos
(`thresholds_used`, PHASE-44.9). Con las dos puestas, mantener el literal dejó
de ser prudencia.

`accounting_std_from_status` deriva la norma de la evidencia, y **no es
cosmético**: `thresholds/seed.py` siembra los cortes de IFRS/PGC con
`model_variant='uncalibrated'`, que es la declaración honesta de «estos cutoffs
son US-GAAP y aquí se aplican sin recalibrar». La etiqueta viaja además CON la
evidencia al re-resolver: si no, un emisor que empieza a presentar 10-K se
quedaría IFRS para siempre — la premisa caducada que la derivación viene a
evitar.

## 2. Ranking: la matriz primero

`santander` dejaba `SAN` en 3.ª posición. Los tres candidatos empatan a
puntuación (token exacto, misma plaza) y desempataba el ticker alfabéticamente:
`BSAC` < `BSBR` < `SAN`.

El criterio correcto estaba en el dato: `Banco Santander, S.A.` es **sólo** lo
buscado más su forma jurídica; los otros añaden un calificativo (BRASIL, CHILE).
`name_specificity` cuenta tokens significativos —descartando forma societaria
(`S.A.`, `plc`, `Inc`, `Corp`…)— y desempata por el menor.

Efecto no buscado y verificado en vivo: `johnson` pasa a devolver **JNJ**
primero, que antes salía detrás de Johnson Controls por el mismo motivo.

## 3. Dos dependencias que ya no eran incidentales

`pandas` y `lxml` entraban como transitivas de `edgartools`/`yfinance`. Desde
44.13 y 44.14 las usan el índice del buscador (la ruta pyarrow devuelve la tabla
sin la columna `exchange`, así que no hay alternativa) y el parser FIRDS.
Declaradas en `pyproject.toml`; el lock no se mueve porque ya estaban pineadas.

## 4. Las 14 tablas del módulo, en `schema.md`

Llevaban desde 44.1 fuera del documento que dice ser el estado del schema. Ahora
están, con su ámbito GLOBAL/SCOPED, PK, FKs y qué guarda cada una, más los ocho
enums del módulo y por qué `analysis_status` **no** es un enum nativo.

---

## 5. Entrega 3 — el combobox accesible

`security-search.tsx` deja de ser una lista de botones:

- `role="combobox"` con **nombre accesible** (`<label>` oculto, no `aria-label`:
  una sola fuente del nombre), `aria-expanded`, `aria-controls`,
  `aria-autocomplete` y `aria-activedescendant`.
- Teclado completo: ↑ ↓ recorren, Enter elige, Esc limpia. Enter sobre una fila
  bloqueada **no hace nada** — el motivo ya está visible; tragarse la pulsación
  en silencio sería peor.
- Lista `role="listbox"` con opciones `role="option"` + `aria-selected`.

**La prop `intent`** decide qué es seleccionable, y no es un detalle de estilo:
en Análisis, elegir SPY lleva a un callejón (tiene CIK, así que la ingesta se
lanza y falla, y el mensaje manda a lanzarla otra vez). Ahora sale
`aria-disabled` **con el motivo pintado** — no en un `title`, que en táctil no
existe y con lector de pantalla llega tarde. En Cartera ese mismo valor es
válido: registrar una compra sólo necesita coste y divisa.

## 6. Entrega 4 — el alta de compra en móvil

La pantalla de Cartera era de sólo lectura desde 44.7 y decía literalmente
«añádelas desde la web». Lo que faltaba no era el buscador —ya lo tenía desde
44.13— sino el formulario. Ahora existe, con los mismos tres campos y el mismo
endpoint que la web, más dos cosas propias del móvil:

- **Coma decimal**: en un teclado español es lo natural, y el backend espera
  `Decimal` con punto. Se convierte antes de enviar.
- **No se pide el tipo de cambio.** Lo deriva el servidor del BCE a la fecha de
  la operación (44.11); un campo aquí invitaría a rellenarlo con un `1`, que es
  exactamente el dato ficticio que costó el lote de JNJ.

## 7. Los estados de móvil, en sus tres modos

El selector «Importe / % común / Variación» que la web tenía y móvil no, aunque
`buildStatementRows` (compartido) ya lo soportaba. Con la nota de qué significa
cada modo: un «% común» sin decir sobre qué base se calcula (ventas en el P&L,
activo total en el balance) es un número sin lectura.

---

## 8. Dos defectos que sólo aparecieron al LEVANTAR la app

Ninguno de los dos lo veía la suite, porque los tests inyectan un índice de dos
o tres filas y el defecto necesita el ruido de 10.365 emisores reales más el
directorio sembrado. Los dos son de la **misma familia**: el orden de las capas
pisando la calidad de la coincidencia.

1. **Una corrección ortográfica desplazaba a una coincidencia literal.**
   `allianz` no tiene NINGUNA coincidencia exacta en la SEC, así que su fuzzy
   proponía `ALLIANT`, `RALLIANT` y `ALLIANCE` —otras empresas— y esas filas
   llenaban el cupo **antes** de que el directorio ofreciera `Allianz SE`, que
   casa exacto por nombre. Buscar «allianz» no devolvía Allianz. El fuzzy es un
   último recurso por diseño; el error era que lo fuera *dentro de su capa* en
   vez de *entre todas*. Ahora el orden es: exacto de la SEC → directorio →
   fuzzy de la SEC.
2. **Un ticker tecleado entero perdía contra un prefijo de otra capa.** Con
   McDonald's en el catálogo, teclear `MC` devolvía `MCD` (prefijo, capa 1) y
   dejaba fuera a Moelis, cuyo ticker **es** `MC`. Preexistente. Lo arregla
   `_exact_ticker_first`, que adelanta lo que casa al 100 % venga de donde
   venga y deja el resto del orden intacto.

Comprobado tras el arreglo contra la BD real, con las tres capas: 13 de 13
consultas devuelven lo esperado en primera posición —incluidas `allianz`→XETR,
`iberdrola`→XMAD, `lvmh`→XPAR y `shell`, que devuelve sus **tres** cotizaciones
reales (NYSE, Ámsterdam y Londres)—. Los dos tests de regresión se validaron
reintroduciendo los bugs: caen los dos.

`Macdonald` pasa a devolver `Brooks Macdonald Group` (XLON) antes que MCD, y se
deja así a propósito: «MACDONALD» es un token literal de ese nombre y MCD sólo
casa por corrección ortográfica. La regla nueva dice que lo literal manda, y
aplicarla con excepciones para que una consulta concreta luzca mejor es cómo se
rompen las demás. MCD sigue saliendo, en segunda posición.

## Verificación

- Backend: suite completa · ruff · black · mypy · 4 tests nuevos del catálogo
  (norma derivada, norma que viaja con la evidencia) y 3 del ranking.
- Frontend: typecheck · lint · knip · **12 tests** del combobox (de 8) y **4**
  del alta móvil.
- Ranking comprobado contra el índice REAL de 10.365 emisores: `santander`→SAN ·
  `coca`→KO · `johnson`→JNJ · `MC`→Moelis · `Macdonald`→MCD · `realty income`→O ·
  `spy`→SPY.

## Limitaciones conocidas

- El combobox no hace auto-scroll de la opción activa: con `limit=20` y la lista
  corta que devuelve el buscador no se ha visto necesario, pero con listas
  largas la opción activa puede quedar fuera de vista.
- El alta móvil pide la fecha como texto `AAAA-MM-DD` con validación, no con el
  date-picker nativo que sí usa Finanzas Domésticas (PHASE-14.3). Reutilizarlo
  es un follow-up barato.
- `intent="analysis"` sólo se pasa desde la página de Análisis; el formulario de
  compra usa el default `portfolio`. Correcto, pero es un acoplamiento por
  convención: si aparece una tercera pantalla, hay que acordarse.

## Próxima fase

Sin decidir. Lo que queda con más valor: los **gráficos del informe** (evolución
common-size, escenarios de stress, heatmap de Δ%), que es lo único grande que
sigue siendo «todo en tablas».
