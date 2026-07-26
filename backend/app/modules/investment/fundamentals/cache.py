"""Cache en disco de los payloads crudos de la SEC (PHASE-44.6, Dec.18).

La cache NO es una optimización, es **evidencia de auditoría**: guarda el JSON
tal y como lo devolvió la SEC, antes de que nadie lo interprete. Si el mapeo
cambia —o si `edgartools` cambia su normalización entre versiones— se puede
re-derivar todo sin volver a pedirle nada a la SEC y comparando contra lo mismo
que se ingirió el primer día.

Layout plano `CIK##########.json`, el mismo que escribe
`scripts/validate_edgar.py`: así el cruzado manual y la ingesta de producción
comparten evidencia en vez de tener cada uno su copia, que es como acaban
divergiendo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FactsCache:
    """Payloads `companyfacts` por CIK.

    No caduca sola: un filing publicado no cambia, y el refresco lo decide la
    ingesta (que sabe si hay un 10-K nuevo), no un TTL a ciegas.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def normalize_cik(cik: str | int) -> str:
        """CIK a 10 dígitos con ceros a la izquierda, como los nombra la SEC."""
        return str(int(cik)).zfill(10)

    def path_for(self, cik: str | int) -> Path:
        return self.root / f"CIK{self.normalize_cik(cik)}.json"

    def has(self, cik: str | int) -> bool:
        return self.path_for(cik).exists()

    def load(self, cik: str | int) -> dict[str, Any] | None:
        """El payload cacheado, o `None` si no está.

        Un JSON corrupto (descarga cortada a medias) se trata como ausencia: es
        recuperable volviendo a descargar, y devolver medio payload haría que el
        fallo apareciese mucho más lejos, ya convertido en huecos raros.
        """
        path = self.path_for(cik)
        if not path.exists():
            return None
        try:
            payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        return payload

    def store(self, cik: str | int, raw: bytes) -> Path:
        """Guarda el payload crudo. Escritura atómica.

        El fichero temporal + `replace` evita que una descarga interrumpida deje
        un JSON a medias que la siguiente ejecución daría por bueno.
        """
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path_for(cik)
        tmp = path.with_suffix(".json.part")
        tmp.write_bytes(raw)
        tmp.replace(path)
        return path
