# ARCHITECTURE — Módulo Bitcoin (spec de implementación)

**Estado**: 🏗️ arquitectura de implementación
**Audiencia**: modelo implementador (Claude Code / Opus). Fuente de
verdad para implementar. Ante ambigüedad prevalece este documento;
ante hueco, **preguntar al usuario antes de improvisar**.
**Documento padre**: `DESIGN-bitcoin-module.md` (decisiones B1-B9,
marco fiscal verificado con fuentes, taxonomía de huérfanos). Este
documento NO redefine tratamiento fiscal — lo referencia.
**Convenciones**: las del monorepo Crisol (`CLAUDE.md`, patrón
`models/schemas/repository/service/router`, Alembic, Pydantic v2,
Decimal, pytest, phase docs).

---

## 0. Principios (no negociables)

1. **Motor fiscal puro**: FIFO, compensaciones, flags y cuota viven en
   funciones puras sin I/O, sin BD, sin reloj. La fecha de referencia
   y el set de eventos entran como parámetros. `BTC_ENGINE_VERSION`
   (semver) en `engine/version.py`; cualquier cambio de regla o
   redondeo lo incrementa.
2. **El módulo nunca decide un hecho imponible** (B6). Los huérfanos
   quedan `ORPHAN_UNRESOLVED` y el informe es provisional. El
   tratamiento conservador es acción explícita del usuario, auditada
   y reversible.
3. **Determinismo total**: mismo set de eventos → mismas allocations,
   mismo informe. Orden total definido (§4.2), redondeo definido
   (§4.3). Sin `random`, sin orden de inserción implícito.
4. **Decimal en todo el pipeline**. BTC a 8 decimales, EUR con
   precisión completa en motor y persistencia; redondeo a 2 solo en
   presentación.
5. **Huecos explícitos**: `eur_amount=None` cuando la fuente no lo
   trae; el motor lo resuelve vía `btc_daily_prices` o marca la
   métrica como no calculable con razón. Jamás 0 silencioso.
6. **Idempotencia de ingesta**: re-subir el mismo CSV es no-op
   (`dedup_hash` UNIQUE).
7. Router → service → repository/engine. Cero lógica en routers.

---

## 1. Estructura de paquetes

```
backend/app/lib/
  fifo.py                        # ★ COMPARTIDA con módulo inversión (B8).
                                 # Si inversión aún no la extrajo, se crea
                                 # aquí y inversión la consumirá.

backend/app/modules/bitcoin/
  __init__.py
  sources/                       # btc_sources + btc_own_addresses
    models.py schemas.py repository.py service.py router.py
  events/                        # event stream canónico
    models.py                    # BtcEvent, BtcImportBatch
    schemas.py repository.py service.py router.py
    canonical.py                 # CanonicalRow (formato interno de parser)
    dedup.py                     # cálculo de dedup_hash
  imports/
    presets/
      base.py                    # Protocol Preset: parse(file) -> list[CanonicalRow]
      generic.py                 # CSV canónico documentado (§5.2) — MVP
      kraken.py binance.py nexo.py revolut.py        # exchanges
      ledger.py trezor.py green.py                    # wallets (reconciliación)
    detector.py                  # autodetección de preset por cabeceras
    service.py router.py         # flujo preview → confirm
  matching/
    engine.py                    # emparejado txid / importe+ventana (§6)
    service.py
  orphans/
    service.py router.py         # cola, clasificación, conservador (B6)
  prices/
    models.py                    # BtcDailyPrice
    kraken_ohlc.py               # update diario REST (límite 720 — §7)
    backfill.py                  # parser XBTEUR_1440.csv (archivo OHLCVT)
    service.py router.py
  fiscal/
    engine/                      # ★ PURO
      version.py                 # BTC_ENGINE_VERSION = "1.0.0"
      types.py                   # EventSet, Lot, Disposal, Allocation,
                                 #   YearReport, Flag
      ordering.py                # orden total (§4.2)
      inventory.py               # derivación lotes/disposiciones desde eventos
      fifo_adapter.py            # mapping dominio ↔ lib/fifo.py
      network_fees.py            # mecánica conservadora (§4.4)
      anti_application.py        # ventana configurable (B9)
      compensation.py            # neteo + arrastre 4 ejercicios
      rcm.py                     # intereses (B2)
      quota.py                   # tramos base del ahorro (cota inferior)
      report.py                  # build_year_report (orquestación pura)
    models.py                    # BtcFiscalSnapshot, BtcFifoAllocation
    schemas.py repository.py service.py router.py
    renta_export.py              # CSV fila-por-transmisión (§8.1)
```

