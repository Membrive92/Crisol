---
version: alpha
name: Finanzas App
description: >
  Personal-finance suite with a modular, multi-portfolio shell. Tone is
  calm and analytical: dark by default, neutral surfaces, blue brand
  accent, semantic tonal chips for status. Privacy-first, local-first.

colors:
  primary: "#2f6fb8"
  primary-dark: "#245690"
  on-primary: "#f4f7fb"
  primary-soft: "#1d2a3d"

  background: "#0f1115"
  surface: "#171a21"
  surface-muted: "#1f232c"

  border: "#272c36"
  border-strong: "#3a4150"

  text: "#e6e7ea"
  text-muted: "#9aa0aa"
  text-subtle: "#6c7280"

  success: "#6dc788"
  success-soft: "#1c2a20"
  danger: "#ef6e6e"
  danger-soft: "#3a1f1f"
  warning: "#f5b461"
  warning-soft: "#322318"

  income: "#6dc788"
  expense: "#ef6e6e"

  light-background: "#fafafa"
  light-surface: "#ffffff"
  light-surface-muted: "#f5f5f5"
  light-border: "#e0e0e0"
  light-border-strong: "#bdbdbd"
  light-text: "#1f1f1f"
  light-text-muted: "#666666"
  light-text-subtle: "#8a8a8a"
  light-primary: "#1976d2"
  light-primary-dark: "#115293"
  light-primary-soft: "#e3eefb"
  light-on-primary: "#f7f9fc"
  light-success-soft: "#e8f5e9"
  light-danger-soft: "#fdecea"
  light-warning-soft: "#fff4e5"

typography:
  display:
    fontFamily: system-ui
    fontSize: 32px
    fontWeight: "700"
    lineHeight: 40px
    letterSpacing: -0.01em
  heading-xl:
    fontFamily: system-ui
    fontSize: 24px
    fontWeight: "700"
    lineHeight: 32px
    letterSpacing: -0.01em
  heading-lg:
    fontFamily: system-ui
    fontSize: 18px
    fontWeight: "600"
    lineHeight: 24px
  heading-md:
    fontFamily: system-ui
    fontSize: 16px
    fontWeight: "600"
    lineHeight: 22px
  body:
    fontFamily: system-ui
    fontSize: 16px
    fontWeight: "400"
    lineHeight: 24px
  body-sm:
    fontFamily: system-ui
    fontSize: 14px
    fontWeight: "400"
    lineHeight: 20px
  caption:
    fontFamily: system-ui
    fontSize: 12px
    fontWeight: "500"
    lineHeight: 16px
  label:
    fontFamily: system-ui
    fontSize: 14px
    fontWeight: "500"
    lineHeight: 20px
  button:
    fontFamily: system-ui
    fontSize: 14px
    fontWeight: "600"
    lineHeight: 20px
  overline:
    fontFamily: system-ui
    fontSize: 12px
    fontWeight: "600"
    lineHeight: 16px
    letterSpacing: 0.04em
    textTransform: uppercase

spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px

rounded:
  sm: 4px
  md: 8px
  lg: 12px
  pill: 9999px

elevation:
  flat: none
  raised: 0 1px 2px rgba(0, 0, 0, 0.18)
  overlay: 0 12px 32px rgba(0, 0, 0, 0.32)

motion:
  duration-instant: 80ms
  duration-fast: 120ms
  duration-base: 150ms
  ease-standard: cubic-bezier(0.2, 0, 0, 1)

borders:
  hairline: 1px solid {colors.border}
  strong: 1px solid {colors.border-strong}
  primary: 1px solid {colors.primary}
  divider: 1px solid {colors.border}
  focus-ring: 2px solid {colors.primary}

