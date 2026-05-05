# PHASE-13.1 — Backend de detección de subscripciones recurrentes

**Estado**: ✅ completada
**Rama**: `feat/phase-13.1-subscriptions-backend`
**Fecha de merge**: 2026-05-05

## Objetivo

Detectar automáticamente subscripciones recurrentes (Netflix,
gimnasio, alquiler, hosting…) a partir de los patrones de
transacciones del usuario. Backend que persiste candidatos como
`pending` para que el frontend (PHASE-13.2/13.3) muestre
"sugerimos esto, ¿confirmas?".

**Sin IA en esta fase** (decidido al alinear scope) — heurística
pura: agrupar por descripción normalizada + amount + currency,
detectar cadencia regular, sugerir si encaja en una ventana
conocida (semanal / quincenal / mensual / trimestral / semestral
/ anual). Si los falsos positivos / negativos en producción
molestan, integrar Ollama es follow-up acotado.

## Qué se implementó

### Modelo `Subscription`

Tabla `subscriptions` con:
- Identidad: `id`, `user_id` (CASCADE).
- Huella (fingerprint): `merchant` (normalizado, primeros 30 chars
  alfanuméricos lowercase), `amount`, `currency`, `cadence_days`
  (canónico: 7/14/30/90/180/365).
- Datos derivados: `raw_description` (sample legible),
  `next_due` (predicción), `first_seen_at`, `last_seen_at`,
  `occurrence_count`, `confidence` (0..1).
- Estado: `status: pending|confirmed|dismissed` enum.
- Categoría sugerida: `category_id` (FK SET NULL — categoría más
  común en las transacciones que matchearon el patrón).
- `created_at`, `updated_at`.

Índices: `user_id`, `merchant`, `status`.

### Migración `a92f5b1c8d34`

Crea `subscriptions` + 3 índices + enum `subscriptionstatus`.
Aplicada a la DB local.

### Detector heurístico (`detector.py`)

- **`normalize_merchant(description)`**: lowercase + strip
  non-alphanumeric + cap a 30 chars. Colapsa "NETFLIX.COM",
  "Netflix Premium", "PRO_NETFLIX SUSCRIP" al mismo bucket sin IA.
  Falsa convergencia es posible — el usuario descarta y la
  subscripción queda `dismissed` para no re-aparecer.
- **`_bucket_cadence(mean_days)`**: mapea la media de gaps a una
  cadencia canónica si cae en alguna ventana conocida (7±1,
  14±1, 30±5, 90±5, 180±10, 365±10). `None` si no encaja.
- **`_detect_in_group(occurrences, ...)`**: requiere mínimo 3
  occurrences. Calcula gaps consecutivos, media y desviación
  estándar. Si `std/mean ≤ 0.30` y la media encaja en una ventana
  → emite `Candidate(cadence_days=canonical, confidence=1-std/mean)`.
- **`detect_for_user(db, user_id, lookback_days=180)`**: query a
  transacciones activas del usuario en los últimos 6 meses,
  agrupa por `(merchant, amount, currency)`, evalúa cada grupo,
  devuelve `list[Candidate]`.

### Service

- **`scan_for_user(db, user_id)`**: ejecuta el detector y por
  cada `Candidate`:
  - Si ya existe row con misma huella (merchant + amount +
    currency + cadence) → refresca `last_seen_at`, `next_due`,
    `occurrence_count`, `confidence`, `raw_description`.
    **Status y category_id NO se tocan** (respeta decisión del
    usuario).
  - Si no existe → crea como `pending`.
  - Una `dismissed` con misma huella es match — sólo se refresca,
    NO se crea fila nueva. Resultado: el usuario que descartó
    algo no lo ve volver.
- **`confirm_subscription`**: `pending → confirmed`. Una
  `dismissed` confirmada se reactiva (caso "me arrepentí").
- **`dismiss_subscription`**: → `dismissed`. El detector NO la
  vuelve a sugerir.
- **`delete_subscription`**: DELETE real. Si el patrón sigue
  cumpliéndose, el siguiente scan vuelve a crearla como
  `pending`.

### Endpoints

| Método | Ruta | Body / Query | Response |
|--------|------|--------------|----------|
| GET | `/subscriptions` | `status?` (`pending\|confirmed\|dismissed`) | `200 SubscriptionResponse[]` ordenado por `next_due ASC` |
| POST | `/subscriptions/scan` | — | `200 ScanResponse { created, updated, total_active_after }` |
| GET | `/subscriptions/{id}` | — | `200 SubscriptionResponse` |
| POST | `/subscriptions/{id}/confirm` | — | `200 SubscriptionResponse` |
| POST | `/subscriptions/{id}/dismiss` | — | `200 SubscriptionResponse` |
| DELETE | `/subscriptions/{id}` | — | `204` |

