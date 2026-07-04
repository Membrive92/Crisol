# PHASE-33 — Transferencias internas: overhaul de UX e integridad

**Estado**: 🚧 en curso (código completo + verde; pendiente prueba manual del usuario y PR)
**Rama**: `feat/transfers-ux-overhaul`
**PR**: —
**Fecha de merge**: —

## Objetivo

Tras PHASE-28/31/32 la *mecánica* de las transferencias internas era
correcta (dirección explícita, signo del saldo bien resuelto), pero
seguía siendo **fácil de hacer mal y difícil de leer** en la UI: términos
españoles que no se detectaban, categorías de transferencia mezcladas con
gastos reales, un badge que confundía pares con patas huérfanas, jerga
contable y un canal de errores de import que marcaba como "fallo" filas
que sí se habían importado.

Esta fase es un overhaul transversal (web + móvil) en 8 sub-entregas
(`transfers-ux P1…P8`) que cierran esos huecos. Tema único: **que sea
difícil meter una transferencia mal y obvio cuando una está incompleta.**

## Qué se implementó

### P1 — Descubrir términos españoles en sospechosas (backend)

El detector de sospechosas en `/transfers` sólo casaba la subcadena
inglesa `%transfer%`, así que **BIZUM** y **TRASPASO** —los movimientos
internos más comunes en extractos españoles— nunca aparecían como
candidatas. Se sustituye el `ILIKE` único por una lista de patrones de
descubrimiento compartida (`_TRANSFER_DISCOVERY_PATTERNS_SQL`:
TRANSFER/TRANSF./TRASPASO/BIZUM/ENVÍO DE DINERO/ENVÍO INMEDIATO) vía el
helper existente `_description_matches_any`. Es una bandeja de revisión,
así que tolera falsos positivos antes que perderse reales.

### P2 — Ofrecer siempre "convertir en deuda financiada" (web + mobile)

El bloque de operación financiada sólo se pintaba cuando la descripción
casaba `looksLikeFinancedOperation`; si el banco describía la compra a
plazos de otra forma, no había manera manual (web ni móvil) de
registrarla y el usuario la archivaba como gasto normal, **infravalorando
deuda y patrimonio neto**. Ahora el bloque se muestra siempre que la tx
está sin emparejar; la heurística sólo añade un chip **"Sugerido"** para
destacar, nunca oculta la opción.

### P3 — Badge de transferencia de tres estados (web + mobile)

El badge de la lista colapsaba pares reales y patas `is_transfer`
huérfanas en un único chip "Transferencia", así que una pata sin
contraparte parecía ya enlazada. Se separa en tres estados con tooltip:

- **Deuda** — operación financiada.
- **Transferencia** — par interno emparejado (`transfer_pair_id`).
- **Sin pareja** — `is_transfer` pero sin `transfer_pair_id`; en tono de
  aviso para señalar que aún necesita enlazarse.

Reflejado en móvil para paridad.

### P4 — Agrupar las categorías de transferencia en el combobox (web)

El combobox de categoría agrupaba sólo en Ingresos/Gastos e ignoraba
`is_transfer`, así que las categorías de transferencia ("Transferencias",
"Transferencia a favor") aparecían mezcladas con ingresos/gastos reales.
El usuario las elegía sin darse cuenta de que crean una pata de
transferencia huérfana —la **puerta principal** por la que entran las
transferencias malformadas—. Ahora van a su propio grupo
**"Transferencias"**, para que se lea como "marcar un movimiento entre
cuentas", no como un gasto.

**Extensión (post-prueba del usuario): mismo combobox en el preview de
import.** El alta manual ya usaba el `CategoryCombobox` agrupado, pero el
preview de importación (`BankConceptMappingSection`) seguía con un
`<select>` nativo plano —la otra puerta por la que se categoriza, y la de
mayor volumen—. Se reutiliza el mismo componente por cada "concepto del
banco". Para encajarlo en la fila inline sin perder affordances, el
combobox gana tres props opcionales: `hideLabel` (el concepto es el label
accesible, oculto), `highlight` (conserva el borde de "sugerencia del
backend" que tenía el `<select>`) y `dense` (sin margen, para alinear en
la fila). El alta manual no cambia (props con default).

