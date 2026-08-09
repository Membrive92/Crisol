"""Ranking del buscador de valores (PHASE-44.8 E2) — capa PURA.

Sin BD, sin red y sin la librería: las filas se construyen a mano con la forma
EXACTA que devuelve el parquet de la SEC, sondeada el 2026-08-07. Los casos no
son inventados; cada uno viene de una consulta que se hizo contra el fichero real
y cuyo resultado está anotado en el propio test.
"""

from __future__ import annotations

from app.modules.investment.catalog.ranking import (
    IndexRow,
    collapse_by_cik,
    fuzzy_token_candidates,
    missing_issuer_notice,
    name_specificity,
    rank_rows,
    relevance_score,
    tokenize,
)


def _row(cik: int, ticker: str, venue: str, name: str) -> IndexRow:
    return IndexRow(
        cik=cik,
        ticker=ticker,
        venue=venue,
        name=name,
        name_upper=name.upper(),
        tokens=tokenize(name),
    )


# Filas reales del fichero de la SEC (cik/ticker/plaza/nombre tal cual).
MCD = _row(63908, "MCD", "NYSE", "MCDONALDS CORP")
KO = _row(21344, "KO", "NYSE", "COCA COLA CO")
COKE = _row(317540, "COKE", "NASDAQ", "Coca-Cola Consolidated, Inc.")
SAN = _row(891478, "SAN", "NYSE", "Banco Santander, S.A.")
BCDRF = _row(891478, "BCDRF", "OTC", "Banco Santander, S.A.")  # MISMO cik que SAN
SNTUF = _row(1087711, "SNTUF", "OTC", "Santander UK plc")
STNDF = _row(1087711, "STNDF", "OTC", "Santander UK plc")  # MISMO cik que SNTUF
MC = _row(1596967, "MC", "NYSE", "Moelis & Co")
ADTX = _row(1726711, "ADTX", "NASDAQ", "Aditxt, Inc.")
SPY = _row(884394, "SPY", "NYSE", "SPDR S&P 500 ETF TRUST")
# Las dos filiales que empataban con la matriz y la adelantaban por orden
# alfabético del ticker, y el par Johnson que destapó el mismo defecto.
BSAC = _row(1027552, "BSAC", "NYSE", "BANCO SANTANDER CHILE")
BSBR = _row(1471055, "BSBR", "NYSE", "Banco Santander (Brasil) S.A.")
JNJ = _row(200406, "JNJ", "NYSE", "JOHNSON & JOHNSON")
JCI = _row(833444, "JCI", "NYSE", "Johnson Controls International plc")

ALL = [MCD, KO, COKE, SAN, BCDRF, SNTUF, STNDF, MC, ADTX, SPY]


class TestTokenize:
    def test_parte_por_los_separadores_de_los_nombres_reales(self) -> None:
        assert tokenize("Banco Santander, S.A.") == ("BANCO", "SANTANDER", "S", "A")
        assert tokenize("Moelis & Co") == ("MOELIS", "CO")

    def test_el_guion_conserva_la_palabra_entera_y_sus_partes(self) -> None:
        """`COCA` debe encontrar `Coca-Cola` igual que `COCA-COLA`."""
        tokens = tokenize("Coca-Cola Consolidated, Inc.")
        assert "COCA-COLA" in tokens
        assert "COCA" in tokens
        assert "COLA" in tokens


class TestRelevancia:
    def test_el_ticker_exacto_gana_a_todo(self) -> None:
        assert relevance_score(MC, "MC") > relevance_score(MCD, "MC")

    def test_una_consulta_corta_no_dispara_la_subcadena_de_nombre(self) -> None:
        """`ITX` es subcadena de `ADITXT`: con `LIKE %itx%` quien busca Inditex
        recibe `ADTX · Aditxt, Inc.`, que no tiene ninguna relación."""
        assert "ITX" in ADTX.name_upper.replace("-", "")  # la trampa existe
        assert relevance_score(ADTX, "ITX") == 0

    def test_una_consulta_larga_si_la_dispara(self) -> None:
        """Con 4+ caracteres la subcadena deja de ser ruido y empieza a ser útil:
        encuentra por el MEDIO de un nombre, que es donde falla el prefijo."""
        assert relevance_score(MCD, "DONALDS") > 0
        assert relevance_score(SPY, "S&P 500") > 0
        # ...y con 3 sigue sin dispararse, aunque la subcadena esté ahí.
        assert "ETF" in SPY.name_upper
        assert relevance_score(SPY, "TF ") == 0

    def test_la_plaza_desempata_dentro_del_tramo_pero_nunca_salta_de_tramo(self) -> None:
        """Que una coincidencia exacta de ticker en OTC gane a un prefijo de
        nombre en NYSE es deliberado; al revés, la plaza decidiría la
        relevancia."""
        assert relevance_score(BCDRF, "BCDRF") > relevance_score(SAN, "BANCO")
        # ...y entre iguales, sí manda la plaza.
        assert relevance_score(SAN, "SANTANDER") > relevance_score(BCDRF, "SANTANDER")


