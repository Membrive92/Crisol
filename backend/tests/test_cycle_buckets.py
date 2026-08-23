"""C4 — El histórico entero cortado por el ciclo del usuario.

El usuario declara el día en que empieza su mes (`users.cycle_start_day`) y las
series de pérdidas y ganancias dejan de cortar por mes natural: pasan a ser
barras de CICLO, para todo el histórico. Decisión D6 del plan, literal del
usuario: *«si el usuario define que el 13 es su fecha de inicio de mes, debería
ajustarse todo el histórico para ver los flujos de caja»*.

Lo que se prueba aquí es el desplazamiento del **bucketing**, y nada más. El
guardarraíl de que ni un céntimo de ningún saldo se mueve vive aparte, en
`test_user_cycle.py::test_el_ciclo_no_mueve_ni_un_centimo`.

De los tests de abajo, estos cuatro son los que gobiernan (el resto cubre las
piezas concretas: bounds, chips, drill-down, cruce de año y el comparable):

- **Conservación**: desplazar el bucketing no puede perder ni duplicar una
  transacción. Es el que caza un off-by-one entre el `GROUP BY` de SQL y el
  relleno de huecos de Python.
- **Frontera en la BD**: réplica en SQL del test puro de `cycle-period.test.ts`.
  Una tx el día D a las 00:00Z abre ciclo; el D−1 a las 23:59:59Z, no.
- **`D = 1` idéntico**: si el ciclo degenerado no da byte a byte el mes natural,
  la aritmética está mal.
- **El portero**: `cycle=true` sin ajuste es 422, y `cycle` ausente deja el mes
  natural intacto aunque el ajuste exista — son dos preguntas distintas y las
  dos siguen teniendo respuesta.
"""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client: AsyncClient, email: str) -> tuple[str, str]:
    """Registra un usuario y crea una cuenta. Devuelve `(token, account_id)`."""
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Ciclo"},
    )
    assert r.status_code == 201, r.text
    token: str = r.json()["access_token"]
    acc = await client.post(
        "/accounts",
        json={"name": "Cuenta principal", "type": "bank", "currency": "USD"},
        headers=_auth(token),
    )
    assert acc.status_code == 201, acc.text
    account_id: str = acc.json()["id"]
    return token, account_id


async def _set_cycle(client: AsyncClient, token: str, day: int | None) -> None:
    r = await client.patch("/users/me", json={"cycle_start_day": day}, headers=_auth(token))
    assert r.status_code == 200, r.text
    # La premisa del test, afirmada: si el PATCH no guardara, todo lo de abajo
    # estaría midiendo el mes natural creyendo medir el ciclo.
    assert r.json()["cycle_start_day"] == day


async def _make_category(client: AsyncClient, token: str, *, name: str, kind: str) -> str:
    r = await client.post("/categories", json={"name": name, "kind": kind}, headers=_auth(token))
    assert r.status_code == 201, r.text
    cid: str = r.json()["id"]
    return cid


async def _make_tx(
    client: AsyncClient,
    token: str,
    account_id: str,
    *,
    amount: str,
    occurred_at: str,
    category_id: str,
    flow: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "account_id": account_id,
        "amount": amount,
        "currency": "USD",
        "occurred_at": occurred_at,
        "category_id": category_id,
    }
    if flow is not None:
        payload["flow"] = flow
    r = await client.post("/transactions", json=payload, headers=_auth(token))
    assert r.status_code == 201, r.text


def _bucket(buckets: list[dict[str, object]], month: str) -> dict[str, object]:
    for b in buckets:
        if b["month"] == month:
            return b
    raise AssertionError(f"no hay bucket {month} en {[b['month'] for b in buckets]}")


def _sum(buckets: list[dict[str, object]], field: str) -> Decimal:
    return sum((Decimal(str(b[field])) for b in buckets), Decimal("0"))


# ─────────────────────────────────────────────────────────────────────
# Conservación — el test que caza un off-by-one del desplazamiento.
# ─────────────────────────────────────────────────────────────────────


