# Análisis del módulo Finanzas Domésticas — validación y mejora

**Fecha**: 2026-07-17
**Ámbito**: módulo `personal-finance` (backend `app/modules/personal_finance/*`,
web `apps/web/app/(app)/personal-finance/*` + `/debt`) sobre el estado de `main`
en el commit `f17edee` (2026-07-16, PHASE-42).
**Contexto**: los módulos de análisis fundamental (inversión) y Bitcoin están
diseñados pero **no implementados** — quedan fuera de este análisis.
**Método**: clonado del repo, lectura de los 2 ADRs nuevos (0004, 0005), fases
32-42, código del núcleo de dinero, y barrido automático de código muerto y
consumidores de endpoints.

---

## ⚠️ Nota de verificación (2026-07-17)

Este documento se contrastó contra el código en `f17edee` antes de ejecutar
ninguna recomendación. **Los hallazgos estructurales (H2–H5) se confirmaron al
dedo**; la sección de datos (H1) arrastra 4 imprecisiones.

El patrón es útil para saber cuánto fiarse de cada parte: el documento es
**exacto donde corrió barridos automáticos** (LoC, imports, endpoints) y **se
quedó viejo donde resumió prosa** — leyó `audits/2026-07-13-*.md` pero se saltó
las notas de resolución ✅ que se le añadieron después.

| # | Afirmación del doc | Realidad verificada |
|---|---|---|
| 1 | PHASE-39 "pendiente prueba manual **+ commit**" (usado como prueba del patrón §3) | **Está commiteada** (`1a35bbf`); `transactions.statement_balance` y `accounts.anchored_statement_balance` viven en la BD. Lo desactualizado es el README. El patrón §3 sobrevive pero más débil: el hueco es la verificación, no el commit |
| 2 | BBVA −11.322,94 € | Cifra que **la propia auditoría ya retiró** ("cifra ingenua del primer pase"). Real: −11.777,93 €, y tras el fix #4a → **−10.953,16 €** |
| 3 | Wise: 210 € de patas huérfanas ⏳ abierto | **Cerrado** el 2026-07-14: eran 6 movimientos / 330 €, reclasificados `TRANSFER_OUT → OUT` por decisión del usuario (gasto real a tercero) |
| 4 | 668 tests BE · 101 web | Cifras de PHASE-41. Reales: **673 BE · 106 web** (verificado: 106 web pasan) |

**Sobre H4 (código muerto)**: confirmado y **ampliado**. Eran **2.318 LoC en 8
ficheros**, no 2.038 en 5 — el barrido manual no cubrió móvil, que tenía otros
3 componentes muertos (`dashboard-filters`, `category-chip`, `origin-badge`).
Ejecutado; ver [`phases/`](../phases/) y la lección en
[`lessons.md`](../lessons.md).

**Barrido de código muerto ampliado al backend (2026-07-17)**: `vulture` con
filtro de capas declarativas → 32 candidatos → **12 funciones muertas borradas**
(auth: `logout_all`+`get_refresh_token_by_id`+`get_active_tokens_for_user`
+`revoke_all_user_tokens` por cascada; currency: `fetch_actual_rate_date`,
`list_distinct_quotes`, `ensure_rate`; imports: `parse_stream`, `_parse_amount`;
debt: `resolve_period_end`) + parámetro muerto `outer_join` (retirada que
PHASE-34.6 dejó pendiente) + 7 tests reapuntados a `_parse_amount_signed`. Total
sesión: **~290 LoC de producción**. Backend verde: ruff · **mypy (arreglados 5
`type: ignore[attr-defined]` de `rowcount` que PHASE-38 documentó pero nunca
commiteó — `main` NO estaba mypy-verde)** · 670 tests.

**⚠️ 3 hallazgos que NO son código muerto — features descableadas (reportadas,
no tocadas):**

