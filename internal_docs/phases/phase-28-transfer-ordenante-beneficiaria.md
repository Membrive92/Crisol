# PHASE-28 — Transferencias con cuenta ordenante / beneficiaria explícita

**Estado**: ✅ completada
**Rama**: `feat/phase-24-debt-from-source` (continúa la rama acumulada)
**Fecha de merge**: 2026-05-24

## Objetivo

Bug de negocio reportado por el usuario: una transferencia del 2 de
febrero de 3.102€ que entró en BBVA aparecía como un **cargo** en BBVA
en lugar de un abono. El sistema asumía que todas las transferencias
"salían de la cuenta donde vivía la tx" — daba por hecho la dirección
en función de `category.kind`, y si la categoría asignada por el
import era "Transferencias (Gasto)" tanto para cargos como para
abonos, los abonos quedaban con el signo invertido.

Además rediseñar el modal de "Marcar como transferencia" para que el
usuario indique **explícitamente** quién es ordenante y quién
beneficiaria — sin ambigüedades, sin inferencias.

## Qué se implementó

### Backend — API explícita

`TransferFromSourceRequest` cambia de:

```python
source_transaction_id: uuid.UUID
destination_account_id: uuid.UUID
```

a:

```python
source_transaction_id: uuid.UUID
originating_account_id: uuid.UUID  # ordenante (de aquí sale)
beneficiary_account_id: uuid.UUID  # beneficiaria (aquí entra)
```

`convert_to_internal_transfer` valida:

1. La tx origen existe, es del usuario y no está pareada.
2. `originating ≠ beneficiary`.
3. `source.account_id` es ordenante O beneficiaria (si no, 400 con
   mensaje claro — el usuario eligió un par incompatible con la tx).
4. Ambas cuentas mismo currency que la tx (cross-currency follow-up).

Luego deriva el `source_kind` canónico:
- `source` ordenante → `EXPENSE` en su cuenta.
- `source` beneficiaria → `INCOME` en su cuenta.

Y **fuerza la categoría del origen** al kind canónico vía
`get_or_create_default_transfer_category(kind=source_kind)` +
`repo_assign_category`. Esto cierra el bug: aunque el import hubiera
puesto "Transferencias (Gasto)" a un abono, al marcar como
beneficiaria la tx pasa a "Transferencias (Ingreso)" y el saldo de
BBVA refleja +3.102 € en lugar de un cargo.

### Frontend — modal rediseñado

`apps/web/components/transfers/mark-as-transfer-modal.tsx` (nuevo):

- Modal centrado, escape/click-fuera cierran.
- Header explica ordenante vs beneficiaria.
- Resumen de la tx (fecha, cuenta origen, descripción, importe) con
  el **signo en vivo** según el rol seleccionado (`+` si la cuenta
  es beneficiaria, `−` si es ordenante).
- Dos `Select` distintos:
  - "Cuenta ordenante (de aquí sale el dinero)"
  - "Cuenta beneficiaria (aquí entra el dinero)"
  Ambos incluyen la cuenta de la tx marcada como
  *"(cuenta de esta tx)"* + el resto de cuentas del usuario en la
  misma moneda no archivadas.
- Default al abrir: si `category.kind === 'income'` → tx en
  beneficiaria; si EXPENSE/null → tx en ordenante. El usuario lo puede
  flipear con un click.
- Validaciones inline: "ordenante = beneficiaria" → mensaje rojo; "la
  cuenta de la tx no es ninguna de las dos" → mensaje rojo.
- Si la tx **ya está pareada** y el usuario quiere reasignar, banner
  amarillo de aviso + botón "Reasignar transferencia" que encadena
  `unlink → convert` para que se viva como una sola operación atómica.

### Frontend — entry point en el detalle

`apps/web/app/(app)/personal-finance/transactions/[id]/page.tsx`:

- Eliminado el bloque inline `ConvertToTransferDialog` (Card que
  vivía debajo del form).
- Reemplazado por una `Card` con título *"¿Es un movimiento entre
  tus cuentas?"* + botón **"Marcar como transferencia"** /
  **"Reasignar transferencia"** que abre el modal.
- En éxito: toast con acción *"Ver transferencias"* +
  `router.back()` para volver a la lista con filtros intactos
  (PHASE-27).
- Componente legacy `ConvertToTransferDialog` borrado del repo
  porque ya no se usa.

### Mobile — adaptación mínima