async def test_los_buckets_de_ciclo_conservan_el_dinero_del_rango(client: AsyncClient) -> None:
    """Σ(buckets de ciclo) == Σ(buckets naturales) == total del período.

    Desplazar el bucketing reparte el dinero de otra forma; no puede hacerlo
    desaparecer. El caso que lo caza es el borde INFERIOR del rango: con `D = 14`
    y un rango que empieza el 1 de julio, el ancla de `date_from` es **junio**
    (1-jul − 13 días), así que una tx del 3 de julio se agrupa en el ciclo del
    14-jun. Un relleno de huecos que iterase meses NATURALES empezaría en julio,
    ese bucket no existiría en la respuesta y sus 300 $ se perderían — sin error,
    sin aviso y con las demás barras cuadrando.
    """
    token, account_id = await _register(client, "cycle-conservacion@example.com")
    gasto = await _make_category(client, token, name="Compras", kind="expense")
    ingreso = await _make_category(client, token, name="Nómina", kind="income")

    # Jul 3 → ciclo del 14-jun · Jul 20 y Ago 5 → ciclo del 14-jul · Ago 20 → 14-ago
    await _make_tx(
        client,
        token,
        account_id,
        amount="300.00",
        occurred_at="2026-07-03T10:00:00Z",
        category_id=gasto,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="2000.00",
        occurred_at="2026-07-20T10:00:00Z",
        category_id=ingreso,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="150.00",
        occurred_at="2026-08-05T10:00:00Z",
        category_id=gasto,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="1000.00",
        occurred_at="2026-08-20T10:00:00Z",
        category_id=ingreso,
    )

    # Una DEVOLUCIÓN (entra dinero en una categoría de GASTO). Sin ella el test
    # era ciego a la mitad del invariante que dice medir: las cuatro tx de
    # arriba caen todas del lado sin signo, así que la igualdad
    # «Σ barras == total del resumen» se cumplía aunque las barras sumaran los
    # reembolsos en positivo y el resumen los restara. Con datos reales esa
    # diferencia era de 272,10 € en un solo mes.
    await _make_tx(
        client,
        token,
        account_id,
        amount="50.00",
        occurred_at="2026-07-25T10:00:00Z",
        category_id=gasto,
        flow="IN",
    )

    await _set_cycle(client, token, 14)
    rango = {"date_from": "2026-07-01T00:00:00Z", "date_to": "2026-08-31T23:59:59Z"}

    natural = (await client.get("/dashboard/by-month", params=rango, headers=_auth(token))).json()
    ciclo = (
        await client.get(
            "/dashboard/by-month", params={**rango, "cycle": "true"}, headers=_auth(token)
        )
    ).json()
    resumen = (await client.get("/dashboard/summary", params=rango, headers=_auth(token))).json()

    # El reparto SÍ cambia — si no, el test no estaría probando el ciclo.
    assert [b["month"] for b in natural] == ["2026-07", "2026-08"]
    assert [b["month"] for b in ciclo] == ["2026-06", "2026-07", "2026-08"]

    # Gasto = 300 + 150 − 50 (la devolución RESTA de su categoría), no 500.
    for field, total in (("income", "3000.00"), ("expenses", "400.00")):
        assert _sum(ciclo, field) == _sum(natural, field) == Decimal(total)
    assert Decimal(resumen["income"]) == Decimal("3000.00")
    assert Decimal(resumen["expenses"]) == Decimal("400.00")

    # Y el reparto concreto, para que la conservación no se cumpla por casualidad
    # con todo en un solo bucket.
    assert Decimal(str(_bucket(ciclo, "2026-06")["expenses"])) == Decimal("300.00")
    assert Decimal(str(_bucket(ciclo, "2026-07")["income"])) == Decimal("2000.00")
    # 150 (5-ago) − 50 (la devolución del 25-jul, que también cae en este ciclo).
    assert Decimal(str(_bucket(ciclo, "2026-07")["expenses"])) == Decimal("100.00")
    assert Decimal(str(_bucket(ciclo, "2026-08")["income"])) == Decimal("1000.00")
    # La devolución NO se cuela en el cubo de ingresos por ningún camino.
    assert _sum(ciclo, "income") == _sum(natural, "income") == Decimal("3000.00")