| Hallazgo | Evidencia | Qué significa |
|---|---|---|
| `resolve_period_end` huérfana | Docstring: *"PHASE-30.8 — fuente ÚNICA de verdad del as-of, para que los TRES endpoints coincidan"*. Verificado: `compute_debt_health` es snapshot de hoy (no toma período), `compute_debt_history` usa `months_back/ahead`. Ninguno comparte corte con Capa 1 | El objetivo de PHASE-30.8 (coherencia de as-of entre los 3 endpoints de deuda) **no está en el código**. La función se dejó (borrarla cementa la regresión) |
| `get_net_savings_movement_for_account` huérfana | Doc PHASE-32 HIGH#1: *"el ahorro neto de la principal es display-only vía `get_net_savings…`"*. La función existe, `is_default` se valida, pero `get_balances` no la llama | La feature "saldo de la cuenta principal = ahorro neto" (PHASE-32) **está regresada**. El saldo mostrado de la principal NO excluye transferencias internas como el doc promete |
| ~~`CardHeader` sin usar~~ → ✅ **retirado 2026-07-17** | PHASE-38.3 lo creó para estandarizar cabeceras de ~22 páginas; nadie lo adoptó | La migración de layout de PHASE-38.3 quedó a medias. Decisión del usuario: **retirar** (no adoptar). `CardTitle` — la primitiva SÍ adoptada por 4 cards — se conserva |

**Matiz que el doc no vio**: móvil tiene copias VIVAS de `balances-card`,
`debt-health-card` y `fab`, importadas por su `analysis.tsx`. Es decir, la
pantalla de Análisis de móvil sigue con el diseño previo a PHASE-37.2 mientras
web usa `kpi-strip` + `accounts-section`. **La paridad que PHASE-37.6 declara ✅
puede no ser tal** — revisar antes de decidir la recomendación #5.

---

## Veredicto

**La arquitectura del dinero está resuelta.** ADR-0004 (`transactions.flow`
como fuente de verdad, categoría 100% descriptiva) es la decisión correcta y va
más allá de lo que proponía PHASE-31: aquel análisis trataba el síntoma (seeds
de transferencias mal categorizadas), ADR-0004 mata la enfermedad (que la
categoría gobernara el signo del dinero). El problema ya no está en el modelo.

**El problema se ha movido a la validación y a la entropía.** Hay una auditoría
de integridad con 4 hallazgos abiertos —dos de severidad alta— sobre datos
reales, sin corregir desde el 2026-07-13. Y los tres rediseños consecutivos
(PHASE-29 → 30 → 37 → 41) han dejado sedimento: código muerto, un módulo de
deuda partido en dos y navegación fragmentada.

> Un módulo con arquitectura impecable que muestra números incorrectos no vale
> nada. Ese es hoy el riesgo principal, y no es un problema de código.

---

## 1. Lo que se valida (sólido — no tocar)

| Pieza | Por qué está bien |
|---|---|
| **`flow` como verdad del dinero** (ADR-0004) | Elimina *estructuralmente* la clase de bug que generó 9 fases. Un error de categoría ya no cuesta dinero: solo cambia el grupo del donut. |
| **`signed_amount_expr` compartida** (`accounts/repository.py:46`) | Un único lugar para el signo; `get_balances_for_user` y `position_history` no pueden divergir. El invariante (último punto de la serie de patrimonio == saldos actuales) se sostiene por construcción. |
| **`else_=Decimal("0")`** para tx sin flujo | Las transacciones sin clasificar ya no contaminan el saldo (cierra PHASE-31.3). |
| **Ancla de saldo del extracto** (PHASE-39) | El banco es la autoridad del saldo, no la acumulación. `re_anchor_from_stored` preservando el invariante `saldo(fecha_ancla) == anchored_statement_balance` al importar histórico anterior es el detalle que separa lo hecho bien de lo hecho rápido. |
| **Cancelar la fusión de motores de recurrencia** (PHASE-41) | Decisión correcta y bien razonada: `fixed_expenses/detector.py` (comercio+importe, regularidad temporal) y `analytics/recurrence.py` (categoría, estabilidad de importe) no comparten primitiva. La lección está escrita. |
| **Poda de la maquinaria de emparejado** (ADR-0005 / PHASE-41) | Retirar `candidates/match/suspects/mark` conservando `link`/`unlink` (load-bearing del asistente de pago de deuda) demuestra que el scoping por consumidores reales funciona. |
| **668 tests BE + golden tests en refactors de dinero** | Es lo que hace posible tocar el núcleo sin miedo. |
| **`lessons.md`** | El mejor activo del repo. Las tres últimas lecciones son de calidad profesional y describen patrones generalizables, no anécdotas. |

