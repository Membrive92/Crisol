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
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.debt.deferral import CyclePurchase, select_deferred_cycle


def _purchase(day: int, amount: str) -> CyclePurchase:
    return CyclePurchase(
        id=uuid.uuid4(),
        occurred_at=datetime(2026, 6, day, 12, 0, tzinfo=UTC),
        amount=Decimal(amount),
        description=f"COMPRA {day}",
    )


# ── La derivación del ciclo (pura) ───────────────────────────────────


def test_the_cycle_is_the_contiguous_run_that_closes() -> None:
    """Las últimas compras que suman EXACTO el recibo son el ciclo."""
    purchases = [_purchase(1, "50.00"), _purchase(10, "300.26"), _purchase(20, "400.00")]

    selection = select_deferred_cycle(purchases, Decimal("700.26"))

    assert selection.closes
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

    assert not selection.closes
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

    assert selection.closes
    assert selection.count == 1
    assert selection.purchases[0].occurred_at.day == 10


def test_overshooting_stops_instead_of_searching_combinations() -> None:
    """Pasarse para el recorrido; no se busca un subconjunto que cuadre.

    Muchos subconjuntos pueden sumar lo mismo y cada uno reparte el gasto entre
    categorías distintas. Esa elección no la puede tomar el sistema.
    """
    purchases = [_purchase(5, "700.26"), _purchase(10, "1000.00")]

    selection = select_deferred_cycle(purchases, Decimal("700.26"))

    assert not selection.closes


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


@pytest_asyncio.fixture
async def session_factory(test_engine):  # type: ignore[no-untyped-def]
    """Sesión directa a la BD de test, para preparar estados que la API no
    expone — aquí, marcar una fila como espejo absorbido por el sistema."""
    return async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)


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
    assert preview.json()["closes"] is True
    assert preview.json()["already_declared"] is False, "aún no se ha declarado nada"
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


