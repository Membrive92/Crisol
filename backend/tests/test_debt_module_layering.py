"""PHASE-47.A — La frontera entre `debt/` y `accounts/`, comprobada por AST.

47.A consolida el dominio deuda en `backend/app/modules/personal_finance/debt/`.
El movimiento sólo es viable porque los seis módulos que se mudan dependen de
`accounts` **por sus hojas** (`models`, `repository`, `schemas`) y nunca de
`accounts.service`, mientras que `accounts.service` sí necesita el cuadro de
amortización. Esa asimetría es la que evita el ciclo de importación.

Una asimetría así no sobrevive escrita en un comentario: el día que alguien
necesite un helper de `accounts.service` desde `debt/` lo importará, y Python no
protestará hasta que el ciclo se cierre — momento en el que el error saldrá en un
sitio que no tiene nada que ver. Por eso la regla se afirma aquí, con su motivo
dentro ([PHASE-44.21]: una decisión razonada sin test se revierte sola).

Se recorre el AST y no el texto: `grep` no distingue un import real de una
mención en un docstring, y este fichero se apoya justo en esa diferencia.

**Un submódulo se puede importar de dos formas** y las dos cuentan:

    from app.modules.personal_finance.accounts.service import get_balances
    from app.modules.personal_finance.accounts import service

La primera versión de este fichero sólo veía la primera —filtraba por el prefijo
con punto final, y la segunda deja `node.module` sin el último segmento—, así
que pasaba en verde con la violación delante. Lo destapó la revisión adversarial
de 47.A, no el test.
"""

from __future__ import annotations

import ast
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1] / "app" / "modules" / "personal_finance"
DEBT_DIR = MODULE_ROOT / "debt"
ACCOUNTS_PKG = "app.modules.personal_finance.accounts"

# Módulos de `accounts` que `debt/` PUEDE importar: son hojas (no importan a su
# vez lógica de dominio), así que no pueden cerrar un ciclo.
ALLOWED_ACCOUNTS_LEAVES = {"models", "repository", "schemas"}

# Los seis módulos que 47.A mudó desde `accounts/`. Se listan para que este
# fichero falle si alguno vuelve a su sitio anterior sin querer.
MOVED_MODULES = {
    "amortization",
    "health",
    "history",
    "installments_model",
    "installments_repository",
    "reconciliation",
}

# Nombres que tenían esos módulos en `accounts/` antes del movimiento.
FORMER_ACCOUNTS_NAMES = (
    "amortization",
    "debt_health",
    "debt_history",
    "debt_reconciliation",
    "installments_model",
    "installments_repository",
)


def _accounts_submodules(path: Path) -> set[str]:
    """Submódulos de `accounts` que `path` importa, en sus DOS formas."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # import app.modules.personal_finance.accounts.service [as x]
            for alias in node.names:
                if alias.name.startswith(ACCOUNTS_PKG + "."):
                    found.add(alias.name[len(ACCOUNTS_PKG) + 1 :].split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == ACCOUNTS_PKG:
                # from app.modules.personal_finance.accounts import service
                found.update(alias.name for alias in node.names)
            elif node.module.startswith(ACCOUNTS_PKG + "."):
                # from app.modules.personal_finance.accounts.service import x
                found.add(node.module[len(ACCOUNTS_PKG) + 1 :].split(".")[0])
    return found


def _debt_python_files() -> list[Path]:
    return sorted(p for p in DEBT_DIR.glob("*.py") if p.name != "__init__.py")


def test_the_six_modules_live_in_debt() -> None:
    """Los seis módulos que 47.A mudó están en `debt/` y ya no en `accounts/`."""
    present = {p.stem for p in _debt_python_files()}
    assert present >= MOVED_MODULES, f"faltan en debt/: {sorted(MOVED_MODULES - present)}"
    stale = [
        name for name in FORMER_ACCOUNTS_NAMES if (MODULE_ROOT / "accounts" / f"{name}.py").exists()
    ]
    assert not stale, f"siguen en accounts/: {stale}"


def test_debt_never_imports_accounts_service() -> None:
    """`debt/` no puede importar `accounts.service`: cerraría el ciclo.

    `accounts.service` importa `debt.installments_repository` (necesita generar y
    leer el cuadro). Si `debt/` devolviera el favor, tendríamos una importación
    circular que sólo se manifiesta según el orden de carga — el peor modo de
    fallo posible: intermitente y en un fichero ajeno.

    Si algún día hace falta de verdad, la salida NO es añadir una excepción
    aquí: es mover a `accounts.repository` (hoja) lo que `debt/` necesite.
    """
    offenders: list[str] = []
    for path in _debt_python_files():
        for submodule in _accounts_submodules(path):
            if submodule not in ALLOWED_ACCOUNTS_LEAVES:
                offenders.append(f"{path.name} → accounts.{submodule}")
    assert not offenders, (
        "debt/ sólo puede importar las HOJAS de accounts "
        f"({sorted(ALLOWED_ACCOUNTS_LEAVES)}); encontrado: {offenders}"
    )


def test_the_detector_sees_both_import_forms() -> None:
    """El detector caza las dos formas de traerse un submódulo.

    Es el test del test: sin él, `_accounts_submodules` puede volver a ver sólo
    una de las dos y el guardarraíl de arriba pasaría en verde con la violación
    delante — que es exactamente lo que hacía la primera versión.
    """
    # Cada submódulo llega por UNA sola forma a propósito: si `service` viniera
    # también en la forma con punto, cegar la otra no cambiaría el resultado y
    # este test pasaría con el detector roto — que es justo lo que hacía la
    # primera versión de este probe.
    src = (
        # forma A — la que se escapaba del filtro de prefijo
        "from app.modules.personal_finance.accounts import service\n"
        # forma B
        "from app.modules.personal_finance.accounts.models import Account\n"
        # forma C
        "import app.modules.personal_finance.accounts.repository\n"
        # ruido: no es de accounts, no debe aparecer
        "from app.modules.personal_finance.debt.health import compute_debt_health\n"
    )
    probe = DEBT_DIR / "_layering_probe_tmp.py"
    probe.write_text(src, encoding="utf-8")
    try:
        found = _accounts_submodules(probe)
    finally:
        probe.unlink()
    assert found == {"service", "models", "repository"}, found


def test_debt_imports_are_absolute() -> None:
    """Sin imports relativos en `debt/`.

    El backend usa rutas absolutas en todo el árbol, y este fichero se apoya en
    ello para saber a qué módulo apunta cada import. Un relativo (`from
    ..accounts.service import …`) se le escaparía a la comprobación de arriba —
    o sea que el guardarraíl dejaría de guardar sin dejar de pasar.
    """
    relative: list[str] = []
    for path in _debt_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                relative.append(f"{path.name}:{node.lineno}")
    assert not relative, f"imports relativos en debt/: {relative}"
