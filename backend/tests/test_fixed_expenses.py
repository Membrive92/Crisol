"""Tests del módulo fixed_expenses (PHASE-13.1, renombrado en
PHASE-17.1)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient

from app.modules.personal_finance.fixed_expenses.detector import (
    Candidate,
    _detect_in_group,
    normalize_merchant,
)

# ---------- normalize_merchant ----------


def test_normalize_merchant_lowercases_and_strips() -> None:
    assert normalize_merchant("NETFLIX.COM") == "netflixcom"
    assert normalize_merchant("Netflix Premium") == "netflixpremium"
    assert normalize_merchant("PRO_NETFLIX SUSCRIP") == "pronetflixsuscrip"


def test_normalize_merchant_handles_none_and_empty() -> None:
    assert normalize_merchant(None) == ""
    assert normalize_merchant("") == ""


def test_normalize_merchant_caps_to_30_chars() -> None:
    long = "x" * 100
    assert len(normalize_merchant(long)) == 30


# ---------- _detect_in_group ----------


def _occ(d: date, desc: str = "Netflix") -> tuple[date, str, None]:
    return (d, desc, None)


def test_detect_returns_none_below_min_occurrences() -> None:
    occurrences = [
        _occ(date(2026, 1, 15)),
        _occ(date(2026, 2, 15)),
    ]
    out = _detect_in_group(
        occurrences,
        merchant="netflix",
        amount=Decimal("12.99"),
        currency="EUR",
    )
    assert out is None


def test_detect_picks_monthly_cadence_with_high_confidence() -> None:
    occurrences = [
        _occ(date(2026, 1, 15)),
        _occ(date(2026, 2, 15)),
        _occ(date(2026, 3, 15)),
        _occ(date(2026, 4, 15)),
    ]
    out = _detect_in_group(
        occurrences,
        merchant="netflix",
        amount=Decimal("12.99"),
        currency="EUR",
    )
    assert out is not None
    assert out.cadence_days == 30
    assert out.occurrence_count == 4
    assert out.confidence > 0.9
    assert out.first_seen_at == date(2026, 1, 15)
    assert out.last_seen_at == date(2026, 4, 15)
    assert out.next_due == date(2026, 4, 15) + timedelta(days=30)


def test_detect_rejects_irregular_cadence() -> None:
    """Gaps muy desiguales no deberían quedar como gasto fijo."""
    occurrences = [
        _occ(date(2026, 1, 1)),
        _occ(date(2026, 1, 5)),  # 4 días
        _occ(date(2026, 3, 15)),  # 69 días
        _occ(date(2026, 3, 18)),  # 3 días
    ]
    out = _detect_in_group(
        occurrences,
        merchant="random",
        amount=Decimal("10.00"),
        currency="EUR",
    )
    assert out is None


def test_detect_picks_yearly_cadence() -> None:
    occurrences = [
        _occ(date(2024, 6, 1)),
        _occ(date(2025, 6, 1)),
        _occ(date(2026, 6, 1)),
    ]
    out = _detect_in_group(
        occurrences,
        merchant="annual",
        amount=Decimal("99.00"),
        currency="EUR",
    )
    assert out is not None
    assert out.cadence_days == 365


# ---------- API integration ----------


async def _setup_user(
    client: AsyncClient, email: str = "sub@example.com"
) -> tuple[str, str]:
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


async def _insert_recurring(
    client: AsyncClient,
    token: str,
    cat_id: str,
    *,
    description: str = "NETFLIX.COM",
    amount: str = "12.99",
    months_back: int = 4,
) -> None:
    """Inserta una serie mensual de transacciones."""
    today = date.today()
    for i in range(months_back):
        # months_back=4 → fechas: hoy, hoy-30, hoy-60, hoy-90
        when = today - timedelta(days=30 * i)
        await client.post(
            "/transactions",
            json={
                "category_id": cat_id,
                "amount": amount,
                "currency": "EUR",
                "occurred_at": f"{when.isoformat()}T12:00:00Z",
                "description": description,
            },
            headers=_auth(token),
        )


async def test_scan_creates_pending_fixed_expense_from_recurring_txs(
    client: AsyncClient,
) -> None:
    token, cat_id = await _setup_user(client, "sub1@example.com")
    await _insert_recurring(client, token, cat_id, months_back=4)

    r = await client.post("/fixed-expenses/scan", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 1
    assert body["updated"] == 0
    assert body["total_active_after"] == 1

    r_list = await client.get("/fixed-expenses", headers=_auth(token))
    items = r_list.json()
    assert len(items) == 1
    assert items[0]["merchant"] == "netflixcom"
    assert items[0]["status"] == "pending"
    assert items[0]["cadence_days"] == 30
    assert items[0]["occurrence_count"] == 4
    assert items[0]["category_id"] == cat_id


async def test_scan_refreshes_existing_fixed_expense_without_duplicating(
    client: AsyncClient,
) -> None:
    """Re-ejecutar scan no crea duplicado si la huella coincide."""
    token, cat_id = await _setup_user(client, "sub2@example.com")
    await _insert_recurring(client, token, cat_id, months_back=4)
    await client.post("/fixed-expenses/scan", headers=_auth(token))

    # Inserto otra ocurrencia (la del mes que viene → sigue siendo el
    # mismo merchant + amount → mismo fingerprint).
    next_month = date.today() + timedelta(days=30)
    await client.post(
        "/transactions",
        json={
            "category_id": cat_id,
            "amount": "12.99",
            "currency": "EUR",
            "occurred_at": f"{next_month.isoformat()}T12:00:00Z",
            "description": "NETFLIX.COM",
        },
        headers=_auth(token),
    )

    r = await client.post("/fixed-expenses/scan", headers=_auth(token))
    body = r.json()
    assert body["created"] == 0
    assert body["updated"] == 1

    r_list = await client.get("/fixed-expenses", headers=_auth(token))
    items = r_list.json()
    assert len(items) == 1
    assert items[0]["occurrence_count"] == 5


async def test_dismiss_prevents_re_suggestion(client: AsyncClient) -> None:
    """Un gasto fijo dismissed sigue ahí pero no vuelve a aparecer
    como pending tras un nuevo scan (porque su fingerprint matchea y
    sólo se refresca sin tocar status)."""
    token, cat_id = await _setup_user(client, "sub3@example.com")
    await _insert_recurring(client, token, cat_id, months_back=4)
    await client.post("/fixed-expenses/scan", headers=_auth(token))

    r_list = await client.get("/fixed-expenses", headers=_auth(token))
    sid = r_list.json()[0]["id"]

    r_dismiss = await client.post(
        f"/fixed-expenses/{sid}/dismiss", headers=_auth(token)
    )
    assert r_dismiss.status_code == 200
    assert r_dismiss.json()["status"] == "dismissed"

    # Re-scan: dismissed no se reactiva.
    await client.post("/fixed-expenses/scan", headers=_auth(token))
    r_pending = await client.get(
        "/fixed-expenses", params={"status": "pending"}, headers=_auth(token)
    )
    assert r_pending.json() == []


async def test_confirm_sets_status_to_confirmed(client: AsyncClient) -> None:
    token, cat_id = await _setup_user(client, "sub4@example.com")
    await _insert_recurring(client, token, cat_id, months_back=4)
    await client.post("/fixed-expenses/scan", headers=_auth(token))
    sid = (await client.get("/fixed-expenses", headers=_auth(token))).json()[0]["id"]

    r = await client.post(f"/fixed-expenses/{sid}/confirm", headers=_auth(token))
    assert r.json()["status"] == "confirmed"


async def test_user_isolation(client: AsyncClient) -> None:
    token_a, cat_a = await _setup_user(client, "subA@example.com")
    token_b, _ = await _setup_user(client, "subB@example.com")

    await _insert_recurring(client, token_a, cat_a, months_back=4)
    await client.post("/fixed-expenses/scan", headers=_auth(token_a))

    # B no ve el gasto fijo de A.
    r_b = await client.get("/fixed-expenses", headers=_auth(token_b))
    assert r_b.json() == []

    sid = (await client.get("/fixed-expenses", headers=_auth(token_a))).json()[0]["id"]
    r_b_get = await client.get(f"/fixed-expenses/{sid}", headers=_auth(token_b))
    assert r_b_get.status_code == 404


async def test_delete_purges_fixed_expense(client: AsyncClient) -> None:
    token, cat_id = await _setup_user(client, "sub5@example.com")
    await _insert_recurring(client, token, cat_id, months_back=4)
    await client.post("/fixed-expenses/scan", headers=_auth(token))
    sid = (await client.get("/fixed-expenses", headers=_auth(token))).json()[0]["id"]

    r = await client.delete(f"/fixed-expenses/{sid}", headers=_auth(token))
    assert r.status_code == 204

    r_get = await client.get(f"/fixed-expenses/{sid}", headers=_auth(token))
    assert r_get.status_code == 404


def test_candidate_dataclass_is_immutable() -> None:
    """Sanity check: `Candidate` es frozen para evitar mutaciones
    accidentales en el service."""
    cand = Candidate(
        merchant="x",
        raw_description="X",
        amount=Decimal("1"),
        currency="EUR",
        cadence_days=30,
        next_due=date(2026, 1, 1),
        first_seen_at=date(2025, 1, 1),
        last_seen_at=date(2025, 12, 1),
        occurrence_count=12,
        confidence=0.9,
        category_id=None,
    )
    try:
        cand.merchant = "y"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("Candidate debería ser frozen (inmutable)")
