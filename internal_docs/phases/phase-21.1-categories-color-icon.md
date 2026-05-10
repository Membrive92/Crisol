# PHASE-21.1 — Categorías con color y emoji + pickers cross-platform

**Estado**: ✅ completada
**Rama**: directo a `main`
**Commit**: `a843962`
**Fecha de merge**: 2026-05-10

## Objetivo

Permitir al usuario personalizar visualmente cada categoría con un
color (hex) y un emoji (icono). Las categorías del seed reciben
defaults coherentes; el resto de la UI (chips de transacción, donut
del análisis, cards de presupuestos) usa esa personalización para
que el usuario reconozca cada categoría de un vistazo.

## Qué se implementó

### Presets compartidos

`packages/ui/src/category-presets.ts` (nuevo):

- **`CATEGORY_COLOR_PALETTE`** — 18 colores curados (red/orange/amber/
  yellow/lime/emerald/green/teal/cyan/sky/indigo/violet/purple/pink/
  rose/slate/graphite/silver). Hex alineados con los que el seed
  asigna a las categorías recomendadas.
- **`CATEGORY_EMOJI_PRESETS`** — ~34 emojis comunes (`🍽️`, `🛒`,
  `⛽`, `🚌`, `📺`, `💊`, `🏠`, `📦`, `💸`, `💰`, `↔️`, `🛡️`,
  `📈`, `🎬`, `🎮`, …).
- **`DEFAULT_CATEGORY_COLOR`** — primer hex del array; fallback si
  el usuario no eligió.

### Pickers UI

- **Web** — `apps/web/components/ui/category-appearance.tsx`:
  swatches circulares (paleta) + grid de emojis con estado seleccionado.
- **Mobile** — `apps/mobile/components/categories/category-appearance-fields.tsx`:
  espejo del web con `Pressable` nativo + `StyleSheet`.

### Seed con defaults

`backend/app/modules/personal_finance/seed/dataset.py` extendido:
cada `SeedCategoryDef` lleva `color` (hex) e `icon` (emoji)
obligatorios. Restaurantes 🍽️ rojo, Supermercado 🛒 verde lima,
Combustible ⛽ naranja, Suscripciones 📺 morado, etc.

`seed/service.py::_upsert_category` rellena `color`/`icon` cuando
NULL en categorías existentes (sin sobrescribir lo que el usuario
haya elegido a mano). Re-ejecutar `POST /seed/recommended` completa
los defaults sin duplicar nada.

### Pantalla mobile de categorías

`apps/mobile/app/(modules)/personal-finance/categories.tsx` (nueva)
+ `apps/mobile/components/categories/category-form-modal.tsx` —
CRUD de categorías con pickers integrados, listado agrupado por
kind (gastos/ingresos), FAB para crear, modal de form.

### Display de color/icon en agregados

- **CategoryChip** (web + mobile): acepta `color?` y `icon?`. Si
  hay `color`, fondo tinta a 15% del hex + foreground = hex; si no,
  paleta por kind (income/expense/null). Si hay `icon`, prefix
  emoji.
- **Donut de análisis** (`apps/web/components/analysis/stitch-expense-breakdown.tsx`,
  `apps/mobile/components/dashboard/category-donut.tsx`): cada slice
  usa `category.color` cuando viene en el response; fallback a
  paleta cíclica.
- **Budget status card** (web + mobile): swatch + emoji prefix en
  el nombre de la categoría.

### Backend dashboard expone color/icon

`backend/app/modules/personal_finance/dashboard/repository.py::get_breakdown_by_category`
incluye `Category.color` y `Category.icon` en SELECT y GROUP BY.
`schemas.CategoryBreakdownItem` añade `category_color` y
`category_icon` (nullable). El frontend los usa para pintar.

## Flujo técnico

```
 Usuario crea/edita categoría en Ajustes → Categorías
    ▼
 CategoryAppearanceFields: swatch picker + emoji grid
    │ onColorChange(hex), onIconChange(emoji|null)
    ▼
 PUT /categories/{id} { color, icon } → BD
    ▼
 Próxima query del dashboard:
    │ /dashboard/by-category devuelve category_color/category_icon
    │ Donut usa color real, leyenda usa emoji
    │ CategoryChip en lista de tx pinta color tinta + emoji prefix
    │ BudgetStatusCard muestra swatch + emoji junto al nombre

 Usuario nuevo:
    │ POST /auth/register → seed_recommended()
    │ → ~18 categorías con color/emoji defaults coherentes

 Usuario existente sin color/emoji en categorías del seed:
    │ POST /seed/recommended (idempotente)
    │ → _upsert_category rellena los NULL
```

