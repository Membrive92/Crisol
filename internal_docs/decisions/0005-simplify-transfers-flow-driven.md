# ADR-0005 — Transferencias dirigidas por `flow`: el emparejado pasa a opcional

**Estado**: en curso — frontend (badge) + T1 (dashboard) implementados; budgets
resuelto por data-fix (Wise = gasto). Pendientes T2–T5 (ver "Estado de implementación")
**Fecha**: 2026-07-13
**Depende de**: [ADR-0004](0004-transaction-level-money-truth.md) (`transactions.flow`
como fuente de verdad del dinero)
**Ámbito**: refactor incremental del módulo `transfers` + carve-out de deuda en
`accounts.repository`. Sin migración destructiva.

## Contexto

Tras ADR-0004, el `flow` (`IN | OUT | TRANSFER_IN | TRANSFER_OUT`) ya es la
fuente de verdad: el saldo y el cashflow se derivan de `flow` + `account.nature`,
no de la categoría. Sin embargo, alrededor de las transferencias sigue viviendo
una capa pesada:

- **`transactions.transfer_pair_id` obligatorio** — cada transferencia interna
  tiene que emparejar sus dos patas.
- **Máquina de emparejado**: endpoints `/transfers/candidates`, `/match`,
  `/link`, síntesis de la contraparte (`from-source`), y el guard **409** al
  editar una pata ya emparejada.
- **3 estados** en el badge de la lista (PHASE-33): *par* (activo↔activo),
  *deuda* (activo↔pasivo), *huérfana* (`is_transfer` sin `transfer_pair_id`).
- **Carve-out H-02** en `signed_amount_expr`: un **self-join** a la pata pareja
  para detectar "pata-activo de un par de deuda que ENTRA → 0" (dinero prestado,
  no ahorro).

### De dónde viene esa complejidad

Casi toda existe para **un solo caso**: cuando el usuario importa **solo una
cuenta**, falta la otra pata de la transferencia y hay que **sintetizarla y
enlazarla** para que el dinero no desaparezca del patrimonio agregado. Los 3
estados y el carve-out distinguen activo↔activo de activo↔pasivo.

### Qué cambió (la precondición nueva)

El usuario **importa ahora TODAS sus cuentas** (banco + tarjetas, tras el
reimport de 2026-07-13, ver PHASE-39). El extracto de cada cuenta ya trae **su**
lado de cada transferencia:

- Cuenta A: `−X TRANSFER_OUT` → baja el saldo de A, neutro al cashflow.
- Cuenta B: `+X TRANSFER_IN` → sube el saldo de B, neutro al cashflow.
- Agregado: `A−X + B+X = 0`. Cashflow: ambas neutras.

**Con todas las cuentas importadas, el emparejado ya no es necesario para la
corrección** de saldo, cashflow ni patrimonio. El `flow` solo hace todo el
trabajo. El `transfer_pair_id` queda como metadato de enlace (útil para mostrar
"estas dos son la misma"), no como requisito de cálculo.

## Decisión

**El `flow` es lo único que gobierna la corrección; el emparejado
(`transfer_pair_id`) pasa a ser metadato OPCIONAL de display.** Los 3 estados
colapsan a 1 ("es transferencia neutra" — o no). La deuda deja de depender del
par: la pata-activo de dinero prestado se marca neutra con un flag por fila, sin
self-join.

### Invariante que sostiene el modelo

> Cada transferencia interna aporta 0 al cashflow y mueve el saldo de SU cuenta;
> si ambas cuentas están importadas, las dos patas se cancelan en el agregado.

El único caso que rompe: una transferencia a/desde una cuenta **no importada**
(el dinero se iría del patrimonio sin contraparte). Se mitiga haciendo el
invariante explícito y **avisando** cuando aparezca una pata sin posible
contraparte (ver T2).

### Qué se conserva vs qué se elimina

