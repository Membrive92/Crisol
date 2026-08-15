# ADR-0011 — La traducción movimiento→evento de deuda la INICIA el sistema; la declaración sigue siendo del usuario

**Estado**: aceptada
**Fecha**: 2026-08-13
**Fase**: PHASE-47.A (bloquea 47.B — plan en
[`improvements/phase-47-implementation-plan.md`](../improvements/phase-47-implementation-plan.md),
diagnóstico en [`improvements/phase-47-debt-recomposition-inbox.md`](../improvements/phase-47-debt-recomposition-inbox.md),
contratos exactos en [`improvements/phase-47-anexo-implementacion.md`](../improvements/phase-47-anexo-implementacion.md))
**Relacionada con**: [ADR-0003](0003-debt-module-two-layer-architecture.md) (pasivos
opt-in, dos capas) y [ADR-0004](0004-transaction-level-money-truth.md) (la verdad
del dinero vive en la transacción; la dirección se declara, no se adivina)

---

## Contexto

Cada hecho real de deuda llega a la aplicación **disfrazado de transacción**: un
cargo del banco puede ser la cuota de un préstamo, la liquidación de una tarjeta,
una compra a plazos o una liquidación anticipada, y el extracto los escribe casi
igual. Traducir ese movimiento al evento que representa es hoy trabajo del
usuario: elige el verbo de memoria entre seis superficies distintas
(`amortization-panel`, `convert-to-debt-dialog`, `financing-matches-section`,
pagar cuota, editar cuota, asistente de pago de deuda), y si se equivoca de
superficie el error no salta.

Lo que se ha ido construyendo hasta aquí resuelve **gestos**, no la traducción:

- [PHASE-45](../phases/phase-45-amortization-link.md) dio el gesto «esto paga
  esta deuda», con previsualizador y sugerencia razonada.
- [PHASE-46](../phases/phase-46-financing-is-not-income.md) dio la propuesta «este
  abono es el nacimiento de esta deuda», apoyada en el capital del cuadro.

Ambas esperan a que el usuario abra la transacción correcta. La consecuencia
medida está en `HANDOFF.md` (sesión del 10 de agosto): **45 de 479 movimientos**
—uno de cada diez— no son ni gasto ni ingreso, y para leer un mes hay que saber
por qué está cada uno. Y las seis correcciones que hicieron falta para dejar
julio cuadrado **no se podían hacer desde la interfaz**.

El otro lado del problema es peor que el trabajo manual: **el silencio**. Cuando
un automatismo no encuentra a qué atar un movimiento, no pasa nada. No hay error,
no hay aviso, no hay cola. Julio de 2026 produjo 700,26 € de ingreso que nadie
cobró y cuatro cargos sin clasificar, y la señal que lo destapó fue **comparar el
recuento de compras entre meses** — no la aplicación. Un modo de fallo cuyo
síntoma es «no ha pasado nada» se lee como éxito; es la misma familia que el cron
mudo de [PHASE-44.13] y el `0` en el log que significaba «no había trabajo»
(ver [`lessons.md`](../lessons.md)).

La tentación evidente —que el sistema clasifique y persista solo— choca de frente
con ADR-0004: la dirección y la naturaleza del dinero **se declaran**, no se
adivinan, porque una señal que puede mentir (la categoría, la redacción del
concepto) gobernaba varias decisiones a la vez y eso costó las lecciones de
PHASE-23.1, 28, 32, 34 y 46.

## Decisión

**Se separa INICIAR de DECLARAR.** El sistema deja de esperar a que el usuario
abra la transacción correcta; lo que no hace nunca es responder por él a una
pregunta de criterio.

1. **El sistema inicia y traduce; el usuario declara.** Una bandeja
   (`GET /debt/inbox`) recorre las transacciones candidatas del periodo, las pasa
   por una cascada de detectores y presenta cada hecho con su **propuesta ya
   resuelta y su motivo escrito**. Las tres decisiones conceptuales —cuadro o sin
   cuadro, capital o pagado, cuenta o no como gasto— llegan pre-rellenadas por
   los motores existentes (PHASE-36, PHASE-45); el usuario acepta o cambia. Esto
   **respeta** ADR-0004: declarar sigue siendo suyo.

2. **Silencio-con-rastro: «nada» deja de ser un estado posible.** Toda
   transacción candidata acaba en exactamente uno de dos sitios: actuada **con
   rastro visible y reversible**, o en la bandeja. Se afirma con un property test
   cuyo universo se construye **con su propia query**, no llamando al
   clasificador: un test que pregunta a la misma función que la bandeja sólo
   demuestra que la función es consistente consigo misma.

