# PHASE-47.E — El recibo aplazado: el gasto existe, pero no ha salido

**Estado**: 🚧 pendiente prueba manual
**Rama**: `main` (push directo)
**Fecha**: 2026-08-15 · **E4 (el aviso dice DÓNDE)**: 2026-08-23
**Diseño**: [`improvements/card-receipt-financing-model.md`](../improvements/card-receipt-financing-model.md)
**Entregas**: E1 · E2 · E3 · E4 (la letra viene del diseño, que las numera así;
no va después de 47.C — es un frente aparte que surgió a mitad de fase cuando
el usuario destapó el descuadre real)
**ADR**: [`0011-system-initiated-debt-event-translation.md`](../decisions/0011-system-initiated-debt-event-translation.md)

## Objetivo

Que financiar el recibo de una tarjeta deje de descuadrar la app, sin dejar de
trazar el gasto. El usuario lo dijo en una frase: _«no aparecen porque se han
aplazado, pero se cuentan en categorías porque el gasto existe, lo único que
está aplazado»_.

## El problema, con sus números

El usuario importa el extracto de la tarjeta para controlar en qué gasta, así
que las 17 compras de junio de 2026 ya están contadas una a una, con su
categoría. Cuando BBVA financió el recibo de esas compras (700,26 €), la app
sumó una deuda **sin restar nada**: el gasto seguía contado y encima nacía un
pasivo. De ahí el descuadre.

## La decisión

Tres reglas, en lenguaje de caja doméstica (no contable de empresa — decisión
explícita del usuario: _«el objetivo del módulo es trazar los flujos de caja»_):

1. **Financiar no es ingresar** — ya resuelto en [PHASE-46](phase-46-financing-is-not-income.md).
2. **Las compras de un ciclo aplazado no son salida de caja**, pero siguen
   siendo gasto con su categoría, marcadas.
3. **Lo que sale después sí es salida de caja**: las cuotas, íntegras.

Suma sobre la vida del aplazamiento: 957,60 € de salida, que es exactamente lo
que sale. Y el desglose de junio intacto.

## Qué se implementó

### E4 · El cargo agregado alcanza al recibo aplazado

El banco cobra en UNA línea las cuotas de todo lo financiado en la tarjeta. La
reconciliación repartía ese cargo sólo entre cuentas de tipo `credit_card`, así
que un recibo aplazado —que se da de alta como préstamo, porque es lo que el
banco vende— nunca entraba y su cuota no se atribuía jamás.

Lo que separa a los pasivos que cobran ahí de los que no es **de qué tarjeta
cuelga cada uno** (`parent_account_id`), no su tipo. Dos mitades simétricas:

- el pool del cargo agregado admite lo que cuelga de una tarjeta;
- el pool de la línea de préstamo **excluye** lo que cuelga de una tarjeta.

La segunda salió de un test que falló, y es la importante: con dos pasivos de
tipo `LOAN`, `_resolve_target` declara ambiguo el cargo de amortización y **el
préstamo de verdad deja de amortizar**. Hoy no se ve sólo porque el recibo
aplazado está archivado.

Además, `parent_account_id` pasa a poder declararse al **editar** (antes sólo
al crear, así que una deuda ya dada de alta suelta no tenía arreglo), con la
validación extraída a una fuente única y relajada en un punto: una hija ya no
tiene que ser de tipo tarjeta.

### E1 · Un recibo escrito de varias formas es UN cobro

BBVA escribe el recibo con dos redacciones (`Adeudo mensual de tarjeta 4940…` y
`Recibo mes anterior`) y las fecha distinto. Medido en la BD del usuario, sobre
siete ciclos: **entre 2 y 4 filas por ciclo** para un único cobro, con hasta
**5 días** de desfase. Las venía borrando a mano, unas veinte en siete meses.

El `import_hash` no puede hacer este trabajo: se calcula sobre fecha, importe y
texto, que es justo lo que difiere entre las copias.

