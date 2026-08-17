# PHASE-47.H — Una devolución no es un ingreso

**Estado**: 🚧 pendiente prueba manual
**Rama**: `main` (push directo)
**Fecha**: 2026-08-17

## Objetivo

Que un reembolso cuente como lo que es —una compra que se deshace— en vez de
como ingreso del mes.

## El síntoma

Julio de 2026 mostraba **2.664,23 € de ingresos** con una nómina de 2.520,68 €.
La diferencia eran las tres devoluciones de Amazon que PHASE-47.G acababa de
corregir de dirección: al pasar a `flow=IN`, entraban en el cubo de ingresos.

El **neto** era correcto (−253,17 €). Lo que mentía era el reparto — y con él la
tasa de ahorro, el runway y el **DTI del módulo de deuda**, que divide por los
ingresos.

## La regla

Una **devolución** es una entrada (`flow=IN`) cuya categoría es de GASTO. Deja
de contar como ingreso y pasa a restar de su propia categoría.

Cada señal responde a lo que sabe, que es la regla que costó nueve lecciones:

- la **dirección** la manda `flow`, probada contra la cadena de saldos del
  extracto (PHASE-47.G);
- la **categoría** sólo responde «¿esto es una categoría de compras?».

Sólo aplica con `flow` explícito: una fila heredada sin flow no tiene dirección
probada, y adivinarla desde la categoría es justo lo que no se hace.

**La propiedad que lo hace seguro: el NETO no se mueve nunca.** 100 de gasto y
30 devueltos dan −70 se cuenten como se cuenten. Verificado contra los datos
reales del usuario en todos los periodos:

| periodo | ingresos | gastos | neto |
|---|---|---|---|
| junio | 2.586,73 → **2.545,38** | 2.131,67 → **2.090,32** | **+455,06** (igual) |
| julio | 2.664,23 → **2.529,68** | 2.917,40 → **2.782,85** | **−253,17** (igual) |

Y el modo de fallo, si algún día una categoría estuviera mal puesta: un ingreso
real pasaría a contar como gasto negativo. Cambia la etiqueta, **nunca el neto
ni el saldo**. Eso es lo que hace aceptable apoyarse aquí en la categoría.

## Qué se implementó

- `_is_refund()` — la definición, en un solo sitio.
- `_is_income()` la excluye; `_is_expense()` la incluye (pertenece al cubo de
  gasto, con signo contrario).
- `expense_amount_expr(amount)` — el importe firmado, aplicado en los **7 sitios
  que SUMAN** bajo el predicado de gasto: 3 en dashboard (resumen ×2 + gasto
  aplazado), el donut, y 4 en analytics (gasto por categoría/mes, estructural vs
  puntual ×2, top categorías).

El helper es explícito y NO vive dentro de `_amount_expr`, que comparten 39
sitios entre ellos los **saldos** y los **presupuestos**. Ahí una devolución es
una entrada normal: firmar allí habría movido el saldo, que es lo único que no
puede cambiar por una cuestión de etiquetas.

### Lo que NO se tocó, por decisión del usuario

**Los presupuestos.** Filtran por `Category.kind == EXPENSE` directamente, sin
pasar por estos predicados (3 sitios en `budgets/repository.py`), así que una
devolución **no libera presupuesto**. Queda como está: *«no los toques porque no
están probados»*.

## Archivos clave

- `backend/app/modules/personal_finance/dashboard/repository.py` — `_is_refund`, `_is_income`, `_is_expense`, `expense_amount_expr`
- `backend/app/modules/personal_finance/analytics/repository.py` — 4 sumas firmadas

## Migraciones

Ninguna.

## Verificación

- [x] Ambas mitades verificadas **rompiendo su línea concreta**: quitar el signo
      del helper, y volver a meter la devolución en los ingresos. Cada sonda
      afirmó que entraba antes de leer el resultado.
- [x] El saldo NO se mueve — con su propio test, que es el guardarraíl del
      diseño.
- [ ] Prueba manual del usuario

**La suite cazó un defecto real de esta fase**, y merece quedar escrito: el
`_is_refund()` original no era NULL-safe. Con categoría NULL, `(flow == IN) AND
(kind == EXPENSE)` da NULL —no `false`— y ese NULL envenenaba el `AND NOT` de
`_is_income()`: toda entrada **sin categoría** dejaba de contar como ingreso.
Cinco tests en rojo, tasa de ahorro `None` y titular del mes en −1.500 € en vez
de +500. El fichero abría diciendo *«los TRES helpers son NULL-safe»* y el
cuarto nació sin serlo. Corregido con `coalesce` y con su propio test de
regresión, verificado quitándolo.

Un test de PHASE-34 afirmaba lo contrario (*«un IN aparcado en categoría de
gasto ES ingreso»*) y su escenario era literalmente este caso. Actualizado con
el matiz: lo que NO cambia es que un OUT en categoría de ingreso sigue siendo
gasto — la dirección la sigue mandando `flow`.

## Limitaciones conocidas

- Una categoría con más devoluciones que compras en un mes daría un total
  **negativo** en el donut. Es aritméticamente correcto, pero un gráfico de
  tarta no sabe pintar un sector negativo. No pasa con los datos actuales
  (238,87 € de devoluciones contra miles de gasto); si llegara a pasar, la
  decisión de presentación está por tomar.
- Los presupuestos siguen ignorando las devoluciones (ver arriba).