components:
  button-primary:
    background: "{colors.primary}"
    foreground: "{colors.on-primary}"
    border: "{borders.primary}"
    radius: "{rounded.md}"
    paddingY: "{spacing.sm}"
    paddingX: "{spacing.md}"
    fontWeight: "600"
    typography: "{typography.button}"
  button-secondary:
    background: transparent
    foreground: "{colors.primary}"
    border: "{borders.primary}"
    radius: "{rounded.md}"
    paddingY: "{spacing.sm}"
    paddingX: "{spacing.md}"
    typography: "{typography.button}"
  button-danger:
    background: "{colors.danger}"
    foreground: "{colors.on-primary}"
    border: 1px solid {colors.danger}
    radius: "{rounded.md}"
    paddingY: "{spacing.sm}"
    paddingX: "{spacing.md}"
    typography: "{typography.button}"
  button-ghost:
    background: transparent
    foreground: "{colors.text}"
    border: "{borders.hairline}"
    radius: "{rounded.md}"
    paddingY: "{spacing.sm}"
    paddingX: "{spacing.md}"
    typography: "{typography.button}"
  card:
    background: "{colors.surface}"
    border: "{borders.hairline}"
    radius: "{rounded.md}"
    padding: "{spacing.md}"
    elevation: "{elevation.flat}"
  input:
    background: "{colors.surface}"
    foreground: "{colors.text}"
    placeholder: "{colors.text-subtle}"
    border: "{borders.hairline}"
    radius: "{rounded.sm}"
    paddingY: "{spacing.sm}"
    paddingX: "{spacing.sm}"
    focusRing: "{borders.focus-ring}"
    typography: "{typography.body}"
  field-label:
    foreground: "{colors.text}"
    typography: "{typography.label}"
    marginBottom: "{spacing.xs}"
  module-switcher:
    background: "{colors.surface}"
    backgroundHover: "{colors.surface-muted}"
    foreground: "{colors.text}"
    border: "{borders.hairline}"
    borderOpen: "{borders.strong}"
    radius: "{rounded.md}"
    indicatorDot: "{colors.primary}"
    paddingY: 6px
    paddingX: 12px
    typography: "{typography.button}"
  module-switcher-menu:
    background: "{colors.surface}"
    border: "{borders.hairline}"
    radius: "{rounded.md}"
    elevation: "{elevation.overlay}"
    optionRadius: "{rounded.sm}"
    optionPadding: 8px 12px
    activeBackground: "{colors.surface-muted}"
    hoverBackground: "{colors.surface-muted}"
    activeBadgeForeground: "{colors.primary}"
    disabledForeground: "{colors.text-subtle}"
  module-section-tab:
    background: transparent
    backgroundActive: "{colors.surface-muted}"
    backgroundHover: "{colors.surface-muted}"
    foreground: "{colors.text-muted}"
    foregroundActive: "{colors.text}"
    radius: "{rounded.md}"
    paddingY: 6px
    paddingX: 12px
    underline: 2px solid {colors.primary}
    typography: "{typography.button}"
  status-badge-pending:
    background: "{colors.primary-soft}"
    foreground: "{colors.primary}"
    radius: "{rounded.sm}"
    paddingY: "{spacing.xs}"
    paddingX: "{spacing.sm}"
    typography: "{typography.overline}"
  status-badge-confirmed:
    background: "{colors.success-soft}"
    foreground: "{colors.success}"
    radius: "{rounded.sm}"
    paddingY: "{spacing.xs}"
    paddingX: "{spacing.sm}"
    typography: "{typography.overline}"
  status-badge-rejected:
    background: "{colors.danger-soft}"
    foreground: "{colors.danger}"
    radius: "{rounded.sm}"
    paddingY: "{spacing.xs}"
    paddingX: "{spacing.sm}"
    typography: "{typography.overline}"
  app-header:
    background: "{colors.surface}"
    border: "{borders.hairline}"
    paddingY: "{spacing.md}"
    paddingX: "{spacing.lg}"
  app-page:
    maxWidth: 960px
    paddingY: "{spacing.lg}"
    paddingX: "{spacing.lg}"

layout:
  page-max-width: 960px
  page-max-width-wide: 1100px
  page-padding: 24px
  header-padding: 16px 24px
  section-gap: 24px
  card-gap: 16px
  field-gap: 16px
---

## Brand & Style

Finanzas App is a personal-finance suite designed for calm, analytical
work. The product is private by default — data lives locally and AI
runs locally — and the design language reflects that promise: muted
palettes, generous breathing room, and minimal chrome that gets out of
the way of numbers.

