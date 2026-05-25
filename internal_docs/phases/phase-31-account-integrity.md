# PHASE-31 — Saneamiento de cuentas e integridad de saldos

**Estado**: 📋 planificada
**Rama propuesta**: `feat/phase-31-account-integrity`
**Prioridad**: alta — los saldos incorrectos son bloqueantes para el uso normal de la app
**Orden recomendado**: ejecutar **antes** de PHASE-30 (rediseño módulo deuda), porque
PHASE-30 construye análisis encima del modelo de cuentas saneado.

## Objetivo

Resolver cuatro fallos observados en el módulo `accounts` que producen
saldos incorrectos visibles para el usuario:

1. **Transferencias entrantes mal categorizadas como gasto**. Causa
   raíz en el seed: existe una sola categoría "Transferencias"
   (`kind=EXPENSE`) cuya regla `_cc("TRANSFERENCIA", 80)` matchea
   indistintamente "TRANSFERENCIA REALIZADA" y "TRANSFERENCIA
   RECIBIDA". Resultado: ingresos por transferencia restan al saldo en
   lugar de sumar. Caso reportado con desviación de orden ~21.000 € en
   una cuenta.
2. **Cuentas `brokerage` / `crypto` contaminan el patrimonio neto**.
   El módulo de inversión está planificado pero no implementado; estas
   cuentas existen hoy solo como destino de transferencias. Su saldo
   como `Σ(movimientos)` no representa el valor real de la cartera y
   contamina `total_assets` en el dashboard y PositionHero.
3. **Transacciones sin categoría suman al saldo** por el fallback
   `else_=Transaction.amount` en `get_balances_for_user`. Si una tx
   queda sin categorizar tras un import fallido, contamina el saldo en
   lugar de quedar fuera del cómputo hasta que el usuario la
   categorice.
4. **Heurística `_infer_transfer_kind` sesgada a banca minorista**.
   Solo busca 5 palabras concretas en la descripción y no respeta el
   kind de una categoría preexistente. Falla en cualquier extracto que
   no use el vocabulario español canónico (brokers, fintechs,
   neobancos extranjeros).

## Sub-fases

| Fase | Nombre | Esfuerzo |
|------|--------|----------|
| 31.1 | Seed transferencias bidireccional + reglas no ambiguas + recategorizado de datos existentes | S |
| 31.2 | UI bulk-fix: detección y corrección de transferencias con dirección dudosa | M |
| 31.3 | Fix `else_=0` para tx sin categoría + banner UX en transacciones | S |
| 31.4 | Brokerage/crypto excluidos del patrimonio neto agregado | S |
| 31.5 | Robustecimiento de `_infer_transfer_kind` con señal de categoría preexistente | XS |

Cada sub-fase es entregable independiente. 31.1 es la más urgente.

---

## PHASE-31.1 — Seed bidireccional + recategorizado

### Cambios en el seed (`dataset.py`)

**Modificar** la categoría existente "Transferencias" para que solo
matchee descripciones inequívocamente salientes. Eliminar la regla
ambigua `_cc("TRANSFERENCIA", 80)`:

```python
{
    "name": "Transferencias",
    "kind": CategoryKind.EXPENSE,
    "is_transfer": True,
    "color": "#64748b",
    "icon": "↔️",
    "rules": [
        _cc("TRANSFERENCIA REALIZADA", 20),
        _cc("TRANSFERENCIA HACIA", 20),
        _cc("CARGO POR TRANSFERENCIA", 20),
        _cc("ORDENES PAGO", 20),
        _cc("ORDEN DE PAGO", 20),
        # ELIMINADAS — eran ambiguas y producían el bug:
        #   _cc("TRANSFERENCIA", 80),
        #   _cc("TRANSFERENCIAS", 80),
        # Si una tx solo dice "TRANSFERENCIA" sin más, queda sin
        # categorizar y se le pide al usuario que decida. Es preferible
        # a adivinar mal sistemáticamente.
    ],
},
```

**Añadir** una categoría nueva para la dirección INCOME:

