"""PHASE-47.A — Desde qué cuenta se cobra un pasivo: propuesta con su evidencia.

El cargo que paga una deuda no vive en la deuda: vive en la cuenta corriente
desde la que el banco lo cobra. Sin declarar ese vínculo no se puede saber qué
cargo cierra el ciclo de qué tarjeta —julio de 2026: cuatro cargos de cierre y
seis pasivos—, y sin eso no hay invariante de conservación ni traducción
automática (ADR-0011).

Este módulo NO adivina la atribución: la CUENTA. Mira los cargos que el usuario
ya enlazó a mano en PHASE-45 y devuelve de qué cuenta salen, con el recuento
dentro para que la frase que ve el usuario sea verificable. Sin enlaces
previos devuelve una propuesta vacía, que es la respuesta honesta: proponer una
cuenta sin haber contado nada es adivinar, y un dato adivinado que se persiste
deja de distinguirse de uno declarado ([PHASE-44.11]).

Hay DOS formas de enlace y las dos cuentan, porque cuál se usó depende de si el
pasivo tiene cuadro y no de dónde sale el dinero:

- Pasivo **sin cuadro**: PHASE-45 crea la contrapartida en la cuenta de deuda
  con `amortization_source_id` apuntando al cargo del banco.
- Pasivo **con cuadro**: no se crea contrapartida — se marcan cuotas, y el cargo
  queda en `liability_installments.paid_transaction_id`.
"""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.personal_finance.accounts.models import Account, AccountNature
from app.modules.personal_finance.debt.installments_model import LiabilityInstallment
from app.modules.personal_finance.transactions.models import Transaction


@dataclass(frozen=True)
class SettlementSuggestion:
    """Propuesta + la evidencia que la sostiene.

    `matches`/`total` viajan a la API a propósito: una propuesta sin su
    recuento es una opinión, y el usuario no tiene forma de calibrarla."""

    account_id: uuid.UUID | None = None
    account_name: str | None = None
    reason: str | None = None
    matches: int = 0
    total: int = 0


async def _charges_from_counterparts(
    db: AsyncSession,
    user_id: uuid.UUID,
    liability_id: uuid.UUID,
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """`(id del cargo, cuenta del cargo)` de un pasivo SIN cuadro."""
    source = aliased(Transaction)
    query = (
        select(source.id, source.account_id)
        .join(Transaction, Transaction.amortization_source_id == source.id)
        .where(
            Transaction.user_id == user_id,
            source.user_id == user_id,
            Transaction.account_id == liability_id,
            Transaction.deleted_at.is_(None),
            source.deleted_at.is_(None),
        )
    )
    return [(row[0], row[1]) for row in (await db.execute(query)).all()]


async def _charges_from_installments(
    db: AsyncSession,
    user_id: uuid.UUID,
    liability_id: uuid.UUID,
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """`(id del cargo, cuenta del cargo)` de un pasivo CON cuadro.

    `.distinct()` no es cosmético: `plan_installments_covering_principal` marca
    VARIAS cuotas con el MISMO `paid_transaction_id`, así que sin él un solo
    cargo del banco votaría una vez por cuota. Eso inflaba el recuento que el
    usuario lee («12 de 12 cargos») y, peor, podía deshacer un empate real —
    una cuenta con un cargo que cubre 5 cuotas ganaría a otra con 4 cargos.
    """
    query = (
        select(Transaction.id, Transaction.account_id)
        .join(
            LiabilityInstallment,
            LiabilityInstallment.paid_transaction_id == Transaction.id,
        )
        .where(
            LiabilityInstallment.user_id == user_id,
            LiabilityInstallment.account_id == liability_id,
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        )
        .distinct()
    )
    return [(row[0], row[1]) for row in (await db.execute(query)).all()]


async def suggest_settlement_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    liability_id: uuid.UUID,
) -> SettlementSuggestion:
    """Propone la cuenta de activo desde la que parece cobrarse `liability_id`.

    Devuelve una propuesta vacía cuando no hay enlaces previos, cuando ninguno
    apunta a una cuenta de activo viva, o cuando hay **empate** en el primer
    puesto: con dos cuentas igual de respaldadas, elegir una sería una moneda
    al aire disfrazada de dato (misma regla que la ambigüedad de la bandeja,
    ADR-0011 punto 5).
    """
    # Un cargo puede llegar por las DOS vías (contrapartida creada y además
    # cuota marcada con la misma tx). Se deduplica por id de cargo para que el
    # recuento sea de CARGOS, que es lo que dice la frase que ve el usuario.
    charges = dict(await _charges_from_counterparts(db, user_id, liability_id))
    charges.update(dict(await _charges_from_installments(db, user_id, liability_id)))
    origins = list(charges.values())
    if not origins:
        return SettlementSuggestion()

    # Sólo cuentas de ACTIVO vivas del propio usuario: proponer una archivada
    # apuntaría a una opción que el formulario ni siquiera ofrece.
    eligible_rows = (
        await db.execute(
            select(Account.id, Account.name).where(
                Account.id.in_(set(origins)),
                Account.user_id == user_id,
                Account.nature == AccountNature.ASSET,
                Account.is_archived.is_(False),
            )
        )
    ).all()
    names = {row[0]: row[1] for row in eligible_rows}
    counts = Counter(a for a in origins if a in names)
    if not counts:
        return SettlementSuggestion(total=len(origins))

    ranked = counts.most_common()
    best_id, best_count = ranked[0]
    total = sum(counts.values())
    if len(ranked) > 1 and ranked[1][1] == best_count:
        # Empate: se dice que hay evidencia, pero no se elige por el usuario.
        return SettlementSuggestion(total=total)

    name = names[best_id]
    if best_count == total:
        reason = (
            f"los {total} cargos que amortizan esta deuda salen de «{name}»"
            if total > 1
            else f"el cargo que amortiza esta deuda sale de «{name}»"
        )
    else:
        reason = f"{best_count} de los {total} cargos que amortizan esta deuda salen de «{name}»"
    return SettlementSuggestion(
        account_id=best_id,
        account_name=name,
        reason=reason,
        matches=best_count,
        total=total,
    )
