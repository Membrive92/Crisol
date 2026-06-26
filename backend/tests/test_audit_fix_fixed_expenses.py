"""Tests del audit-fix del módulo fixed_expenses.

Cubre los cinco hallazgos:

1. [high] El detector sólo considera gastos reales (kind=EXPENSE,
   is_transfer=False, transfer_pair_id IS NULL) — nóminas (ingresos) y
   transferencias periódicas dejan de detectarse como "gasto fijo".
2. [low] `detect_for_user` usa UTC como default de `today`, no la hora
   local del proceso.
3. [low] La fusión por prefijo conserva su comportamiento (no se
   endurece para no romper casos legítimos); el riesgo queda
   documentado en código. Aquí se fija el comportamiento esperado.
4. [low] El autopost avanza `next_due` por calendario para cadencias
   mensual/trimestral/semestral/anual (sin deriva), y por días para
   semanal/quincenal.
5. [low] `confirm_fixed_expense` reactiva un `dismissed` directamente a
   `confirmed` (sin la rama muerta que pasaba por `pending`).

Tests puros (helpers de cadencia, default UTC, prefijo) no tocan BD;
los de integración usan el fixture `client` igual que el resto de la
suite del módulo.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.fixed_expenses import detector
from app.modules.personal_finance.fixed_expenses.detector import (
    _merge_by_common_prefix,
)
from app.modules.personal_finance.fixed_expenses.models import (
    FixedExpense,
    FixedExpenseStatus,
)
from app.modules.personal_finance.fixed_expenses.service import (
    _add_months,
    _advance_due,
    autopost_due_for_user,
    confirm_fixed_expense,
)
from app.modules.personal_finance.transactions.models import Transaction

# ---------------------------------------------------------------------------
# Finding 4 — avance por calendario (tests puros, sin BD)
# ---------------------------------------------------------------------------


def test_add_months_keeps_day_of_month() -> None:
    assert _add_months(date(2026, 1, 15), 1) == date(2026, 2, 15)
    assert _add_months(date(2026, 1, 15), 3) == date(2026, 4, 15)
    assert _add_months(date(2026, 1, 15), 12) == date(2027, 1, 15)


def test_add_months_clamps_to_last_valid_day() -> None:
    """31 de enero + 1 mes → 28 de febrero (no existe el 31)."""
    assert _add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    # Año bisiesto: febrero tiene 29.
    assert _add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    # 31 de marzo + 1 mes → 30 de abril.
    assert _add_months(date(2026, 3, 31), 1) == date(2026, 4, 30)


def test_advance_due_weekly_and_biweekly_stay_day_based() -> None:
    """Semanal/quincenal son múltiplos exactos de semana — días fijos."""
    assert _advance_due(date(2026, 1, 1), 7, anchor_day=1) == date(2026, 1, 8)
    assert _advance_due(date(2026, 1, 1), 14, anchor_day=1) == date(2026, 1, 15)
    # Cadencia no canónica (p.ej. 45 días, no debería existir) → días.
    assert _advance_due(date(2026, 1, 1), 45, anchor_day=1) == date(2026, 2, 15)


def test_advance_due_monthly_no_drift_over_year() -> None:
    """Mensual anclado al día 15: 12 ciclos sin deriva."""
    d = date(2026, 1, 15)
    for _ in range(12):
        d = _advance_due(d, 30, anchor_day=15)
    assert d == date(2027, 1, 15)


def test_advance_due_monthly_reanchors_after_short_month() -> None:
    """Día 31 de cada mes: tras recortar a 28/30, vuelve a 31 cuando el
    mes lo permite (no se degrada a 28 permanentemente)."""
    d = date(2026, 1, 31)
    seq = []
    for _ in range(5):
        d = _advance_due(d, 30, anchor_day=31)
        seq.append(d)
    assert seq == [
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
        date(2026, 5, 31),
        date(2026, 6, 30),
    ]


def test_advance_due_quarterly_and_semestral() -> None:
    assert _advance_due(date(2026, 1, 31), 90, anchor_day=31) == date(2026, 4, 30)
    assert _advance_due(date(2026, 8, 31), 180, anchor_day=31) == date(2027, 2, 28)


def test_advance_due_yearly_leap_day_reanchors() -> None:
    """29-feb (bisiesto) anclado al día 29: cae al 28 en años no
    bisiestos y vuelve al 29 cuando toque (re-ancla al anchor, no
    arrastra el 28)."""
    d = date(2024, 2, 29)
    d = _advance_due(d, 365, anchor_day=29)
    assert d == date(2025, 2, 28)
    d = _advance_due(d, 365, anchor_day=29)
    assert d == date(2026, 2, 28)
    d = _advance_due(d, 365, anchor_day=29)
    assert d == date(2027, 2, 28)
    d = _advance_due(d, 365, anchor_day=29)  # 2028 sí es bisiesto
    assert d == date(2028, 2, 29)


# ---------------------------------------------------------------------------
# Finding 2 — default UTC (test puro: comprobamos la firma/comportamiento
# del default sin depender de la TZ del host)
# ---------------------------------------------------------------------------


def test_detect_default_today_is_utc() -> None:
    """Cuando no se pasa `today`, el detector ancla en UTC.

    El default se calcula al vuelo dentro de `detect_for_user` y la
    query exige BD para ejercitarse, así que verificamos la intención
    inspeccionando el AST del módulo: el default debe ser
    `datetime.now(UTC).date()` y NUNCA `datetime.now().date()` (hora
    local del proceso). Falla en cuanto alguien revierta a la versión
    naive.
    """
    import ast
    import inspect

    source = inspect.getsource(detector.detect_for_user)
    tree = ast.parse(source.strip())

    naive_now_date = False
    utc_now = False
    for node in ast.walk(tree):
        # Buscar llamadas datetime.now(...)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "now"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "datetime"
        ):
            if not node.args and not node.keywords:
                naive_now_date = True  # datetime.now() sin tz → naive
            for arg in node.args:
                if isinstance(arg, ast.Name) and arg.id == "UTC":
                    utc_now = True

    assert utc_now, "detect_for_user debe usar datetime.now(UTC) como default de today"
    assert not naive_now_date, "detect_for_user no debe usar datetime.now() naive (hora local)"


# ---------------------------------------------------------------------------
# Finding 3 — fusión por prefijo: comportamiento documentado (sin BD)
# ---------------------------------------------------------------------------


def _occ(d: date) -> tuple[date, str, None]:
    return (d, "x", None)


def test_merge_still_combines_legitimate_prefix_variants() -> None:
    """Variantes del mismo comercio con sufijo divergente siguen
    fusionándose (no se endurece el umbral)."""
    grouped = {
        ("netflixmonthly", Decimal("12.99"), "EUR"): [_occ(date(2026, 1, 15))],
        ("netflixsuscripcionplus", Decimal("12.99"), "EUR"): [_occ(date(2026, 2, 15))],
    }
    out = _merge_by_common_prefix(grouped)
    assert len(out) == 1
    assert ("netflixsuscripcionplus", Decimal("12.99"), "EUR") in out


def test_merge_keeps_distinct_amounts_separate() -> None:
    """Salvaguarda parcial: mismo prefijo pero amount distinto no se
    fusiona."""
    grouped = {
        ("netflixcom", Decimal("12.99"), "EUR"): [_occ(date(2026, 1, 15))],
        ("netflixcom", Decimal("15.99"), "EUR"): [_occ(date(2026, 2, 15))],
    }
    out = _merge_by_common_prefix(grouped)
    assert len(out) == 2


# ---------------------------------------------------------------------------
# Helpers de integración (mismo patrón que el resto de la suite)
# ---------------------------------------------------------------------------


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


async def _create_category(
    client: AsyncClient,
    token: str,
    *,
    name: str,
    kind: str,
    is_transfer: bool = False,
) -> str:
    r = await client.post(
        "/categories",
        json={"name": name, "kind": kind, "is_transfer": is_transfer},
        headers=_auth(token),
    )
    return r.json()["id"]


async def _create_account(client: AsyncClient, token: str, name: str = "Cuenta") -> str:
    r = await client.post(
        "/accounts",
        json={"name": name, "type": "bank", "currency": "EUR"},
        headers=_auth(token),
    )
    return r.json()["id"]


async def _post_monthly_txs(
    client: AsyncClient,
    token: str,
    *,
    account_id: str,
    category_id: str,
    description: str,
    amount: str,
    count: int = 4,
) -> None:
    today = date.today()
    for i in range(count):
        when = today - timedelta(days=30 * i)
        await client.post(
            "/transactions",
            json={
                "account_id": account_id,
                "category_id": category_id,
                "amount": amount,
                "currency": "EUR",
                "occurred_at": f"{when.isoformat()}T12:00:00Z",
                "description": description,
            },
            headers=_auth(token),
        )


# ---------------------------------------------------------------------------
# Finding 1 — el detector excluye ingresos y transferencias
# ---------------------------------------------------------------------------


async def test_scan_ignores_income_payroll(client: AsyncClient) -> None:
    """Una nómina mensual recurrente (kind=income) NO se sugiere como
    gasto fijo."""
    token = await _register(client, "auditfix_income@example.com")
    account_id = await _create_account(client, token)
    income_cat = await _create_category(client, token, name="Nomina", kind="income")

    await _post_monthly_txs(
        client,
        token,
        account_id=account_id,
        category_id=income_cat,
        description="NOMINA EMPRESA SA",
        amount="2500.00",
    )

    await client.post("/fixed-expenses/scan", headers=_auth(token))
    items = (await client.get("/fixed-expenses", headers=_auth(token))).json()
    assert items == []


async def test_scan_ignores_transfer_category(client: AsyncClient) -> None:
    """Un movimiento periódico con categoría marcada is_transfer NO se
    sugiere como gasto fijo."""
    token = await _register(client, "auditfix_transfer@example.com")
    account_id = await _create_account(client, token)
    transfer_cat = await _create_category(
        client, token, name="Traspaso ahorro", kind="expense", is_transfer=True
    )

    await _post_monthly_txs(
        client,
        token,
        account_id=account_id,
        category_id=transfer_cat,
        description="TRASPASO A AHORRO",
        amount="300.00",
    )

    await client.post("/fixed-expenses/scan", headers=_auth(token))
    items = (await client.get("/fixed-expenses", headers=_auth(token))).json()
    assert items == []


async def test_scan_ignores_transfer_pair_leg(client: AsyncClient, test_engine) -> None:
    """Una pata de transferencia (transfer_pair_id IS NOT NULL) NO entra
    en el detector aunque su categoría sea un gasto normal."""
    token = await _register(client, "auditfix_pair@example.com")
    account_id = await _create_account(client, token)
    expense_cat = await _create_category(client, token, name="Movs", kind="expense")

    await _post_monthly_txs(
        client,
        token,
        account_id=account_id,
        category_id=expense_cat,
        description="MOVIMIENTO INTERNO",
        amount="150.00",
    )

    # Marcamos todas las txs como patas emparejadas (transfer_pair_id no
    # nulo) directamente en BD — basta apuntarlas unas a otras.
    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        txs = (
            (await db.execute(select(Transaction).order_by(Transaction.occurred_at)))
            .scalars()
            .all()
        )
        assert len(txs) >= 3
        # Encadenamos cada tx con la siguiente como su "par".
        for i, tx in enumerate(txs):
            tx.transfer_pair_id = txs[(i + 1) % len(txs)].id
        await db.commit()

    await client.post("/fixed-expenses/scan", headers=_auth(token))
    items = (await client.get("/fixed-expenses", headers=_auth(token))).json()
    assert items == []


async def test_scan_still_detects_real_expense(client: AsyncClient) -> None:
    """Regresión: un gasto real recurrente (kind=expense, no transfer)
    SÍ se sigue detectando — el filtro no es demasiado estricto."""
    token = await _register(client, "auditfix_realexpense@example.com")
    account_id = await _create_account(client, token)
    expense_cat = await _create_category(client, token, name="Streaming", kind="expense")

    await _post_monthly_txs(
        client,
        token,
        account_id=account_id,
        category_id=expense_cat,
        description="NETFLIX.COM",
        amount="12.99",
    )

    r = await client.post("/fixed-expenses/scan", headers=_auth(token))
    assert r.json()["created"] == 1


async def test_scan_excludes_only_income_keeps_expense(client: AsyncClient) -> None:
    """Mezcla: nómina (income) + alquiler (expense) recurrentes. Sólo el
    gasto sobrevive al detector."""
    token = await _register(client, "auditfix_mixed@example.com")
    account_id = await _create_account(client, token)
    income_cat = await _create_category(client, token, name="Nomina", kind="income")
    expense_cat = await _create_category(client, token, name="Vivienda", kind="expense")

    await _post_monthly_txs(
        client,
        token,
        account_id=account_id,
        category_id=income_cat,
        description="NOMINA EMPRESA",
        amount="2500.00",
    )
    await _post_monthly_txs(
        client,
        token,
        account_id=account_id,
        category_id=expense_cat,
        description="ALQUILER PISO",
        amount="900.00",
    )

    await client.post("/fixed-expenses/scan", headers=_auth(token))
    items = (await client.get("/fixed-expenses", headers=_auth(token))).json()
    assert len(items) == 1
    assert items[0]["merchant"].startswith("alquiler")


# ---------------------------------------------------------------------------
# Finding 5 — confirmar reactiva un dismissed directamente a confirmed
# ---------------------------------------------------------------------------


async def test_confirm_reactivates_dismissed_directly(client: AsyncClient, test_engine) -> None:
    """Confirmar un gasto fijo `dismissed` lo lleva a `confirmed` (la
    rama muerta que pasaba por `pending` se eliminó)."""
    token = await _register(client, "auditfix_confirm@example.com")
    account_id = await _create_account(client, token)
    expense_cat = await _create_category(client, token, name="Gym", kind="expense")
    await _post_monthly_txs(
        client,
        token,
        account_id=account_id,
        category_id=expense_cat,
        description="GIMNASIO MCFIT",
        amount="29.99",
    )
    await client.post("/fixed-expenses/scan", headers=_auth(token))
    fid = (await client.get("/fixed-expenses", headers=_auth(token))).json()[0]["id"]

    # Dismiss → confirm vía service directo para inspeccionar el estado.
    await client.post(f"/fixed-expenses/{fid}/dismiss", headers=_auth(token))

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        import uuid as _uuid

        item = (
            await db.execute(select(FixedExpense).where(FixedExpense.id == _uuid.UUID(fid)))
        ).scalar_one()
        assert item.status == FixedExpenseStatus.DISMISSED

        result = await confirm_fixed_expense(db, item.id, item.user_id)
        await db.commit()
        assert result.status == FixedExpenseStatus.CONFIRMED


# ---------------------------------------------------------------------------
# Finding 4 — integración: autopost mensual no deriva de día
# ---------------------------------------------------------------------------


async def test_autopost_monthly_advances_by_calendar(client: AsyncClient, test_engine) -> None:
    """Con cadencia mensual (30) y next_due en el día 31, el autopost
    avanza por calendario (28/30/31) en vez de sumar 30 días fijos."""
    token = await _register(client, "auditfix_autopost@example.com")
    account_id = await _create_account(client, token)
    expense_cat = await _create_category(client, token, name="Hipoteca", kind="expense")
    await _post_monthly_txs(
        client,
        token,
        account_id=account_id,
        category_id=expense_cat,
        description="HIPOTECA SANTANDER",
        amount="800.00",
    )
    await client.post("/fixed-expenses/scan", headers=_auth(token))
    fid = (await client.get("/fixed-expenses", headers=_auth(token))).json()[0]["id"]
    await client.put(
        f"/fixed-expenses/{fid}",
        json={"auto_post": True, "account_id": account_id},
        headers=_auth(token),
    )

    import uuid as _uuid

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        item = (
            await db.execute(select(FixedExpense).where(FixedExpense.id == _uuid.UUID(fid)))
        ).scalar_one()
        # Forzamos cadencia mensual + next_due al 31 de enero + anchor al
        # día 31 (vía first_seen_at) para ejercitar el avance calendario.
        # El autopost sólo dispara con status=CONFIRMED (list_due_for_autopost),
        # así que confirmamos el item explícitamente.
        item.status = FixedExpenseStatus.CONFIRMED
        item.cadence_days = 30
        item.first_seen_at = date(2026, 1, 31)
        item.next_due = date(2026, 1, 31)
        await db.commit()

        # `today` justo después del primer vencimiento → un solo ciclo.
        result = await autopost_due_for_user(db, item.user_id, today=date(2026, 2, 1))
        await db.commit()
        assert result.created == 1

        await db.refresh(item)
        # 31-ene + 1 mes calendario = 28-feb (no 2-mar, que sería 31+30d).
        assert item.next_due == date(2026, 2, 28)
        assert item.next_due != date(2026, 1, 31) + timedelta(days=30)
