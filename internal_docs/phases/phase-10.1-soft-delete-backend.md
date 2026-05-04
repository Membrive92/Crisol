# PHASE-10.1 — Backend soft-delete + papelera de transacciones

**Estado**: ✅ completada
**Rama**: `feat/phase-10.1-soft-delete-backend`
**PR**: —
**Fecha de merge**: 2026-05-04

## Objetivo

Cubrir la mayor laguna funcional pendiente del MVP: borrar una
transacción era destructivo total (DELETE real). Esta fase introduce
soft-delete en el modelo + papelera + endpoints de restore/purge,
manteniendo dashboard y agregaciones limpias de filas trasheadas.

PHASE-10.2 cierra el frente: UI de papelera (web + mobile) y
consumir los nuevos endpoints.

## Qué se implementó

### Migración Alembic — `e4f7c91a8b3d_transactions_soft_delete.py`

- `transactions.deleted_at TIMESTAMPTZ NULL`. NULL = activa,
  timestamp = en papelera.
- Nuevo partial index `ix_transactions_user_id_active` sobre
  `user_id WHERE deleted_at IS NULL` — todas las queries de
  listado/agregación añaden ese filtro, así que mantenemos el índice
  delgado en el caso común.
- Recreado `uq_transactions_user_import_hash` con predicado
  `import_hash IS NOT NULL AND deleted_at IS NULL`. Una fila
  importada y trasheada ya no bloquea re-importar la misma fila del
  fichero original (decisión consciente — si el usuario restaura
  luego, asume el riesgo de duplicado).
- `downgrade()` simétrico: revierte ambos índices al estado previo y
  elimina la columna.

### Modelo `Transaction`

Nuevo `deleted_at: Mapped[datetime | None]`. `__table_args__` pasa
de un solo partial unique a tres índices: el unique recreado con el
predicado nuevo, el partial sobre `user_id` activos, y mantiene el
índice de FK sobre `category_id`.

### Repository `transactions/repository.py`

- `_scope` acepta `deleted: Literal["active","trashed","any"]` (default
  `"active"`). Todos los listados pasan por aquí, así que el filtro
  está garantizado por construcción.
- `get_transaction_by_id(..., deleted="active"|"trashed"|"any")` —
  por defecto sólo activas. Para restore/purge el caller pide
  `"trashed"` para que devolver una activa o inexistente sea 404.
- Nuevas funciones:
  - `list_trashed_transactions(user_id, limit, offset)` — ordena por
    `deleted_at DESC`, cuenta total. Sin filtros adicionales (la
    papelera es vista plana de "qué borré recientemente").
  - `soft_delete_transaction(tx)` — `tx.deleted_at = datetime.now(UTC)`
    + flush + refresh. Usa Python-side timestamp en lugar de
    `func.now()` por coherencia con el typing del campo (la
    diferencia de microsegundos vs server-clock es irrelevante para
    ordenar la papelera).
  - `restore_transaction(tx)` — `tx.deleted_at = None`.
  - `purge_transaction(tx)` — DELETE real.

### Service `transactions/service.py`

- `delete_transaction(...)` mantiene firma pero ahora soft-deletes
  (cambio de comportamiento documentado).
- `list_trashed_transactions(...)`, `restore_transaction(...)`,
  `purge_transaction(...)` — cada uno valida que la tx pertenece al
  usuario y que está en el estado correcto (activa para delete,
  trashed para restore/purge), 404 en cualquier mismatch.
- `get_trashed_transaction(...)` — helper interno que reutilizan
  restore y purge para garantizar 404 si la fila no está en papelera.

### Schemas `transactions/schemas.py`

`TransactionResponse` añade `deleted_at: datetime | None = None`.
Los listados normales lo devuelven siempre `None` (excluyen
soft-deleted); el endpoint `/trash` lo rellena con timestamp para
que la UI pueda pintar "borrada hace X días".

### Router `transactions/router.py`

Tres endpoints nuevos:

- `GET /transactions/trash?limit&offset` — lista paginada de
  soft-deleted del usuario, `deleted_at DESC`.
- `POST /transactions/{id}/restore` → `TransactionResponse`. 404 si
  no existe o no está en papelera.
- `DELETE /transactions/{id}/purge` → 204. 404 si no existe o no
  está en papelera (forzar pasar por `/{id}` soft-delete antes —
  evita el "uy purgué directo sin querer").

`DELETE /transactions/{id}` mantiene 204 pero ahora soft-deletes.
Documentado en docstring + en el doc de endpoints.

### Dashboard

