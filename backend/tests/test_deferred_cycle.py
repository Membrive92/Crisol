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
from datetime import UTC, datetime, timedelta
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
    description: str | None = None,
) -> str:
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": category_id,
            "amount": amount,
            "currency": "EUR",
            "occurred_at": f"2026-06-{day:02d}T12:00:00Z",
            "description": description or f"COMPRA {day}",
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


async def _financed_receipt(client: AsyncClient, token: str, card: str, principal: str) -> str:
    """Un recibo aplazado dado de alta bajo su tarjeta, con cuadro."""
    r = await client.post(
        "/accounts",
        json={
            "name": f"Recibo aplazado {principal}",
            "type": "loan",
            "currency": "EUR",
            "opening_balance": principal,
            "apr": "0.10",
            "term_months": 36,
            "start_date": "2026-06-25",
            "parent_account_id": card,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


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


# ── Regresiones de la revisión adversarial (2026-08-15) ──────────────
#
# Cinco defectos reales que la suite en verde no veía. Cada uno con su test,
# y todos verificados rompiendo la línea concreta que dicen proteger.


async def test_declaring_the_cycle_twice_does_not_mark_a_second_set(
    client: AsyncClient, deferred_scenario  # type: ignore[no-untyped-def]
) -> None:
    """Un doble clic no puede marcar compras DISTINTAS con el mismo pasivo.

    `_card_purchases` excluye lo ya marcado, así que la segunda llamada buscaba
    en un pool fresco — y si las compras del ciclo anterior sumaban lo mismo,
    cerraba otra vez y les estampaba el mismo aplazamiento. Dos ciclos marcados
    por un recibo que sólo pagó uno.
    """
    token, card = deferred_scenario
    groceries = await _category(client, token, "Ocio", "expense")
    # Ciclo ANTERIOR, aún sin marcar, que suma exactamente lo mismo.
    await _tx(client, token, account_id=card, category_id=groceries, amount="700.26", day=2)

    liability = await _financed_receipt(client, token, card, "700.26")
    first = await client.post(f"/debt/liabilities/{liability}/deferred-cycle", headers=_auth(token))
    assert first.status_code == 200, first.text
    assert len(first.json()["purchases"]) == 2

    second = await client.post(
        f"/debt/liabilities/{liability}/deferred-cycle", headers=_auth(token)
    )

    assert second.status_code == 200, second.text
    # Las MISMAS dos compras, no cuatro.
    assert len(second.json()["purchases"]) == 2
    assert {p["id"] for p in second.json()["purchases"]} == {
        p["id"] for p in first.json()["purchases"]
    }


async def test_the_cycle_closes_at_the_card_settlement_not_the_contract_date(
    client: AsyncClient, deferred_scenario  # type: ignore[no-untyped-def]
) -> None:
    """El corte lo marca la liquidación de la tarjeta, no cuándo se firmó.

    `start_date` es la fecha en que el banco contrató la financiación, y entre
    el cierre de facturación y esa fecha caben compras del ciclo SIGUIENTE.
    Como el recorrido va de la más reciente hacia atrás, esas entrarían las
    primeras. La liquidación del extracto de la tarjeta ES el corte.
    """
    token, card = deferred_scenario
    other = await _category(client, token, "Ocio", "expense")
    # El recibo aparece en el extracto de la TARJETA el día 20: ahí cierra.
    await _tx(
        client,
        token,
        account_id=card,
        category_id=other,
        amount="700.26",
        day=20,
        flow="TRANSFER_OUT",
        description="Recibo mes anterior",
    )
    # Compra del ciclo SIGUIENTE, anterior a la fecha de contrato (día 25).
    await _tx(client, token, account_id=card, category_id=other, amount="55.00", day=22)

    liability = await _financed_receipt(client, token, card, "700.26")
    preview = await client.get(
        f"/debt/liabilities/{liability}/deferred-cycle", headers=_auth(token)
    )

    assert preview.status_code == 200, preview.text
    assert preview.json()["closes_exactly"] is True
    marked = {p["amount"] for p in preview.json()["purchases"]}
    assert "55.00" not in marked


async def test_an_asset_account_is_not_a_debt(
    client: AsyncClient, deferred_scenario  # type: ignore[no-untyped-def]
) -> None:
    """Pasar una cuenta corriente devolvía 200 y pedía declarar una tarjeta."""
    token, _ = deferred_scenario
    checking = await _account(client, token, "Cuenta corriente", "bank")

    r = await client.get(f"/debt/liabilities/{checking}/deferred-cycle", headers=_auth(token))

    assert r.status_code == 400, r.text
    assert "no es una cuenta de deuda" in r.json()["detail"]


async def test_the_savings_rate_is_computed_over_a_single_universe(
    client: AsyncClient, deferred_scenario  # type: ignore[no-untyped-def]
) -> None:
    """Las dos mitades del cociente tienen que mirar los mismos movimientos.

    El ingreso sale de `get_totals_by_kind` (que excluye lo aplazado) y el
    gasto de `expense_split_totals`. Si el segundo NO excluye, la tasa
    estructural puede salir POR DEBAJO de la bruta — aritméticamente
    imposible, porque el gasto estructural es un subconjunto del bruto — y la
    pantalla enseña un badge que contradice a su propio titular.

    Es el mismo defecto que la fase arregla, vivo en el módulo de al lado.
    """
    token, card = deferred_scenario
    salary = await _category(client, token, "Nómina", "income")
    bank = await _account(client, token, "BBVA", "bank")
    await _tx(
        client, token, account_id=bank, category_id=salary, amount="2000.00", day=1, flow="IN"
    )

    liability = await _financed_receipt(client, token, card, "700.26")
    assert (
        await client.post(f"/debt/liabilities/{liability}/deferred-cycle", headers=_auth(token))
    ).status_code == 200

    summary = await _summary(client, token)
    r = await client.get("/analytics/expense-structure", params=JUNE, headers=_auth(token))
    assert r.status_code == 200, r.text
    structure = r.json()

    # El gasto que ve Análisis es el mismo que el del resultado del mes.
    gross = Decimal(str(structure["structural_total"])) + Decimal(
        str(structure["exceptional_total"])
    )
    assert gross == Decimal(str(summary["expenses"]))
    # Y la estructural no puede quedar por debajo de la bruta.
    assert structure["savings_rate_structural"] >= structure["savings_rate_gross"]


# ── Las lecturas de la ventana móvil (runway y recurrencia) ──────────
#
# Estas dos miran la ventana de 6 meses cerrados de `analytics`, así que sus
# fechas se derivan de HOY y no se escriben a mano: un test cuyo resultado
# depende del mes en que se ejecute es una bomba de relojería (AUDIT-2026-08),
# y con fechas fijas dejaría de probar nada en cuanto el mes elegido saliera
# de la ventana.


def _month_start(offset_back: int) -> datetime:
    """Primer día del mes que está `offset_back` meses antes del actual."""
    today = datetime.now(UTC)
    year, month = today.year, today.month - offset_back
    while month <= 0:
        month += 12
        year -= 1
    return datetime(year, month, 1, tzinfo=UTC)


async def _tx_at(
    client: AsyncClient,
    token: str,
    *,
    account_id: str,
    category_id: str,
    amount: str,
    when: datetime,
    flow: str = "OUT",
    description: str = "COMPRA",
) -> None:
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": category_id,
            "amount": amount,
            "currency": "EUR",
            "occurred_at": when.replace(hour=12).isoformat(),
            "description": description,
            "flow": flow,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text


@pytest.fixture
async def recurring_scenario(client: AsyncClient):  # type: ignore[no-untyped-def]
    """Una categoría recurrente cuyo ÚLTIMO mes depende del ciclo aplazado.

    La regla 3 exige 4 meses con importe en banda dentro de la ventana de 6.
    Se siembran 3 meses de 400 € desde el banco y el cuarto —el del ciclo— sólo
    con las compras de la tarjeta, 420 € en total (dentro de la banda ±40 % de
    la mediana). Así el escenario DISCRIMINA: si la clasificación excluyera lo
    aplazado, ese mes desaparecería, quedarían 3 y la categoría dejaría de ser
    estructural. Con un mes que tuviera gasto por otro lado, el test pasaría
    hiciera lo que hiciera el código.
    """
    token = await _register(client, "aplazado_ventana@example.com")
    card = await _account(client, token, "Tarjeta BBVA", "credit_card")
    bank = await _account(client, token, "BBVA", "bank")
    groceries = await _category(client, token, "Supermercado", "expense")

    for back in (2, 3, 4):
        await _tx_at(
            client,
            token,
            account_id=bank,
            category_id=groceries,
            amount="400.00",
            when=_month_start(back) + timedelta(days=5),
        )
    cycle_month = _month_start(1)
    await _tx_at(
        client,
        token,
        account_id=card,
        category_id=groceries,
        amount="200.00",
        when=cycle_month + timedelta(days=9),
    )
    await _tx_at(
        client,
        token,
        account_id=card,
        category_id=groceries,
        amount="220.00",
        when=cycle_month + timedelta(days=19),
    )
    return token, card, cycle_month


def _month_params(month: datetime) -> dict[str, str]:
    """Rango [primer día, último instante] del mes dado."""
    end = (month + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
    return {
        "date_from": month.isoformat(),
        "date_to": end.isoformat(),
        "currency": "EUR",
    }


async def _structure(client: AsyncClient, token: str, month: datetime) -> dict:
    r = await client.get(
        "/analytics/expense-structure", params=_month_params(month), headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    return dict(r.json())


async def _declare(client: AsyncClient, token: str, card: str, month: datetime) -> str:
    r = await client.post(
        "/accounts",
        json={
            "name": "Recibo aplazado",
            "type": "loan",
            "currency": "EUR",
            "opening_balance": "420.00",
            "apr": "0.10",
            "term_months": 36,
            "start_date": (month + timedelta(days=24)).date().isoformat(),
            "parent_account_id": card,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    liability = str(r.json()["id"])
    applied = await client.post(
        f"/debt/liabilities/{liability}/deferred-cycle", headers=_auth(token)
    )
    assert applied.status_code == 200, applied.text
    return liability


async def test_the_runway_base_does_not_count_deferred_purchases(
    client: AsyncClient, recurring_scenario  # type: ignore[no-untyped-def]
) -> None:
    """El coste de vida mensual es CAJA: lo aplazado no salió de la cuenta.

    `structural_monthly_avg` es el denominador de líquido ÷ consumo mensual.
    Contándolo, el colchón se acorta — y cuando lleguen las cuotas, que caen en
    una categoría de pago de deuda (estructural por la regla 2), los mismos
    euros entrarían en la media por segunda vez.

    Este test es el que FALTABA, y por eso el arreglo anterior pudo aplicarse a
    la función de al lado sin que nada se quejara: verificar rompiendo el
    código sólo prueba lo que algún test mira.
    """
    token, card, month = recurring_scenario

    base_before = Decimal(str((await _structure(client, token, month))["structural_monthly_avg"]))
    assert base_before > 0, "sin base estructural el test no probaría nada"

    await _declare(client, token, card, month)

    base_after = Decimal(str((await _structure(client, token, month))["structural_monthly_avg"]))
    assert base_after < base_before


async def test_recurrence_still_sees_a_deferred_purchase(
    client: AsyncClient, recurring_scenario  # type: ignore[no-untyped-def]
) -> None:
    """Aplazar el pago NO deja de hacer recurrente a una categoría.

    Qué categorías son estructurales lo decide el PATRÓN de gasto —¿aparece
    Supermercado mes tras mes?— y cuándo salió el dinero no cambia si la compra
    se hizo. Si la clasificación excluyera lo aplazado, la categoría podría
    parecer que se salta un mes, dejaría de ser estructural, y su gasto pasaría
    a puntual EN TODAS PARTES: la marca de un mes reescribiendo el histórico.
    """
    token, card, month = recurring_scenario
    await _declare(client, token, card, month)

    structure = await _structure(client, token, month)

    puntuales = {c["category_name"] for c in structure["exceptional_by_category"]}
    assert "Supermercado" not in puntuales
