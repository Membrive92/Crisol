"""El mes lo define el usuario — `users.cycle_start_day` (entregable C1).

Dos cosas viven aquí:

1. **El guardarraíl de toda la fase**: cambiar el ciclo no mueve ni un céntimo
   de ningún saldo. Es el invariante innegociable del diseño y está escrito
   como test, no como comentario, porque un comentario no se recalcula.
2. El contrato de `PATCH /users/me`: rango, limpieza del ajuste, propagación a
   `GET /auth/me` y aislamiento entre usuarios.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.accounts.models import Account, AccountNature, AccountType
from app.modules.personal_finance.accounts.position_history import compute_position_as_of
from app.modules.personal_finance.accounts.service import get_balances
from app.modules.personal_finance.categories.models import Category, CategoryKind
from app.modules.personal_finance.debt.health import compute_debt_health
from app.modules.personal_finance.transactions.models import Transaction, TransactionFlow
from app.modules.users.models import User

# Ventana con transacciones a ambos lados del día 14: si alguna query de dinero
# empezara a cortar por ciclo, estos importes se repartirían distinto y los
# agregados cambiarían. Con un mes natural todo julio va junto; con D=14, la
# nómina del 14 abre un ciclo nuevo y las compras del 3 y el 10 se quedan en el
# anterior.
_JUL_03 = datetime(2026, 7, 3, 9, 0, 0, tzinfo=UTC)
_JUL_10 = datetime(2026, 7, 10, 9, 0, 0, tzinfo=UTC)
_JUL_14 = datetime(2026, 7, 14, 9, 0, 0, tzinfo=UTC)
_JUL_28 = datetime(2026, 7, 28, 9, 0, 0, tzinfo=UTC)
_AUG_05 = datetime(2026, 8, 5, 9, 0, 0, tzinfo=UTC)
_AUG_14 = datetime(2026, 8, 14, 9, 0, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def session_factory(test_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)


async def _seed_user(session_factory) -> uuid.UUID:  # type: ignore[no-untyped-def]
    uid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            User(
                id=uid,
                email=f"cycle_{uid.hex[:8]}@example.com",
                password_hash="x",
                display_name="Cycle",
            )
        )
        await db.commit()
    return uid


async def _set_cycle_start_day(  # type: ignore[no-untyped-def]
    session_factory, user_id: uuid.UUID, value: int | None
) -> None:
    async with session_factory() as db:
        user = await db.get(User, user_id)
        assert user is not None
        user.cycle_start_day = value
        await db.commit()


async def _seed_account(  # type: ignore[no-untyped-def]
    session_factory,
    user_id: uuid.UUID,
    *,
    nature: AccountNature,
    type_: AccountType,
    opening_balance: Decimal = Decimal("0"),
) -> uuid.UUID:
    aid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            Account(
                id=aid,
                user_id=user_id,
                name=f"acc_{aid.hex[:6]}",
                nature=nature,
                type=type_,
                currency="EUR",
                opening_balance=opening_balance,
            )
        )
        await db.commit()
    return aid


async def _seed_category(  # type: ignore[no-untyped-def]
    session_factory, user_id: uuid.UUID, *, kind: CategoryKind
) -> uuid.UUID:
    cid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            Category(
                id=cid,
                user_id=user_id,
                name=f"cat_{cid.hex[:6]}",
                kind=kind,
                is_transfer=False,
            )
        )
        await db.commit()
    return cid


async def _seed_tx(  # type: ignore[no-untyped-def]
    session_factory,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    *,
    amount: Decimal,
    flow: TransactionFlow,
    when: datetime,
    category_id: uuid.UUID | None = None,
) -> None:
    async with session_factory() as db:
        db.add(
            Transaction(
                id=uuid.uuid4(),
                user_id=user_id,
                account_id=account_id,
                category_id=category_id,
                amount=amount,
                currency="EUR",
                occurred_at=when,
                flow=flow,
            )
        )
        await db.commit()


async def _money_snapshot(session_factory, user_id: uuid.UUID) -> dict[str, object]:  # type: ignore[no-untyped-def]
    """Las tres respuestas de dinero del backend, serializadas al céntimo.

    `get_balances` (saldo por cuenta + patrimonio), `compute_position_as_of`
    (patrimonio a fecha + Δ del período) y `compute_debt_health` (deuda viva,
    tasa de esfuerzo, intereses). Si el ciclo se colara en cualquiera de ellas,
    este diccionario cambiaría.
    """
    async with session_factory() as db:
        balances = await get_balances(db, user_id)
        position = await compute_position_as_of(
            db,
            user_id,
            date_from=datetime(2026, 7, 1, 0, 0, 0, tzinfo=UTC),
            date_to=datetime(2026, 8, 31, 23, 59, 59, tzinfo=UTC),
        )
        health = await compute_debt_health(db, user_id)
    return {
        "balances": balances.model_dump(),
        "position": position.model_dump(),
        "debt_health": health.model_dump(),
    }


# ─────────────────────────────────────────────────────────────────────
# El guardarraíl de la fase.
# ─────────────────────────────────────────────────────────────────────


async def test_el_ciclo_no_mueve_ni_un_centimo(session_factory) -> None:  # type: ignore[no-untyped-def]
    """Cambiar `cycle_start_day` no altera ningún saldo, patrimonio ni KPI de deuda.

    El ciclo del usuario es una convención de PRESENTACIÓN: dice cómo se
    AGRUPAN los flujos para enseñarlos, no qué hizo el dinero. La fuente de
    verdad del dinero es `transactions.flow` + `account.nature` (ADR-0004) y no
    puede moverse por una cuestión de etiquetas — es la familia de lecciones
    PHASE-34/37/38, y la misma forma que el guardarraíl de PHASE-47.H («el neto
    no se mueve»).

    **Hoy este test pasa trivialmente**, porque ninguna query de dinero lee la
    columna. Ese es exactamente el punto y por eso se escribe AHORA y no al
    final: el entregable siguiente (C4) desplaza el bucketing mensual de las
    series de P&G a `date_trunc('month', occurred_at − (D−1) días)`, y ese
    desplazamiento tiene que quedarse en los flujos. El día que alguien lo cuele
    en `signed_amount_expr`, en `get_balances_for_user` o en el MUX del cuadro
    de amortización, este test se cae — que es la única forma de que la premisa
    sobreviva a quien la escribió (lección PHASE-44.21).

    Los datos están sembrados a ambos lados del día 14 a propósito: con D=14 la
    nómina del 14 de julio abre un ciclo nuevo y las compras del 3 y el 10 se
    quedan en el anterior. Si el corte se filtrara a estas tres respuestas, el
    reparto distinto asomaría.
    """
    uid = await _seed_user(session_factory)
    bbva = await _seed_account(
        session_factory,
        uid,
        nature=AccountNature.ASSET,
        type_=AccountType.BANK,
        opening_balance=Decimal("1000.00"),
    )
    tarjeta = await _seed_account(
        session_factory,
        uid,
        nature=AccountNature.LIABILITY,
        type_=AccountType.CREDIT_CARD,
        opening_balance=Decimal("0"),
    )
    compras = await _seed_category(session_factory, uid, kind=CategoryKind.EXPENSE)
    nomina = await _seed_category(session_factory, uid, kind=CategoryKind.INCOME)

    # Antes del corte del 14.
    await _seed_tx(
        session_factory,
        uid,
        bbva,
        amount=Decimal("120.50"),
        flow=TransactionFlow.OUT,
        when=_JUL_03,
        category_id=compras,
    )
    await _seed_tx(
        session_factory,
        uid,
        tarjeta,
        amount=Decimal("75.25"),
        flow=TransactionFlow.OUT,
        when=_JUL_10,
        category_id=compras,
    )
    # Justo en el corte: la nómina del 14 es el caso motivador de la fase.
    await _seed_tx(
        session_factory,
        uid,
        bbva,
        amount=Decimal("2520.68"),
        flow=TransactionFlow.IN,
        when=_JUL_14,
        category_id=nomina,
    )
    # Después del corte, y en el ciclo siguiente.
    await _seed_tx(
        session_factory,
        uid,
        bbva,
        amount=Decimal("340.00"),
        flow=TransactionFlow.OUT,
        when=_JUL_28,
        category_id=compras,
    )
    await _seed_tx(
        session_factory,
        uid,
        tarjeta,
        amount=Decimal("60.00"),
        flow=TransactionFlow.OUT,
        when=_AUG_05,
        category_id=compras,
    )
    await _seed_tx(
        session_factory,
        uid,
        bbva,
        amount=Decimal("2520.68"),
        flow=TransactionFlow.IN,
        when=_AUG_14,
        category_id=nomina,
    )

    # Mes natural (el estado de todo el mundo hoy).
    await _set_cycle_start_day(session_factory, uid, None)
    natural = await _money_snapshot(session_factory, uid)

    # El ciclo del usuario: su mes empieza el 14.
    await _set_cycle_start_day(session_factory, uid, 14)
    con_ciclo = await _money_snapshot(session_factory, uid)

    assert con_ciclo == natural

    # Y el día 1, que degenera en el mes natural, tampoco puede cambiar nada:
    # cubre el caso en que alguien "aplicara" el ciclo sólo cuando no es NULL.
    await _set_cycle_start_day(session_factory, uid, 1)
    con_dia_uno = await _money_snapshot(session_factory, uid)
    assert con_dia_uno == natural

    # Sanity con importes concretos: si el snapshot saliera vacío o a cero, las
    # igualdades de arriba serían ciertas sin probar nada — un test que compara
    # dos veces la nada. Activo: 1000 − 120,50 + 2520,68 − 340,00 + 2520,68.
    # Pasivo: 75,25 + 60,00 de cargos en la tarjeta.
    balances = natural["balances"]
    assert isinstance(balances, dict)
    assert balances["total_assets"] == Decimal("5580.86")
    assert balances["total_liabilities"] == Decimal("135.25")
    assert balances["net_worth"] == Decimal("5445.61")


# ─────────────────────────────────────────────────────────────────────
# El dato: la columna y su rango.
# ─────────────────────────────────────────────────────────────────────


async def test_el_check_de_la_bd_rechaza_un_dia_fuera_de_rango(session_factory) -> None:  # type: ignore[no-untyped-def]
    """El rango 1-28 lo reafirma un CHECK en la BD, no sólo el schema Pydantic.

    Es la última línea de defensa: valga cual valga la vía de escritura (script
    de data-fix, seed, fix manual), un día imposible no llega a persistirse. Sin
    esto, la validación viviría sólo en la frontera HTTP.
    """
    uid = await _seed_user(session_factory)
    with pytest.raises(IntegrityError):
        async with session_factory() as db:
            user = await db.get(User, uid)
            assert user is not None
            user.cycle_start_day = 31
            await db.commit()


async def test_el_ajuste_nace_vacio(session_factory) -> None:  # type: ignore[no-untyped-def]
    """NULL es el estado correcto por defecto, no un hueco por rellenar.

    La columna no tiene default numérico a propósito (lección PHASE-44.11): un
    `1` afirmaría que el usuario declaró que su mes empieza el día 1, y sería
    indistinguible de un dato que puso él.
    """
    uid = await _seed_user(session_factory)
    async with session_factory() as db:
        user = await db.get(User, uid)
    assert user is not None
    assert user.cycle_start_day is None


# ─────────────────────────────────────────────────────────────────────
# PATCH /users/me
# ─────────────────────────────────────────────────────────────────────


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Cycle"},
    )
    assert r.status_code == 201, r.text
    token: str = r.json()["access_token"]
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_patch_me_guarda_el_dia_y_aparece_en_auth_me(client: AsyncClient) -> None:
    """El día se persiste y viaja en `GET /auth/me`, que serializa el mismo schema."""
    token = await _register(client, "cycle_ok@example.com")

    me_antes = await client.get("/auth/me", headers=_auth(token))
    assert me_antes.status_code == 200
    assert me_antes.json()["cycle_start_day"] is None

    r = await client.patch("/users/me", json={"cycle_start_day": 14}, headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["cycle_start_day"] == 14

    me = await client.get("/auth/me", headers=_auth(token))
    assert me.json()["cycle_start_day"] == 14


async def test_patch_me_acepta_los_dos_extremos_del_rango(client: AsyncClient) -> None:
    """1 y 28 son válidos — el umbral se prueba a los DOS lados (PHASE-44.14).

    El 1 importa además por sí mismo: degenera exactamente en el mes natural y
    es la propiedad que verifica que la aritmética del ciclo está bien.
    """
    token = await _register(client, "cycle_bounds@example.com")

    for value in (1, 28):
        r = await client.patch("/users/me", json={"cycle_start_day": value}, headers=_auth(token))
        assert r.status_code == 200, r.text
        assert r.json()["cycle_start_day"] == value


@pytest.mark.parametrize("bad", [0, 29, 31])
async def test_patch_me_rechaza_dias_imposibles(client: AsyncClient, bad: int) -> None:
    """0 (no existe el día 0), 29 y 31 (no existen en todos los meses) → 422.

    29-31 quedan fuera a propósito y no por prudencia: con `D ≤ 28` el ciclo
    nunca necesita clamping de fin de mes, y el clamp de febrero es una charca
    de bugs a cambio de un caso que nadie tiene.
    """
    token = await _register(client, f"cycle_bad_{bad}@example.com")
    r = await client.patch("/users/me", json={"cycle_start_day": bad}, headers=_auth(token))
    assert r.status_code == 422, r.text


async def test_patch_me_con_null_limpia_el_ajuste(client: AsyncClient) -> None:
    """`null` devuelve al usuario al mes natural.

    Por eso el campo es requerido-pero-nullable en el body: enviar `null`
    significa algo, así que no hace falta distinguir ausente-vs-None.
    """
    token = await _register(client, "cycle_clear@example.com")
    puesto = await client.patch("/users/me", json={"cycle_start_day": 14}, headers=_auth(token))
    # La premisa del test, afirmada: sin esto, un servidor que NUNCA guarda
    # nada pasaría este test —el valor ya nacía a `null`— y el "limpia" no
    # probaría nada. Lo destapó romper el service a propósito.
    assert puesto.json()["cycle_start_day"] == 14

    r = await client.patch("/users/me", json={"cycle_start_day": None}, headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["cycle_start_day"] is None

    me = await client.get("/auth/me", headers=_auth(token))
    assert me.json()["cycle_start_day"] is None


async def test_patch_me_exige_el_campo(client: AsyncClient) -> None:
    """Omitir el campo es 422, no un no-op silencioso.

    Un PATCH que acepta el body vacío deja al cliente sin saber si su intención
    se aplicó; aquí sólo hay una preferencia y su ausencia es un error del
    llamante.
    """
    token = await _register(client, "cycle_missing@example.com")
    r = await client.patch("/users/me", json={}, headers=_auth(token))
    assert r.status_code == 422, r.text


async def test_patch_me_requiere_autenticacion(client: AsyncClient) -> None:
    """Sin token, 401 — el endpoint no tiene otra forma de saber a quién toca."""
    r = await client.patch("/users/me", json={"cycle_start_day": 14})
    assert r.status_code == 401


async def test_patch_me_no_toca_el_ajuste_de_otro_usuario(client: AsyncClient) -> None:
    """Aislamiento: el único perfil alcanzable es el del token.

    No hay identificador de usuario en la ruta ni en el body, así que no existe
    superficie para pedir el de otro; el test fija ese contrato para que añadir
    un `user_id` al body más adelante tenga que romperlo antes.
    """
    token_a = await _register(client, "cycle_a@example.com")
    token_b = await _register(client, "cycle_b@example.com")

    await client.patch("/users/me", json={"cycle_start_day": 14}, headers=_auth(token_a))
    me_b = await client.get("/auth/me", headers=_auth(token_b))
    assert me_b.json()["cycle_start_day"] is None

    await client.patch("/users/me", json={"cycle_start_day": 7}, headers=_auth(token_b))
    me_a = await client.get("/auth/me", headers=_auth(token_a))
    assert me_a.json()["cycle_start_day"] == 14
    me_b2 = await client.get("/auth/me", headers=_auth(token_b))
    assert me_b2.json()["cycle_start_day"] == 7


async def test_patch_me_refresca_updated_at_sin_missing_greenlet(client: AsyncClient) -> None:
    """`updated_at` llega recalculado en la MISMA respuesta del PATCH.

    La columna lleva `onupdate=func.now()`, así que tras el UPDATE el valor que
    calcula la BD no vuelve solo al objeto en memoria: serializarlo sin
    `db.refresh` dispararía un lazy load sobre una sesión async y reventaría con
    `MissingGreenlet` (lección PHASE-4.1). Que el timestamp AVANCE es lo que
    prueba que el refresh ocurrió — un 200 con el valor viejo también sería
    verde sin él.
    """
    token = await _register(client, "cycle_updated@example.com")
    before = (await client.get("/auth/me", headers=_auth(token))).json()["updated_at"]

    r = await client.patch("/users/me", json={"cycle_start_day": 14}, headers=_auth(token))
    assert r.status_code == 200, r.text
    after = r.json()["updated_at"]
    assert after > before