Regla: dos liquidaciones del **mismo importe exacto** en la misma cuenta dentro
de **7 días** son el mismo hecho. Sobrevive la copia que más dice (la que el
clasificador entendió, la que resolvió categoría, la que trae el número de
tarjeta), con desempate total para que no dependa del orden del fichero.

Lo que **no** colapsa, y es lo que decide si la regla se puede tener: el abono
que financia el recibo y el cargo que lo salda son también un par del mismo
importe y el mismo día. Sólo uno de los dos es una liquidación.

### E2 · El aplazamiento como hecho

`transactions.deferred_by_account_id` → el pasivo que aplazó ese gasto. El
ciclo se **deriva**: las últimas compras que suman EXACTO el recibo, hacia
atrás desde el cierre. Cierre al céntimo o nada.

El plan pedía además `accounts.refinanced_account_id` y emitir la liquidación
que baja la tarjeta. Ninguna de las dos hizo falta: `parent_account_id` (E4) ya
dice de qué tarjeta cuelga, y el extracto de la propia tarjeta ya trae su
`Recibo mes anterior`, así que su saldo baja al importarlo. Inventar el apunte
habría duplicado uno que existe.

### E3 · Las dos lecturas y su marca

- **Resultado mensual** (¿he ahorrado?): excluye las marcadas. Mide caja.
- **Categorías** (¿en qué gasté?): las mantiene. Mide gasto.
- `summary.deferred_expenses` publica la diferencia y el desglose la dice.
- Cada compra aplazada lleva su **asterisco** en la lista de transacciones, con
  el hover explicando que el gasto sigue contando en su categoría — sin esa
  frase la marca se lee como «esto no cuenta», que es lo contrario.

Los meses con aplazamiento las dos cifras dejan de cuadrar **a propósito**. Sin
ese número, quien lo intente concluirá que la app está mal.

## El panel (web)

`DeferredCyclePanel`, dentro del editor de una deuda que cuelga de una tarjeta
—que es la única que puede haber aplazado un recibo—. Enseña la aritmética
entera antes de escribir nada: qué movimientos, con sus fechas e importes, lo
que suman y lo que dice el recibo. El botón **sólo se enciende cuando cierra al
céntimo**; si no, se explica qué falta y no se ofrece aproximar.

Una vez declarado, el mismo panel ofrece retirar la marca. El estado viaja como
dato (`already_declared`) y no se deduce del texto del mensaje: una frase se
reescribe cualquier día y quien la estuviera comparando se entera en producción.

## Endpoints añadidos

- `GET /debt/liabilities/{id}/deferred-cycle` — qué compras cubriría. No escribe.
- `POST /debt/liabilities/{id}/deferred-cycle` — marca el ciclo. 409 si no cierra.
- `DELETE /debt/liabilities/{id}/deferred-cycle` — retira la marca.

## Migraciones

- `k7g40f2b5c3e96` — `transactions.deferred_by_account_id` (FK a `accounts`,
  `ON DELETE SET NULL`) + índice parcial. Reversible.

## Verificación

- [x] Backend: ruff · black · mypy (225 ficheros) · `alembic upgrade/downgrade`
      reversibles, sin drift, cabeza única.
- [x] Frontend: typecheck · lint · knip · 180 web + 76 ui + 60 services + 3 store.
- [x] Tests nuevos **verificados rompiendo el código**: 8 de E1 (cuatro
      roturas), 8 de E2/E3 (cuatro roturas), 6 de E4 (dos roturas), 4 de la
      capa de texto compartida y 2 de componente.
- [ ] Prueba manual del usuario.

## Lo que la revisión adversarial cambió (2026-08-15)

Cinco frentes en paralelo con verificación por hallazgo. **La revisión se
ejecutó a medias** —66 de 111 agentes murieron por límite de sesión, incluido
el crítico de completitud— así que su silencio no prueba nada sobre lo que no
llegó a mirar. Aun así destapó seis defectos reales, todos corregidos y con su
regresión verificada rompiendo el código:

