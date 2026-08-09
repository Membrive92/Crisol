# PHASE-44.14 — Directorio oficial UE/UK (FIRDS) + alta validada (E5 del buscador)

**Estado**: ✅ código completo y verde · ⏳ pendiente prueba manual del usuario
**Rama**: `main` (push directo, convención del proyecto)
**Fecha**: 2026-08-07
**ADR**: [0010 — Identidad sobre registros oficiales](../decisions/0010-identity-official-registers.md)
**Plan del usuario**: [`improvements/phase-44.8-E5-directorio-oficial-eu-uk.md`](../improvements/phase-44.8-E5-directorio-oficial-eu-uk.md)
(criterio: **cero deuda futura**; Twelve Data descartada definitivamente)

## Objetivo

Que Inditex, Iberdrola o Allianz se puedan **encontrar y dar de alta** — la
mitad que faltaba del multi-mercado. La otra mitad (cotizarlos) existía desde
PHASE-44.11 y estaba varada: el mapa de sufijos sabía componer `IBE.MC` pero
ninguna vía podía crear un `Security` con `exchange='XMAD'`.

## La arquitectura en una frase

**Identidad sobre registros oficiales; precios sobre capas tolerantes.** La
capa que no tolera rotura (qué valores existen, con qué nombre, plaza y divisa)
se construye SÓLO sobre registros regulatorios — EDGAR (US, ya en E2), ESMA
FIRDS (UE/EEA) y FCA FIRDS (UK) — locales tras seed. El proveedor de precios
aporta dos comodidades del alta, ambas con salida digna si fallan.

## Qué se construyó

### 1. Tabla `listing_directory` (migración `f2b84a6c1d9e73`)

Global, PK `(isin, mic)`, con `pg_trgm` (primera extensión que activa el
proyecto aparte de las de la imagen). Sembrada: **3.012 filas** (2.141 ESMA +
871 FCA) en 12 mercados: XMAD, XLON, XETR, XPAR, XAMS, XBRU, XLIS, XMIL, XWBO,
XCSE, XSTO, XHEL, XOSL.

### 2. Parser FULINS (`catalog/firds.py`, streaming)

Los ficheros reales del 2026-08-01 miden 366+140 MB (ESMA) y **809 MB** (FCA)
descomprimidos; `lxml.iterparse` con liberación por elemento. Filtro: CFI `ES*`
(acciones; ETFs = añadir `'CE'` a la constante, decisión ya tomada: NO ahora),
segmento admitido, sin `TermntnDt` pasada.

### 3. Seed idempotente (`scripts/seed_listing_directory.py`)

Descarga por las APIs máquina-a-máquina (verificadas golpeándolas: ESMA es
Solr; la FCA es Elasticsearch y NO entiende `NOW-9DAYS`, fechas explícitas),
se queda con el set del sábado más reciente, y sincroniza con semántica de
**espejo honesto**: compara campo a campo, escribe sólo lo que cambió, elimina
los deslistados — con un suelo (`MIN_ROWS_TO_PRUNE`) para que un fichero
truncado no vacíe el directorio. Segunda pasada real: **0 escrituras**.
`--dry-run` y `--from-dir` (ZIPs locales, sin red). Sin cron: el refresh es
re-ejecutar el comando, y la UI declara la fecha del último seed.

### 4. Búsqueda unificada (tercera capa local)

Catálogo → índice SEC → directorio, sin red ninguna. Por nombre (subcadena +
`word_similarity` de pg_trgm para erratas), por `ShrtNm` y por ISIN exacto.
Dedupe capa 1↔3 por `(isin, plaza)`. El aviso «ITX → Inditex» **desaparece**:
Inditex sale de verdad — su `ShrtNm` registral es `ITX/AC 0.03`, así que el
ticker local funciona por DATOS, no por alias. El mapa de alias queda reducido
a la frontera suiza (NESN, ROG, NOVN: SIX no reporta a FIRDS).

### 5. Alta validada (`ext:<MIC>:<ISIN>` en `listing_key`, con checksum ISO 6166)

