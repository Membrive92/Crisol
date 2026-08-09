# ADR-0010 — Identidad sobre registros oficiales; precios sobre capas tolerantes

**Estado**: aceptada (usuario, 2026-08-07) · **Fase**: PHASE-44.14 (E5 del buscador)
**Relacionadas**: [ADR-0008](0008-investment-symbol-search.md) (buscador local-first),
[ADR-0007](0007-investment-global-tables.md) (tablas globales),
ADR-0009 (FX único vía `currency`).

## Contexto

El buscador de valores cubre los emisores de la SEC (E2: índice local de
~10.400 filas) y nada más: Inditex, Iberdrola o Allianz no se pueden encontrar
ni dar de alta, pese a que el `PriceAdapter` de yfinance ya sabe cotizarlos
(mapa de sufijos por MIC desde PHASE-44.11). El multi-mercado necesita una
fuente de **identidad**: qué valores existen, con qué nombre, en qué plaza y en
qué divisa.

Las opciones evaluadas para esa fuente:

1. **Twelve Data** (plan original de 44.8): símbolo + nombre + MIC + divisa sin
   API key. Su ToS prohíbe cachear en local y el uso comercial del plan gratis.
2. **La búsqueda de Yahoo** como directorio: sin licencia clara, contrato no
   documentado, puede cerrar o cambiar sin aviso.
3. **Registros regulatorios FIRDS**: ESMA (UE/EEA) y FCA (UK) publican
   semanalmente el universo completo de instrumentos admitidos a negociación,
   en XML ISO 20022, dominio público, con identificadores registrales (ISIN,
   MIC, LEI, CFI).

## Decisión

**La capa de identidad se construye SÓLO sobre registros oficiales**:

- **US**: EDGAR (ya sembrado en E2 — el parquet de la SEC).
- **UE/EEA**: ESMA FIRDS (ficheros FULINS de equity).
- **UK**: FCA FIRDS.

Se materializa en una tabla global `listing_directory` (sin `user_id`, extiende
ADR-0007), sembrada por un comando idempotente y consultada **en local, sin
red**. Los identificadores del catálogo son los registrales — los mismos que
usan el bróker y la información fiscal del usuario; ninguna convención
propietaria de un proveedor de precios entra en la identidad.

**Los precios siguen en capas tolerantes** (yfinance tras selector, PHASE-44.11):
un proveedor de precios puede degradarse, cachearse o sustituirse sin tocar la
identidad. La resolución ISIN→símbolo de Yahoo se usa **sólo como comodidad del
alta** y con bypass manual: si falla, el formulario pide el ticker a mano con
todo lo demás pre-relleno desde FIRDS. Verificado en el spike del 2026-08-07:
7 de 8 ISINs resuelven con exactamente un resultado; Unilever
(`GB00B10RZP78`) falla en `Search` y en `Lookup`, así que la degradación no es
un adorno.

**Twelve Data queda descartada definitivamente** — una licencia que prohíbe
cachear y el uso comercial es una hipoteca sobre el proyecto entero, no una
dependencia. **Yahoo como directorio, descartado** — nada no-oficial en la capa
que no tolera rotura.

## Por qué esto no genera deuda

- El refresh del directorio es re-ejecutar un comando (datos), no tocar código.
- Si Yahoo muere: el directorio ni se entera; el alta degrada a ticker manual;
  los precios tienen su escalera documentada (EODHD).
- Ampliar cobertura es datos: ETFs = añadir `'CE'` a la constante de prefijos
  CFI; otro país = otro seed. Suiza (SIX no reporta a ESMA ni a FCA) queda como
  **frontera documentada**: alta manual o ADR US, y si algún día pesa, un tercer
  seed con los listados propios de SIX.

## Consecuencias

- Migración nueva: `listing_directory` + extensión `pg_trgm` (búsqueda por
  nombre con trigramas). Primera extensión de Postgres que activa el proyecto
  aparte de pgvector (que ya venía en la imagen).
- `listing_key` gana el origen `ext:<MIC>:<ISIN>`; el alta `ext:` valida por
  cotización y cruza sufijo↔MIC con el mapa de `pricing/adapters/yfinance.py`
  antes de persistir — discrepancia = parada, jamás auto-alta.
- El aviso «ITX → Inditex» del buscador desaparece para lo cubierto por el
  directorio: Inditex sale de verdad. Se conserva para lo no cubierto (Nestlé).
- Los ficheros FULINS se parsean en streaming (`lxml.iterparse`): son cientos
  de MB de XML y cargarlos enteros está prohibido en el seed.
- Sin cron: el directorio envejece con gracia y la UI declara la fecha del
  último seed. Una IPO posterior cae en el alta manual hasta el refresh.