The default theme is dark. Backgrounds are not pure black; they sit on
a near-charcoal blue scale (`#0f1115` page → `#171a21` surface →
`#1f232c` muted) so cards and panels feel like layered paper rather
than holes. The brand accent is a single deep blue (`#2f6fb8`) used
sparingly: solid only for primary CTAs, otherwise it appears as the
1-px outline of secondary buttons or as a 2-px underline beneath the
active tab. A complementary light theme exists with the same structure
and contrast targets; see the `light-*` color tokens for the inverted
palette.

Status uses a tonal-chip pattern across both themes: a tinted
background paired with a saturated foreground of the same hue. In dark
mode the soft tints are deliberately *dark* (`#1c2a20`, `#3a1f1f`,
`#322318`) — never pastel pink or pastel green — so the chips feel
embedded in the surface, not stickered onto it.

## Colors

`primary` is the only chromatic accent in the chrome. Everything else
uses the neutral grey-blue ramp (`background`, `surface`,
`surface-muted`, `border`, `border-strong`, `text`, `text-muted`,
`text-subtle`). Three semantic colors — `success`, `danger`, `warning`
— appear only on status surfaces (badges, error messages, charts);
they never decorate layout.

The `*-soft` variants are the canonical tonal backgrounds (`primary-soft`,
`success-soft`, `danger-soft`, `warning-soft`). They are always paired
with the saturated counterpart as foreground. Do **not** apply
`rgba(color, 0.1)` at runtime: the soft tints are picked per theme so
they read correctly against both `surface` and `background`.

`income` and `expense` are domain-specific aliases of `success` and
`danger` and exist so charts and amounts can be color-coded without
implying success/failure.

## Typography

The product uses a system font stack (`-apple-system`, `Segoe UI`,
`Roboto`…) — there are no custom typefaces and no web-fonts to load.
This is deliberate: financial UIs need to render fast and look native
on every OS, and a system stack respects the user's accessibility
settings (size, weight, OpenType features).

Hierarchy is built mainly through size and weight, not color. Three
weights are in use: regular (400) for body, medium (500) for labels
and inactive nav, semibold (600) for buttons, headings, and active
nav, bold (700) for the page title. The largest size in regular use
is `heading-xl` (24px); `display` (32px) is reserved for empty
states or marketing surfaces.

The `overline` style — 12px semibold uppercase with `0.04em`
letter-spacing — is the badge typography. It also labels minor
section dividers ("Gastos", "Ingresos"). Tabular numbers should be
rendered with `font-variant-numeric: tabular-nums` whenever amounts
appear in tables or KPI cards (not encoded as a token, but expected).

## Layout & Spacing

Spacing is a 4-px grid: `xs: 4`, `sm: 8`, `md: 16`, `lg: 24`,
`xl: 32`, `xxl: 48`. `md` is the default gap between siblings;
`lg` is the page padding and the gap between sections.

Pages live in a single centered column. List pages cap at 960px,
the dashboard at 1100px. The application chrome is a two-row header
fixed to the top: brand + module switcher + account actions on row
one; section tabs on row two. Both rows align to the same horizontal
gutter as the page content.

Forms use vertical stacking only — never side-by-side fields except
for tightly related pairs (importe + moneda, fecha + hora). Field
labels sit above their inputs at 14-px medium, with `xs` (4-px) of
breathing room below the label and `md` (16-px) between consecutive
fields.

## Elevation & Depth

Three levels:

- `flat` — the default. Cards, inputs, and the header sit on the
  surface with a 1-px hairline border. No shadow.
- `raised` — `0 1px 2px rgba(0,0,0,0.18)`. Reserved; not currently in
  active use, kept for future toast-style notifications.
- `overlay` — `0 12px 32px rgba(0,0,0,0.32)`. Used by the module
  switcher dropdown and any future popovers. The shadow is heavier
  than typical because the overlay sits on dark surfaces; in light
  theme it should soften to `rgba(0,0,0,0.12)`.

Depth is communicated primarily through tonal layering of surfaces
(`background` < `surface` < `surface-muted`) rather than shadows.
A panel placed on `surface` and a hovered button placed on
`surface-muted` already read as different planes without any cast
shadow.

## Shapes

Three radii cover the system:

- `sm: 4px` — inputs, status badges. Tight, almost rectangular,
  appropriate for dense data surfaces.
- `md: 8px` — buttons, cards, dropdown menus. The default for any
  interactive container.
- `lg: 12px` — large feature cards (dashboard charts, hero panels).

