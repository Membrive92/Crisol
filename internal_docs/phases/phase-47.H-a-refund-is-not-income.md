# PHASE-47.H — Una devolución no es un ingreso

**Estado**: 🚧 pendiente prueba manual
**Rama**: `main` (push directo)
**Fecha**: 2026-08-17 (backend) / 2026-08-23 (pantalla)

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

| periodo | ingresos                | gastos                  | neto                |
| ------- | ----------------------- | ----------------------- | ------------------- |
| junio   | 2.586,73 → **2.545,38** | 2.131,67 → **2.090,32** | **+455,06** (igual) |
| julio   | 2.664,23 → **2.529,68** | 2.917,40 → **2.782,85** | **−253,17** (igual) |

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
devolución **no libera presupuesto**. Queda como está: _«no los toques porque no
están probados»_.

## La segunda mitad: el signo tenía que llegar a la pantalla

El backend restaba bien desde el primer día. Lo que no salía de él era **cuál**
de las filas restaba: el item del ranking viaja con el importe SIN signo —es el
que ordena— y ningún campo decía su dirección.

Lo vio el usuario en el drill-down de «Suscripciones»: seis movimientos que
suman **187,95 €** presididos por un total de **184,95 €**. Los dos números son
correctos; la diferencia son los 3,00 € de un reembolso de Netflix de 1,50 €
contado una vez de más arriba y una de menos abajo. Nadie puede cuadrar eso
mirando la pantalla, y las dos cifras son igual de plausibles: sólo se
contradicen si las miras juntas, que es exactamente lo que ninguna herramienta
hace.

- `TopExpenseItem` publica `flow` en los dos endpoints que lo emiten
  (`/dashboard/category/{id}` y `/dashboard/top-expenses`, que devuelve el cubo
  de gasto entero y por tanto también incluye devoluciones), y **`TxRef` de
  analytics** en el tercero (`/analytics/expense-structure`, cuyo
  `top_exceptional` sale del MISMO `_is_expense()`).
- `packages/ui/src/refund-sign.ts` es el gemelo de `expense_amount_expr` para la
  UI, compartido por las tres listas (web + móvil). Niega el importe
  **manipulando la cadena**, no parseando a `number`: la columna tiene que sumar
  el total al céntimo.
- El tipo declara `flow` **opcional**. Un backend en marcha anterior al campo no
  lo manda, y el tipo describe lo que puede llegar, no lo que emite el servidor
  de hoy ([PHASE-44.16]). Por eso la comprobación es por VERDAD y no contra
  `null`: `undefined !== null` habría marcado TODAS las filas ([PHASE-47.E]).
- La fila lo dice además con palabras («Devolución») y color. Un signo menos
  solo es demasiado fácil de leer como un error de la app.

### El tercer emisor, que sólo apareció en la revisión

La primera versión de esta entrega arregló dos endpoints y tres listas, y lo
escribió así. Faltaba uno: `top_exceptional_transactions` de analytics filtra
por el **mismo** `_is_expense()` —importado literalmente de dashboard— y
alimenta «Top movimientos del periodo» de Análisis, que pintaba el importe
crudo. O sea, el defecto exacto que esta fase cierra, en la tarjeta de al lado,
y contradiciendo al desglose de **la misma pantalla**, que sí resta.

Con los datos reales no se ve hoy, y por poco: ejecutando el servicio contra la
base, en el período 12-jun a 12-jul el corte del top-5 está en **43,58 €** y la
devolución de Amazon de ese período es de **41,35 €**. Dos euros.

Lo encontraron dos lentes independientes de la revisión adversarial. Ninguna
herramienta podía: el gate de esta misma entrega no lo miraba (ese componente
usa `AnalyticsTxRef`, no `TopExpenseItem`) y el tipo compilaba.

El invariante que defienden los tests no es «pinta un menos»: es que **la
columna suma el total que preside la pantalla**. Hay tres redes —el test del
helper con los importes reales de julio, el del backend que afirma que la suma
firmada de `top_transactions` es igual a `total`, y un gate de cableado que
recorre las dos apps y falla si una lista vuelve a formatear el importe crudo—.
La tercera existe porque este riesgo **no es de tipos**: `formatAmount(tx.amount)`
compila hoy y compilará siempre.