Flujo del plan §4, con el resolver inyectable (`ExternalListingResolver`):

1. Identidad de FIRDS (nombre, divisa, plaza) — nada del proveedor.
2. Resolución ISIN→símbolo (Yahoo `Search`). Si no hay → **422
   `ticker_required`** con la identidad pre-rellenada; el formulario pide el
   símbolo local. Degradación diseñada, no fallo.
3. Cross-check sufijo↔MIC contra el mapa de `pricing/adapters/yfinance.py`
   (accesor público `suffix_for_venue` — una sola definición). Discrepancia →
   parada con mensaje, jamás auto-alta.
4. **Validación por cotización** (regla universal): `probe_symbol` reutiliza
   `_fetch_one` del adapter — la misma normalización GBp→GBP, no una copia.
   Sin cotización real no se persiste nada.
5. `Security`: ticker sin sufijo, `exchange=MIC`, divisa registral, `cik=NULL`,
   `analysis_status='not_supported'`. Divisa proveedor≠registral: se loguea y
   la regla D4 vigente la marca en la posición.

### 6. Frontend (web + móvil)

Filas del directorio identificadas por nombre + plaza + divisa + ISIN (sin
ticker inventado), formulario inline de `ticker_required`, mensajes del
servidor con motivo, y el estado «directorio sin sembrar» declarado.

## Los tres hallazgos que doblaron el plan (todos con datos, no con opinión)

1. **FIRDS reporta en MICs de SEGMENTO, no operativos.** Allianz no aparece en
   `XETR` en ningún registro: aparece en `XETA` («Regulierter Markt»). Y
   `XMAD` es a su vez segmento del operativo `BMEX`. Con el filtro literal del
   plan, **Alemania entera quedaba fuera**. Solución: mapa curado
   segmento→operativo contra el registro ISO 10383 (CSV oficial), con colapso
   por prioridad (XETA gana a XETU/XEMA) — la columna `mic` habla el mismo
   vocabulario que `securities.exchange` y el mapa de sufijos.
2. **Los tablones alemanes cotizan el mundo entero.** Frankfurt (`FRAB`) trae
   12.298 filas de equity ella sola — cruces de todo, valores US incluidos.
   Meterlos habría creado los duplicados de presentación que el plan excluye
   con los MTF. Por eso `XFRA` no se siembra aunque el mapa de sufijos sepa
   cotizarlo (`.F` queda para altas manuales).
3. **El FULINS de la FCA trae también venues europeos** (Kontron y Commerzbank
   en XETR, valores nórdicos…). Lo cazó el **dry-run del seed** con un choque
   de PK — el camino de escritura probado antes de aplicar, la lección
   [PHASE-44.13] pagando dividendo a las 24 horas. Solución: partición
   jurisdiccional (`UK_VENUES`): cada registro se queda con su regulador.

## Los puntos de parada del plan, resueltos

| Parada | Resultado |
|---|---|
| (a) Spike ISIN→símbolo | 7/8 con exactamente un resultado (`ITX.MC`, `IBE.MC`, `ALV.DE`, `MC.PA`, `AZN.L`, `BP.L`, `SHEL.L`). Unilever `GB00B10RZP78` falla en `Search` Y en `Lookup` — y tampoco está en la FCA FIRDS: el ISIN está muerto. La degradación manual no es un adorno |
| (b) API de la FCA | Confirmada: Elasticsearch, fechas explícitas, `hits.hits[]._source` |
| (c) Particionado/streaming | Sin sorpresas: iterparse recorre los 3 ficheros en ~30 s |
| (d) MIC fuera del seed | No aplica a la cartera actual; la desviación XFRA/segmentos quedó documentada aquí y en el código |

## Verificación (contra la BD real y los proveedores vivos, además de los tests)