Frontend:

```
apps/web/app/(app)/bitcoin/
  page.tsx                       # navegador de ejercicios (vista principal)
  imports/page.tsx               # wizard subida → preview → confirmar
  orphans/page.tsx               # cola de resolución
apps/web/components/bitcoin/
  year-selector.tsx  events-table.tsx  fiscal-panel.tsx
  inventory-card.tsx orphan-queue.tsx  orphan-resolve-dialog.tsx
  import-wizard.tsx  import-preview.tsx
  conservative-confirm-dialog.tsx      # muestra consecuencia fiscal antes de aplicar
packages/types/src/models/bitcoin.ts
packages/types/src/dto/bitcoin.dto.ts
packages/services/src/api/endpoints/bitcoin.ts
packages/services/src/query/hooks/useBitcoin*.ts
```

Registro del módulo (`packages/types/src/registry/modules.ts`): la
entrada "Criptomonedas" existente pasa a `enabled` al cerrar la fase
de UI del MVP, renombrada "Bitcoin" (alcance real).

---

## 2. Esquema (DDL)

Todas las tablas **scoped por `user_id`** salvo `btc_daily_prices`
(dato objetivo global — extiende el ADR de tablas globales del módulo
de inversión; anotarlo en ese ADR, no crear uno nuevo).

