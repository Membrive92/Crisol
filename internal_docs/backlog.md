# Backlog — deuda técnica, limitaciones y follow-ups

> Inventario consolidado de trabajo no hecho. Recopila las "Limitaciones
> conocidas" de cada fase + entradas `[tech-debt]` de `lessons.md` +
> follow-ups explícitos.
>
> Reglas:
>
> - Cada item lleva la fase origen entre corchetes (`[PHASE-X.Y]`) para
>   poder bajar al doc original.
> - Si una nueva fase resuelve algo de aquí, **se borra** del backlog
>   (no se tacha) — la phase doc deja la traza histórica.
> - Si un item se promueve a fase formal, se traslada a
>   `phases/phase-X.Y-*.md` y se borra de aquí.
> - Última actualización: 2026-05-05 (PHASE-10.3).

---

## Top candidatos prácticos

Si quieres atacar trabajo real (no polish), por orden:

1. **Cron nocturno de tasas (APScheduler)** — el lazy fetch cubre
   "primer uso del día", pero si la app pasa días sin abrirse las
   tasas se quedan atrás.
2. **`useCurrencyStore` cross-platform (AsyncStorage adapter)** —
   pre-requisito para que mobile herede el toggle `convertAll` y la
   moneda activa global del web.
3. **Sistema de toasts global** — el banner web y el snackbar mobile
   de "Movido a papelera" son ad-hoc para la pantalla de
   transacciones; otros flujos (imports, receipt confirm) siguen sin
   feedback de éxito.
4. **Captura de tickets por cámara mobile** (heredado de PHASE-5.2)
   — el backend ya lo soporta; falta integrar `expo-camera` /
   `expo-image-picker`.

---

## Multimoneda — follow-ups de fase 8

- **[PHASE-8.4]** `StitchRecentActivity` (sidebar del dashboard) sigue
  mostrando los 4 últimos movimientos en su moneda original. Para
  alinearlo con el toggle global, basta exponer `target_currency` en
  la query con `limit=4` y consumir `tx.converted_amount` en el
  componente. Decidido fuera de PHASE-8.4 para no convertir vistas
  compactas.
- **[PHASE-8.1 / 8.2 / 8.3]** Sin cron nocturno de tasas. El lazy
  fetch cubre "primer uso del día"; si nadie abre la app, las tasas
  no se refrescan. Añadir APScheduler o equivalente cuando moleste.
- **[PHASE-8.x]** JPY (y otras monedas sin decimales) redondea a 2.
  La política `quantize` per-currency vive en `currency.service` —
  habrá que añadirla cuando entren datos JPY reales.
- **[PHASE-8.3]** `ensure_rates_for_dates` hace una llamada a
  frankfurter por fecha (serial). Para 50 fechas distintas en frío
  son 50 round-trips. Paralelizar con `asyncio.gather` si la primera
  carga molesta.
- **[PHASE-8.4]** `previous_period_*` aún hace una segunda query
  contra `get_totals_by_kind`. Consolidar al 100% requeriría un
  SELECT con doble scope; no compensa la complejidad por ahora.

---

## Backend y dominio

### Auth

- **[PHASE-1.1]** Sin reset / "forgot password" ni verificación por
  email.
- **[PHASE-1.1]** Sin RBAC. No hace falta aún (single-user).
- **[PHASE-1.1]** Sin rate limiting en `/auth/login` —
  protección bruteforce pendiente.

### Transactions / categories

- **[PHASE-10.1]** Sin TTL / auto-purge nocturno de papelera. Si
  crece de forma indefinida, añadir cron en una fase futura.
- **[PHASE-10.1]** Receipts no soft-delete. Sólo transactions. Si
  hace falta, replicar el patrón.
- **[PHASE-2.1]** Search es `ILIKE` simple — sin full-text ni semántico.
- **[PHASE-2.1]** Sin idempotencia en `POST` (irrelevante hasta que
  haya bulk-create vía API).

### Dashboard

- **[PHASE-3.1]** Sin caching de agregaciones — cada request reejecuta
  `SUM`/`GROUP BY`. Aceptable para volúmenes personales; meter TTL
  cache si regresa la performance.

### Imports

- **[PHASE-4.1]** El fichero importado no se persiste. Para re-auditar
  hay que volver a subirlo.
- **[PHASE-4.1]** Sin endpoint de preview previo al import — el pipeline
  es síncrono y va a completion en el mismo request.
- **[PHASE-4.3]** PDFs sin texto extraíble (escaneados) terminan en
  `failed`. Fallback OCR vía Ollama documentado como branch
  `feat/pdf-vision-fallback` (no abierto).

### Receipts

- **[PHASE-5.1]** `ReceiptExtraction.line_items` se persiste pero no
  se materializa en transacciones individuales — el MVP crea **una**
  sola transacción con el total.
- **[PHASE-5.1]** Sin endpoint de descarga de blob ni presigned URL
  (`GET /receipts/{id}/blob` con presigned URL pendiente si la UI lo
  necesita).
- **[PHASE-5.1]** No hay smoke real de extracción end-to-end con un
  ticket de verdad — requiere `qwen2.5-vl:7b` descargado.

### IA local (módulo `ai`)

- **[PHASE-7.1]** Smart Insights es placeholder honesto en UI.
  Requiere madurar el módulo `ai` antes de generar consejos reales.

---

## Frontend web

- **[PHASE-1.2]** Refresh token en `localStorage` (no `httpOnly`).
  Documentado como MVP local-only — al desplegar, mover a cookie
  `httpOnly` vía backend.
