# PHASE-22 — Módulo de deuda: liabilities + amortización + KPIs de salud

**Estado**: ✅ completada
**Rama**: directo a `main`
**Commit**: `81816df`
**Fecha de merge**: 2026-05-12

## Objetivo

Habilitar los tipos de cuenta `credit_card`, `loan` y `mortgage` como
deuda real del usuario y construir encima un módulo de análisis: cuadro
de amortización francés para préstamos/hipotecas, asistente para pagar
la cuota mensual (separa principal de intereses) y panel de KPIs en el
dashboard (DTI con bandas healthy/caution/stressed, deuda/activos, APR
ponderado, intereses YTD, time-to-payoff).

Con esto el patrimonio neto deja de ser sólo "activos" y empieza a
significar realmente `activos − pasivos`.

## Qué se implementó

### Backend — liabilities habilitados

- **`accounts/service.py::_nature_for_type`** — helper que asigna
  `AccountNature.LIABILITY` cuando el `type` está en
  `LIABILITY_ACCOUNT_TYPES`, `ASSET` en caso contrario. `create_account`
  ya no rechaza tipos de pasivo; `update_account` re-sincroniza
  `nature` si cambia el `type`.
- **`accounts/schemas.py`** — separación explícita
  `ASSET_ACCOUNT_TYPES` / `LIABILITY_ACCOUNT_TYPES`. La unión de los
  dos es la lista de tipos válidos.

### Backend — inversión de signo para pasivos

- **`accounts/repository.py::get_balances_for_user`** — ahora calcula
  `signed_amount` con un CASE que mira `Account.nature` y
  `Category.kind` a la vez:
  - liability + expense → +amount (sube la deuda)
  - liability + income → −amount (la baja, es un pago)
  - asset + expense → −amount
  - asset + income → +amount
  De este modo `current_balance` de una tarjeta crece con cada compra
  y baja con cada transferencia desde la cuenta corriente.
- **`accounts/service.py::get_balances`** — `total_liabilities` suma
  el `current_balance` de las cuentas activas con
  `nature=LIABILITY`. Patrimonio neto = `total_assets − total_liabilities`.

### Backend — amortización francesa

- **`accounts/amortization.py`** (módulo nuevo) — `build_schedule`
  genera el cuadro completo iterando mes a mes:
  - cuota constante calculada con la fórmula francesa
    `P·(i·(1+i)^n) / ((1+i)^n − 1)`,
  - intereses del mes = saldo pendiente · tasa mensual,
  - principal del mes = cuota − intereses,
  - última fila ajusta el principal para cerrar a 0 exacto y compensa
    el redondeo acumulado.
  Soporta APR = 0 (cuota lineal). `_add_month` cuida el clamp del día
  cuando el mes destino tiene menos días.
- **`Account`** gana 3 campos opcionales: `apr` (Numeric(6,4)),
  `term_months` (Integer), `start_date` (Date). Sólo significativos
  para `loan` / `mortgage`. El service los ignora silenciosamente para
  otros tipos.
- **Alembic** `l9b03d5f8e6b2_account_amortization.py` añade las 3
  columnas nullable a `accounts`.
- **`accounts/service.py::get_amortization_schedule`** — valida que la
  cuenta es loan/mortgage, que tiene los 3 campos y que
  `opening_balance > 0`. Devuelve `AmortizationScheduleResponse` con
  filas + agregados (`monthly_payment`, `total_interest`,
  `total_paid`).

### Backend — KPIs de salud financiera

- **`accounts/debt_health.py`** (módulo nuevo) — `compute_debt_health`
  reúne todos los indicadores en un solo endpoint:
  - **`total_liabilities`, `total_assets`, `net_worth`,
    `debt_to_assets_ratio`** — sólo cuentas no archivadas en la
    `reference_currency` (la primera por display_order).
  - **`monthly_debt_payment`** — para loans/mortgages con
    `apr + term_months` definidos, cuota francesa; para tarjetas con
    APR, cuota teórica a 12 meses; para tarjetas sin APR, 3% del saldo
    como pago mínimo estimado.
  - **`weighted_apr`** — APR medio ponderado por saldo entre las
    liabilities que declaran `apr`.
  - **`monthly_income_avg`** — media de ingresos de los últimos 6
    meses cerrados, excluyendo transferencias internas y papelera.
  - **`dti_ratio`** + **`dti_status`** — `monthly_debt_payment /
    monthly_income_avg`, clasificado en healthy (<0.36), caution
    (0.36–0.43), stressed (>0.43), unknown si no hay datos.
  - **`interest_paid_ytd`** — suma de expenses desde 1-enero en las
    categorías de la frozenset `INTEREST_CATEGORY_NAMES`.
  - **`time_to_payoff_months`** — proyección lineal: principal
    amortizado en los últimos 3 meses → ratio mensual → meses para
    saldar el total. `None` si no hay actividad de pago.