```sql
CREATE TYPE btc_source_kind AS ENUM ('EXCHANGE','WALLET');
CREATE TYPE btc_event_type AS ENUM (
  'BUY','SELL','TRANSFER_IN','TRANSFER_OUT','NETWORK_FEE',
  'INTEREST_REWARD','MINING_REWARD','SPEND','GIFT_IN','GIFT_OUT','LOSS');
CREATE TYPE btc_match_status AS ENUM (
  'MATCHED','ORPHAN_UNRESOLVED','RESOLVED_MANUAL','CONSERVATIVE_APPLIED');
CREATE TYPE btc_eur_source AS ENUM ('CSV','DAILY_PRICE','MANUAL');

CREATE TABLE btc_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  name TEXT NOT NULL,
  kind btc_source_kind NOT NULL,
  preset VARCHAR(24) NOT NULL,          -- kraken|binance|nexo|revolut|
                                        -- hodlhodl_manual|ledger|trezor|green|generic
  counts_for_721 BOOLEAN NOT NULL DEFAULT FALSE,
      -- TRUE solo para EXCHANGE custodio extranjero (Kraken, Binance,
      -- Nexo). Hodl Hodl (no custodio) y wallets: FALSE.
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (user_id, name)
);

CREATE TABLE btc_own_addresses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  address TEXT NOT NULL,
  label TEXT, source_id UUID REFERENCES btc_sources(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (user_id, address)
);

CREATE TABLE btc_import_batches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  source_id UUID NOT NULL REFERENCES btc_sources(id),
  filename TEXT NOT NULL, preset_used VARCHAR(24) NOT NULL,
  status VARCHAR(12) NOT NULL,          -- previewed|confirmed|discarded
  stats JSONB NOT NULL DEFAULT '{}',    -- {rows, imported, deduped, orphans}
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE btc_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  source_id UUID NOT NULL REFERENCES btc_sources(id),
  import_batch_id UUID REFERENCES btc_import_batches(id),  -- NULL = manual
  event_type btc_event_type NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,     -- UTC. Año fiscal = fecha en
                                        -- Europe/Madrid (§4.1)
  btc_amount NUMERIC(20,8) NOT NULL CHECK (btc_amount > 0),
  eur_amount NUMERIC(16,4),             -- NULL si la fuente no lo trae
  eur_amount_source btc_eur_source,
  fee_btc NUMERIC(20,8) NOT NULL DEFAULT 0,
  fee_eur NUMERIC(16,4) NOT NULL DEFAULT 0,
  txid TEXT, address_from TEXT, address_to TEXT,
  match_event_id UUID REFERENCES btc_events(id),
  match_status btc_match_status NOT NULL DEFAULT 'ORPHAN_UNRESOLVED',
      -- BUY/SELL/rewards nacen MATCHED (no necesitan pareja);
      -- TRANSFER_* nacen ORPHAN_UNRESOLVED hasta emparejar/clasificar.
  classification_note TEXT, evidence_ref TEXT,
  dedup_hash VARCHAR(64) NOT NULL,
  raw_row JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE (user_id, dedup_hash)
);
CREATE INDEX ix_btc_events_user_time ON btc_events(user_id, occurred_at);
CREATE INDEX ix_btc_events_orphans ON btc_events(user_id)
  WHERE match_status = 'ORPHAN_UNRESOLVED';

CREATE TABLE btc_daily_prices (      -- GLOBAL, sin user_id
  date DATE PRIMARY KEY,
  close_eur NUMERIC(16,4) NOT NULL,
  source VARCHAR(24) NOT NULL        -- kraken_ohlcvt_csv | kraken_rest
);

CREATE TABLE btc_fifo_allocations (  -- regenerable; caché auditable
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  disposal_event_id UUID NOT NULL REFERENCES btc_events(id) ON DELETE CASCADE,
  lot_event_id UUID NOT NULL REFERENCES btc_events(id) ON DELETE CASCADE,
  quantity NUMERIC(20,8) NOT NULL,
  cost_basis_eur NUMERIC(16,4) NOT NULL,
  proceeds_eur NUMERIC(16,4) NOT NULL,
  gain_eur NUMERIC(16,4) NOT NULL,
  is_network_fee BOOLEAN NOT NULL DEFAULT FALSE,   -- §4.4
  anti_application_flag BOOLEAN NOT NULL DEFAULT FALSE,
  anti_application_trigger_event_id UUID REFERENCES btc_events(id),
  engine_version VARCHAR(16) NOT NULL,
  computed_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_btc_alloc_user ON btc_fifo_allocations(user_id, disposal_event_id);

CREATE TABLE btc_fiscal_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  fiscal_year INT NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL,
  engine_version VARCHAR(16) NOT NULL,
  is_provisional BOOLEAN NOT NULL,
  unresolved_count INT NOT NULL,
  superseded BOOLEAN NOT NULL DEFAULT FALSE,  -- §4.6 recompute policy
  data JSONB NOT NULL
);
```

---

## 3. Contrato de `lib/fifo.py` (compartida)

```python
@dataclass(frozen=True)
class FifoLot:
    ref: Any                    # id opaco del dominio llamante
    quantity: Decimal
    unit_cost: Decimal          # coste por unidad (fees de compra ya
                                # incorporadas por el llamante)

@dataclass(frozen=True)
class FifoDisposal:
    ref: Any
    quantity: Decimal
    proceeds_total: Decimal     # neto de fees de venta

@dataclass(frozen=True)
class FifoAllocation:
    disposal_ref: Any; lot_ref: Any
    quantity: Decimal; cost_basis: Decimal; proceeds: Decimal
    # gain = proceeds - cost_basis (lo calcula el llamante)

def match_fifo(
    lots: Sequence[FifoLot],            # en orden de adquisición
    disposals: Sequence[FifoDisposal],  # en orden de disposición
) -> list[FifoAllocation]:
    """Consume lotes en orden. Prorratea proceeds y cost por cantidad;
    el residuo de redondeo de cada disposal se asigna a su ÚLTIMA
    allocation para que Σ allocations == totales exactos (§4.3).
    Lanza InsufficientInventoryError(disposal_ref, shortfall) si una
    disposición excede el inventario disponible en ese punto."""
```

