# Auditoría de integridad de datos — pendiente de verificar

**Fecha:** 2026-07-13
**Origen:** revisión manual del usuario sobre el drill-down de la categoría
"Tarjeta de crédito" (`/personal-finance/analysis/category/2b18c5c0-…`) →
auditoría completa cruzando la BD (`crisol`, usuario `membrij7@gmail.com`)
con el código.
**Estado:** ⏳ hallazgos abiertos. Ninguno corregido todavía.

> Leyenda de tipo:
> 🐛 **BUG-CÓDIGO** = defecto de software (fix en repo).
> 💾 **DATO** = inconsistencia en la BD del usuario (fix de datos + posible
> guardarraíl en código).
> 🔍 **VERIFICAR** = requiere contraste con el extracto bancario real antes
> de decidir si es dato malo o comportamiento correcto.

---

## Resumen ejecutivo

| # | Tipo | Título | Severidad | Impacto | Estado |
|---|------|--------|-----------|---------|--------|
| 1 | 🐛 BUG-CÓDIGO | Selector temporal desincronizado (UTC vs local) en drill-down de categoría | Media | UX rota: "Sin meses con datos en 2025", chip de año sin marcar, barra de meses vacía | ✅ **corregido** (2026-07-13; pendiente verificación manual + commit) |
| 2 | 💾/🔍 DATO | Falta la tarjeta (ADEUDO + cuota) en abril 2026 | Media | Hueco en la evolución mensual; reconciliación FIFO desplazada | ⏳ abierto |
| 3 | 💾 DATO | Doble conteo de gasto en compra financiada de Taxdown (239 €) | Alta | Una compra de 239 € computa ~500 € de gasto | ⏳ abierto |
| 4 | 💾 DATO | Pares de transferencia incoherentes en operaciones financiadas | Alta | Patrimonio neto y saldo BBVA desviados (doble descuento / signo invertido) | 🟡 **4a corregido** (2026-07-13) · 4b ⏳ abierto |
| 5 | 🔍 VERIFICAR | Posibles duplicados en BBVA (marzo) | Media | Hasta +900 € de salida fantasma / patas sobrantes | ⏳ abierto |
| 6 | 💾 DATO | Saldos de cuenta sin `opening_balance` real (BBVA −11k, Wise −5k) | Media | Patrimonio neto agregado incorrecto | ⏳ abierto |

**Lo que SÍ está correcto** (verificado, no tocar): suma del drill-down
(1.494,45 € = 5 cuotas), ticket medio, ADEUDOs correctamente excluidos del
gasto (`TRANSFER_OUT`), **cero** descuadres `category.kind` ↔ `flow` en todo
el ledger, y el ancla temporal del préstamo (22 cuotas pre-datos pagadas,
saldo gobernado por el cuadro).

---

## 1. 🐛 BUG-CÓDIGO — Selector temporal desincronizado (UTC vs local)

> **✅ CORREGIDO (2026-07-13).** Fix aplicado en
> `category/[id]/page.tsx:52-62`: el rango por defecto se construye con
> `Date.UTC` (idéntico a `pickYear` del TimeSelector y a `boundsForAnchor`).
> Verificado: `pnpm --filter @crisol/web typecheck` + `lint` + `test`
> (95/95) verdes. Barrido del resto del codebase confirmado: los demás
> constructores de rango (`transactions/page.tsx`, `boundsForAnchor`,
> `rangeForPeriod` web) ya usaban `Date.UTC`; el drill-down móvil usa una
> ventana deslizante (no alineada a año) → sin bug análogo. Pendiente:
> verificación manual del usuario en la app + commit.

**Síntoma (captura del usuario):** chip de año marca "2026", el display de
rango dice "01 Ene 2026 – 31 Dic 2026 · rango personalizado", pero el banner
dice **"Sin meses con datos en 2025"** y la barra de meses desaparece. Las
tres anomalías son el mismo bug.

**Causa raíz:** desfase entre construir el rango en hora **local** y leerlo
en **UTC**.

- `apps/web/app/(app)/personal-finance/analysis/category/[id]/page.tsx:53-56`
  construye el rango por defecto con hora local:
  ```ts
  const start = new Date(now.getFullYear(), 0, 1);            // local
  const end   = new Date(now.getFullYear(), 11, 31, 23, 59, 59);
  return { dateFrom: start.toISOString(), dateTo: end.toISOString() };
  ```
  En Madrid (UTC+1/+2) `new Date(2026, 0, 1).toISOString()` →
  `2025-12-31T23:00:00Z`.