### El gate, segunda versión

La primera comprobaba la PRESENCIA de `categoryRowAmount(` en el fichero. La
revisión escribió cuatro formas normales de reintroducir el defecto, **las
ejecutó**, y el gate dio verde en las cuatro: una lista nueva cuyo tipo se
infiere del hook (no contiene el literal `TopExpenseItem[]`), una segunda tabla
en la misma página (el fichero conserva la llamada de la primera), la tabla
extraída a un componente que pierde el kind por el camino, y un callback con la
variable llamada `row` en vez de `tx`.

Ahora comprueba por **sitio de llamada** —ningún `formatAmount` recibe un
`<lo que sea>.amount` ni una variable que venga de uno— y la selección de
ficheros es ancha (cinco señales, incluido el nombre del hook, porque el día
que web pinte su «Top gastos» el tipo se infiere y no aparece ningún literal).
Quien fija el kind a mano tiene que estar en una lista con su motivo escrito,
como las exclusiones de `knip.config.ts`. Las cinco esquivas, reproducidas una
a una, tumban el gate.

## Archivos clave

- `backend/app/modules/personal_finance/dashboard/repository.py` — `_is_refund`, `_is_income`, `_is_expense`, `expense_amount_expr`
- `backend/app/modules/personal_finance/analytics/repository.py` — 4 sumas firmadas
- `backend/app/modules/personal_finance/dashboard/schemas.py` — `TopExpenseItem.flow`
- `packages/ui/src/refund-sign.ts` — el signo en la UI, para las tres listas
- `apps/web/app/refund-sign-wiring.test.ts` — el gate de cableado (las dos apps)

## Migraciones

Ninguna.

## Verificación

- [x] Ambas mitades verificadas **rompiendo su línea concreta**: quitar el signo
      del helper, y volver a meter la devolución en los ingresos. Cada sonda
      afirmó que entraba antes de leer el resultado.
- [x] El saldo NO se mueve — con su propio test, que es el guardarraíl del
      diseño.
- [x] El signo de la pantalla, verificado rompiendo **las cuatro** listas por
      separado, más las **cinco esquivas** que encontró la revisión: cada una
      tumba el gate, y cada sonda afirmó que entraba antes de leer el resultado
      —una no aplicaba tras un reformateo de prettier y habría dado un verde
      falso—. Igual con los tres sitios del backend que publican `flow`: romper
      cada uno tumba exactamente su test, no el de los otros.
- [x] Revisión adversarial: **4/4 lentes vivas**, 26 hallazgos brutos, 8
      confirmados tras refutación. Los 8 arreglados. Que las cuatro lentes
      trajeran resultado se reporta a propósito: un resultado vacío por lentes
      muertas es indistinguible de una revisión limpia.
- [ ] Prueba manual del usuario

**La suite cazó un defecto real de esta fase**, y merece quedar escrito: el
`_is_refund()` original no era NULL-safe. Con categoría NULL, `(flow == IN) AND
(kind == EXPENSE)` da NULL —no `false`— y ese NULL envenenaba el `AND NOT` de
`_is_income()`: toda entrada **sin categoría** dejaba de contar como ingreso.
Cinco tests en rojo, tasa de ahorro `None` y titular del mes en −1.500 € en vez
de +500. El fichero abría diciendo _«los TRES helpers son NULL-safe»_ y el
cuarto nació sin serlo. Corregido con `coalesce` y con su propio test de
regresión, verificado quitándolo.

Un test de PHASE-34 afirmaba lo contrario (_«un IN aparcado en categoría de
gasto ES ingreso»_) y su escenario era literalmente este caso. Actualizado con
el matiz: lo que NO cambia es que un OUT en categoría de ingreso sigue siendo
gasto — la dirección la sigue mandando `flow`.

## Limitaciones conocidas

- Una categoría con más devoluciones que compras en un mes daría un total
  **negativo** en el donut. Es aritméticamente correcto, pero un gráfico de
  tarta no sabe pintar un sector negativo. No pasa con los datos actuales
  (238,87 € de devoluciones contra miles de gasto); si llegara a pasar, la
  decisión de presentación está por tomar.
- Los presupuestos siguen ignorando las devoluciones (ver arriba).
