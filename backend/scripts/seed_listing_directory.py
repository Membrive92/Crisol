"""Seed del directorio oficial de valores UE/UK (PHASE-44.14, ADR-0010).

Descarga los últimos FULINS de equity de ESMA (UE/EEA) y de la FCA (UK), los
parsea en streaming y sincroniza `listing_directory`. Idempotente: re-ejecutarlo
sin que los registros hayan cambiado escribe cero filas. El refresh es esto
mismo — manual, trimestral o a demanda; sin cron (local-first).

Uso:
    python -m scripts.seed_listing_directory              # descarga y siembra
    python -m scripts.seed_listing_directory --dry-run    # informa, no escribe
    python -m scripts.seed_listing_directory --from-dir C:/ruta  # ZIPs locales

Forma de las APIs (verificada golpeándolas, 2026-08-07):

- ESMA — Solr: `registers.esma.europa.eu/solr/esma_registers_firds_files/select`
  con `q=*`, `fq=file_type:FULINS AND publication_date:[NOW-9DAYS TO NOW]`.
  Responde `response.docs[]` con `file_name` y `download_link`. Los full files
  salen los sábados; `FULINS_E_YYYYMMDD_NNofMM.zip` es equity, particionado.
- FCA — Elasticsearch: `api.data.fca.org.uk/fca_data_firds_files` con
  `q=((file_type:FULINS) AND (publication_date:[F1 TO F2]))`. **No** entiende
  `NOW-9DAYS`: fechas explícitas. Responde `hits.hits[]._source` con los mismos
  campos.

Los ficheros del 2026-08-01 miden 366+140 MB (ESMA) y 809 MB (FCA)
descomprimidos — de ahí el parseo streaming de `catalog/firds.py` y el timeout
generoso: aquí no espera ningún usuario.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
import zipfile
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Import por EFECTO LATERAL: registra todos los modelos en el metadata (FKs de
# tablas ajenas incluidas). La lección del backfill de FX ([PHASE-44.13]): el
# camino que escribe necesita el metadata completo, y el dry-run no lo delata.
import app.main  # noqa: F401
from app.core.config import settings
from app.modules.investment.catalog import repository as repo
from app.modules.investment.catalog.firds import (
    FirdsRecord,
    collapse_records,
    parse_fulins,
    partition_for_source,
)

ESMA_SOLR = "https://registers.esma.europa.eu/solr/esma_registers_firds_files/select"
FCA_API = "https://api.data.fca.org.uk/fca_data_firds_files"
_DOWNLOAD_TIMEOUT = 600.0
_EQUITY_MARKER = "FULINS_E_"


def _list_esma_files(client: httpx.Client) -> list[tuple[str, str]]:
    """`(file_name, url)` de los FULINS de equity más recientes de ESMA."""
    r = client.get(
        ESMA_SOLR,
        params={
            "q": "*",
            "fq": "file_type:FULINS AND publication_date:[NOW-9DAYS TO NOW]",
            "wt": "json",
            "rows": 200,
        },
    )
    r.raise_for_status()
    docs = r.json().get("response", {}).get("docs", [])
    files = [
        (d["file_name"], d["download_link"])
        for d in docs
        if d.get("file_name", "").startswith(_EQUITY_MARKER)
    ]
    return _latest_set(files)


def _list_fca_files(client: httpx.Client) -> list[tuple[str, str]]:
    """Idem para la FCA. Fechas explícitas: su Elasticsearch no acepta NOW-."""
    today = date.today()
    frm = (today - timedelta(days=9)).isoformat()
    r = client.get(
        FCA_API,
        params={
            "q": f"((file_type:FULINS) AND (publication_date:[{frm} TO {today.isoformat()}]))",
            "from": 0,
            "size": 200,
        },
    )
    r.raise_for_status()
    hits = r.json().get("hits", {}).get("hits", [])
    files = [
        (h["_source"]["file_name"], h["_source"]["download_link"])
        for h in hits
        if h.get("_source", {}).get("file_name", "").startswith(_EQUITY_MARKER)
    ]
    return _latest_set(files)


def _latest_set(files: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Se queda con el set de la fecha más reciente (todas sus partes).

    El nombre codifica la fecha: `FULINS_E_20260801_01of02.zip`. Si la ventana
    de búsqueda pilló dos sábados, sin esto se mezclarían dos universos.
    """
    if not files:
        return []
    latest = max(name.split("_")[2] for name, _ in files)
    return sorted((n, u) for n, u in files if n.split("_")[2] == latest)


def _download(client: httpx.Client, url: str, dest: Path) -> None:
    with client.stream("GET", url) as response:
        response.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in response.iter_bytes(1 << 20):
                fh.write(chunk)


