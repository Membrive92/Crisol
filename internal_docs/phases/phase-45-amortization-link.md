# PHASE-45 — «Es una amortización»: el cargo del banco que baja la deuda

**Estado**: ✅ implementada (pendiente de prueba manual)
**Rama**: `main` (push directo)
**Alcance**: backend + web + móvil. Una migración aditiva.

## El caso que faltaba

Cuatro cargos `ADEUDO MENSUAL DE TARJETA` de julio (406,33 · 384,38 · 164,94 ·
143,99 = **1.099,64 €**) salían de BBVA y **no tocaban el módulo de deuda**.
No había ningún gesto en la app para decir «este dinero paga esta deuda»: los
seis meses anteriores funcionaban porque el emparejador les había creado su pata
en la tarjeta, y estos cuatro se quedaron sueltos.

El módulo tenía el mecanismo (`transfers/link`, el asistente «Pagar cuota») pero
sólo hacia adelante: sirve para **crear** el pago, no para adoptar uno que ya
está importado.

## Dos decisiones, y cada una la toma quien sabe

**Cómo baja la deuda lo decide el pasivo**, y ya estaba decidido desde
[PHASE-36]: con cuadro manda el cuadro, sin cuadro mandan los movimientos. Aquí
sólo se respeta el mismo MUX —extraído a `resolve_liability_outstanding` para
que `get_balances` y el panel no puedan divergir— con su consecuencia:

| | Con cuadro (préstamo, compra a plazos) | Sin cuadro (tarjeta con saldo arrastrado) |
|---|---|---|
| Qué se escribe | se marcan cuotas pagadas | se crea el movimiento contrario en la deuda |
| Cuánto baja | el **capital** de esas cuotas | el importe entero |
| Pata en la deuda | **ninguna** — sería invisible para el saldo | sí, `TRANSFER_IN` |

Que la deuda baje por el capital y no por lo pagado es la distinción que el
panel existe para explicar: si no se dice, el usuario paga 232,27 €, ve que debe
150 € menos y piensa que hay un error. La frase lo dice y el test lo afirma.

**Si cuenta como gasto lo decide el usuario**, porque depende de algo que sólo
él sabe: si ese dinero ya se contó al comprar. El servidor sugiere con su motivo
escrito y obedece la declaración — es la lección de [PHASE-28] («la dirección se
declara, no se adivina») aplicada a la clasificación:

- Pasivo con cuadro → sugiere **sí**: su capital entró como deuda y no se contó
  como gasto en ningún sitio. Es lo que [PHASE-38] ya decidió para la cuota de
  una compra a plazos.
- Tarjeta **con compras registradas** → sugiere **no**: esas compras ya cuentan
  en su mes (la tarjeta del usuario aportó 835,28 € de gasto en mayo y 685,01 €
  en junio), así que contar además lo que las liquida cobraría el mismo dinero
  dos veces.
- Tarjeta **sin ninguna compra registrada** → sugiere **sí**: ese cargo es el
  único rastro de ese gasto.

La sugerencia se cuenta contra los datos (`count_registered_outflows`), no
contra el tipo de cuenta.

## Por qué NO se empareja cuando cuenta como gasto

Un par significa «el mismo dinero visto por los dos lados, fuera del cashflow»,
y eso no es una convención decorativa: `budgets/repository.py` y
`debt/repository.py` filtran `transfer_pair_id IS NULL` en ocho consultas. Una
pata declarada como gasto y emparejada desaparecería del presupuesto y del gasto
de deuda — exactamente lo contrario de lo que el usuario acaba de pedir.

De ahí la columna nueva `transactions.amortization_source_id`: la contrapartida
apunta al cargo del banco sin usar el par. Con ella la operación es
**detectable** (¿ya está registrada?), **idempotente** (409 al segundo intento)
y **reversible** (el `DELETE` sabe qué pata borrar). Reutilizar
`transfer_pair_id` habría sido más barato de escribir y falso.

## Qué se entrega

**Backend**
- `POST /transfers/amortization` con `dry_run`: previsualiza el efecto EXACTO
  sin escribir. El plan de cuotas sale de la misma función pura que lo aplica
  (`plan_installments_covering_principal`), así que lo prometido y lo ocurrido
  no pueden discrepar.
- `GET /transfers/amortization/{tx}` — el registro, o 404 (que la pantalla lee
  como estado normal, no como error).
- `DELETE /transfers/amortization/{tx}` — desmarca cuotas, desempareja y manda
  la contrapartida a la papelera.
- Migración `h4d17c9e2f0b63`, aditiva y reversible, sin backfill.

**Compartido** — `packages/ui/src/amortization-copy.ts`: las frases, las
etiquetas y el aviso viven en la capa PURA, no en cada app ([PHASE-44.13]: la
partición va después del contenido). Si vivieran duplicadas, una pantalla podría
acabar diciendo que la deuda baja por lo pagado y la otra por el capital.

**Web y móvil** — el mismo panel, mismo previsualizador, mismas frases; sólo
cambia el renderizado. Aparece en el detalle de una transacción de salida sin
emparejar.

## Guardarraíles

| Situación | Respuesta |
|---|---|
| La tx es un ingreso | 400 — una amortización es dinero que sale |
| Ya registrada | 409 con «deshaz el registro antes» |
| La tx está emparejada | 409 — el par ya mueve el dinero; amortizar además bajaría la deuda dos veces |
| Cuenta destino no es deuda / es la propia / otra divisa | 400 |
| Aplicar sin declarar `counts_as_expense` | 400 |
| Tx o cuenta de otro usuario | 404 |

## Verificación

- **19 tests nuevos** en `backend/tests/test_amortization.py`, verificados
  **rompiendo el código**: al hacer que la deuda bajara por lo pagado en vez de
  por el capital, y al emparejar siempre, cayeron tres.
- 9 tests de la capa compartida en `packages/ui` y 7 del panel web, éste también
  verificado rompiéndolo (enviar la sugerencia en vez de la declaración del
  usuario tumba el test que lo afirma).
- `ruff` · `black` · `mypy` · `alembic upgrade`/`downgrade` reversibles, cabeza
  única, `alembic check` sin drift · `typecheck` · `lint` · `knip` · la suite
  completa del backend y los cinco paquetes de frontend.

## Limitaciones conocidas

- **Sin prueba manual todavía.** Los cuatro cargos de julio siguen sin registrar:
  ahora se hacen desde la pantalla, uno a uno, eligiendo la deuda.
- **Sin cross-currency** (400 explícito), igual que sus dos endpoints hermanos.
- **La contrapartida va a la papelera al deshacer**, no se borra. Si se restaura
  desde la papelera, quedaría duplicada — el caso es raro y visible, pero no hay
  guardarraíl.
- El panel no ofrece repartir principal/intereses a mano: para un pasivo con
  cuadro toma el reparto del propio cuadro, que es la fuente de verdad. Si el
  banco cobra algo distinto, la vía sigue siendo editar la cuota.
