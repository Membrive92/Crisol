# PHASE-36 — Saldo de deuda gobernado por el cuadro + reconciliación de aportaciones

**Estado**: ✅ completada (en `main`) · documentada retroactivamente
**Rama**: `feat/phase-34-transaction-flow` (convive con PHASE-34/35)
**PR**: — (squash directo)
**Fecha de merge**: 2026-07-04 (squash `5215a80`, `Refs: PHASE-34, PHASE-35, PHASE-36`)

> Esta fase se plegó en el squash de PHASE-34/35 sin doc propia. Se documenta
> aquí a posteriori durante la revisión integral de docs (2026-07-12).

## Objetivo

Que el saldo vivo de una liability con plan **salga del cuadro de
amortización** (`schedule_outstanding` = Σ de las cuotas no pagadas), y que
las aportaciones reales del extracto (amortización de préstamo, cuotas de
"operación financiada con tarjeta") **descuenten** esa deuda marcando cuotas
como pagadas — sin crear patas sintéticas ni tocar el cashflow. Extiende
ADR-0004 ("el cuadro manda" para la deuda, igual que `flow` manda para la
caja).

## Qué se implementó

- **Módulo `accounts/debt_reconciliation.py`** con la mecánica idempotente y
  reversible:
  1. **Generar el cuadro que falte** (préstamo dado de alta sin cuotas).
  2. **Ancla temporal**: las cuotas con `due_date` anterior a la ventana de
     datos del usuario se marcan pagadas (sin tx) → el saldo de arranque es el
     saldo económico real a la primera fecha de datos, no el principal
     original.
  3. **Match aportación → cuota**:
     - *Préstamo/hipoteca* (`is_loan_amortization`): cada cargo de
       amortización marca la siguiente cuota pendiente de su liability (FIFO),
       enlazando `paid_transaction_id`.
     - *Tarjeta financiada* (PHASE-36.1, `is_card_financed_op`): el cargo
       `OPERACIÓN FINANCIADA CON TARJETA` es AGREGADO (engloba varias compras
       a plazos de la misma tarjeta), así que un cargo paga la siguiente cuota
       pendiente de CADA tarjeta con cuadro ya iniciada (mes del cargo ≥ mes
       de inicio del plan).
  4. **Exceso asumido**: el sobrante de un cargo de tarjeta sobre las cuotas
     que cubre (compras de años previos no registradas) NO toca el saldo — se
     reporta como `assumed_unregistered_debt` (línea informativa).
- **Endpoint `POST /accounts/reconcile-debt`** con `?dry_run=` (def `true`):
  `dry_run=true` devuelve el `ReconcilePlanResponse` (plan) sin escribir;
  `false` lo aplica.
- **`schedule_outstanding`** como fuente del saldo vivo de la liability con
  cuadro (consumido por debt-health y `/debt`).

## Flujo técnico

```
Extracto (tx reales)                Cuadro (liability_installments)
   │  cargo "AMORTIZACIÓN…"             cuota #k pendiente
   │  cargo "OPERACIÓN FINANCIADA…"     cuota #j pendiente (por tarjeta)
   ▼                                    ▼
debt_reconciliation.reconcile ──► marca paid (paid_transaction_id) ──► saldo = Σ cuotas no pagadas
   (sin crear contrapartidas; no toca cashflow ni flow)
```

## Archivos clave
- `backend/app/modules/personal_finance/accounts/debt_reconciliation.py` — motor
  de reconciliación + predicados `is_loan_amortization` / `is_card_financed_op`.
- `backend/app/modules/personal_finance/accounts/router.py` — endpoint
  `POST /accounts/reconcile-debt`.
- `backend/app/modules/personal_finance/accounts/debt_health.py` /
  `debt/service.py` — saldo vivo desde `schedule_outstanding`.
- `apps/web/components/accounts/debt-payment-wizard.tsx` — UI del flujo.
- `backend/tests/test_debt_reconciliation.py` — cobertura.

## Endpoints añadidos
- `POST /accounts/reconcile-debt` — ver [api/endpoints.md](../api/endpoints.md).

## Migraciones
- Ninguna nueva propia: reusa `liability_installments` (`o2e36g8cb1f9d5`,
  PHASE-24.1). La reconciliación sólo muta `paid_at` / `paid_transaction_id`.

## Decisiones tomadas
- **"El cuadro manda"**: el saldo de una liability con plan no se deriva de la
  categoría ni del signo de las tx, sino de las cuotas pendientes. Coherente
  con ADR-0004 (la caja la manda `flow`; la deuda, el cuadro).
- **Sin patas sintéticas**: reconciliar NO crea transacciones — sólo marca
  cuotas. Evita el doble conteo "dos fuentes de verdad" (lección PHASE-34).
- **`is_card_financed_op` compartido**: el mismo predicado que usa PHASE-38 en
  `classify_import_flow`, para que clasificador y matcher no diverjan.

## Limitaciones conocidas
- El cargo de tarjeta agregado sólo casa cuotas de planes cuyo mes de inicio
  ≤ mes del cargo; compras previas no registradas quedan como
  `assumed_unregistered_debt` (informativo, no ajusta saldo).
- Mono-divisa (misma limitación que el resto del módulo de deuda).

## Próxima fase
PHASE-37 — Rediseño módulo Análisis (consume `schedule_outstanding` e interés
del cuadro vía MUX por pasivo).
