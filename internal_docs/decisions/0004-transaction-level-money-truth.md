# ADR-0004 — La verdad del dinero vive en la transacción, no en la categoría

**Estado**: aceptada (implementada en PHASE-34; en `main`, squash `5215a80`,
2026-07-04)
**Fecha**: 2026-06-27 (propuesta) · 2026-06-29 (aceptada)
**Fase**: PHASE-34 — ver [`phases/phase-34-transaction-flow.md`](../phases/phase-34-transaction-flow.md)

## Contexto

Toda la matemática del dinero se **deriva de la categoría** de cada
transacción:

- **Saldo** (`accounts.repository.get_balances_for_user`): el signo de
  `amount` (siempre positivo en BD) se reconstruye con un `CASE` sobre
  `category.kind` + `account.nature` (`EXPENSE → −`, `INCOME → +`, sin
  categoría `→ 0`).
- **Cashflow** (`dashboard.repository`): income/expense por `category.kind`,
  excluyendo `category.is_transfer = TRUE`.

Una sola categoría equivocada rompe a la vez el **signo** y la
**clasificación**, en silencio. El import ya conoce el signo del extracto
al parsear (`_parse_amount_signed`) pero lo descarta con `abs()`.

### Los DOS doble-conteos medidos (datos reales, usuario membrij7)

El usuario reportó "el gasto del mes parece duplicado". Confirmado, y la
causa es **doble**:

1. **Transferencias contadas como gasto.** Enero 2026: 5.060 € (73% del
   gasto del mes) eran traspasos a Wise metidos en una categoría de gasto
   normal (`SCL`, `is_transfer=false`).
2. **Liquidación de tarjeta contada como gasto.** `ADEUDO MENSUAL DE
   TARJETA`: 209,93 € (ene) + 264,84 € (feb). El usuario importa el
   extracto de la cuenta **y** el de la tarjeta por separado para
   catalogar cada compra; el ADEUDO es la **liquidación mensual de esas
   mismas compras**, así que contarlo **duplica** lo ya contado compra a
   compra. Con ambos, enero se infla un **76%**.

Más un tercer fallo de integridad (no infla gasto, corrompe saldo):
transferencias con la **dirección invertida** (4.000 € enviados
categorizados como ingreso → +4.000 en vez de −4.000).

### Por qué los parches anteriores no bastan

PHASE-23.1 / 28 / 32 atacan síntomas del mismo defecto de raíz: **la
categoría es la fuente de verdad del dinero.** Mientras lo sea, cualquier
mecanismo de categorización puede producir un bug de dinero con un solo
fallo.

## Decisión

**El signo y la naturaleza de cada movimiento se almacenan en la
transacción y son la fuente de verdad. La categoría es 100% descriptiva.**

### Núcleo — columna `transactions.flow`

Enum a nivel de transacción: `IN | OUT | TRANSFER_IN | TRANSFER_OUT`.

| `flow` | Dirección | ¿Cuenta en cashflow? |
|--------|-----------|----------------------|
| `IN` | entra | sí → **ingreso** |
| `OUT` | sale | sí → **gasto** |
| `TRANSFER_IN` | entra | **no** (neutro) |
| `TRANSFER_OUT` | sale | **no** (neutro) |

- `amount` sigue **positivo**; el signo lo aplica la query desde `flow`.
- **Saldo** = `flow` + `account.nature` (nunca la categoría):
  `ASSET`: `IN → +`, `OUT → −`. `LIABILITY`: invertido.
- **Cashflow**: `gasto = Σ amount where flow = OUT`,
  `ingreso = Σ amount where flow = IN`. `TRANSFER_*` se excluyen por el
  propio movimiento.
- `category.kind` queda como hint de agrupación de UI; `category.is_transfer`
  obsoleto. **Las transferencias dejan de ser categorías.**

### Refinamientos (validados por análisis multi-agente — veredicto "refinar")

1. **El signo lo manda el extracto — invariante DURO**, no nota al margen.
   En import, `flow` IN/OUT sale de `_parse_amount_signed`, nunca de la
   categoría ni de `infer_transfer_kind` (que queda como último recurso en
   alta manual). Es el mayor win de facilidad.
2. **Política explícita para `sign=0`** (muchos CSV/XLSX no traen signo,
   verificado en `service.py:1101`): con signo es ley y cero decisiones;
   sin signo, la fila va a una **bandeja de confirmación** con default
   conservador, nunca se adivina la dirección en silencio.
3. **El usuario NUNCA elige TRANSFER_IN/OUT** (reintroduciría el bug de
   dirección). Solo dos controles ortogonales: segmento
   **[Gasto] [Ingreso] [Entre mis cuentas]** + cuenta destino. Declara
   **cuentas**, no direcciones.