`apps/mobile/components/transfers/convert-to-transfer-block.tsx`
sigue con su UI antigua (un único dropdown) pero mapea internamente:
- categoría INCOME → tx es beneficiaria, otra es ordenante
- el resto → tx es ordenante, otra es beneficiaria

Así mantiene el contrato nuevo sin cambiar la UX mobile. Rediseño
completo en mobile = follow-up.

### Tipos compartidos

`packages/types/src/dto/transfer.dto.ts`:

```ts
export interface TransferFromSourceRequest {
  source_transaction_id: string;
  originating_account_id: string;
  beneficiary_account_id: string;
}
```

## Flujo técnico (caso del bug)

```
Tx en BBVA: 02/02/2026 +3.102€, categoría "Transferencias (Gasto)"
   │  (importada por bank-mapping incorrecto)
   ▼
Usuario entra al detalle → "Marcar como transferencia" → modal
   │
   ▼
Modal default: tx en ordenante (category.kind=expense)
   │  pero el usuario sabe que ENTRÓ → cambia:
   │   ordenante = Wise
   │   beneficiaria = BBVA
   ▼
POST /transfers/from-source {
  source_transaction_id: ...,
  originating_account_id: wise_id,
  beneficiary_account_id: bbva_id,
}
   │
   ▼
Backend valida + detecta source.account_id == bbva_id == beneficiary
   │  → source_role = "beneficiary"
   │  → source_kind = INCOME
   │  → fuerza categoría origen a "Transferencias (Ingreso)"
   │  → crea contraparte en Wise: EXPENSE -3.102€
   │  → empareja ambas vía transfer_pair_id
   ▼
Resultado: BBVA pasa a +3.102€ (income), Wise a -3.102€ (expense).
Par excluido del cashflow.
```

## Tests añadidos

- `test_from_source_400_when_source_not_in_pair` — bloquea el caso
  "la tx no pertenece a ordenante ni beneficiaria".
- `test_from_source_incoming_overrides_wrong_category` — cubre el bug
  original: tx en acc_a con categoría EXPENSE mal asignada → marcar
  acc_a como beneficiaria → balances `acc_a +1000, acc_b -1000`.

Tests existentes (`test_from_source_creates_counterpart_and_pairs`,
`test_from_source_400_same_account`,
`test_from_source_400_different_currency`) actualizados al nuevo
contrato del body.

## Archivos clave

- `backend/app/modules/personal_finance/transfers/schemas.py` —
  `TransferFromSourceRequest` rediseñado
- `backend/app/modules/personal_finance/transfers/service.py` —
  `convert_to_internal_transfer` con validación rol + fuerza categoría
- `backend/app/modules/personal_finance/transfers/router.py` —
  endpoint pasa los nuevos campos
- `backend/tests/test_transfers.py` — 2 tests nuevos + 3 actualizados
- `apps/web/components/transfers/mark-as-transfer-modal.tsx` — modal
  nuevo
- `apps/web/components/transfers/convert-to-transfer-dialog.tsx` —
  **eliminado**
- `apps/web/app/(app)/personal-finance/transactions/[id]/page.tsx` —
  Card con botón "Marcar como transferencia" que abre el modal
- `apps/mobile/components/transfers/convert-to-transfer-block.tsx` —
  mapeo a la nueva API sin cambio de UX
- `packages/types/src/dto/transfer.dto.ts` — DTO actualizado

## Verificación

- [x] `pytest tests/test_transfers.py` (28/28) y suite completa
      (386/386)
- [x] Web + mobile typecheck verdes
- [x] Web 46/46 tests
- [x] Manual: tx "Transferencias (Gasto)" en BBVA → marcar BBVA como
      beneficiaria → categoría se actualiza a "Transferencias
      (Ingreso)" y balance de BBVA pasa de cargo a abono
- [x] Manual: re-pareo con banner de aviso encadena unlink+convert

## Limitaciones conocidas

- Mobile sigue con UI antigua (mapea internamente). Refactor mobile
  para exponer los dos slots = follow-up.
- Cross-currency aún rechaza (heredado de PHASE-23.1).
- "Matchear con tx existente del extracto destino" (en vez de crear
  contraparte de cero) sigue como follow-up — se hacía y se sigue
  haciendo via `/transfers` matcher.

## Próxima fase

Pendientes priorizadas:
- Vista global mejorada en `/transfers` (badge "N pendientes" desde
  Transacciones).
- Mobile parity del nuevo modal.
- Cross-currency transfers.