Sin conocimiento de dominios: ni "acciones" ni "BTC". Los dos módulos
la envuelven (`fifo_adapter.py` aquí; el equivalente en inversión).
**Tests de la lib viven junto a la lib**, no duplicados por módulo.

---

## 4. Motor fiscal — reglas operativas exactas

Estas reglas cierran los huecos que el DESIGN deja al implementador.
No improvisar fuera de ellas.

### 4.1. Año fiscal y zona horaria
`fiscal_year(event) = (occurred_at convertido a Europe/Madrid).year`.
Un SELL a las 23:30 UTC del 31/12 es 00:30 del 01/01 en Madrid → año
siguiente. Los CSV de exchanges suelen venir en UTC; los presets
normalizan a UTC y la conversión a Madrid ocurre SOLO en el motor.

### 4.2. Orden total de eventos
Clave de ordenación: `(occurred_at, type_priority, dedup_hash)` donde
`type_priority`: adquisiciones (BUY, TRANSFER_IN, INTEREST_REWARD,
MINING_REWARD, GIFT_IN) = 0; disposiciones (SELL, SPEND, GIFT_OUT,
LOSS, NETWORK_FEE, TRANSFER_OUT) = 1. Con timestamp idéntico, la
compra precede a la venta (evita inventario negativo espurio en
operaciones del mismo segundo). `dedup_hash` como desempate
determinista final.

### 4.3. Redondeo y prorrateo
Motor en Decimal exacto. Prorrateo de coste por cantidad
(`cost = lot.unit_cost * qty`); el residuo de cada disposición se
asigna a su última allocation (invariante: la suma de allocations de
una disposición reproduce exactamente proceeds y coste consumido).
EUR a 2 decimales SOLO en presentación/export; persistencia a 4.
Test de propiedad obligatorio: `Σ gain_eur(allocations del año) ==
neto del informe` sin deriva de céntimos.

### 4.4. Mecánica de NETWORK_FEE (conservador, B1)
La fee en BTC consume inventario FIFO con `proceeds := cost_basis`
(gain = 0) y `is_network_fee = TRUE`. Consecuencias deliberadas:
el coste consumido desaparece del inventario (las ventas futuras
tendrán MÁS ganancia → tratamiento contra el contribuyente =
conservador correcto); la allocation NO aparece en la lista
fila-por-transmisión de Renta; SÍ suma al total anual de fees visible.
**No** implementar la variante "reducir cantidad sin consumir coste"
(equivaldría a deducir la fee de facto — contradice B1).

### 4.5. Semántica de transferencias emparejadas
TRANSFER_OUT/IN con `match_status=MATCHED` **no generan lotes ni
disposiciones**: el pool es global (V0975-22). Solo mueven saldo
por-fuente para reconciliación. Su `fee_btc` genera un evento
NETWORK_FEE sintético (mismo batch) con la mecánica §4.4.

### 4.6. Política de recomputación
Las allocations son caché derivada determinista del event set. Cualquier
mutación de eventos (insert por import confirmado, reclasificación,
resolución de huérfano, conservador aplicado/revertido, delete) →
`DELETE` de allocations del usuario → recomputación lazy en la
siguiente lectura fiscal/inventario. Los snapshots NO se recalculan:
si una mutación afecta a un año con snapshot, el snapshot se marca
`superseded=TRUE` (se conserva como foto histórica). La UI lo señala.

