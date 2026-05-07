"""Tests de la fusión por prefijo común en el detector (PHASE-14.7)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient

from app.modules.personal_finance.fixed_expenses.detector import (
    _common_prefix,
    _merge_by_common_prefix,
)


def test_common_prefix_basic() -> None:
    assert _common_prefix("netflixcom", "netflixsuscrip") == 7
    assert _common_prefix("spotify", "spaceshop") == 2
    assert _common_prefix("", "anything") == 0
    assert _common_prefix("identical", "identical") == 9


def _occ(d: date) -> tuple[date, str, None]:
    return (d, "x", None)


def test_merge_groups_with_common_prefix_and_same_amount() -> None:
    grouped = {
        ("netflixcom", Decimal("12.99"), "EUR"): [
            _occ(date(2026, 1, 15)),
            _occ(date(2026, 2, 15)),
        ],
        ("netflixsuscrip", Decimal("12.99"), "EUR"): [
            _occ(date(2026, 3, 15)),
            _occ(date(2026, 4, 15)),
        ],
    }
    out = _merge_by_common_prefix(grouped)
    # Se queda con el merchant más largo como llave.
    assert ("netflixsuscrip", Decimal("12.99"), "EUR") in out
    assert len(out) == 1
    assert len(out[("netflixsuscrip", Decimal("12.99"), "EUR")]) == 4


def test_merge_does_not_combine_different_amounts() -> None:
    """Mismo prefijo pero amount distinto → siguen separados."""
    grouped = {
        ("netflixcom", Decimal("12.99"), "EUR"): [_occ(date(2026, 1, 15))],
        ("netflixcom", Decimal("15.99"), "EUR"): [_occ(date(2026, 2, 15))],
    }
    out = _merge_by_common_prefix(grouped)
    assert len(out) == 2


def test_merge_does_not_combine_short_prefix() -> None:
    """Prefijo común < MIN_COMMON_PREFIX → siguen separados."""
    grouped = {
        ("spotify", Decimal("9.99"), "EUR"): [_occ(date(2026, 1, 15))],
        ("spaceshop", Decimal("9.99"), "EUR"): [_occ(date(2026, 2, 15))],
    }
    out = _merge_by_common_prefix(grouped)
    # "sp" sólo, < 6 chars → no fusiona.
    assert len(out) == 2


def test_merge_three_way_keeps_longest() -> None:
    """Tres merchants compartiendo prefijo: la llave es la más larga."""
    grouped = {
        ("netflixcom", Decimal("12.99"), "EUR"): [_occ(date(2026, 1, 15))],
        ("netflixsuscripcionplus", Decimal("12.99"), "EUR"): [
            _occ(date(2026, 2, 15))
        ],
        ("netflixpremium", Decimal("12.99"), "EUR"): [_occ(date(2026, 3, 15))],
    }
    out = _merge_by_common_prefix(grouped)
    assert len(out) == 1
    assert ("netflixsuscripcionplus", Decimal("12.99"), "EUR") in out


# ---------- Integration: scan API recoge la fusión ----------


async def _setup_user(client: AsyncClient, email: str) -> tuple[str, str]:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    token = r.json()["access_token"]
    cat = await client.post(
        "/categories",
        json={"name": "Streaming", "kind": "expense"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, cat.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_scan_merges_descriptions_with_common_prefix(
    client: AsyncClient,
) -> None:
    """Crear 4 cargos mensuales alternando descripciones tipo
    "NETFLIX.COM" y "Netflix Premium" → el detector las trata como
    un único gasto fijo."""
    token, cat_id = await _setup_user(client, "pf1@example.com")
    today = date.today()

    # Todas comparten prefijo "netflix" tras normalizar — el de
    # mayor longitud ("netflixsuscripcionplus") se queda como llave.
    descriptions = [
        "NETFLIX.COM",
        "Netflix Premium",
        "Netflix Suscripcion Plus",
        "netflix-monthly",
    ]
    for i, desc in enumerate(descriptions):
        when = today - timedelta(days=30 * i)
        await client.post(
            "/transactions",
            json={
                "category_id": cat_id,
                "amount": "12.99",
                "currency": "EUR",
                "occurred_at": f"{when.isoformat()}T12:00:00Z",
                "description": desc,
            },
            headers=_auth(token),
        )

    r = await client.post("/fixed-expenses/scan", headers=_auth(token))
    body = r.json()
    # Pre-PHASE-14.7 hubieran sido 4 gastos fijos distintos.
    # Ahora se funden a 1.
    assert body["created"] == 1

    items = (await client.get("/fixed-expenses", headers=_auth(token))).json()
    assert len(items) == 1
    assert items[0]["occurrence_count"] == 4