| Elemento | Destino |
|---|---|
| `flow` como verdad (ADR-0004) | **Se conserva** (núcleo) |
| Clasificación `classify_import_flow` (detección por signo+texto) | **Se conserva** (sigue habiendo que saber si una línea es transferencia) |
| `transfer_pair_id` como requisito de cálculo | **Se elimina** (pasa a display-only, luego se deprecia) |
| `/candidates`, `/match`, `/link`, síntesis de contraparte | **Se elimina** (o se reduce a cálculo de display, sin persistir) |
| Estado "huérfana / sin pareja" | **Desaparece** (sin par obligatorio, no hay huérfana) |
| Guard 409 al editar una pata | **Se elimina** (no hay par que descuadrar) |
| Carve-out H-02 con self-join | **Se sustituye** por un flag neutro por fila |
| Badge de 3 estados | **Colapsa a 1** |

## Blast radius real (audit 2026-07-14 — corrige el supuesto inicial)

El supuesto "solo el carve-out lee `transfer_pair_id`" era **falso**. El audit
del código encuentra dos naturalezas:

- **Load-bearing (deuda) — riesgo alto:** `signed_amount_expr` (carve-out,
  self-join) en `accounts/repository.py` y `accounts/position_history.py`;
  y `debt_health.py` / `debt_history.py` usan `transfer_pair_id IS NOT NULL`
  para **identificar operaciones financiadas** y su amortización. Desacoplar
  esto (T3) toca patrimonio neto + salud de deuda, no un carve-out aislado.
- **Redundante (belt-and-suspenders) — riesgo bajo:** `dashboard/repository.py`
  y `budgets/repository.py` filtran `transfer_pair_id IS NULL` **además** de
  `_is_internal_transfer()` (que ya excluye por `flow`). El filtro del par es un
  cinturón extra del caso legacy "flow NULL"; sobra una vez `flow` está poblado,
  PERO quitarlo exige confirmar antes que no queda ninguna tx `flow IS NULL AND
  is_transfer = FALSE AND transfer_pair_id IS NOT NULL` (o el filtro dejaría
  pasar una transferencia emparejada sin flow).

Consecuencia: **T1 no es un no-op** y **T3 es más caro/arriesgado** de lo
estimado. El plan se mantiene phased justo por esto — NO hacer "del tirón".

## Plan incremental (sin migración destructiva)

Cada fase deja `main` verde y **no borra datos**: `transfer_pair_id` sobrevive
hasta la última fase, así cada paso es reversible.

- **T1 — `flow` manda, par no obligatorio.** Auditar que ningún cálculo de
  saldo/cashflow/patrimonio dependa de `transfer_pair_id` (solo el carve-out lo
  usa; se aborda en T3). Quitar la obligatoriedad del emparejado en el write
  path e imports. Golden test de equivalencia saldo/cashflow antes↔después.
- **T2 — Vista de transferencias por cálculo.** `/transfers` muestra "posibles
  pares" **calculados** (mismo importe + fechas cercanas + direcciones opuestas
  entre cuentas), sin persistir `transfer_pair_id`. Detectar y **avisar** de
  patas sin contraparte posible (posible cuenta no importada = el único caso que
  rompe el invariante).
- **T3 — Deuda sin par.** Reemplazar el carve-out H-02 (self-join a
  `paired_account.nature == LIABILITY`) por un **marcador por fila** en la
  pata-activo de dinero prestado (contribuye 0 sin join). Es la pieza más
  delicada — golden test específico del patrimonio con operaciones financiadas
  (los 3 pares que enlazamos hoy sirven de fixture real).
- **T4 — Deprecar la máquina de emparejado.** Retirar endpoints de
  `match`/`link`/candidatos y el estado huérfana; badge a 1 estado. Marcar los
  endpoints como deprecated antes de borrarlos (compat de clientes móvil/web).
- **T5 (opcional) — Drop de columna.** Cuando nada lea `transfer_pair_id`,
  migración que la elimina. Solo después de que T1–T4 estén en `main` estables.

## Estado de implementación (2026-07-14)

**Hecho:**

- **Frontend — badge a 1 estado.** `transaction-list.tsx`: `badgeFor` colapsa
  el estado de aviso "Sin pareja" (una transferencia sin emparejar es normal con
  `flow`, no un error). Badges resultantes: *Deuda* (par activo↔pasivo), *Pago de
  deuda* (`role=DEBT_*`), *Transferencia* (resto). El gate del badge usa
  `isTransferFlow(tx.flow)` además del par/categoría, así que una transferencia
  de solo-`flow` (sin par) también se marca. Test actualizado.
