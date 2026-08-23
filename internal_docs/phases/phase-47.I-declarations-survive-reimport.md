# PHASE-47.I — Una declaración manual sobrevive a una reimportación

**Estado**: 🚧 pendiente prueba manual
**Rama**: trabajo directo sobre `main` (sin PR, como el resto del proyecto)
**Fecha**: 2026-08-21

## Objetivo

Que reimportar un extracto deje de revertir, en silencio, decisiones que el
usuario tomó a mano. Y que el cargo agregado de una tarjeta sepa **de qué
tarjeta** viene, para que el sistema soporte todas las que el usuario quiera.

## El problema, medido

El 2026-08-18 el usuario reimportó julio (un fichero nuevo con los días 1-5 que
faltaban). La reimportación borró las filas viejas y creó otras, y con las
viejas se fueron sus declaraciones: los cuatro `Adeudo mensual` que había
declarado GASTO —1.099,64 € de liquidaciones anticipadas— renacieron neutros.
**El resultado de julio pasó de −253,17 a +398,87 € sin que nadie lo
decidiera.**

Lo que sobrevivía: las cuotas pagadas del cuadro (viven en
`liability_installments`, no en las filas) y las marcas de aplazamiento. Lo que
no: toda declaración a nivel de fila.

## Qué se implementó

### `transactions.flow_declared_at` — la firma que faltaba

El `import_hash` de la fila reimportada es **idéntico** al de la borrada (se
compone de usuario + importe + fecha + descripción), así que la anterior es
localizable en la papelera. Lo que no era localizable es **qué de ella era
decisión y qué conjetura del clasificador**: las dos viven en `flow` y ninguna
iba firmada.

`flow_declared_at` es esa firma. `NULL` = lo puso el sistema; con valor, lo
declaró el usuario y ese día. La escribe `update_transaction` cuando el cliente
manda `flow` explícito, y el panel «Es una amortización» (PHASE-45); la BORRA la
re-derivación desde la categoría, porque si la dirección vuelve a salir de la
categoría ya no consta declaración sobre ella.

### La reposición, y su gate

`find_declarations_in_trash` busca por `import_hash` las filas borradas que
declaren algo y repone sobre la fila nueva: el `flow` **sólo si va firmado**,
más `amortization_source_id` y `deferred_by_account_id` (ésos el import no los
escribe nunca, así que son declaración pura). El resumen del import lo dice en
voz alta: una reposición silenciosa sería tan difícil de auditar como la
pérdida que arregla.

### El bloqueante que casi lo tumba

El `import_hash` se calculaba sobre `occurred_at.isoformat()`. Al pasar el
parser a tz-aware (PHASE-47.J), el sufijo `+00:00` habría cambiado **todos** los
hashes persistidos: reimportar duplicaría todo, la reposición no encontraría
nada y el guardarraíl de fichero-en-cuenta-equivocada quedaría ciego.

Se resolvió serializando la fecha **sin el sufijo de zona**, que reproduce byte
a byte lo que producía el naive — verificado recomputando el hash de tres filas
reales de la BD. Cero hashes que recalcular.

### El cargo agregado sabe de qué tarjeta es

Desde PHASE-36 el cargo pagaba «la siguiente cuota pendiente de CADA tarjeta con
cuadro». Con una tarjeta es correcto; con dos es un doble descuento silencioso.

`_plans_of_charge` acota el reparto con una cascada de señales que **ya
existían**: una sola tarjeta con plan → esa; `settlement_account_id` (creada en
PHASE-47.A precisamente para esto, y que la reconciliación nunca leía); vínculo
por categoría. Si tras las tres siguen habiendo varias candidatas, **no marca
ninguna cuota** y el motivo llega a `skipped_payments`: no repartir es
recuperable, repartir a todas escribe cuotas pagadas que nadie pagó.

## Archivos clave

- `backend/app/modules/personal_finance/transactions/models.py` — la columna.
- `backend/app/modules/personal_finance/imports/repository.py` —
  `find_declarations_in_trash`.
- `backend/app/modules/personal_finance/imports/service.py` — la reposición y el
  hash estabilizado.
- `backend/app/modules/personal_finance/debt/reconciliation.py` —
  `_plans_of_charge`.

## Migraciones

- `m9i62h4d7e5g18_add_flow_declared_at_to_transactions.py` — aditiva y
  reversible, sin backfill.

## Limitaciones conocidas

- **Sin backfill, y tiene consecuencia**: las declaraciones anteriores a la
  migración no llevan firma, así que una reimportación todavía se las llevaría.
  Deducirlas comparando con el clasificador de hoy es justo la conjetura que la
  columna existe para evitar.
- Un plan sólo declara de qué tarjeta cuelga desde PHASE-35
  (`parent_account_id`). Los que no lo declaran comparten un único grupo y se
  reparten entre sí, que es el comportamiento previo.

## Verificación

- BE 1478 tests · mypy · ruff · black · `alembic upgrade/downgrade` reversibles.
- Los cuatro tests nuevos **verificados rompiendo el código**. Uno de ellos no
  probaba nada en su primera versión (el flow de la papelera y el del
  clasificador coincidían, así que heredar a ciegas daba el mismo verde);
  reescrito con un escenario que sí distingue.
