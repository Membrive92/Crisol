# El recibo aplazado: el gasto existe, pero no ha salido

**Estado**: 📋 diseño — listo para acordar alcance
**Fecha**: 2026-08-15
**Versión**: v2. **Sustituye íntegramente a la v1 de este fichero**, que partía de
una premisa equivocada (ver §9).
**Origen**: el usuario, sobre su propio julio — *«al financiar este recibo lo
estoy agregando a deuda pero no restando»* — y, sobre el modelo que le propuse:
*«esto son finanzas personales, no empresariales; hay que pensar desde un punto
de vista doméstico»*.
**Todos los datos están medidos** contra su base de datos, no supuestos.

---

## 1. El objetivo, en una línea

> Lo que entra menos lo que sale. Eso es lo que pintan las gráficas.

Todo lo demás es fontanería para que esa resta salga bien importando **dos
extractos del mismo dinero**: el de la cuenta y el de la tarjeta.

---

## 2. El problema base, y por qué hoy funciona

Cada euro gastado con tarjeta aparece dos veces:

```
extracto tarjeta    21,41  Mercadona            ← la compra, con su categoría
extracto banco     990,02  Adeudo de tarjeta    ← el pago de ésa y de otras 16
```

La app ya lo resuelve, y **la decisión es buena**: la compra es el gasto (tiene
categoría, es en lo que te lo gastaste) y el recibo es **fontanería** —
`TRANSFER_OUT`, mueve dinero pero no es gasto nuevo.

El precio es un desfase de ~30 días: cuentas el gasto al comprar y el dinero sale
al mes siguiente. **Mientras el recibo se pague, la aproximación es buena** y
nadie la nota.

---

## 3. Lo que rompe la financiación

El mes que BBVA no cobra el recibo sino que lo **aplaza**, la anticipación se
queda sin cumplir y nadie la deshace:

```
700,26 €   compras del ciclo, contadas como gasto cuando se hicieron
     0 €   de la cuenta no salió nada: el recibo se financió
957,60 €   y ahora saldrán 26,60 €/mes durante 36 meses, que también son gasto
──────────
contado 1.657,86 €  ·  salido de verdad 957,60 €  ·  sobran 700,26 €
```

Sobran exactamente el recibo. Ésa es la «doble salida».

**Y es puntual**: en siete meses ha pasado dos veces (dic-25 y jun-26). Los otros
cinco el recibo se cobró y no hay nada que hacer. Así que no hay que rediseñar
cómo se cuenta el gasto — sólo hay que saber qué pasa el mes que la anticipación
no se cumple.

---

## 4. La decisión

**Cuando un recibo se aplaza, las compras de ese ciclo quedan marcadas.** Y de esa
marca se deriva todo, sin inventar ningún apunte:

| | ¿Aparecen las compras del ciclo aplazado? |
|---|---|
| **Resultado mensual** (¿he ahorrado?) | **No.** No han salido de la cuenta. |
| **Gasto por categorías** | **Sí, con su marca.** El gasto existe; lo único que está es aplazado. |
| **Las cuotas** | Cuentan cuando salen, íntegras — como la del préstamo. |

En palabras del usuario: *«no aparecen porque se han aplazado, pero se cuentan en
categorías porque el gasto existe, lo único que está es aplazado»*.

**No se inventa una fila de descuento.** La v1 proponía un apunte negativo en el
mes de la financiación; se descarta porque **ese apunte no existe en el extracto**
y la app no debe fabricar movimientos que el banco no hizo.

### Las tres reglas

1. **Financiar no es ingresar.** El abono no suma a lo que entra: nace una deuda.
   (Ya resuelto en [PHASE-46](../phases/phase-46-financing-is-not-income.md).)
2. **Las compras de un ciclo aplazado no son salida de caja** — pero siguen
   siendo gasto con su categoría, marcadas como aplazadas.
3. **Lo que sale después sí es salida de caja.** Las cuotas, íntegras.

---

## 5. Con sus números

Ciclo de junio: 17 compras, 700,26 €. Aplazado a 36 meses, cuota 26,60 € (14,00
de capital + 12,60 de interés). Total a devolver 957,60 €.

