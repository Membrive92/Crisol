# PHASE-26 — Imports hardening (XLSX smart + capital obligatorio + mensajes PDF claros)

**Estado**: ✅ completada
**Rama**: `feat/phase-24-debt-from-source` (sin cortar la rama acumulada)
**Fecha de merge**: 2026-05-24

## Objetivo

Tres fricciones reales encontradas trabajando con datos del usuario:

1. **XLSX bancarios reales fallaban con "El XLSX no tiene cabecera"** —
   los exports de BBVA / Santander / ING / CaixaBank meten un bloque
   inicial con logo, periodo, saldos resumen, etc., y la cabecera real
   queda en la fila 5-10. El parser asumía fila 1.
2. **PDFs cifrados devolvían `"PDF inválido: "` (mensaje vacío)** — el
   usuario no sabía si era su fichero o un bug.
3. **Crear préstamos sin Capital generaba cuentas en estado roto** —
   campos como TIN/plazo/fecha bien rellenados pero `opening_balance=0`
   silencioso, sin cuadro de amortización ni saldo. El dashboard
   mostraba 0 €.

## Qué se implementó

### Backend — parser XLSX

- **`parse_xlsx`** ahora escanea hasta `_XLSX_HEADER_SCAN_LIMIT=30`
  filas buscando la primera con ≥2 celdas no vacías. Las filas
  iniciales con un único título o vacías se saltan automáticamente.
- **`parse_xlsx_smart`** (nuevo) — espejo del `parse_pdf_smart`:
  reusa `_classify_columns` con los hints
  (`_CATEGORY_HEADER_HINTS = {concepto, categoría, tipo, movimiento,
  operación, ...}`,
  `_AMOUNT_HEADER_HINTS = {importe, amount, monto, ...}`, etc.) para
  detectar roles de columna automáticamente. Si encuentra sólo una
  columna tipo "Concepto" (caso típico bancos ES), copia su valor a
  `description` Y `category_name` — mismo truco que el PDF. Eso
  dispara el autocompletado de categorías (bank-mapping) que antes
  no se activaba con XLSX.
- **`_parse_with_fallbacks`** para `xlsx` ahora intenta primero
  `parse_xlsx_smart`; si lanza `SmartParseAmbiguous` (no encuentra
  columnas críticas), cae al `parse_xlsx` legacy con el mapping
  manual del usuario (comportamiento histórico preservado).
- **`ImportSource.XLSX_SMART`** nuevo enum value para distinguir en
  preview/badge.

### Backend — PDF errors más claros

- En `parse_pdf` y `parse_pdf_smart`, si `pdfplumber.open()` lanza
  con `str(e) == ""`, ahora caemos a
  `f"{type(e).__name__} sin mensaje (probablemente PDF cifrado o
  corrupto)"`. El usuario ya no ve `"PDF inválido: "` vacío.

### Backend — validación loan/mortgage en `create_account`

- **400 si** `data.type ∈ {LOAN, MORTGAGE}` Y
  `data.opening_balance is None or data.opening_balance <= 0`. Mensaje:
  *"El capital del préstamo o hipoteca es obligatorio y debe ser
  mayor que 0."* Defensa por si el frontend se salta la validación.
- `credit_card` se mantiene permitiendo Capital=0 — su deuda puede
  vivir en la tx contraparte (flujo convert-to-debt, PHASE-24).

### Frontend — form de cuenta

- **`account-form-fields.tsx`**: el label del campo de saldo ahora
  varía:
  - `loan` / `mortgage` → **"Capital"** (sin "(opcional)", input
    `required={true}`).
  - `credit_card` y otros liability → "Capital (opcional)".
  - Asset → "Saldo inicial (opcional)" (sin cambios).
- **`settings/accounts/page.tsx#validate()`**: rechaza el submit con
  mensaje claro cuando `loan` / `mortgage` y Capital está vacío o ≤ 0.
  Antes el form pasaba al backend que respondía OK pero la cuenta
  quedaba inutilizable.

### Frontend — preview de imports

- **`preview-step.tsx`**: nuevos labels para `xlsx_smart`:
  *"Excel (XLSX) — columnas detectadas automáticamente"* + texto
  explicativo. Mismo patrón que `pdfplumber_smart`.

### Tipos compartidos

- **`packages/types/src/models/import.ts`**: añadido `xlsx_smart`
  al union `ImportSource`.

## Flujo técnico (XLSX smart, caso BBVA)

```
Usuario sube abril.xlsx (BBVA, primera fila con logo)
   │
   ▼
detect_format("abril.xlsx") → "xlsx"
   │
   ▼
parse_xlsx_smart(payload)
   │  - load_workbook + iter_rows
   │  - skip filas hasta hallar primera con ≥2 cells (fila 7 p.ej.)
   │  - _classify_columns(headers): {concepto→category_name,
   │      importe→amount, f.operación→occurred_at}
   │  - para cada fila: amount/occurred_at/description=concepto/
   │      category_name=concepto (mismo valor en ambos)
   ▼
preview UI: bank_concept_groups poblado → autocompletado activo
   │
   ▼
Commit: tx con category resuelta por mapping/regla/AI
```

## Archivos clave

- `backend/app/modules/personal_finance/imports/parser.py` — `parse_xlsx`
  tolerante + `parse_xlsx_smart` nuevo + mensaje PDF mejor
- `backend/app/modules/personal_finance/imports/service.py` —
  `_parse_with_fallbacks` rama xlsx_smart
- `backend/app/modules/personal_finance/imports/schemas.py` —
  `ImportSource.XLSX_SMART`
- `backend/app/modules/personal_finance/accounts/service.py` —
  validación loan/mortgage en `create_account`
- `apps/web/components/accounts/account-form-fields.tsx` — label dinámico
  + `required` para loan/mortgage
- `apps/web/app/(app)/settings/accounts/page.tsx` — `validate()` con
  guard para Capital
- `apps/web/components/imports/preview-step.tsx` — etiquetas
  `xlsx_smart`
- `packages/types/src/models/import.ts` — union actualizado

## Verificación

- [x] `pytest tests/test_imports.py` (20/20) y suite completa (386/386)
- [x] Web typecheck verde
- [x] Prueba manual: `abril.xlsx` BBVA con preámbulo → preview con
      grupos de concepto poblados → autocompletado de categorías por
      mapping
- [x] Prueba manual: crear loan sin Capital → error claro en form
- [x] Prueba manual: PDF cifrado → mensaje informa "cifrado o corrupto"

## Limitaciones conocidas

- Los hints del smart parser están en español/inglés básicos. Bancos
  con cabeceras en otros idiomas (DE, FR) caerían al legacy parser.
- La validación de Capital es estricta para loan/mortgage; no aplica
  a credit_card por compatibilidad con convert-to-debt.

## Próxima fase

PHASE-27 — TimeSelector reutilizable + filtros sincronizados con URL.