# ─────────────────────────────────────────────────────────────────────
# La frontera, en la BD.
# ─────────────────────────────────────────────────────────────────────


async def test_la_frontera_del_ciclo_en_sql_es_el_dia_d_a_las_cero_horas(
    client: AsyncClient,
) -> None:
    """El día D a las 00:00Z abre ciclo; el D−1 a las 23:59:59Z cierra el anterior.

    Réplica en PostgreSQL del test puro de `cycle-period.test.ts`: el corte lo
    hace SQL restando `D − 1` días, y el frontend lo hace en JavaScript emitiendo
    los bounds. Si los dos no cortan en el MISMO instante, el usuario ve un
    período cuyos totales no cuadran con sus barras.
    """
    token, account_id = await _register(client, "cycle-frontera@example.com")
    gasto = await _make_category(client, token, name="Compras", kind="expense")
    await _set_cycle(client, token, 14)

    await _make_tx(
        client,
        token,
        account_id,
        amount="11.00",
        occurred_at="2026-08-14T00:00:00Z",
        category_id=gasto,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="22.00",
        occurred_at="2026-08-13T23:59:59Z",
        category_id=gasto,
    )

    buckets = (
        await client.get(
            "/dashboard/by-month", params={"year": 2026, "cycle": "true"}, headers=_auth(token)
        )
    ).json()
    assert Decimal(str(_bucket(buckets, "2026-08")["expenses"])) == Decimal("11.00")
    assert Decimal(str(_bucket(buckets, "2026-07")["expenses"])) == Decimal("22.00")


async def test_el_ciclo_cruza_el_ano_sin_partirse(client: AsyncClient) -> None:
    """Una tx del 5 de enero con `D = 14` pertenece al ciclo del 14 de DICIEMBRE.

    El año hay que leerlo del instante desplazado igual que el mes: leyéndolo del
    original, el ciclo del 14-dic aparecería partido entre dos años y la vista
    anual perdería sus últimas semanas.
    """
    token, account_id = await _register(client, "cycle-ano@example.com")
    gasto = await _make_category(client, token, name="Compras", kind="expense")
    await _set_cycle(client, token, 14)
    await _make_tx(
        client,
        token,
        account_id,
        amount="90.00",
        occurred_at="2026-01-05T10:00:00Z",
        category_id=gasto,
    )

    en_2025 = (
        await client.get(
            "/dashboard/by-month", params={"year": 2025, "cycle": "true"}, headers=_auth(token)
        )
    ).json()
    en_2026 = (
        await client.get(
            "/dashboard/by-month", params={"year": 2026, "cycle": "true"}, headers=_auth(token)
        )
    ).json()

    # El período del 14-dic-2025 es su propio bucket en la vista de 2025…
    assert Decimal(str(_bucket(en_2025, "2025-12")["expenses"])) == Decimal("90.00")
    # …y NO aparece en la de 2026.
    #
    # Aquí se afirmó lo contrario durante unas horas: que ese bucket abriera
    # también la vista de 2026, para no perder los días 1..D−1 de enero. El
    # usuario lo vio en pantalla y lo cortó de raíz: «si estoy viendo gastos de
    # 2026, no debería salir ese diciembre de 2025».
    #
    # Tenía razón, y lo que faltaba no era una barra: era desplazar también el
    # AÑO. El año del usuario va del 14-ene al 13-ene, así que sus doce
    # períodos lo cubren entero y ese gasto del 5 de enero cae en su año 2025,
    # donde le toca.
    assert "2025-12" not in [b["month"] for b in en_2026]
    assert _sum(en_2026, "expenses") == Decimal("0")


