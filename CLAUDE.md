# Crisol — Monorepo híbrido (web + móvil)

## Stack
- Frontend: Next.js (web) + Expo/React Native (móvil) + Turborepo + pnpm
- Backend: FastAPI + SQLAlchemy 2.0 + PostgreSQL 16
- Lang: TypeScript strict (frontend), Python 3.12+ (backend)

## Documentación clave
- **Guía maestra para entender y continuar el proyecto sin contexto previo:
  internal_docs/PROJECT-GUIDE.md (leer PRIMERO si llegas nuevo)**
- **Estado de HOY (qué está sin probar, qué sigue): internal_docs/HANDOFF.md**
- Índice de internal docs: @internal_docs/README.md
- Arquitectura del sistema: @internal_docs/architecture.md
- Desglose de fases y metodología: @internal_docs/development-spec.md
- Errores conocidos y lecciones: @internal_docs/lessons.md
- Contexto de consulta bajo demanda para IA: internal_docs/ai-context/
  (no se carga por defecto — Claude lo consulta cuando necesita glosario del
  dominio, ejemplos anonimizados, evaluaciones de modelos o prompts guardados)

## Skills
- Frontend best practices: .claude/skills/frontend-best-practices/SKILL.md
  - IMPORTANTE: Leer SIEMPRE la skill y la referencia relevante antes de generar 
    código frontend. Contiene patrones de componentes, arquitectura del monorepo, 
    gestión de estado (Zustand + TanStack Query), y estándares de testing/calidad.
  - Las referencias están en .claude/skills/frontend-best-practices/references/
    (architecture.md, components.md, state-and-data.md, testing-and-quality.md)
- IA local: no hay skill aparte. Las reglas viven en la sección «IA local» de
  abajo y el módulo en `backend/app/modules/ai/` (cliente Ollama,
  `extract_receipt`, `extract_bank_statement_page`, `/ai/health`).

## IA local — principios no negociables
- Runtime: Ollama (local). Modelo visión por defecto: qwen2.5-vl:7b.
- Los datos del usuario NUNCA salen del equipo. Sin APIs externas.
- Solo `backend/app/modules/ai/` importa el cliente HTTP. Otros módulos usan
  `ai.service.<función>` y reciben tipos del dominio.
- La IA sugiere, el usuario confirma. Nada se persiste en BD sin confirmación.
- Respuestas del modelo siempre validadas con Pydantic antes de devolverse.

## Comandos

### Frontend
```bash
pnpm dev              # Ambas apps
pnpm dev:web          # Solo web
pnpm dev:mobile       # Solo móvil
pnpm lint             # Lint todo
pnpm typecheck        # TypeScript check todo
pnpm test             # Tests todo
pnpm format           # Prettier
```

### Backend
```bash
cd backend
uvicorn app.main:app --reload                    # Dev server
pytest tests/ -v                                 # Todos los tests (NUNCA dos a la vez: una sola BD de test)
pytest tests/test_auth.py -v                     # Tests de un módulo (ficheros planos test_*.py)
alembic upgrade head                             # Aplicar migraciones
alembic revision --autogenerate -m "desc"        # Nueva migración
mypy app/                                        # Type check Python
```

### Docker
```bash
docker compose up -d          # Postgres + MinIO + Ollama (el backend corre en el host)
docker compose down           # Parar todo
```

### Entorno de desarrollo (Windows) — reglas duras
- `.\dev.ps1` levanta todo en ventanas separadas; `.\dev.ps1 -Stop` lo para.
- El backend de dev escucha en el puerto de `apps/web/.env.local`
  (`BACKEND_ORIGIN`, hoy 8002), NO en el 8000 del Makefile. Si «los cambios del
  backend no aparecen», comprueba puerto y uvicorn zombi antes que el código.
- Intérprete del backend: `backend/.venv/Scripts/python.exe` (3.12, el de CI).
  El `python` del PATH es otro y su verde no vale.
- NUNCA dos `pytest` a la vez (incluidos los de subagentes): comparten
  `crisol_test`. Redirige la suite a fichero; `| tail` enmascara el exit code.
- Formatear: `prettier --write <fichero>`, nunca `pnpm format`.
- Un test nuevo se verifica ROMPIENDO la línea que dice proteger y comprobando
  que la rotura entró (ver internal_docs/lessons.md).

## Reglas de código — OBLIGATORIAS

### TypeScript (frontend)
- NUNCA usar `any` — usar `unknown` + narrowing
- NUNCA usar `as` salvo en boundaries de API
- NUNCA usar `@ts-ignore` — usar `@ts-expect-error` con comentario
- Imports: externos → packages internos (@app/*) → relativos → types
- Componentes en packages/ui/ NUNCA hacen data fetching
- Estado servidor → TanStack Query. Estado cliente global → Zustand
- Estilos → NativeWind/Tailwind. NUNCA StyleSheet.create en packages/

### Python (backend)
- Cada módulo: router.py → service.py → repository.py → models.py → schemas.py
- NUNCA string interpolation en queries SQL — siempre parámetros bind
- NUNCA importar entre módulos directamente — usar dependency injection
- Todos los endpoints validan input con Pydantic
- Funciones async por defecto (asyncio + asyncpg)
- Decimal para todo lo monetario — NUNCA float

### Ambos
- Funciones públicas documentadas (JSDoc / docstring)
- Tests para toda lógica de negocio
- No instalar dependencias no especificadas sin documentar en internal_docs/decisions/

## Desarrollo incremental
- IMPORTANTE: Leer internal_docs/development-spec.md antes de cada fase
- Diseño original: rama `feat/phase-X.Y-nombre` → PR → CI verde → squash merge.
  **Práctica real**: commit sólo tras la prueba manual del usuario y push
  directo a `main`. Comprueba `git log origin/main..HEAD` antes de dar algo por subido
- Cada fase se documenta en internal_docs/phases/ ANTES del merge
- Commits: `tipo(scope): descripción — Refs: PHASE-X.Y` — mensaje en INGLÉS;
  la documentación, en español
- NO anticipar funcionalidad de fases futuras
- Al terminar una fase: lint + typecheck + tests + knip + `check_docs.py` deben
  pasar (local Y en CI); phase doc en internal_docs/phases/, fila en
  internal_docs/README.md, endpoints/schema si tocan, HANDOFF reescrito
- Un commit (o pocos) = una fase. No mezclar fases.

## Verificación rápida
```bash
# Ejecutar ANTES de marcar una fase como completada (incluye knip y check_docs)
make verify
# o, a mano y con el intérprete del proyecto:
pnpm lint && pnpm typecheck && pnpm test && pnpm knip && python scripts/check_docs.py
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q && .venv/Scripts/python.exe -m mypy app/ scripts/
```

## Lecciones aprendidas
Ver @internal_docs/lessons.md — se actualiza cada vez que se corrige un error.
Si cometes un error que se podría prevenir, AÑÁDELO a lessons.md.