```python
{
    "name": "Transferencia a favor",
    "kind": CategoryKind.INCOME,
    "is_transfer": True,
    "color": "#d97706",
    "icon": "💰",
    "rules": [
        _cc("TRANSFERENCIA RECIBIDA", 20),
        _cc("TRANSFERENCIA A FAVOR", 20),
        _cc("ABONO POR TRANSFERENCIA", 20),
        _cc("ABONO TRANSFERENCIA", 20),
        _cc("INGRESO POR TRANSFERENCIA", 20),
        _cc("TRANSFERENCIA DESDE", 25),
        _cc("RECIBIDA DE", 25),
        _cc("TRASPASO RECIBIDO", 25),
    ],
},
```

**Por qué `priority=20`**: las reglas específicas tienen que ganar
contra las custom del usuario (default 100) y contra las generales del
seed (80). El motor de reglas (PHASE-20) usa **menor número = mayor
prioridad**.

**Por qué desaparecen las reglas genéricas**: el caso de uso del
usuario incluye categorías custom como `SCL` (gasto cuya forma de pago
es transferencia bancaria). Reglas genéricas tipo "TRANSFERENCIA"
secuestraban esos casos. El nuevo seed deja "TRANSFERENCIA" sin regla
canónica para que la regla custom del usuario gane.

### Migración Alembic con recategorizado de datos existentes

Migración `o2c36g9b4f0a3_seed_transfer_categories.py`:

```python
"""PHASE-31.1 — Saneamiento de categorías de transferencia.

1. Inserta la categoría "Transferencia a favor" (INCOME, is_transfer)
   para todos los usuarios que ya tienen seed de "Transferencias" pero
   no la versión INCOME.
2. Recategoriza las transacciones existentes que están en
   "Transferencias" (EXPENSE) pero cuya descripción indica claramente
   un movimiento entrante.

La migración es idempotente: re-ejecutarla no duplica categorías ni
vuelve a recategorizar las que ya están bien.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC

from alembic import op
import sqlalchemy as sa


revision = "o2c36g9b4f0a3"
down_revision = "n1b25f8a3d9e4"  # ← ajustar al último cabeza real
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Para cada usuario que tiene "Transferencias" EXPENSE,
    #    crear "Transferencia a favor" INCOME si no existe.
    bind.execute(sa.text("""
        INSERT INTO categories (
            id, user_id, name, kind, is_transfer, color, icon,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            tx_cat.user_id,
            'Transferencia a favor',
            'INCOME'::categorykind,
            TRUE,
            '#d97706',
            '💰',
            NOW(),
            NOW()
        FROM categories tx_cat
        WHERE tx_cat.name = 'Transferencias'
          AND tx_cat.kind = 'EXPENSE'
          AND tx_cat.is_transfer = TRUE
          AND NOT EXISTS (
              SELECT 1 FROM categories existing
              WHERE existing.user_id = tx_cat.user_id
                AND existing.name = 'Transferencia a favor'
          );
    """))

    # 2. Recategorizar transacciones cuya descripción indica
    #    inequívocamente que son entrantes pero están en la categoría
    #    EXPENSE. Sólo toca las que cumplen ambos: categoría incorrecta
    #    + descripción que matchea uno de los patrones de entrada.
    bind.execute(sa.text("""
        UPDATE transactions t
        SET category_id = (
            SELECT id FROM categories
            WHERE user_id = t.user_id
              AND name = 'Transferencia a favor'
              AND kind = 'INCOME'
            LIMIT 1
        ),
        updated_at = NOW()
        FROM categories c_old
        WHERE t.category_id = c_old.id
          AND c_old.kind = 'EXPENSE'
          AND c_old.is_transfer = TRUE
          AND c_old.name = 'Transferencias'
          AND t.deleted_at IS NULL
          AND (
              t.description ILIKE '%RECIBIDA%'
           OR t.description ILIKE '%RECIBIDO%'
           OR t.description ILIKE '%ABONO POR TRANSFER%'
           OR t.description ILIKE '%ABONO TRANSFER%'
           OR t.description ILIKE '%INGRESO POR TRANSFER%'
           OR t.description ILIKE '%TRANSFERENCIA DESDE%'
           OR t.description ILIKE '%TRASPASO RECIBIDO%'
          )
          AND t.transfer_pair_id IS NULL  -- no tocar las ya emparejadas
        ;
    """))


def downgrade() -> None:
    # No revertimos el recategorizado: la información de qué tx fue
    # tocada se ha perdido. Volver a EXPENSE rompería el saldo del
    # usuario otra vez. Sí permitimos eliminar la categoría
    # "Transferencia a favor" si NO tiene tx asociadas; si las tiene
    # (que las tendrá tras 1), lanzamos error.
    bind = op.get_bind()
    blocking = bind.execute(sa.text("""
        SELECT COUNT(*) FROM transactions t
        JOIN categories c ON c.id = t.category_id
        WHERE c.name = 'Transferencia a favor'
          AND c.kind = 'INCOME'
    """)).scalar()
    if blocking and int(blocking) > 0:
        raise RuntimeError(
            f"PHASE-31.1 downgrade bloqueado: {blocking} transacciones "
            "asignadas a 'Transferencia a favor'. Recategorízalas antes "
            "de hacer downgrade."
        )
    bind.execute(sa.text("""
        DELETE FROM categories
        WHERE name = 'Transferencia a favor'
          AND kind = 'INCOME'
          AND is_transfer = TRUE
    """))
```