## Archivos clave

- `packages/ui/src/category-presets.ts` (nuevo)
- `apps/web/components/ui/category-appearance.tsx` (nuevo)
- `apps/mobile/components/categories/` (carpeta nueva)
- `apps/mobile/app/(modules)/personal-finance/categories.tsx` (nuevo)
- `apps/web/app/(app)/settings/categories/page.tsx` (pickers integrados)
- `apps/web/components/ui/category-chip.tsx` + `apps/mobile/components/ui/category-chip.tsx`
  (acepta color/icon)
- `apps/web/components/analysis/stitch-expense-breakdown.tsx`
  (donut con color real)
- `apps/mobile/components/dashboard/category-donut.tsx`
  (donut con color real)
- `apps/web/components/budgets/budget-status-card.tsx` +
  `apps/mobile/components/budgets/budget-status-card.tsx`
  (swatch + emoji)
- `backend/app/modules/personal_finance/seed/dataset.py`
  (color/emoji por categoría)
- `backend/app/modules/personal_finance/seed/service.py`
  (rellenar NULL en upsert)
- `backend/app/modules/personal_finance/dashboard/{repository,service,schemas}.py`
  (exponer category_color/category_icon)
- `packages/types/src/models/dashboard.ts` (campos en
  CategoryBreakdownItem)

## Endpoints añadidos

Ninguno. Se reusan `categories.*`, `dashboard.*`, `seed.*`.

## Migraciones

Ninguna — `categories.color` y `categories.icon` ya existían como
`nullable` en migraciones anteriores. Esta fase sólo los rellena
y los expone.

## Verificación

- [x] `pnpm typecheck`, `pnpm lint`, `pnpm test` verdes (40 web
      + 18 mobile).
- [x] `pytest backend/tests/` verde (321 tests).
- [x] Editar color/icon de una categoría existente → reload del
      dashboard muestra el color real en chips, donut y cards.
- [x] Crear categoría custom con picker → chip y donut respetan
      la elección.
- [x] Re-correr `POST /seed/recommended` para usuario con
      categorías existentes sin color → se rellenan sin duplicar.

## Decisiones tomadas

- **Emojis sobre librería de iconos** (lucide u otra). El emoji
  es nativo de la plataforma, sin dependencias, idéntico en web y
  mobile, expandible sin actualizar código. La librería de iconos
  habría requerido mantener un mapa cerrado de iconos disponibles
  en cada plataforma.
- **Paleta única para web y mobile** en `packages/ui`. Si alguna
  vez divergen los temas (dark mode con paleta distinta), añadir
  variantes; por ahora el set único es suficiente.
- **`DEFAULT_CATEGORY_COLOR`** en lugar de tono "neutro" para
  categorías sin color. Ayuda visualmente: cualquier categoría es
  reconocible por color, incluso si el usuario no lo configuró.
- **Tinta 15% para fondo de chip**, no fondo del color completo.
  Conserva legibilidad del label en cualquier tema y no compite
  con el resto del UI.
- **Migración del icon usando texto plano** (max 50 chars), no
  enum. Permite cualquier emoji incluyendo combinaciones (ZWJ
  sequences) sin tener que enumerar todas.

## Limitaciones conocidas

- **El donut mobile concatena el emoji al label** (`🍽️ Restaurantes`)
  en lugar de renderizarlo como elemento separado. `react-native-gifted-charts`
  no soporta nodos custom dentro de los slices. Aceptable visualmente.
- **Sin tema oscuro específico**. La paleta funciona en claro y
  oscuro pero algunos colores (yellow, lime) pueden tener contraste
  bajo en oscuro. Follow-up si se reportan quejas.
- **Re-seed tras editar a mano**. Si el usuario edita una categoría
  del seed, después borra y reseed, vuelve al default — la edición
  manual no persiste si la categoría se borra. Aceptable; el botón
  "Crear recomendadas" no sobrescribe lo que ya existe.

## Próxima fase

PHASE-21.2 — Cuentas declaradas + onboarding bloqueante +
account_id obligatorio en transacciones.