- **[PHASE-4.2]** Mapping de columnas es free-text — sin validar
  contra cabeceras del fichero antes del upload. Si el usuario teclea
  un nombre que no está, el job termina con `rows_failed`.
- **[PHASE-4.2]** Jobs inmutables — sin retry/edit desde UI; re-subir
  el fichero es la única vía.
- **[PHASE-5.2]** Sin botón "re-invocar IA" si la extracción de un
  ticket es mala — toca editar manualmente o rechazar y resubir.
- **[PHASE-7.2]** Description en tabla truncada a 280px — sólo en el
  detalle se ve completo.
- **[PHASE-7.6]** Color e icono per-categoría: las columnas existen en
  BD (`categories.color`, `categories.icon`) pero el selector en UI
  está pendiente — hoy se pinta por `kind`.

---

## Mobile (área más débil)

- **[PHASE-5.2]** Sin captura por cámara. El backend ya lo soporta —
  falta integrar `expo-camera` / `expo-image-picker`.
- **[PHASE-9.2]** `convertAll` (toggle cross-currency global) sólo
  existe en web — `useCurrencyStore` persiste en `localStorage`.
  Pre-requisito: portar el store a `AsyncStorage` cross-platform.
- **[PHASE-9.2]** `MonthlyChart` ligado a año en curso (la query
  `useDashboardByMonth` sólo acepta `year`). Si se quiere "últimos
  12 meses rolling" o rango libre, requiere cambio en backend.
- **[PHASE-9.2]** `rangeForPeriod` duplicada entre web y mobile (15
  líneas puras). Mover a `packages/ui` cuando aparezca un tercer caller.
- **[PHASE-9.2]** `apps/mobile/components/dashboard/dashboard-filters.tsx`
  quedó sin callers tras PHASE-9.2 (lo reemplazó `currency-picker.tsx`).
  Eliminar si no resurge necesidad de year picker.
- **[PHASE-2.2]** Sin date picker nativo — input de texto con formato
  `YYYY-MM-DD`. `@react-native-community/datetimepicker` pendiente.
- **[PHASE-2.2]** Sin tests de UI mobile (`jest-expo` no configurado).
- **[PHASE-2.2]** Pull-to-refresh: web no tiene equivalente — depende
  de `staleTime` para revalidar.

---

## Infra / despliegue / seguridad

- **[PHASE-0.2]** Sin Dockerfile del backend — desarrollo corre uvicorn
  en host. Empaquetado deferido a fase de despliegue.
- **[PHASE-0.2]** Sin headers de seguridad (HSTS, CSP, X-Frame-Options).
  Pendiente reverse proxy (Caddy/Traefik) en despliegue.
- **[PHASE-0.3]** Modelo de visión no se descarga automático — `docker
  exec ollama pull qwen2.5-vl:7b` es manual. Automatizar en compose
  con `entrypoint` script.
- **[PHASE-1.1]** JWT secret de tests es corto — produce
  `InsecureKeyLengthWarning`. Producción usa ≥32 bytes (irrelevante
  pero ruido en logs de pytest).

---

## Tests

- **[PHASE-2.2]** Mobile component tests pospuestos — requieren
  `jest-expo` setup.
- **[PHASE-5.1]** Sin smoke real de extracción de ticket (requiere
  modelo descargado).
- **[PHASE-5.2]** Sin E2E de UI — la cobertura vive en lógica pura
  (formatters, query keys, endpoints).
- **[PHASE-8.1]** Sin smoke contra frankfurter real — todo mock.
  Periódicamente revisar contrato; si frankfurter cambia, lo veremos
  en producción antes que en CI.

---

## UX / polish menor

- **[PHASE-7.1]** `KpiDelta` con `previous=0` y `current!=0` no puede
  dividir por cero — muestra signo sin %. Caption "Nuevo" como mejora
  futura.
- **[PHASE-7.5]** Footer del "Flujo de caja neto" en Análisis muestra
  texto estático cuando no hay periodo previo, no flecha + % como en
  Dashboard. Consciente.
- **[PHASE-7.2]** Pagination con `maxButtons=5` puede pintar 6 en
  bordes (cosmético, raro).
- **[PHASE-8.2 / 8.3]** "≈ —" cuando falta tasa — aceptable como señal
  UX, pero un tooltip explicativo sería mejor.

---

## Tech debt resuelto — patrones a recordar

Estos son aprendizajes ya **aplicados** que conviene mantener en mente
al tocar zonas afines (la fuente canónica es `lessons.md`):

- Detección RN vs SSR vs browser → `navigator?.product === 'ReactNative'`.
- 204 con cookie en FastAPI: construir la `Response` final dentro del
  handler, no inyectarla.
- Cookies tras rewrite Next.js: `Path=/`.
- `exactOptionalPropertyTypes`: declarar `prop?: T | undefined` cuando
  el padre puede pasar `undefined` explícito.
- Vitest+JSX: `esbuild.jsx: 'automatic'` en cada `vitest.config`.
- Axios: NO fijar `Content-Type` por defecto; al reintentar tras
  refresh con `FormData`, borrar el header (boundary).
- Next.js dev: `experimental.proxyTimeout` ≥ 300s para endpoints
  lentos (IA local).
- FastAPI ≥ 0.116 con `status_code=204`: declarar
  `response_class=Response` explícito y devolver `Response(status_code=204)`.
- `model_validate` post-`flush()` con `onupdate=func.now()`: hacer
  `await db.refresh(obj)` antes de serializar.
- jsdom no implementa `Blob.text()` — usar `FileReader` para tests de
  parsers de ficheros.