---

## 2. Hallazgos

### 🔴 H1 — Los datos siguen mal: la auditoría lleva 4 días parada

Fuente: `internal_docs/audits/2026-07-13-data-integrity-pending-check.md`.
**4 de 6 hallazgos abiertos**, dos de severidad alta:

| # | Sev. | Hallazgo | Estado |
|---|---|---|---|
| 3 | Alta | Doble conteo en compra financiada de Taxdown: 239 € computan ~500 € de gasto. **Contradice el modelo de PHASE-38** | ⏳ abierto |
| 4b | Alta | Western Union 215,99 € con `TRANSFER_IN` de signo dudoso + **falta el guardarraíl** que fuerce el par canónico OUT↔IN | ⏳ abierto |
| 6 | Media | Saldos sin `opening_balance` real: BBVA −11.322,94 € con apertura 0; Wise con apertura −5.000 € de apaño + 210 € de patas huérfanas | ⏳ abierto |
| 2 / 5 | Media | Hueco de tarjeta en abril 2026; posibles duplicados en BBVA (12/03 dos cargos de 900 €; 18/03 dos de 1.000 €) | ⏳ abierto |

**La observación que importa**: PHASE-39 construyó el ancla de saldo del
extracto **motivada por el descuadre de BBVA**, y el ancla no se ha aplicado a
BBVA. El patrimonio neto que muestra la app sigue siendo ficción.

Todo lo demás de esta lista puede esperar. Esto no.

**Duda a resolver antes de actuar**: el hallazgo #3 está tipado como 💾 DATO
pero su propia descripción dice "contradice el modelo PHASE-38". Si el modelo no
cubre el caso, es 🐛 BUG-CÓDIGO y hay una fase pendiente que nadie ha escrito.
Determinar cuál de las dos cosas es, es el primer paso.

---

### 🟠 H2 — Deuda partida en dos módulos (split-brain)

| Ubicación | Contenido | LoC |
|---|---|---|
| `personal_finance/debt/` | **1 endpoint**: `GET /debt/category-summary` | 1.529 |
| `personal_finance/accounts/` | `debt_health.py` (966), `debt_history.py` (666), `debt_reconciliation.py` (524), `amortization.py`, `installments_model.py`, `installments_repository.py` | ~3.000 |

La API expone `/accounts/debt-health`, `/accounts/debt-history`,
`/accounts/reconcile-debt` e `installments` mientras el módulo de producto se
llama `/debt`.

El backlog lo clasifica como "reorg físico backend del módulo deuda **(sin
cambio de comportamiento)** — relocalización mecánica sin beneficio" y lo
aplaza. **Discrepo del encuadre**: no es cosmético. Un desarrollador —o Claude
Code— que busque "la lógica de deuda" encuentra dos sitios y ninguno es
autoritativo. Es exactamente el patrón contra el que advierte la lección de
PHASE-41 ("dos cosas que parecen duplicadas: léelas antes de fusionar"), pero
en su versión inversa: **una cosa que es una sola, viviendo en dos sitios**.

El coste de mantener el split no es el fichero mal ubicado: es que cada cambio
futuro en deuda obliga a decidir dónde va, y esa decisión se toma distinto cada
vez.

---

### 🟠 H3 — Navegación fragmentada: PHASE-30 tarea #12 nunca se ejecutó

Para una única tarea conceptual ("gestionar mi hipoteca") el usuario salta
entre tres superficies:

```
/settings/accounts                             ← crear / editar la cuenta pasivo
/debt                                          ← ver KPIs y lista de contratos
/personal-finance/accounts/[id]/amortization   ← ver el cuadro de amortización
```

`apps/web/app/(app)/debt/` contiene **un solo `page.tsx`**. El módulo top-level
es una vista huérfana sobre datos que se gestionan en otro módulo.

Las dos salidas limpias siguen siendo las de PHASE-30 §7:

- **A — Debt como vertical completo**: absorbe sus páginas
  (`/debt/contracts/[id]/schedule`, gestión de cuentas pasivo).