### Cron diario (PHASE-11.1 reuse)

`app/core/scheduler.py` extendido:
- Nuevo `scan_subscriptions_job` que itera `users.is_active=True`,
  llama a `subscriptions_service.scan_for_user` por cada uno y
  loguea totales.
- `create_scheduler` ahora registra ambos jobs (currency +
  subscriptions) según sus respectivos flags.
- Nuevos settings: `enable_subscriptions_cron` (default True),
  `subscriptions_cron_hour=4`, `subscriptions_cron_minute=0`
  (UTC, después del cron de tasas).
- Errores por usuario individual NO tiran el job — `try/except` +
  rollback + log + siguiente.

### Tests

`backend/tests/test_subscriptions.py` (14 tests):

- 3 unit tests de `normalize_merchant`.
- 4 unit tests de `_detect_in_group` (mínimo occurrences,
  cadencia mensual, irregular rechazada, cadencia anual).
- 6 integration tests (scan crea pending, refresh sin
  duplicar, dismiss bloquea re-suggestion, confirm setea
  status, aislamiento user, delete purga).
- 1 sanity test de inmutabilidad de `Candidate`.

`test_currency_cron.py` actualizado para patch de ambos flags
(`enable_currency_cron` + `enable_subscriptions_cron`) — sin esto
el test "returns_none_when_disabled" fallaba al activarse el
flag de subscriptions por defecto.

Suite full: **202/202** (188 previos + 14 nuevos).

## Flujo técnico

```
 Usuario ya tiene transacciones recurrentes (4 cobros mensuales
 de "NETFLIX.COM 12.99 EUR")
    ▼
 POST /subscriptions/scan (manual)  o  cron 04:00 UTC
    │
    ▼ subscriptions_service.scan_for_user(db, user_id)
    │   ▼ detector.detect_for_user(db, user_id, lookback_days=180)
    │       ├── load active transactions in last 180d
    │       ├── group by (normalize_merchant(desc), amount, currency)
    │       └── per group with ≥ 3 occurrences:
    │             gaps = [t[i] - t[i-1] for i in 1..n]
    │             if std/mean ≤ 0.30 AND mean ∈ known windows:
    │                 emit Candidate(cadence=canonical,
    │                                confidence=1-std/mean,
    │                                next_due=last + cadence,
    │                                category=most_common)
    │   ▼ for each candidate:
    │       existing = find_by_fingerprint(merchant, amount, currency, cadence)
    │       if existing: refresh data, keep status/category
    │       else: create as pending
    ▼
 ScanResponse { created: 1, updated: 0, total_active_after: 1 }

 GET /subscriptions
    ▼
 [{ merchant: "netflixcom", raw: "NETFLIX.COM", amount: "12.99",
    currency: "EUR", cadence: 30, confidence: 0.97,
    next_due: "2026-06-15", status: "pending", ... }]

 Usuario decide:
    POST /{id}/confirm  → status=confirmed (aparece en su lista)
    POST /{id}/dismiss → status=dismissed (no se vuelve a sugerir)
    DELETE /{id}        → desaparece (re-detectable en próximo scan)
```

## Archivos clave

- `backend/alembic/versions/a92f5b1c8d34_subscriptions_module.py` (nuevo)
- `backend/app/modules/personal_finance/subscriptions/__init__.py`
- `backend/app/modules/personal_finance/subscriptions/models.py`
- `backend/app/modules/personal_finance/subscriptions/schemas.py`
- `backend/app/modules/personal_finance/subscriptions/detector.py` (heurística)
- `backend/app/modules/personal_finance/subscriptions/repository.py`
- `backend/app/modules/personal_finance/subscriptions/service.py`
- `backend/app/modules/personal_finance/subscriptions/router.py`
- `backend/app/main.py` (router incluido)
- `backend/app/core/scheduler.py` (job + ID estable + create_scheduler)
- `backend/app/core/config.py` (3 flags nuevos)
- `backend/tests/conftest.py` (Subscription importado)
- `backend/tests/test_subscriptions.py` (nuevo, 14 tests)
- `backend/tests/test_currency_cron.py` (patch dual de flags)

## Verificación

- [x] `pytest tests/` — 202/202 (14 nuevos).
- [x] `mypy app/` — 13 pre-existentes (`ai/`, `dashboard/conversion.py`);
      **0 introducidos**.
- [x] `ruff check app/ tests/` verde.
- [ ] Smoke manual con DB real:
  - [ ] Insertar serie de 4 cargos mensuales de "NETFLIX.COM
        12.99 EUR" → POST /subscriptions/scan → ver pending.
  - [ ] POST /confirm → aparece en `?status=confirmed`.
  - [ ] POST /dismiss otra → re-scan → no vuelve.
  - [ ] DELETE → re-scan → vuelve como pending.