| | Resultado mensual | Gasto por categorías |
|---|---|---|
| **Junio** | +700,26 € de ahorro respecto a hoy (no salieron) | 700,26 € repartidos en supermercado, suscripciones, ocio… **con asterisco** |
| **Julio** | sin cambios | sin cambios |
| **Ago-2026 → jul-2029** | −26,60 €/mes | 26,60 €/mes como «financiación tarjeta jun-26» |

Suma sobre la vida del aplazamiento: **957,60 € de salida de caja**, que es
exactamente lo que sale. Y el desglose de junio **intacto**.

### El asterisco

Sobre las compras del **ciclo**, no del mes natural — el recibo de julio liquida
de ~28/05 a ~25/06. Los ciclos son identificables: medidos contra sus datos,
**cierran al céntimo** (§8).

> *Forma parte del recibo de junio (700,26 €), que aplazaste a 36 meses. Lo estás
> pagando desde agosto de 2026: 26,60 €/mes hasta julio de 2029.*

Y en las dos direcciones: desde la cuota, «estás pagando el recibo de junio → ver
las 17 compras».

### Qué NO se hace

**No se reparte cada cuota entre las categorías del ciclo.** Se podría —10,64 € de
supermercado, 4,20 € de ocio…— pero mancharía tres años de gráficas con migajas
de una compra de 2026. La cuota se traza a un nivel más alto: *«el aplazamiento
de junio»*, que es una cosa real que estás pagando, con su detalle detrás.

### Y una consecuencia que la UI tiene que asumir

A partir de aquí, **el resultado mensual y la suma del desglose por categorías
dejan de coincidir** los meses con aplazamiento. Es deliberado, pero si alguien
intenta cuadrarlos a mano y no puede, la app está mintiendo por omisión. El
desglose tiene que decir la diferencia en voz alta:

> Gasto de junio: 1.624,40 € · **de los cuales 700,26 € aplazados** (no salieron
> de tu cuenta este mes).

---

## 6. El otro «doble pago», que hay que arreglar igual

Independiente de todo lo anterior, y es trabajo manual del usuario **cada mes**:

| Mes | Importe | Se borra a mano | Sobrevive |
|---|---|---|---|
| dic-25 | 824,77 | `RECIBO MES ANTERIOR` | `Adeudo mensual de tarjeta` |
| feb | 264,84 | `Recibo mes anterior` | `Adeudo mensual de tarjeta` |
| mar | 4.062,80 | `Recibo mes anterior` | `Adeudo mensual de tarjeta` |
| abr | 577,16 | `Recibo mes anterior` | `Adeudo mensual de tarjeta` |
| may | 1.278,34 | `Recibo mes anterior` | `Adeudo mensual de tarjeta` |
| jun | 990,02 | `Recibo mes anterior` | `Adeudo mensual de tarjeta` |

**Siete meses, siete borrados.** Son el mismo hecho escrito de dos formas —una
del extracto de la tarjeta, otra del banco—, mismo importe y mismo día. El dedup
no las ve porque compara la descripción.

Mientras el recibo se paga da igual cuál se borre. **El mes que se aplaza, no**:
una de las dos es el abono que crea la deuda y la otra es la que salda la
tarjeta. Julio se quedó irreal por un borrado que las otras siete veces era
correcto, y nada avisó.

La app tiene que reconocer el par en vez de dejárselo al usuario.

---

## 7. Qué se construye

### E1 · Reconocer el par duplicado — HECHO (2026-08-15)

Dos filas del mismo importe, misma cuenta, ventana corta, una con forma de
liquidación → **un hecho, no dos**. Se conserva una y la otra se marca con la
maquinaria que ya existe (`absorbed_as_mirror`), no con un borrado.

Retira siete borrados manuales al año y es lo que el usuario nota antes.

### E2 · El aplazamiento como hecho — HECHO (2026-08-15)

`transactions.deferred_by_account_id` → el pasivo que aplazó ese gasto. Una
columna lo lleva todo: la exclusión del resultado mensual, la marca y el enlace
en las dos direcciones.

**`refinanced_account_id` no hizo falta.** El plan lo pedía para registrar qué
saldó el pasivo al nacer, pero E4 ya había dejado esa relación puesta:
`parent_account_id` dice de qué tarjeta cuelga, y la marca en cada compra dice
qué cubrió. Una tercera columna habría afirmado lo mismo por tercera vez, que
es como empiezan a divergir (PHASE-46).

**Tampoco hace falta emitir la liquidación** que baja la tarjeta: el extracto
de la propia tarjeta ya trae su `Recibo mes anterior`, así que su saldo baja
solo al importarlo. Inventar el apunte habría duplicado uno que existe.

