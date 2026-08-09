# PHASE-44.8 E5 — Directorio oficial de valores UE/UK (FIRDS) + alta validada

**Estado**: ✅ **IMPLEMENTADO como PHASE-44.14** (2026-08-07) — as-built en
[`phases/phase-44.14-eu-uk-listing-directory.md`](../phases/phase-44.14-eu-uk-listing-directory.md),
ADR en [`decisions/0010`](../decisions/0010-identity-official-registers.md).
Este documento se conserva como el plan que fue.

> **Tres desviaciones, todas por datos verificados y documentadas en el
> as-built**: (1) FIRDS reporta en MICs de **segmento**, no operativos, así que
> `MICS_SEED` se sustituyó por un mapa curado segmento→operativo contra ISO
> 10383 — con la lista literal del §2.4, Alemania entera quedaba fuera; (2) los
> tablones alemanes (Frankfurt, Stuttgart…) se excluyen aunque el mapa de
> sufijos los conozca, porque cotizan el mundo entero por cruce; (3) el fichero
> de la FCA trae venues europeos, así que la partición es **jurisdiccional** y
> no por fichero. El §2.6 «sin cron» y el §5 «Suiza fuera» se cumplen tal cual.

**Criterio del usuario**: **cero deuda futura**; tiempo y coste de cómputo no
son restricción.
**Encaje**: Entrega 5 del buscador (la que `pricing/adapters/base.py` anuncia
en comentario). Ajustar numeración al índice real del repo.
**ADR asociado (escribir primero)**: *Identidad sobre registros oficiales;
precios sobre capas tolerantes.* Identidad = EDGAR (US, ya sembrado en E2) +
**ESMA FIRDS** (UE) + **FCA FIRDS** (UK), locales tras seed. Precios =
yfinance tras selector (ya implementado, staleness-tolerant). Ninguna
dependencia no oficial en la capa de identidad. Toda dependencia de red en el
alta tiene bypass manual. **Twelve Data: descartada definitivamente**
(licencia no-comercial + prohibición de cacheo = hipoteca). **yfinance-Search
como directorio: descartado** (no oficial en la capa que no tolera rotura).

---

## 0. Por qué esto no genera deuda

- Los identificadores son los **registrales** (ISIN, MIC, LEI) — los mismos
  que usan tu bróker y tu información fiscal. No hay convención propietaria
  de ningún proveedor en el catálogo.
- El refresh del directorio es **actualización de datos** (re-ejecutar un
  comando), no cambio de arquitectura.
- Si Yahoo muere, el directorio ni se entera: la resolución ISIN→símbolo del
  alta degrada a completar ticker a mano, y los precios tienen su escalera
  de fallback ya documentada (EODHD).
- Ampliar cobertura futura = datos, no código: ETFs es una constante de
  filtro; otro país es otro seed. Nada de lo existente se toca.

## 1. Tabla `listing_directory` (global, sin user_id — extiende el ADR de tablas globales)

```sql
CREATE TABLE listing_directory (
  isin CHAR(12) NOT NULL,
  mic CHAR(4) NOT NULL,                -- venue oficial (XMAD, XLON, XETR...)
  name TEXT NOT NULL,                  -- FullNm del registro
  short_name TEXT,
  currency CHAR(3) NOT NULL,           -- NtnlCcy
  cfi CHAR(6) NOT NULL,
  lei CHAR(20),
  first_trade_date DATE,
  termination_date DATE,               -- NULL = activo
  source VARCHAR(8) NOT NULL,          -- 'ESMA' | 'FCA'
  seeded_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (isin, mic)
);
CREATE INDEX ix_listdir_name ON listing_directory
  USING gin (name gin_trgm_ops);       -- búsqueda por nombre (pg_trgm)
CREATE INDEX ix_listdir_isin ON listing_directory (isin);
```

## 2. Seed: `scripts/seed_listing_directory.py` (comando idempotente)

1. **Listado de ficheros** por interfaz máquina-a-máquina:
   - ESMA: API Solr de registros (`registers.esma.europa.eu/solr/
     esma_registers_firds_files/select` con filtro por fecha de publicación y
     tipo FULINS) → URLs de los ZIP más recientes. Los full files se publican
     **semanalmente (sábados)**; nos basta el último set.
   - FCA: API equivalente (`api.data.fca.org.uk/fca_data_firds_files`) para
     XLON. *(Punto de parada b: verificar forma exacta del endpoint al
     implementar.)*
2. **Descarga** de los FULINS de equity (particionados por tamaño — iterar
   todas las partes).
3. **Parseo streaming** (lxml `iterparse`, liberar elementos): los ficheros
   son grandes; prohibido cargarlos enteros en memoria. Payload ISO 20022:
   por registro → ISIN (`FinInstrmGnlAttrbts/Id`), nombre (`FullNm`),
   `ShrtNm`, CFI (`ClssfctnTp`), divisa (`NtnlCcy`), MIC
   (`TradgVnRltdAttrbts/Id`), LEI del emisor, fechas.
4. **Filtro**:
   - `cfi` empieza por `'ES'` (acciones ordinarias/preferentes). Constante
     `INCLUDE_CFI_PREFIXES = ('ES',)` — ampliar a ETFs algún día es tocar
     esta tupla, no el código.
   - `mic ∈ MICS_SEED` = exactamente los MICs del mapa de sufijos de pricing
     **menos los US** (US ya tiene identidad vía EDGAR; duplicarla sería
     doble fuente): `{XMAD, XLON, XETR, XPAR, XAMS, XBRU, XMIL, XLIS, XWBO,
     ...}`. Los MTF (Aquis/CBOE/Turquoise) quedan fuera por construcción →
     sin duplicados de presentación.
   - `termination_date` NULL o futura.