### Archivos backend

- `backend/app/modules/personal_finance/seed/dataset.py` — actualizar
  reglas de "Transferencias" + añadir "Transferencia a favor".
- `backend/alembic/versions/o2c36g9b4f0a3_seed_transfer_categories.py` —
  migración con backfill.

### Tests (`backend/tests/test_seed_transfers.py`)

- Tras seed inicial: existen ambas categorías "Transferencias"
  (EXPENSE) y "Transferencia a favor" (INCOME).
- Una tx importada con descripción "TRANSFERENCIA RECIBIDA DE X" cae
  en la categoría INCOME, no en EXPENSE.
- Una tx importada con descripción "TRANSFERENCIA REALIZADA A Y" cae
  en EXPENSE.
- Una tx importada con descripción "TRANSFERENCIA" sin más
  (ambiguo) → `category_id IS NULL` (no se adivina).
- Una tx importada con descripción "Transferencia a SCL" (la regla
  custom del usuario para "SCL" tiene priority 100 vs nuestra 20)
  cae en la regla específica del usuario, no en la nuestra. Test que
  protege la convivencia con categorías custom.
- Migración `o2c36g9b4f0a3` aplicada a una BD con 5 tx en
  "Transferencias" (3 RECIBIDA + 2 REALIZADA): tras `upgrade()`, las 3
  RECIBIDA están en "Transferencia a favor", las 2 REALIZADA siguen
  en "Transferencias".
- `downgrade()` con tx ya asignadas a la nueva categoría: lanza error.
- `upgrade()` ejecutado dos veces: idempotente (no crea categoría
  duplicada, no recategoriza dos veces).

### Verificación

- [ ] `pytest backend/tests/test_seed_transfers.py` verde.
- [ ] `alembic upgrade head` aplica la migración limpia en BD local
      con datos reales.
- [ ] Smoke manual: subir un extracto BBVA con un mix de transferencias
      realizadas y recibidas. Tras el import, el saldo de la cuenta
      coincide con el real.
- [ ] Smoke manual: confirmar con el usuario reportante (~21.000 €)
      que el saldo se autocorrige tras la migración.

### Hotfix antes de la migración (anexo SQL)

Para el usuario reportante que necesita corrección **antes** de que la
fase llegue a su entorno, el siguiente SQL ejecuta el equivalente del
paso 2 de la migración. Probar primero el `SELECT`, luego el `UPDATE`.