- **T1 (dashboard) — filtros de par redundantes retirados.** En
  `dashboard/repository.py`, `list_user_currencies` y `get_totals_by_month`
  tenían `transfer_pair_id IS NULL` **junto a** `_is_internal_transfer() IS FALSE`
  (flow) en la misma query. Retirado el de par (verificado en datos reales: 0
  filas `flow NULL AND transfer_pair_id NOT NULL`). Golden: 76 tests
  dashboard+budgets verdes sin cambios.

**NO tocado (deliberadamente):**

- **`_apply_scope` (helper compartido).** Su `transfer_pair_id IS NULL` es
  load-bearing para `get_top_expenses`, que lo usa **sin** `_exclude_transfer_kind`
  (solo `_is_expense()` + el par). Retirarlo del helper compartido es un cambio
  más amplio → se mantiene.
- **`budgets/repository.py` — sin cambio de código; resuelto por data-fix.**
  Budgets excluye transferencias por `(transfer_pair_id NOT NULL OR is_transfer)`,
  **no por `flow`**. Al auditar el switch a `flow` aparecieron **6 filas**
  (kind=EXPENSE) que divergían — transferencias **Wise / Western Union**
  ("Transferencia realizada Wi…", categoría *SCL*, 30–60 € ene–jun 2026),
  clasificadas `TRANSFER_OUT` sin par: budgets **las contaba como gasto** mientras
  el análisis (flow) **las excluía** → las dos vistas se contradecían.
  **Decisión del usuario (2026-07-14): son gasto real a un tercero externo**
  (sin cuenta contraparte importada = el caso rompe-invariante del ADR, y el
  follow-up #4b Western Union). Data-fix auditado y reversible: `flow`
  `TRANSFER_OUT → OUT` en las 6 filas (ids en el audit). Efecto: cuentan como
  gasto en análisis **y** presupuesto (coherentes); saldo sin cambio
  (`signed_amount_expr` trata `OUT`/`TRANSFER_OUT` igual en un activo; el
  carve-out H-02 solo toca patas `TRANSFER_IN`↔pasivo). Tras el fix, budgets(actual)
  y `_is_internal_transfer()` son **equivalentes** (ambos excluyen 19 filas de
  gasto) → el switch de budgets a `flow` queda como refactor no-op **opcional**
  futuro, no urgente.

## Consecuencias

**A favor:**
- Menos código y menos superficie de bug: sin síntesis de contraparte, sin
  estados intermedios, sin par que mantener, sin self-join en la query de saldo.
- Más robusto: la mayoría de bugs históricos de transferencias (PHASE-23.1/28/32)
  eran de *dirección/emparejado*; con `flow` por fila y sin par obligatorio, esa
  clase de bug desaparece.
- Alineado con ADR-0004: lleva "la verdad vive en la transacción" hasta su
  conclusión (también la transfer-ness, no solo el signo).

**En contra / riesgos:**
- **Depende del invariante "todas las cuentas importadas".** Si el usuario deja
  de importar una cuenta, una transferencia a ella descuadra el patrimonio. T2
  lo detecta y avisa, pero es una regresión respecto a la síntesis actual (que
  inventaba la contraparte). Trade-off consciente: preferimos avisar a mantener
  la maquinaria.
- **Refactor de zona muy curada** (PHASE-23→34). Mitigación: incremental, golden
  tests de equivalencia en cada fase, `transfer_pair_id` no se borra hasta T5.
- **Pérdida del enlace explícito** entre patas. Mitigación: T2 lo reconstruye por
  cálculo para la vista; nadie depende de él para el dinero.

## Alternativas descartadas

- **Volver a categorías `is_transfer`** (modelo pre-ADR-0004): es exactamente lo
  que causó los bugs repetidos; regresión, no simplificación.
- **Mantener el emparejado pero automatizarlo mejor**: sigue siendo la misma
  maquinaria (candidatos, síntesis, estados); no reduce la superficie.

## Notas

- Precondición de negocio: este modelo asume el flujo real del usuario (importa
  todas sus cuentas). Documentarlo en la UI de onboarding/imports.
- El manual "marcar como transferencia" / "convertir en operación financiada"
  puede seguir creando la contraparte como conveniencia, pero el par resultante
  es informativo, no gobierna ningún cálculo.