El ciclo se **deriva**: las últimas compras que suman EXACTO el recibo, hacia
atrás desde el cierre. Y si no cuadra al céntimo, **no se marca nada** y se
dice por qué — es el caso del recibo de 990,02 € de junio, al que le faltan
compras de mayo. Elegir «las que más se acerquen» repartiría el gasto entre
categorías que no son las suyas y el usuario no tendría forma de saberlo.

### E3 · Las dos lecturas — HECHO (2026-08-15)

- **Resultado mensual** (`get_summary_aggregates`, `get_totals_by_kind` y las
  dos series mensuales): excluye las marcadas. Mide caja.
- **Categorías** (`get_breakdown_by_category` y el drill-down): las mantiene.
  Mide gasto.
- `summary.deferred_expenses` publica la diferencia, y la pantalla la dice.
  Sin ese número las dos cifras no cuadran y no hay forma de saber por qué.

Ambas salen de la misma columna. No hay dos contabilidades: hay una marca.

### E4 · El bug que existe hoy — HECHO (2026-08-15)

[`debt/reconciliation.py`](../../backend/app/modules/personal_finance/debt/reconciliation.py)
repartía el cargo agregado de cuotas **sólo entre tarjetas**
(`a.type == AccountType.CREDIT_CARD`). `Compra finaciada recibo junio` es de
tipo `LOAN` —es lo que el banco vende— así que nunca entraba y su cuota no se
atribuía jamás.

**La solución que este documento proponía era insegura**, y leer el código lo
destapó: abrir el pool a `settlement_account_id == tx.account_id` habría metido
también al préstamo personal, que se cobra de la misma cuenta pero tiene su
PROPIA línea («Cargo por amortizacion…»). Habría avanzado **dos cuotas al mes**
en silencio.

Lo que de verdad separa a los dos es **de qué tarjeta cuelga cada uno**
(`parent_account_id`, PHASE-35): el banco cobra dentro de la línea agregada
exactamente lo que se financió en esa tarjeta. Una hija cuenta sea cual sea su
`type`.

El arreglo tiene **dos mitades simétricas**, y la segunda salió de un test que
falló:

1. El pool del cargo agregado = con cuadro **y** (`credit_card` **o** cuelga de
   una tarjeta).
2. El pool de la línea de préstamo **excluye** lo que cuelga de una tarjeta.
   Sin esto, dos pasivos de tipo `LOAN` hacen que `_resolve_target` declare
   ambiguo el cargo de amortización y **el préstamo de verdad deja de
   amortizar** — un fallo silencioso que aparece justo cuando el usuario modela
   bien su deuda. Hoy no se ve sólo porque el recibo aplazado está archivado.

Y hacía falta una tercera pieza para que fuera usable: `parent_account_id` sólo
se podía declarar **al crear**, así que una deuda ya dada de alta suelta —el
caso real— no tenía arreglo. Ahora se puede declarar y retirar después, con la
validación extraída a una fuente única (`_validate_parent_card`) usada por los
dos caminos, y relajada en un punto: una hija ya no tiene que ser
`credit_card`.

---

## 8. Lo que ya está verificado

**Los ciclos cierran al céntimo.** Para cada recibo, existe un tramo contiguo de
compras que suma exactamente su importe:

```
recibo 04/02   264,84  ← 13 compras del 01/01 al 25/01
recibo 04/03 4.062,80  ←  8 compras del 03/02 al 22/02
recibo 01/04   577,16  ← 13 compras del 25/02 al 25/03
recibo 04/05 1.278,34  ← 10 compras del 03/04 al 27/04
```

El ciclo cierra sobre el día 25-27 y se cobra el 1-4 del mes siguiente. Eso es
justo el «desfase de corte» que [PHASE-47 §9](phase-47-implementation-plan.md)
daba por no modelado: **es derivable de los datos**.

**Dos no cierran, y por motivos distintos:**

- 43,93 y 166,00 del 07/01 liquidan el ciclo de diciembre, fuera de la ventana de
  datos (empiezan el 2026-01-01). Esperado.
- **990,02 del 04/06 no cuadra con ningún tramo.** Faltan compras en mayo. Es la
  misma familia que julio y **no se había detectado hasta ahora**. Conviene
  mirarlo antes de construir nada que dependa del ciclo.

