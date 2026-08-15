# PHASE-47 — Recomposición de deuda: bandeja, detalle por deuda y costura con finanzas personales

**Estado**: 📋 planificada
**Origen**: feedback directo del usuario en dos capas: (1) "veo el módulo algo
complejo de utilizar"; (2) "el manejo desde finanzas personales a deuda me
parece engorroso". Diagnóstico verificado contra el repo (2026-08-10,
commit 6e7a766).
**Depende de**: PHASE-36 (matcher de cuotas + MUX `resolve_liability_
outstanding`), PHASE-45 (motor de sugerencias `count_registered_outflows`,
adopción de cargos), PHASE-46 (par de financiación), ADR-0003 (pasivos
opt-in), ADR-0004 (la dirección se declara, no se adivina).
**Sucesora**: PHASE-48 = liquidación anticipada (el plan ya escrito en
`phase-45-debt-early-settlement.md` se **renumera a 48** — sin cambios de
contenido; su cola de "posible liquidación" es una fila más de la bandeja
de esta fase).

---

## 0. Diagnóstico (por qué es complejo y engorroso)

1. **Observatorio sin verbos**: `/debt` muestra (13 componentes, 4 gráficos
   del mismo agregado) pero las acciones viven fuera (amortization-panel y
   convert-to-debt en transfers, financing-matches en transactions, pagar/
   editar cuota…). Seis superficies-verbo; el usuario debe recordar cuál
   ejecuta qué.
2. **La costura está expuesta**: cada evento real de deuda llega disfrazado
   de transacción y la traducción transacción→evento la hace el usuario a
   mano, eligiendo verbo de memoria.
3. **Automatización intermitente**: el emparejador actuó 6 meses y en julio
   dejó 4 cargos sueltos EN SILENCIO (documentado en PHASE-45). Una
   automatización que a veces calla obliga a vigilar siempre.
4. **Unidad mental equivocada**: el usuario piensa en "la hipoteca", "el
   aplazado de junio"; la página solo ofrece agregados. No existe vista de
   detalle por deuda.
5. **Un evento, cuatro superficies**: "financié un recibo" = settings
   (pasivo) + plan + vincular desde transacciones + verificar en /debt.

## 1. Principios de la fase (no negociables)

- **El sistema propone, el usuario adjudica.** Las decisiones conceptuales
  (cuadro/sin-cuadro, capital-vs-pagado, cuenta-como-gasto) llegan
  pre-resueltas por los motores existentes, con su motivo escrito; el
  usuario acepta o cambia. ADR-0004 se respeta: declarar sigue siendo del
  usuario — iniciar y traducir deja de serlo.
- **La redacción del concepto JAMÁS discrimina** (lección PHASE-46: el
  mismo hecho llegó como "Operacion financiada" y como "Recibo anterior").
  Discriminan (a) la **estructura del dinero** y (b) el **estado del
  sistema** (compras registradas, planes vivos).
- **Silencio-con-rastro**: el sistema o actúa dejando marca visible y
  deshacer, o deja el item en la bandeja. El silencio mudo deja de ser un
  estado posible.
- **Solo interrumpe cuando la aritmética no cierra.** El mes normal fluye
  solo.
- ADR-0003 intacto: una tarjeta en modo "pago todo cada mes" no necesita
  cuenta pasivo; el sistema no da la lata para crearla.

---

## 47.0 — Prerequisito: consolidar el dominio deuda (H2)

Movimiento mecánico, **sin cambio de comportamiento**:

```
accounts/debt_health.py            → debt/health.py
accounts/debt_history.py           → debt/history.py
accounts/debt_reconciliation.py    → debt/reconciliation.py
accounts/amortization.py           → debt/amortization.py
accounts/installments_model.py     → debt/installments_model.py
accounts/installments_repository.py→ debt/installments_repository.py
```

- URLs `/accounts/debt-*` e `installments` se mantienen con **alias
  deprecado** (redirect interno) — sin ruptura de contrato; el router
  nuevo vive en `/debt/*`.
- `accounts/service.py` se parte: lo de cuentas+saldos queda; lo de
  amortización/cuotas se va con su dominio.
- Imports actualizados; **cero cambios de lógica** (diff funcional vacío);
  golden de `debt_health` y `get_balances` idéntico antes/después.

**Salida**: `grep -rn "debt\|amort\|install" accounts/` devuelve solo el
consumo vía `debt/` público. Tests verdes sin tocar asserts.

---

## 47.1 — Backend: cascada de clasificación + invariante de conservación

### 47.1.a Motor puro `debt/classification.py`

Entrada: transacciones candidatas (OUT/TRANSFER_OUT de cuentas corrientes +
pares detectables) + estado (planes vivos con cuotas esperadas, compras
registradas por tarjeta, historial de cierres). Salida:
`DebtInboxItem(transaction_ids, kind, proposal, reason, confidence)`.

**Cascada — orden determinista, primer match gana**:

