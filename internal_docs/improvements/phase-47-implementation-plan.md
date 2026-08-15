# PHASE-47 — Plan de implementación

**Estado**: 📋 listo para ejecutar, con dos paradas de datos
**Jerarquía documental** (declarada por el anexo): respuestas > anexo > plan
original. Este documento **no reabre ninguna decisión**: recoge lo decidido,
**corrige lo que el anexo afirma sobre el código y no es cierto** (§1), cierra
con defaults las seis dudas que ni el anexo ni las respuestas tocan (§2), y lo
convierte en entregables ejecutables (§3-§5).

**Aviso**: el anexo cita `phase-47-respuestas.md` como
autoridad máxima sobre D1–D14. **Ese fichero no está en el repo** (lo confirma
`scripts/check_docs.py`, por eso aquí se nombra sin enlazar), y las líneas
`→ Respuesta:` de
[`phase-47-open-questions.md`](phase-47-open-questions.md) siguen vacías. Este
plan reconstruye las respuestas **desde el propio anexo**, que las implica casi
todas; donde no las implica, §2 pone un default marcado como tal. Si el fichero
de respuestas existe fuera del repo y contradice algo de §2, manda él.

**Documentos**: [plan original](phase-47-debt-recomposition-inbox.md) ·
[dudas](phase-47-open-questions.md) · [anexo](phase-47-anexo-implementacion.md).

---

## 1. Correcciones al anexo (verificadas contra `6e7a766`)

El anexo manda sobre el plan, así que un error suyo se implementa tal cual. Estos
seis son de hecho, no de criterio: el código dice otra cosa.

### 1.1 · La tabla se llama `import_jobs`, no `import_batches` (§F, §I)