class TestColapsoPorCik:
    def test_un_emisor_una_fila_con_la_plaza_mas_prominente(self) -> None:
        """`SAN`/NYSE y `BCDRF`/OTC son el MISMO cik 891478."""
        out = collapse_by_cik([(BCDRF, 800), (SAN, 800)])
        assert len(out) == 1
        assert out[0][0].ticker == "SAN"

    def test_dos_lineas_otc_del_mismo_emisor_colapsan(self) -> None:
        """Santander UK sale dos veces en el fichero: `SNTUF` y `STNDF`."""
        out = collapse_by_cik([(SNTUF, 800), (STNDF, 800)])
        assert len(out) == 1

    def test_conserva_la_mejor_puntuacion_aunque_muestre_la_otra_fila(self) -> None:
        """Si tecleas el ticker OTC exacto, ese emisor debe seguir arriba —
        aunque se te muestre su cotización principal."""
        out = collapse_by_cik([(SAN, 100), (BCDRF, 1000)])
        assert len(out) == 1
        row, score = out[0]
        assert row.ticker == "SAN", "se muestra la principal"
        assert score == 1000, "pero puntúa como la coincidencia exacta que fue"

    def test_emisores_distintos_no_se_colapsan(self) -> None:
        out = collapse_by_cik([(SAN, 800), (SNTUF, 800)])
        assert len(out) == 2


class TestRanking:
    def test_coca_devuelve_ko_primero(self) -> None:
        """Criterio de aceptación del plan."""
        assert rank_rows(ALL, "coca", limit=5)[0].ticker == "KO"

    def test_santander_no_devuelve_duplicados(self) -> None:
        """8 filas en el fichero, 5 emisores. Sin colapsar, 3 son ruido."""
        out = rank_rows(ALL, "santander", limit=10)
        tickers = [r.ticker for r in out]
        assert "SAN" in tickers
        assert "BCDRF" not in tickers, "la línea OTC del mismo cik"
        assert len({r.cik for r in out}) == len(out), "un emisor, una fila"

    def test_santander_devuelve_la_matriz_primero(self) -> None:
        """Los tres empatan a puntuación (token exacto, misma plaza) y antes
        desempataba el ticker alfabéticamente, así que la matriz salía TERCERA
        detrás de sus dos filiales (`BSAC` < `BSBR` < `SAN`). Quien busca un
        emisor por su nombre quiere el que se llama así, no el que se llama así
        **y además** Chile."""
        out = rank_rows([*ALL, BSAC, BSBR], "santander", limit=5)
        assert out[0].ticker == "SAN"

    def test_johnson_devuelve_jnj_primero(self) -> None:
        """El mismo desempate, en un caso que no se buscaba: `JOHNSON &
        JOHNSON` (dos tokens útiles) gana a `Johnson Controls International`
        (tres)."""
        out = rank_rows([JNJ, JCI], "johnson", limit=5)
        assert out[0].ticker == "JNJ"

    def test_la_forma_juridica_no_cuenta_como_calificativo(self) -> None:
        """`S.A.`, `plc` o `Inc` son forma jurídica, no parte del nombre: si
        contaran, `Banco Santander, S.A.` (4 tokens brutos) perdería contra
        `BANCO SANTANDER CHILE` (3) — justo al revés de lo que se quiere."""
        assert name_specificity(SAN) < name_specificity(BSAC)

    def test_itx_no_devuelve_aditxt(self) -> None:
        assert [r.ticker for r in rank_rows(ALL, "itx", limit=5)] == []

    def test_mc_devuelve_moelis_primero(self) -> None:
        assert rank_rows(ALL, "MC", limit=5)[0].ticker == "MC"

    def test_limite_respetado(self) -> None:
        assert len(rank_rows(ALL, "c", limit=2)) <= 2


class TestFuzzy:
    VOCAB = ("MCDONALDS", "COCA-COLA", "SANTANDER", "STANDARD", "MOELIS")

    def test_corrige_la_falta_de_ortografia_que_motivo_la_deuda(self) -> None:
        """La SEC escribe `MCDONALDS` sin apóstrofo, así que `Macdonald` no casa
        por subcadena por mucho que sea lo que teclea la gente."""
        assert "MCDONALDS" in fuzzy_token_candidates(self.VOCAB, "MACDONALD")

    def test_no_confunde_santander_con_standard(self) -> None:
        """El falso positivo que aparece en cuanto se baja el umbral."""
        assert "STANDARD" not in fuzzy_token_candidates(self.VOCAB, "SANTANDR")

    def test_no_corrige_consultas_cortas(self) -> None:
        """Adivinar la ortografía de algo de 3 letras es inventar."""
        assert fuzzy_token_candidates(self.VOCAB, "MCD") == ()


class TestAvisos:
    def test_explica_la_frontera_suiza(self) -> None:
        """Un desplegable vacío se lee como «esa empresa no existe». Nestlé
        existe: lo que pasa es que SIX no reporta a FIRDS (ADR-0010 §5)."""
        notice = missing_issuer_notice("NESN")
        assert notice is not None
        assert "Nestlé" in notice and "SIX" in notice

    def test_explica_por_que_un_etf_abierto_no_sale(self) -> None:
        notice = missing_issuer_notice("VOO")
        assert notice is not None and "SPY" in notice

    def test_no_avisa_de_lo_que_si_existe(self) -> None:
        """Avisar de «no existe» sobre lo que devuelve resultados sería mentir
        en la otra dirección. `SAN`, `MC`, `SAP`… están en el índice SEC, y
        desde PHASE-44.14 `ITX`, `IBE` y `BMW` salen del directorio FIRDS —
        por eso dejaron de tener alias."""
        for present in ("SAN", "MC", "SAP", "ASML", "AIR", "OR", "SPY", "QQQ", "ITX", "IBE", "BMW"):
            assert missing_issuer_notice(present) is None, present