| # | Detector | Caso | Propuesta |
|---|---|---|---|
| 1 | Cargo casa con **cuota esperada** de un plan vivo (importe ±tolerancia, ventana de fecha) — reutiliza matcher PHASE-36 | C — cuota | "Cuota {n} de {plan}" · cuadro manda · sugerencia gasto del motor PHASE-45 |
| 2 | **Par neto-cero**: IN y OUT de importe igual (±0,01) en ventana ≤ `PAIR_WINDOW_DAYS` — generaliza el detector de PHASE-46 | B — financiación nace | "Financiación de recibo → crear plan" (asistente 47.4.b) |
| 3 | Cargo casa con **cierre de ciclo de tarjeta**: importe ≈ Σ compras registradas de esa tarjeta en el ciclo (§47.1.b) | A — recibo autoliquidable | **AUTO-VINCULA con rastro** ("cuadra con tus compras del ciclo" + deshacer). NO aparece en pendientes. TRANSFER neutro, no gasto, no crea deuda |
| 4 | Importe ≥ `SETTLEMENT_GUARD_K` × cuota esperada del plan | Posible **liquidación anticipada** | Item "Revisar" → PHASE-48 (hasta entonces: clasificación manual asistida, jamás auto-match a una cuota) |
| 5 | Cierre de ciclo con **hueco**: Σ compras − cargo > tolerancia | B' — financiación implícita | "Pagaste {cargo} de {Σ} — el hueco {Δ} ¿es una financiación?" con el importe exacto |
| 6 | Nada casa | Pendiente genérico | Opciones con el porqué de cada una (motor PHASE-45) |

**Regla de no-silencio (property test)**: toda transacción que entra en la
cascada acaba en exactamente uno de dos estados — actuada-con-rastro
(reversible) o en bandeja. Nunca "nada".

### 47.1.b Invariante de conservación del ciclo de tarjeta

```
Σ compras registradas del ciclo = recibo pagado + importe financiado
```

- **Ciclo** = intervalo entre cargos de cierre consecutivos de la misma
  tarjeta (aprendido del propio historial: los 6 meses que el emparejador
  sí casó son la serie de entrenamiento). Sin historial → ventana por
  defecto configurable.
- El invariante se **calcula y se muestra** cada mes en el detalle de la
  tarjeta: verde si cierra (±`CYCLE_TOLERANCE_EUR`), y si no cierra, el
  hueco cuantificado alimenta el detector #5.
