"""El comparador de dos análisis (PHASE-44.24.F).

La regla que gobierna el módulo: un cambio puede venir de la EMPRESA o del
MÉTODO, y presentarlos juntos es peor que no comparar. Lo que estos tests atan
es que `comparable=False` VACÍE los cambios de empresa, no que los etiquete.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.modules.investment.analysis.presentation.diff import diff_runs


def _run(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "11111111-1111-1111-1111-111111111111",
        "run_date": datetime(2026, 1, 1, tzinfo=UTC),
        "engine_version": "1.7.0",
        "thresholds_version": "abc",
        "years_covered": [2022, 2023, 2024],
        "scores_detail": {
            "base_ratios": {"metrics": []},
            "forensic": {"metrics": []},
        },
        "evolution": {"metrics": []},
        "dividend_analysis": {"metrics": []},
        "flags": [],
        "verdict": {
            "safety_profile": {"label": "watch", "blocking_reasons": []},
            "dividend_verdict": "healthy",
            "questions": [],
        },
    }
    base.update(overrides)
    return base


def _metric(key: str, year: int, value: str, band: str | None) -> dict[str, Any]:
    return {"key": key, "fiscal_year": year, "value": value, "band": band, "status": "ok"}


def _with_metrics(run: dict[str, Any], *metrics: dict[str, Any]) -> dict[str, Any]:
    run["scores_detail"] = {"base_ratios": {"metrics": list(metrics)}, "forensic": {"metrics": []}}
    return run


# ── La precondición ───────────────────────────────────────────────────


def test_si_cambio_el_motor_no_se_emite_ni_un_cambio_de_empresa() -> None:
    """No es una etiqueta: es que las listas vienen VACÍAS.

    Con el motor distinto, un cambio de banda puede ser el corte y no el
    negocio. Listarlo «con un aviso» invita justo a la lectura equivocada.
    """
    antes = _with_metrics(_run(), _metric("L1", 2024, "1.2", "caution"))
    despues = _with_metrics(_run(engine_version="1.8.0"), _metric("L1", 2024, "1.2", "stressed"))
    diff = diff_runs(antes, despues)
    assert diff.comparable is False
    assert diff.bands == []
    assert diff.scores == []
    assert diff.flags == []
    assert diff.questions == []
    assert diff.method_changes == ["el motor pasó de 1.7.0 a 1.8.0"]
    assert diff.caveat is not None and "no son comparables" in diff.caveat


def test_una_recalibracion_tambien_rompe_la_comparabilidad() -> None:
    diff = diff_runs(_run(), _run(thresholds_version="xyz"))
    assert diff.comparable is False
    assert len(diff.method_changes) == 1
    assert "calibración" in diff.method_changes[0]


def test_cuando_ademas_cambian_los_ejercicios_se_dice_que_las_causas_se_mezclan() -> None:
    """Sin esa frase, el usuario descarta un cierre nuevo que sí explica parte."""
    diff = diff_runs(_run(), _run(engine_version="1.8.0", years_covered=[2022, 2023, 2024, 2025]))
    assert diff.caveat is not None
    assert "se mezclan" in diff.caveat
    assert diff.years_added == [2025]


# ── Cambios de la empresa ─────────────────────────────────────────────


def test_solo_se_listan_las_metricas_que_cruzaron_un_corte() -> None:
    """Un ratio que se mueve del 1,41 al 1,42 no es noticia.

    Listar todo movimiento enterraría los que sí cambiaron de banda, que son la
    única razón de mirar esta pantalla.
    """
    antes = _with_metrics(
        _run(),
        _metric("L1", 2024, "1.41", "healthy"),
        _metric("S2", 2024, "6.0", "healthy"),
    )
    despues = _with_metrics(
        _run(),
        _metric("L1", 2024, "1.42", "healthy"),
        _metric("S2", 2024, "3.0", "stressed"),
    )
    diff = diff_runs(antes, despues)
    assert [b.key for b in diff.bands] == ["S2"]
    assert diff.bands[0].band_before == "healthy"
    assert diff.bands[0].band_after == "stressed"


def test_las_metricas_se_toman_del_ultimo_ejercicio_de_cada_run() -> None:
    """Lo que se compara es el dictamen de entonces con el de ahora.

    Con un cierre nuevo, el ejercicio del dictamen cambia: comparar el mismo año
    en los dos respondería otra pregunta.
    """
    # El orden es DESCENDENTE a propósito: con el ascendente, el diccionario se
    # quedaba con el último iterado —que resultaba ser el correcto— y el test
    # pasaba aunque el filtro por ejercicio no existiera.
    antes = _with_metrics(
        _run(), _metric("L1", 2024, "2.0", "healthy"), _metric("L1", 2023, "0.5", "stressed")
    )
    despues = _with_metrics(
        _run(years_covered=[2023, 2024, 2025]),
        _metric("L1", 2025, "0.4", "stressed"),
        _metric("L1", 2024, "2.0", "healthy"),
    )
    diff = diff_runs(antes, despues)
    assert [b.key for b in diff.bands] == ["L1"]
    assert diff.bands[0].value_before == "2.0"
    assert diff.bands[0].value_after == "0.4"


def test_los_scores_forenses_van_en_su_propio_bloque_y_no_entre_las_bandas() -> None:
    antes = _with_metrics(_run(), _metric("z_score", 2024, "3.1", "healthy"))
    despues = _with_metrics(_run(), _metric("z_score", 2024, "2.4", "caution"))
    diff = diff_runs(antes, despues)
    assert [s.key for s in diff.scores] == ["z_score"]
    assert diff.bands == []


def test_los_ocho_forenses_salen_del_catalogo_del_motor() -> None:
    """Escritos a mano tenían DOS claves inventadas y les faltaban DOS reales.

    El único síntoma habría sido que `F7` y `FZ` aparecieran en el bloque de
    métricas corrientes — un agrupamiento raro que nadie mira dos veces.
    """
    from app.modules.investment.analysis.engine import forensic
    from app.modules.investment.analysis.presentation.diff import _SCORE_KEYS

    assert set(_SCORE_KEYS) == {d.key for d in forensic.METRIC_CATALOG}
    assert len(_SCORE_KEYS) == 8

    # Y se comporta: cada uno de los ocho cae en `scores`, no en `bands`.
    for clave in _SCORE_KEYS:
        antes = _with_metrics(_run(), _metric(clave, 2024, "1", "healthy"))
        despues = _with_metrics(_run(), _metric(clave, 2024, "1", "stressed"))
        resultado = diff_runs(antes, despues)
        assert [s.key for s in resultado.scores] == [clave], clave
        assert resultado.bands == [], clave


def test_una_bandera_nueva_y_una_que_se_apaga_se_distinguen() -> None:
    antes = _run(flags=[{"key": "dilution", "label": "Dilución", "severity": "warning"}])
    despues = _run(flags=[{"key": "accrual_spike", "label": "Accruals", "severity": "alert"}])
    diff = diff_runs(antes, despues)
    porc = {f.key: f.appeared for f in diff.flags}
    assert porc == {"accrual_spike": True, "dilution": False}


def test_una_pregunta_que_pierde_evidencia_sin_cambiar_de_color_se_reporta() -> None:
    """Pasar de «verde auditado» a «verde sin evidencia» no mueve el color.

    Es una pérdida real de respaldo, y sin el eje de evidencia sería invisible —
    exactamente el falso verde que esta familia de fases lleva cerrando.
    """
    pregunta_buena = {
        "key": "accounting",
        "verdict": "healthy",
        "evaluated_count": 5,
        "signals": [{"key": "m_score", "counted": True}],
        "audited": True,
    }
    pregunta_vacia = {
        "key": "accounting",
        "verdict": "healthy",
        "evaluated_count": 0,
        "signals": [{"key": "m_score", "counted": False}],
        "audited": True,
    }
    antes = _run(
        verdict={
            "safety_profile": {"label": "watch", "blocking_reasons": []},
            "dividend_verdict": "healthy",
            "questions": [pregunta_buena],
        }
    )
    despues = _run(
        verdict={
            "safety_profile": {"label": "watch", "blocking_reasons": []},
            "dividend_verdict": "healthy",
            "questions": [pregunta_vacia],
        }
    )
    diff = diff_runs(antes, despues)
    assert len(diff.questions) == 1
    cambio = diff.questions[0]
    assert cambio.verdict_before == cambio.verdict_after == "healthy"
    assert cambio.evidence_before == "evaluated"
    assert cambio.evidence_after == "no-evidence"


def test_sin_ningun_cambio_no_se_inventa_ninguno() -> None:
    diff = diff_runs(_run(), _run())
    assert diff.comparable is True
    assert (diff.bands, diff.scores, diff.flags, diff.questions) == ([], [], [], [])
    assert diff.caveat is None


def test_las_reexpresiones_viajan_con_su_recuento_de_partidas() -> None:
    diff = diff_runs(
        _run(),
        _run(),
        [
            {
                "fiscal_year": 2023,
                "filing_a": "10-K 2023",
                "filing_b": "10-K 2024",
                "divergences": [{"item": "revenue"}, {"item": "ebit"}],
            }
        ],
    )
    assert len(diff.restatements) == 1
    assert diff.restatements[0].item_count == 2


def test_las_metricas_salen_de_las_cuatro_capas_que_las_publican() -> None:
    """No hay lista plana en el payload.

    Olvidar un bloque no falla: deja sus métricas fuera de la comparación como
    si no hubieran cambiado nunca — que es el modo de fallo silencioso de
    `collectRunMetrics` en el frontend.
    """
    antes = _run()
    antes["scores_detail"] = {
        "base_ratios": {"metrics": [_metric("L1", 2024, "1", "healthy")]},
        "forensic": {"metrics": [_metric("accruals", 2024, "0.1", "healthy")]},
    }
    antes["evolution"] = {"metrics": [_metric("E3", 2024, "0.02", "healthy")]}
    antes["dividend_analysis"] = {"metrics": [_metric("D1", 2024, "0.4", "healthy")]}

    despues = _run()
    despues["scores_detail"] = {
        "base_ratios": {"metrics": [_metric("L1", 2024, "1", "stressed")]},
        "forensic": {"metrics": [_metric("accruals", 2024, "0.1", "stressed")]},
    }
    despues["evolution"] = {"metrics": [_metric("E3", 2024, "0.02", "stressed")]}
    despues["dividend_analysis"] = {"metrics": [_metric("D1", 2024, "0.4", "stressed")]}

    diff = diff_runs(antes, despues)
    assert sorted(b.key for b in diff.bands) == ["D1", "E3", "L1"]
    assert [s.key for s in diff.scores] == ["accruals"]