4. **El preview de import muestra DINERO FIRMADO**, no strings. Mover la
   resolución de `flow` de `_process_and_persist` (commit) a `run_preview`;
   ampliar `ImportPreviewRow` con `flow`+`signed_amount`. Cada fila pinta
   "−45,20 € gasto" / "↔ traspaso a Wise (neutro)" con badge "Posible
   transferencia" / "Posible pago de tarjeta", accionable in-situ.
5. **Reescribir saldo + ahorro-neto en el MISMO PR**
   (`get_balances_for_user` y `get_net_savings_movement_for_account`
   derivan hoy de la categoría en paralelo — bomba latente documentada en
   el repo, líneas 256-264).

### Modelo de tarjetas y deuda (decisión del usuario: cuentas exactas + vista unificada)

La tarjeta de crédito es una **cuenta-pasivo** (saldo y deuda exactos),
pero la UI presenta **siempre un único libro** (todas las cuentas
fusionadas, con filtros): el usuario nunca navega cuenta por cuenta. La
trazabilidad no se sacrifica; la separación queda bajo el capó.

Reglas de clasificación por tipo de línea del extracto:

| Línea | Qué es | `flow` / tratamiento |
|-------|--------|----------------------|
| `PAGO CON TARJETA` (débito) + compras del extracto de crédito | Compras reales | `OUT` (**gasto**) |
| **`ADEUDO MENSUAL DE TARJETA`** | Liquidación de compras ya contadas | **`TRANSFER_OUT`** banco→tarjeta (**no gasto** — evita el 2º doble-conteo) |
| `OPERACIÓN FINANCIADA CON TARJETA` (cuota fraccionada) | Pago de una compra ya contada como gasto | **`TRANSFER_OUT`** (pago de deuda, **no gasto**; interés absorbido — el usuario no lo mide aquí) |
| `OPERACIÓN FINANCIADA` (ingreso) | Evento de financiación (crea deuda) | Neutro (financiación, no ingreso real) |
| `BIZUM` | Pago (normalmente a comercio) | `OUT` (**gasto**) por defecto; override manual a transferencia si es a cuenta propia |
| `TRANSFERENCIA` a Wise/TR/IBKR | Entre cuentas propias | `TRANSFER_*` (**no gasto**) |
| `CARGO AMORTIZACIÓN PRÉSTAMO` | Cuota del préstamo | `OUT` (**gasto** entero, interés incluido — decisión del usuario); el saldo del préstamo se lleva aparte en el módulo deuda para patrimonio |

**Invariante preservado** (PHASE-24 convert-to-debt): la "pata ASSET de un
par financiado" se reexpresa en `flow`+`nature`, no se inventa un 5º valor
de enum. Las operaciones financiadas genuinas (deuda con plan) viven en el
módulo deuda; sus cálculos precisos de interés siguen ahí.

### Vista unificada (requisito de primera clase)

El listado de transacciones muestra **por defecto todas las cuentas
juntas**, con filtros por cuenta/método. Pagar la tarjeta o traspasar a
Wise se ve en el mismo libro, marcado como movimiento interno. La "cuenta
tarjeta" existe para la exactitud del saldo y la deuda, pero no es un
destino de navegación obligatorio.

## Consecuencias

### Positivas
- Los **dos** doble-conteos y la corrupción de saldo se vuelven
  **estructuralmente imposibles**: el saldo cuadra con el extracto (signo
  del banco) y ni transferencias ni liquidación de tarjeta cuentan como
  gasto (lo decide el movimiento, no su etiqueta).
- **Un error de categoría deja de costar dinero**: solo cambia el grupo
  del donut.
- **UX más simple y unificada**: un solo libro; al crear, [Gasto]/[Ingreso]/
  [Entre mis cuentas]; nunca eliges dirección ni categoría-trampa.
- Cierra la familia de lecciones PHASE-23.1 / 28 / 32.

### Negativas / coste
- Refactor transversal (migración, queries de saldo/cashflow, import,
  forms, ~560 tests BE, FE que asume importe positivo). Riesgo de
  regresión de dinero → **golden tests** obligatorios antes de tocar UI.
- El backfill de `flow` derivado de `kind`/`is_transfer` **reproduce** los
  bugs en datos históricos → backfill en dos pasadas + data-fix auditado.
- La vista unificada y el preview firmado añaden trabajo FE a fases que el
  ADR v1 planeaba como puro backend.

## Plan por fases (PHASE-34)

