# ADR-0008 — El buscador de valores es local-first, y el mercado lo decide el servidor

**Estado**: aceptada
**Fecha**: 2026-07-25
**Fase**: PHASE-44.8 (Entrega 1 implementada; Entregas 2-5 planificadas en
[`improvements/phase-44.8-investment-search-hybrid.md`](../improvements/phase-44.8-investment-search-hybrid.md))
**Sustituye a**: el buscador de tres pasos descrito en
`improvements/ARCHITECTURE-investment-module.md` §5 y el papel de «symbol search»
que `improvements/DESIGN-v2-investment-module.md` §7 asignaba a Finnhub.

---

## Contexto

El diseño original resolvía el buscador así: (1) catálogo local, (2) si hay pocos
resultados, `symbol_search` del `PriceAdapter` (Finnhub) para cubrir otros
mercados, (3) al elegir un hit externo, `POST /resolve` con `{ticker, exchange}`.

Al implementarlo aparecieron dos hechos que invalidan ese diseño:

1. **El `/search` de Finnhub no devuelve la bolsa.** Sus únicos cuatro campos son
   `description`, `displaySymbol`, `symbol` y `type` (verificado contra su OpenAPI
   oficial). La implementación que existía rellenaba `exchange` con
   `displaySymbol`, que es un ticker de visualización: un buscador multi-mercado
   sin mercado. El endpoint que sí trae `mic` y `currency` es `/stock/symbol`, que
   no es un buscador sino un listado **por bolsa**.
2. **Que el cliente aporte el `exchange` es un defecto de diseño, no un detalle.**
   La restricción única del catálogo es `(ticker, exchange)`. El frontend mandaba
   `'US'` —un país— y el móvil también, así que el mismo valor podía existir como
   `MCD/US` y `MCD/NYSE`: dos filas, dos ingestas, dos `AnalysisRun` y los lotes
   de cartera repartidos entre dos ids.

Y un tercero, sobre el alcance: el motor forense **sólo** puede correr sobre
filers de la SEC, porque necesita XBRL con taxonomía us-gaap. Ninguna fuente
gratuita **con licencia usable** cubre mercados europeos (verificado: Twelve Data
lo cubre técnicamente pero su ToS prohíbe caché persistente y uso comercial;
OpenFIGI tiene licencia de dominio público pero limita `/v3/search` a 5 req/min y
no devuelve ni divisa ni MIC).

## Decisión

1. **El buscador es local-first.** Capa 1: catálogo. Capa 2 (Entrega 2): índice
   en memoria de los ~10.400 emisores que la SEC conoce, desde el parquet que
   `edgartools` ya empaqueta — sin red, sin API key, sin tabla nueva y sin cron.
2. **El mercado lo decide el servidor.** `exchange` pasa a ser opcional y no
   vinculante: se normaliza contra un vocabulario (`catalog/venues.py`) donde un
   país **no** es una plaza, y la idempotencia real pasa a ser `(cik, ticker)` —
   la identidad del instrumento— en vez de la clave de la tabla. La Entrega 2
   sustituye el `exchange` del body por un `listing_key` opaco.
3. **La regla de «se puede analizar» vive en un solo sitio**
   (`catalog/capabilities.py`) y responde **con motivo**, para poder decirlo en la
   fila antes del clic en vez de fallar después.
4. **Buscar símbolos deja de ser responsabilidad del proveedor de precios.**
   `PriceAdapter.symbol_search` y `SymbolHit` se retiran (no tenían ningún
   consumidor). La capa 3 externa, si se activa, vivirá en su propio contrato
   `catalog/adapters/symbol_search/`, apagada por defecto
   (`investment_symbol_provider="none"`) y **sólo** en la pestaña de Cartera.
5. **Nada del proveedor externo se persiste.** Caché en memoria con TTL corto. No
   se descarga su volcado de instrumentos a Postgres.

## Consecuencias