- **`accounts/router.py`** — añade `GET /accounts/debt-health` y
  `GET /accounts/{id}/amortization-schedule`.

### Backend — seed de categorías de interés

`backend/app/modules/personal_finance/seed/dataset.py` añade tres
categorías de gasto con sus reglas:

- "Intereses hipoteca" — keywords: "intereses hipoteca", "interés
  préstamo hipotecario", "comisión apertura hipoteca", etc.
- "Intereses préstamo" — keywords: "intereses préstamo", "interés
  préstamo personal", "comisión apertura préstamo", etc.
- "Intereses tarjeta" — keywords: "intereses tarjeta", "interés
  aplazamiento", "comisión revolving", etc.

`INTEREST_CATEGORY_NAMES` en `debt_health.py` referencia los nombres
exactos. Si el usuario renombra una, sigue funcionando para el resto.

### Frontend — types / services / hooks

- **`packages/types/src/models/account.ts`** — añade
  `LIABILITY_ACCOUNT_TYPES`, `SELECTABLE_ACCOUNT_TYPES` (asset ∪
  liability), `AMORTIZABLE_ACCOUNT_TYPES` (`loan | mortgage`). El
  `Account` gana los 3 nullable: `apr`, `term_months`, `start_date`.
- **`packages/types/src/models/debt.ts`** (nuevo) — `AmortizationRow`,
  `AmortizationSchedule`, `DebtHealthKpis`, `DtiStatus`.
- **`packages/services/src/api/endpoints/accounts.ts`** — añade
  `debtHealth()` y `amortizationSchedule(id)`.
- **`packages/services/src/query/hooks/useAccounts.ts`** — añade
  `useDebtHealth()` (staleTime 1 min) y
  `useAmortizationSchedule(id)` (staleTime 5 min, `enabled: !!id`).
- **`packages/services/src/query/keys.ts`** — nuevas keys
  `accounts.debtHealth()`, `accounts.amortization(id)`.

### Frontend web

- **`apps/web/components/accounts/account-form-fields.tsx`** — el
  selector de tipo agrupa visualmente "Activos" vs "Pasivos - deuda".
  Cuando el tipo es loan/mortgage aparecen 3 campos extra (APR%,
  plazo en meses, fecha de inicio). Cambiar a un tipo no-amortizable
  los resetea a null.
- **`apps/web/components/accounts/balances-card.tsx`** — la card
  separa activos de pasivos, pinta el patrimonio neto en rojo si es
  negativo y etiqueta cada fila de liability con un badge "DEUDA" +
  saldo en rojo.
- **`apps/web/components/accounts/debt-payment-wizard.tsx`** (nuevo)
  — asistente de 3 pasos para pagar cuota:
  1. Elegir cuenta origen + cuenta liability destino.
  2. Introducir total + split principal/intereses (precarga la fila
     del cuadro de amortización del mes en curso si existe).
  3. Elegir categoría de intereses + confirmar.
  Crea las 2 transacciones + el link de transfer-pair desde el
  cliente con 3 mutations encadenadas. Atomicidad transaccional
  apuntada como follow-up.
- **`apps/web/app/(app)/personal-finance/accounts/[id]/amortization/page.tsx`**
  (nuevo) — tabla completa del cuadro con KPIs arriba
  (`monthly_payment`, `total_interest`, `total_paid`). Resalta el
  mes en curso.
- **`apps/web/components/dashboard/debt-health-card.tsx`** (nuevo) —
  card del dashboard con el `dti_status` como badge (verde / ámbar /
  rojo), `monthly_debt_payment`, `weighted_apr`, `time_to_payoff`,
  `interest_paid_ytd`, `debt_to_assets_ratio`. Estados vacíos cuando
  no hay datos.