| Fase | Alcance | ¿Cambia comportamiento? |
|------|---------|--------------------------|
| **34.0** *(paliativo, primero)* | Guardarraíl import: una descripción de transferencia o un `ADEUDO`/liquidación no caen en gasto sin confirmar. Frena los dos doble-conteos ya. Ortogonal a `flow`. | Sí (frena fugas) |
| **34.1** | Columna `flow` + migración backfill en 2 pasadas (derivar de kind/is_transfer; corregir transfers y ADEUDO obvios por signo+descripción+pareja) + data-fix auditado de las filas rotas del usuario. Sin tocar queries. Test: backfill ≡ derivación actual salvo correcciones. | No |
| **34.2** | Saldo + ahorro-neto + cashflow leen de `flow`+`nature` (MISMO PR). Preservar carve-out pata-ASSET; respetar filtro `currency==account.currency`. Golden tests verdes antes de avanzar. | **Sí — arregla los bugs** |
| **34.3** | Import escribe `flow` directo. Invariante duro: IN/OUT = signo del extracto. `sign=0` → bandeja. Detección conservadora: `ADEUDO`/cuota fraccionada → `TRANSFER_OUT` (pago de tarjeta), `BIZUM` → `OUT`, `TRANSFERENCIA` → `TRANSFER_*`. Alta manual escribe `flow`. | Backend |
| **34.4** | Las transferencias dejan de ser categorías. Reasignar históricos a `flow`. `category.kind` solo agrupación. | Datos |
| **34.5a** | Preview de import con dinero firmado + badges "Posible transferencia/pago de tarjeta" + bandeja de excepciones dentro del wizard. Saltar el mapeo manual de columnas en PDF/XLSX smart. | **Sí (UX)** |
| **34.5b** | Forms web+mobile unificados ([Gasto][Ingreso][Entre mis cuentas]); **vista de libro unificada** (todas las cuentas juntas + filtros); listas/KPI/saldos leen `flow`. Probar manualmente + go-ahead del usuario antes de commit. | **Sí (UX)** |
| **34.6** | Limpieza: quitar `category.kind`/`is_transfer` de la matemática del dinero; borrar derivación vieja; reducir `/transfers` a red de seguridad. | No |

## Decisiones del usuario (cerradas en esta sesión)

- Extractos BBVA **traen el signo** (cargo −, abono +) → caso común a cero
  fricción.
- Default de alta manual: **[Gasto]**.
- Arranque del rollout: **paliativo 34.0 primero**.
- **Bizum** → gasto por defecto (override manual a transferencia).
- **Tarjeta**: cuentas exactas + **vista unificada** (no navegar por
  separado). `ADEUDO` y cuotas fraccionadas → traspaso (no gasto).
- **Préstamo**: cuota entera = gasto (interés incluido), saldo aparte.
- Interés de tarjeta: no se mide en cashflow (el módulo deuda lo calcula
  fino si se necesita).

## Puntos a validar con fixtures reales durante 34.3/34.5

- Mecánica exacta de `OPERACIÓN FINANCIADA` (ingreso) ↔ cuota fraccionada:
  confirmar que una compra financiada no se cuenta dos veces (compra +
  cuota) con un extracto real delante.
- `BIZUM ENVIADO: [persona]` vs `BIZUM COMPRA: [comercio]`: ambos gasto por
  defecto; ¿el primero merece sugerencia de "¿transferencia?".
- Transferencia entre dos cuentas propias **ambas importadas** (matcher
  cross-import) vs una sola pata marcada como neutra.
- Multi-divisa (BBVA EUR → IBKR USD): `get_balances_for_user` solo agrega
  `currency==account.currency`; definir si esas patas caen a bandeja.

## Alternativas consideradas

1. **Solo guardarraíl** (es ahora la fase 34.0, paliativa, no la solución).
2. **Importe con signo** en `amount`: más invasivo en display; descartado a
   favor de `flow` + `amount` positivo.
3. **Tarjeta sin cuenta (un solo libro, saldo aproximado)**: descartada por
   el usuario a favor de cuentas exactas con vista unificada.
4. **No importar el extracto de tarjeta**: pierde trazabilidad compra a
   compra; descartada.

## Referencias

- `internal_docs/lessons.md` — PHASE-23.1, 28, 32 (la familia que cierra).
- `internal_docs/phases/phase-33-transfers-ux.md` — overhaul de UX previo.
- `accounts/repository.py` (`get_balances_for_user`, `get_net_savings_movement_for_account`).
- `dashboard/repository.py` (`_exclude_transfer_kind`).
- `imports/service.py` (`_parse_amount_signed`, `_parse_row`, `run_preview`).