async def test_el_desglose_dice_que_categorias_estan_aplazadas(
    client: AsyncClient, deferred_scenario  # type: ignore[no-untyped-def]
) -> None:
    """PHASE-47.E4 — el aviso decía CUÁNTO hay aplazado, no DÓNDE.

    Con `deferred_total` por categoría, la pantalla puede marcar la fila que lo
    explica; y como el reparto por categoría suma exactamente el total del
    periodo, el aviso puede derivarse de lo que se está mostrando en vez de
    citar un conjunto distinto cuando el usuario filtra.
    """
    token, card = deferred_scenario
    # Una segunda categoría que NO se aplaza, para que la marca distinga. Va en
    # la CUENTA del banco, no en la tarjeta: si entrara en el ciclo de la
    # tarjeta, las compras dejarían de sumar el recibo al céntimo y el
    # aplazamiento no se declararía (que es el guardarraíl de PHASE-47.E).
    banco = await _account(client, token, "BBVA", "bank")
    ocio = await _category(client, token, "Ocio", "expense")
    await _tx(client, token, account_id=banco, category_id=ocio, amount="50.00", day=12)

    liability = await _financed_receipt(client, token, card, "700.26")
    applied = await client.post(
        f"/debt/liabilities/{liability}/deferred-cycle", headers=_auth(token)
    )
    assert applied.status_code == 200, applied.text

    r = await client.get(
        "/dashboard/by-category", params={**JUNE, "kind": "expense"}, headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    por_categoria = {i["category_name"]: i for i in r.json()}

    # Supermercado: todo su gasto está aplazado. Ocio: nada.
    assert Decimal(str(por_categoria["Supermercado"]["deferred_total"])) == Decimal("700.26")
    assert Decimal(str(por_categoria["Ocio"]["deferred_total"])) == Decimal("0")
    assert Decimal(str(por_categoria["Ocio"]["total"])) == Decimal("50.00")

    # El invariante que hace que el aviso pueda derivarse de la vista: lo
    # aplazado repartido por categorías suma lo que dice el resumen.
    summary = await _summary(client, token)
    repartido = sum(
        (Decimal(str(i["deferred_total"])) for i in r.json()),
        Decimal(0),
    )
    assert repartido == Decimal(str(summary["deferred_expenses"])) == Decimal("700.26")

    # Y la parte nunca es mayor que el todo.
    for item in r.json():
        assert Decimal(str(item["deferred_total"])) <= Decimal(str(item["total"]))


async def test_el_gasto_puntual_por_categoria_tambien_dice_lo_aplazado(
    client: AsyncClient, deferred_scenario  # type: ignore[no-untyped-def]
) -> None:
    """PHASE-47.E4 — sin esto, el filtro Fijo/Variable del desglose no puede
    repartir lo aplazado y su aviso vuelve a citar el periodo entero.

    Con datos reales, junio de 2026 decía «496,67 € aplazados» mientras la
    vista de Fijo sólo contenía 245,53 € de ellos.
    """
    token, card = deferred_scenario
    liability = await _financed_receipt(client, token, card, "700.26")
    applied = await client.post(
        f"/debt/liabilities/{liability}/deferred-cycle", headers=_auth(token)
    )
    assert applied.status_code == 200, applied.text

    r = await client.get(
        "/analytics/expense-structure",
        params={"currency": "EUR", **JUNE},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    puntual = r.json()["exceptional_by_category"]
    assert puntual, "el escenario tiene gasto puntual"
    # Supermercado sólo tiene actividad en un mes → puntual, y aplazado entero.
    fila = next(i for i in puntual if i["category_name"] == "Supermercado")
    assert Decimal(str(fila["deferred_total"])) == Decimal("700.26")


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
    assert preview.json()["closes"] is False
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
    # El estado viaja como DATO. La pantalla decide con él si ofrece «declarar»
    # o «retirar la marca»; deducirlo del texto de `reason` la rompería el día
    # que alguien reescriba la frase.
    assert first.json()["already_declared"] is True
    assert second.json()["already_declared"] is True
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
    assert preview.json()["closes"] is True
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


# ── La devolución dentro del ciclo ───────────────────────────────────
#
# Lo destapó mirar los datos reales del usuario: con las devoluciones netadas,
# DOS de sus cuatro recibos cierran al céntimo; sin netarlas, ninguno. El banco
# liquida el neto, así que un ciclo con una devolución dentro no puede sumar el
# recibo si sólo se cuentan las compras.


def _refund(day: int, amount: str) -> CyclePurchase:
    """Una devolución: mismo sitio que una compra, importe en negativo."""
    return CyclePurchase(
        id=uuid.uuid4(),
        occurred_at=datetime(2026, 6, day, 12, 0, tzinfo=UTC),
        amount=Decimal(amount),
        description=f"DEVOLUCION {day}",
    )


def test_a_refund_inside_the_cycle_is_netted() -> None:
    """400 + 350 − 49,74 = 700,26: el ciclo cierra con la devolución dentro."""
    movements = [_purchase(10, "400.00"), _refund(12, "-49.74"), _purchase(20, "350.00")]

    selection = select_deferred_cycle(movements, Decimal("700.26"))

    assert selection.closes
    assert selection.count == 3
    assert selection.total == Decimal("700.26")


def test_the_walk_does_not_give_up_before_reaching_a_refund() -> None:
    """Pasarse NO es motivo de abandono si aún queda una devolución detrás.

    Recorriendo de la más reciente hacia atrás, la suma llega a 750,00 —por
    encima del recibo— y sólo vuelve a 700,26 al alcanzar la devolución, que
    es más antigua. Con el corte ingenuo «me he pasado, paro», este ciclo no
    cerraría nunca.
    """
    movements = [_refund(5, "-49.74"), _purchase(10, "400.00"), _purchase(20, "350.00")]

    selection = select_deferred_cycle(movements, Decimal("700.26"))

    assert selection.closes
    assert selection.count == 3


async def test_a_refund_on_the_card_reaches_the_cycle(
    client: AsyncClient, deferred_scenario  # type: ignore[no-untyped-def]
) -> None:
    """End-to-end: la devolución tiene que llegar desde la CONSULTA.

    Los dos tests de arriba son puros y no tocan la BD, así que no dicen nada
    sobre qué filas selecciona `_card_purchases`. Este sí: con la consulta
    filtrando sólo `flow='OUT'` —como estaba— la devolución no llega, la suma
    se queda alta y el ciclo no cierra.
    """
    token, card = deferred_scenario
    returns = await _category(client, token, "Devoluciones", "income")
    # El escenario tiene 300,26 + 400,00 = 700,26. Se añade una compra de más
    # y su devolución: el NETO sigue siendo el recibo.
    groceries = await _category(client, token, "Ocio", "expense")
    await _tx(client, token, account_id=card, category_id=groceries, amount="49.74", day=12)
    await _tx(
        client,
        token,
        account_id=card,
        category_id=returns,
        amount="49.74",
        day=14,
        flow="IN",
        description="DEVOLUCION Ocio",
    )

    liability = await _financed_receipt(client, token, card, "700.26")
    preview = await client.get(
        f"/debt/liabilities/{liability}/deferred-cycle", headers=_auth(token)
    )

    assert preview.status_code == 200, preview.text
    assert preview.json()["closes"] is True, preview.json()["reason"]
    assert Decimal(str(preview.json()["total"])) == Decimal("700.26")
    assert len(preview.json()["purchases"]) == 4


# ── La papelera no es donde vive lo que absorbió el sistema ──────────


async def test_an_absorbed_mirror_is_not_user_trash(
    client: AsyncClient,
    deferred_scenario,  # type: ignore[no-untyped-def]
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Un cargo espejo absorbido no se lista, ni se restaura, ni se purga.

    Está soft-borrado, pero lo borró el SISTEMA al crear su contrapartida
    (AUDIT-2026-07 H-04), y `find_existing_hashes` cuenta con que siga ahí para
    no resucitarlo al reimportar. Apareciendo en la papelera, «vaciar» lo
    borraba de verdad — y el siguiente import lo traía de vuelta sin
    contrapartida, descuadrando la cuenta sin que nada avisara.
    """
    token, card = deferred_scenario
    groceries = await _category(client, token, "Ocio", "expense")
    tx_id = await _tx(client, token, account_id=card, category_id=groceries, amount="99.00", day=5)

    # Se marca como espejo absorbido, que es lo que hace el sistema al
    # convertir una compra en deuda.
    async with session_factory() as db:
        await db.execute(
            sql_text(
                "UPDATE transactions SET deleted_at = now(), absorbed_as_mirror = true "
                "WHERE id = CAST(:i AS uuid)"
            ),
            {"i": tx_id},
        )
        await db.commit()

    listed = await client.get("/transactions/trash", headers=_auth(token))
    assert listed.status_code == 200, listed.text
    assert tx_id not in {t["id"] for t in listed.json()["items"]}

    purged = await client.delete("/transactions/trash", headers=_auth(token))
    assert purged.status_code == 200, purged.text

    # Sigue ahí: el vaciado no se lo llevó.
    async with session_factory() as db:
        still = await db.execute(
            sql_text("SELECT count(*) FROM transactions WHERE id = CAST(:i AS uuid)"),
            {"i": tx_id},
        )
        assert still.scalar_one() == 1


# ── La holgura de redondeo ───────────────────────────────────────────
#
# Medido sobre los datos reales del usuario: el ciclo de junio de 2026 suma
# 700,27 € contra un recibo de 700,26 €. UN céntimo. Exigir coincidencia
# perfecta convertía un ciclo perfectamente identificable en «faltan datos»,
# que es un diagnóstico falso y le manda a buscar un fichero inexistente.


def test_a_one_cent_rounding_still_closes() -> None:
    """700,27 contra un recibo de 700,26: cierra, y se dice que no es exacto."""
    movements = [_purchase(10, "300.27"), _purchase(20, "400.00")]

    selection = select_deferred_cycle(movements, Decimal("700.26"))

    assert selection.closes
    assert not selection.is_exact
    assert selection.difference == Decimal("-0.01")
    assert "redondeo" in selection.reason


def test_an_exact_run_wins_over_a_tolerated_one() -> None:
    """Si más atrás hay un tramo EXACTO, gana sobre el que sólo se acerca.

    El recorrido encuentra antes el tolerado (2 movimientos, un céntimo de
    más); seguir hasta el exacto y preferirlo es lo que impide que la holgura
    se coma un ciclo que sí cuadraba.
    """
    movements = [_purchase(1, "-0.01"), _purchase(10, "300.27"), _purchase(20, "400.00")]

    selection = select_deferred_cycle(movements, Decimal("700.26"))

    assert selection.closes
    assert selection.is_exact
    assert selection.count == 3


def test_the_tolerance_is_bounded_by_the_number_of_movements() -> None:
    """Dos movimientos admiten dos céntimos, no más.

    Es lo que impide que la holgura haga cuadrar un tramo EQUIVOCADO: entre dos
    ciclos reales hay euros de diferencia, nunca céntimos, así que la ventana no
    puede crecer hasta alcanzar una segunda respuesta.
    """
    justo = select_deferred_cycle(
        [_purchase(10, "300.00"), _purchase(20, "400.28")], Decimal("700.26")
    )
    assert justo.closes, "0,02 con 2 movimientos entra"

    pasado = select_deferred_cycle(
        [_purchase(10, "300.00"), _purchase(20, "400.29")], Decimal("700.26")
    )
    assert not pasado.closes, "0,03 con 2 movimientos NO entra"


def test_a_real_gap_is_still_refused() -> None:
    """Faltar 39 € sigue siendo «faltan datos», no un redondeo."""
    selection = select_deferred_cycle(
        [_purchase(10, "300.00"), _purchase(20, "361.15")], Decimal("700.26")
    )

    assert not selection.closes
    assert "no suman" in selection.reason


def test_among_tolerated_runs_the_closest_one_wins() -> None:
    """Sin ningún tramo exacto, gana el que menos se desvía.

    Recorriendo hacia atrás aparece primero un tramo que se pasa por 2
    céntimos y después uno que sólo se pasa por 1. Quedarse con el primero
    marcaría un movimiento de menos. Es lo único que distingue la regla de
    preferencia del retorno anticipado del exacto: en el caso exacto las dos
    dan lo mismo, así que un test con exacto no puede probar ninguna.
    """
    movements = [_purchase(1, "-0.01"), _purchase(10, "300.28"), _purchase(20, "400.00")]

    selection = select_deferred_cycle(movements, Decimal("700.26"))

    assert selection.closes
    assert not selection.is_exact
    assert selection.count == 3, "gana el tramo de 700,27, no el de 700,28"
    assert selection.total == Decimal("700.27")


def test_the_cycle_may_end_before_the_cut_but_not_months_before() -> None:
    """El corte que se conoce es el del COBRO, no el del cierre.

    El banco cobra unos días después de cerrar la facturación, así que fijar el
    final del tramo en la fecha del cargo arrastra las compras de esos días —que
    ya son del ciclo siguiente— y el ciclo no cierra nunca. Es lo que pasaba con
    el recibo real de 700,26 €: el tramo que cuadra termina 3 días antes del
    cargo.

    Pero la ventana tiene que estar acotada: sin ella, una compra suelta de
    meses atrás que coincidiera con el importe cerraría el ciclo por
    casualidad.
    """
    # Cierra 3 días antes del corte, con compras posteriores que son del
    # ciclo siguiente.
    dentro = select_deferred_cycle(
        [_purchase(10, "300.26"), _purchase(20, "400.00"), _purchase(25, "88.00")],
        Decimal("700.26"),
        until=datetime(2026, 6, 23, tzinfo=UTC),
    )
    assert dentro.closes
    assert dentro.count == 2

    # La misma coincidencia, pero fuera de la ventana: no vale.
    fuera = select_deferred_cycle(
        [_purchase(1, "700.26"), _purchase(28, "88.00")],
        Decimal("700.26"),
        until=datetime(2026, 6, 28, 23, 59, tzinfo=UTC),
    )
    assert not fuera.closes, "una compra de 27 días antes no cierra el ciclo"