- `dashboard/repository._apply_scope` añade `deleted_at IS NULL`
  siempre. Cubre `get_totals_by_kind`, `get_summary_aggregates`,
  `get_breakdown_by_category`, `get_top_expenses`.
- `get_totals_by_month` no pasa por `_apply_scope` — añadido el
  filtro inline.
- `list_user_currencies` también filtra activas: una moneda que sólo
  exista en transacciones trasheadas no debe aparecer en el selector
  global.
- `dashboard/service.ensure_rates_for_user_scope` filtra activas
  cuando obtiene las fechas distintas a backfillear (no malgastar
  fetches a frankfurter por txs trasheadas).

### Imports

`imports/repository.find_existing_hashes` filtra `deleted_at IS NULL`
para coherencia con el partial unique. Re-importar un fichero cuya
fila previa fue trasheada produce una nueva tx (no bloqueado por
dedup).

### Tests

`backend/tests/test_transactions_soft_delete.py` — 9 tests:

- `test_delete_moves_to_trash_not_destructive` — DELETE 204, GET 404,
  /trash 1 con `deleted_at` no-NULL.
- `test_restore_returns_to_active` — restore + reaparece en list.
- `test_restore_404_when_active` — restaurar una activa es 404.
- `test_purge_only_works_on_trashed` — purgar activa 404, purgar
  trasheada 204, después no aparece ni en /trash.
- `test_trash_user_isolation` — User B no ve/restaura/purga las de A.
- `test_trash_ordered_by_deleted_at_desc` — verifica orden.
- `test_dashboard_summary_excludes_trashed` — summary se actualiza.
- `test_top_expenses_excludes_trashed` — ranking ignora soft-deleted.
- `test_imports_dedup_ignores_trashed` — re-import del mismo fichero
  funciona si el original está en papelera.

Suite completo: 173/173 (164 previos + 9 nuevos), nada roto.

## Flujo técnico

```
 Usuario clica "Borrar transacción"
    ▼
 DELETE /transactions/{id}
    │
    ├── service.delete_transaction
    │     ├── get_transaction (404 si no existe o ya trasheada)
    │     └── soft_delete_in_db: tx.deleted_at = datetime.now(UTC)
    │                            flush + refresh
    │
    ▼ 204
 La tx desaparece de:
   - GET /transactions
   - GET /transactions/{id} (404)
   - dashboard/* (summary, top-expenses, by-category, by-month)
   - currency selector (si era la única en esa moneda)
   - imports dedup (re-import permitido)

 La tx sigue accesible vía:
   - GET /transactions/trash
   - POST /transactions/{id}/restore  → vuelve a activa
   - DELETE /transactions/{id}/purge  → borrado permanente
```

## Archivos clave

- `backend/alembic/versions/e4f7c91a8b3d_transactions_soft_delete.py` (nuevo)
- `backend/app/modules/personal_finance/transactions/models.py` (deleted_at + indexes)
- `backend/app/modules/personal_finance/transactions/repository.py`
  (_scope con DeletedScope, list_trashed, soft_delete, restore, purge)
- `backend/app/modules/personal_finance/transactions/service.py`
  (delete ahora soft, nuevos restore/purge/list_trashed/get_trashed)
- `backend/app/modules/personal_finance/transactions/router.py`
  (GET /trash, POST /restore, DELETE /purge)
- `backend/app/modules/personal_finance/transactions/schemas.py`
  (deleted_at en TransactionResponse)
- `backend/app/modules/personal_finance/dashboard/repository.py`
  (_apply_scope filtra activas; list_user_currencies; get_totals_by_month)
- `backend/app/modules/personal_finance/dashboard/service.py`
  (ensure_rates_for_user_scope filtra activas)
- `backend/app/modules/personal_finance/imports/repository.py`
  (find_existing_hashes filtra activas)
- `backend/tests/test_transactions_soft_delete.py` (nuevo, 9 tests)

## Endpoints

| Método | Ruta | Cambio |
|--------|------|--------|
| DELETE | `/transactions/{id}` | **Cambio de comportamiento**: soft-delete en lugar de DELETE real. 204 igual que antes. |
| GET    | `/transactions/trash` | **Nuevo**. Lista paginada soft-deleted, ordenada `deleted_at DESC`. |
| POST   | `/transactions/{id}/restore` | **Nuevo**. Saca de papelera. 404 si no está trasheada. |
| DELETE | `/transactions/{id}/purge` | **Nuevo**. DELETE real. 404 si no está trasheada (forzar soft-delete previo). |

## Migraciones

`e4f7c91a8b3d_transactions_soft_delete.py` — añade `deleted_at`,
crea partial index activos, recrea unique de import_hash con el
predicado nuevo. `downgrade()` simétrico.