3. **La única excepción a (1) es la aritmética, no el criterio.** El sistema
   puede actuar sin confirmación **sólo** cuando la respuesta la demuestra una
   suma: el invariante del ciclo de tarjeta cierra dentro de tolerancia contra
   las compras registradas. Ahí «no es gasto nuevo» no es una opinión —está
   probado por la Σ—. Toda acción automática deja `auto_applied = TRUE`, aparece
   en la sección «Resuelto automáticamente este periodo» y es reversible.
   Cualquier otro caso va a bandeja con la propuesta precargada.

4. **La redacción del concepto puede AÑADIR confianza; nunca seleccionar ni
   descartar candidatas.** Es la reformulación honesta del principio que el plan
   original escribió como «la redacción JAMÁS discrimina»: los motores que hoy
   existen (el clasificador del import, el buscador del cargo espejo, el
   reconciliador) **son textuales**, y el principio absoluto exigía reescribir
   los tres o quedarse en aspiración. Manda la señal **estructural** cuando
   existe —importe que cuadra, capital del cuadro, saldo del extracto, plan
   vivo—; el texto sólo sube la confianza de una propuesta ya sostenida por otra
   cosa. Se comprueba alimentando cada detector con **dos redacciones distintas
   del mismo hecho** y exigiendo el mismo item.

5. **Ambigüedad se muestra, no se resuelve en silencio.** Con dos o más
   candidatos, el item lleva la lista y el usuario adjudica. Esto sustituye al
   silencio de PHASE-46 ante empate, que era honesto pero mudo.

6. **El orden de la cascada es contrato de comportamiento.** Primer match gana, y
   el orden no se altera sin decisión explícita: cambiarlo reclasifica hechos
   pasados sin que nadie lo pida.

7. **El deshacer de la bandeja cubre acciones de tipo VÍNCULO, no de tipo
   ASISTENTE.** Des-marcar una cuota, des-enlazar una amortización o revertir
   `counts_as_expense` son inocuos. Un asistente que creó pasivo + cuadro +
   vínculos se revierte por su propio flujo (borrar el plan), no por un botón de
   la bandeja: un deshacer que borra cuentas y cuadros en un clic es una pistola
   cargada.

8. **ADR-0003 intacto.** Una tarjeta que se paga íntegra cada mes no necesita
   cuenta de pasivo, y la bandeja no da la lata para crearla.

## Consecuencias

**A favor**

- El mes normal fluye solo: la bandeja vacía dice «todo cuadra — N movimientos
  verificados», que es información, no ausencia de información.
- El fallo se vuelve visible **por construcción**. Lo que hoy es un hueco que
  sólo aparece comparando meses pasa a ser una fila con su importe exacto.
- La unidad mental del usuario («la hipoteca», «el aplazado de junio») recupera
  sitio: los pendientes de una deuda viven en su detalle.
- La cola de PHASE-48 (liquidación anticipada) nace como una fila más de esta
  bandeja en vez de como otra superficie-verbo.

**En contra, y asumido**

- Una bandeja mal alimentada es peor que ninguna: si el universo de candidatas
  hereda transacciones mal ubicadas —el fichero de la tarjeta importado en la
  cuenta del banco—, se llena de items falsos y el usuario concluye que no
  funciona. Por eso el guardarraíl del import entra en **la misma entrega**
  (47.A) que este ADR, y no después.
- El punto 3 introduce el único camino en que el sistema declara por el usuario.
  Se acota a un caso demostrable y con rastro, y se vigila con un test que exige
  que un pasivo **con cuadro** nunca entre por ahí.

## Deuda declarada

- **El punto 4 describe la regla, no el estado del código.** Los tres motores
  textuales existentes siguen siéndolo; lo que este ADR prohíbe es que un
  detector NUEVO de la cascada seleccione candidatas por texto. Reescribir los
  tres viejos sobre señal estructural no entra en PHASE-47 y no se declara hecho.

- **La atribución cargo→tarjeta es un dato que hasta 47.A no existía.**
  `accounts.settlement_account_id` lo hace explícito: sin él no hay ciclo, ni
  invariante, ni caso automático del punto 3. Se propone a partir de los enlaces
  que el usuario ya hizo en PHASE-45, pero lo adjudica él.

- **Este ADR no responde la pregunta de las dos verdades del saldo.** El MUX
  cuadro-vs-movimientos de PHASE-36 sigue en pie: la bandeja hace llevadera la
  traducción, no reduce las dos verdades a una. Esa pregunta se contesta mejor
  con la bandeja delante, y su sitio es PHASE-48 §48.1 (doble saldo con nombre).