async def test_la_serie_en_ciclos_cubre_el_ano_del_usuario_sin_huecos(
    client: AsyncClient,
) -> None:
    """CONSERVACIÓN: los doce períodos cubren el año DEL USUARIO, entero.

    La versión anterior de este test comparaba la suma en ciclos con la del año
    NATURAL y exigía que fueran iguales. Ya no lo son, y es correcto que no lo
    sean: son años distintos. El año del usuario con D=13 va del 13-ene al
    12-ene, así que un gasto del 3 de enero pertenece a su año ANTERIOR.

    Lo que sí tiene que cumplirse —y es la propiedad que importa— es que sus
    doce períodos no dejen huecos: todo movimiento entre el 13-ene y el 12-ene
    del año siguiente cae en exactamente una barra.
    """
    token, account_id = await _register(client, "cycle-conserva@example.com")
    gasto = await _make_category(client, token, name="Compras", kind="expense")
    await _set_cycle(client, token, 13)
    # Uno el primer día de su año, otro el último, y uno fuera (su año anterior).
    for fecha, importe in (
        ("2026-01-13", "40.00"),
        ("2027-01-12", "60.00"),
        ("2026-01-03", "99.00"),
    ):
        await _make_tx(
            client,
            token,
            account_id,
            amount=importe,
            occurred_at=f"{fecha}T10:00:00Z",
            category_id=gasto,
        )

    en_ciclos = (
        await client.get(
            "/dashboard/by-month", params={"year": 2026, "cycle": "true"}, headers=_auth(token)
        )
    ).json()

    assert len(en_ciclos) == 12, "doce períodos, ni uno más"
    # Los dos extremos de SU año entran; el del 3 de enero no (es de su 2025).
    assert _sum(en_ciclos, "expenses") == Decimal("100.00")
    assert Decimal(str(_bucket(en_ciclos, "2026-01")["expenses"])) == Decimal("40.00")
    assert Decimal(str(_bucket(en_ciclos, "2026-12")["expenses"])) == Decimal("60.00")


# ─────────────────────────────────────────────────────────────────────
# `D = 1` degenera en el mes natural.
# ─────────────────────────────────────────────────────────────────────


async def test_el_dia_uno_da_exactamente_el_mes_natural(client: AsyncClient) -> None:
    """Con el ajuste a 1 y `cycle=true`, la respuesta es IDÉNTICA a la de hoy.

    No es una curiosidad: es la propiedad que verifica la aritmética. El día 1
    debe restar cero días, así que el ciclo y el mes natural son el mismo
    intervalo. Si estas respuestas difieren en un bucket, el desplazamiento tiene
    un off-by-one y todos los demás días están mal por la misma cantidad.

    Se comprueban las TRES formas del endpoint —vista de año, rango libre y los
    chips de períodos—, porque cada una lee el desplazamiento por su lado.

    Y se comprueban **en absoluto**, no sólo comparando las dos respuestas entre
    sí: desde C4 el relleno de huecos del rango pasa por la MISMA aritmética en
    los dos modos (`D = 1` es el mes natural), así que un fallo en ella movería
    las dos a la vez y la igualdad seguiría cierta. Lo destapó una sonda que no
    tumbó el test: restar `D` en vez de `D − 1` añadía un bucket vacío a las dos
    respuestas y pasaba en verde. Las listas de meses esperadas son el
    guardarraíl que faltaba.
    """
    token, account_id = await _register(client, "cycle-dia-uno@example.com")
    gasto = await _make_category(client, token, name="Compras", kind="expense")
    ingreso = await _make_category(client, token, name="Nómina", kind="income")
    for amount, when, cat in (
        ("300.00", "2026-07-03T10:00:00Z", gasto),
        ("2000.00", "2026-07-20T10:00:00Z", ingreso),
        ("150.00", "2026-08-05T10:00:00Z", gasto),
        ("1000.00", "2026-08-20T10:00:00Z", ingreso),
    ):
        await _make_tx(client, token, account_id, amount=amount, occurred_at=when, category_id=cat)

    rango = {"date_from": "2026-07-01T00:00:00Z", "date_to": "2026-08-31T23:59:59Z"}
    ano_natural = (
        await client.get("/dashboard/by-month", params={"year": 2026}, headers=_auth(token))
    ).json()
    rango_natural = (
        await client.get("/dashboard/by-month", params=rango, headers=_auth(token))
    ).json()
    chips_natural = (
        await client.get("/transactions/available-periods", headers=_auth(token))
    ).json()

    await _set_cycle(client, token, 1)
    ano_ciclo = (
        await client.get(
            "/dashboard/by-month", params={"year": 2026, "cycle": "true"}, headers=_auth(token)
        )
    ).json()
    rango_ciclo = (
        await client.get(
            "/dashboard/by-month", params={**rango, "cycle": "true"}, headers=_auth(token)
        )
    ).json()
    chips_ciclo = (
        await client.get(
            "/transactions/available-periods", params={"cycle": "true"}, headers=_auth(token)
        )
    ).json()

    assert ano_ciclo == ano_natural
    assert rango_ciclo == rango_natural
    assert chips_ciclo == chips_natural
    # En ABSOLUTO: el rango 1-jul → 31-ago son exactamente esos dos meses, ni uno
    # más. Sin esta línea, un desplazamiento que se colara en los dos modos a la
    # vez (p. ej. restar `D` en vez de `D − 1`) añadiría un bucket vacío en ambos
    # y las igualdades de arriba lo taparían.
    assert [b["month"] for b in rango_natural] == ["2026-07", "2026-08"]
    assert [b["month"] for b in ano_natural] == [f"2026-{m:02d}" for m in range(1, 13)]
    # Sanity: si las tres respuestas estuvieran vacías, las igualdades de arriba
    # serían ciertas sin probar nada (dos veces la nada).
    assert _sum(ano_natural, "income") == Decimal("3000.00")
    assert chips_natural == {"periods": [{"year": 2026, "months": [7, 8]}]}


