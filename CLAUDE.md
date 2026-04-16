# Finanzas App — Monorepo híbrido (web + móvil)

## Stack
- Frontend: Next.js (web) + Expo/React Native (móvil) + Turborepo + pnpm
- Backend: FastAPI + SQLAlchemy 2.0 + PostgreSQL 16
- Lang: TypeScript strict (frontend), Python 3.12+ (backend)

## Documentación clave
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
- Local AI integration: pendiente — se creará en PHASE-5.1 cuando se implemente
  el módulo `backend/app/modules/ai/` y el pipeline de extracción de tickets.

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
pytest tests/ -v                                 # Todos los tests
pytest tests/modules/test_auth.py -v             # Tests de un módulo
alembic upgrade head                             # Aplicar migraciones
alembic revision --autogenerate -m "desc"        # Nueva migración
mypy app/                                        # Type check Python
```

### Docker
```bash
docker compose up -d          # Levantar todo
docker compose logs -f app    # Ver logs backend
docker compose down           # Parar todo
```

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
- Cada fase es una rama `feat/phase-X.Y-nombre` → PR → CI verde → squash merge a main
- Cada fase se documenta en internal_docs/phases/ ANTES del merge
- Commits: `tipo(scope): descripción — Refs: PHASE-X.Y`
- NO anticipar funcionalidad de fases futuras
- Al terminar una fase: lint + typecheck + tests deben pasar (local Y en CI)
- Un PR = una fase. Squash merge recomendado.

## Verificación rápida
```bash
# Ejecutar ANTES de marcar una fase como completada
pnpm lint && pnpm typecheck && pnpm test && cd backend && pytest && mypy app/
```

## Lecciones aprendidas
Ver @internal_docs/lessons.md — se actualiza cada vez que se corrige un error.
Si cometes un error que se podría prevenir, AÑÁDELO a lessons.md.