- `apps/web/components/ui/time-selector.tsx:347` (`inferActiveRange`) lee en
  UTC → cree que el año activo es **2025** y que el rango NO es "año
  completo" → no marca el chip 2026, pinta "rango personalizado", y la barra
  de meses (`MonthBar`) busca meses de 2025 (inexistentes) → banner "Sin
  meses con datos en 2025".
- El `RangeDisplay`/`formatShortDate` (`time-selector.tsx:412-418`) usa
  getters **locales**, así que muestra "01 Ene 2026" y oculta el desfase.

**Regresión conocida:** el propio `time-selector.tsx:82-101` ya documenta que
los límites deben construirse con `Date.UTC` (lección de PHASE-27). El
drill-down de categoría reintrodujo la construcción en hora local.

**Fix propuesto:** en `category/[id]/page.tsx` construir el rango con
`Date.UTC(...)` igual que hace `pickYear`/`pickMonth` en el TimeSelector.
Comprobar también `analysis/page.tsx` y cualquier otra vista que fije rangos
por defecto. ~3 líneas.

**Verificación:** con navegador en huso ≠ UTC, entrar al drill-down de una
categoría → el chip del año debe quedar resaltado y la barra de meses
poblada.

---

## 2. 💾/🔍 DATO — Falta la tarjeta en abril 2026

**Hallazgo:** abril 2026 tiene 49 transacciones importadas, pero **no existe
ni el `ADEUDO MENSUAL DE TARJETA` ni la cuota `OPERACIÓN FINANCIADA CON
TARJETA`**. Todos los demás meses (Ene–Jun) los tienen.

Movimientos de tarjeta por mes (categoría "Tarjeta de crédito"):

| Mes | ADEUDO (`TRANSFER_OUT`) | Cuota (`OUT`) |
|-----|--------------------------|----------------|
| Ene | 824,77 / 43,93 / 166,00 | 373,93 |
| Feb | 264,84 | 200,46 |
| Mar | 4062,80 | 287,36 |
| **Abr** | **— (falta)** | **— (falta)** |
| May | 1278,34 | 316,35 |
| Jun | 990,02 (borrada) | 316,35 |

**Impacto:** la gráfica "Evolución mensual" salta Ene→Feb→Mar→[vacío]→May→Jun
(solo 5 puntos). Además la reconciliación FIFO marcó la cuota de abril como
pagada usando el cargo de mayo → los cuadros parecen al día pero falta un
cargo real en el ledger.

**Acción:** 🔍 verificar el extracto de abril. Dos posibilidades:
(a) el extracto se importó incompleto → reimportar; (b) el banco no pasó
adeudo ese mes → dato correcto, no tocar.

---

## 3. 💾 DATO — Doble conteo de gasto en compra financiada de Taxdown (239 €)

**Contradice el modelo de PHASE-38** ("la cuota es gasto porque la compra
original NO cuenta como gasto en ninguna otra parte"). Aquí la compra
original **sí** cuenta.

| Fecha | Movimiento | Flow | Categoría | Efecto |
|-------|------------|------|-----------|--------|
| 24/03 | TAXDOWN 239 € | `OUT` | Impuestos | **Gasto contado** ✓ |
| 24/03 | OPERACION FINANCIADA +239 € | `TRANSFER_IN` | Operacion financiada | neutro |
| May→Ene'27 | Cuotas 29 € × 9 (dentro del cargo mensual agregado) | `OUT` | Tarjeta de crédito | **Gasto contado** ✓ |

**Prueba cuantitativa:** el cargo mensual de tarjeta pasó de 287,36 € (marzo)
a 316,35 € (mayo) = **+28,99 €**, exactamente la cuota nueva de la compra
"mar-2026". Es decir, la compra de 239 € acaba computando ~500 € de gasto
(239 € en marzo como "Impuestos" + 261 € repartidos en cuotas).

**Origen del defecto:** la compra se registró como un `OUT` normal ("Impuestos")
Y además como creación de deuda a plazos. El flujo de "convertir en operación
financiada" debería dejar la compra original **neutra** (o el abono contar
como `IN` que compensa), no como gasto.

**Acción:** decidir con el usuario el modelo canónico:
- Opción A: la compra original neutra (`TRANSFER_OUT`) y las cuotas como gasto
  (consistente con PHASE-38). Requiere recategorizar la tx de 239 €.
- Opción B: la compra original como gasto y las cuotas neutras. Inconsistente
  con PHASE-38 para el resto de compras a plazos.
- Data-fix puntual + posible guardarraíl en el flujo convert-to-financed.

Relacionado: `[[project_transfers_money_model_redesign]]` /
lección PHASE-38 sobre "qué es un pago de deuda".

---

## 4. 💾 DATO — Pares de transferencia incoherentes en operaciones financiadas