- Tarjeta **sin compras registradas**: el invariante no aplica; el cargo va
  a bandeja con la sugerencia ya existente ("cuenta como gasto: sí — es el
  único rastro"), coherente con PHASE-45.

### 47.1.c API

```
GET  /debt/inbox                    → items ordenados (auto-actuados con
                                      rastro al final, colapsados)
POST /debt/inbox/{id}/accept        → ejecuta la propuesta (motor existente
                                      de PHASE-45/36 según kind)
POST /debt/inbox/{id}/resolve       → variante elegida por el usuario
POST /debt/inbox/{id}/dismiss       {reason} → "no es deuda" (auditado)
POST /debt/inbox/{id}/undo          → revierte una acción (auto o manual)
GET  /debt/{account_id}/detail      → cuadro condensado + movimientos +
                                      pendientes de ESA deuda + invariante
                                      de ciclo si es tarjeta
```

Todo reversible y con rastro (patrón PHASE-36). La bandeja NO inventa
motores: **compone** matcher-36 + sugerencias-45 + par-46 + guard-48 bajo
un orden único.

---

## 47.2 — Web: la bandeja en `/debt`

- Posición: **primera sección** de la página. Contador en el título.
- Item: descripción del hecho + propuesta + motivo en una línea +
  `[Aceptar] [Cambiar]`. "Cambiar" abre el flujo unificado (47.4.a) con la
  propuesta precargada.
- Sección colapsada "Resuelto automáticamente este periodo" (caso A y
  cuotas casadas): línea por acción con su rastro y `[Deshacer]`.
- Estado vacío explícito: "Todo cuadra — {n} movimientos verificados este
  periodo" (la confianza también se muestra cuando no hay trabajo).
- Móvil: paridad mínima = ver bandeja + aceptar/deshacer (cambiar/asistente
  pueden quedar web-only en esta fase, marcado).

## 47.3 — Web: detalle por deuda `/debt/[account_id]`

La unidad mental correcta por fin tiene página:

- Cabecera: nombre · **principal pendiente** · cuota · próximo cargo ·
  chip estado.
- Cuadro condensado (componente existente `schedule-condensed`).
- Movimientos de ESA deuda (filtro del movements-card existente).
- **Pendientes de esa deuda** (subset de la bandeja).
- Tarjetas: el invariante del ciclo (47.1.b) con su verde/hueco.
- Acciones de la deuda: pagar cuota, editar plan, (48: liquidar).
- La lista de `/debt` se adelgaza: una línea por deuda → navega al detalle.
  El donut desaparece (el peso va como columna/sublabel en la fila).

## 47.4 — Flujos: uno por evento, no un diálogo por mecanismo

**a. "Cruzar con deuda"** — flujo único con ramas que absorbe los seis
diálogos actuales. Entrada desde: bandeja, transacción, detalle de deuda.
Pantalla única: deuda destino (propuesta) + las 3 decisiones conceptuales
**pre-resueltas** con su porqué expandible (motor 45) + un tap para
aceptar. Los diálogos viejos (`amortization-panel`,
`convert-to-debt-dialog`, `financing-matches-section` como flujo aparte,
`installment-pay-buttons` sueltos) redirigen aquí y se retiran al final de
la fase (barrido de muertos).

**b. "Nueva financiación"** — asistente de un evento en una pasada: desde
la transacción (o el par detectado): confirma importe/plazo/TIN →
**crea el pasivo + genera el cuadro + vincula el par y los cargos** de una
vez. Fin de la excursión por cuatro superficies. Reutiliza el alta de
plan existente (24.x) por debajo.

## 47.5 — Simplificación de superficie

- **Un gráfico**: evolución mensual con selector de rango. Se borran
  `debt-daily-evolution` (la deuda se mueve por cuotas — el diario es
  ruido) y `debt-trend-chart` (redundante); `debt-composition-donut`
  plegado a la lista.
- `effort-ratio-section` (359 LoC) → strip compacto de 1 línea (veredicto +
  ratio + banda); el detalle completo ya vive en el dashboard-summary.
- Barrido de componentes huérfanos tras 47.4 (re-ejecutar el grep de
  imports, no asumir la lista).

---

## Config

| Variable | Default |
|---|---|
| `DEBT_CYCLE_TOLERANCE_EUR` | `2.00` |
| `DEBT_PAIR_WINDOW_DAYS` | `3` |
| `DEBT_QUOTA_MATCH_TOLERANCE_EUR` | la vigente de PHASE-36 |
| `DEBT_SETTLEMENT_GUARD_K` | `1.8` |

## Tests

| Caso | Verifica |
|---|---|
| Cascada determinista | Mismo input → mismos items, mismo orden; primer-match-gana (una cuota que también forma par → gana #1) |
| **Regresión julio (datos reales)** | Los 4 ADEUDO (406,33 · 384,38 · 164,94 · 143,99) → items C propuestos, no silencio; el par +700,26/−700,26 → item B "crear plan" |
| Caso A silencioso | Recibo ≈ Σ compras del ciclo → auto-vinculado con rastro, NO en pendientes, deshacer funciona |
| Invariante con hueco | Σ compras 1.099,64, recibo 399,38 → detector #5 con Δ=700,26 exacto |
| Tarjeta sin compras | Invariante no aplica; bandeja con sugerencia "gasto sí" |
| Property no-silencio | ∀ tx candidata → actuada-con-rastro ∨ en bandeja |
| Guard liquidación | Cargo 4× cuota → item "revisar", JAMÁS auto-match a una cuota (regresión del lío original) |
| Reversibilidad | accept → undo → estado idéntico (incl. sugerencia de gasto) |
| 47.0 | Golden debt_health/get_balances idéntico pre/post movimiento |
| Asistente financiación | Par → un flujo → pasivo+cuadro+vínculos creados y coherentes |

## Puntos de parada obligatoria

(a) El aprendizaje del ciclo de tarjeta con el historial real del usuario
antes de fijar la ventana default — validar contra sus 6 meses casados.
(b) Cualquier patrón de cargo del banco que no encaje en la cascada →
listar y preguntar, no añadir detectores en silencio. (c) El orden de la
cascada NO se altera sin decisión del usuario (es contrato de
comportamiento). (d) Retirada de los diálogos viejos solo tras verificar
que el flujo unificado cubre sus casos (checklist por diálogo).

## Verificación global

- [ ] Suites verdes; property no-silencio en CI.
- [ ] **Validación manual del usuario (indelegable)**: su julio real
      reproducido — bandeja con los 4+1 items correctos, aceptación en
      ≤5 taps total, invariante del ciclo verde tras resolver.
- [ ] Un mes simulado "normal" (recibo que cuadra + 2 cuotas que casan) →
      bandeja vacía con "todo cuadra".
- [ ] `/debt` renderiza: bandeja + lista adelgazada + 1 gráfico + strip
      esfuerzo. Nada más.
- [ ] Barrido de muertos ejecutado y documentado.

## Fuera de alcance

Liquidación anticipada (→ **PHASE-48**, plan ya escrito, renumerar
`phase-45-debt-early-settlement.md`; su UI nace dentro del detalle 47.3 y
su cola es la fila #4 de esta bandeja) · tracking de revisiones Euríbor
(pendiente: ¿hipoteca fija o variable?) · ranking de deudas por coste
(fase corta posterior; datos existentes) · simulador what-if (viaja con 48,
`dry_run` del motor de liquidación) · recomendaciones invertir-vs-amortizar.