```sql
-- Sustituye :user_email por tu email registrado.
-- Asume que ya tienes una categoría INCOME que actúa como
-- contraparte (la captura de pantalla del usuario muestra
-- "TRANSFERENCIA A FAVOR" existente).

WITH user_ctx AS (
    SELECT id FROM users WHERE email = :user_email
),
wrong_cat AS (
    SELECT id FROM categories
    WHERE user_id = (SELECT id FROM user_ctx)
      AND name = 'Transferencias'
      AND kind = 'EXPENSE'
),
right_cat AS (
    SELECT id FROM categories
    WHERE user_id = (SELECT id FROM user_ctx)
      AND kind = 'INCOME'
      AND (
          name ILIKE 'Transferencia a favor%'
       OR name ILIKE 'Transferencia interna (entrada)%'
      )
    ORDER BY created_at ASC
    LIMIT 1
)

-- PASO 1: revisar qué se va a tocar.
SELECT
    t.id,
    t.occurred_at,
    t.amount,
    t.description,
    (SELECT name FROM categories WHERE id = t.category_id) AS current_category
FROM transactions t
WHERE t.user_id = (SELECT id FROM user_ctx)
  AND t.category_id IN (SELECT id FROM wrong_cat)
  AND t.deleted_at IS NULL
  AND t.transfer_pair_id IS NULL
  AND (
      t.description ILIKE '%RECIBIDA%'
   OR t.description ILIKE '%RECIBIDO%'
   OR t.description ILIKE '%ABONO POR TRANSFER%'
   OR t.description ILIKE '%ABONO TRANSFER%'
   OR t.description ILIKE '%INGRESO POR TRANSFER%'
   OR t.description ILIKE '%TRANSFERENCIA DESDE%'
   OR t.description ILIKE '%TRASPASO RECIBIDO%'
  )
ORDER BY t.occurred_at DESC;

-- PASO 2: tras revisar la lista, ejecutar el UPDATE.
-- DESCOMENTAR cuando se haya verificado:
--
-- UPDATE transactions
-- SET category_id = (SELECT id FROM right_cat),
--     updated_at = NOW()
-- WHERE id IN (
--     -- copia aquí los IDs del SELECT del paso 1 que quieras tocar
-- );
```

**Antes de ejecutar el UPDATE en local**: `pg_dump` por seguridad.

---

## PHASE-31.2 — UI bulk-fix de transferencias con dirección dudosa

### Backend

**Endpoint nuevo** `GET /transfers/misclassified`:

Devuelve transacciones que cumplen las dos condiciones:

1. Categoría con `is_transfer=true`.
2. Descripción indica una dirección incompatible con el `kind` de la
   categoría (RECIBIDA en EXPENSE, o REALIZADA/HACIA en INCOME).

```python
# transfers/repository.py

INCOME_HINTS_SQL = [
    "%RECIBIDA%", "%RECIBIDO%",
    "%ABONO POR TRANSFER%", "%ABONO TRANSFER%",
    "%INGRESO POR TRANSFER%", "%TRANSFERENCIA DESDE%",
    "%TRASPASO RECIBIDO%",
]
EXPENSE_HINTS_SQL = [
    "%TRANSFERENCIA REALIZADA%", "%TRANSFERENCIA HACIA%",
    "%CARGO POR TRANSFER%", "%ORDEN DE PAGO%",
]

async def list_misclassified_transfers(
    db: AsyncSession, user_id: uuid.UUID,
) -> list[MisclassifiedSuspect]:
    # tx en categoría is_transfer EXPENSE pero descripción es de income
    # OR tx en categoría is_transfer INCOME pero descripción es de expense
    # AND tx no está ya en un par (transfer_pair_id IS NULL).
    # Devuelve la sugerencia de categoría destino (la counterpart kind).
    ...
```

**Endpoint nuevo** `POST /transfers/reclassify-bulk`:

```python
class ReclassifyBulkRequest(BaseModel):
    transaction_ids: list[uuid.UUID]
    # Opcional: forzar la categoría destino. Si no viene, el service
    # busca/crea la default del kind opuesto al actual.
    target_category_id: uuid.UUID | None = None
```

Service:
- Valida que las tx existen y pertenecen al usuario.
- Para cada tx, infiere el `kind` correcto desde la descripción
  (reusando `_infer_transfer_kind` mejorado de 31.5).
- Reasigna `category_id` a la categoría del kind correcto
  (`get_or_create_default_transfer_category`).
- Devuelve `{ reclassified: int, errors: [...] }`.

### Frontend web

**Vista nueva** en `/personal-finance/transfers`: una sección
"Transferencias con dirección dudosa" arriba de la lista actual de
sospechosas. Aparece solo si `misclassified.length > 0`.

```
┌────────────────────────────────────────────────────────────┐
│ ⚠ TRANSFERENCIAS POSIBLEMENTE MAL CATEGORIZADAS            │
│                                                            │
│ Hemos detectado 7 transacciones cuya categoría no coincide │
│ con la dirección del movimiento. Esto puede estar          │
│ afectando al saldo de tus cuentas.                         │
│                                                            │
│ [ ] 31/03/2026 · TRANSFERENCIA RECIBIDA D... · -1.820 €    │
│      Actual: Transferencias (gasto)                        │
│      Sugerido: Transferencia a favor (ingreso)             │
│                                                            │
│ [ ] 19/03/2026 · TRANSFERENCIA RECIBIDA D... · -2.000 €    │
│      Actual: Transferencias (gasto)                        │
│      Sugerido: Transferencia a favor (ingreso)             │
│                                                            │
│ ... (5 más)                                                │
│                                                            │
│ [Seleccionar todas]    [Re-categorizar las marcadas]       │
└────────────────────────────────────────────────────────────┘
```