**A favor**

- El buscador funciona sin red y sin credenciales, que es el modo por defecto del
  proyecto.
- Deja de existir la clase de bug «el mismo valor duplicado por discrepar en la
  etiqueta del mercado».
- Un valor no analizable se puede marcar como tal en la fila; hoy el usuario lo
  descubría con un error después de elegirlo.
- Cambiar de proveedor externo (Twelve Data gratis → EODHD comercial: €399/mes
  uso interno, €2.499/mes con display a clientes) es un adapter, no un rediseño.

**En contra, y asumido**

- **No hay multi-mercado en la Entrega 2.** `ITX`, `IBE`, `VOO` y `NESN` no
  existirán en el buscador hasta que se active la capa 3. La UI debe decirlo por
  su nombre en vez de devolver ruido.
- El índice empaquetado se congela con la versión de `edgartools`: ~7% de deriva
  frente al fichero vivo de la SEC (388 tickers ausentes + 341 ya deslistados).
- Se desvía de la ARCHITECTURE original, que queda corregida en el mismo commit
  para que no describa un buscador que ya no existe.

## Deuda declarada de la Entrega 1

- ~~`capabilities_for` reproduce el predicado anterior mientras no exista
  `securities.analysis_status`.~~ **Resuelto en la misma entrega.** La columna se
  adelantó de la Entrega 2 al cerrar el callejón de SPY, porque la alternativa
  —negarse a crear el `Security`— habría roto el caso legítimo de tener SPY en
  cartera. La regla sigue respondiendo lo mismo cuando la columna es NULL, así
  que la equivalencia del movimiento se mantiene demostrable (lección PHASE-34).

  Recuentos verificados ejecutando `edgartools` contra la SEC:

  | Valor | 10-K | 20-F | `analysis_status` |
  |---|---|---|---|
  | MCD | 33 | 0 | `ok` |
  | SPY | 0 | 0 | `no_annual` — es un vehículo, no una empresa |
  | SAN | 0 | 25 | `non_gaap` — publica, pero en IFRS |
  | ASML | 0 | 27 | `non_gaap` |

  Los tres ceros no son el mismo cero, y por eso hay dos recuentos y no uno:
  decirle a alguien que Santander «no publica cuentas anuales» sería falso.

  El veredicto es una foto. Los que **bloquean** se re-verifican cada vez que
  alguien resuelve ese valor —reintentar sobre algo bloqueado es justo cuando al
  usuario le importa—; un `ok` se conserva, porque un emisor no deja de publicar
  de un día para otro y no vale una petición en cada alta.
- `resolve_security` sigue escribiendo `currency='USD'` y `accounting_std=GAAP`.
  Afinarlo exige contar filings (red), y etiquetar IFRS «por si acaso» sería un
  no-op numérico —`thresholds/seed.py` genera los mismos cortes para las tres
  normas— que además movería el `thresholds_hash` de los runs ya guardados.

  **Acoplamiento latente, y es la parte importante de esta deuda.** Hoy la
  etiqueta falsa no mueve ningún número porque `annual.ANNUAL_FORMS` sólo admite
  `10-K`: el 20-F de un ADR (SAN, ASML, SAP — verificado en sus `submissions`)
  nunca entra en el pipeline, así que la ingesta falla antes de producir un
  estado. El día que alguien añada `20-F` a ese conjunto para dar soporte a
  IFRS, `accounting_std` pasa a ser load-bearing **de golpe** y esos estados se
  analizarían con cortes calibrados en US-GAAP sin decirlo. Quien toque
  `ANNUAL_FORMS` tiene que arreglar `accounting_std` en el mismo commit.
- `pandas` entra como dependencia transitiva de `edgartools` y no está declarada
  en `pyproject.toml`. La Entrega 2 la usa para leer el parquet: importarla
  **dentro** de la función, no a nivel de módulo (~1 s en cada arranque).