[`imports/models.py`](../../backend/app/modules/personal_finance/imports/models.py#L38):
`__tablename__ = "import_jobs"`. Ya tiene `account_id`, `column_mappings` (JSON)
y `preview_payload` (JSON). La migración 4 del anexo apunta a una tabla
inexistente.

**Consecuencia útil**: los `column_mappings` de los jobs históricos **contienen
las columnas del fichero**, así que la huella de cabecera se puede *retro-rellenar*
para los imports que ya existen. Sin ese backfill, la señal F.1 nace ciega y no
detecta nada hasta que cada cuenta tenga un import posterior a 47.A — es decir,
no habría cazado julio. Va como **script auditado con `--dry-run`**, no dentro de
la migración ([PHASE-34]: una migración reproduce, no corrige).

### 1.2 · `transactions.resolution` no existe (§J)

La query del universo usa `t.resolution IS NULL` como «criterio de no resuelta
vigente». No hay tal columna
([`transactions/models.py`](../../backend/app/modules/personal_finance/transactions/models.py#L63)).
«Resuelta» hay que **definirla**, y es la decisión más cargada de toda la fase
porque gobierna a la vez la bandeja y la property de no-silencio. Definición
propuesta — una tx está resuelta si **cualquiera** de estas es cierta:

| Señal | Columna | Significa |
|---|---|---|
| Emparejada | `transfer_pair_id IS NOT NULL` | el dinero ya está contado por los dos lados |
| Amortización registrada | existe tx con `amortization_source_id = t.id` | PHASE-45 |
| Cuota marcada | `t.id ∈ liability_installments.paid_transaction_id` | PHASE-36 |
| Espejo absorbido | `t.absorbed_as_mirror = TRUE` | PHASE-34 |
| Descartada | `t.id ∈ debt_inbox_dismissals.transaction_ids` | PHASE-47 |

Se declara **una sola vez** como expresión SQL reutilizable
(`debt/inbox_repository.py::unresolved_filter`) — con una excepción deliberada,
ver §4.3.

### 1.3 · `accounts` no tiene `kind` (§J)

La query filtra `a.kind IN ('LIABILITY','CREDIT_CARD')`. `Account` tiene
[`nature`](../../backend/app/modules/personal_finance/accounts/models.py#L46)
(`asset` | `liability`, minúsculas) y `type` (`bank`, `savings`, …,
`credit_card`, `loan`, `mortgage`). Además `LIABILITY` y `CREDIT_CARD` no son
alternativas: toda `credit_card` **es** `nature='liability'`. El filtro correcto
es `a.nature = 'liability' OR a.id IN (SELECT settlement_account_id …)`.

### 1.4 · Las cuotas no tienen estado `PENDING` (§C)

[`LiabilityInstallment`](../../backend/app/modules/personal_finance/debt/installments_model.py#L37)
no tiene enum de estado: pendiente es `paid_at IS NULL`. Detalle que importa para
el detector #1: **el usuario puede editar el importe de una cuota** (PHASE-24.1),
así que el `payment` contra el que se compara puede no ser el del cuadro francés.
Es justo lo que la tolerancia de ±1 € existe para absorber, y por eso el riesgo
que el anexo lista en §L es real y está bien mitigado.

### 1.5 · El detector #2 con ventana de fecha **como filtro** regresa el caso vivo

§D exige que el plan candidato tenga «fecha de alta dentro de ±10 días del
abono». [`list_liabilities_awaiting_origination`](../../backend/app/modules/personal_finance/transfers/repository.py#L74)
no usa fecha alguna, y PHASE-46 lo razonó: *«el capital del cuadro sí, y además no
caduca cuando el banco cambia la redacción»*.

Hay ahora mismo una propuesta viva en la app —`06/07 · Operación financiada ·
700,26 €` ↔ `Compra finaciada recibo junio`, según [`HANDOFF.md`](../HANDOFF.md)—
cuyo pasivo lo creó el usuario **a mano y después**. Si su `start_date` (primera
cuota) cae fuera de ±10 días del abono, la ventana **mata la única propuesta que
hoy funciona**.

**Corrección**: la fecha es **corroboración, no filtro** — exactamente el trato
que el propio anexo da al texto en §C (*«puede AÑADIR confianza, nunca filtrar
candidatas»*). El importe contra el capital del cuadro sigue siendo el único
criterio de candidatura. Con ventana → `confidence: "structural"`; sin ella →
`"suggested"`. Regresión obligatoria: **el caso de las 700,26 € debe seguir
proponiéndose**, y se escribe como test antes de tocar el detector.

### 1.6 · El rastro `auto_applied` necesita una guarda para bastar con una columna

§B/§I ponen el rastro en `transactions.amortization_auto_applied`. Eso sólo
existe cuando la amortización **crea contrapartida**, que es el camino de un
pasivo **sin cuadro**; si el pasivo tiene cuadro, PHASE-45 marca cuotas y no
escribe ninguna tx nueva, así que no habría dónde poner el rastro.

No hace falta una segunda columna: el caso A es por definición un recibo de
tarjeta revolving cuyas compras están registradas — un pasivo **sin cuadro**. Se
cierra con una **guarda explícita**: *el caso A auto-actúa sólo si el pasivo
destino no tiene cuotas; si las tiene, va a bandeja*. Una línea, y mantiene
honesto el diseño de una sola columna. Va con test que lo afirma con su motivo
dentro ([PHASE-44.21]).

### 1.7 · Precisión sobre el guardarraíl del import (§F)

Las dos señales no son «1 y luego 2»: cubren casos distintos y **sólo la primera
habría cazado julio**.

| Señal | Caza | Julio |
|---|---|---|
| F.1 huella de cabecera | fichero con formato de otra cuenta | ✅ (mayo y junio ya tenían el formato de tarjeta) |
| F.2 solape de dedup | **re**-importar algo ya presente en otra cuenta | ❌ era la primera vez |

F.2 sale casi gratis y con un efecto secundario que conviene saber:
[`_compute_hash`](../../backend/app/modules/personal_finance/imports/service.py#L1541)
**no incluye `account_id`**, y el índice único es `(user_id, import_hash)`. O sea
que un fichero ya importado en la cuenta equivocada **bloquea** su reimportación
en la correcta — que es exactamente por qué hicieron falta
`undo_card_statement_into_bank.py` y `move_import_to_account.py`. F.2 convierte
ese choque en un aviso legible antes de que ocurra.

---

## 2. Las seis dudas que nadie cerró (defaults propuestos)

Marcadas como **default**: se ejecutan salvo objeción.

| # | Duda | Default |
|---|---|---|
| **D5** | Qué son los 4 ADEUDO de julio; qué mes sirve de caso verde | **Sigue abierta y es la única que bloquea.** Bloquea la parada 2 de 47.B (fixtures §K), no el arranque. 47.A no la necesita |
| **D7** | ¿Se mueve la página de detalle o nacen dos? | **Se mueve** `accounts/…/amortization` → `/debt/{account_id}` con redirect permanente. Dos páginas de detalle es el problema que la fase resuelve |
| **D10** | ¿ADR? | **Sí, ADR-0011**, dentro de 47.A: «la traducción movimiento→evento la inicia el sistema; la declaración sigue siendo del usuario», con el orden de la cascada dentro y su relación con [ADR-0003](../decisions/0003-debt-module-two-layer-architecture.md) y [ADR-0004](../decisions/0004-transaction-level-money-truth.md) |
| **D12** | Barrido de gráficos en móvil | **47.B oculta en web, 47.C borra en las dos apps.** Borrar en una y dejar en otra crea una divergencia documentada que se pudre |
| **D13** | Orden de rutas del router de deuda | **Rutas nombradas antes que paramétricas** + test que lo afirma. `accounts/router.py` ya depende de ese orden |
| **D14** | El plan de PHASE-48 no existe | **47 no depende de él.** El detector #4 emite un item «Revisar» con clasificación manual asistida y jamás auto-match; la cola a PHASE-48 se cablea cuando 48 exista |

---

## 3. Entregables

### 47.A — Cimientos (sin comportamiento nuevo salvo el guardarraíl)

No necesita ningún dato del usuario. Se puede empezar hoy.

#### A1 · Consolidación del dominio deuda (plan §47.0, anexo §G)

`git mv` de seis módulos, conservando `__tablename__` (cero migraciones):

```
accounts/debt_health.py             → debt/health.py
accounts/debt_history.py            → debt/history.py
accounts/debt_reconciliation.py     → debt/reconciliation.py
accounts/amortization.py            → debt/amortization.py
accounts/installments_model.py      → debt/installments_model.py
accounts/installments_repository.py → debt/installments_repository.py
```

Schemas que se van a `debt/schemas.py` (verificados como usados sólo por esos
seis y sus routers): `DebtTypeSlice`, `DebtHealthKpis`, `AmortizationRowResponse`,
`InstallmentUpdateRequest`, `InstallmentPayRequest`, `InstallmentBulkPayRequest`,
`InstallmentBulkPayResponse`, `ReconcileActionResponse`,
`ReconcileLiabilityResponse`, `ReconcilePlanResponse`,
`AmortizationScheduleResponse`, `DebtHistoryPoint`, `DebtHistoryResponse`.
**Se quedan** en `accounts/schemas.py`: `Account*`, `ReconcileBalanceRequest`
(es el cuadre de saldo, no de deuda) y los `Position*`.

**Invariante de capas, con test**: `debt/*` puede importar
`accounts.{models,repository,schemas}` (hojas) y **nunca** `accounts.service`;
`accounts.service` sí importa `debt.installments_repository`. Un test que
recorra los imports por AST y falle si aparece `accounts.service` dentro de
`debt/` — sin él, el ciclo vuelve el día que alguien necesite un helper.

**URLs: cero cambios** (D6). Los endpoints siguen registrados en
`accounts/router.py`; sólo cambia de dónde importan. Además `alembic/env.py` y
`tests/conftest.py` importan los modelos explícitamente: al mover
`installments_model.py` hay que repuntar **las dos** listas.

**Verificación de no-cambio** (anexo §G.4): golden byte a byte de `debt-health`,
`get_balances` y `category-summary` con el seed de tests, pre y post; `pytest`
verde **sin tocar un solo assert**; `alembic check` sin drift y sin migraciones
nuevas.

#### A2 · Atribución cargo→tarjeta (D4)

Migración aditiva:

```sql
ALTER TABLE accounts ADD COLUMN settlement_account_id UUID NULL
  REFERENCES accounts(id) ON DELETE SET NULL;
```

Validación en `create_account`/`update_account`: la cuenta apuntada debe ser
`nature='asset'` del mismo usuario y distinta de sí misma; sólo tiene sentido en
`nature='liability'`. Sin backfill.

**Propuesta, no adivinanza** (flujo (c) de D4): el servidor deriva un candidato
de los enlaces PHASE-45 que ya existan —si las contrapartidas de un pasivo
apuntan a cargos de la cuenta X, propone X— y lo ofrece precargado en el
formulario. El usuario adjudica.

FE: campo nuevo en el formulario de cuenta (web y móvil), visible sólo para
pasivos.

#### A3 · Guardarraíl del import (D9, anexo §F)

Migración aditiva: `ALTER TABLE import_jobs ADD COLUMN header_fingerprint VARCHAR(64) NULL;`

- **Huella** = sha256 de la lista ordenada y normalizada (trim + casefold) de las
  columnas del fichero. Se calcula en el preview y se persiste al confirmar.
- **Backfill** en `backend/scripts/backfill_header_fingerprint.py` con
  `--dry-run` y `--apply`, derivándola de `column_mappings` /
  `preview_payload.effective_mappings` de los jobs históricos. Sin él, F.1 nace
  ciega. Ejecutar el `--apply` contra una copia primero ([PHASE-44.13]: el
  dry-run prueba la consulta, no la escritura).
- **F.1**: la huella del fichero coincide con la histórica de OTRA cuenta y no
  con la elegida → aviso.
- **F.2**: recalcular los hashes de las filas del preview y contar cuántos
  existen ya en transacciones de OTRA cuenta; solape > `IMPORT_CROSS_OVERLAP_PCT`
  → aviso, nombrando la cuenta y el número de filas.
- Los dos son **bloqueables, no prohibiciones**: la respuesta del preview lleva
  `warnings[]`, y el confirm exige `acknowledged_warnings[]` con las claves o
  devuelve **409**.

**Parada A** (anexo §F): antes de dar A3 por bueno, comprobar con los CSV/PDF
reales de BBVA que la huella **discrimina** banco de tarjeta. Si los dos ficheros
tienen la misma cabecera, F.1 no sirve y hay que **preguntar** antes de inventar
heurísticas.

#### A4 · ADR-0011 (D10)

#### Commits de 47.A

```
refactor(debt): consolidate debt domain under debt/ (no behavior change) — Refs: PHASE-47.A
feat(accounts): declare which asset account settles a liability — Refs: PHASE-47.A
feat(imports): warn when a file looks like it belongs to another account — Refs: PHASE-47.A
docs(adr): 0011 system-initiated debt event translation — Refs: PHASE-47.A
```

---

### 47.B — La bandeja

Depende de A2 (sin `settlement_account_id` no hay ciclo ni caso A) y, para
cerrar, de **D5**.

#### B1 · Motor puro `debt/classification.py`

**Puro**: sin BD, sin red, sin reloj — `today` entra por parámetro. Test de
pureza por AST, copiando el que ya protege el engine de inversión.

```python
class InboxKind(StrEnum):
    QUOTA_MATCH = "QUOTA_MATCH"            # detector 1
    FINANCING_BIRTH = "FINANCING_BIRTH"    # detector 2
    CYCLE_CLOSE = "CYCLE_CLOSE"            # detector 3 (único auto)
    POSSIBLE_SETTLEMENT = "POSSIBLE_SETTLEMENT"  # detector 4
    CYCLE_GAP = "CYCLE_GAP"                # detector 5
    UNCLASSIFIED = "UNCLASSIFIED"          # detector 6
```

Cascada en el orden del plan §47.1.a — **primer match gana**, y el orden es
contrato (punto de parada (c)). Specs: anexo §C (con la corrección 1.4), §D (con
la corrección **1.5**: la fecha corrobora, no filtra), §E, y guard
`SETTLEMENT_GUARD_K` para el #4.

Regla transversal ya decidida (D3, anexo §C): **el texto puede subir la confianza
de una propuesta; nunca puede seleccionar ni descartar candidatas.** Un test por
detector que lo afirme, alimentando la misma transacción con dos redacciones
distintas y exigiendo el mismo item.

Item y errores según anexo §H. `confidence` ∈ `arithmetic | structural |
suggested`, con la semántica que ya usa el resto del proyecto: *arithmetic* = lo
demuestra una suma (el invariante cierra); *structural* = lo demuestra una
relación modelada (capital del cuadro, cuota concreta); *suggested* = el motor de
PHASE-45 propone y el usuario adjudica.

#### B2 · Universo, resolución y persistencia

- `debt/inbox_repository.py::unresolved_filter` con las cinco señales de §1.2.
- Universo de candidatas (§1.3): transacciones activas del periodo cuya cuenta
  sea `nature='liability'` **o** sea `settlement_account_id` de algún pasivo.
  **Los dos signos** — el detector #2 necesita un abono (D3).
- Migraciones aditivas:

```sql
CREATE TABLE debt_inbox_dismissals (
  id UUID PRIMARY KEY,                       -- default=uuid4 en Python, como el resto
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  item_id VARCHAR(16) NOT NULL,
  transaction_ids UUID[] NOT NULL,
  kind VARCHAR(24) NOT NULL,
  reason TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (user_id, item_id)
);
ALTER TABLE transactions ADD COLUMN amortization_auto_applied BOOLEAN NULL;
```

`NULL` = acción pre-47, origen desconocido: la sección «Resuelto
automáticamente» pinta **sólo `TRUE`** (anexo §B). La FK a `users` y el UUID
generado en Python son la convención del repo, no lo del DDL del anexo.

#### B3 · API

```
GET    /debt/inbox                      ?date_from&date_to
POST   /debt/inbox/{item_id}/accept
POST   /debt/inbox/{item_id}/resolve
POST   /debt/inbox/{item_id}/dismiss    {reason}
POST   /debt/inbox/{item_id}/undo
DELETE /debt/inbox/{item_id}/dismiss    (undismiss, §B)
GET    /debt/{account_id}/detail
```

Flujo de `accept`/`resolve` **exactamente** el del anexo §A: recalcular sólo el
set de la tx, comparar `id` + `proposal_hash`, y 404 / 409 / 422 según su tabla.
Nada de caché de items en servidor. Rutas nombradas declaradas **antes** que
`/{account_id}` (D13) con test.

Invalidación: toda mutación de la bandeja invalida `queryKeys.debt.all` y
`queryKeys.accounts.all` (el saldo cambia). Ya existe esa raíz única.

#### B4 · Web

- **Bandeja** como primera sección de `/debt`, con contador, estado vacío
  explícito y la sección colapsada «Resuelto automáticamente este periodo».
  Items tipo-asistente muestran **«Gestionar plan →»**, no «Deshacer» (anexo §B).
- **Detalle por deuda**: se **mueve** la página de amortización por cuenta a
  `/debt/{account_id}` con redirect (D7), y se le añaden movimientos de esa
  deuda, pendientes de esa deuda y el invariante del ciclo si es tarjeta.
- `/debt` adelgaza: lista de una línea por deuda + un gráfico. Los charts que
  salen (`debt-daily-evolution`, `debt-trend-chart`, donut) se **dejan de
  renderizar**; los ficheros se borran en 47.C (D12).

#### B5 · Fixtures y parada 2

Las dos fixtures reales de §K **no se inventan** (es el error de H4). 47.B queda
parado hasta tener de D5: qué mes sirve de caso verde y qué son los cuatro
cargos. En esa parada se calibran `DEBT_QUOTA_MATCH_TOLERANCE_EUR`,
`DEBT_QUOTA_DATE_WINDOW_DAYS` y `DEBT_CYCLE_TOLERANCE_EUR` contra los datos
reales — y **sólo ahí** (anexo §L, regla anti-tuning).

---

### 47.C — Unificación y barrido

Sólo cuando 47.B lleve un mes real demostrando que cubre los casos (punto de
parada (d) del plan).

- **Flujo único «Cruzar con deuda»** con las tres decisiones pre-resueltas y su
  porqué expandible. Entradas: bandeja, transacción, detalle de deuda.
- **Retirada de los seis diálogos** con checklist por diálogo: cada uno se
  retira sólo tras marcar que sus casos están cubiertos. Los seis:
  `amortization-panel`, `convert-to-debt-dialog`, `financing-matches-section`,
  `installment-pay-buttons`, `installment-edit-dialog`, `debt-payment-wizard`.
- **Paridad móvil**: ver bandeja + aceptar + deshacer (el asistente puede quedar
  web-only, marcado en el phase doc).
- **Barrido**: borrar los charts en **las dos apps** (D12), retirar el shim de
  schemas de A1, y re-ejecutar `pnpm knip` en vez de asumir la lista
  ([PHASE-43]: un hallazgo es una hipótesis).

---

## 4. Tests

### 4.1 Regresiones que se escriben ANTES de tocar nada

| Test | Afirma |
|---|---|
| `test_financing_match_700_26_sigue_proponiendose` | La corrección 1.5: el caso vivo sobrevive al detector #2 |
| Golden 47.0 | `debt-health` / `get_balances` / `category-summary` idénticos pre/post movimiento |

### 4.2 Por entregable

- **A1**: golden + test de capas por AST (`debt/` no importa `accounts.service`).
- **A2**: `settlement_account_id` rechaza self-reference, cuenta de otro usuario
  y cuenta `liability`; la propuesta derivada de enlaces PHASE-45 acierta.
- **A3**: F.1 avisa con formato de otra cuenta y **no** avisa con el propio; F.2
  cuenta el solape correctamente; el confirm sin `acknowledged_warnings` da 409.
  **Y el caso al otro lado del umbral** ([PHASE-44.14]): un solape del 19 % no
  avisa, uno del 21 % sí.
- **B1**: un test por detector con **dos redacciones distintas del mismo hecho**
  → mismo item (la regla del texto). Ambigüedad ≥2 candidatas → item con lista,
  nunca elección silenciosa. Guard #4: cargo 4× cuota → «Revisar», jamás
  auto-match. Caso A con pasivo **que sí tiene cuadro** → bandeja, no auto
  (corrección 1.6).
- **B3**: `accept` dos veces → 404 la segunda; propuesta cambiada → 409 con
  `current`; `resolve` con variante no ofrecida → 422.

### 4.3 La property de no-silencio, y por qué se duplica a propósito

El universo se construye **con su propia query escrita en el test**, no llamando
al clasificador ni al helper `unresolved_filter` — si el test pregunta a la misma
función que la bandeja, sólo demuestra que la función es consistente consigo
misma (D3). Es una duplicación **deliberada**, y va con su motivo escrito dentro
del test para que nadie la «deduplique» en seis meses.

Assert: cada id del universo ∈ (items ∪ acciones con rastro del periodo ∪
dismissals).

**Y una comprobación de que el gate no está ciego**: el test se valida
rompiéndolo — apagar un detector debe hacerlo fallar. Un property test que pasa
con la cascada desactivada no prueba nada ([PHASE-44.14]).

### 4.4 Todos los tests nuevos se verifican **rompiendo el código**

Es la práctica de PHASE-45 y PHASE-46, y en esta fase importa más que nunca: la
mitad de los detectores devuelven «nada» cuando fallan, que es el modo de fallo
que se lee como éxito.

---

## 5. Config

| Variable | Default | Se calibra |
|---|---|---|
| `DEBT_QUOTA_MATCH_TOLERANCE_EUR` | `1.00` | Parada 2 |
| `DEBT_QUOTA_DATE_WINDOW_DAYS` | `7` | Parada 2 |
| `DEBT_CYCLE_TOLERANCE_EUR` | `2.00` | Parada 2 |
| `DEBT_FINANCING_BIRTH_WINDOW_DAYS` | `10` | Sólo sube confianza (1.5) |
| `DEBT_PAIR_WINDOW_DAYS` | `3` | Corroboración del #2 |
| `DEBT_SETTLEMENT_GUARD_K` | `1.8` | — |
| `IMPORT_CROSS_OVERLAP_PCT` | `20` | Parada A |

Todas en `app/core/config.py` con el patrón `Settings` existente.
`DEBT_PAIR_WINDOW_DAYS` **no sustituye** los ±31 días de `_MIRROR_WINDOW`: son
conjuntos disjuntos porque la bandeja sólo consume no-resueltas y el espejo marca
`absorbed_as_mirror` (D11, anexo §D). Merece un comentario en el código diciendo
justo eso, porque «dos ventanas para el mismo hecho» es el patrón que costó la
lección de PHASE-46.

---

## 6. Migraciones (4 aditivas, ninguna toca datos)

| # | Entregable | DDL |
|---|---|---|
| 1 | A2 | `accounts.settlement_account_id UUID NULL REFERENCES accounts(id) ON DELETE SET NULL` |
| 2 | A3 | `import_jobs.header_fingerprint VARCHAR(64) NULL` |
| 3 | B2 | `CREATE TABLE debt_inbox_dismissals` |
| 4 | B2 | `transactions.amortization_auto_applied BOOLEAN NULL` |

`down_revision` se toma de `alembic heads`, **nunca** del último fichero por
orden alfabético ([PHASE-44.1]). Tras cada una: `alembic heads` debe devolver una
sola línea y `alembic check` no detectar drift.

---

## 7. Orden de ejecución y paradas

```
47.A ──► PARADA A  ──► 47.B ──► PARADA 2 ──► 47.B (cierre) ──► 47.C
         ¿la huella      (bloqueada     calibrar con
         discrimina?)    por D5)        mayo/junio reales
```

| Parada | Qué se decide | Quién |
|---|---|---|
| **A** | Si la cabecera de BBVA discrimina banco↔tarjeta; si no, preguntar antes de heurísticas | Usuario, con los ficheros |
| **2** | D5 + calibración de las tres tolerancias + las dos fixtures reales | Usuario (indelegable) |

---

## 8. Verificación

Por entregable: `pytest` completo (nunca dos a la vez, ni lanzados por un
subagente) · `mypy` · `ruff` · `black` · `alembic upgrade`/`downgrade`
reversibles · `pnpm typecheck && lint && test && knip` ·
`python scripts/check_docs.py`. Con el intérprete del proyecto
(`backend/.venv`), que es el de CI.

Y lo indelegable, al cerrar 47.B: **reproducir julio** —bandeja con los items
correctos, aceptación en ≤5 taps, invariante verde tras resolver— y **un mes
normal**, que debe salir con la bandeja vacía y el «todo cuadra».

---

## 9. Lo que esta fase NO resuelve, dicho en voz alta

- **Las dos verdades del saldo de deuda.** El [`HANDOFF.md`](../HANDOFF.md) dejó
  abierta la pregunta de si el saldo necesita el MUX cuadro-vs-movimientos de
  PHASE-36. La bandeja hace llevadera la traducción; **no reduce las dos verdades
  a una**. Si la respuesta fuera «no las necesita», parte de 47.1 sobraría — y
  esa pregunta se contesta mejor con la bandeja delante que ahora.
- **El desfase del ciclo de tarjeta.** El invariante de §E define el ciclo como
  el intervalo entre cargos, pero un recibo del 8 de julio liquida compras
  cerradas hacia finales de junio: hay un desfase de corte que ninguna fórmula
  del anexo modela. Si en la parada 2 el invariante no cierra con mayo/junio, el
  sospechoso es este desfase antes que la tolerancia — **subir la tolerancia para
  que cierre sería tuning, y está prohibido por §L**.
- **Liquidación anticipada** (PHASE-48, cuyo plan no existe todavía, D14),
  Euríbor, ranking de deudas por coste, simulador what-if.
