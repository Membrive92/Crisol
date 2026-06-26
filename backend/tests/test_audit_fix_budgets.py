"""Tests del audit-fix del módulo budgets.

Cubre tres defectos detectados en revisión:

  #1 [high]   `sum_expenses_in_period` no excluía categorías marcadas como
              transferencia interna (`is_transfer=True`) cuando la tx no
              tenía pareja (`transfer_pair_id IS NULL`, caso "una sola pata
              importada") → over-budget falsos.
  #2 [medium] `create_budget` no validaba que la categoría fuese del
              usuario ni que fuese de gasto (kind=EXPENSE, no transfer).
  #3 [low]    `list_active_budgets` / `get_active_budget_for_category`
              reportaban como activos presupuestos con `effective_from`
              futuro → acumulaban gasto y bloqueaban crear otro.

Los tests usan el cliente HTTP de extremo a extremo (mismo enfoque que
`test_budgets.py`) para ejercitar router → service → repository contra una
DB real, que es donde viven los filtros SQL corregidos.
"""

from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _setup_user(client: AsyncClient, email: str) -> tuple[str, str, str]:
    """Registra usuario, crea una categoría de gasto y una cuenta.

    Devuelve `(token, expense_category_id, account_id)`.
    """
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    token = r.json()["access_token"]
    cat = await client.post(
        "/categories",
        json={"name": "Comida", "kind": "expense"},
        headers=_auth(token),
    )
    acc = await client.post(
        "/accounts",
        json={"name": "Cuenta principal", "type": "bank", "currency": "EUR"},
        headers=_auth(token),
    )
    return token, cat.json()["id"], acc.json()["id"]


# --------------------------------------------------------------------------- #
# Finding #1 — transferencias internas no consumen presupuesto                 #
# --------------------------------------------------------------------------- #


async def test_global_budget_excludes_internal_transfer_single_leg(
    client: AsyncClient,
) -> None:
    """Una tx con categoría `is_transfer=True` y SIN pareja no debe
    consumir un presupuesto global (regresión del finding #1).

    Antes del fix sólo se excluían las tx con `transfer_pair_id`; una
    transferencia importada como un único movimiento (sin pareja) tenía
    su importe sumado al gasto del mes, inflando el budget a `over`.
    """
    token, _cat_id, account_id = await _setup_user(client, "afbg1@example.com")

    # Categoría de transferencia interna (gasto + is_transfer=True), que es
    # exactamente lo que produce un import de una transferencia saliente.
    transfer_cat = await client.post(
        "/categories",
        json={"name": "Traspaso", "kind": "expense", "is_transfer": True},
        headers=_auth(token),
    )
    transfer_cat_id = transfer_cat.json()["id"]

    await client.post(
        "/budgets",
        json={"amount": "100.00", "currency": "EUR", "effective_from": "2026-05-01"},
        headers=_auth(token),
    )

    today_iso = date.today().isoformat()
    # Movimiento de transferencia de 500€ — muy por encima del budget si
    # contara. NO tiene pareja (creación manual/import de una sola pata).
    await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": transfer_cat_id,
            "amount": "500.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )

    r = await client.get("/budgets/status", headers=_auth(token))
    assert r.status_code == 200, r.text
    item = r.json()["items"][0]
    # La transferencia no es gasto → spent=0, status ok (no over).
    assert float(item["spent_this_month"]) == 0.0
    assert item["status"] == "ok"


async def test_global_budget_still_counts_normal_expense_alongside_transfer(
    client: AsyncClient,
) -> None:
    """El fix excluye SÓLO transferencias: un gasto normal del mismo mes
    sigue contando. Garantiza que no excluimos de más.
    """
    token, cat_id, account_id = await _setup_user(client, "afbg2@example.com")
    transfer_cat = await client.post(
        "/categories",
        json={"name": "Traspaso", "kind": "expense", "is_transfer": True},
        headers=_auth(token),
    )
    transfer_cat_id = transfer_cat.json()["id"]

    await client.post(
        "/budgets",
        json={"amount": "100.00", "currency": "EUR", "effective_from": "2026-05-01"},
        headers=_auth(token),
    )

    today_iso = date.today().isoformat()
    # Gasto real de 40€ (cuenta) + transferencia de 500€ (no cuenta).
    await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": cat_id,
            "amount": "40.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )
    await client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "category_id": transfer_cat_id,
            "amount": "500.00",
            "currency": "EUR",
            "occurred_at": f"{today_iso}T12:00:00Z",
        },
        headers=_auth(token),
    )

    r = await client.get("/budgets/status", headers=_auth(token))
    item = r.json()["items"][0]
    assert float(item["spent_this_month"]) == 40.0
    assert item["status"] == "ok"


# --------------------------------------------------------------------------- #
# Finding #2 — validación de propiedad y kind de la categoría                  #
# --------------------------------------------------------------------------- #