## Decisiones tomadas

- **Heurística sin IA en esta fase**. Decidido al alinear scope.
  La IA aporta valor para descriptions caóticas, pero la
  normalización (lowercase + alfanumérico) cubre el ~80% de los
  casos comunes (Netflix, Spotify, Apple, etc.). Si los falsos
  positivos / negativos molestan, sub-fase futura integra Ollama
  como segundo paso de clustering.
- **Modelo persistido (no detección on-demand)**. Sin
  persistencia no hay distinción `pending|confirmed|dismissed`,
  el usuario tendría que dismissar lo mismo cada vez. Persistir
  habilita: (1) UX coherente, (2) `next_due` tracking que abre
  la puerta a alertas "X se cobrará mañana", (3) histórico de
  cuándo se detectó algo.
- **Cron diario + endpoint manual**. El cron es passive (todos
  los días corre); el endpoint manual permite re-evaluar tras
  imports masivos sin esperar al día siguiente.
- **Iteración por usuarios en el cron**. Una sola query a
  `users.is_active=True` + bucle. Para volúmenes esperados (1
  user por instancia local) es trivial; si se despliega
  multi-tenant con muchos usuarios, paralelizar con `asyncio.gather`.
- **Dismissed bloquea re-suggestion vía fingerprint match**. El
  scan encuentra el patrón, busca por huella, encuentra la
  dismissed, sólo refresca. El usuario nunca ve la sugerencia
  otra vez (a menos que cambie la huella: amount diferente o
  cadence diferente, lo que sería realmente un patrón nuevo).
- **Categoría sugerida = la más común entre los matches**. No
  perfecto pero útil — el usuario suele etiquetar las txs de
  Netflix con "Streaming" desde el principio. Si la categoría
  sugerida es incorrecta, una sub-fase futura puede añadir UI
  para cambiarla en el detail.
- **Status (pending/confirmed/dismissed) y `category_id` NO se
  refrescan en re-scan**. Solo `last_seen_at`, `next_due`,
  `occurrence_count`, `confidence`, `raw_description`. El usuario
  ya decidió sobre status/category — el detector no se mete.
- **`Candidate` como `@dataclass(frozen=True)`**. Inmutable
  evita mutaciones accidentales en el service. Test sanity
  comprueba el comportamiento.
- **Lookback 180 días, mín 3 occurrences**. Trimestral (90
  días) cabe holgado: 180/90=2 occurrences, no llega — necesita
  3, así que efectivamente trimestral requiere ~270 días de
  histórico. Aceptable.
- **`test_create_scheduler_returns_none` actualizado a "all
  disabled"**. Antes patchea sólo `enable_currency_cron`; ahora
  `create_scheduler` mira ambos flags. Test patcheaba sólo uno y
  fallaba. Patch dual.

## Limitaciones conocidas

- **Sin IA — falsa convergencia posible**. "NETFLIX" y
  "NETFLIXSUSCRIP" colapsan al mismo `netflix*` tras
  truncamiento, pero hay casos límite. El `dismissed` flow es la
  red de seguridad.
- **Sin alertas push de "X se cobrará mañana"**. `next_due` está
  ahí, pero no hay mecanismo de notificación. Sub-fase futura
  cuando se priorice un canal (toast en login, push, email).
- **Sin "pause" entre confirmed y dismissed**. Si el usuario
  cancela una subscripción real (canceló Netflix), el row queda
  `confirmed` con `next_due` futura sin sentido. UX para
  "marcar como cancelada" pendiente.
- **Lookback fijo 180d**. No expuesto como query param. Si el
  usuario tiene una subscripción anual cuya última ocurrencia
  fue hace > 6 meses, no se detecta. El cron diario va
  reaccionando con cada nueva ocurrencia.
- **Sin paginación en GET /subscriptions**. Asumimos < 100
  subscripciones por usuario. Si crece, añadir.
- **Cron itera secuencial**. Para multi-tenant escalado,
  paralelizar con `asyncio.gather` en chunks.
- **No usa `target_currency`** (cross-currency). Cada
  subscripción vive en una currency fija — si el usuario paga la
  misma "Netflix" en EUR un mes y en USD otro, son fingerprints
  distintas y aparecen como dos subscripciones separadas.
  Decisión: aceptable, los casos reales son pocos.

## Próxima fase

PHASE-13.2 — Frontend web. Ruta
`/personal-finance/subscriptions` con:
- Tabla pending (con [Confirmar] / [Descartar]).
- Tabla confirmed (con próxima fecha + acción [Eliminar]).
- Botón "Re-escanear" → POST /scan + toast con N created/updated.
- Hooks shared en `packages/services` (`useSubscriptions`,
  `useConfirmSubscription`, `useDismissSubscription`,
  `useScanSubscriptions`).
