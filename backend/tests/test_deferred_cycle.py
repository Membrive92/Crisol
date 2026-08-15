"""PHASE-47.E2/E3 — El gasto aplazado existe, pero no ha salido.

Cuando el banco financia el recibo de una tarjeta, las compras de ese ciclo
siguen siendo gasto —se hicieron, tienen categoría y fecha— pero no salieron de
la cuenta ese mes. Salen como cuota, durante los años siguientes.

De ahí las **dos lecturas**, que es la decisión de la fase:

- **Resultado mensual** (¿he ahorrado?): las excluye. Mide caja.
- **Desglose por categorías** (¿en qué gasté?): las mantiene. Mide gasto.

Y una consecuencia deliberada: los meses con aplazamiento las dos cifras dejan
de cuadrar. Por eso el resumen publica `deferred_expenses` — sin ese número, la
pantalla mentiría por omisión.

Los importes son los reales del usuario: recibo de junio de 2026, 700,26 €.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.modules.personal_finance.debt.deferral import CyclePurchase, select_deferred_cycle


def _purchase(day: int, amount: str) -> CyclePurchase:
    return CyclePurchase(
        id=uuid.uuid4(),
        occurred_at=datetime(2026, 6, day, 12, 0, tzinfo=UTC),
        amount=Decimal(amount),
        description=f"COMPRA {day}",
    )


# ── La derivación del ciclo (pura) ───────────────────────────────────


def test_the_cycle_is_the_contiguous_run_that_closes_exactly() -> None:
    """Las últimas compras que suman EXACTO el recibo son el ciclo."""
    purchases = [_purchase(1, "50.00"), _purchase(10, "300.26"), _purchase(20, "400.00")]

    selection = select_deferred_cycle(purchases, Decimal("700.26"))

    assert selection.closes_exactly
    assert selection.count == 2
    assert selection.total == Decimal("700.26")
    # Contiguo y hacia atrás desde el cierre: la compra del día 1 pertenece al
    # recibo anterior, que ya se pagó.
    assert [p.amount for p in selection.purchases] == [Decimal("300.26"), Decimal("400.00")]


def test_a_cycle_that_does_not_close_marks_nothing() -> None:
    """Si no cuadra al céntimo, no se marca NADA — y se dice por qué.

    Es el caso real del recibo de 990,02 € de junio: faltan compras de mayo por
    importar. Marcar «las que más se acerquen» repartiría el gasto entre
    categorías que no son las suyas, y el usuario no tendría forma de saberlo.
    """
    purchases = [_purchase(10, "300.00"), _purchase(20, "500.00")]

    selection = select_deferred_cycle(purchases, Decimal("700.26"))

    assert not selection.closes_exactly
    assert selection.count == 0
    assert "no suman" in selection.reason


def test_purchases_after_the_cut_off_belong_to_the_next_receipt() -> None:
    """Una compra POSTERIOR al cierre no está en este recibo.

    Sin este corte, el ciclo se comería compras que el banco aún no ha
    facturado — y que aparecerán en el recibo del mes siguiente.
    """
    purchases = [_purchase(10, "700.26"), _purchase(28, "700.26")]

    selection = select_deferred_cycle(
        purchases, Decimal("700.26"), until=datetime(2026, 6, 25, tzinfo=UTC)
    )

    assert selection.closes_exactly
    assert selection.count == 1
    assert selection.purchases[0].occurred_at.day == 10


def test_overshooting_stops_instead_of_searching_combinations() -> None:
    """Pasarse para el recorrido; no se busca un subconjunto que cuadre.

    Muchos subconjuntos pueden sumar lo mismo y cada uno reparte el gasto entre
    categorías distintas. Esa elección no la puede tomar el sistema.
    """
    purchases = [_purchase(5, "700.26"), _purchase(10, "1000.00")]

    selection = select_deferred_cycle(purchases, Decimal("700.26"))

    assert not selection.closes_exactly


# ── Las dos lecturas, end-to-end ─────────────────────────────────────


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "T"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _account(client: AsyncClient, token: str, name: str, type_: str) -> str:
    r = await client.post(
        "/accounts",
        json={"name": name, "type": type_, "currency": "EUR"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _category(client: AsyncClient, token: str, name: str, kind: str) -> str:
    r = await client.post("/categories", json={"name": name, "kind": kind}, headers=_auth(token))
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _tx(
    client: AsyncClient,
    token: str,
    *,
    account_id: str,
    category_id: str,
    amount: str,
    day: int,
    flow: str = "OUT",
) -> str:
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": category_id,
            "amount": amount,
            "currency": "EUR",
            "occurred_at": f"2026-06-{day:02d}T12:00:00Z",
            "description": f"COMPRA {day}",
            "flow": flow,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


# `currency` explícita: el usuario nace con la divisa por defecto de la app y
# estas cuentas son en euros. Sin declararla, el resumen filtra por la del
# usuario y no vería ni una de estas compras.
JUNE = {
    "date_from": "2026-06-01T00:00:00Z",
    "date_to": "2026-06-30T23:59:59Z",
    "currency": "EUR",
}


async def _summary(client: AsyncClient, token: str) -> dict:
    r = await client.get("/dashboard/summary", params=JUNE, headers=_auth(token))
    assert r.status_code == 200, r.text
    return dict(r.json())


async def _breakdown_total(client: AsyncClient, token: str) -> Decimal:
    r = await client.get(
        "/dashboard/by-category", params={**JUNE, "kind": "expense"}, headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    return sum((Decimal(str(i["total"])) for i in r.json()), Decimal(0))


@pytest.fixture
async def deferred_scenario(client: AsyncClient):  # type: ignore[no-untyped-def]
    """Una tarjeta con dos compras de junio que suman el recibo de 700,26 €."""
    token = await _register(client, "aplazado_lecturas@example.com")
    card = await _account(client, token, "Tarjeta BBVA", "credit_card")
    groceries = await _category(client, token, "Supermercado", "expense")
    await _tx(client, token, account_id=card, category_id=groceries, amount="300.26", day=10)
    await _tx(client, token, account_id=card, category_id=groceries, amount="400.00", day=20)
    return token, card


async def test_before_declaring_it_both_readings_agree(
    client: AsyncClient, deferred_scenario  # type: ignore[no-untyped-def]
) -> None:
    """Sin aplazamiento declarado, resultado y desglose coinciden.

    Es la línea base: lo que cambia después lo cambia la marca, no otra cosa.
    """
    token, _ = deferred_scenario

    summary = await _summary(client, token)

    assert Decimal(str(summary["expenses"])) == Decimal("700.26")
    assert Decimal(str(summary["deferred_expenses"])) == Decimal("0")
    assert await _breakdown_total(client, token) == Decimal("700.26")


async def test_once_deferred_the_month_stops_counting_it_but_the_breakdown_does_not(
    client: AsyncClient, deferred_scenario  # type: ignore[no-untyped-def]
) -> None:
    """La decisión de la fase, en un test.

    Tras declarar el aplazamiento: el resultado del mes deja de contar los
    700,26 € —no salieron de la cuenta— y el desglose por categorías los
    mantiene enteros, porque el gasto se hizo. Y el resumen dice la diferencia.
    """
    token, card = deferred_scenario
    r = await client.post(
        "/accounts",
        json={
            "name": "Recibo junio aplazado",
            "type": "loan",
            "currency": "EUR",
            "opening_balance": "700.26",
            "apr": "0.10",
            "term_months": 36,
            "start_date": "2026-06-25",
            "parent_account_id": card,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    liability = str(r.json()["id"])

    preview = await client.get(
        f"/debt/liabilities/{liability}/deferred-cycle", headers=_auth(token)
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["closes_exactly"] is True
    assert len(preview.json()["purchases"]) == 2

    applied = await client.post(
        f"/debt/liabilities/{liability}/deferred-cycle", headers=_auth(token)
    )
    assert applied.status_code == 200, applied.text

    summary = await _summary(client, token)
    assert Decimal(str(summary["expenses"])) == Decimal("0")
    assert Decimal(str(summary["deferred_expenses"])) == Decimal("700.26")
    # El desglose NO se toca: el gasto existe, sólo está aplazado.
    assert await _breakdown_total(client, token) == Decimal("700.26")

    # Y es reversible: quitar la marca devuelve el gasto a la caja.
    undo = await client.delete(
        f"/debt/liabilities/{liability}/deferred-cycle", headers=_auth(token)
    )
    assert undo.status_code == 204, undo.text
    assert Decimal(str((await _summary(client, token))["expenses"])) == Decimal("700.26")


async def test_a_liability_without_a_declared_card_says_so(
    client: AsyncClient, deferred_scenario  # type: ignore[no-untyped-def]
) -> None:
    """Sin tarjeta declarada no hay ciclo que buscar, y se dice.

    Es el estado en el que nace la deuda del usuario: dada de alta suelta. El
    preview tiene que explicar qué falta en vez de devolver una lista vacía,
    que se leería como «no hay compras».
    """
    token, _ = deferred_scenario
    r = await client.post(
        "/accounts",
        json={
            "name": "Recibo suelto",
            "type": "loan",
            "currency": "EUR",
            "opening_balance": "700.26",
            "apr": "0.10",
            "term_months": 36,
            "start_date": "2026-06-25",
            # Sin `parent_account_id`: es como nace de verdad la deuda del
            # usuario, dada de alta suelta desde el asistente.
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    liability = str(r.json()["id"])

    preview = await client.get(
        f"/debt/liabilities/{liability}/deferred-cycle", headers=_auth(token)
    )

    assert preview.status_code == 200, preview.text
    assert preview.json()["closes_exactly"] is False
    assert "tarjeta" in preview.json()["reason"]
    assert preview.json()["card_id"] is None


async def test_applying_a_cycle_that_does_not_close_is_refused(
    client: AsyncClient, deferred_scenario  # type: ignore[no-untyped-def]
) -> None:
    """409 y ni una marca escrita si el ciclo no cuadra."""
    token, card = deferred_scenario
    r = await client.post(
        "/accounts",
        json={
            "name": "Recibo que no cuadra",
            "type": "loan",
            "currency": "EUR",
            "opening_balance": "990.02",
            "apr": "0.10",
            "term_months": 36,
            "start_date": "2026-06-25",
            "parent_account_id": card,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    liability = str(r.json()["id"])

    applied = await client.post(
        f"/debt/liabilities/{liability}/deferred-cycle", headers=_auth(token)
    )

    assert applied.status_code == 409, applied.text
    assert Decimal(str((await _summary(client, token))["expenses"])) == Decimal("700.26")
