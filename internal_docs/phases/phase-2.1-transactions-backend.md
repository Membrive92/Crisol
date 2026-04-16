# PHASE-2.1 — Transactions backend

**Estado**: ✅ completada
**Rama**: `feat/phase-2.1-transactions-backend`
**PR**: —
**Fecha de merge**: 2026-04-16

> Documento redactado retroactivamente en PHASE-2.2.

## Objetivo

Primer módulo de dominio del MVP: CRUD de **categorías** y **transacciones**
con aislamiento estricto por `user_id`, listado con filtros y paginación.

## Qué se implementó

- Módulo `categories/` siguiendo la plantilla
  `router → service → repository → models → schemas`:
  - Enum `CategoryKind` (`income` / `expense`).
  - CRUD completo con endpoints `/categories`.
- Módulo `transactions/`:
  - Enum `TransactionSource` (`manual` / `import` / `receipt`).
  - `amount` como `NUMERIC(14, 2)` → `Decimal` en Python (nunca `float`).
  - Listado con filtros `category_id`, `date_from`, `date_to`, `search`
    (texto sobre `description`) y paginación `limit` / `offset`.
  - FK `category_id` nullable (una transacción puede existir sin categoría).
- Migración Alembic con tablas `categories` y `transactions`, FKs con
  `ON DELETE CASCADE` hacia `users`.
- Tests de aislamiento multi-usuario: un usuario no puede ver, modificar ni
  borrar registros de otro usuario.

## Endpoints añadidos

### Categories (`/categories`)

| Método | Ruta                     | Descripción                          |
|--------|--------------------------|--------------------------------------|
| GET    | `/categories`            | Lista categorías del usuario         |
| GET    | `/categories/{id}`       | Detalle de una categoría             |
| POST   | `/categories`            | Crear categoría                      |
| PUT    | `/categories/{id}`       | Actualizar categoría                 |
| DELETE | `/categories/{id}`       | Eliminar categoría                   |

### Transactions (`/transactions`)

| Método | Ruta                     | Descripción                                         |
|--------|--------------------------|-----------------------------------------------------|
| GET    | `/transactions`          | Lista con filtros y paginación                      |
| GET    | `/transactions/{id}`     | Detalle de una transacción                          |
| POST   | `/transactions`          | Crear transacción                                   |
| PUT    | `/transactions/{id}`     | Actualizar transacción                              |
| DELETE | `/transactions/{id}`     | Eliminar transacción                                |

Query params de `GET /transactions`:
- `category_id` (UUID)
- `date_from`, `date_to` (ISO datetime)
- `search` (string)
- `limit` (1..200, default 50), `offset` (default 0)

## Archivos clave

- `backend/app/modules/categories/` — módulo completo.
- `backend/app/modules/transactions/` — módulo completo.
- `backend/alembic/versions/*_categories_transactions.py` — migración.
- `backend/tests/modules/test_categories.py` — tests aislamiento.
- `backend/tests/modules/test_transactions.py` — tests aislamiento + filtros.

## Decisiones tomadas

- **`amount` siempre positivo + `category.kind`** determina signo (income vs
  expense) en el frontend. Evita que un `-5,00` en la base signifique algo
  ambiguo.
- **Sin `limit` hard cap tipo 1000**: se cortó a 200 para evitar abusos.
- **`search` es `ILIKE`** simple sobre `description`. Búsqueda semántica /
  full-text queda para una fase posterior.

## Limitaciones conocidas

- No hay agregaciones (balance, por categoría, por mes) — van en PHASE-3.1.
- Sin soft-delete. Borrar es destructivo. Revisable cuando aparezca
  "papelera".
- Sin idempotencia en `POST` — posible si se introduce importación masiva.

## Verificación

- [x] `make verify` verde.
- [x] Tests de aislamiento pasan (usuario A no ve datos de usuario B).
- [x] Migración aplicable y reversible.
- [x] Prueba manual con `curl` contra `/transactions` con distintos filtros.

## Próxima fase

PHASE-2.2 — Transactions frontend.