**Componente nuevo** `apps/web/components/transfers/misclassified-section.tsx`.

### Tests

- `test_transfers.py`: una tx con descripción "RECIBIDA" en categoría
  "Transferencias" (EXPENSE) aparece en `/transfers/misclassified`.
- Una tx con descripción ambigua "TRANSFERENCIA" sin más NO aparece
  (no hay forma de saber la dirección, no es candidata).
- `POST /transfers/reclassify-bulk` con 3 IDs reclasifica correctamente
  y devuelve `reclassified=3`.
- Idempotente: ejecutar dos veces no rompe.

---

## PHASE-31.3 — Fix `else_=0` para tx sin categoría

### Cambio en `accounts/repository.py`

**Línea 126 actual**:
```python
else_=Transaction.amount,   # ← bug: sin categoría afecta al saldo
```

**Corregido**:
```python
else_=Decimal("0"),   # tx sin categoría no contribuye al saldo
                      # hasta que el usuario la categorice.
```

Idéntico cambio en `get_balance_for_account` (líneas 163, 169).

### Banner UX

**Componente nuevo** `apps/web/components/transactions/uncategorized-banner.tsx`:

```
┌────────────────────────────────────────────────────────────┐
│ ⓘ Tienes 4 transacciones sin categorizar (€340 en total).  │
│   No afectan a tu saldo hasta que les asignes una categoría.│
│                                       [Ver y categorizar]  │
└────────────────────────────────────────────────────────────┘
```

Aparece encima de la tabla de transacciones (`/personal-finance/transactions`)
solo si `count_uncategorized > 0`.

Click en "Ver y categorizar" → aplica filtro `?category=none` (filtro
ya existente).

### Tests

- Una tx sin `category_id` no afecta al saldo de la cuenta (regresión
  del bug actual).
- Cuando la tx recibe categoría, el saldo se actualiza coherentemente.
- El banner aparece solo cuando hay tx sin categorizar; desaparece al
  categorizar la última.

### Migración de datos

**Ninguna**: el cambio es puramente de cómputo. Tras desplegarlo, los
saldos se recalculan automáticamente al siguiente request.

**Consideración**: usuarios con saldo "compensado" por tx mal contadas
verán **cambiar su saldo** al desplegar 31.3. Esto es **el
comportamiento correcto**, pero conviene avisar con changelog visible
en el primer login: *"Hemos corregido un bug en el cómputo de saldos.
Si tienes transacciones sin categorizar, ahora aparecen como pendientes
y tu saldo refleja solo las transacciones confirmadas."*

---

## PHASE-31.4 — Brokerage/crypto fuera del patrimonio neto

### Cambios en `accounts/service.py`

**Modificar** `get_balances` (líneas 225-287). En el bucle que computa
`total_assets` y `total_liabilities`, añadir una rama que excluye
brokerage/crypto:

```python
# Tipos cuya valoración real no se computa por Σ(movimientos).
# Mientras no exista el módulo de inversiones (locked en el registry),
# estas cuentas no entran al patrimonio neto agregado. Sí aparecen en
# `items` para que el usuario las vea y la mecánica de transferencias
# las acepte como destino válido.
UNVALUED_TYPES = {AccountType.BROKERAGE, AccountType.CRYPTO}

for account in accounts:
    movements_balance = movements.get(account.id, Decimal("0"))
    current_balance = account.opening_balance + movements_balance
    items.append(
        AccountBalance(
            account_id=account.id,
            ...
            is_unvalued=account.type in UNVALUED_TYPES,  # nuevo campo
        )
    )
    if account.is_archived:
        continue
    active_currencies.add(account.currency)

    # 31.4: brokerage/crypto NO entran al agregado de patrimonio.
    if account.type in UNVALUED_TYPES:
        continue

    if account.nature == AccountNature.LIABILITY:
        total_liabilities += current_balance
    else:
        total_assets += current_balance
```

### Schemas

`AccountBalance` gana un campo:

```python
is_unvalued: bool = False
```

### Frontend web

**Modificar** `apps/web/components/analysis/position-hero.tsx`:

- En `AccountsRow`, cuando `item.is_unvalued=true`, mostrar badge "No valorada" junto al tile (estilo `surface-muted` background + `text-subtle` foreground, 10px overline).
- Tooltip: *"El valor real de esta cuenta depende del mercado y no se computa automáticamente. Solo registra movimientos para historial y transferencias."*

**Modificar** `apps/web/components/accounts/balances-card.tsx`:

- Misma lógica: badge "No valorada" en las filas correspondientes.

**Modificar** `apps/web/app/(app)/settings/accounts/page.tsx`:

- En el form de creación/edición, cuando el tipo es `brokerage` /
  `crypto`, mostrar nota informativa: *"Esta cuenta no entra al
  cálculo de patrimonio neto. Se usa solo para historial de
  movimientos y transferencias. El módulo de inversión está
  planificado para una versión futura."*

### Tests

- `test_accounts.py`: una cuenta brokerage con saldo +10.000 no suma
  a `total_assets`. Su `is_unvalued=true` en la respuesta.
- Una cuenta brokerage con saldo +10.000 y otra bank con +5.000:
  `total_assets=5000`, items contiene ambas, `net_worth=5000`.
- `items` mantiene a la cuenta brokerage visible (no se filtra).

### Migración de datos

Ninguna — cambio de cómputo. Los usuarios con cuenta brokerage verán
su patrimonio neto **bajar** al desplegar, reflejando solo las cuentas
valoradas. Cambio coherente con el principio de precisión del producto.

Changelog visible: *"Las cuentas de inversión y crypto ya no
contaminan tu patrimonio neto con saldos no representativos. Cuando
implementemos el módulo de inversiones, se reincorporarán con su
valoración real."*

---

## PHASE-31.5 — Robustecimiento de `_infer_transfer_kind`

### Problema actual

`transfers/service.py:246-264`:

```python
_INCOMING_DESCRIPTION_HINTS = ("recibida", "recibido", "entrante", "entrada", "a favor")

def _infer_transfer_kind(description: str | None) -> CategoryKind:
    if description is None:
        return CategoryKind.EXPENSE     # default arbitrario
    lowered = description.lower()
    return (
        CategoryKind.INCOME
        if any(hint in lowered for hint in _INCOMING_DESCRIPTION_HINTS)
        else CategoryKind.EXPENSE
    )
```

Tres fallos:
1. **Vocabulario limitado**: faltan "abono", "ingreso por", "traspaso recibido", "transferencia desde", "provisión".
2. **Default arbitrario** cuando la descripción no matchea nada.
3. **No usa información que ya tiene**: si la tx ya tiene una
   categoría con `kind` explícito, debería respetarla en lugar de
   re-inferir.

### Cambios

**Ampliar la lista de hints**:

```python
_INCOMING_DESCRIPTION_HINTS = (
    "recibida", "recibido", "entrante", "entrada", "a favor",
    "abono por transfer", "abono transfer",
    "ingreso por transfer",
    "transferencia desde", "transf desde",
    "traspaso recibido", "traspaso de",
    "provisión de", "provision de",
)

_OUTGOING_DESCRIPTION_HINTS = (
    "realizada", "realizado", "saliente", "salida",
    "transferencia hacia", "transf hacia",
    "cargo por transfer",
    "orden de pago", "ordenes pago",
    "traspaso enviado", "traspaso a",
)
```

**Cambiar la firma para aceptar contexto**:

```python
def _infer_transfer_kind(
    description: str | None,
    *,
    existing_category_kind: CategoryKind | None = None,
) -> CategoryKind | None:
    """Infiere el kind correcto para una tx que se está marcando como
    transferencia.

    Orden de señales:
    1. Si la tx ya tiene categoría con kind explícito, respetarlo
       (asumimos que el rules engine + el usuario lo decidieron bien).
    2. Si la descripción matchea hints de INCOME, INCOME.
    3. Si la descripción matchea hints de EXPENSE, EXPENSE.
    4. Si nada matchea, devolver None — el caller decide si fallar
       o pedir input al usuario.
    """
    if existing_category_kind is not None:
        return existing_category_kind

    if description is None:
        return None

    lowered = description.lower()
    if any(hint in lowered for hint in _INCOMING_DESCRIPTION_HINTS):
        return CategoryKind.INCOME
    if any(hint in lowered for hint in _OUTGOING_DESCRIPTION_HINTS):
        return CategoryKind.EXPENSE
    return None
```