- **B — Debt como sección de personal-finance**: baja del registry, una pestaña
  más.

Lo que hay hoy es lo peor de ambas.

---

### 🟡 H4 — Código muerto: 2.038 LoC de frontend (≈10% de los componentes)

Verificado por barrido de imports (ningún consumidor fuera del propio fichero y
su test):

| Fichero | LoC | Origen |
|---|---|---|
| `components/analysis/position-hero.tsx` | 855 | PHASE-37.2 lo desmontó, no lo borró |
| `components/accounts/balances-card.tsx` | 404 | sustituido por `accounts-section` |
| `components/dashboard/debt-health-card.tsx` | 373 | sustituido por `debt-summary-card` |
| `components/analysis/stitch-key-metrics.tsx` | 333 | sustituido por `kpi-strip` |
| `components/ui/fab.tsx` | 73 | huérfano |
| **Total** | **2.038** | |

**Peligro concreto**: `position-hero.tsx` contiene una copia del gauge de tasa
de esfuerzo y de la composición de patrimonio. Si alguien "arregla" un umbral
ahí, no arregla nada y no se entera. El código muerto que *parece* vivo es peor
que el código muerto obvio.

Borrarlos es una fase de 20 minutos con `git rm` + typecheck.

---

### 🟡 H5 — `accounts/service.py` es un god-service (1.180 LoC, 21 funciones)

Dos dominios sin relación cohabitando en un fichero:

| Rango | Dominio |
|---|---|
| L72–769 | CRUD de cuentas, validación, saldos, reconciliación, anclaje |
| L794–1180 | Cuadros de amortización, cuotas, `pay_installments_by_principal` |

El corte natural es evidente y **coincide con el split de H2**: el mismo
refactor resuelve los dos hallazgos.

**Mención aparte**: `imports/service.py` (1.542 LoC) es el fichero más grande
del backend y concentra parsing, clasificación de `flow`, anclaje de saldo,
dedup por hash y persistencia. No lo he auditado a fondo en esta pasada; es el
candidato #1 a deuda oculta del módulo.

---

## 3. El patrón de fondo

**Doce fases y dos ADRs sobre un solo concepto** (transferencias / flujo del
dinero):

```
21.3 → 23 → 23.1 → 24.x → 28 → 32 → 33 → 34 (+ADR-0004) → 41 (+ADR-0005)
```

Once de las 90 fases llevan *fix / hardening / integrity / redesign /
simplification / polish / refresh* en el título.

Esto **no es crítica**: ADR-0004 documenta explícitamente que 23.1/28/32 eran
parches al mismo defecto de raíz y cierra la familia. El diagnóstico ya está
hecho y bien hecho.

Pero hay un patrón derivado que sigue vivo:

> **Se completa la construcción y no se cierra el ciclo de verificación.**

Evidencia acumulada:

| Artefacto | Estado declarado |
|---|---|
| PHASE-39 | "código completo y verde — **pendiente prueba manual del usuario + commit**" |
| PHASE-41 | verificación automática ✅ · "**Prueba manual (transferencias / papelera / tickets) — pendiente en prod**" |
| AUDIT-2026-07-13 | "**Ninguno corregido todavía**" (4 de 6 abiertos) |
| AUDIT #1 (el corregido) | "corregido — **pendiente verificación manual + commit**" |

La construcción va más rápido que la verificación. El resultado es una app
arquitectónicamente madura cuyo dueño no sabe si sus números son correctos.

Y como el proyecto tiene **un solo usuario**, ese usuario es el único verificador
posible: no hay QA que lo detecte por él. La ironía, dado el oficio del autor,
es deliberada y merece un cambio de proceso, no otra fase de código.

---

## 4. Recomendaciones (priorizadas)

