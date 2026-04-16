# PHASE-1.1 — Auth backend

**Estado**: ✅ completada
**Rama**: `feat/phase-1.1-auth-backend`

## Objetivo

Implementar autenticación completa: registro, login, JWT con refresh token
en BD (revocable y rotable), logout, endpoint `/me`, y tests de aislamiento
multi-usuario.

## Qué se implementó

### Módulos

- **`users/`** — modelo `User` (UUID, email unique, password_hash argon2id,
  display_name, is_active, timestamps). Repository: `get_by_id`, `get_by_email`,
  `create`.
- **`auth/`** — modelo `RefreshToken` (UUID, user_id FK, token_hash, expires_at,
  revoked). Router con 5 endpoints. Service con lógica de register, login,
  refresh (rotación), logout, logout_all.
- **`core/security.py`** — hashing argon2id + JWT (PyJWT): `hash_password`,
  `verify_password`, `create_access_token`, `create_refresh_token`,
  `hash_refresh_token`, `verify_refresh_token`, `decode_access_token`.
- **`core/deps.py`** — `get_current_user` dependency + type alias `CurrentUser`.

### Primera migración real

`333677d9875f_create_users_and_refresh_tokens_tables.py` — crea tablas `users`
y `refresh_tokens` con índices en `email` y `user_id`.

### Dependencias añadidas

- `argon2-cffi` — password hashing (argon2id)
- `PyJWT[crypto]` — JWT tokens
- `email-validator` — validación de EmailStr en Pydantic

## Endpoints añadidos

| Método | Ruta             | Auth | Descripción |
|--------|------------------|------|-------------|
| POST   | /auth/register   | No   | Registra usuario, devuelve tokens |
| POST   | /auth/login      | No   | Login, devuelve tokens |
| POST   | /auth/refresh    | No   | Rota refresh token |
| POST   | /auth/logout     | Sí   | Revoca refresh token |
| GET    | /auth/me         | Sí   | Datos del usuario autenticado |

## Verificación

- [x] `ruff check app tests` verde
- [x] `black --check app tests` verde
- [x] `mypy app` verde (strict)
- [x] `alembic upgrade head` verde (tablas creadas)
- [x] `pytest -v` verde (15 tests: 11 auth + 3 ai + 1 health)

## Tests

- `test_register_ok` — registro exitoso
- `test_register_duplicate_email` — 409
- `test_login_ok` — login devuelve tokens
- `test_login_wrong_password` — 401
- `test_login_nonexistent_user` — 401
- `test_refresh_ok` — nuevo access + refresh, viejo revocado
- `test_refresh_revoked_token` — reuso de token revocado → 401
- `test_logout_ok` — revoca el refresh token
- `test_me_ok` — devuelve datos correctos
- `test_me_unauthorized` — sin token → 401
- `test_user_isolation` — usuario A ≠ usuario B

## Decisiones tomadas

- **Refresh tokens en BD** (no stateless) — permite revocación real, rotación
  con detección de robo, y logout de todos los dispositivos.
- **`auth/` importa `User` de `users/models.py`** — única excepción aceptable
  a la regla "no imports entre módulos" (los modelos ORM son la interfaz
  compartida).
- **`NullPool` en test engine** — evita el error `another operation in progress`
  de asyncpg cuando ASGITransport y tests comparten event loop.
- **Truncate tables por test** (no transaction rollback) — más robusto con
  asyncpg + async FastAPI.
- **Argon2id para refresh tokens** — un refresh token es un secreto, se hashea
  igual que un password.

## Limitaciones conocidas

- JWT warning `InsecureKeyLengthWarning` en tests: el secret por defecto es
  corto. En producción se configura uno de ≥32 bytes.
- No hay rate limiting en login.
- No hay "forgot password" ni email verification.
- No hay roles/permisos (no los necesitamos aún).
- `_find_matching_token` itera todos los tokens activos — aceptable con pocos
  usuarios. Si escala, se puede indexar por un hash parcial.

## Próxima fase

PHASE-1.2 — Auth frontend: pantallas login/register en web y mobile, store de
sesión (Zustand), interceptor HTTP con refresh automático, logout limpia estado.