### P5 — Separar "A revisar" del canal "Errores" en imports (web)

El resumen del import fundía fallos reales y notas de revisión en un solo
`error_log` y los mostraba todos como "Errores", así que filas que **sí**
se importaron (p. ej. transferencias cuya dirección no se pudo
determinar) parecían fallos. Se particiona por el flag `review` existente
en un canal separado **"A revisar"** (tono de aviso, su propio contador,
enlace a `/transfers`). Sólo frontend: el backend ya etiqueta las
entradas de revisión y `rows_failed` ya las excluía.

### P6 — Lenguaje cotidiano en vez de jerga contable (web)

- "ordenante/beneficiaria" → **"de qué cuenta sale / a qué cuenta entra"**
  en el modal de marcar-como-transferencia (labels, placeholders, copy de
  validación).
- "excluir del cashflow / fuera del cashflow" → **"no cuenta como gasto ni
  ingreso del mes"** en los forms de categoría, el detalle de tx y el
  diálogo de deuda.

Copy puro; sin cambio de lógica.

### P7 — Declarar la dirección de transferencia explícita en móvil

El `ConvertToTransferBlock` de móvil derivaba la dirección de
`category.kind` y pedía una sola cuenta, así que una categoría mal mapeada
por un bank-mapping **invertía en silencio el saldo** de la cuenta sin
forma de corregirlo (el bug de signo de PHASE-28, ya cerrado en web con
dos slots explícitos). Ahora el usuario declara la dirección con un toggle
**"salió de aquí / entró aquí"** y elige la otra cuenta; `kind` sólo
siembra la sugerencia inicial (editable). Es un fix de integridad de
datos, no sólo UX: **el saldo deja de depender de en qué plataforma
categorizó el usuario**.

### P8 — Proteger las invariantes del par al editar la transacción (backend)

`update_transaction` asignaba campos directamente sin revalidar el par,
así que editar el importe/divisa/cuenta de una pata dejaba el par
descuadrado y el saldo silenciosamente mal (una pata emparejada requiere
**igual importe + divisa y cuentas distintas**, como en `link_manually`).
Esos edits se rechazan ahora con un **409** que dice al usuario que
desenlace primero; editar descripción/fecha/categoría sigue pasando.

## Flujo técnico — invariante del par en `update_transaction`

```
update_transaction(tx, payload):
  if tx.transfer_pair_id is not None:
      breaks_pair =
            payload.amount   cambia el importe   de la pata   ó
            payload.currency cambia la divisa    de la pata   ó
            payload.account_id la deja == cuenta de la contraparte
      if breaks_pair:
          raise HTTPException(409, "desenlaza el par antes de editar …")
  # description / date / category_id → siempre permitidos
```

## Archivos clave

### Backend
- `backend/app/modules/personal_finance/transfers/repository.py` — P1:
  `_TRANSFER_DISCOVERY_PATTERNS_SQL` + `_description_matches_any` en el
  query de sospechosas.
- `backend/app/modules/personal_finance/transactions/service.py` — P8:
  guard de invariante del par en `update_transaction` (409).
- `backend/tests/test_transfers.py` — +95 líneas: cobertura P1 (BIZUM /
  TRASPASO salen como sospechosas) + P8 (edit que rompe el par → 409,
  edits seguros pasan).

### Frontend — web
- `apps/web/components/transactions/category-combobox.tsx` — P4: grupo
  "Transferencias" + props `hideLabel` / `highlight` / `dense` para el uso
  inline en imports.
- `apps/web/components/imports/preview-step.tsx` — P4 (extensión): el
  selector de categoría por concepto del banco usa `CategoryCombobox` en
  vez del `<select>` plano.
- `apps/web/components/transactions/transaction-list.tsx` — P3: badge de
  tres estados.
- `apps/web/components/imports/result-step.tsx` +
  `packages/types/src/models/import.ts` — P5: canal "A revisar".