# ─────────────────────────────────────────────────────────────────────
# El portero: `cycle` sin ajuste, y `cycle` ausente con ajuste.
# ─────────────────────────────────────────────────────────────────────


async def test_pedir_ciclo_sin_ajuste_configurado_es_422(client: AsyncClient) -> None:
    """Sin día definido, `cycle=true` no puede responderse — y no se finge.

    Devolver el mes natural con un 200 sería peor que el error: el cliente creería
    estar viendo sus ciclos. Los cinco endpoints comparten el mismo portero, así
    que se comprueban los cinco.
    """
    token, account_id = await _register(client, "cycle-sin-ajuste@example.com")
    gasto = await _make_category(client, token, name="Compras", kind="expense")
    await _make_tx(
        client,
        token,
        account_id,
        amount="10.00",
        occurred_at="2026-08-20T10:00:00Z",
        category_id=gasto,
    )

    for path, params in (
        ("/dashboard/by-month", {"year": 2026}),
        ("/dashboard/summary", {}),
        (f"/dashboard/category/{gasto}", {}),
        (f"/dashboard/category/{gasto}/available-periods", {}),
        ("/transactions/available-periods", {}),
    ):
        r = await client.get(path, params={**params, "cycle": "true"}, headers=_auth(token))
        assert r.status_code == 422, f"{path} → {r.status_code} {r.text}"
        assert "Ajustes" in r.json()["detail"]


async def test_sin_el_flag_el_mes_natural_queda_intacto(client: AsyncClient) -> None:
    """Tener el ajuste puesto no cambia nada por sí solo.

    «Mes» y «Mi ciclo» son dos preguntas distintas —el calendario y la nómina— y
    las dos tienen que seguir teniendo respuesta. Si configurar el día re-cortara
    también las vistas de mes natural, el usuario perdería la vista del
    calendario sin haberlo pedido.
    """
    token, account_id = await _register(client, "cycle-sin-flag@example.com")
    gasto = await _make_category(client, token, name="Compras", kind="expense")
    await _make_tx(
        client,
        token,
        account_id,
        amount="40.00",
        occurred_at="2026-08-03T10:00:00Z",
        category_id=gasto,
    )

    antes = (
        await client.get("/dashboard/by-month", params={"year": 2026}, headers=_auth(token))
    ).json()
    await _set_cycle(client, token, 14)
    despues = (
        await client.get("/dashboard/by-month", params={"year": 2026}, headers=_auth(token))
    ).json()

    assert despues == antes
    assert Decimal(str(_bucket(antes, "2026-08")["expenses"])) == Decimal("40.00")
    # Y con el flag SÍ se mueve: el 3-ago pertenece al ciclo del 14-jul.
    con_ciclo = (
        await client.get(
            "/dashboard/by-month", params={"year": 2026, "cycle": "true"}, headers=_auth(token)
        )
    ).json()
    assert Decimal(str(_bucket(con_ciclo, "2026-07")["expenses"])) == Decimal("40.00")


