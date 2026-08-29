"""Tests del análisis end-to-end (PHASE-44.7).

resolve → ingest (adapter falso, hechos sintéticos) → run → veredicto persistido.
El engine puro ya tiene sus 188 tests; aquí se prueba el CABLEADO (builder
BD→engine, serialización a JSONB, persistencia y scoping).
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date
from decimal import Decimal

from httpx import AsyncClient

from app.main import app
from app.modules.investment.analysis.engine.catalog import (
    ALL_DEFAULT_THRESHOLDS,
    ALL_METRIC_KEYS,
)
from app.modules.investment.analysis.engine.metrics import MetricUnit
from app.modules.investment.analysis.engine.types import ThresholdSpec
from app.modules.investment.analysis.engine.version import ENGINE_VERSION
from app.modules.investment.enums import ThresholdDirection
from app.modules.investment.fundamentals.adapters.base import SecurityIdentity, XbrlFact
from app.modules.investment.fundamentals.adapters.factory import get_fundamentals_adapter
from app.modules.investment.fundamentals.canonical import CANONICAL_ITEMS, ItemGroup
from app.modules.investment.thresholds.service import thresholds_hash


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _bal(concept: str, value: object, year: int, accession: str) -> XbrlFact:
    return XbrlFact(
        taxonomy="us-gaap",
        concept=concept,
        value=Decimal(str(value)),
        unit="USD",
        period_end=date(year, 12, 31),
        period_start=None,
        form_type="10-K",
        fiscal_period="FY",
        fiscal_year=year,
        accession=accession,
        filing_date=date(year + 1, 2, 20),
    )


def _flow(concept: str, value: object, year: int, accession: str) -> XbrlFact:
    return XbrlFact(
        taxonomy="us-gaap",
        concept=concept,
        value=Decimal(str(value)),
        unit="USD",
        period_end=date(year, 12, 31),
        period_start=date(year, 1, 1),
        form_type="10-K",
        fiscal_period="FY",
        fiscal_year=year,
        accession=accession,
        filing_date=date(year + 1, 2, 20),
    )


def _year(year: int, accession: str, revenue: int) -> list[XbrlFact]:
    return [
        _bal("Assets", revenue * 2, year, accession),
        _bal("StockholdersEquity", revenue, year, accession),
        _bal("LiabilitiesCurrent", revenue // 4, year, accession),
        _bal("AssetsCurrent", revenue // 2, year, accession),
        _flow("Revenues", revenue, year, accession),
        _flow("OperatingIncomeLoss", int(revenue * 0.4), year, accession),
        _flow("NetIncomeLoss", int(revenue * 0.3), year, accession),
        _flow("NetCashProvidedByUsedInOperatingActivities", int(revenue * 0.35), year, accession),
    ]


_FACTS = _year(2022, "a-22", 24000) + _year(2023, "a-23", 25000) + _year(2024, "a-24", 26000)

_MCD = SecurityIdentity(
    ticker="MCD",
    cik="0000063908",
    name="MCDONALDS CORP",
    sic="5812",
    is_reit=False,
    is_financial=False,
)


class _FakeAdapter:
    async def resolve(self, ticker: str) -> SecurityIdentity:
        return _MCD

    async def fetch_facts(
        self, identity: SecurityIdentity, *, refresh: bool = False
    ) -> tuple[XbrlFact, ...]:
        return tuple(_FACTS)


def _override() -> None:
    app.dependency_overrides[get_fundamentals_adapter] = _FakeAdapter


async def _resolve_and_ingest(client: AsyncClient, token: str) -> str:
    resolved = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )
    security_id = resolved.json()["id"]
    await client.post(
        f"/investment/fundamentals/{security_id}/ingest",
        json={"filings_back": 5},
        headers=_auth(token),
    )
    return security_id


async def test_run_sin_datos_da_409(client: AsyncClient) -> None:
    token = await _register(client, "an1@example.com")
    _override()
    resolved = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "MCD", "exchange": "NYSE"},
        headers=_auth(token),
    )
    security_id = resolved.json()["id"]

    run = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
    )
    assert run.status_code == 409
    assert "ingesta" in run.json()["detail"].lower()


async def test_un_valor_sin_cik_da_422_con_motivo_no_409(client: AsyncClient) -> None:
    """Un 409 dice "falta un paso": lanza la ingesta. Pero para un valor sin CIK la
    ingesta NO puede funcionar nunca —no hay filing en EDGAR—, así que el usuario
    la lanzaba, fallaba y no había forma de entender por qué. 422 + motivo
    (PHASE-44.8 E1).
    """

    class _NoCikAdapter:
        async def resolve(self, ticker: str) -> SecurityIdentity:
            # Un listing no-US: sin CIK. Es lo que producirá la capa externa de la
            # Entrega 5 al adoptar Inditex o Iberdrola para llevarlas en cartera.
            return SecurityIdentity(ticker=ticker, cik="", name="INDUSTRIA DE DISENO TEXTIL")

        async def fetch_facts(
            self, identity: SecurityIdentity, *, refresh: bool = False
        ) -> tuple[XbrlFact, ...]:
            return ()

    token = await _register(client, "an-sin-cik@example.com")
    app.dependency_overrides[get_fundamentals_adapter] = _NoCikAdapter
    resolved = await client.post(
        "/investment/securities/resolve",
        json={"ticker": "ITX"},
        headers=_auth(token),
    )
    security_id = resolved.json()["id"]
    assert resolved.json()["analysis_available"] is False

    run = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
    )

    assert run.status_code == 422, run.text
    detalle = run.json()["detail"]
    assert "ITX" in detalle
    assert "cartera" in detalle


async def test_run_produce_veredicto(client: AsyncClient) -> None:
    token = await _register(client, "an2@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)

    run = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
    )
    assert run.status_code == 200, run.text
    data = run.json()

    assert data["engine_version"]
    assert len(data["thresholds_version"]) == 64
    assert data["years_covered"] == [2022, 2023, 2024]
    # confianza ∈ [0,1]
    assert Decimal("0") <= Decimal(data["confidence"]) <= Decimal("1")
    # las 4 preguntas de la síntesis salen con su semáforo
    questions = data["verdict"]["questions"]
    assert {q["key"] for q in questions} == {"accounting", "cash", "dividend", "resilience"}
    assert all(q["verdict"] in {"healthy", "caution", "stressed"} for q in questions)
    # el desglose viaja completo
    assert "forensic" in data["scores_detail"]
    assert "base_ratios" in data["scores_detail"]
    assert data["dividend_verdict"] in {"healthy", "caution", "stressed", "not_applicable"}


async def test_run_con_stress_params(client: AsyncClient) -> None:
    token = await _register(client, "an3@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)

    run = await client.post(
        f"/investment/analysis/{security_id}/run",
        json={"stress_params": {"revenue_drops": ["0.15", "0.25"], "pct_variable_debt": "0.5"}},
        headers=_auth(token),
    )
    assert run.status_code == 200, run.text
    assert "stress" in run.json()["verdict"]


async def test_historico_y_scoping(client: AsyncClient) -> None:
    token_a = await _register(client, "an4a@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token_a)
    created = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token_a)
    )
    run_id = created.json()["id"]

    history = await client.get(f"/investment/analysis/{security_id}/runs", headers=_auth(token_a))
    assert [r["id"] for r in history.json()["items"]] == [run_id]

    detail = await client.get(f"/investment/analysis/runs/{run_id}", headers=_auth(token_a))
    assert detail.status_code == 200

    token_b = await _register(client, "an4b@example.com")
    theirs = await client.get(f"/investment/analysis/runs/{run_id}", headers=_auth(token_b))
    assert theirs.status_code == 404


# ── PHASE-44.9 — el contrato que hace explicable el veredicto ─────────


async def test_catalogo_de_metricas_sirve_todas_con_su_unidad(client: AsyncClient) -> None:
    """Sin este endpoint el cliente escribía las etiquetas a mano, y tres
    acabaron mintiendo sobre su propio número (F5, F6, D8).

    El recuento no se fija a un literal: se compara contra el catálogo del
    engine, que es la fuente única. Así añadir una métrica no obliga a tocar el
    test — sólo a catalogarla."""
    token = await _register(client, "cat1@example.com")
    r = await client.get("/investment/analysis/metrics", headers=_auth(token))
    assert r.status_code == 200, r.text
    data = r.json()

    assert len(data["items"]) == len(ALL_METRIC_KEYS)
    assert {m["key"] for m in data["items"]} == set(ALL_METRIC_KEYS), (
        "el catálogo servido debe ser EXACTAMENTE el que calcula el engine: "
        "si alguien añade una métrica sin catalogarla, esto falla"
    )
    assert data["engine_version"] == ENGINE_VERSION

    unidades = {u.value for u in MetricUnit}
    for metric in data["items"]:
        assert metric["label"], metric["key"]
        assert metric["family"], metric["key"]
        assert metric["unit"] in unidades, metric["key"]

    con_banda = [m for m in data["items"] if m["direction"] is not None]
    assert len(con_banda) == len(ALL_DEFAULT_THRESHOLDS)


async def test_el_catalogo_desmiente_las_tres_etiquetas_que_mentian(client: AsyncClient) -> None:
    """Regresión de PHASE-44.9: la web rotulaba F5 como «deuda emergente», F6
    como «dilución» y D8 como «rentabilidad por dividendo». Ninguna lo es — y
    D8 encima prometía algo que necesita precio de mercado, que el run no tiene.
    """
    token = await _register(client, "cat2@example.com")
    r = await client.get("/investment/analysis/metrics", headers=_auth(token))
    por_clave = {m["key"]: m["label"] for m in r.json()["items"]}

    assert por_clave["F5"] == "Riesgo de fondo de comercio"
    assert por_clave["F6"] == "Anomalía del circulante"
    assert por_clave["D8"] == "Margen de seguridad"


async def test_el_catalogo_de_ayuda_sirve_las_fichas_de_los_scores(client: AsyncClient) -> None:
    """Los ocho scores forenses con su ficha y sus variables (PHASE-44.24.A).

    Sin este endpoint, la tarjeta de desglose imprimía la CLAVE del motor y el
    usuario leía `DSRI` y `P4_cfo_supera_beneficio` en pantalla — el mismo
    defecto que PHASE-44.9 cerró para las señales del veredicto.

    Los recuentos NO se fijan a literales: se comparan contra el catálogo del
    engine, que es la fuente única, para que añadir un score no obligue a tocar
    el test — sólo a escribir su ficha.
    """
    from app.modules.investment.analysis.engine.forensic import METRIC_KEYS as FORENSIC_KEYS

    token = await _register(client, "help1@example.com")
    r = await client.get("/investment/analysis/help", headers=_auth(token))
    assert r.status_code == 200, r.text
    data = r.json()

    assert {s["key"] for s in data["scores"]} == set(FORENSIC_KEYS)
    assert data["engine_version"] == ENGINE_VERSION

    por_clave = {s["key"]: s for s in data["scores"]}
    for score in data["scores"]:
        for campo in ("what", "why", "reading"):
            assert score[campo].strip(), f"{score['key']}.{campo} vacío"

    # Los cuatro que sí publican desglose lo traen con etiqueta legible; los
    # otros cuatro llegan con la lista VACÍA, que es el dato: son un ratio
    # único, no un agregado, y la pantalla lo dice en vez de dejar al usuario
    # buscando un desplegable que no existe.
    assert len(por_clave["m_score"]["components"]) == 8
    assert len(por_clave["z_score"]["components"]) == 4
    assert len(por_clave["f_score"]["components"]) == 9
    assert len(por_clave["F7"]["components"]) == 6
    for sin_desglose in ("accruals", "F5", "F6", "FZ"):
        assert por_clave[sin_desglose]["components"] == []

    etiquetas = {c["key"]: c["label"] for c in por_clave["m_score"]["components"]}
    assert "DSRI" in etiquetas, "la clave sigue siendo la del motor, para poder cruzarla"
    assert etiquetas["DSRI"] != "DSRI", "la etiqueta NO puede ser la clave cruda"
    assert "cobros" in etiquetas["DSRI"].lower()

    # Las banderas, con el campo que las distingue de las demás fichas: dónde
    # comprobarlas. Sin él el usuario sabe QUÉ ha saltado y no qué hacer con ello.
    from app.modules.investment.analysis.engine.flag_catalog import FLAG_LABELS

    assert {f["key"] for f in data["flags"]} == set(FLAG_LABELS)
    for bandera in data["flags"]:
        assert bandera["label"] == FLAG_LABELS[bandera["key"]], "la etiqueta tiene una sola fuente"
        for campo in ("what", "why", "reading", "how_to_verify"):
            assert bandera[campo].strip(), f"{bandera['key']}.{campo} vacío"


async def test_catalogo_de_partidas_sirve_las_49_agrupadas(client: AsyncClient) -> None:
    token = await _register(client, "cat3@example.com")
    r = await client.get("/investment/fundamentals/items", headers=_auth(token))
    assert r.status_code == 200, r.text
    items = r.json()["items"]

    assert len(items) == len(CANONICAL_ITEMS)
    assert {i["key"] for i in items} == set(CANONICAL_ITEMS)
    assert all(i["label"] for i in items)
    grupos = {g.value for g in ItemGroup}
    assert all(i["group"] in grupos for i in items)
    por_estado = Counter(i["statement"] for i in items)
    assert por_estado == {"balance": 23, "income": 16, "cashflow": 10}


async def test_el_run_guarda_los_umbrales_efectivos_y_cuadran_con_su_hash(
    client: AsyncClient,
) -> None:
    """`thresholds_version` DETECTA que dos runs se midieron distinto; sólo
    `thresholds_used` permite reconstruir con qué cortes. El seed muta las filas
    in situ y el hash es irreversible, así que sin esto un run pasado no se
    puede explicar."""
    token = await _register(client, "thr1@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)
    run = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
    )
    assert run.status_code == 200, run.text
    used = run.json()["thresholds_used"]

    assert set(used) == set(
        ALL_DEFAULT_THRESHOLDS
    ), "debe traer una entrada por cada métrica con banda del juego cargado"
    rehidratados = {
        key: ThresholdSpec(
            metric_key=spec["metric_key"],
            direction=ThresholdDirection(spec["direction"]),
            low_alarm=None if spec["low_alarm"] is None else Decimal(spec["low_alarm"]),
            low_ok=None if spec["low_ok"] is None else Decimal(spec["low_ok"]),
            high_ok=None if spec["high_ok"] is None else Decimal(spec["high_ok"]),
            high_alarm=None if spec["high_alarm"] is None else Decimal(spec["high_alarm"]),
            model_variant=spec["model_variant"],
            applies=spec["applies"],
        )
        for key, spec in used.items()
    }
    assert (
        thresholds_hash(rehidratados) == run.json()["thresholds_version"]
    ), "ida y vuelta: lo guardado tiene que volver a hashear a la versión del run"


async def test_las_señales_del_veredicto_viajan_con_su_valor_y_su_banda(
    client: AsyncClient,
) -> None:
    """El requisito de la pantalla: poder decir POR QUÉ. Antes cada pregunta
    sólo publicaba nombres sueltos, y 8 de ellos eran la clave en crudo."""
    token = await _register(client, "sig1@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)
    run = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
    )
    questions = run.json()["verdict"]["questions"]

    for question in questions:
        assert question["signals"], question["key"]
        assert question["evaluated_count"] + question["unavailable_count"] == len(
            question["signals"]
        )
        for signal in question["signals"]:
            assert signal["kind"] in {"metric", "flag", "derived"}
            assert "_" not in signal["label"], f"{signal['key']} viaja como clave cruda"
            if not signal["counted"]:
                assert signal["reason"], f"{signal['key']} no cuenta y no dice por qué"


async def test_runs_latest_devuelve_lo_mismo_que_el_run_por_id(client: AsyncClient) -> None:
    token = await _register(client, "last1@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)

    vacio = await client.get(
        f"/investment/analysis/{security_id}/runs/latest", headers=_auth(token)
    )
    assert vacio.status_code == 404

    created = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
    )
    run_id = created.json()["id"]

    latest = await client.get(
        f"/investment/analysis/{security_id}/runs/latest", headers=_auth(token)
    )
    por_id = await client.get(f"/investment/analysis/runs/{run_id}", headers=_auth(token))
    assert latest.status_code == 200
    assert latest.json() == por_id.json(), "misma forma exacta, para que la pantalla no bifurque"

    otro = await _register(client, "last2@example.com")
    ajeno = await client.get(f"/investment/analysis/{security_id}/runs/latest", headers=_auth(otro))
    assert ajeno.status_code == 404, "los runs son de quien los lanzó"


async def test_el_run_llega_con_su_capa_de_lectura(client: AsyncClient) -> None:
    """PHASE-44.24.C — distancia, orden y procedencia, calculados al SERVIR.

    Sin este test los doce anteriores seguirían en verde con `report` en `None`:
    el campo es opcional para que un cliente viejo no se rompa, así que su
    ausencia no falla por sí sola. Ése es exactamente el verde que no prueba
    nada.
    """
    token = await _register(client, "rep1@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)
    run = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
    )
    assert run.status_code == 200, run.text
    report = run.json()["report"]
    assert report is not None, "el run se sirve sin su capa de lectura"

    # El perfil lo emite el SERVIDOR, con lo que lo determina: componerlo en la
    # pantalla con `security.sector` miente en toda entidad financiera
    # clasificada en otro sector.
    perfil = report["threshold_profile"]
    assert perfil["effective"] and perfil["sector"]
    assert "is_financial" in perfil and "is_reit" in perfil

    preguntas = {q["key"]: q for q in report["questions"]}
    assert preguntas, "la capa no trae ninguna pregunta"

    # El orden es total y empieza en cero.
    #
    # OJO: esto SOLO comprueba que los rangos son consecutivos, y eso es cierto
    # por construcción de `enumerate` aunque nadie ordene nada — lo destapó una
    # sonda que quitó el `sort` y dejó el test en verde. Lo que prueba el orden
    # es la comprobación de abajo, sobre las bandas.
    for pregunta in preguntas.values():
        rangos = [s["severity_rank"] for s in pregunta["signals"]]
        assert rangos == list(range(len(rangos))), f"{pregunta['key']}: los rangos no son densos"

    # Lo que SÍ prueba que están ordenadas: ninguna señal puede ir por delante
    # de otra de banda peor. Se cruza con el veredicto persistido, que es donde
    # vive la banda de cada señal.
    bandas_por_pregunta = {
        q["key"]: {s["key"]: s.get("band") for s in (q.get("signals") or [])}
        for q in run.json()["verdict"]["questions"]
    }
    peso = {"stressed": 0, "caution": 1, "healthy": 2, None: 3}
    desordenadas = []
    for clave, pregunta in preguntas.items():
        bandas = bandas_por_pregunta.get(clave, {})
        secuencia = [peso[bandas.get(s["key"])] for s in pregunta["signals"]]
        if secuencia != sorted(secuencia):
            desordenadas.append((clave, secuencia))
    assert desordenadas == [], f"señales fuera de orden de severidad: {desordenadas}"

    # Y alguna señal tiene que traer distancia de verdad: si ninguna la trajera,
    # el barrido de arriba pasaría con el cálculo entero desconectado.
    con_distancia = [
        s
        for pregunta in preguntas.values()
        for s in pregunta["signals"]
        if s["distance"] is not None
    ]
    assert con_distancia, "ninguna señal trae distancia: el cálculo no está conectado"
    assert all(s["threshold_origin"] for s in con_distancia)


async def test_un_run_recien_ejecutado_declara_la_procedencia_que_registro(
    client: AsyncClient,
) -> None:
    """Con el motor ≥ 1.7.0 la procedencia se LEE del run, no se infiere.

    Y ninguna señal con vara aplicable puede salir como `not_recorded`: eso
    significaría que el run no guardó el corte con el que se midió.
    """
    token = await _register(client, "rep2@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)
    run = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
    )
    report = run.json()["report"]
    used = run.json()["thresholds_used"]

    origenes = {
        s["threshold_origin"] for q in report["questions"] for s in q["signals"] if s["key"] in used
    }
    assert origenes, "ninguna señal cruza con los umbrales guardados"
    assert "not_recorded" not in origenes, "un run nuevo no puede tener cortes sin registrar"
    assert "earlier_calibration" not in origenes, (
        "un run recién ejecutado no puede venir de una calibración anterior: "
        "si sale esto, la procedencia se está DERIVANDO en vez de leerse"
    )


# ── El comparador de runs (PHASE-44.24.F) ─────────────────────────────


async def test_comparar_sin_dos_analisis_es_un_404_con_motivo(client: AsyncClient) -> None:
    token = await _register(client, "cmp0@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)

    vacio = await client.get(
        f"/investment/analysis/{security_id}/runs/compare", headers=_auth(token)
    )
    assert vacio.status_code == 404
    assert "dos análisis" in vacio.json()["detail"]

    await client.post(f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token))
    uno = await client.get(f"/investment/analysis/{security_id}/runs/compare", headers=_auth(token))
    assert uno.status_code == 404, "con UN análisis tampoco hay comparación"


async def test_comparar_los_dos_ultimos_es_el_caso_por_defecto(client: AsyncClient) -> None:
    """Dos análisis del mismo motor y los mismos datos: nada se ha movido.

    Que salgan CERO cambios no es un test trivial: es la prueba de que el diff
    no inventa diferencias por ejecutarse dos veces (el run es reproducible).
    """
    token = await _register(client, "cmp1@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)
    primero = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
    )
    segundo = await client.post(
        f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
    )

    diff = await client.get(
        f"/investment/analysis/{security_id}/runs/compare", headers=_auth(token)
    )
    assert diff.status_code == 200
    payload = diff.json()
    assert payload["comparable"] is True
    assert payload["base_id"] == primero.json()["id"]
    assert payload["target_id"] == segundo.json()["id"]
    assert payload["method_changes"] == []
    assert (payload["bands"], payload["scores"], payload["flags"], payload["questions"]) == (
        [],
        [],
        [],
        [],
    )


async def test_elegir_solo_el_target_compara_contra_su_anterior(client: AsyncClient) -> None:
    """La selección parcial es lo que manda móvil, y web mientras no elijas base.

    La primera versión sólo distinguía «los dos ids» de «ninguno», así que esto
    caía a «los dos últimos» y devolvía la comparación de OTROS dos análisis con
    sus fechas en la cabecera — un resultado plausible y equivocado.
    """
    token = await _register(client, "cmp2@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)
    ids = [
        (
            await client.post(
                f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
            )
        ).json()["id"]
        for _ in range(3)
    ]

    diff = await client.get(
        f"/investment/analysis/{security_id}/runs/compare?target={ids[1]}", headers=_auth(token)
    )
    assert diff.status_code == 200
    assert diff.json()["target_id"] == ids[1]
    assert diff.json()["base_id"] == ids[0], "el anterior, no el último"

    mas_antiguo = await client.get(
        f"/investment/analysis/{security_id}/runs/compare?target={ids[0]}", headers=_auth(token)
    )
    assert mas_antiguo.status_code == 404, "el más antiguo no tiene contra qué compararse"
    assert "más antiguo" in mas_antiguo.json()["detail"]


async def test_el_orden_de_los_ids_no_invierte_la_comparacion(client: AsyncClient) -> None:
    """`base` es SIEMPRE el más antiguo, elija el usuario el orden que elija.

    Un diff al revés diría que un score «mejoró» cuando empeoró — el peor modo
    de fallo posible en una pantalla que existe para responder «¿va peor?».
    """
    token = await _register(client, "cmp3@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)
    ids = [
        (
            await client.post(
                f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token)
            )
        ).json()["id"]
        for _ in range(2)
    ]

    al_reves = await client.get(
        f"/investment/analysis/{security_id}/runs/compare?base={ids[1]}&target={ids[0]}",
        headers=_auth(token),
    )
    assert al_reves.status_code == 200
    assert al_reves.json()["base_id"] == ids[0]
    assert al_reves.json()["target_id"] == ids[1]


async def test_un_run_de_otro_usuario_no_se_puede_comparar(client: AsyncClient) -> None:
    token = await _register(client, "cmp4@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)
    ajeno = (
        await client.post(f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token))
    ).json()["id"]
    await client.post(f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token))

    otro = await _register(client, "cmp5@example.com")
    fuera = await client.get(
        f"/investment/analysis/{security_id}/runs/compare?target={ajeno}", headers=_auth(otro)
    )
    assert fuera.status_code == 404, "los runs son de quien los lanzó"


async def test_el_resumen_del_historico_trae_thresholds_version(client: AsyncClient) -> None:
    """Sin él, el selector no puede decir si dos análisis son comparables sin
    pedirlos enteros — y una etiqueta que no se puede calcular no se pinta."""
    token = await _register(client, "cmp6@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)
    await client.post(f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token))

    listado = await client.get(f"/investment/analysis/{security_id}/runs", headers=_auth(token))
    assert listado.status_code == 200
    item = listado.json()["items"][0]
    assert item["thresholds_version"], "el resumen debe traer la calibración con la que se midió"


async def test_comparar_un_analisis_consigo_mismo_es_un_404(client: AsyncClient) -> None:
    """Un diff vacío se presenta como «nada se ha movido», que es cierto y engañoso.

    La guarda existía SÓLO en la rama de `base` suelto: pedir el mismo id como
    base y como target caía en la otra rama y devolvía la comparación vacía.
    """
    token = await _register(client, "cmp7@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)
    uno = (
        await client.post(f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token))
    ).json()["id"]
    await client.post(f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token))

    # Las DOS formas de pedirlo: con los dos ids, y con `base` suelto apuntando
    # al último (que es el `target` por defecto).
    ambos = await client.get(
        f"/investment/analysis/{security_id}/runs/compare?base={uno}&target={uno}",
        headers=_auth(token),
    )
    assert ambos.status_code == 404
    assert "consigo mismo" in ambos.json()["detail"]

    ultimo = (
        await client.get(f"/investment/analysis/{security_id}/runs", headers=_auth(token))
    ).json()["items"][0]["id"]
    suelto = await client.get(
        f"/investment/analysis/{security_id}/runs/compare?base={ultimo}", headers=_auth(token)
    )
    assert suelto.status_code == 404
    assert "consigo mismo" in suelto.json()["detail"]


async def test_cada_motivo_de_404_es_distinguible_por_su_detail(client: AsyncClient) -> None:
    """La pantalla los pinta tal cual; si el servidor no los distingue, no puede.

    Antes la UI colapsaba los cuatro en «hace falta más de un análisis», que en
    tres de los cuatro casos es FALSO.
    """
    token = await _register(client, "cmp8@example.com")
    _override()
    security_id = await _resolve_and_ingest(client, token)
    primero = (
        await client.post(f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token))
    ).json()["id"]

    solo_uno = await client.get(
        f"/investment/analysis/{security_id}/runs/compare", headers=_auth(token)
    )
    await client.post(f"/investment/analysis/{security_id}/run", json={}, headers=_auth(token))
    mas_antiguo = await client.get(
        f"/investment/analysis/{security_id}/runs/compare?target={primero}", headers=_auth(token)
    )
    ajeno = await client.get(
        f"/investment/analysis/{security_id}/runs/compare?target={uuid.uuid4()}",
        headers=_auth(token),
    )
    consigo = await client.get(
        f"/investment/analysis/{security_id}/runs/compare?base={primero}&target={primero}",
        headers=_auth(token),
    )

    motivos = [
        solo_uno.json()["detail"],
        mas_antiguo.json()["detail"],
        ajeno.json()["detail"],
        consigo.json()["detail"],
    ]
    assert all(r.status_code == 404 for r in (solo_uno, mas_antiguo, ajeno, consigo))
    assert len(set(motivos)) == 4, f"dos motivos indistinguibles: {motivos}"