- **`apps/web/app/(app)/personal-finance/analysis/page.tsx`** monta
  `DebtHealthCard` junto a `BalancesCard`.
- **`apps/web/app/(app)/settings/accounts/page.tsx`** — cada fila de
  liability gana 2 botones: "Pagar cuota" (abre el wizard) y "Ver
  cuadro" (link a la amortization page). Sólo se muestran cuando
  aplica.
- **`apps/web/app/onboarding/accounts/page.tsx`** — fix del redirect
  post-onboarding (`/personal-finance/analysis`, antes apuntaba a
  una ruta inexistente).

### Frontend mobile

- **`apps/mobile/components/accounts/account-form-modal.tsx`** —
  agrupado activos/pasivos + campos de amortización condicionales,
  espejo del web.
- **`apps/mobile/components/accounts/balances-card.tsx`** — separa
  activos de pasivos, badge "DEUDA", patrimonio neto en rojo si
  negativo.
- **`apps/mobile/components/accounts/debt-payment-wizard.tsx`**
  (nuevo) — wizard de 3 pasos en `Modal` nativo, mismo flujo y
  validaciones que el web.
- **`apps/mobile/app/(modules)/personal-finance/accounts/[id]/amortization.tsx`**
  (nuevo) — tabla scrollable con KPIs arriba.
- **`apps/mobile/components/dashboard/debt-health-card.tsx`** (nuevo)
  — equivalente del de web montado en la pantalla `analysis`.
- **`apps/mobile/app/(modules)/personal-finance/accounts.tsx`** —
  botones "Pagar cuota" / "Ver cuadro" en las filas de liability.
- **`apps/mobile/app/(modules)/personal-finance/_layout.tsx`** —
  registra la `Stack.Screen` de la pantalla de amortization.

## Flujo técnico

```
 Usuario añade su tarjeta Visa con saldo inicial 0 (no debe nada aún)
    │
 Compra de 120€ en el supermercado pagando con la tarjeta
    │ Transaction { account: Visa, amount: 120, kind: expense, cat: "Comida" }
    │ get_balances_for_user → CASE liability + expense → +120
    │ Saldo Visa: 0 + 120 = 120€ (deuda)
    ▼
 Fin de mes, llega la cuota de 120€ + 8€ de intereses
    │ Wizard "Pagar cuota":
    │   step 1: origen = BBVA, destino = Visa
    │   step 2: total 128€, principal 120€, intereses 8€
    │   step 3: cat intereses = "Intereses tarjeta"
    │
    │ Genera 2 txs:
    │   A) BBVA  -120€  (expense, sin categoría) ──┐
    │   B) Visa  +120€  (income, sin categoría) ───┤ transfer_pair_id mutuo
    │   C) BBVA  -8€    (expense, "Intereses tarjeta")
    ▼
 Saldos resultantes:
    │ BBVA:  -128€
    │ Visa:   +120 (compra) -120 (pago, income en liability invierte signo) = 0
    │ Intereses YTD += 8€
 KPIs:
    │ monthly_debt_payment cae a 0 si era el único pasivo
    │ DTI cae a 0 (sin pagos pendientes ese mes)
```

```
 Usuario añade hipoteca: opening_balance 100.000€, apr 3.5%, term 240
    │ start_date 2026-01-01
    ▼
 GET /accounts/{id}/amortization-schedule
    │ build_schedule(P=100_000, apr=0.035, n=240, start=2026-01-01)
    │ cuota = 100000 · (0.035/12) · (1 + 0.035/12)^240 / ((1+0.035/12)^240 - 1)
    │       ≈ 579,96€/mes
    │ mes 1: interés = 100000 · 0.035/12 = 291,67€ → principal = 288,29€
    │ mes 2: saldo = 99711,71 → interés = 290,82€ → principal = 289,14€
    │ ...
    │ mes 240: ajusta principal para cerrar a 0 exacto
    ▼
 Tabla en /personal-finance/accounts/{id}/amortization
    │ total_paid ≈ 139.190€, total_interest ≈ 39.190€
```

## Archivos clave