# ─────────────────────────────────────────────────────────────────────
# «vs período anterior» ciclo-exacto.
# ─────────────────────────────────────────────────────────────────────


async def test_el_periodo_anterior_es_el_ciclo_anterior_completo(client: AsyncClient) -> None:
    """Con ciclo, el comparable es el ciclo anterior EXACTO, no una ventana igual.

    Los ciclos no miden lo mismo: el del 14-mar dura 31 días y el del 14-feb, 28.
    La ventana de igual longitud retrocede 31 días desde el 14-mar y aterriza en
    el **11 de febrero**, tres días dentro del ciclo anterior al anterior. Aquí
    esos tres días llevan un gasto de 500 $ que la ventana cuenta y el ciclo real
    no.

    El test afirma las DOS ramas a propósito: sin `cycle` sale 700 (la ventana) y
    con `cycle` sale 200 (el ciclo del 14-feb al 13-mar). Si sólo comprobara la
    segunda, un cambio que dejara de aplicar la rama del ciclo tendría que dar la
    casualidad de coincidir para pasar — y aquí no coincidirían.
    """
    token, account_id = await _register(client, "cycle-anterior@example.com")
    gasto = await _make_category(client, token, name="Compras", kind="expense")
    ingreso = await _make_category(client, token, name="Nómina", kind="income")

    # Ciclo del 14-ene → 13-feb: sólo lo alcanza la ventana de igual longitud.
    await _make_tx(
        client,
        token,
        account_id,
        amount="500.00",
        occurred_at="2026-02-12T10:00:00Z",
        category_id=gasto,
    )
    # Ciclo anterior de verdad (14-feb → 13-mar).
    await _make_tx(
        client,
        token,
        account_id,
        amount="1000.00",
        occurred_at="2026-02-20T10:00:00Z",
        category_id=ingreso,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="200.00",
        occurred_at="2026-03-05T10:00:00Z",
        category_id=gasto,
    )
    # Período actual (14-mar → 13-abr).
    await _make_tx(
        client,
        token,
        account_id,
        amount="2000.00",
        occurred_at="2026-03-20T10:00:00Z",
        category_id=ingreso,
    )

    await _set_cycle(client, token, 14)
    periodo = {"date_from": "2026-03-14T00:00:00Z", "date_to": "2026-04-13T23:59:59Z"}

    aproximado = (
        await client.get("/dashboard/summary", params=periodo, headers=_auth(token))
    ).json()
    exacto = (
        await client.get(
            "/dashboard/summary", params={**periodo, "cycle": "true"}, headers=_auth(token)
        )
    ).json()

    assert Decimal(aproximado["previous_period_expenses"]) == Decimal("700.00")
    assert Decimal(exacto["previous_period_expenses"]) == Decimal("200.00")
    assert Decimal(exacto["previous_period_income"]) == Decimal("1000.00")
    # El período actual no se mueve: `cycle` cambia el COMPARABLE, no el filtro.
    assert Decimal(exacto["income"]) == Decimal(aproximado["income"]) == Decimal("2000.00")


async def test_un_rango_libre_con_el_preset_activo_sigue_comparando_por_ventana(
    client: AsyncClient,
) -> None:
    """La rama del ciclo exige que el rango SEA un ciclo, no sólo que exista el ajuste.

    Con el preset puesto el usuario puede seguir pidiendo un rango libre. Ahí no
    hay «ciclo anterior» que valga: el comparable honesto es la ventana de igual
    longitud, la misma de siempre. Sin esta condición, un rango de 5 días se
    compararía contra un mes entero.
    """
    token, account_id = await _register(client, "cycle-rango-libre@example.com")
    gasto = await _make_category(client, token, name="Compras", kind="expense")
    await _make_tx(
        client,
        token,
        account_id,
        amount="60.00",
        occurred_at="2026-03-08T10:00:00Z",
        category_id=gasto,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="99.00",
        occurred_at="2026-03-18T10:00:00Z",
        category_id=gasto,
    )
    await _set_cycle(client, token, 14)

    # 10-mar → 19-mar (10 días): no es un ciclo. La ventana anterior es 28-feb →
    # 9-mar, que contiene el gasto del 8 de marzo.
    rango = {"date_from": "2026-03-10T00:00:00Z", "date_to": "2026-03-19T23:59:59Z"}
    r = (
        await client.get(
            "/dashboard/summary", params={**rango, "cycle": "true"}, headers=_auth(token)
        )
    ).json()

    assert Decimal(r["expenses"]) == Decimal("99.00")
    assert Decimal(r["previous_period_expenses"]) == Decimal("60.00")