## Verificación

- [x] `ruff check app/ tests/` verde.
- [x] `mypy app/` — 13 errores pre-existentes en `ai/client.py` y
      `dashboard/conversion.py` (PHASE-8.4 los documentaba); **0
      introducidos por esta fase**.
- [x] `pytest tests/` — 173/173 pasan (9 nuevos).
- [ ] Smoke manual con DB real:
  - [ ] Aplicar `alembic upgrade head` en tu BD personal.
  - [ ] DELETE una transacción → ya no aparece en list ni dashboard.
  - [ ] GET /transactions/trash la devuelve.
  - [ ] POST /transactions/{id}/restore la devuelve a list.
  - [ ] DELETE /transactions/{id}/purge tras soft-delete: 204; ya
        no aparece en /trash.

## Decisiones tomadas

- **Soft-delete hide-by-default, no flag opt-in**. Todas las queries
  existentes filtran activas automáticamente (vía `_scope` /
  `_apply_scope`). Una nueva query que olvide el filtro es difícil
  porque los repos están centralizados en esos helpers. Si en el
  futuro hace falta exponer trasheadas en otro endpoint (admin?), se
  pasa el flag `deleted=` explícitamente.
- **`get_transaction_by_id` con `DeletedScope` literal en lugar de
  un bool `include_deleted`**. La distinción `active`/`trashed`/`any`
  es semánticamente distinta de "incluyo o no". El restore endpoint
  necesita `trashed` (no `any`) para que pedir restore sobre una
  activa sea 404.
- **Purge requiere pasar por papelera primero**. `DELETE /{id}/purge`
  sobre una activa devuelve 404. Forzar el doble click reduce el
  riesgo de "uy borré para siempre sin querer". El usuario que sabe
  lo que hace puede encadenar dos llamadas.
- **`deleted_at` en Python-side (`datetime.now(UTC)`) en lugar de
  `func.now()` server-side**. Más simple para typing
  (`Mapped[datetime | None]`), evita `# type: ignore`. El skew vs
  server-clock es ~ms, irrelevante para ordenar papelera.
- **Partial unique de import_hash excluye trasheadas**. Re-importar
  un fichero cuya fila previa fue trasheada produce una tx nueva. Si
  el usuario restaura después, puede acabar con duplicado. Decidido
  porque el flujo "trasheo + re-import" es esperable, y el flujo
  "restauro mucho después + descubro duplicado" se resuelve con
  borrar uno de los dos.
- **Sin TTL / auto-purge nocturno**. La papelera es indefinida en
  esta fase. Si crece y molesta, añadir un cron en una fase futura
  (mismo lugar donde irá el cron de tasas).
- **Tests usan `currency=EUR` explícito en dashboard**. El default
  del endpoint es `USD` cuando no llega ni `currency` ni
  `target_currency` — ese default no se aplica en mis tests porque
  creo txs en EUR. Pasar `currency=EUR` evita el falso negativo.

## Limitaciones conocidas

- **No hay UI todavía** — `DELETE /transactions/{id}` ya hace
  soft-delete pero el frontend lo presenta como borrado total. La
  papelera, restore y purge son inalcanzables desde la UI hasta
  PHASE-10.2.
- **Sin TTL / auto-purge** (decidido). Si la papelera crece de
  forma indefinida, añadir cron en una fase futura.
- **Receipts no soft-delete** — sólo transactions. Borrar un
  receipt sigue siendo destructivo total. Si bite, replicar el
  patrón en su módulo.
- **`receipts.transaction_id` es UUID sin FK formal**. Si se purga
  una transacción, los receipts que la referenciaban quedan
  apuntando a un UUID huérfano (igual que antes — receipts.service
  ya manejaba esto). Si en el futuro se añade FK, hacerlo
  `ON DELETE SET NULL`.
- **`get_transaction_by_id` con `deleted="any"` no se usa** todavía.
  Se mantiene en el contrato por si alguna ruta admin lo necesita
  más adelante. Si en una sesión futura se confirma que no hace
  falta, quitarlo (YAGNI).

## Próxima fase

PHASE-10.2 — Frontend papelera (web + mobile). Cierra el frente:

- Hooks `useTrashedTransactions`, `useRestoreTransaction`,
  `usePurgeTransaction` en `packages/services`.
- Web: nueva ruta `/personal-finance/trash` con tabla + acciones
  restaurar/eliminar permanente.
- Mobile: idem como tab o modal accesible desde el header.
- UX: el toast del DELETE actual cambia de "Eliminado" a
  "Movido a papelera" + acción "Deshacer" (restore inmediato).