### Backend
- `backend/app/modules/personal_finance/accounts/amortization.py` (nuevo)
- `backend/app/modules/personal_finance/accounts/debt_health.py` (nuevo)
- `backend/app/modules/personal_finance/accounts/{models,schemas,service,repository,router}.py`
- `backend/app/modules/personal_finance/seed/dataset.py` (3 categorías
  de intereses)
- `backend/alembic/versions/l9b03d5f8e6b2_account_amortization.py`
- `backend/tests/test_debt.py` (9 tests nuevos)
- `backend/tests/test_accounts.py` (un test actualizado: liability ya
  no se rechaza)

### Frontend
- `packages/types/src/models/account.ts`,
  `packages/types/src/models/debt.ts` (nuevo),
  `packages/types/src/dto/account.dto.ts`
- `packages/services/src/api/endpoints/accounts.ts`,
  `packages/services/src/query/hooks/useAccounts.ts`,
  `packages/services/src/query/keys.ts`
- `apps/web/components/accounts/account-form-fields.tsx`
- `apps/web/components/accounts/balances-card.tsx`
- `apps/web/components/accounts/debt-payment-wizard.tsx` (nuevo)
- `apps/web/components/dashboard/debt-health-card.tsx` (nuevo)
- `apps/web/app/(app)/personal-finance/accounts/[id]/amortization/page.tsx` (nuevo)
- `apps/mobile/components/accounts/{account-form-modal,balances-card,debt-payment-wizard}.tsx`
- `apps/mobile/components/dashboard/debt-health-card.tsx` (nuevo)
- `apps/mobile/app/(modules)/personal-finance/accounts/[id]/amortization.tsx` (nuevo)

## Endpoints añadidos

- `GET /accounts/debt-health` — KPIs de salud financiera del usuario
  en la divisa de referencia.
- `GET /accounts/{id}/amortization-schedule` — cuadro francés
  completo + agregados. Errores:
  - 400 si la cuenta no es loan/mortgage,
  - 400 si falta APR / plazo / fecha de inicio,
  - 400 si `opening_balance <= 0`,
  - 404 si la cuenta no es del usuario.

## Migraciones

- `l9b03d5f8e6b2_account_amortization.py` — `ADD COLUMN apr
  NUMERIC(6,4) NULL, term_months INTEGER NULL, start_date DATE NULL`
  en `accounts`. Sin backfill — los pasivos existentes quedan sin
  cuadro hasta que el usuario los complete.

## Verificación

- [x] `pytest backend/tests/` verde (incluye 9 tests nuevos en
      `test_debt.py` + el ajuste de `test_accounts.py`).
- [x] `pnpm typecheck`, `pnpm lint`, `pnpm test` verdes en los 4
      paquetes que tienen suite.
- [x] Migración `l9b03d5f8e6b2` aplicada en BD local sin errores.
- [x] Smoke manual:
  - [x] Crear cuenta tipo `credit_card` con saldo inicial 0.
  - [x] Crear cuenta `mortgage` con APR 3.5% y plazo 240 → cuadro
        genera 240 filas y total_paid ≈ 139k para 100k€.
  - [x] Compra con tarjeta → balance Visa sube.
  - [x] Wizard "Pagar cuota" → transferencia + intereses + ambos
        recogidos en KPIs.
  - [x] Dashboard muestra DTI verde con un usuario sin deuda
        significativa, ámbar cuando llega a 38% de los ingresos.

## Decisiones tomadas

- **Tarjeta de crédito como liability con saldo arrastrado**, no
  como entidad separada de "aplazamientos". Cada compra sube la
  deuda, cada pago la baja. Es el patrón estándar de Mint / YNAB y
  encaja con la inversión de signo de la PHASE-22 sin entidades
  nuevas.
- **Wizard de pago crea 3 mutations desde el cliente** en lugar de
  un endpoint atómico backend. Acelera el MVP. La atomicidad real
  (rollback si falla la 2ª o 3ª) queda como follow-up. Si una
  falla, el wizard muestra error y el usuario puede borrar lo
  parcial.
- **DTI con bandas 0.36 / 0.43**. Es el estándar de la literatura
  (US mortgage lending standards). Bandas: healthy `<0.36`, caution
  `0.36–0.43`, stressed `>0.43`. Si el usuario no tiene ingresos
  registrados o no tiene deuda, `unknown`.
