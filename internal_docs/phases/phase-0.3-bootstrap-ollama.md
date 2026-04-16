# PHASE-0.3 — Bootstrap Ollama

**Estado**: ✅ completada
**Rama**: `feat/phase-0.3-bootstrap-ollama`

## Objetivo

Añadir Ollama como servicio en docker-compose, crear el módulo `ai/` en el
backend con un cliente HTTP mínimo y un endpoint `/ai/health` que verifica
la conectividad con Ollama y la disponibilidad del modelo de visión.

## Qué se implementó

- **`docker-compose.yml`** — nuevo servicio `ollama` (imagen `ollama/ollama`,
  puerto 11434, volumen persistente, comentario para GPU NVIDIA).
- **`backend/app/core/config.py`** — nuevas settings: `ollama_base_url`,
  `ollama_vision_model`, `ollama_timeout_seconds`.
- **`backend/app/modules/ai/`** — primer módulo del backend:
  - `client.py` — único archivo que habla con Ollama via httpx async.
    Funciones: `ping()`, `list_models()`, `is_model_available()`.
  - `router.py` — `GET /ai/health` (response model: `AiHealthResponse`).
  - `schemas.py` — `AiHealthResponse` (Pydantic).
  - `exceptions.py` — `AiError`, `AiUnavailableError`, `AiTimeoutError`,
    `AiInvalidOutputError`.
- **`backend/app/main.py`** — registra el router del módulo `ai`.
- **Tests** (3 tests nuevos, todos mockeando `client.ping` / `is_model_available`):
  - `test_ai_health_ollama_up` — Ollama responde + modelo disponible.
  - `test_ai_health_ollama_down` — Ollama no responde.
  - `test_ai_health_model_missing` — Ollama responde pero modelo no descargado.

## Endpoints añadidos

- `GET /ai/health` — devuelve:
  ```json
  {
    "status": "ok | degraded",
    "ollama": "connected | unavailable",
    "model": "qwen2.5-vl:7b",
    "model_available": true | false
  }
  ```

## Verificación

- [x] `ruff check app tests` verde
- [x] `black --check app tests` verde
- [x] `mypy app` verde
- [x] `pytest -v` verde (4 tests: 3 ai + 1 health)
- [x] `docker compose up -d ollama` arranca y responde en `localhost:11434`
- [x] Cliente async `ping()` devuelve `True` contra Ollama real
- [x] `is_model_available()` devuelve `False` (modelo no descargado aún — correcto)

## Descargar el modelo de visión (manual, no automático)

```bash
docker exec -it finanzas-ollama ollama pull qwen2.5-vl:7b
```

Tarda ~5 minutos (modelo de ~5 GB). Tras la descarga, `/ai/health` devolverá
`model_available: true`.

## Decisiones tomadas

- **El módulo `ai/` no tiene `models.py` ni `repository.py`** — no gestiona
  tablas propias. Su `client.py` equivale al repository de otros módulos.
- **Los tests mockean `client.ping` y `client.is_model_available`**, no el
  transporte HTTP — los módulos consumidores mockean `ai.service` (PHASE-5.1),
  y los tests del propio módulo mockean las funciones del cliente.
- **No se auto-descarga el modelo en compose** — docker compose up debe ser
  rápido; la descarga de 5 GB es un paso manual documentado.
- **Excepciones con sufijo `Error`** — convención `ruff N818`.

## Limitaciones conocidas

- El modelo de visión no se descarga automáticamente. Es un paso manual tras
  el primer `docker compose up`.
- `client.py` solo expone `ping`, `list_models` e `is_model_available`.
  La función `generate_vision` (inferencia real) se implementa en PHASE-5.1.
- No hay tests de integración contra Ollama real en CI — Ollama no corre como
  service container en GitHub Actions (imagen pesada). Los tests lo mockean.

## Próxima fase

PHASE-1.1 — Auth backend: módulos `users/` + `auth/`, endpoints register, login,
refresh, logout, me. JWT access + refresh con rotación. Argon2id. Tests de
aislamiento multi-usuario.