Las patas de "Deuda contraída desde BBVA" ↔ su contraparte en BBVA no
mantienen el invariante OUT↔IN.

| Cuenta hija | Importe | Pata hija | Pata BBVA (par) | Estado |
|-------------|---------|-----------|-----------------|--------|
| Compra financiada | 824,77 € (ene) | `TRANSFER_OUT` | `TRANSFER_OUT` ❌ | **ambas restan** |
| Compra financiada mar-2026 | 239,00 € | `TRANSFER_OUT` | `TRANSFER_IN` ✓ | correcto |
| Compra financiada ingles | 215,99 € (31/05) | `TRANSFER_OUT` | `TRANSFER_IN` sobre WESTERN UNION ⚠️ | signo dudoso |

**4a — Compra financiada 824,77 € (par OUT↔OUT):** BBVA pierde 824,77 € Y la
deuda sube 824,77 € → el patrimonio neto se descuenta **dos veces**
(−1.649,54 € en lugar de neutro). Un par de transferencia válido es OUT↔IN.

> **✅ CORREGIDO (2026-07-13).** Data-fix: la pata BBVA
> (`e6856b9d-2cc3-4520-bd5c-9d38a906e2e6`, "OPERACIÓN FINANCIADA") volteada de
> `TRANSFER_OUT` → `TRANSFER_IN`, para que el carve-out H-02
> (`asset_leg_of_debt_pair & is_inflow → 0`) la neutralice, idéntico al caso
> correcto de 239 €. La pata pasivo (`4f4867f9…`, "Deuda contraída") sin tocar
> → la deuda sigue en 824,77 €. Efecto verificado: **BBVA −11.777,93 →
> −10.953,16 €**, deuda intacta, par ahora OUT↔IN. Barrido confirmó que era la
> ÚNICA pata-activo `TRANSFER_OUT` emparejada con un pasivo. Reversible:
> `UPDATE … SET flow='TRANSFER_OUT' WHERE id='e6856b9d…'`.
>
> Follow-up de código (guardarraíl, no hecho): el flujo de convertir a
> operación financiada debería forzar el par canónico OUT↔IN (lección
> PHASE-28 sobre dirección explícita), para que no vuelva a colarse una pata
> con el signo invertido.

**4b — Compra financiada ingles 215,99 €:** la pata de BBVA es un movimiento
`WESTERN UNION-EUR` marcado `TRANSFER_IN` (fecha 31/05). La app afirma que ese
día **entraron** 215,99 € en BBVA. Nota adicional: hay OTRO `WESTERN UNION-EUR`
de 243,99 € el 26/05 marcado `OUT` (categoría "Ingles"). Si el movimiento real
era un cargo, el saldo de BBVA está inflado en +215,99 € (desviación de
~431,98 € entre ambos Western Union).

**Acción:** normalizar los pares a OUT↔IN; verificar el signo real de los
Western Union contra el extracto. Guardarraíl: el flujo de creación de deuda
a plazos debería forzar el par canónico (la lección PHASE-28 sobre dirección
explícita aplica).

---

## 5. 🔍 VERIFICAR — Posibles duplicados en BBVA (marzo)

Requiere contraste con el extracto antes de borrar nada (el hash de import
permite deliberadamente dos filas idénticas del mismo fichero — ver
`_compute_hash` con `occurrence`, `imports/service.py:1285`).

