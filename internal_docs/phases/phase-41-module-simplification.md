# PHASE-41 — Simplificación del módulo Finanzas Domésticas

**Estado**: ✅ completada
**Rama**: `main` (push directo, sin PR)
**Fecha de merge**: 2026-07-15
**Commits**: `5c1d01c` · `29ef4dd` · `cb9356c` · `d95d441` · `6b97bd7` · `9c9f47f`

## Objetivo

Reducir la superficie del módulo tras un **análisis de utilidad financiera** de
las pestañas. El usuario validó Análisis + Transacciones como núcleo y dudaba
del resto. La conclusión: la pestaña **Transferencias** ya no gana su sitio
(tras ADR-0004/0005 la verdad del dinero vive en `transactions.flow`), mientras
Presupuestos y Gastos fijos sí (son las únicas superficies *prospectivas*).

## Qué se implementó

1. **Transferencias fuera de las pestañas primarias (ADR-0005 T4).** El módulo
   pasa de 5 a **4 tabs** (Análisis · Transacciones · Presupuestos · Gastos
   fijos). Retirada la maquinaria de emparejado heurístico: endpoints
   `GET /transfers`, `/candidates`, `/match`, `/suspects`, `/mark` +
   service/repository/schemas/hooks/types/query-keys. Borradas la página web
   `/transfers`, la pantalla móvil y los `transfer-pair-card`.
   - **Conservado (load-bearing)**: `link`/`unlink` (asistente de pago de deuda
     + "deshacer" desde la lista), `from-source` / `from-source-debt`
     (convertir una tx en transferencia/deuda desde su detalle),
     `classify_import_flow` / `infer_transfer_kind` (los usa imports).
   - `dashboard/repository` deja de filtrar por `transfer_pair_id` (redundante:
     `flow` ya excluye las transferencias del cashflow).
2. **Copy corregido**: al borrar la página desaparece el texto que instruía a
   "enlazar salida y entrada para que no cuenten" (premisa falsa bajo `flow`).
3. **Bulk-fix de mal-clasificadas** movido a la página de Transacciones
   (`MisclassifiedSection`, solo se pinta si hay tx mal direccionadas).
4. **Papelera atómica.** Borrar una pata de transferencia **arrastra su pareja
   a la papelera** (atómico) conservando el enlace; restaurar (individual o
   "Restaurar todo") **re-vincula el par**; si la pareja se purgó, vuelve sin
   pareja. Elimina la discrepancia silenciosa de AUDIT-2026-05 sin desvincular
   ni migración.
5. **Tickets heredan categoría + `flow=OUT`.** Nuevo `categorization.py` con la
   cascada compartida (`bank_mapping` > nombre exacto > reglas > default); el
   confirm la hereda cuando el usuario no elige categoría. Fija `flow=OUT`
   (un ticket es gasto) → **arregla un bug latente**: antes un ticket confirmado
   quedaba con `flow`/categoría `NULL` y aportaba **0 al saldo/cashflow**.

Se commiteó junto con la fase el flag **`counts_as_debt`** (PHASE-40): una
tarjeta revolving pagada íntegra cada mes se excluye del módulo de deuda pero se
mantiene en el patrimonio neto.

## Lo que NO se hizo (decisión)

- **Unificar los dos motores de recurrencia** (`fixed_expenses/detector.py` vs
  `analytics/recurrence.py`): **cancelado**, era un falso positivo del análisis.
  No comparten código ni la primitiva asumida (recurrence.py no calcula cadencia;
  agrupa por categoría y mide estabilidad de importe mensual). Fusionarlos movería
  los números de Análisis (tasa de ahorro, runway) — core intocable.

## Verificación

- [x] FE typecheck (6 paquetes) · lint (6) · tests (web 101 + móvil 18)
- [x] BE mypy (138 ficheros) · ruff · **pytest 668**
- [ ] Prueba manual (transferencias / papelera / tickets) — pendiente en "prod".

## Decisiones tomadas

- `link`/`unlink` NO son maquinaria de matching: los usa el asistente de pago de
  deuda. Corrección del scoping antes de borrar (ver `lessons.md`).
- `flow` sigue siendo la verdad del dinero: en tickets se fija `OUT` explícito,
  no se deriva de la categoría resuelta (ADR-0004).
- Podados 5 `type: ignore[attr-defined]` sobre `rowcount` (PHASE-38, ya
  innecesarios con los stubs actuales de SQLAlchemy) → mypy verde.

## Limitaciones conocidas / follow-ups

- **Doble-conteo ticket↔import**: un ticket de tarjeta capturado antes del
  extracto se cuenta dos veces (sin dedup; `source=RECEIPT` no lleva
  `import_hash`). Al fijar `flow=OUT` el doble-conteo se vuelve visible. Pendiente
  reconciliación por importe+fecha+comercio.
- **ADR-0005 T3/T5**: `convert_to_debt_operation` aún depende de
  `transfer_pair_id`; la columna se mantiene.
- Sin paridad móvil del `MisclassifiedSection`.
- PHASE-39 (statement_balance) sigue 🚧, ajena a esta fase.

## Próxima fase

Sin definir. Candidatos: reconciliación ticket↔import, ADR-0005 T3, paridad
móvil del flag `counts_as_debt`.