5. **Upsert** por (isin, mic) + stats de ejecución (leídas/filtradas/
   upsertadas) + `seeded_at`.
6. **Refresh**: re-ejecutar el comando (manual, trimestral o a demanda).
   **Sin cron** — local-first. El directorio envejece con gracia: una IPO
   posterior al seed cae en el alta manual hasta el siguiente refresh. La UI
   del buscador muestra "directorio actualizado el {max(seeded_at)}".

## 3. Búsqueda unificada (la Entrega 5 propiamente)

Local, sin red: EDGAR local (E2) para US ∪ `listing_directory` para UE/UK.
Query por nombre (trigram) e ISIN exacto. Resultado: nombre, ISIN, MIC,
divisa, fuente. El hint "ITX → Inditex" desaparece: Inditex sale de verdad.

## 4. Alta desde el directorio (flujo)

1. Usuario elige una fila → **identidad autoritativa de FIRDS** (isin, mic,
   name, currency). Nada de eso lo decide un proveedor de precios.
2. **Resolución de símbolo de pricing**: consulta de búsqueda de Yahoo por
   ISIN → símbolo (`IBE.MC`). *(Punto de parada a — spike de 1 h al arrancar
   la entrega: probar 5 ISINs — Inditex, Iberdrola, Allianz, LVMH, Unilever.
   Si la resolución por ISIN no es fiable, NO se fuerza: el formulario pide
   el ticker a mano, con todo lo demás pre-relleno. Degradación diseñada,
   no fallo.)*
3. **Cross-check**: sufijo del símbolo resuelto ↔ MIC elegido, vía el mapa
   existente de `yfinance.py`. Discrepancia → parada con mensaje, jamás
   auto-alta.
4. **Validación por cotización** (regla universal): `fast_info` del símbolo
   → existe + divisa del proveedor vs divisa FIRDS (discrepancia → quality
   flag, regla D4 vigente).
5. Persistir `Security`: ticker (símbolo sin sufijo), exchange = MIC,
   name/isin/currency de FIRDS, listing key `ext:` (implementarlo en
   `listing_key.py` — hoy solo entiende `cat:` y `typed:`),
   `analysis_available = false` (sin CIK).

## 5. Alta manual `ext:` — feature permanente, no fallback de segunda

Para todo lo fuera del universo sembrado, con la misma validación por
cotización del §4.4-5:
- **Suiza, explícitamente**: SIX no está en ESMA ni en FCA FIRDS (no es
  UE/EEA ni UK). Nestlé/Novartis/Roche → alta manual, o su ADR US vía
  EDGAR. Frontera documentada, no deuda. (Si algún día pesa, SIX publica
  listados propios → sería un tercer seed sin tocar nada.)
- OTC, listados nuevos pre-refresh, cualquier rareza.

## 6. Tests

| Qué | Cómo |
|---|---|
| Parser FULINS | Fixture XML recortado de un FULINS de equity real (~30 registros): campos extraídos, filtro CFI, filtro MIC, terminados fuera |
| Idempotencia del seed | Segundo run sobre mismo fixture → 0 cambios |
| Búsqueda | Nombre parcial (trigram) e ISIN exacto; US y EU mezclados |
| Alta desde directorio | Resolución ISIN mockeada: feliz, discrepancia sufijo↔MIC → parada, divisa proveedor≠FIRDS → flag |
| Degradación | Resolución ISIN falla → formulario manual pre-relleno |
| Alta manual `ext:` | Con validación por cotización mockeada |
| Cero red en CI | Todo fixture/mock; verificación viva en smoke |

## 7. Puntos de parada obligatoria

(a) Spike ISIN→símbolo antes de comprometer el flujo §4.2. (b) Endpoint real
de la API de ficheros de la FCA. (c) Si el particionado/tamaño de los FULINS
complica el streaming, preguntar antes de cambiar de estrategia. (d) MIC de
la cartera real del usuario fuera de `MICS_SEED` → preguntar, no ampliar en
silencio.

## 8. Fuera de alcance

ETFs (constante preparada, decisión futura del usuario) · derivados/renta
fija (jamás) · Suiza como seed (documentada como frontera) · cron de
refresh · Twelve Data y cualquier directorio de proveedor comercial ·
usar la búsqueda de Yahoo como directorio.

## 9. Decisión — RESUELTA (usuario, 2026-08)

**ETFs: NO en el seed ahora.** Entrarán en el futuro, y cuando entren la
receta completa es datos + una barrera estructural, cero rediseño:

1. Añadir `'CE'` (ETFs, ISO 10962) a `INCLUDE_CFI_PREFIXES` y re-ejecutar
   el seed.
2. `ALTER TYPE security_type ADD VALUE 'ETF'` (aditivo).
3. El alta de un ETF lo deja **fuera del motor de acciones** — estructural
   por `security_type`, no por flag manual. Los ETFs se trazan desde el día
   uno (cartera, lotes, FIFO, precios, distribuciones); su análisis llegará
   como **flujo propio** cuando exista el selector por tipo
   (Acción/Fondo/ETF — ver DESIGN v2 §1, "familia de motores"). Lo
   permanente es el invariante: **ningún tipo entra en el motor de otro**.
   Beneish/Altman/Piotroski modelan empresas operativas; un ETF no lo es.
   Misma mecánica que `is_financial`: el informe explica el porqué, no
   calcula basura.

Nota de preparación gratuita: la Tab Cartera ya es ETF-ready por
construcción — `inv_lots`/FIFO/quotes/`inv_dividends_received` son
agnósticos al tipo, y fiscalmente la venta de un ETF sigue el mismo FIFO
de valores homogéneos que una acción (los ETFs no gozan del régimen de
traspasos de los fondos). Cero cambios en esa mitad.
