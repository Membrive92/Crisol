# PHASE-46 — La deuda que nace no es un ingreso

**Estado**: 🚧 pendiente prueba manual
**Rama**: `main` (push directo)
**PR**: —
**Fecha**: 2026-08-10

## Objetivo

Que un aplazamiento deje de contar como ingreso. Reportado por el usuario sobre
la gráfica anual: *«La deuda generada no puede contar como ingreso ya que no son
ingresos, son aplazamientos»*.

## El hallazgo

Julio de 2026 tenía **700,26 € de ingreso que nadie cobró** — y resultó ser el
**100 %** del ingreso que la app atribuía a ese mes. La pareja completa, tal como
está en la BD:

| Fecha | Concepto | Importe | `flow` | Debía ser |
|---|---|---|---|---|
| 07-04 | `Recibo anterior jun-26 Otras financiaciones` | +700,26 | `IN` | `TRANSFER_IN` |
| 07-05 | `Recibo mes anterior No categorizable` | −700,26 | `OUT` | `TRANSFER_OUT` |

BBVA financió el recibo de la tarjeta de junio: abona el importe y al día
siguiente lo cobra. Neto de caja **cero**, y queda una deuda a 36 meses. La app
lo leyó como un ingreso de 700,26 € y un gasto de 700,26 € — este segundo,
además, **doblando** compras que ya habían contado una a una en su mes.

Dos cosas hacen el diagnóstico concluyente en vez de plausible:

1. El **mismo hecho en marzo** (`Operacion financiada Otras financiaciones`,
   +239,00) se clasificó bien y quedó atado a su deuda. La diferencia no era el
   hecho: era la redacción.
2. El usuario **ya había creado la deuda**: `Compra finaciada recibo junio`,
   36 cuotas, capital **700,26 € exactos**. Lo que faltaba era el enlace.

## Causa

Tres listas de redacciones bancarias escritas a mano decidían todo esto, y BBVA
usó dos que no estaban en ninguna:

- `_INTERNAL_MOVEMENT_PATTERNS` (servicio) — exigía `"operacion financiada"`.
- `_CARD_SETTLEMENT_LIKE` (repositorio) — exigía `%adeudo%tarjeta%`.
- `is_card_financed_op` (reconciliación).

Las dos primeras describen **lo mismo** —qué es una liquidación de tarjeta— en
sitios distintos, que es justo lo que PHASE-38 dejó dicho que no se hiciera.
Divergieron: `Recibo mes anterior` no estaba en ninguna, así que el clasificador
la contó como gasto nuevo **y** el buscador del cargo espejo no la reconoció.

## Qué se implementó

### 1. Una sola definición (`accounts/debt_reconciliation.py`)

Las secuencias de tokens se declaran una vez y cada consumidor deriva su forma:
subcadena ordenada en Python, `ILIKE '%tok1%tok2%'` en SQL. `_matches_token_sequence`
avanza el cursor tras cada token para que las dos caras no puedan responder
distinto sobre la misma descripción.

- `CARD_SETTLEMENT_SEQUENCES` + `is_card_settlement`
- `FINANCING_INFLOW_SEQUENCES` + `is_financing_inflow`

Un gate (`test_card_settlement_definition_is_shared_with_the_mirror_finder`)
falla si alguien vuelve a enumerar liquidaciones en un solo lado.

### 2. La financiación entrante nunca es ingreso

`classify_import_flow` marca `TRANSFER_IN` un abono cuyo texto sea una
financiación. **La condición del signo no es defensiva, es lo que hace correcta
la regla**: el mismo producto reaparece con signo contrario cuando llega la
cuota, y ésa sí es gasto real de caja (PHASE-38, porque su compra no cuenta como
gasto en ningún otro sitio). Sin el signo, apagar el ingreso falso apagaría el
gasto verdadero.

### 3. Reconocimiento por el CUADRO, no por el texto

`find_financing_matches` propone la deuda cuyo capital de cuadro coincide con el
abono (tolerancia de un céntimo, la misma de la reconciliación) y que aún no
tiene registrado el movimiento que la originó. El texto decide **si** un abono
es una financiación; el capital decide **a qué deuda pertenece** — el extracto no
trae ninguna referencia común con la cuenta que el usuario dio de alta, y el
capital sí, porque un aplazamiento y su cuadro nacen del mismo importe.

Se propone sólo cuando la coincidencia es **única**: con dos deudas del mismo
capital sin originar, elegir una sería inventarse cuál.

### 4. La columna Saldo decide la dirección cuando el importe no la trae

Salió al revisar julio con el usuario. Su extracto de cuenta viene **sin
signos**, así que la dirección se deduce del texto y, si falla, del kind de la
categoría. `Operación financiada 4940…` (700,26 €) no dice ni «abono» ni
«recibido» y no resolvió categoría → entró `flow = NULL`, la única de 40 filas.

La prueba estaba **dentro de la propia fila**: PHASE-39 ya guardaba
`statement_balance = 1.417,36`, y el saldo anterior era 717,10. El salto es
exactamente el importe, y su signo es la dirección.