- **`monthly_income_avg` mira 6 meses cerrados** (no incluye el mes
  en curso). El mes actual estaría incompleto y bajaría la media
  artificialmente. Excluye transferencias internas
  (`transfer_pair_id IS NULL`) — un Bizum entre cuentas propias no
  es ingreso.
- **Estimación de cuota de tarjeta**: si tiene APR, cuota teórica a
  12 meses; si no, 3% del saldo (mínimo común en banca española).
  El usuario puede sobreescribir la cuota efectiva pagándola por el
  wizard — el KPI sólo es una proyección.
- **`weighted_apr` ignora liabilities sin APR**. Una tarjeta sin
  APR declarado no entra ni al numerador ni al denominador, no
  arrastra la media.
- **`time_to_payoff` con ventana de 3 meses**, no de 1 ni de 6. Con
  1 mes la proyección es ruidosa (un pago grande la dispara). Con
  6 es lenta de reaccionar a cambios de estrategia. 3 es el punto
  de equilibrio.
- **Categorías de interés por nombre exacto en frozenset**.
  Acoplado al seed, pero si el usuario renombra una categoría
  (e.g. "Intereses hipoteca" → "Intereses casa") sólo pierde esa
  agregación; las otras siguen contando. Alternativa con flag en
  la tabla `categories` quedó descartada por sobrediseño para 3
  categorías concretas.
- **Inversión de signo en SQL, no en service.py**. La query es la
  fuente única de saldos, no hay riesgo de divergencia entre
  módulos que la llamen. Si se quiere otro caller con semántica
  distinta (e.g. extracto contable), sería un método de repository
  aparte.
- **`apr` como `Numeric(6,4)`**. Permite 99.9999% como máximo (más
  que suficiente; APRs típicos son 3–24%). 4 decimales = 0.01%
  de precisión.

## Limitaciones conocidas

- **Wizard de pago no es atómico**. Si la 1ª mutation crea las txs
  pero la 2ª (el link de transfer-pair) falla, quedan dos txs sin
  emparejar. El usuario tiene que enlazarlas a mano o borrarlas.
- **No hay generación automática del schedule en BD**. Las filas
  del cuadro se calculan al vuelo en cada GET. Para hipotecas a
  30 años son 360 filas — barato. Si en algún momento queremos
  cuadros editables (renegociaciones, amortizaciones parciales) sí
  habría que persistir.
- **DTI no descuenta gastos esenciales** (vivienda, comida, etc.).
  Usa pago de deuda / ingresos brutos. Es la métrica estándar de
  banca, no de personal-finance avanzada. Una variante "debt service
  ratio" más rica queda como follow-up.
- **`time_to_payoff` lineal**, no proyectivo. No considera tipos
  variables ni cambios de cuota futuros. Para hipotecas a tipo fijo
  con cuadro francés es exacto; para tarjetas con saldo creciente
  puede subestimar.
- **No hay alerta proactiva si DTI cruza una banda**. El badge cambia
  pero no se notifica. PHASE-14.5 introdujo notificaciones para
  presupuestos; replicar para DTI sería un follow-up natural.
- **Cross-currency en debt-health = no soportado**. La función
  computa todo en la `reference_currency` (primera cuenta por
  display_order); cuentas en otras divisas se ignoran silenciosamente.
  Mismo enfoque conservador que `mixed_currencies` en `/balances`.
- **Sin reconciliación banca → tarjeta**. Si el banco lista la
  compra con la tarjeta como una línea normal en el extracto, el
  import la mete en la cuenta corriente (no en la Visa) y no se
  empareja con la cuota mensual. El usuario tiene que mover txs a
  la cuenta correcta a mano. Reconciliar tarjetas con imports es
  un mini-proyecto aparte.

## Próxima fase

Sin fase encadenada decidida. Candidatos para la siguiente iteración:

- **PHASE-23 — Alertas DTI / debt-health**: replicar el sistema de
  notificaciones de PHASE-14.5 para avisar cuando DTI cruza una
  banda o se acerca a stressed.
- **PHASE-24 — Atomicidad del wizard de pago**: nuevo endpoint
  `POST /accounts/{id}/debt-payment` que ejecute las 3 inserciones
  en una transacción de BD.
- **PHASE-25 — Persistencia y edición del schedule**: tabla
  `amortization_rows` para soportar amortizaciones parciales y
  renegociación de tipo.