1. **[bloqueador] Las tasas de ahorro mezclaban dos universos.**
   `expense_split_totals` no excluía lo aplazado mientras su ingreso venía de
   `get_totals_by_kind`, que sí. Efecto: la tasa estructural podía salir POR
   DEBAJO de la bruta —aritméticamente imposible, porque el gasto estructural
   es un subconjunto— y la pantalla pintaba un badge contradiciendo su propio
   titular. Su docstring afirmaba «su suma == gasto total del rango
   (invariante que los tests verifican)», un invariante que este mismo trabajo
   había roto: otra premisa escrita a mano caducando en silencio, esta vez
   creada por mí el día anterior.
2. **[alto] El runway contaba lo aplazado.** `structural_monthly_avg` es el
   denominador de líquido ÷ consumo mensual, o sea caja pura: metía el ciclo
   aplazado en la media y acortaba el colchón, para volver a contarlo cuando
   llegaran las cuotas.
3. **[alto] El dedup ignoraba la DIRECCIÓN.** `amount` guarda la magnitud sin
   signo (ADR-0004), así que un recibo y su DEVOLUCIÓN son idénticos para una
   regla que sólo mire importe y fecha: el banco te devuelve 264,84 € y la app
   se los come.
4. **[alto] Declarar el ciclo dos veces marcaba conjuntos distintos.** Como
   `_card_purchases` excluye lo ya marcado, la segunda llamada buscaba en un
   pool fresco y podía cerrar sobre las compras del ciclo ANTERIOR. Un doble
   clic bastaba.
5. **[alto] El corte del ciclo era la fecha de contrato**, no el cierre de
   facturación, y entre las dos caben compras del ciclo siguiente — que el
   recorrido, al ir hacia atrás, cogía las primeras. Ahora el corte lo marca
   la propia liquidación del extracto de la tarjeta, que es la señal
   estructural que ya estaba en los datos.
6. **[bajo] Una cuenta corriente pasaba por deuda** y la respuesta le pedía al
   usuario que declarase con qué tarjeta financió su nómina.

Y un comentario que mentía: justificaba el riesgo de falso positivo del dedup
diciendo que el usuario puede recuperar la copia «desde la papelera», cuando la
fila descartada nunca llega a existir.

## E4 — el aviso decía cuánto, no dónde (2026-08-23)

Lo reportó el usuario mirando junio: _«aparece el texto especificando que hay un
pago aplazado pero en este desglose no aparece marcado con asterisco qué gastos
son los aplazados»_. Con nueve categorías en pantalla, saber que hay 496,67 €
aplazados no permite señalar ni una fila.

Y al medirlo apareció un segundo defecto que nadie había visto: **el aviso no
estaba acotado al filtro**. El desglose tiene un segmentado Todo / Fijo /
Variable, y el número venía del resumen del periodo, que no sabe nada de él.
Ejecutado contra la base real, junio de 2026:

| vista    | aplazado que hay EN PANTALLA | lo que decía el aviso |
| -------- | ---------------------------- | --------------------- |
| Todo     | 496,67 €                     | 496,67 € ✓            |
| Fijo     | **245,53 €**                 | 496,67 € ✗            |
| Variable | **251,14 €**                 | 496,67 € ✗            |

Los 251,14 € que faltan bajo «Fijo» son Ropa (219,15 €) y Juegos (31,99 €),
categorías variables que ese filtro no enseña. Es la misma familia de defecto
que el resto de la sesión: dos cifras plausibles que sólo se contradicen si las
miras juntas.

**Qué se hizo**: `deferred_total` por categoría en los dos endpoints que
alimentan el desglose (`/dashboard/by-category` y el `exceptional_by_category`
de `/analytics/expense-structure` — hacen falta los dos porque el filtro se
calcula restando el segundo del primero). La fila lleva su asterisco, con el
importe en el hover (web) y **escrito al lado** (móvil, donde no hay hover), y
el aviso se **deriva de las filas que se están mostrando**: así no puede
describir otra cosa que lo que hay delante.