- `apps/web/components/transfers/convert-to-debt-dialog.tsx` +
  `apps/web/app/(app)/personal-finance/transactions/[id]/page.tsx` — P2:
  bloque deuda siempre visible + chip "Sugerido".
- `apps/web/components/transfers/mark-as-transfer-modal.tsx`,
  `apps/web/components/categories/category-form-modal.tsx`,
  `apps/web/app/(app)/settings/categories/page.tsx` — P6: copy cotidiano.

### Frontend — móvil
- `apps/mobile/components/transfers/convert-to-transfer-block.tsx` — P7:
  toggle de dirección + segunda cuenta.
- `apps/mobile/app/(modules)/personal-finance/(tabs)/transactions.tsx` —
  P3: badge de tres estados (paridad).
- `apps/mobile/components/transfers/convert-to-debt-block.tsx` +
  `apps/mobile/app/(modules)/personal-finance/transaction/[id].tsx` — P2:
  bloque deuda siempre visible.

## Endpoints modificados
- `GET /transfers/suspects` — P1: el detector reconoce ahora términos
  españoles (TRASPASO, BIZUM, envíos) además de `%transfer%`. Mismo
  contrato de response; sólo cambia el conjunto de candidatas.
- `PATCH /transactions/{id}` — P8: devuelve **409 Conflict** si el edit
  rompería la invariante de una pata emparejada (importe/divisa/cuenta).
  Edits que no la tocan siguen en 200.

## Migraciones
- Ninguna. La fase no toca el schema (reusa `is_transfer`,
  `transfer_pair_id` y el flag `review` ya existentes).

## Verificación
- [x] `pnpm lint` / `pnpm typecheck` verdes.
- [x] `pnpm test` — 67 web + 18 móvil verdes (incluye los nuevos de
      `transaction-list`, `category-combobox`).
- [x] `ruff` / `mypy app/` verdes (128 ficheros).
- [x] `pytest` backend completo — **560 verde** (incluye P1/P8).
- [ ] Prueba manual:
  - `/transfers` lista un BIZUM y un TRASPASO como sospechosas.
  - Editar el importe de una pata emparejada → 409 con mensaje de
    "desenlaza primero"; editar su descripción/fecha → OK.
  - Una tx no financiada muestra el bloque "convertir en deuda" (sin chip
    "Sugerido"); una que casa la heurística lo muestra **con** chip.
  - La lista distingue "Transferencia" (par) de "Sin pareja" (huérfana).
  - El combobox agrupa "Transferencias" aparte de Ingresos/Gastos.
  - Importar un extracto con una transferencia de dirección dudosa: la
    fila aparece en "A revisar", no en "Errores".
  - En móvil, convertir a transferencia con el toggle "salió / entró aquí"
    mueve el saldo en el sentido correcto.

## Decisiones tomadas
- **P3/P4 atacan la entrada, P1 la detección, P8 la corrupción posterior.**
  Las tres puertas por las que una transferencia se rompe (elegir la
  categoría sin querer, no detectar la sospechosa, descuadrar el par al
  editar) se cierran a la vez en lugar de parchear sólo síntomas.
- **Patrones de descubrimiento como lista compartida** (P1), no como
  cadena ILIKE suelta: añadir un término español nuevo es una línea, y el
  helper `_description_matches_any` ya estaba probado.
- **La dirección se declara, no se infiere** (P7) — generaliza a móvil la
  lección de PHASE-28: cuando una sola pista (category.kind) puede mentir
  y deriva el signo del saldo, se expone como input explícito.

## Limitaciones conocidas
- P8 rechaza el edit que rompe el par pero no ofrece desenlazar +
  re-editar en un solo paso; el usuario desenlaza y vuelve a editar.
- El detector de sospechosas (P1) prioriza recall sobre precisión: puede
  listar movimientos que sólo *mencionan* "transferencia" sin serlo. Es
  por diseño (bandeja de revisión), pero infla el contador.

## Próxima fase
Pendiente de definir.