---

## 9. Lo que se cae de la v1

La v1 daba por supuesto que **el gasto se cuenta cuando compras** y, por tanto,
que las cuotas de un aplazamiento sólo aportan su interés. El usuario lo rechazó:

> *«Si cuento sólo el interés como gasto falseo mi track financiero: si yo he
> aplazado un gasto, no sólo el interés es gasto.»*
>
> *«El objetivo del módulo es trazar los flujos de caja. La cuota íntegra es un
> gasto porque sale de la caja. Esto son finanzas personales, no empresariales.»*

Con eso desaparece toda la maquinaria de la v1:

- `principal_already_counted` y las banderas de origen del capital,
- la descomposición del cargo agregado contra los cuadros,
- el offset por capital y el residuo,
- las tres preguntas sobre de dónde salió el capital de cada deuda.

Nada de eso hace falta: **lo que sale es gasto**, y lo que se aplazó no sale.
La única excepción es puntual y está marcada.

De la v1 sobrevive un hallazgo: la app enseña una frase falsa en el panel de
amortización ([`transfers/service.py:917`](../../backend/app/modules/personal_finance/transfers/service.py#L917)),
que afirma que el capital de una deuda con cuadro «no se contó como gasto en
ningún sitio». Para un recibo aplazado es al revés.

---

## 10. Los agujeros, en voz alta

- **Un ciclo que no cierra** (el de 990,02) deja el aplazamiento sin poder marcar
  sus compras con exactitud. Hace falta decidir qué se hace: proponer el tramo
  más probable y que el usuario ajuste, o no marcar nada y avisar.
- **La ventana de datos.** `Compra financiada` (824,77 €) es el recibo de
  diciembre aplazado, pero diciembre está fuera de los datos: sus compras no
  existen, así que no hay nada que marcar. Sus cuotas cuentan como salida, que es
  correcto, pero el asterisco no tiene a qué apuntar.
- **El resultado mensual y el desglose dejan de coincidir** los meses con
  aplazamiento (§5).
- **Julio sigue sin reimportar**: el extracto de la tarjeta está en la cuenta del
  banco, así que el ciclo de junio no tiene compras que marcar. No bloquea el
  diseño —el usuario lo da por trámite— pero sí bloquea comprobar el resultado
  sobre sus datos reales.
- **25 cuotas** con `paid_transaction_id` apuntando a transacciones borradas.
- **Presupuestos queda fuera** por decisión del usuario: *«aún no es usable, se
  hizo pero ni se probó»*.

---

## 11. Decisiones tomadas (2026-08-15)

**1 · Un ciclo que no cierra se trata como un problema de DATOS, no de marcado.**
La app dice qué falta —«el recibo son 990,02 € y sólo encuentro 760,54 €;
probablemente falte parte del extracto»— y ofrece marcar el tramo por fecha de
todas formas, **con el descuadre a la vista**. El usuario decide si completa los
datos o tira adelante. Nunca marca a ciegas: excluir del resultado mensual una
compra que sí se pagó sería un error silencioso, y silencioso es el modo de fallo
que costó julio.

**2 · La marca se PERSISTE**, en una columna de `transactions` que apunta al
pasivo que la aplazó. Es una **declaración**, no un cálculo: el usuario aceptó
ese marcado. Derivarla al vuelo la haría depender de una coincidencia de importes,
y entonces reimportar o que aparezca una compra tarde movería el resultado de un
mes ya cerrado **sin que nadie lo pida** — exactamente lo que [PHASE-34] prohíbe.
Persistida es además auditable (se puede ver por qué un mes excluyó 700,26 €),
reversible y editable. Cuesta una migración aditiva.

**3 · Orden: E4 → E1 → E2+E3.** Primero el bug, que es pequeño y aislado. Luego
el reconocimiento del par, que quita un borrado manual al mes **y protege el dato
que E2 necesita**: en julio, la fila que había que conservar era justo una de las
que el usuario borra por costumbre. Y al final el modelo del aplazamiento.

---

## 12. Encaje

- **E4** cabe en 47.A o justo después.
- **E1** encaja en la bandeja de [47.B](phase-47-implementation-plan.md): es un
  item más de la cascada.
- **E2 + E3** son fase propia. No dependen de
  [PHASE-48](phase-48-debt-early-settlement.md) ni la bloquean.