async def test_create_budget_rejects_foreign_category_404(client: AsyncClient) -> None:
    """Crear un budget sobre una categoría de OTRO usuario → 404.

    No se debe filtrar la existencia de IDs ajenos ni permitir asociar un
    presupuesto a una categoría que no pertenece al usuario.
    """
    token_a, cat_a, _ = await _setup_user(client, "afbg3a@example.com")
    token_b, _cat_b, _ = await _setup_user(client, "afbg3b@example.com")

    # B intenta presupuestar la categoría de A.
    r = await client.post(
        "/budgets",
        json={
            "category_id": cat_a,
            "amount": "100.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
        },
        headers=_auth(token_b),
    )
    assert r.status_code == 404, r.text
    # token_a no usado más allá del setup; silencia linters de "unused".
    assert token_a


async def test_create_budget_rejects_income_category_400(client: AsyncClient) -> None:
    """Crear un budget sobre una categoría de ingreso → 400."""
    token, _cat_id, _ = await _setup_user(client, "afbg4@example.com")
    income_cat = await client.post(
        "/categories",
        json={"name": "Nómina", "kind": "income"},
        headers=_auth(token),
    )
    r = await client.post(
        "/budgets",
        json={
            "category_id": income_cat.json()["id"],
            "amount": "100.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
        },
        headers=_auth(token),
    )
    assert r.status_code == 400, r.text


async def test_create_budget_rejects_transfer_category_400(client: AsyncClient) -> None:
    """Crear un budget sobre una categoría de transferencia interna → 400.

    El gasto de una categoría `is_transfer` siempre se excluye (finding
    #1), así que el budget sería inerte. Se rechaza en la entrada.
    """
    token, _cat_id, _ = await _setup_user(client, "afbg5@example.com")
    transfer_cat = await client.post(
        "/categories",
        json={"name": "Traspaso", "kind": "expense", "is_transfer": True},
        headers=_auth(token),
    )
    r = await client.post(
        "/budgets",
        json={
            "category_id": transfer_cat.json()["id"],
            "amount": "100.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
        },
        headers=_auth(token),
    )
    assert r.status_code == 400, r.text


async def test_create_budget_accepts_valid_expense_category(client: AsyncClient) -> None:
    """Sanidad: una categoría de gasto propia válida sigue creándose (201)."""
    token, cat_id, _ = await _setup_user(client, "afbg6@example.com")
    r = await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "100.00",
            "currency": "EUR",
            "effective_from": "2026-05-01",
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text


async def test_create_global_budget_skips_category_validation(client: AsyncClient) -> None:
    """Un budget global (`category_id` ausente) no requiere categoría y
    no debe tropezar con la validación nueva.
    """
    token, _cat_id, _ = await _setup_user(client, "afbg7@example.com")
    r = await client.post(
        "/budgets",
        json={"amount": "1000.00", "currency": "EUR", "effective_from": "2026-05-01"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["category_id"] is None


# --------------------------------------------------------------------------- #
# Finding #3 — effective_from futuro no es "activo"                            #
# --------------------------------------------------------------------------- #


async def test_future_budget_not_listed_as_active(client: AsyncClient) -> None:
    """Un budget con `effective_from` futuro no aparece en la lista de
    activos ni en el status hasta que llega su fecha.
    """
    token, cat_id, _ = await _setup_user(client, "afbg8@example.com")
    future = (date.today() + timedelta(days=30)).isoformat()
    r = await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "100.00",
            "currency": "EUR",
            "effective_from": future,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text

    r_list = await client.get("/budgets", headers=_auth(token))
    assert r_list.status_code == 200
    assert r_list.json() == []

    r_status = await client.get("/budgets/status", headers=_auth(token))
    assert r_status.status_code == 200
    assert r_status.json()["items"] == []


async def test_future_budget_does_not_block_creating_active_one(
    client: AsyncClient,
) -> None:
    """Con la política "un activo por categoría", un budget futuro NO debe
    contar como activo y por tanto no debe bloquear crear uno que empiece
    hoy para la misma categoría (regresión del finding #3).
    """
    token, cat_id, _ = await _setup_user(client, "afbg9@example.com")
    future = (date.today() + timedelta(days=30)).isoformat()
    today_iso = date.today().isoformat()

    r_future = await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "100.00",
            "currency": "EUR",
            "effective_from": future,
        },
        headers=_auth(token),
    )
    assert r_future.status_code == 201, r_future.text

    # Crear otro que empieza hoy para la misma categoría: debe permitirse,
    # porque el futuro no se considera activo.
    r_today = await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "200.00",
            "currency": "EUR",
            "effective_from": today_iso,
        },
        headers=_auth(token),
    )
    assert r_today.status_code == 201, r_today.text

    # El activo de hoy sí aparece; el futuro no.
    r_list = await client.get("/budgets", headers=_auth(token))
    active = r_list.json()
    assert len(active) == 1
    assert active[0]["effective_from"] == today_iso


async def test_active_today_budget_still_listed(client: AsyncClient) -> None:
    """Sanidad: un budget que empieza hoy (o en el pasado) sigue siendo
    activo tras el fix — no excluimos de más.
    """
    token, cat_id, _ = await _setup_user(client, "afbg10@example.com")
    today_iso = date.today().isoformat()
    r = await client.post(
        "/budgets",
        json={
            "category_id": cat_id,
            "amount": "100.00",
            "currency": "EUR",
            "effective_from": today_iso,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text

    r_list = await client.get("/budgets", headers=_auth(token))
    assert len(r_list.json()) == 1
