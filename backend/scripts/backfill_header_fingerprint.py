"""Data-fix: rellena `import_jobs.header_fingerprint` en los jobs históricos.

**Por qué existe.** PHASE-47.A avisa cuando un fichero tiene el formato de los
que sueles importar en OTRA cuenta. Esa comparación necesita conocer el formato
de los imports anteriores, y la columna nace vacía: sin este backfill la señal no
detecta nada hasta que cada cuenta tenga un import posterior a 47.A.

**Por qué es un script y no la migración.** Lección [PHASE-34]: una migración
backfilea para REPRODUCIR el comportamiento previo; corregir datos es un paso
aparte y auditado.

**De qué jobs se puede derivar y de cuáles NO.** Esto es lo delicado, y la
primera versión de este script lo tenía mal. `preview_payload.rows` guarda las
filas YA PARSEADAS, y los dos smart-parsers (`parse_pdf_smart`,
`parse_xlsx_smart`) y el de visión emiten claves FIJAS por contrato. Para esos
jobs, `rows[0].keys()` no es la cabecera del fichero: es la misma constante para
todos los bancos y todos los productos. Derivarla de ahí escribiría un valor
idéntico en todas las cuentas — y con eso el guardarraíl se apagaría solo,
porque el formato «ya habría entrado» en la cuenta elegida.

Así que sólo se deriva de los jobs cuyo parseo indexa por la cabecera REAL:
CSV y los caminos legacy (`parse_file`). Para el resto se deja NULL, que es la
respuesta honesta —«no se sabe»— y hace que la cuenta simplemente no tenga
formato registrado, no que tenga uno falso. Se detecta por la FORMA de las
claves, no por el campo `source`, para que un job con `source` ausente o raro no
se cuele.

Uso:
    python -m scripts.backfill_header_fingerprint            # dry-run
    python -m scripts.backfill_header_fingerprint --apply    # escribe

Sólo toca jobs COMPLETADOS con la huella a NULL: un preview abandonado no dice
nada sobre a qué cuenta pertenece un formato.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.main  # noqa: F401  (efecto lateral: registra los modelos)
from app.core.config import settings
from app.modules.personal_finance.imports.fingerprint import header_fingerprint
from app.modules.personal_finance.imports.models import ImportJob, ImportJobStatus

# Conjuntos de claves que NO son una cabecera: los emiten los parsers con
# claves fijas. Si el job trae exactamente uno de éstos, su fichero original es
# irrecuperable y la huella se queda en NULL.
FIXED_KEY_SETS: tuple[frozenset[str], ...] = (
    # SMART_FORCED_MAPPING (parse_pdf_smart / parse_xlsx_smart)
    frozenset({"amount", "occurred_at", "description", "category_name", "statement_balance"}),
    # Variante sin saldo, anterior a PHASE-39
    frozenset({"amount", "occurred_at", "description", "category_name"}),
    # VISION_FORCED_MAPPING
    frozenset({"amount", "occurred_at", "description"}),
)


def _real_header(job: ImportJob) -> list[str] | None:
    """Cabecera real del fichero, o `None` si no es recuperable."""
    payload = job.preview_payload or {}
    rows = payload.get("rows") or []
    if not rows or not isinstance(rows[0], dict) or not rows[0]:
        return None
    keys = list(rows[0].keys())
    if frozenset(keys) in FIXED_KEY_SETS:
        return None
    return keys


async def main(apply: bool) -> None:
    engine = create_async_engine(settings.database_url, future=True)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    updated = 0
    skipped = 0
    async with factory() as db:
        jobs = (
            (
                await db.execute(
                    select(ImportJob).where(
                        ImportJob.status == ImportJobStatus.COMPLETED,
                        ImportJob.header_fingerprint.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        print(f"jobs completados sin huella: {len(jobs)}")
        for job in jobs:
            columns = _real_header(job)
            fingerprint = header_fingerprint(columns) if columns else None
            if fingerprint is None:
                skipped += 1
                source = (job.preview_payload or {}).get("source", "?")
                print(
                    f"  - {job.filename[:40]:40} [{source}] cabecera no recuperable "
                    "-> se deja NULL"
                )
                continue
            updated += 1
            print(
                f"  - {job.filename[:40]:40} {len(columns or [])} columnas "
                f"-> {fingerprint[:12]}..."
            )
            if apply:
                job.header_fingerprint = fingerprint
        if apply:
            await db.commit()
    print(
        f"\n{'APLICADO' if apply else 'DRY-RUN'}: {updated} con huella, "
        f"{skipped} sin cabecera recuperable (se quedan en NULL a propósito)."
    )
    if not apply and updated:
        print("Vuelve a ejecutarlo con --apply para escribir.")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="escribe (por defecto dry-run)")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))