### Cambios en los callers

`mark_as_transfer` (`service.py:267-305`):

```python
async def mark_as_transfer(...):
    ...
    # Si la tx ya tenía categoría, pasamos su kind como señal primaria.
    existing_kind = None
    if tx.category_id is not None:
        existing_cat = await get_category_by_id(db, tx.category_id, user_id)
        if existing_cat is not None:
            existing_kind = existing_cat.kind

    target_kind = _infer_transfer_kind(
        tx.description,
        existing_category_kind=existing_kind,
    )

    if target_kind is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No podemos determinar si esta transferencia es entrante o "
                "saliente desde la descripción. Edita la categoría manualmente "
                "o usa 'Convertir en transferencia' especificando las dos "
                "cuentas."
            ),
        )

    category = await get_or_create_default_transfer_category(
        db, user_id, kind=target_kind
    )
    await repo_assign_category(db, tx, category.id)
    ...
```

### Tests

- Tx con descripción "ABONO POR TRANSFERENCIA": kind = INCOME.
- Tx con descripción "TRASPASO RECIBIDO DE X": kind = INCOME.
- Tx con descripción "TRANSFERENCIA HACIA Z": kind = EXPENSE.
- Tx con descripción "X" (ambigua) sin categoría previa: devuelve None
  y el caller retorna 400 con mensaje claro.
- Tx con descripción "X" pero ya con categoría INCOME asignada:
  respeta INCOME aunque la descripción no matchee.

---

## Resumen de archivos clave

### Backend
```
backend/app/modules/personal_finance/seed/dataset.py                            [31.1]
backend/alembic/versions/o2c36g9b4f0a3_seed_transfer_categories.py              [nuevo, 31.1]
backend/app/modules/personal_finance/transfers/repository.py                    [31.2]
backend/app/modules/personal_finance/transfers/service.py                       [31.2, 31.5]
backend/app/modules/personal_finance/transfers/router.py                        [31.2]
backend/app/modules/personal_finance/transfers/schemas.py                       [31.2]
backend/app/modules/personal_finance/accounts/repository.py                     [31.3]
backend/app/modules/personal_finance/accounts/service.py                        [31.4]
backend/app/modules/personal_finance/accounts/schemas.py                        [31.4]
backend/tests/test_seed_transfers.py                                            [nuevo, 31.1]
backend/tests/test_transfers.py                                                 [31.2, 31.5]
backend/tests/test_accounts.py                                                  [31.3, 31.4]
```

### Frontend shared
```
packages/types/src/models/account.ts                                            [31.4: is_unvalued]
packages/types/src/dto/transfer.dto.ts                                          [31.2]
packages/services/src/api/endpoints/transfers.ts                                [31.2]
packages/services/src/query/hooks/useMisclassifiedTransfers.ts                  [nuevo, 31.2]
packages/services/src/query/hooks/useUncategorizedCount.ts                      [nuevo, 31.3]
packages/services/src/query/keys.ts                                             [31.2, 31.3]
```

### Frontend web
```
apps/web/components/transfers/misclassified-section.tsx                         [nuevo, 31.2]
apps/web/components/transactions/uncategorized-banner.tsx                       [nuevo, 31.3]
apps/web/components/analysis/position-hero.tsx                                  [31.4: badge No valorada]
apps/web/components/accounts/balances-card.tsx                                  [31.4]
apps/web/app/(app)/settings/accounts/page.tsx                                   [31.4: nota brokerage/crypto]
apps/web/app/(app)/personal-finance/transfers/page.tsx                          [31.2: monta misclassified]
apps/web/app/(app)/personal-finance/transactions/page.tsx                       [31.3: monta banner]
```

## Endpoints añadidos

- `GET /transfers/misclassified` — txs con dirección dudosa (31.2).
- `POST /transfers/reclassify-bulk` — corrección masiva (31.2).

## Endpoints modificados

- `GET /accounts/balances` — los items pueden venir con
  `is_unvalued=true` y dejan de contribuir al agregado (31.4).
  Backward compatible: el campo es opcional con default false.

## Migraciones

