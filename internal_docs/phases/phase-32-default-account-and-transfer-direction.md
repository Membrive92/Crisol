# PHASE-32 — Cuenta principal, reasignación en bloque y dirección de transferencias en imports

**Estado**: ✅ completada (en `main`)
**Rama**: `main` (push directo, checkpoint `5a5fc74`)
**PR**: —
**Fecha de merge**: 2026-06-26 (commit `5a5fc74`)

## Objetivo

Cerrar tres huecos detectados tras PHASE-31 sobre la integridad de
saldos por cuenta:

1. **Cuenta principal (`is_default`)** — una cuenta "por defecto" que se
   pre-selecciona en todos los formularios (transacción, import, ticket)
   y cuyo saldo refleja **ahorro neto** (excluye transferencias
   internas).
2. **Reasignación en bloque de cuenta** — mover de golpe las
   transacciones que matcheen los filtros a una cuenta destino
   (consolidar "el mes" en la cuenta principal).
3. **Dirección de transferencias en imports** — un bank-mapping aprendido
   ya no puede invertir el signo de una transferencia: la dirección la
   manda SIEMPRE la descripción (RECIBIDA/REALIZADA).

## Qué se implementó

### 1. Cuenta principal (`accounts.is_default`)

- Columna `is_default BOOLEAN NOT NULL DEFAULT FALSE` en `accounts`
  (migración `w0m25o7lk9n8m4`). Backfill implícito a `false`; nadie tiene
  cuenta principal hasta marcarla.
- **Única por usuario**: `create_account`/`update_account` llaman a
  `clear_default_accounts(user_id, except_id=…)` cuando se marca una,
  desmarcando el resto.
- **Saldo = ahorro neto**: en `get_balances_for_user`, la cuenta
  `is_default` NO suma las transferencias internas (`is_transfer`) — un
  case `is_default & is_transfer → 0`. Mover dinero entre tus propias
  cuentas no es ni ahorro ni gasto. El resto de cuentas sigue en modo
  cash (PHASE-23.1).
- **Pre-selección en formularios** (web + mobile): transaction-form,
  receipt confirm / capture, imports upload-step usan
  `accounts.find(a => a.is_default) ?? accounts[0]`.
- **UI de settings**: botón "Hacer principal" (sólo cuentas activas no
  pasivo) + badge "Principal" (web y mobile).

### 2. Reasignación en bloque (`POST /transactions/reassign-account`)

- Mueve a `target_account_id` todas las tx **activas** que matcheen los
  mismos filtros que `GET /transactions` (cuenta origen, categoría,
  rango de fechas, búsqueda). Sin filtros, todas.
- **Excluye** transferencias internas (`transfer_pair_id` no nulo —
  mover una sola pata rompería el par) y las que ya están en la cuenta
  destino. Valida que la cuenta destino es del usuario (404 si no).
- UI en `/transactions`: `select` de cuenta destino (default = la
  principal) + botón "Mover a la cuenta" + `ConfirmDialog` que avisa si
  aplica a todas o sólo a las filtradas.

### 3. Dirección de transferencias en imports

- `infer_transfer_kind` (antes `_infer_transfer_kind`, ahora público con
  alias retro-compatible) se reutiliza en el pipeline de imports.
- Tras resolver la categoría (mapping > lookup > regla), si es
  `is_transfer` se corrige la dirección con la descripción y se reasigna
  a la categoría hermana del kind correcto (`_load_transfer_categories`
  devuelve `{kind → id}` de las categorías `is_transfer` del usuario).
- **No crea categorías**: si falta la hermana del kind necesario, deja la
  resuelta. Ver lección PHASE-32 en `lessons.md`.

### 4. AUDIT-2026-06 — invalidación de deuda al mutar cuentas

- `useCreateAccount`/`useUpdateAccount`/`useDeleteAccount` invalidan
  además `queryKeys.debt.all`: crear/editar/borrar una cuenta-pasivo
  recalcula los KPIs y charts de deuda, que antes quedaban stale hasta el
  `staleTime` de 60 s.

## Flujo técnico — saldo de la cuenta principal

```
get_balances_for_user (case por tx):
  is_default & is_transfer            → 0           (ahorro neto: ignora movimientos internos)
  liability & expense                 → -amount     (sube deuda)
  liability & income                  → +amount     (amortiza)
  asset & expense                     → -amount
  asset & income                      → +amount
  (resto / sin categoría)             → else_=0     (PHASE-31.3)
saldo cuenta = opening_balance + Σ signed_amount
```

## Archivos clave

### Backend
- `backend/alembic/versions/w0m25o7lk9n8m4_account_is_default.py` — migración.
- `backend/app/modules/personal_finance/accounts/{models,schemas,service,repository}.py`
  — columna, `clear_default_accounts`, saldo ahorro-neto.
- `backend/app/modules/personal_finance/transactions/{router,service,repository}.py`
  — `reassign-account` (endpoint → service → `bulk_reassign_account`).
- `backend/app/modules/personal_finance/imports/service.py` —
  `_load_transfer_categories` + corrección de dirección en `_parse_row`.
- `backend/app/modules/personal_finance/transfers/service.py` —
  `infer_transfer_kind` público (+ alias `_infer_transfer_kind`).

### Frontend
- `packages/types/src/{models/account.ts,dto/account.dto.ts}` — `is_default`.
- `packages/services/src/query/hooks/useAccounts.ts` — invalidación debt.
- `packages/services/.../useTransactions.ts` + `endpoints/transactions.ts`
  — `useReassignAccount`.
- `apps/web/app/(app)/personal-finance/transactions/page.tsx` — UI reasignar.
- `apps/web/app/(app)/settings/accounts/page.tsx` — botón/badge principal.
- `apps/{web,mobile}/components/{transaction-form,receipt*,imports/upload-step}`
  — pre-selección.
