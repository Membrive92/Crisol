# PHASE-47 — Dudas de implementación

**Estado**: 📋 abierto — bloquea la escritura del plan de implementación
**Sobre**: [`phase-47-debt-recomposition-inbox.md`](phase-47-debt-recomposition-inbox.md)
**Verificado contra**: el árbol en `6e7a766` (2026-08-12). Cada afirmación de
este documento lleva su `fichero:línea`; si algo no lo lleva, es una opinión y
está marcado como tal.
**Cómo se usa**: responder bajo el `→ **Respuesta:**` de cada pregunta. Las de la
Parte 2 bloquean; las de la Parte 3 llevan recomendación y se pueden delegar.

---

## Resumen ejecutivo

El diagnóstico del plan (§0) es **exacto** y verificable: 13 componentes en
[`components/debt/`](../../apps/web/components/debt/), 4 gráficos del mismo
agregado en [`debt/page.tsx`](../../apps/web/app/(app)/debt/page.tsx), y seis
superficies-verbo repartidas por la app. La dirección —bandeja, detalle por
deuda, un flujo por evento— es la correcta.

Lo que no se sostiene es la **premisa de reutilización**: el plan asume que la
cascada «compone motores existentes» y que por eso 47.1 es barato. Tres de los
seis detectores necesitan motores que hoy no existen, y uno de ellos necesita un
dato que la base de datos no tiene.

| Afirmación del plan | Estado | Dónde |
|---|---|---|
| 13 componentes, 4 gráficos, 6 superficies-verbo | ✅ cierto | [`components/debt/`](../../apps/web/components/debt/) |
| Detector #1 «reutiliza matcher PHASE-36» | ❌ el matcher no compara importes | H1 |
| `DEBT_QUOTA_MATCH_TOLERANCE_EUR` «la vigente de PHASE-36» | ❌ no existe | H1 |
| Detector #2 «generaliza el detector de PHASE-46» | ❌ son detectores distintos | H2 |
| Invariante del ciclo (47.1.b) | ⚠️ falta el dato que atribuye cargo→tarjeta | H3 |
| Test «Σ compras 1.099,64, recibo 399,38» | ❌ 1.099,64 son cargos, no compras | H4 |
| «El emparejador… dejó 4 cargos sueltos» | ⚠️ mal atribuido; el reconciliador es manual | H5 |
| 47.0 mueve las URLs a `/debt/*` | ⚠️ contradice una decisión ya tomada | D6 |
| Ya no existe vista de detalle por deuda | ❌ existe desde PHASE-24.1 | D7 |
| Sin migraciones (no se mencionan) | ❌ `dismiss` auditado y `undo` piden tabla | D1 |

---

# Parte 1 — Hallazgos (no son preguntas: son correcciones)

## H1 · El detector #1 no puede reutilizar el matcher de PHASE-36

El plan describe el detector #1 como «cargo casa con **cuota esperada** de un
plan vivo (importe ±tolerancia, ventana de fecha) — reutiliza matcher PHASE-36».