### 4.7. Inventario insuficiente
`InsufficientInventoryError` → el informe del año queda provisional
con error bloqueante específico ("venta de X BTC el d/m/a excede el
inventario en Y BTC — probable fuente sin importar o entrada sin
clasificar") y enlace a la cola de huérfanos. No se calcula un
informe parcial silencioso.

### 4.8. Anti-aplicación (B9)
Se evalúa **por disposición** (no por allocation): si
`gain_neto(disposal) < 0`, buscar adquisiciones tipo BUY (no
TRANSFER_IN; rewards excluidos — no son "recompra" en sentido propio,
anotar la duda en el informe si coinciden en ventana) en
`[fecha − W, fecha + W]`, `W = BTC_ANTI_APPLICATION_DAYS` (365
default, 61 alternativa). Flag + trigger event. NUNCA se descuenta
del neto: se lista aparte con ambos netos ("neto computando todo /
neto excluyendo pérdidas marcadas") para que el asesor elija.

### 4.9. Intereses (B2)
`INTEREST_REWARD`: (1) RCM del ejercicio = `eur_amount` (del CSV de
Nexo si lo trae; si no, `DAILY_PRICE` a fecha de recepción); (2) lote
con `unit_cost = eur_amount / btc_amount`. Ambos hechos del mismo
evento — sin evento duplicado.

### 4.10. Cuota estimada (B4.b)
Tramos sobre `max(0, neto_GyP_computable) + RCM`: 19% ≤6.000 · 21%
≤50.000 · 23% ≤200.000 · 27% ≤300.000 · 30% resto. Constantes
nombradas con vigencia anotada (revisar por ejercicio — los tramos
cambian por ley). Etiqueta fija de cota inferior (DESIGN B4).

---

## 5. Ingesta

### 5.1. Contrato de preset

```python
class CanonicalRow(TypedDict):
    occurred_at_utc: datetime
    event_type: BtcEventType
    btc_amount: Decimal          # > 0 siempre; semántica por type
    eur_amount: Decimal | None
    fee_btc: Decimal; fee_eur: Decimal
    txid: str | None; address_from: str | None; address_to: str | None
    ref: str | None              # id de fila del exchange si existe

class Preset(Protocol):
    name: str
    def sniff(self, headers: list[str]) -> bool: ...   # autodetección
    def parse(self, file: BinaryIO) -> list[CanonicalRow]: ...
```

`dedup_hash = sha256(source_id, occurred_at_utc, event_type,
btc_amount, txid or eur_amount or ref)`.

**Regla dura**: una fila del CSV que no mapee limpio a la taxonomía
(tipo desconocido, swap BTC↔altcoin, columna ambigua) NO se adivina:
el preview la lista en "filas no reconocidas" con la fila cruda y el
import puede confirmarse sin ellas. Swaps cripto-cripto → rechazo con
el aviso del DESIGN §1.

### 5.2. CSV canónico (preset `generic` — MVP y Hodl Hodl)
UTF-8, coma, cabecera obligatoria, una fila por evento:
```
datetime_utc,type,btc_amount,eur_amount,fee_btc,fee_eur,txid,address_from,address_to,ref
2024-03-10T14:22:00Z,BUY,0.05000000,3050.00,0,12.50,,,,"hodlhodl #4812"
```
`type` ∈ taxonomía. Documentar en la UI del wizard con ejemplo
descargable.

### 5.3. Presets de exchange — punto de parada obligatorio
Los formatos de export cambian sin aviso. **Cada preset (kraken,
binance, nexo, revolut, ledger, trezor, green) se implementa contra un
CSV real del usuario, que debe aportarlo antes de esa sub-fase.** Sin
muestra real → el preset no se implementa; `generic` es el fallback
universal. El preset de Nexo debe mapear sus filas de interés a
`INTEREST_REWARD` (B2 activo en MVP). Fixture anonimizado de cada CSV
real en `backend/tests/fixtures/bitcoin/` para regresión.

---

## 6. Matching (transferencias entre fuentes propias)

Sobre eventos `TRANSFER_OUT`/`TRANSFER_IN` (y retiradas/depósitos de
exchange que los presets emiten como tales):

1. **Por txid**: igualdad exacta out.txid == in.txid → MATCHED.
2. **Por dirección propia**: `address_to ∈ btc_own_addresses` →
   TRANSFER_OUT auto-clasificado (aunque la pata IN no exista aún).
3. **Fallback importe+ventana**: candidato si
   `in.btc_amount ∈ [out.btc_amount − out.fee_btc − ε, out.btc_amount]`
   y `|Δt| ≤ BTC_MATCH_WINDOW_HOURS` (24 default),
   `ε = BTC_MATCH_TOLERANCE_BTC` (0.00001000 default). Un solo
   candidato → MATCHED; varios → cola de preview con los candidatos
   ordenados por |Δt|.
4. Resto → ORPHAN_UNRESOLVED → cola (taxonomía DESIGN §6).

El matching corre en el preview del import y bajo demanda
(`POST /bitcoin/matching/run`) tras altas manuales o de direcciones.

---

## 7. Precios históricos (B7) — con la limitación verificada

**Trampa documentada**: el endpoint REST OHLC de Kraken devuelve como
máximo las 720 entradas más recientes; los datos más antiguos no son
recuperables aunque se use `since`. Con `interval=1440` (diario) son
~2 años. Por tanto:

- **Backfill**: Kraken publica archivos CSV descargables con el OHLCVT
  completo de cada par desde el inicio del mercado, con incrementos
  trimestrales. El usuario descarga el ZIP y sube el
  `XBTEUR_1440.csv` vía `POST /bitcoin/prices/backfill` (formato:
  `timestamp,open,high,low,close,volume,trades`; se toma `close` por
  fila → `date` en Europe/Madrid del timestamp de apertura de vela).
  Operación única + refresco trimestral opcional.
- **Update diario**: `GET https://api.kraken.com/0/public/OHLC?pair=XBTEUR&interval=1440`
  — la clave del resultado usa nomenclatura interna (tipo `XXBTZEUR`);
  resolver la clave dinámicamente, no hardcodear. Sin API key.
  Refresh on-access con TTL 24 h + endpoint manual.
- **Fecha sin vela** (sin trades ese día — raro en XBTEUR diario):
  usar el `close` anterior más próximo y marcar
  `eur_amount_source=DAILY_PRICE` con nota "precio del día D-n".
- Si un evento necesita FMV y no hay precio para su fecha ni backfill
  cargado → evento en estado "pendiente de valoración", informe
  provisional, aviso con enlace al backfill. Jamás inventar precio.

---

## 8. API

Prefijo `/bitcoin`. Todo scoped por usuario salvo lecturas de
`btc_daily_prices`.

```
# fuentes y direcciones
POST/GET/DELETE /bitcoin/sources
POST/GET/DELETE /bitcoin/own-addresses          (POST acepta bulk)

# ingesta (dos pasos, patrón imports de Crisol)
POST /bitcoin/imports/preview     multipart{file, source_id, preset?}
     → { batch_id, rows_parsed, deduped, matched, auto_classified,
         orphans[], unrecognized_rows[] }
POST /bitcoin/imports/{batch_id}/confirm
POST /bitcoin/imports/{batch_id}/discard

# eventos
GET  /bitcoin/events?year=&type=&source_id=&status=
POST /bitcoin/events                             (alta manual, generic)
PATCH /bitcoin/events/{id}                       (reclasificar; dispara §4.6)
DELETE /bitcoin/events/{id}

# huérfanos
GET  /bitcoin/orphans
POST /bitcoin/orphans/{id}/resolve   {classification, eur_amount?,
                                      evidence_ref?, own_address?}
POST /bitcoin/orphans/apply-conservative  {event_ids | "all"}
POST /bitcoin/orphans/{id}/revert-conservative
POST /bitcoin/matching/run

# fiscal
GET  /bitcoin/fiscal/{year}
     → YearReport: net_gain, per_operation[] (fila-por-transmisión),
       anti_application[] (con neto dual §4.8), carryforward[]
       (origen, restante, caducidad), rcm_interest, balance_dec31
       {btc, eur, price_date, over_721_threshold}, quota_estimate
       {amount, disclaimer}, is_provisional, blocking_errors[]
POST /bitcoin/fiscal/{year}/snapshot
GET  /bitcoin/fiscal/{year}/export?format=renta_csv
GET  /bitcoin/inventory
     → { total_btc, by_source[], avg_cost_live, avg_cost_historical,
         network_fees_ytd_btc }        # dos medias etiquetadas (DESIGN §7)

# precios
GET  /bitcoin/prices/status              (rango cubierto, huecos)
POST /bitcoin/prices/backfill            multipart{file XBTEUR_1440.csv}
POST /bitcoin/prices/refresh
```

Errores: HTTPException con `detail` en español accionable. 409 en
confirm si el batch ya fue confirmado; 422 con filas y motivo en
parse.

### 8.1. Export `renta_csv`
Una fila por transmisión (exigencia de Renta Web — introducir el
agregado es error): `fecha_transmision, btc_vendido, valor_transmision_eur,
valor_adquisicion_eur, ganancia_perdida_eur, flag_antiaplicacion,
fechas_lotes_consumidos`. Excluye allocations `is_network_fee` y
disposiciones no imponibles. Cabecera con disclaimer y
`engine_version`.

---

## 9. Frontend (contratos)

- **`/bitcoin` (vista principal)**: selector de año → `events-table`
  del ejercicio (compras/ventas; transferencias propias atenuadas con
  toggle) + `fiscal-panel` (todo el YearReport §8, badge PROVISIONAL
  enlazando a orphans, snapshot superseded señalizado) +
  `inventory-card` (dos medias etiquetadas, fees anuales).
- **Wizard import**: fuente → archivo → preview con cuatro secciones
  (emparejados / auto-clasificados / huérfanos / filas no
  reconocidas) → confirmar. Nada se persiste sin confirm.
- **Cola de huérfanos**: taxonomía por dirección (DESIGN §6), warning
  art. 39 con checklist de triple prueba en entradas,
  `conservative-confirm-dialog` que muestra la consecuencia fiscal
  exacta ("este lote entrará a coste 0 € → toda la venta futura será
  ganancia") antes de aplicar.
- Formato: tabular-nums; BTC 8 decimales; EUR es-ES; disclaimer fiscal
  persistente en el panel. Tokens del design system, sin librerías
  nuevas.

---

## 10. Testing

| Nivel | Qué | Cómo |
|---|---|---|
| `lib/fifo.py` | Prorrateo, residuo a última allocation, inventario insuficiente, determinismo | Unit puro; property test: Σ allocations == totales exactos |
| Motor fiscal golden | Escenario completo multi-año | Fixture sintético: compras 3 años, venta parcial cruzando lotes, transferencia emparejada con fee, interés Nexo, huérfano→conservador, pérdida con recompra en ventana, arrastre con caducidad. Golden = YearReport serializado por año. Cambio sin bump de `BTC_ENGINE_VERSION` → falla |
| Edge cases §4 | Cada regla operativa | Orden total con timestamps idénticos; 31/12 23:30 UTC → año siguiente (Madrid); NETWORK_FEE gain 0 y coste consumido; anti-aplicación en frontera de ventana y de año; reclasificación → recompute → snapshot superseded |
| Presets | Parse contra CSV real | Fixture anonimizado por preset; filas no reconocidas listadas, no adivinadas; Nexo mapea interés → INTEREST_REWARD |
| Matching | txid, dirección propia, importe+ventana, ambiguo | Unit sobre `matching/engine.py` |
| Precios | Backfill XBTEUR_1440 + hueco de vela | Fixture recortado del CSV real; fecha sin vela → close anterior con nota |
| API | Contratos + idempotencia | Re-subir mismo CSV → deduped=100%; confirm doble → 409; scoping user |

Sin red en tests: `kraken_ohlc.py` se testea con respuestas fixture;
smoke manual documentado en `scripts/kraken_prices_smoke.py`.

---

## 11. Configuración

| Variable | Uso | Default |
|---|---|---|
| `BTC_ANTI_APPLICATION_DAYS` | Ventana B9 | `365` |
| `BTC_MATCH_WINDOW_HOURS` | Fallback matching | `24` |
| `BTC_MATCH_TOLERANCE_BTC` | ε del matching | `0.00001000` |
| `BTC_PRICE_TTL_HOURS` | Refresh on-access del diario | `24` |
| `BTC_FISCAL_TZ` | Zona de imputación | `Europe/Madrid` |

Tramos de la cuota: constantes nombradas en `quota.py` con comentario
de vigencia (no env — cambian por ley, no por despliegue).

---

## 12. Secuencia de implementación (fases orientativas PHASE-50.x)

Ajustar numeración al índice real del repo. Cada fase con tests verdes
antes de avanzar; **no adelantar frontend antes de que el motor esté
golden-tested**.

| Fase | Contenido | Criterio de salida |
|---|---|---|
| 50.1 | Migraciones + enums + `lib/fifo.py` (o consumo si inversión ya la creó) + nota en ADR global-tables por `btc_daily_prices` | up/down reversibles; tests de la lib |
| 50.2 | `btc_daily_prices`: backfill OHLCVT + update REST + status | Fixture backfill; hueco de vela cubierto |
| 50.3 | Event stream + dedup + preset `generic` + alta manual + endpoints de eventos | Import idempotente end-to-end |
| 50.4 | Motor fiscal completo (§4) + allocations + YearReport + snapshots + export renta_csv | **Golden multi-año verde**; verificación manual del usuario contra un cálculo a mano de su histórico real |
| 50.5 | Matching + own_addresses + cola de huérfanos + conservador/revert | Edge tests §6 y §4.6 |
| 50.6 | Web: vista principal + wizard + cola + panel fiscal | Flujo manual completo con datos reales |
| 50.7 | Presets kraken, binance, **nexo (interés)**, revolut — **bloqueada hasta recibir CSV reales del usuario** | Fixtures reales; filas no reconocidas correctamente listadas |
| 50.8 | Wallets (ledger/trezor/green) como tier reconciliación + vista de saldos por fuente | Reconciliación cuadra con caso real |
| 50.9 | Registro del módulo `enabled` + (futuro) integración Dashboard | — |

**Puntos de parada obligatoria para el implementador**: (a) 50.7 no
arranca sin CSV reales de cada exchange — pedirlos, no inventar
formatos; (b) cualquier fila de CSV que no mapee a la taxonomía →
listar y preguntar, jamás crear tipos nuevos; (c) 50.4 requiere
validación manual del usuario (su histórico real contra el motor)
antes de dar el motor por bueno; (d) cualquier duda de tratamiento
fiscal fuera de lo escrito en DESIGN §3/§6 y aquí §4 → preguntar al
usuario/asesor, no interpretar la LIRPF por cuenta propia.

---

## 13. Anti-objetivos (no implementar)

- Otras criptomonedas, swaps cripto-cripto, DeFi, staking on-chain.
- Generación de modelos tributarios (100/721/714) — solo datos.
- Conexión API a exchanges (solo CSV) o a nodos Bitcoin.
- Precio intradía o histórico de cotización para charts.
- Cálculo automático del diferimiento de pérdidas por anti-aplicación
  (solo flag + neto dual).
- Cola externa / scheduler: todo on-access u on-demand, local-first.
- Cualquier tratamiento fiscal no documentado en DESIGN/aquí.