El invariante que lo hace seguro, y que tiene test: lo aplazado repartido por
categorías suma exactamente el `deferred_expenses` del resumen.

**Ausente ≠ cero, otra vez**: el campo es opcional y su ausencia se propaga como
tal por todo el reparto. Un backend anterior no lo manda; convertirlo en `0`
haría que la pantalla AFIRMARA «aquí no hay nada aplazado» en vez de callar y
caer al total del periodo, que es lo único que se sabe.

**De paso, una duplicación retirada**: `deriveStructural` y `toBreakdownItem`
vivían copiadas palabra por palabra en las dos apps. Mientras sólo repartían el
total daba igual; repartir también lo aplazado en dos copias es exactamente
cómo divergen dos pantallas que deben decir lo mismo. Subidas a
`packages/ui/src/breakdown-structure.ts`, con los tests de web —que sólo
cubrían una de las dos copias— movidos con ellas.

**El aviso de móvil se mudó** de la pantalla al propio `CategoryDonut`: el
filtro es estado del componente, así que desde fuera era imposible saber qué
se está mostrando.

## Limitaciones conocidas

- **Un extracto SIN signos no distingue un recibo de su devolución.** El
  clasificador deduce la dirección del texto y, para una liquidación, elige
  salida; la segunda pasada del saldo (PHASE-46) sólo rellena direcciones
  AUSENTES, no corrige las adivinadas. En ese escenario el dedup descartaría
  la devolución. La guarda de dirección protege el caso con signos, que es el
  común; cerrar el otro exige que la cadena de saldos pueda CORREGIR una
  dirección deducida del texto, un cambio de radio mucho mayor que merece su
  propia fase. Anotado en el backlog.
- **La marca POR COMPRA sólo existe en web.** El aviso del desglose sí está en
  las dos plataformas, pero el asterisco de cada fila lo pinta únicamente
  `apps/web/components/transactions/transaction-list.tsx`; en móvil no hay ni un
  consumidor de `deferredPurchaseNotice`. Tampoco lo muestra la pantalla de
  DETALLE de una transacción en ninguna de las dos.
  _(Esta línea afirmaba lo contrario hasta que el crítico de completitud
  contrastó el documento contra el código. La corrección se deja anotada aquí
  a propósito: es la novena vez que una premisa escrita a mano caduca en este
  repo, y la primera que la caza un revisor con ese encargo explícito.)_
- La propuesta **automática** —ofrecer el aplazamiento al enlazar la
  financiación con su cuadro, que es cuando el sistema ya sabe todo lo
  necesario— queda para 47.C. Hoy hay que abrir la deuda en Ajustes → Cuentas
  y pulsar «¿Qué gasto aplazó este recibo?».
- **Dos de los cuatro ciclos del usuario cierran al céntimo; dos no.** Medido
  el 2026-08-16 sobre sus datos reales: el recibo del 4-may (1.278,34 €) y el
  del 1-abr (577,16 €) cierran exactos; el del 4-jun (990,02 €) y el
  aplazamiento de junio (700,26 €) se quedan a 1,41 € y 0,88 € del mejor tramo
  contiguo. No es «faltan compras de mayo» —eso se afirmó antes de medirlo y
  era falso—: es que a esos dos ciclos les falta algún movimiento suelto. Uno
  identificado: una compra de 38,00 € del 10-jun (Parking aeropuerto) está en
  la papelera, borrada a mano por parecerse a otra idéntica del 17-may que
  sigue viva; restaurarla deja el ciclo de junio a 1,11 € de cerrar.

## Próximo paso

Prueba manual: reimportar julio a la cuenta correcta (el extracto de la tarjeta
se importó a la del banco), declarar el aplazamiento del recibo de junio y
comprobar las dos lecturas.
