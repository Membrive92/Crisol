"""PHASE-47.A — Golden del dominio deuda: lo que la consolidación NO puede mover.

47.A mueve seis módulos de `accounts/` a `debt/` sin tocar una línea de lógica.
Un movimiento así falla en SILENCIO: si un `git mv` se lleva por delante una
función, o un import se repunta al símbolo parecido de al lado, la suite puede
seguir verde mientras la respuesta que ve el frontend cambia de forma. Este
fichero congela el JSON de los tres endpoints que dependen de los seis módulos
—`/accounts/debt-health`, `/accounts/balances` y `/debt/category-summary`—
byte a byte contra una fixture generada ANTES del movimiento.

**La semilla vive en un año fijo y pasado (2023), no relativo a hoy.** Un golden
cuyo contenido dependa del mes en que se ejecute es una bomba de relojería
([AUDIT-2026-08] en `lessons.md`). Consecuencia deliberada y sabida: los KPIs de
ventana móvil (`interest_paid_ytd`, `monthly_income_avg`, `time_to_payoff_months`)
salen en 0/`None` porque su ventana es "este año" / "los últimos 6 meses" / "de
este mes en adelante", y 2023 queda fuera de las tres. Su lógica la cubren
`test_debt_health_schedule.py` y `test_debt.py`; lo que este fichero protege es
la FORMA de la respuesta y los agregados de STOCK (deuda viva, composición por
tipo, interés contractual del cuadro, patrimonio).

Para regenerar la fixture a propósito (sólo cuando un cambio de comportamiento
lo justifique, y explicando el diff en el commit)::

    UPDATE_DEBT_GOLDEN=1 .venv/Scripts/python.exe -m pytest tests/test_debt_domain_golden.py
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from httpx import AsyncClient

GOLDEN_PATH = Path(__file__).parent / "fixtures" / "debt" / "golden_47a_debt_domain.json"

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# Ventana fija y pasada — ver docstring del módulo.
_YEAR = 2023


# ── seed ─────────────────────────────────────────────────────────────


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Golden"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_account(client: AsyncClient, token: str, **fields: object) -> dict[str, Any]:
    r = await client.post("/accounts", json=fields, headers=_auth(token))
    assert r.status_code == 201, r.text
    return dict(r.json())


async def _create_category(
    client: AsyncClient,
    token: str,
    name: str,
    kind: str,
    role: str,
) -> str:
    r = await client.post(
        "/categories",
        json={"name": name, "kind": kind, "role": role},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _post_tx(
    client: AsyncClient,
    token: str,
    *,
    account_id: str,
    category_id: str,
    amount: str,
    occurred_at: str,
    description: str,
) -> None:
    r = await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": category_id,
            "amount": amount,
            "occurred_at": occurred_at,
            "description": description,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text


async def _seed(client: AsyncClient) -> str:
    """Un usuario con las cuatro formas de deuda que el dominio distingue.

    Cuenta corriente (activo) · tarjeta revolving (pasivo sin cuadro) · préstamo
    con cuadro francés y tres cuotas pagadas · compra a plazos colgada de la
    tarjeta (PHASE-35: hija con cuadro propio, que no debe doblar con el padre).
    """
    token = await _register(client, "golden_debt_domain@example.com")

    cte = await _create_account(
        client,
        token,
        name="Cuenta corriente",
        type="bank",
        currency="EUR",
        opening_balance="4000.00",
        display_order=0,
        is_default=True,
    )
    card = await _create_account(
        client,
        token,
        name="Tarjeta",
        type="credit_card",
        currency="EUR",
        opening_balance="0.00",
        display_order=1,
    )
    loan = await _create_account(
        client,
        token,
        name="Préstamo coche",
        type="loan",
        currency="EUR",
        opening_balance="12000.00",
        apr="0.0500",
        term_months=12,
        start_date=f"{_YEAR}-01-01",
        display_order=2,
    )
    await _create_account(
        client,
        token,
        name="Compra a plazos sofá",
        type="credit_card",
        currency="EUR",
        opening_balance="1200.00",
        apr="0.1000",
        term_months=6,
        start_date=f"{_YEAR}-02-01",
        display_order=3,
        parent_account_id=card["id"],
    )

    salary = await _create_category(client, token, "Nómina", "income", "GENERIC")
    shopping = await _create_category(client, token, "Compras", "expense", "GENERIC")
    debt_capital = await _create_category(
        client, token, "Préstamo coche", "expense", "DEBT_PAYMENT"
    )
    debt_interest = await _create_category(
        client, token, "Intereses préstamo", "expense", "DEBT_INTEREST"
    )

    for month in (1, 2, 3):
        await _post_tx(
            client,
            token,
            account_id=cte["id"],
            category_id=salary,
            amount="2000.00",
            occurred_at=f"{_YEAR}-0{month}-25T12:00:00Z",
            description="Nómina",
        )
    await _post_tx(
        client,
        token,
        account_id=cte["id"],
        category_id=debt_capital,
        amount="1000.00",
        occurred_at=f"{_YEAR}-03-01T12:00:00Z",
        description="Cuota préstamo",
    )
    await _post_tx(
        client,
        token,
        account_id=cte["id"],
        category_id=debt_interest,
        amount="50.00",
        occurred_at=f"{_YEAR}-03-01T12:00:00Z",
        description="Intereses préstamo",
    )
    await _post_tx(
        client,
        token,
        account_id=card["id"],
        category_id=shopping,
        amount="150.00",
        occurred_at=f"{_YEAR}-03-10T12:00:00Z",
        description="Compra con tarjeta",
    )

    # Tres cuotas del préstamo pagadas: el cuadro es quien manda sobre la deuda
    # viva (PHASE-36) y sobre el interés (PHASE-37).
    r = await client.get(f"/accounts/{loan['id']}/amortization-schedule", headers=_auth(token))
    assert r.status_code == 200, r.text
    for row in r.json()["rows"][:3]:
        p = await client.post(
            f"/accounts/installments/{row['id']}/pay",
            json={"paid_at": f"{_YEAR}-{row['due_date'][5:7]}-15T10:00:00Z"},
            headers=_auth(token),
        )
        assert p.status_code == 200, p.text

    return token


# ── normalización ────────────────────────────────────────────────────


def _normalise(payload: Any, ids: dict[str, str]) -> Any:
    """Sustituye los UUID generados por el servidor por alias estables.

    El alias se asigna en orden de primera aparición recorriendo el JSON, que es
    determinista porque el orden de las claves y de las listas lo fija el propio
    contrato de la respuesta. Sin esto el golden compararía uuid4 contra uuid4 y
    fallaría siempre — que es tan inútil como no tenerlo.
    """
    if isinstance(payload, dict):
        return {k: _normalise(v, ids) for k, v in payload.items()}
    if isinstance(payload, list):
        return [_normalise(v, ids) for v in payload]
    if isinstance(payload, str) and _UUID_RE.match(payload):
        return ids.setdefault(payload, f"<uuid:{len(ids)}>")
    return payload


async def _snapshot(client: AsyncClient, token: str) -> dict[str, Any]:
    responses: dict[str, Any] = {}
    for key, url in (
        ("debt_health", "/accounts/debt-health?target_currency=EUR"),
        ("balances", "/accounts/balances?target_currency=EUR"),
        (
            "category_summary",
            f"/debt/category-summary?range=custom&date_from={_YEAR}-01-01"
            f"&date_to={_YEAR}-12-31&target_currency=EUR",
        ),
    ):
        r = await client.get(url, headers=_auth(token))
        assert r.status_code == 200, f"{url} → {r.status_code} {r.text}"
        responses[key] = r.json()
    ids: dict[str, str] = {}
    return {key: _normalise(value, ids) for key, value in responses.items()}


# ── el test ──────────────────────────────────────────────────────────


async def test_debt_domain_responses_match_golden(client: AsyncClient) -> None:
    """Las tres respuestas del dominio deuda, byte a byte contra la fixture."""
    token = await _seed(client)
    snapshot = await _snapshot(client, token)
    serialised = json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    if os.environ.get("UPDATE_DEBT_GOLDEN"):
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(serialised, encoding="utf-8")

    assert GOLDEN_PATH.exists(), (
        f"falta {GOLDEN_PATH.name}: regenérala con UPDATE_DEBT_GOLDEN=1 "
        "ANTES de mover ningún fichero"
    )
    expected = GOLDEN_PATH.read_text(encoding="utf-8")
    assert serialised == expected, (
        "el dominio deuda ha cambiado de respuesta. Si el cambio es "
        "deliberado, regenera la fixture y explica el diff en el commit; "
        "si estás moviendo ficheros (47.A), es un bug del movimiento."
    )


async def test_golden_seed_is_not_degenerate(client: AsyncClient) -> None:
    """El golden compara algo, no un puñado de ceros.

    Un golden de una respuesta vacía pasa siempre y no protege nada — la
    familia de [PHASE-44.14]: un test que sólo comprueba que el guardarraíl
    salta no prueba lo que el guardarraíl protege. Estos asserts fijan el suelo
    de señal de la semilla; si alguien la adelgaza, saltan aquí y no en un diff
    silencioso de la fixture.
    """
    token = await _seed(client)
    snapshot = await _snapshot(client, token)

    health = snapshot["debt_health"]
    assert float(health["total_liabilities"]) > 0
    assert float(health["interest_scheduled_total"]) > 0  # el cuadro aporta interés
    assert float(health["interest_remaining"]) > 0
    assert len(health["debt_by_type"]) >= 2  # préstamo + compra a plazos
    assert float(health["net_worth"]) != 0

    balances = snapshot["balances"]
    assert len(balances["items"]) == 4

    summary = snapshot["category_summary"]
    assert float(summary["total_payments"]) > 0
    assert float(summary["interests_and_fees"]) > 0
    assert float(summary["outstanding_at_end"]) > 0
    assert summary["by_type"]
