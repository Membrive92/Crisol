# PHASE-47.F — El dinero prestado es dinero

**Estado**: 🚧 pendiente prueba manual y arreglo de datos
**Rama**: `main` (push directo)
**Fecha**: 2026-08-17

## Objetivo

Que el saldo de una cuenta de activo vuelva a coincidir con el que imprime el
banco. Ninguna línea de un extracto puede aportar 0 al saldo de su cuenta.

## El síntoma

El usuario decía haber ahorrado ~1.000 € y la app le enseñaba otra cosa.
Ejecutando `get_balances_for_user` —la función real, no una reimplementación en
SQL— contra su base de datos:

| cuenta | app | extracto (`anchored_statement_balance`) | diferencia |
|---|---|---|---|
| BBVA | 1.077,93 | 1.778,19 | **−700,26** |

Las demás cuentas de activo cuadraban al céntimo.

> El [`backlog.md`](../backlog.md) había documentado este mismo hallazgo **con la
> dirección invertida** («+700,26 € por encima del real»). Aquella entrada salía
> de leer las filas; la corrección, de ejecutar el cálculo.

## La causa

La fila `Operación financiada 4940…` del 07-jul-2026 lleva
`statement_balance = 1.417,36`, y la anterior del extracto tenía 717,10: **el
banco abonó 700,26 € y su propio saldo subió**. No es un apunte neutro, es caja
que entró.

Esa fila es la «pata-activo» de un par de deuda, y `signed_amount_expr` la
fijaba en 0 con este argumento, escrito en su docstring:

> *Ese ingreso es dinero PRESTADO, no ahorro disponible: si contara, inflaría
> `total_assets` […] dejando un «activo fantasma».*

**El argumento estaba invertido.** Caja +X contra deuda +X deja el patrimonio
IGUAL — que es exactamente lo que significa recibir un préstamo. Lo que producía
el carve-out era caja 0 contra deuda +X, o sea neto −X: la app apuntaba la deuda
y escondía el dinero. Un préstamo te empobrecía sobre el papel por el hecho de
recibirlo.

El carve-out se sostenía porque venía acompañado de una SEGUNDA corrección del
mismo hecho: `convert_to_debt_operation` buscaba el «cargo espejo» —una línea del
mismo importe con pinta de liquidación— y lo mandaba a la papelera. Con las dos,
el neto salía 0. Pero en julio el cargo que absorbió (`Recibo mes anterior`,
04-jul) **no tiene `statement_balance`**: venía del extracto de la TARJETA
importado por error en la cuenta del banco. Se anuló un abono real contra un
cargo que en esa cuenta nunca existió.

## Qué se implementó

1. **Fuera el carve-out** (`accounts/repository.py`). `signed_amount_expr` pasa a
   `signed_amount_expr(account)` y los cuatro consumidores pierden el self-join
   que sólo servía para él. El `outerjoin(Category)` se mantiene: sin él sale un
   producto cartesiano ([PHASE-41]).
2. **Fuera su copia** en `get_net_savings_movement_for_account`, que además era
   redundante — las dos patas de un par son `TRANSFER_*` y la rama de
   transferencia interna ya las dejaba en 0.
3. **La tx origen conserva su dirección.** Se le imponía `TRANSFER_IN` fuera cual
   fuera; era inocuo sólo mientras el saldo la anulara después. Sin la anulación,
   imponerla convierte una compra en un abono. Ahora emparejar cambia la
   transfer-ness (sale del cashflow), nunca el sentido.
   Efecto colateral bueno: **convertir a deuda deja de mover el saldo del
   activo**, así que el ancla del extracto deja de caducar sola.
4. **Fuera la absorción del cargo espejo** y `find_mirror_charge` con ella.
   Cuando el espejo es real, borrarlo y anular el abono da EXACTAMENTE el mismo
   número que dejar los dos vivos. Lo único que añadía era una forma de
   equivocarse.
5. **El gate de PHASE-46 se repunta**, no se va. Vivía sobre la constante del
   buscador; ahora ata `CARD_SETTLEMENT_SEQUENCES` a `imports/repository`. Lo que
   protege es que la definición siga siendo una sola, no quién la use.
6. **La financiación entrante mira la DIRECCIÓN, no el signo**
   (`classify_import_flow`). La regla exigía `bank_sign > 0` y el extracto de la
   tarjeta no trae signos, así que no podía dispararse ni cuando la dirección se
   conocía por otra vía: la fila entraba como `IN`, ingreso que nadie cobró. La
   condición sigue existiendo —el mismo producto es gasto real cuando llega la
   cuota (PHASE-38)— pero sobre la dirección ya resuelta.

### Herramientas

- **`scripts/audit_balances_vs_statement.py`** — compara el saldo de cada cuenta
  con `anchored_statement_balance`. Es lo que habría cazado esto el primer día:
  el testigo existe desde PHASE-39 y nadie lo consultaba después de anclarlo.
  Sale con código 1 si alguna cuenta anclada diverge.
- **`scripts/restore_absorbed_mirrors.py`** — devuelve a la vida los espejos que
  SÍ eran del extracto de su cuenta, con `--dry-run` por defecto. El criterio no
  es un juicio: es `statement_balance IS NOT NULL`. Una fila sin saldo no es
  «falsa», es DESCONOCIDA, y se lista para que la decida una persona.