- `o2c36g9b4f0a3_seed_transfer_categories` (31.1) — categoría INCOME +
  backfill idempotente de tx mal categorizadas.

## Verificación global

- [ ] `pytest backend/tests/` verde (incluye los 5 nuevos suites).
- [ ] `pnpm typecheck` verde en los 4 paquetes.
- [ ] `pnpm lint` verde.
- [ ] `pnpm test` web verde.
- [ ] Migración `o2c36g9b4f0a3` aplicada en BD local con datos reales.
      Verificar manualmente que el saldo de la cuenta afectada por el
      bug se autocorrige tras aplicar.
- [ ] Smoke manual: subir un nuevo extracto BBVA con transferencias
      mixtas (entrada+salida). Tras el import, ambas direcciones se
      categorizan correctamente sin intervención.
- [ ] Smoke manual: crear una tx sin categoría en una cuenta. El
      banner aparece. El saldo NO incluye su importe. Categorizar →
      banner desaparece y saldo se actualiza.
- [ ] Smoke manual: crear cuenta brokerage con opening_balance=1000.
      El patrimonio neto en `/analysis` no incluye esos 1000 €. El
      tile en PositionHero muestra badge "No valorada".

## Decisiones tomadas

- **Las reglas genéricas tipo `"TRANSFERENCIA"` se eliminan, no se
  bajan de prioridad**. Eliminar es seguro porque ambas direcciones
  específicas (RECIBIDA / REALIZADA) están cubiertas con reglas
  precisas. Bajarlas de prioridad dejaría un fallback ambiguo que
  podría capturar reglas custom del usuario (caso SCL).
- **El downgrade de la migración NO revierte el recategorizado**.
  Sería destructivo y rompería los saldos del usuario otra vez. Solo
  permite borrar la categoría "Transferencia a favor" si está vacía.
- **`else_=0` en lugar de `else_=Transaction.amount`**. Las tx sin
  categoría son ruido — no se debe asumir signo. Un banner en UI
  educa al usuario a categorizar.
- **Brokerage/crypto fuera del patrimonio neto** pero **visibles en
  la lista de cuentas**. Necesitamos que sigan siendo destino válido
  de transferencias hasta que llegue el módulo de inversión.
- **`_infer_transfer_kind` devuelve `None` en caso ambiguo** en
  lugar de un default arbitrario. El caller decide. Es más
  conservador que adivinar mal.
- **Categoría preexistente con kind explícito gana sobre descripción**
  en la inferencia. Si el usuario ya categorizó manualmente como
  INCOME, no re-inferimos como EXPENSE solo porque la descripción no
  matchee los hints.

## Limitaciones conocidas tras PHASE-31

- El bulk-reclassify (31.2) solo cubre el caso "transferencia
  is_transfer con dirección dudosa". No cubre tx mal categorizadas en
  general (un gasto categorizado como ingreso por error humano). Eso
  es un problema más amplio que requiere otro flujo (PHASE futura:
  herramientas de auditoría del usuario).
- La heurística sigue siendo heurística — extractos en idiomas no
  españoles o de bancos internacionales pueden no matchear. La
  alternativa es un mini-modelo de clasificación (Ollama), fuera de
  scope para 31.5.
- El campo `is_unvalued` se calcula por type. Si en el futuro un
  usuario quiere una cuenta `bank` que tampoco valore, no podrá. Por
  ahora es suficiente — cuando llegue el módulo de inversiones, la
  decisión de qué cuentas valoran y cómo se reformulará.

## Próxima fase

**PHASE-30 — Rediseño módulo deuda en dos capas**. Asume el modelo
de cuentas saneado por PHASE-31. En particular:

- PHASE-30.1 (`categories.role` enum) puede absorber `is_transfer` y
  diseñar `role` con las categorías ya bidireccionales.
- PHASE-30.2 (`/debt/category-summary`) consume `categories.role` y
  los flujos están correctamente signados gracias a 31.1.
- PHASE-30.3 (rediseño `/debt`) puede confiar en que el patrimonio
  neto que aparece en PositionHero es coherente, sin contaminación
  de cuentas no valoradas.

Sin PHASE-31, los KPIs de PHASE-30 partirían de datos sesgados y la
tasa de esfuerzo del usuario reportante saldría con valores
incorrectos (porque sus ingresos por transferencia están como egresos).
