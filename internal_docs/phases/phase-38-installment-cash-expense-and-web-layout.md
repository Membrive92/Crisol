# PHASE-38 — Cuota de compra a plazos = gasto de caja + estandarización de layout web

**Estado**: 🚧 en curso (sin commitear; groundwork sobre la rama de PHASE-37)
**Rama**: `feat/phase-37-analysis-redesign` (sin rama/PR propios todavía)
**PR**: —
**Fecha de merge**: —

> Fase entrelazada encima de PHASE-37 (aún sin mergear). No es self-contained
> en su propia rama: requiere rebase o aterrizar PHASE-37 antes. Sólo web +
> backend (sin paridad móvil).

## Objetivo

Empaqueta dos hilos independientes:

1. **Caja de la cuota financiada**: que la CUOTA mensual de una compra a
   plazos con tarjeta (`OPERACIÓN FINANCIADA CON TARJETA`) cuente como **gasto
   real** (`flow=OUT`) en el neto del mes, en lugar de quedar como movimiento
   interno neutro — mientras la liquidación de tarjeta (ADEUDO) y la creación
   de deuda ("operación financiada" a secas) siguen neutras.
2. **Estandarización de layout web**: tokens de anchura compartidos y un
   componente `Card` más rico, para dejar de fijar `maxWidth` y padding a mano
   página por página.

## Qué se implementó

### 38.1 — Carve-out `is_card_financed_op` en `classify_import_flow`
- `transfers/service.py`:
  `is_transfer = (category_is_transfer or text_says_internal) and not is_card_financed_op(text)`.
  La cuota de una compra financiada se fuerza a `flow=OUT` aunque el texto o la
  categoría digan "transferencia". Reusa el **mismo predicado** que la
  reconciliación de deuda (PHASE-36) → clasificador y matcher no divergen.
- Racional: la compra original se modela como creación de deuda (neutra), así
  que la cuota no aparece como gasto en ningún otro sitio; contarla no dobla
  nada. La deuda la sigue descontando el cuadro (independiente del `flow`).
  `is_outflow()` trata `OUT` y `TRANSFER_OUT` igual para un ASSET, así que el
  saldo/patrimonio no cambian; el módulo de deuda excluye la categoría
  vinculada al pasivo con cuadro, así que no dobla el interés. Es una vista de
  **caja** deliberada (el capital de la cuota cuenta como gasto del mes).

### 38.2 — UX deuda-como-gasto (web)
- `transactions/transaction-form.tsx`: al elegir categoría, el `onChange` fija
  además el segmento de dirección (income→`IN`, expense→`OUT`) por defecto —
  salvo `is_transfer` o form ya en modo transferencia. Es sólo un default de
  UI; `flow` sigue siendo la verdad explícita (ADR-0004) y el usuario puede
  re-alternarlo.
- `transactions/transaction-list.tsx`: badge "Pago de deuda" para categorías
  con `role IN (DEBT_PAYMENT, DEBT_INTEREST)` — la cuota se lee como gasto real
  que además amortiza (su contraparte es el cuadro, no una tx emparejada, así
  que no se marca "Sin pareja").

### 38.3 — Estandarización de layout web
- `packages/ui/src/tokens.ts`: `layout = { pageWide: 2400, pageNarrow: 720 }`.
  `pageWide` alinea páginas de datos/grid con `/analysis`; `pageNarrow` para
  formularios/detalle de una columna.
- `apps/web/components/ui/card.tsx`: padding por defecto `md`→`lg` (24px); prop
  `compact?` para volver a `md`; `CardTitle` (h3, `md`/`sm`) y `CardHeader`
  (icono + título + acción) nuevos. Un `padding` explícito en `style` sigue
  ganando.
- ~22 `page.tsx` migradas a `layout.pageWide`/`pageNarrow`; 5 cards de análisis
  adoptan `CardTitle` y `balances-card` elimina overrides de padding.

### Housekeeping
- `type: ignore[attr-defined]` + comentario en `result.rowcount` (auth repo +
  5 helpers DML de transactions repo): SQLAlchemy tipa `execute()` como
  `Result` sin `rowcount`, pero en un DML el runtime devuelve `CursorResult`.
- Poda de `backlog.md` (items ya resueltos en fases 14/21/37).

## Flujo técnico

```
Import: "OPERACIÓN FINANCIADA CON TARJETA"  ── is_card_financed_op(text)=True ──► flow=OUT (gasto de caja)
        "ADEUDO MENSUAL DE TARJETA"          ── liquidación ─────────────────────► TRANSFER_* (neutro)
        "OPERACIÓN FINANCIADA" (a secas)     ── creación de deuda ───────────────► TRANSFER_* (neutro)
```

## Archivos clave
- `backend/app/modules/personal_finance/transfers/service.py` — carve-out.
- `backend/app/modules/personal_finance/accounts/debt_reconciliation.py` —
  `is_card_financed_op` (predicado compartido).
- `apps/web/components/ui/card.tsx` · `packages/ui/src/tokens.ts` — layout.
- `apps/web/components/transactions/transaction-form.tsx` · `transaction-list.tsx` — UX.
- `backend/tests/test_flow_money_model.py` — cobertura del carve-out.

## Endpoints añadidos
- Ninguno.

## Migraciones
- Ninguna.

## Verificación
- [x] Backend: nuevos/renombrados tests en `test_flow_money_model.py`
      (cuota con tarjeta → `OUT`; "operación financiada" a secas → `TRANSFER_OUT`;
      carve-out gana sobre `category_is_transfer`).
- [ ] Frontend: sin tests nuevos para form-direction, badge "Pago de deuda" ni
      los tokens de layout/Card.
- [ ] Prueba manual del usuario (pendiente).

## Decisiones tomadas
- **Vista de caja para la cuota financiada** (decisión del usuario): el capital
  de la cuota cuenta como gasto del mes, no accrual contable. Ver lección
  `[PHASE-38]` en [lessons.md](../lessons.md).
- **Un solo predicado `is_card_financed_op`** para clasificador y matcher.

## Limitaciones conocidas
- **Sin paridad móvil**: el flujo deuda-como-gasto, el badge y los tokens de
  layout/Card sólo están en web.
- **API de `Card` parcialmente sin usar**: `compact` y `CardHeader` están
  exportados pero sin consumidores reales todavía.
- **`Card` padding `md`→`lg`** afecta a TODA card sin padding explícito, más
  allá de los 5 ficheros tocados (estandarización deliberada).
- Fase sin commitear ni doc/README hasta esta pasada; DoD pendiente.

## Próxima fase
Sin definir. Follow-up natural: paridad móvil del carve-out y del badge.
