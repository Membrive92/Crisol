# PHASE-35 — Compras a plazos bajo una tarjeta (`parent_account_id`)

**Estado**: 🚧 en curso (código completo + verde; pendiente prueba manual del usuario y PR)
**Rama**: `feat/phase-34-transaction-flow` (convive con PHASE-34)
**PR**: —
**Fecha de merge**: —

## Objetivo

Permitir que **una tarjeta de crédito agrupe varias compras financiadas a
plazos**, cada una con su propio TIN/TAE/plazo/cuadro de amortización. El
modelo previo sólo admitía **un** plan por cuenta, así que dos compras a
plazos distintas en la misma tarjeta no se podían representar con exactitud.

Cada compra a plazos es una **cuenta-deuda hija** (`credit_card`) con
`parent_account_id` apuntando a la tarjeta. En la UI las hijas se **agrupan
bajo el padre** en el módulo de deuda (con total combinado) y se **ocultan**
de los selectores de cuenta de transacciones e imports: no son destino de
movimientos, su deuda vive en su cuadro de amortización.

## Qué se implementó

### Backend
- **Columna** `accounts.parent_account_id` (nullable, FK a `accounts`,
  `ON DELETE CASCADE`) + índice parcial. Migración `a4q70s2pn4r3q9`.
- **Validación en `create_account`** cuando llega `parent_account_id`:
  - el padre existe y es del usuario (404 si no);
  - el padre es `credit_card` (400 si no);
  - el padre no es a su vez una compra a plazos (no se anida);
  - la cuenta hija es `credit_card`;
  - trae plan completo (capital > 0 + TIN + plazo + fecha) para generar su
    cuadro propio (400 si falta algo).
- `AccountResponse` y `AccountBalance` exponen `parent_account_id`.
- **No** se permite re-parentar vía `update` (la columna no está en
  `AccountUpdate`): el vínculo se fija al crear.

### Frontend
- **Tipos** (`packages/types`): `parent_account_id` en `Account`,
  `AccountCreateRequest` y `AccountBalance`.
- **Alta** (`account-form-fields.tsx` + `settings/accounts/page.tsx`):
  selector "¿Es una compra a plazos dentro de una tarjeta?" visible **sólo al
  crear** una `credit_card` (se pasa `parentCardOptions` con las tarjetas
  activas no-hijas). Al elegir padre, el plan de financiación pasa a
  **obligatorio** (capital + TIN + plazo + fecha; validado en cliente y
  backend) y el label del importe cambia a "Importe de la compra".
- **Selectores de transacción** (`transaction-form.tsx`, `upload-step.tsx`):
  las hijas se ocultan; nunca se pre-seleccionan. Al editar una tx ya
  asignada a una hija (caso heredado) se conserva su cuenta para no perderla.
- **Vista de deuda** (`debt-list.tsx`): las hijas se anidan bajo su tarjeta
  padre (indentadas, etiqueta "Compra a plazos") y el padre muestra el
  **total combinado** (tarjeta + hijas de su misma moneda) y cuántas compras
  agrupa. Una hija huérfana (padre archivado/ausente) cae a nivel superior
  para no perderse.

## Migraciones
- `a4q70s2pn4r3q9_accounts_parent_account_id.py` — columna nullable + FK
  CASCADE + índice parcial `ix_accounts_parent_account_id`. Aditiva.

## Archivos clave
### Backend
- `accounts/models.py` — columna `parent_account_id` + índice.
- `accounts/schemas.py` — `parent_account_id` en `AccountCreate`,
  `AccountResponse`, `AccountBalance`.
- `accounts/service.py` — validación de compra a plazos en `create_account`.
- `tests/test_accounts.py` — cobertura de la validación.

### Frontend
- `packages/types/src/models/account.ts`, `account-balance.ts`,
  `dto/account.dto.ts` — `parent_account_id`.
- `apps/web/components/accounts/account-form-fields.tsx` — selector de padre +
  plan obligatorio en compra a plazos.
- `apps/web/app/(app)/settings/accounts/page.tsx` — `parentCardOptions`,
  payload y validación.
- `apps/web/components/transactions/transaction-form.tsx`,
  `apps/web/components/imports/upload-step.tsx` — ocultar hijas.
- `apps/web/components/debt/debt-list.tsx` (+ `debt-list.test.tsx`) —
  agrupación padre→hijas + total combinado.

## Verificación
- [x] `ruff` / `mypy app/` verdes.
- [x] `pytest` backend completo — **589 verde** (incluye `test_accounts`).
- [x] `pnpm lint` / `pnpm typecheck` verdes.
- [x] `pnpm test` — 71 web (incluye `debt-list.test`) + 18 móvil verdes.
- [ ] Prueba manual del usuario (gate de commit):
  - Crear una tarjeta; luego crear una "compra a plazos" dentro de ella con
    su plan → aparece anidada en `/debt` con su cuadro.
  - El total de la tarjeta en `/debt` suma tarjeta + compras a plazos.
  - Las compras a plazos no aparecen al registrar una transacción ni al
    importar.

## Decisiones tomadas
- **Cuentas exactas + vista unificada** (decisión del usuario en ADR-0004):
  cada compra a plazos es una cuenta-deuda real (saldo y cuadro exactos),
  pero la UI las agrupa bajo la tarjeta y las oculta de los selectores — el
  usuario nunca navega cuenta por cuenta.
- **El vínculo se fija al crear**, no se re-parenta: simplifica el invariante
  (una hija siempre tuvo su plan propio desde el alta).

## Limitaciones conocidas
- Las compras a plazos siguen apareciendo como filas planas en
  **Ajustes › Cuentas** (donde se gestionan/borran). La agrupación es sólo de
  la vista de deuda y los selectores.
- No hay aún un atajo "añadir compra a plazos" desde la fila de la tarjeta en
  `/debt`; se crea desde el alta de cuenta eligiendo la tarjeta padre.

## Próxima fase
Pendiente de definir (posible: atajo de alta de compra a plazos desde `/debt`
+ paridad móvil de la agrupación).