| # | Acción | Esfuerzo | Por qué en este orden |
|---|---|---|---|
| **1** | **Cerrar la auditoría 2026-07-13**: aplicar el ancla de PHASE-39 a BBVA y Wise; resolver #3 (Taxdown — decidir antes si es DATO o BUG); resolver #4b; verificar #2 y #5 contra el extracto real | 1 sesión | Sin esto, todo lo demás decora números falsos |
| **2** | **Guardarraíl del par canónico OUT↔IN** (pendiente explícito de #4b) | XS | Impide que el hallazgo #4 se repita |
| **3** | ~~**Borrar los 5 componentes muertos** (2.038 LoC)~~ → ✅ **hecho 2026-07-17**: 8 ficheros / **2.318 LoC** (los 5 de web + 3 de móvil que este doc no vio) + `knip` cableado a `make verify` para que no vuelva a acumularse | XS | Elimina trampas de mantenimiento. Gratis |
| **4** | **Resolver el split-brain de deuda**: mover `debt_health` / `debt_history` / `debt_reconciliation` / `amortization` / `installments_*` a `debt/`; partir `accounts/service.py` en dos (cuentas+saldos / amortización+cuotas). URLs `/accounts/debt-*` con alias deprecado, no ruptura | M | Un solo sitio autoritativo. Habilita el #5 |
| **5** | **Decidir `debt`: módulo o sección.** Si módulo → mover `/personal-finance/accounts/[id]/amortization` → `/debt/contracts/[id]/schedule` + gestión de cuentas pasivo. Si sección → bajarlo del registry | M | Cierra PHASE-30 tarea #12 |
| **6** | **Ritual de cierre de fase**: ninguna fase se marca ✅ sin verificación manual + commit. Añadirlo a `CLAUDE.md` como regla dura | XS | Ataca el patrón de fondo, no un síntoma. **Mayor retorno a 6 meses** |

**Agrupación práctica**: 1–3 son una sola sesión. 4–5 son una fase real
(candidata a PHASE-43). 6 es un cambio de proceso.

### Lo que NO se recomienda tocar

- El modelo `flow` y `signed_amount_expr` — el núcleo está bien.
- El ancla de saldo del extracto (PHASE-39).
- Los dos motores de recurrencia (`detector.py` / `recurrence.py`) — la
  decisión de no fusionarlos es correcta y está justificada.
- Los golden tests de dinero.

---

## 5. Preguntas abiertas

1. **Hallazgo #3 (Taxdown)**: ¿dato huérfano o el modelo de PHASE-38 no cubre
   el caso? La auditoría lo tipa 💾 DATO pero dice que contradice el modelo. Si
   es lo segundo, falta una fase por escribir.
2. **`debt`**: ¿vertical completo (A) o sección de personal-finance (B)? La
   decisión lleva pendiente desde PHASE-30 y bloquea la #5.
3. **`imports/service.py` (1.542 LoC)**: ¿merece una auditoría dedicada? No se
   ha inspeccionado a fondo y concentra cinco responsabilidades.

---

## Anexo — Inventario del módulo (estado 2026-07-17)

**Backend** `app/modules/personal_finance/` — 14 submódulos, ~21.000 LoC:

| Submódulo | LoC | Ficheros |
|---|---|---|
| accounts | 5.706 | 13 |
| imports | 3.101 | 7 |
| transactions | 2.004 | 6 |
| dashboard | 1.712 | 6 |
| debt | 1.529 | 5 |
| transfers | 1.437 | 5 |
| fixed_expenses | 1.404 | 8 |
| analytics | 893 | 6 |
| budgets | 762 | 6 |
| seed | 672 | 4 |
| receipts | 513 | 6 |
| category_rules | 505 | 6 |
| categories | 360 | 6 |
| bank_mappings | 355 | 6 |

**Ficheros mayores**: `imports/service.py` (1.542) · `accounts/service.py`
(1.180) · `accounts/debt_health.py` (966) · `transfers/service.py` (859) ·
`debt/service.py` (835) · `imports/parser.py` (765).

**Frontend web**: 89 componentes (~21.179 LoC sin tests) · 91 endpoints backend
· 14 hooks de query.

**Pestañas del módulo** (tras PHASE-41, de 5 → 4): Análisis · Transacciones ·
Presupuestos · Gastos fijos. Imports y Tickets como flujos secundarios dentro de
Transacciones.

**Documentación**: 90 fases · 5 ADRs · `lessons.md` · `backlog.md` · 1 auditoría
abierta.

**Tests**: 668 backend (pytest) · 101 web · 18 móvil.
