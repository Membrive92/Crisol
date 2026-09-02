#!/usr/bin/env python3
"""Verificador de podredumbre documental (PHASE-44.9).

`knip` y `vulture` responden «¿alguien usa este código?». Nadie responde «¿esta
documentación sigue siendo cierta?», y en este proyecto esa clase de fallo ha
mordido **seis veces**:

1. `position-hero.tsx`, conservado por un comentario cuya premisa caducó → 1.632
   LoC muertas (PHASE-43).
2. El README declarando PHASE-39 «pendiente de commit» tres fases después.
3. Un análisis citando un saldo que la auditoría ya había retractado.
4. Las etiquetas F5/F6/D8 de la web, escritas a mano cuando eran ciertas.
5. El docstring de `version.py` afirmando un gate que no existía.
6. `backlog.md` describiendo el informe como «veredicto + tablas» dos días
   después de dejar de serlo, y citando `BE 1042` y un head de Alembic viejo.

`lessons.md` ya tiene la lección escrita ([PHASE-43]) y también la regla que la
gobierna: **si parcheas la misma raíz ≥2 veces, mueve la fuente de verdad**
([PHASE-34]). Escribir la lección por séptima vez sería justo lo que esa regla
prohíbe. Esto es el detector que sí se recalcula en cada `make verify`.

Comprueba SÓLO lo que se puede comprobar sin inventar:

- **A** — que los enlaces relativos resuelvan.
- **B** — que los identificadores de migración citados existan.
- **C** — que quien declare un head de Alembic nombre el head REAL.
- **D** — que los documentos VIVOS no lleven números volátiles.

Lo que NO comprueba, y hay que seguir mirando a mano al cerrar una fase: si una
afirmación cualitativa («el informe son tablas») dejó de ser cierta. Eso no es
automatizable.

Uso: `python scripts/check_docs.py` — código 1 si algo falla.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "internal_docs"
VERSIONS_DIR = ROOT / "backend" / "alembic" / "versions"

DOC_GLOBS = ("internal_docs/**/*.md", "CLAUDE.md", "README.md")

LIVE_DOCS = (
    DOCS_DIR / "backlog.md",
    DOCS_DIR / "HANDOFF.md",
    DOCS_DIR / "PROJECT-GUIDE.md",
)
"""Documentos que describen el AHORA y se reescriben.

La distinción con `phases/` es la que cierra el patrón: una phase doc es una
**foto fechada** —un recuento de tests allí es historia y envejece bien—; estos
describen el presente, así que un número que cambia cada fase es podredumbre
garantizada. Nadie vuelve a `backlog.md` a actualizar un `BE 1042`.
`PROJECT-GUIDE.md` (2026-09-02) entra por la misma razón: es la guía de entrada
para quien llega sin contexto, y una guía de entrada con un recuento viejo
enseña a desconfiar del resto.
"""

HEAD_CLAIM_DOCS = (*LIVE_DOCS, DOCS_DIR / "data-model" / "schema.md")
"""Dónde declarar un head de Alembic significa «AHORA MISMO es este».

Fuera de aquí, nombrar un head es historia legítima: la phase doc de 44.1 dice
que el head **era** `f9v25x7us9w8v4` y eso sigue siendo cierto de aquel momento,
igual que la lección de PHASE-44.1 al explicar el error que la originó. Marcar
esas dos cosas convertiría el chequeo en ruido, y un verificador ruidoso se
ignora — que es la forma más cara de no tener verificador."""

# Enlace markdown con paréntesis balanceados a un nivel: `(...)` dentro de la
# URL es legal y aparece en las rutas de Expo Router (`app/(modules)/...`).
MD_LINK = re.compile(r"\[[^\]]*\]\(\s*((?:[^()\s]|\([^()\s]*\))+?)\s*\)")

REVISION_ID = re.compile(r"\b(?=[a-z0-9]{14}\b)(?=[a-z0-9]*\d)[a-z0-9]{14}\b")
"""Los revision id de este repo son 14 caracteres alfanuméricos en minúscula.