`resolve_flows_from_balance_chain` es una segunda pasada sobre el lote —tiene
que serlo: el salto es una relación ENTRE filas consecutivas—. Sólo actúa
cuando el salto coincide **exactamente** con el importe: si entre dos saldos
hubiera un movimiento sin saldo, no cuadraría y no se toca nada. Una fila
neutra es honesta; una dirección inventada, no. La fila resuelta vuelve a pasar
por `classify_import_flow` con el signo deducido, así que su transfer-ness sale
de la misma regla que el resto — por eso la «transfer-ness» se extrajo a
`is_internal_movement_row`.

El orden importa: BBVA imprime el movimiento más reciente arriba. Leyendo el
fichero en su orden, el salto sale con el signo cambiado y la fila entraría **al
revés**, que es peor que dejarla neutra. Se reutiliza la detección de orden que
ya tenía `_pick_balance_anchor`, con un test que lo fija.

### 5. Se propone, no se aplica

El enlace lo confirma el usuario desde Transacciones. Atarlo cambia dónde vive
ese dinero —sale del ingreso del mes y pasa a ser deuda—, y eso es una afirmación
sobre su vida, no sobre sus datos (PHASE-28: la dirección se declara).

## Archivos clave

- `backend/app/modules/personal_finance/accounts/debt_reconciliation.py` — las
  secuencias compartidas y los dos predicados nuevos.
- `backend/app/modules/personal_finance/transfers/service.py` — regla del signo
  en `classify_import_flow`; `find_financing_matches`.
- `backend/app/modules/personal_finance/transfers/repository.py` — el espejo
  deriva sus patrones de la fuente común; dos queries nuevas.
- `apps/web/components/transactions/financing-matches-section.tsx` — la propuesta.

## Endpoints añadidos

- `GET /transfers/financing-matches` → `list[FinancingMatchResponse]`.

## Migraciones

Ninguna.

## Efecto esperado al confirmar (datos del usuario)

| | Antes | Después |
|---|---|---|
| Ingresos julio 2026 | 700,26 € | 0,00 € |
| Gastos julio 2026 | 1.309,40 € | 609,14 € |
| Saldo BBVA | — | **sin cambio** (el par ya se anulaba) |
| Deuda viva | — | **sin cambio** (el cuadro ya mandaba los 700,26) |

Que el saldo y la deuda no se muevan es la comprobación de que el arreglo toca
la etiqueta y no el dinero.

## Verificación

- [x] BE **1353 tests** en verde · ruff · black · mypy (221 ficheros)
- [x] Los tests nuevos verificados **rompiendo el código**: quitar la redacción
      de la liquidación tumba 3; quitar la condición del signo tumba 1 — y es la
      que protege el gasto real.
- [x] FE typecheck · lint · knip · 307 tests (5 nuevos del panel) + móvil
- [x] Emparejado probado contra la BD real: **una** propuesta, la correcta, y no
      propone la de marzo (ya atada)
- [ ] Prueba manual del usuario: confirmar la propuesta en Transacciones y ver
      caer el ingreso de julio en la gráfica anual

## Lo que apareció al probarlo con datos reales

La prueba manual destapó que el problema de julio era **más grande que el
aplazamiento**: `julio criedito.pdf` (extracto de la TARJETA) se había importado
eligiendo la cuenta **BBVA**. Efecto medido: julio fue el único mes en que la
tarjeta no recibió ni una compra (mayo 7, junio 7, **julio 0**) y 17 compras de
tarjeta (609,14 €) colgaban del banco.

Por eso había **tres** líneas de 700,26 €: no era un duplicado, eran los **dos
puntos de vista** del mismo hecho —el del extracto de la tarjeta (cargo del
recibo + aplazamiento) y el del extracto de la cuenta (`Operación financiada`,
el dinero entrando)—, cada uno perteneciente a una cuenta distinta. La propuesta
enganchó la deuda a la copia de la tarjeta porque era la única que reconocía:
con los datos que veía hizo lo correcto, pero los datos estaban en la cuenta
equivocada.

`scripts/undo_card_statement_into_bank.py` deja el terreno listo para
reimportar: deshace el enlace, manda las filas a la papelera (soft-delete, así
`find_existing_hashes` no las cuenta) y **limpia `absorbed_as_mirror`** del cargo
espejo. Ese último paso no es cosmético: esa marca hace que un cargo absorbido
cuente como existente para no resucitarlo (AUDIT-2026-07 H-04), que es correcto
en su caso y justo lo contrario aquí — sin limpiarla, la reimportación se
saltaría esa línea en silencio y a la tarjeta le faltaría un movimiento.

## Limitaciones conocidas

- Los abonos de financiación **ya importados** siguen como `IN` hasta que se
  confirma la propuesta; el clasificador sólo actúa en importaciones futuras.
- Si dos deudas sin originar tienen el mismo capital exacto, no se propone
  ninguna (a mano desde el detalle de la transacción, como antes).
- Sin paridad móvil: la propuesta sólo está en web.

## Próxima fase

Pendiente de decidir con el usuario: la conversación que abrió esta fase era
sobre el módulo de deuda entero, y esto sólo cierra la puerta de entrada.