def _records_from_zip(path: Path, *, today: date, counter: list[int]) -> Iterator[FirdsRecord]:
    """Filas que pasan el filtro, contándolas por el camino.

    El recuento no es cosmético: un filtro roto (un MIC renombrado, un CFI que
    cambia) produce CERO filas y eso se lee como «no había trabajo». Con el
    número delante, «0 filtradas de un fichero de 800 MB» se lee como lo que es.
    """
    with zipfile.ZipFile(path) as z:
        for member in z.namelist():
            with z.open(member) as fh:
                for record in parse_fulins(fh, today=today):
                    counter[0] += 1
                    yield record


async def _apply(
    batches: dict[str, dict[tuple[str, str], FirdsRecord]],
    *,
    apply: bool,
    filtered: dict[str, int],
) -> int:
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    seeded_at = datetime.now(UTC)
    try:
        async with factory() as db:
            for source, records in batches.items():
                stats = await repo.sync_directory_source(
                    db, records, source=source, seeded_at=seeded_at
                )
                verb = "" if apply else " (dry-run)"
                print(
                    f"  {source}: {filtered.get(source, 0)} filas pasaron el filtro, "
                    f"{len(records)} únicas tras colapsar -> "
                    f"{stats.inserted} nuevas, {stats.updated} cambiadas, "
                    f"{stats.removed} eliminadas, {stats.unchanged} intactas{verb}"
                )
                if not records:
                    print(
                        f"  ! {source}: CERO filas tras el filtro. O el fichero no llegó, "
                        "o el filtro (MICs/CFI) dejó de casar con lo que publica el "
                        "regulador — no es «no había trabajo»."
                    )
                elif stats.removed == 0 and len(records) < repo.MIN_ROWS_TO_PRUNE:
                    print(
                        f"  ! {source}: lote sospechosamente pequeño "
                        f"(<{repo.MIN_ROWS_TO_PRUNE}); no se han eliminado ausentes"
                    )
            if apply:
                await db.commit()
            else:
                await db.rollback()
    finally:
        await engine.dispose()
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        # La consola de Windows es cp1252; un nombre con Ñ en el informe no
        # puede tirar el seed ([PHASE-44.13], el backfill de FX).
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="informa sin escribir")
    parser.add_argument(
        "--from-dir",
        type=Path,
        default=None,
        help="usa los ZIP FULINS_E_*.zip de un directorio local en vez de descargar",
    )
    args = parser.parse_args()
    today = date.today()

    batches: dict[str, dict[tuple[str, str], FirdsRecord]] = {}
    #: Filas que pasaron el filtro por fuente, ANTES de colapsar duplicados.
    filtered: dict[str, int] = {}

    if args.from_dir is not None:
        # Sin red: útil para re-aplicar una descarga previa o para depurar.
        # La fuente se infiere del nombre no-oficial que use el directorio;
        # aquí simplemente se aplican todos como un único lote por fuente
        # detectada en el nombre (`*FCA*` → FCA, resto → ESMA).
        esma: list[FirdsRecord] = []
        fca: list[FirdsRecord] = []
        counters = {"ESMA": [0], "FCA": [0]}
        for path in sorted(args.from_dir.glob("*.zip")):
            is_fca = "FCA" in path.name.upper()
            target = fca if is_fca else esma
            print(f"  leyendo {path.name}…")
            target.extend(
                _records_from_zip(path, today=today, counter=counters["FCA" if is_fca else "ESMA"])
            )
        filtered = {source: counter[0] for source, counter in counters.items()}
        batches["ESMA"] = partition_for_source(collapse_records(iter(esma)), source="ESMA")
        batches["FCA"] = partition_for_source(collapse_records(iter(fca)), source="FCA")
    else:
        with (
            httpx.Client(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client,
            tempfile.TemporaryDirectory(prefix="firds_") as tmp,
        ):
            tmpdir = Path(tmp)
            for source, listing in (
                ("ESMA", _list_esma_files(client)),
                ("FCA", _list_fca_files(client)),
            ):
                records: list[FirdsRecord] = []
                counter = [0]
                if not listing:
                    print(f"  ! {source}: la API no listó ningún FULINS de equity")
                for name, url in listing:
                    dest = tmpdir / name
                    print(f"  descargando {name}…")
                    _download(client, url, dest)
                    records.extend(_records_from_zip(dest, today=today, counter=counter))
                    dest.unlink()  # los ZIP pesan cientos de MB; no acumular
                filtered[source] = counter[0]
                batches[source] = partition_for_source(
                    collapse_records(iter(records)), source=source
                )

    return asyncio.run(_apply(batches, apply=not args.dry_run, filtered=filtered))


if __name__ == "__main__":
    raise SystemExit(main())