El segundo lookahead exige un dígito **dentro del propio token**: sin acotarlo,
`(?=.*\\d)` miraba el resto de la línea y «comportamiento» (14 letras) pasaba por
revisión en cuanto hubiera un número más adelante."""

HEAD_CLAIM = re.compile(
    r"head[^.\n]{0,40}?`?([a-z0-9]{14})`?|`?([a-z0-9]{14})`?[^.\n]{0,20}?\(head\)",
    re.IGNORECASE,
)

VOLATILE_PATTERNS = (
    (re.compile(r"\b\d{2,5}\s+(?:tests?|passed)\b", re.IGNORECASE), "un recuento de tests"),
    (re.compile(r"\b(?:BE|FE)\s+\d{2,5}\b"), "un recuento de tests"),
    (re.compile(r"\bmypy\s+\d{2,5}\b", re.IGNORECASE), "un recuento de ficheros de mypy"),
    (re.compile(r"\b[0-9a-f]{64}\b"), "un hash de 64 caracteres"),
)

ALLOW_MARKER = "<!-- docs-check: ignore-line -->"
"""Escotilla explícita, por si alguna vez un número volátil es imprescindible.
Va en la MISMA línea. Que exija una marca visible es el punto: obliga a
justificarlo en vez de colarlo."""


@dataclass(frozen=True)
class Problem:
    check: str
    file: Path
    line: int
    message: str

    def render(self) -> str:
        rel = self.file.relative_to(ROOT).as_posix()
        return f"  [{self.check}] {rel}:{self.line} — {self.message}"


def doc_files() -> list[Path]:
    files: list[Path] = []
    for pattern in DOC_GLOBS:
        files.extend(sorted(ROOT.glob(pattern)))
    return [f for f in files if f.is_file()]


# ── A · Enlaces ───────────────────────────────────────────────────────


def check_links(files: list[Path]) -> list[Problem]:
    problems: list[Problem] = []
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in MD_LINK.finditer(line):
                target = match.group(1)
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                clean = target.split("#", 1)[0]
                if not clean:
                    continue
                if not (path.parent / clean).exists():
                    problems.append(
                        Problem(
                            "enlace",
                            path,
                            number,
                            f"apunta a `{target}`, que no existe",
                        )
                    )
    return problems


# ── B y C · Migraciones ───────────────────────────────────────────────


def migration_graph() -> tuple[set[str], set[str]]:
    """`(todas las revisiones, los heads)` leídos de los ficheros.

    Se calcula desde el DAG en disco y NO desde la BD: así el chequeo corre sin
    Postgres levantado y sin depender de en qué revisión esté una base concreta.
    """
    revisions: set[str] = set()
    parents: set[str] = set()
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        revision = re.search(r'^revision(?::\s*str)?\s*=\s*["\']([^"\']+)["\']', source, re.M)
        down = re.search(
            r'^down_revision(?::[^=]+)?\s*=\s*["\']([^"\']+)["\']', source, re.M
        )
        if revision:
            revisions.add(revision.group(1))
        if down:
            parents.add(down.group(1))
    return revisions, revisions - parents


def check_migrations(files: list[Path], revisions: set[str], heads: set[str]) -> list[Problem]:
    problems: list[Problem] = []
    head_docs = {p.resolve() for p in HEAD_CLAIM_DOCS}
    for path in files:
        claims_head_here = path.resolve() in head_docs
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in REVISION_ID.finditer(line):
                candidate = match.group(0)
                # Sólo se juzga lo que ya parece una revisión conocida o lo que
                # el texto presenta como tal; un id inventado en prosa no se
                # puede distinguir de una palabra cualquiera.
                if candidate in revisions:
                    continue
                # `revisi` cubre «revision» y «revisión»: buscar la forma sin
                # tilde dejaba pasar la mitad de las menciones, que están en
                # español.
                if "revisi" in line.lower() or "migraci" in line.lower():
                    problems.append(
                        Problem(
                            "migración",
                            path,
                            number,
                            f"cita la revisión `{candidate}`, que no existe en "
                            f"alembic/versions/",
                        )
                    )
            if not claims_head_here:
                continue
            for match in HEAD_CLAIM.finditer(line):
                claimed = match.group(1) or match.group(2)
                if not claimed or claimed not in revisions:
                    continue
                if claimed not in heads:
                    real = ", ".join(sorted(heads)) or "(ninguno)"
                    problems.append(
                        Problem(
                            "head",
                            path,
                            number,
                            f"declara `{claimed}` como head de Alembic, pero el head "
                            f"real es `{real}`",
                        )
                    )
    return problems


# ── D · Números volátiles en documentos vivos ─────────────────────────


def check_volatile(files: list[Path]) -> list[Problem]:
    problems: list[Problem] = []
    live = {p.resolve() for p in LIVE_DOCS}
    for path in files:
        if path.resolve() not in live:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ALLOW_MARKER in line:
                continue
            for pattern, what in VOLATILE_PATTERNS:
                if pattern.search(line):
                    problems.append(
                        Problem(
                            "volátil",
                            path,
                            number,
                            f"lleva {what} en un documento VIVO. Cambia cada fase y "
                            f"nadie vuelve a actualizarlo: sustitúyelo por cómo "
                            f"obtenerlo (`make verify`) o llévalo a una phase doc, "
                            f"que sí es una foto fechada",
                        )
                    )
                    break
    return problems


# ── Entrada ───────────────────────────────────────────────────────────


def main() -> int:
    # La consola de Windows usa cp1252 por defecto, donde un emoji o un `·` no
    # existen: sin esto, el script muere con `UnicodeEncodeError` al imprimir su
    # PRIMERA línea — o sea que el verificador de podredumbre documental no se
    # podía ejecutar en la máquina de desarrollo, sólo en el CI de Linux. Se
    # reconfigura la salida en vez de quitar los símbolos porque el informe se
    # lee mucho mejor con ellos y en CI se ven bien.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    files = doc_files()
    revisions, heads = migration_graph()

    problems = [
        *check_links(files),
        *check_migrations(files, revisions, heads),
        *check_volatile(files),
    ]

    print(f"📄 docs-check: {len(files)} documentos · {len(revisions)} migraciones en el DAG")

    if not problems:
        print("✅ Sin podredumbre detectable.")
        return 0

    by_check: dict[str, list[Problem]] = {}
    for problem in problems:
        by_check.setdefault(problem.check, []).append(problem)

    print(f"❌ {len(problems)} problema(s):\n")
    for check, items in sorted(by_check.items()):
        print(f"{check.upper()} ({len(items)})")
        for item in items:
            print(item.render())
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