## Cambio de comportamiento declarado

Convertir a deuda una tx que es un **CARGO** deja ahora el patrimonio en −2X
(antes −X). No es un defecto del cálculo: pagar X y deber X por la misma compra
es contradictorio, y la app lo enseña en vez de taparlo. Cuando el banco financia
de verdad, el extracto trae también el abono que lo compensa; para una compra a
plazos, la ruta es dar de alta el pasivo con su capital (PHASE-35), que no crea
pata-activo ninguna. Ninguno de los cuatro pares del usuario es de este tipo:
los cuatro son abonos.

## Archivos clave

- `backend/app/modules/personal_finance/accounts/repository.py` — `signed_amount_expr`
- `backend/app/modules/personal_finance/accounts/position_history.py` — dos consumidores
- `backend/app/modules/personal_finance/transfers/service.py` — `convert_to_debt_operation`, `classify_import_flow`, `is_internal_movement_row`
- `backend/app/modules/personal_finance/transfers/repository.py` — se va `find_mirror_charge`
- `backend/scripts/audit_balances_vs_statement.py`, `backend/scripts/restore_absorbed_mirrors.py`

## Migraciones

Ninguna. `transactions.absorbed_as_mirror` **se queda**: las filas ya absorbidas
que se decida dejar muertas la siguen necesitando para que reimportar el extracto
no las resucite (`find_existing_hashes`).

## Verificación

- [x] BE **1431 tests** · mypy · ruff · black
- [x] FE typecheck · lint · knip · **329 tests**
- [x] Tests nuevos verificados **rompiendo la línea concreta** que protegen, con
      la sonda afirmando que la rotura entró antes de leer el resultado
      ([PHASE-47.E]).
- [ ] Prueba manual del usuario
- [ ] Arreglo de datos (ver abajo)

## Lo que falta: el arreglo de datos

El cambio de código, solo, deja BBVA en **3.057,95 €** (+1.279,76 sobre el
extracto): hay CUATRO pares de deuda y tres tenían su cargo borrado.

Evidencia recogida fila a fila contra la cadena de `statement_balance`:

| pata-activo | ¿abono? | ¿línea real de BBVA? | su «espejo» | ¿real? |
|---|---|---|---|---|
| 06-ene 824,77 | sí (→1.891,67) | **sí** | `Adeudo mensual` 04-ene | **sí** (1.114,37) |
| 24-mar 239,00 | — | **no** | `Taxdown` 22-mar | no |
| 01-jun 215,99 | sí (→1.785,36) | **sí** | 2× `Western union` 26-may | no |
| 07-jul 700,26 | sí (→1.417,36) | **sí** | `Recibo mes anterior` 04-jul | no |

Las cuatro filas «no reales» vienen del extracto de la tarjeta importado en la
cuenta del banco: **el lío de julio venía pasando desde marzo**. Los cinco
espejos están todos en BBVA, así que ninguna otra cuenta corre riesgo.

Orden obligatorio: código → restaurar → re-anclar → y sólo entonces reimportar
el extracto de la tarjeta. Nunca al revés: `re_anchor_from_stored` corre en cada
commit de import y absorbería la diferencia en silencio, borrando la única señal
de diagnóstico disponible.

## Decisiones tomadas

- El diseño no es ninguno de los dos que se plantearon (carve-out condicional /
  quitarlo a secas). El condicional **no arregla julio**: la condición «hubo
  espejo absorbido» se cumple, porque el espejo falso también se absorbió.
- No se desemparejan las cuatro patas: la contrapartida es la señal de que esa
  deuda ya tiene su origen contado (`list_liabilities_awaiting_origination`).

## El golden de 47.A no cubría esto

Al regenerar `golden_47a_debt_domain.json` el diff salió de **9 líneas añadidas
y 1 borrada**, y las 8 útiles son los campos nuevos de 47.G. Ni un número se
movió — pese a que esta fase cambia `signed_amount_expr`, que es justo lo que
ese golden vigila.

La explicación es que su fixture **no tiene ningún par de deuda**: sin una
pata-activo emparejada con un pasivo, el carve-out no se dispara y quitarlo no
puede cambiar nada. O sea que el golden que existe para demostrar que no se
mueve un céntimo estaba ciego precisamente en el camino que esta fase corrige.

No es un defecto del golden —se tomó en 47.A para vigilar un movimiento de
ficheros, y para eso sirve—, pero conviene saberlo: lo que cubre este cambio son
los tests dedicados, no él. Misma familia que [PHASE-44.17]: un gate que nunca
ha fallado no demuestra que el contrato sea estable, puede estar mirando a otro
lado.

## Limitaciones conocidas

- El residuo que quede tras el arreglo vivirá en `opening_balance`, que es un
  tapón: absorbe toda la historia no importada (p. ej. la ventana 30-jun → 05-jul
  de BBVA, que no está en ningún extracto cargado). El saldo de HOY queda
  correcto; los puntos intermedios de la serie de patrimonio, no.
- Sin paridad móvil (no hay UI específica que cambiar; el efecto es de cálculo).
