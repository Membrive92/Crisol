"""Router del módulo seed."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.modules.personal_finance.seed.service import seed_recommended

router = APIRouter(prefix="/seed", tags=["seed"])


class SeedResultResponse(BaseModel):
    categories_created: int
    categories_existed: int
    rules_created: int
    rules_existed: int


@router.post("/recommended", response_model=SeedResultResponse)
async def seed_recommended_endpoint(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SeedResultResponse:
    """Crea categorías y reglas de categorización recomendadas para
    bancos españoles. Idempotente: ejecutarlo varias veces no duplica
    categorías ni reglas.
    """
    result = await seed_recommended(db, user.id)
    await db.commit()
    return SeedResultResponse(**result.to_dict())