A `pill` token (`9999px`) is reserved for chip-style filters and
avatar containers. There are no fully circular elements in chrome
except for the 8-px module indicator dot.

## Components

### Buttons

Primary CTA: solid `primary` background, `on-primary` foreground,
`md` radius. Used for the strongest action on the screen — "Confirmar
y crear transacción", "Iniciar sesión", "Crear cuenta", "Analizar
ticket".

Secondary CTA: transparent background, `primary` foreground and 1-px
`primary` border. Used for supporting actions in list-page headers
("+ Subir ticket", "+ Nueva", "+ Nueva importación") and as the
companion to a primary button in two-action rows.

Danger: solid `danger` background, used only for irreversible
destructive actions ("Rechazar ticket", "Eliminar categoría" once
confirmed). Always preceded by a confirmation step.

Ghost: transparent background with a neutral hairline border. Used
for pagination ("← Anterior", "Siguiente →") and inline cancel
actions.

All buttons share `md` radius, semibold 14-px label, `sm × md`
padding, `0.5` opacity when disabled, and a `120ms` opacity
transition.

### Cards

A surface container with hairline border, `md` radius, and `md`
padding by default. Cards do not stack shadows on each other — when
a modal/sheet is needed, use the `overlay` elevation on a dropdown
or the future popover, not on cards.

### Inputs

Single-line text inputs, textareas, and selects share the same
shell: `surface` background, hairline border, `sm` radius, `sm`
padding, body typography. Focus state is a 2-px `primary` outline
with 1-px offset (set globally on `input`, `textarea`, `select`).
The native date-picker indicator is inverted in dark mode so the
icon stays legible.

### Module Switcher

A chip in the top-left of the header. Layout: 8-px primary-color
dot, label, chevron. Hovered or open it picks up the
`surface-muted` background; when open, the border deepens to
`border-strong`.

The dropdown opens 6-px below, anchored left, minimum width 260-px.
Each option is a button with the same dot pattern (primary for the
active module, neutral grey for enabled but inactive, subtle for
disabled "Próximamente" modules). Active option also shows a small
"Activo" caption in primary on the right; disabled options show
"Próximamente" in `text-subtle`.

### Module Section Tabs

A horizontal row of pill-style links. Inactive tabs render as
muted text on a transparent background; hover or active state
fills the pill with `surface-muted` and lifts the foreground to
full text color. The active tab also draws a 2-px `primary`
underline 1-px below the pill, inset to the pill's horizontal
padding so it visually wraps the label rather than the whole row.

### Status Badges

A 2-px-radius rounded rectangle, `xs` vertical / `sm` horizontal
padding, overline typography. Three variants — pending, confirmed,
rejected — pair the matching `*-soft` background with the
saturated foreground. The pending variant uses `primary-soft` and
`primary` so that it reads as "in progress" without implying
success. Badges always sit inline next to the entity title; they
never appear alone or as a row marker.

### Dashboard KPI cards

Standard `card` with a 32-px display number on the first line and
a 14-px muted label on the second. Income amounts use `income`,
expense amounts use `expense`, balance uses `text` (positive)
or `expense` (negative). KPIs do not carry tonal backgrounds — the
neutrality keeps the focus on the number.

## Do's and Don'ts

**Do** — use the `*-soft` tokens for any status background. They
adapt per theme and pair correctly with their saturated counterpart.

**Do** — keep one strong CTA per screen. Use the `secondary`
button variant when two actions of similar weight share a row.

**Do** — communicate depth with surface layering before reaching
for shadows. `surface-muted` over `surface` already feels lifted.

**Don't** — apply `rgba(color, 0.x)` at runtime to fake tonal
backgrounds. The result clashes against either theme; use the
predefined `*-soft` tokens instead.

**Don't** — introduce a second chromatic accent. The blue is the
only brand color; new semantic states (info, neutral) should
extend the existing soft-tonal pattern rather than introduce new
hues.

**Don't** — use color alone to convey state. Always pair with an
icon, label, or shape. Income vs expense is also encoded through
sign and category, not just `success`/`danger` color.

**Don't** — reduce the radius scale. Three steps (`sm` 4 / `md` 8
/ `lg` 12) is enough for the entire product; introducing 6-px or
10-px radii fragments the visual rhythm.