**Búsqueda contra el directorio sembrado**: `inditex` → XMAD ✓ · `ITX` → XMAD ✓
(por ShrtNm, sin alias) · `iberdrola` ✓ · `allianz` → XETR ✓ (la normalización de
segmento, en vivo) · `Iberdola` (errata) ✓ · `shell` → sus DOS listings reales
(XAMS/EUR y XLON/GBP) ✓ · `ES0148396007` ✓ · `santandr` → Madrid y Londres ✓.

**Cadena del alta contra los proveedores reales** (lo que los dobles de test no
pueden probar): `ES0148396007` → `ITX.MC` → cotización **58,66 EUR**;
`ES0144580Y14` → `IBE.MC`; `DE0008404005` → `ALV.DE` → **433,50 EUR**. La divisa
del proveedor coincide con la registral en los dos, así que la bandera D4 no se
dispara. Un símbolo inexistente devuelve `QuoteError` y para el alta;
`GB00B10RZP78` (Unilever) devuelve lista vacía → `ticker_required`. Ese ISIN
tampoco está en el FIRDS de la FCA: está muerto, y la degradación es el camino
correcto para él.

- Backend: ruff · black · mypy 219 ficheros · migración `upgrade`/`downgrade`
  reversible, cabeza única, `alembic check` sin drift · **la cadena completa
  aplicada sobre una base creada desde cero** (30 tablas, extensión `pg_trgm` y
  los dos índices de `listing_directory`) — es lo que normalmente sólo se ve en
  el runner de CI, y la extensión es lo primero que podría fallar allí por
  permisos · **26 tests nuevos**
  (9 del parser FULINS + el contrato sembrable↔cotizable, 17 del directorio,
  el sync y el alta) · suite completa verde al cierre.
- Frontend: typecheck · lint · knip · 3 tests web nuevos (fila del directorio,
  flujo `ticker_required` completo con reintento, y la regresión del estado
  pegajoso).

**Dos defectos propios cazados en la autorrevisión** (la multi-agente murió por
límite de sesión y se sustituyó por lectura crítica):

1. **El borrado del sync no se ejecutaba en ningún test.** El fixture real tiene
   5 filas y el suelo son 100, así que todos los tests corrían por debajo: sólo
   estaba probado que el guardarraíl salta, nunca lo que protege. Cerrado con
   tres tests sobre lotes sintéticos (borra de verdad · un cambio real se
   escribe y mueve `seeded_at` · sembrar una fuente no toca la otra).
2. **Estado pegajoso en el buscador**: el formulario de ticker manual sobrevivía
   al cambio de consulta, así que quedaba apuntando al listing anterior y pulsar
   «Añadir» habría dado de alta el valor equivocado. Corregido en web y móvil,
   con regresión.
- Seed real aplicado dos veces: **3.012 filas** (2.141 ESMA + 871 FCA), luego
  0 nuevas / 0 cambiadas / 0 eliminadas. Invariante comprobado contra la BD:
  ninguna plaza aparece en dos fuentes.

## Limitaciones conocidas

- **Suiza es frontera documentada** (ADR-0010 §5): SIX no reporta a ESMA ni a
  la FCA. Alta manual o ADR US; si algún día pesa, sería un tercer seed.
- Los mercados SME/growth (AIM, Euronext Growth, First North, BME Growth) no se
  siembran — decisión de alcance, revisable añadiendo filas al mapa de
  segmentos.
- El alta `ext:` exige red (resolución + validación por cotización). Sin red no
  hay alta europea — deliberado: nada se persiste sin ver una cotización.
- La búsqueda del directorio no pagina; con ~3K filas y `limit` del endpoint es
  irrelevante (crecerá un orden de magnitud con ETFs, sigue siendo pequeño).
- ETFs fuera del seed (decisión del usuario, plan §9): entrarán como datos
  (`'CE'` en `INCLUDE_CFI_PREFIXES` + enum + barrera por `security_type`).

## Próxima fase

Sin decidir. Candidatos: E3 del buscador (combobox rico con teclado), E4
(alta desde Cartera en móvil — hoy esa pantalla es de sólo lectura), o los modos
«% común»/«Δ%» de los estados en móvil.