[`build_reconcile_plan`](../../backend/app/modules/personal_finance/debt/reconciliation.py#L354)
no hace nada de eso:

1. Selecciona candidatas **por texto** —
   [`is_loan_amortization`](../../backend/app/modules/personal_finance/debt/reconciliation.py#L161)
   (`"amortizac" in description`) y
   [`is_card_financed_op`](../../backend/app/modules/personal_finance/debt/reconciliation.py#L166)
   (`"operaci"` + `"financiada"` + `"tarjeta"`).
2. Resuelve la deuda destino por unicidad del pool o por `accounts.category_id`
   ([`_resolve_target`](../../backend/app/modules/personal_finance/debt/reconciliation.py#L307)).
3. Marca **la siguiente cuota pendiente, FIFO**. El importe del cargo **nunca**
   se compara con el de la cuota; sólo se usa al final para calcular el exceso
   (`assumed_unregistered_debt`).

Consecuencias directas:

- `DEBT_QUOTA_MATCH_TOLERANCE_EUR` «la vigente de PHASE-36» no existe. **No hay
  tolerancia porque no hay comparación.** La constante de la tabla de config hay
  que inventarla y calibrarla, no heredarla.
- El detector #1 es **código nuevo**, no un envoltorio.
- Y sobre todo: el motor que el plan quiere componer **es textual**, que es lo
  que el principio §1 («la redacción del concepto JAMÁS discrimina») prohíbe. Lo
  mismo vale para el clasificador del import y para el buscador del cargo
  espejo: los tres comparten
  [`CARD_SETTLEMENT_SEQUENCES`](../../backend/app/modules/personal_finance/debt/reconciliation.py#L112).

→ **El principio §1, tal y como está escrito, o exige reescribir esos tres
motores o es aspiracional.** Ver D3.

## H2 · El detector #2 no generaliza el de PHASE-46 — y es más laxo que los dos que existen

Hay **dos** detectores en el código y el plan describe un **tercero**:

| | Qué casa | Ventana | Exige texto | Ambigüedad |
|---|---|---|---|---|
| [`find_financing_matches`](../../backend/app/modules/personal_finance/transfers/service.py#L699) (PHASE-46) | abono ↔ **capital del cuadro** de un pasivo | — | no | **se calla si hay ≥2 candidatos** |
| [`find_mirror_charge`](../../backend/app/modules/personal_finance/transfers/repository.py#L111) (PHASE-34) | abono ↔ cargo del mismo importe | **±31 días** | **sí** (liquidación) | coge el más cercano |
| Detector #2 del plan | IN ↔ OUT del mismo importe | ±3 días | no | no se dice |

El propuesto quita la señal estructural (el capital del cuadro) que PHASE-46
introdujo precisamente para no depender del texto, y no la sustituye por nada:
«IN y OUT del mismo importe en 3 días» dispara con transferencias entre cuentas
propias, reembolsos y duplicados de import. La lección de PHASE-46 dice lo
contrario de lo que el detector #2 hace.

## H3 · El invariante del ciclo necesita un dato que no está en la base

47.1.b define el ciclo como «intervalo entre cargos de cierre consecutivos de la
**misma tarjeta**». Eso hoy no es derivable:

- Los cargos de cierre viven en la cuenta del **banco**, no en la tarjeta —
  [`find_mirror_charge`](../../backend/app/modules/personal_finance/transfers/repository.py#L111)
  exige `account_id == source.account_id` justamente por eso.
- [`Account`](../../backend/app/modules/personal_finance/accounts/models.py#L90) no
  tiene día de cierre ni cuenta de cargo asociada.
- La única atribución cargo→tarjeta existente es `accounts.category_id`
  (PHASE-30.4) o el enlace manual de PHASE-45.
- En julio hubo **4 cargos** y hay **6 pasivos**: la atribución es ambigua.

Además, la función que el plan da por reutilizable no sirve:
[`count_registered_outflows`](../../backend/app/modules/personal_finance/transfers/repository.py#L196)
es un `COUNT(*)` de todas las salidas de la cuenta **sin ventana temporal**. El
invariante necesita una `SUM` acotada al ciclo. Es una función nueva.

## H4 · Los importes del caso de regresión no describen lo que el plan dice

El plan escribe: «Invariante con hueco | Σ compras **1.099,64**, recibo 399,38 →
detector #5 con Δ=700,26».

`406,33 + 384,38 + 164,94 + 143,99 = 1.099,64`: eso es exactamente la suma de los
**cuatro cargos ADEUDO** de julio listados en
[`phase-45-amortization-link.md`](../phases/phase-45-amortization-link.md), que
son *liquidaciones*, no compras. Y [`HANDOFF.md`](../HANDOFF.md) dice que el
gasto de tarjeta de julio fue **609,14 €** y que julio tuvo **0 compras en la
tarjeta**, porque el extracto se importó a la cuenta del banco.

El caso de test más importante de la fase está construido sobre esa lectura. Hay
que refijarlo con los datos reales antes de escribirlo — ver D5.

## H5 · La «automatización intermitente» está mal atribuida, y eso cambia qué hay que arreglar

El diagnóstico §0.3 dice que «el emparejador actuó 6 meses y en julio dejó 4
cargos sueltos en silencio».

El reconciliador **no se ejecuta solo**:
[`POST /accounts/reconcile-debt`](../../backend/app/modules/personal_finance/accounts/router.py#L172)
es su único consumidor en todo el repo. Lo que actuó durante seis meses fue el
**absorbedor del cargo espejo en el import**, que necesita un abono al que
espejar. Y julio no falló por intermitencia: falló porque el extracto de la
tarjeta se importó a BBVA (documentado en [`lessons.md`](../lessons.md), PHASE-46).

→ **Si la bandeja arregla «la automatización que a veces calla» y nadie toca el
import, el mes que viene la bandeja se llena de items falsos** derivados de
transacciones que están en la cuenta equivocada. Ver D9.

---

# Parte 2 — Bloqueantes

## D1 · ¿La bandeja persiste, o se calcula al vuelo?

**Qué dice el plan**: nada sobre migraciones. Pero pide
`POST /debt/inbox/{id}/dismiss {reason}` «auditado», `POST /debt/inbox/{id}/undo`
que revierte **acciones automáticas**, y una sección «Resuelto automáticamente
este periodo» con su rastro.

**Qué está en juego**: ninguna de las tres se sostiene sin estado persistido. Y
`{id}` obliga a decidir antes: si los items se calculan al vuelo, el id tiene que
ser **derivable y estable** entre dos peticiones (si no, aceptar el item que el
usuario está viendo puede ejecutar otro).

**Recomendación**: híbrido.
- Items **calculados al vuelo** con `id` determinista = hash de
  `(sorted(transaction_ids), kind)`. Nada que sincronizar, nada que se pudra.
- Una tabla `debt_inbox_dismissals` (tx + motivo + fecha) para los descartes.
- El rastro de las auto-acciones **no necesita tabla propia**: ya existe
  `transactions.amortization_source_id` (PHASE-45) y `paid_transaction_id` en las
  cuotas (PHASE-36). Lo que falta es marcar *quién* lo hizo (usuario vs. sistema)
  para poder pintar la sección «resuelto automáticamente» y ofrecer deshacer:
  una columna booleana `auto_applied` sobre la fila que ya existe basta.

→ 1-2 migraciones aditivas que el plan no presupuesta.

→ **Respuesta:**

## D2 · ¿El caso A actúa sin confirmación del usuario?

**Qué dice el plan**: detector #3 → «**AUTO-VINCULA con rastro**… NO aparece en
pendientes», con `counts_as_expense` resuelto por el sistema (neutro).

**Qué hay en el código**: PHASE-45 devuelve **400 si se aplica sin declarar
`counts_as_expense`**, y su phase doc razona por qué: *«si cuenta como gasto lo
decide el usuario, porque depende de algo que sólo él sabe: si ese dinero ya se
contó al comprar»*. Es [ADR-0004](../decisions/0004-transaction-level-money-truth.md)
aplicado a la clasificación.

**Qué está en juego**: el plan dice que ADR-0004 se respeta porque «declarar
sigue siendo del usuario — iniciar y traducir deja de serlo». Pero el caso A
**declara** por él.

**Recomendación**: auto-actuar sólo cuando la respuesta sea **aritmética y no de
criterio** — es decir, cuando el invariante del ciclo cierre (±tolerancia) con
compras registradas. Ahí «no es gasto nuevo» no es una opinión: está demostrado
por la Σ. En cualquier otro caso, item en bandeja con la propuesta precargada.
Esto además vuelve el caso A **imposible** hasta que D4 esté resuelto, lo que es
información útil para la secuencia.

→ **Respuesta:**

## D3 · ¿Qué es una «candidata», y hasta dónde llega el principio «la redacción no discrimina»?

**Dos problemas en la misma frase.** El plan define la entrada de la cascada como
«transacciones candidatas (OUT/TRANSFER_OUT de cuentas corrientes + pares
detectables)».

1. **La definición es incoherente con sus propios detectores**: el #2 necesita un
   **IN** (el abono de financiación) y el #5 necesita las compras **de la
   tarjeta**, que no son de una cuenta corriente.
2. **La property de no-silencio es tautológica**: la regla #6 («nada casa →
   pendiente genérico») la hace verdadera por construcción. El riesgo real no
   está en la cascada, está en **qué entra**; y eso es justo lo que la property
   no cubre. Es el mismo patrón que la lección de PHASE-44.14 («un test que sólo
   verifica que el guardarraíl salta no prueba lo que el guardarraíl protege»).

Y de fondo, H1: si las candidatas o los detectores siguen seleccionándose por
texto, el principio §1 no es cierto.

**Recomendación**:
- Candidatas = **toda transacción activa no resuelta** cuya cuenta o contrapartida
  toque el dominio deuda, en los dos signos, sin filtrar por texto.
- La property se reescribe sobre un **universo independiente de la cascada**
  («toda tx de este periodo en cuentas con pasivo aparece en la bandeja o tiene
  resolución registrada»), o no prueba nada.
- El principio §1 se reformula a lo que sí se puede sostener: *el texto puede
  proponer, pero nunca puede ser la única señal que decide*. La señal estructural
  (importe que cuadra, capital del cuadro, saldo del extracto) manda cuando
  existe.

→ **Respuesta:**

## D4 · ¿Cómo se atribuye un cargo de cierre a su tarjeta?

Ver H3. Sin resolver esto no hay 47.1.b, ni detector #3, ni #5, ni caso A.

**Opciones**:

| | Coste | Qué implica |
|---|---|---|
| (a) Campo `settlement_account_id` en la tarjeta | 1 migración + campo en el form | El usuario lo declara una vez. Explícito, sin adivinar |
| (b) Forzar el vínculo por `accounts.category_id` | 0 migraciones | Reutiliza PHASE-30.4, pero exige que el usuario tenga una categoría por tarjeta |
| (c) Aprenderlo del primer enlace manual (PHASE-45) | 0 migraciones | Se aprende solo, pero el primer mes no hay invariante |

**Recomendación**: (a) + (c) — el campo explícito, precargado con lo que se
aprenda del primer enlace, editable. Es el patrón que ya funcionó en PHASE-45:
el sistema propone con su motivo, el usuario adjudica.

→ **Respuesta:**

## D5 · Los cuatro ADEUDO de julio: ¿qué son exactamente?

Necesario para escribir el caso de regresión (H4) y para tu punto de parada (a)
—validar el aprendizaje del ciclo contra tus seis meses casados—.

| Fecha | Importe | Concepto |
|---|---|---|
| 08-jul | 406,33 € | Adeudo mensual de tarjeta |
| 08-jul | 384,38 € | Adeudo mensual de tarjeta |
| 15-jul | 164,94 € | Adeudo mensual de tarjeta |
| 15-jul | 143,99 € | Adeudo mensual de tarjeta |

Dos el día 8 y dos el 15 huele a **dos tarjetas × dos conceptos**, no a cuatro
ciclos. Preguntas concretas:

- ¿Cuántas tarjetas físicas hay detrás de esos cuatro cargos?
- ¿Cuál de ellos es la liquidación del ciclo y cuál la cuota de un aplazamiento?
- ¿Cuál es el importe real de «Σ compras del ciclo» del mes que sirva de caso
  verde (uno donde el extracto de la tarjeta SÍ se importó a la tarjeta: mayo o
  junio, con 7 compras cada uno)?

**Recomendación**: usar **mayo o junio** como caso verde del invariante y julio
como caso del hueco, no al revés. Julio es el mes contaminado.

→ **Respuesta:**

---

# Parte 3 — Alcance y secuencia (con recomendación; delegables)

## D6 · 47.0 contradice una decisión ya tomada en el backlog

[`backlog.md`](../backlog.md) (entrada «[Ola 6] Reorg físico backend del módulo
deuda») dice literalmente: *«URL `/accounts/debt-*` se mantiene (cambiarla a
`/debt/*` rompe contrato; migración versionada futura)»*.

El movimiento de ficheros **sí es viable sin ciclos**: los seis módulos a mover
sólo importan `accounts.models`, `accounts.repository` y `accounts.schemas`, que
son hojas; ninguno importa `accounts.service`. Un detalle a resolver:
`debt_health.py` importa `DebtHealthKpis` de `accounts.schemas` — o se mueven
también esos schemas, o queda un import cruzado.

**Recomendación**: hacer 47.0 en un commit propio y **sin tocar URLs**. El alias
deprecado es trabajo y superficie a cambio de nada que el usuario note.

→ **Respuesta:**

## D7 · Ya existe una página de detalle por deuda

El plan dice «no existe vista de detalle por deuda». Existe desde PHASE-24.1:
la [página de amortización por cuenta](../../apps/web/app/(app)/personal-finance/accounts/[id]/amortization/page.tsx)
y su gemela en móvil, con cabecera, KPIs, `ScheduleCondensed` y pagar/editar
cuota. Lo que le falta es lo que 47.3 añade: movimientos de esa deuda, pendientes
de esa deuda e invariante del ciclo.

**Recomendación**: **mover** esa página a `/debt/[account_id]` con redirect, no
crear una segunda. Dos páginas de detalle por deuda es exactamente el problema
que la fase existe para resolver.

→ **Respuesta:**

## D8 · ¿Esto es una fase o cinco?

47.0 (mover 6 ficheros) · 47.1 (motor + 6 endpoints + persistencia + 2
detectores nuevos + 1 dato nuevo) · 47.2 (bandeja web) · 47.3 (detalle) · 47.4
(unificar seis diálogos) · 47.5 (barrido) · paridad móvil.

**Recomendación**: tres entregables probables por separado.

| | Contenido | Por qué corta ahí |
|---|---|---|
| **47.A** | 47.0 + D4 (dato de atribución) + guardarraíl del import (D9) | Sin comportamiento nuevo salvo el guardarraíl. Se puede probar en un rato |
| **47.B** | 47.1 + 47.2 + 47.3 | La bandeja y el sitio donde vive. Es lo que resuelve la queja |
| **47.C** | 47.4 + 47.5 + paridad móvil | Retirar los diálogos viejos **sólo** cuando 47.B lleve un mes demostrando que los cubre (tu punto de parada (d)) |

→ **Respuesta:**

## D9 · ¿Entra el guardarraíl del import en esta fase?

Es el fallo que causó el lío de julio y sigue abierto en
[`lessons.md`](../lessons.md) (*«Pendiente: que el import avise cuando el
contenido no encaje con la cuenta elegida»*). Es barato —comparar el contenido
del fichero con la cuenta elegida antes de confirmar— y evita que la bandeja se
llene de items derivados de transacciones mal ubicadas.

**Recomendación**: sí, como 47.A. Sin él, la bandeja hereda basura y el usuario
concluye que la bandeja no funciona.

→ **Respuesta:**

## D10 · ¿ADR?

El plan declara el orden de la cascada «contrato de comportamiento» y cambia
quién decide qué (D2). Eso es exactamente lo que pide un ADR.

**Recomendación**: ADR-0011 — «la traducción movimiento→evento de deuda la
inicia el sistema; la declaración sigue siendo del usuario», con el orden de la
cascada dentro y la relación con
[ADR-0003](../decisions/0003-debt-module-two-layer-architecture.md) y
[ADR-0004](../decisions/0004-transaction-level-money-truth.md).

→ **Respuesta:**

---

# Parte 4 — Menores

## D11 · Dos ventanas para el mismo hecho

`DEBT_PAIR_WINDOW_DAYS = 3` frente a los **±31 días** de
[`_MIRROR_WINDOW`](../../backend/app/modules/personal_finance/transfers/repository.py#L35).
Si el detector #2 convive con el espejo, hay dos definiciones de «el mismo
dinero visto por los dos lados» que pueden divergir — el patrón exacto que costó
la lección de PHASE-46. ¿Sustituye o convive? Si convive, ¿cuál manda?

→ **Respuesta:**

## D12 · El barrido de 47.5 en móvil

`debt-daily-evolution` y `debt-trend-chart` existen **también** en
[`apps/mobile/components/debt/`](../../apps/mobile/components/debt/). ¿Se borran
en las dos apps, o móvil se queda con los gráficos viejos hasta la paridad?

→ **Respuesta:**

## D13 · Orden de rutas en el router

`GET /debt/{account_id}/detail` convive sin colisión con `/debt/dashboard-summary`
y `/debt/category-summary` porque lleva segmento después. Conviene fijarlo por
escrito para que nadie añada `GET /debt/{account_id}` a secas más adelante —
[`accounts/router.py`](../../backend/app/modules/personal_finance/accounts/router.py#L349)
ya tiene ese patrón y depende del orden de declaración.

→ **Respuesta:**

## D14 · El plan de PHASE-48 no existe

El documento cita «el plan ya escrito en `phase-45-debt-early-settlement.md`»
para renumerarlo a 48. **Ese fichero no está en el repo ni en el historial de
git.** ¿Lo tienes fuera, o hay que escribirlo? Afecta al detector #4, que sólo
tiene sentido si hay una cola a la que mandar el item.

→ **Respuesta:**

---

## Secuencia propuesta, si todo sale como recomiendo

1. **47.A** — mover ficheros sin tocar URLs (D6) · atribución cargo→tarjeta (D4)
   · guardarraíl del import (D9) · ADR-0011 (D10).
2. **Parada**: validar el aprendizaje del ciclo contra mayo/junio reales (D5,
   punto de parada (a) del plan).
3. **47.B** — motor de clasificación con los detectores #1 y #2 **escritos de
   nuevo** sobre señal estructural (H1, H2) · endpoints · bandeja · detalle por
   deuda **movido**, no duplicado (D7).
4. **Parada**: reproducir julio y un mes normal.
5. **47.C** — flujo unificado, retirada de los seis diálogos con checklist por
   diálogo, barrido, paridad móvil.

Fuera de esta fase, y conviene decirlo en voz alta: la pregunta que el
[`HANDOFF.md`](../HANDOFF.md) dejó abierta —*si el saldo de la deuda necesita las
dos verdades del MUX de PHASE-36*— **este plan no la responde**. La bandeja hace
más llevadera la traducción; no reduce las dos verdades a una. Si la respuesta
fuera «no las necesita», parte de 47.1 sobraría.