- `apps/mobile/app/(modules)/personal-finance/accounts.tsx` — badge principal.

## Endpoints añadidos
- `POST /transactions/reassign-account` → `{ reassigned_count }`.

## Endpoints modificados
- `POST /accounts`, `PUT /accounts/{id}`, `GET /accounts*` — campo
  `is_default` en request/response.

## Migraciones
- `w0m25o7lk9n8m4_account_is_default.py` (down_revision `v9l14n6kj8m7l3`).

## Verificación
- [x] `pnpm typecheck` / `pnpm lint` / `pnpm test` verdes.
- [x] `ruff` / `black --check` / `mypy app/` verdes (los `cast()` redundantes
      que metía la auditoría se quitaron — mypy 1.20.2 los marca con
      `strict=true`).
- [x] `pytest` backend completo — 556 verde (incluye los tests nuevos de los
      HIGH + MEDIUM/LOW).
- [ ] Prueba manual: marcar cuenta principal → saldo ignora transferencias;
      reasignar un mes a la principal; importar extracto con "RECIBIDA"
      mal mapeado → cae en categoría INCOME.

## Correcciones post-auditoría (15 hallazgos)

Una auditoría adversarial multi-agente sobre la superficie de PHASE-32
(antes de commitear) confirmó 15 defectos (5 HIGH + 4 MEDIUM + 6 LOW). Todos
corregidos (o ya moot), con test de regresión en los de lógica. Los 5 HIGH
de corrección/dinero:

- **HIGH#1 — patrimonio neto encogía con transferencias internas a la
  principal.** El carve-out `is_default & is_transfer → 0` zeraba la pata
  entrante en la principal pero la saliente seguía contando en la otra
  cuenta → el agregado bajaba por el importe. Fix: `get_balances_for_user`
  vuelve a CASH para todas; el ahorro neto de la principal es ahora
  display-only (`get_net_savings_movement_for_account`), y el agregado usa
  cash para que las dos patas se cancelen.
- **HIGH#2 — una cuenta de pasivo podía marcarse principal.** `create`/
  `update_account` lo rechazan ahora con 400 (la UI ya ocultaba el botón).
- **HIGH#3 — reasignar cross-divisa borraba dinero del saldo.** El saldo
  por cuenta sólo agrega `currency == account.currency`; mover una tx EUR a
  una cuenta USD la hacía desaparecer. Fix: `bulk_reassign_account` filtra
  por la divisa de la cuenta destino; las de otra divisa se quedan y se
  reportan en `skipped_other_currency` (response + toast).
- **HIGH#4 — el fix de dirección se auto-anulaba si faltaba la categoría
  hermana.** Ahora marca la fila para revisión en vez de dejar la dirección
  invertida en silencio (reintroducía el bug "BBVA a 0 con ingreso neto").
- **HIGH#5 — transferencias sin RECIBIDA/REALIZADA en el texto no se
  corregían.** Ahora caen al SIGNO del extracto (`bank_sign`) cuando el
  texto no decide (BIZUM, ABONO, NÓMINA, TRASPASO…).

Una segunda revisión adversarial **de los propios fixes** cazó un gap
(MEDIUM): `update_account` permitía convertir a tipo de pasivo una cuenta
principal ASSET sin tocar `is_default`, dejando un pasivo principal — cerrado
con `effective_is_default` + re-chequeo de `nature` en el display.

Y los MEDIUM/LOW restantes:

- **MEDIUM#6** — archivar la cuenta principal limpia `is_default` (los forms
  sólo cargan activas; quedaba un puntero colgante).
- **MEDIUM#8** — `infer_transfer_kind` con guard de ambigüedad: texto que
  matchea ambas listas (p. ej. "TRASPASO A FAVOR DE…") devuelve `None` y
  decide el signo (antes ganaba incoming por orden).
- **LOW#11** — índice parcial único `UNIQUE(user_id) WHERE is_default`
  (modelo + migración `y2o47q9nm1p0o6`) como backstop de BD a la unicidad.
- **LOW#12** — el ConfirmDialog del reassign ya no promete un número exacto
  (sobreestimaba); describe las exclusiones.
- **LOW#13** — mobile gana la acción "Hacer principal" (antes sólo el badge).
- **LOW#14** + **MEDIUM#9** — pre-selección de cuenta y destino del reassign
  vía helper `pickPreferredAccount` (principal → primer **activo**, nunca un
  pasivo ni `''`).
- **fix-review LOW** — `TransactionCreate/Update` normaliza la divisa a
  mayúsculas (una `eur` quedaba invisible al saldo, que filtra
  `currency == account.currency`).
- Ya moot: el comentario del carve-out (#10, eliminado) y "reassign sin filtro
  de divisa" (#7, resuelto por HIGH#3).

## Decisiones tomadas
- `is_default` como columna booleana (no enum, no tabla aparte). Unicidad:
  la fuerza el service (`clear_default_accounts`) Y, desde LOW#11, un índice
  parcial único en BD como backstop.
- La dirección de transferencia se deriva del texto **en el punto de
  uso** (import), no se confía en la equivalencia aprendida — generaliza
  PHASE-28 a los bank-mappings.

## Limitaciones conocidas
- `reassign-account` no soporta deshacer (no genera papelera); el usuario
  puede volver a reasignar a la cuenta anterior con los mismos filtros.

Los MEDIUM/LOW del audit (archive-dangling, ambigüedad de hints, índice
único, fallback de pre-selección, contador del ConfirmDialog, make-default
mobile, casing de divisa) están **resueltos** — ver "Correcciones
post-auditoría" arriba.

## Próxima fase
Pendiente de definir.
