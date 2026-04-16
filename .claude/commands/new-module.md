# Crear módulo backend

Crea un nuevo módulo backend para: $ARGUMENTS

Sigue EXACTAMENTE esta estructura:

```
backend/app/modules/{nombre}/
├── __init__.py
├── router.py        # APIRouter con prefix y tags
├── service.py       # Lógica de negocio (async)
├── repository.py    # Queries a DB (async, SQLAlchemy)
├── models.py        # SQLAlchemy models
└── schemas.py       # Pydantic v2 request/response models
```

## Reglas
- router.py: usa Depends() para auth y db session
- service.py: recibe db session y user_id como parámetros, NUNCA accede a request
- repository.py: queries con parámetros bind, NUNCA string interpolation
- models.py: todos los modelos tienen id (UUID), created_at, user_id FK
- schemas.py: separar Request y Response models, usar Field() con descripciones
- Registrar el router en app/main.py

Después de crear la estructura, genera la migración con Alembic:
```bash
cd backend && alembic revision --autogenerate -m "create {nombre} tables"
```