# ─────────────────────────────────────────────────────────────────────
# Bounds de las flechas y chips de períodos.
# ─────────────────────────────────────────────────────────────────────


async def test_los_bounds_y_los_chips_apuntan_al_ciclo_que_contiene_los_datos(
    client: AsyncClient,
) -> None:
    """Una tx del 3-feb con `D = 14` hace navegable el ciclo del 14-ENE, no el del 14-feb.

    Los bounds acotan las flechas ◀▶ y los chips ofrecen los períodos pulsables.
    Si siguieran siendo meses naturales mientras las series son ciclos, el
    navegador aterrizaría en «febrero» —el ciclo del 14-feb, que empieza once
    días DESPUÉS de la única transacción— y pintaría un período vacío. Con el
    ciclo, un ancla fuera de datos ya no es cosmética.
    """
    token, account_id = await _register(client, "cycle-bounds@example.com")
    gasto = await _make_category(client, token, name="Compras", kind="expense")
    await _make_tx(
        client,
        token,
        account_id,
        amount="25.00",
        occurred_at="2026-02-03T10:00:00Z",
        category_id=gasto,
    )
    await _set_cycle(client, token, 14)

    natural = (await client.get("/dashboard/summary", headers=_auth(token))).json()
    assert (natural["available_from"], natural["available_to"]) == ("2026-02", "2026-02")

    ciclo = (
        await client.get("/dashboard/summary", params={"cycle": "true"}, headers=_auth(token))
    ).json()
    assert (ciclo["available_from"], ciclo["available_to"]) == ("2026-01", "2026-01")

    chips = (
        await client.get(
            "/transactions/available-periods", params={"cycle": "true"}, headers=_auth(token)
        )
    ).json()
    assert chips == {"periods": [{"year": 2026, "months": [1]}]}

    chips_categoria = (
        await client.get(
            f"/dashboard/category/{gasto}/available-periods",
            params={"cycle": "true"},
            headers=_auth(token),
        )
    ).json()
    assert chips_categoria == {"periods": [{"year": 2026, "months": [1]}]}


async def test_la_serie_del_drill_down_de_categoria_corta_por_ciclo(client: AsyncClient) -> None:
    """La evolución mensual del drill-down también es de ciclos.

    Es la misma serie de P&G vista por una sola categoría: si el desglose cortara
    por mes natural mientras el navegador corta por ciclo, el usuario vería la
    misma compra en dos barras distintas según por dónde entrara.
    """
    token, account_id = await _register(client, "cycle-drilldown@example.com")
    gasto = await _make_category(client, token, name="Compras", kind="expense")
    await _make_tx(
        client,
        token,
        account_id,
        amount="30.00",
        occurred_at="2026-08-03T10:00:00Z",
        category_id=gasto,
    )
    await _make_tx(
        client,
        token,
        account_id,
        amount="70.00",
        occurred_at="2026-08-20T10:00:00Z",
        category_id=gasto,
    )
    await _set_cycle(client, token, 14)

    natural = (await client.get(f"/dashboard/category/{gasto}", headers=_auth(token))).json()[
        "by_month"
    ]
    ciclo = (
        await client.get(
            f"/dashboard/category/{gasto}", params={"cycle": "true"}, headers=_auth(token)
        )
    ).json()["by_month"]

    assert natural == [{"month": "2026-08", "total": "100.00"}]
    assert ciclo == [
        {"month": "2026-07", "total": "30.00"},
        {"month": "2026-08", "total": "70.00"},
    ]