**5a — 12/03, dos cargos idénticos de 900 €** ("TRANSFERENCIA REALIZADA
U13407774 / Jose A…"), `TRANSFER_OUT`, sin par, importados en el mismo lote
(28-jun), pero con **hashes distintos** (`910fd67f…` y `dd2a9b14…`) → el
sistema los trató como dos líneas legítimas. Si el extracto solo traía una,
sobra −900 € de salida fantasma. (El mismo día hay además un cargo de 300 €
del mismo emisor, presumiblemente legítimo.)

**5b — 18/03, dos cargos de 1.000 €** hacia Interactive Brokers, cada uno
emparejado con un ingreso manual de 1.000 € en IB (`TRANSFER_IN`). Si solo
hubo una transferencia de 1.000 €, sobra una pata en cada lado (BBVA e IB).

**Acción:** el usuario confirma contra su extracto de marzo; si son
duplicados, soft-delete de la fila sobrante (y su par).

---

## 6. 💾 DATO — Saldos de cuenta sin `opening_balance` real

Saldos calculados por `flow` + `account.nature` (ADR-0004):

| Cuenta | Nature | opening_balance | Saldo calculado (app) | Nota |
|--------|--------|-----------------|-----------------------|------|
| BBVA | ASSET | 0,00 | **−10.953,16 €** (era −11.777,93 antes de arreglar #4a) | banco en −11k con apertura 0 → falta fijar saldo inicial |
| Wise | ASSET | −5.000,00 | 0,00 | apertura negativa como apaño para cuadrar a 0 |
| Trade Republic | ASSET | 8.427,49 | 4.013,44 | revisar |
| Interactive Brokers | ASSET | 1.102,00 | 0,00 | — |

> **Corrección (2026-07-13):** el saldo REAL que computa la app es
> **−11.777,93 €**, no −11.322,94 € (cifra ingenua del primer pase). La
> diferencia (454,99 €) son dos patas-activo de pares de deuda que el
> carve-out **H-02** de `signed_amount_expr` neutraliza a 0 (las de 239 € y
> 215,99 €, `TRANSFER_IN` emparejadas con pasivos), mientras el SQL ingenuo
> del primer pase las sumaba como ingreso. Verificado replicando la expresión
> exacta con el join al par.

**6a — BBVA −11.777,93 €:** con `opening_balance = 0`, un banco en −11,8k no es
la realidad del usuario. **No es un bug: es el artefacto esperado de no haber
fijado el saldo inicial** — los imports arrancan en enero 2026 desde 0 y el
usuario ya tenía un saldo positivo real en BBVA antes. La herramienta correcta
es "Cuadrar saldo" (`POST /accounts/{id}/reconcile`), que fija
`opening_balance = saldo_real − Σmovimientos`. Como `position_history` aplica
el `opening_balance` en TODOS los puntos de la serie (no usa
`opening_balance_date`), cuadrar reancla toda la serie de patrimonio, no solo
el punto de hoy. **Todo el patrimonio neto agregado hereda este error hasta
que se cuadre.**

Matiz de orden: la parte del −11,8k que es artefacto de apertura (dominante)
la resuelve cuadrar; la parte que es movimiento erróneo (#4a ≈ 824,77 €, más
posibles duplicados #5 ≈ 900–1900 €) NO la resuelve cuadrar — la absorbe en el
`opening_balance` y reaparece como deriva si luego se corrigen los bugs. Ver
"Orden de ataque".

**6b — Wise:** `opening_balance = −5.000 €` en cuenta de activo (apaño para
dejarla a 0 tras la transferencia de 5.000 € de enero). Además hay 4
transferencias huérfanas hacia Wise (60 + 60 + 30 + 60 = **210 €**,
`TRANSFER_OUT` sin pata de entrada). Si ese dinero está en Wise, la app lo
pinta a 0.

**Acción:** fijar `opening_balance` real de BBVA y Wise con "Cuadrar saldo";
emparejar o revisar las patas huérfanas de Wise.

> **✅ Patas huérfanas Wise resueltas (2026-07-14):** tras el reimport eran **6**
> movimientos "Transferencia realizada Wi…" (categoría *SCL*, 30–60 €, 330 € total),
> `TRANSFER_OUT` sin contraparte. Decisión del usuario: son **gasto real a un
> tercero externo**, no traspaso a su Wise. Reclasificados `flow TRANSFER_OUT → OUT`
> (data-fix auditado, ver [ADR-0005](../decisions/0005-simplify-transfers-flow-driven.md)).
> Ahora cuentan como gasto en análisis y presupuesto (antes se contradecían). El
> `opening_balance` de Wise y la transferencia de 5.000 € de enero siguen aparte.

> **🚧 En curso vía PHASE-39 (2026-07-13):** en lugar de cuadrar a mano, se
> implementó la captura de la columna Saldo del extracto + auto-anclaje del
> `opening_balance` al confirmar imports (ver
> [`phases/phase-39-statement-balance-anchor.md`](../phases/phase-39-statement-balance-anchor.md)).
> El plan del usuario es REIMPORTAR el histórico completo: cada import
> anclará el saldo a lo que declara el banco (BBVA a 30/04/2026 = 5.817,76 €
> según su captura → opening implícito ≈ 12.017 €). Wise/duplicados (#5)
> siguen pendientes de verificación manual.

---

## Orden de ataque sugerido

1. **#1** — fix de código trivial (UTC), sin riesgo de datos.
2. **#3 y #4** — tocan el modelo de dinero, arreglo claro; decidir modelo
   canónico con el usuario antes del data-fix.
3. **#2, #5, #6** — requieren que el usuario contraste contra su extracto
   bancario antes de modificar datos.

## Notas de método

- Todos los saldos y agregados se recomputaron directamente en la BD con la
  misma matemática que la app (`flow` + `nature`), no leyendo la UI.
- La BD del usuario tiene 403 tx vivas (476 totales) en 2026 y 0 vivas en
  2025 → el histórico real arranca en enero 2026.
- Este documento NO corrige nada: es el inventario para la sesión de
  saneamiento.
