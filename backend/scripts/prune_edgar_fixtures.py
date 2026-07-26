"""Poda los `companyfacts` cacheados a fixtures pequeñas y commiteables (PHASE-44.7).

El crudo de la SEC pesa 3-4 MB por empresa (cientos de conceptos, todos los
trimestres). El golden test solo necesita los conceptos que el `concept_map`
referencia y los datapoints de 10-K. Podando a eso, la fixture baja a ~100 KB.

Uso:
    .venv/Scripts/python.exe scripts/prune_edgar_fixtures.py
Lee de `EDGAR_CACHE_DIR` y escribe en `tests/fixtures/edgar/`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.modules.investment.fundamentals.adapters.concept_map import (
    COMBINED_MAP,
    CONCEPT_MAP,
    DEI_MAP,
    NET_LINE_FALLBACKS,
)

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_CACHE_DIR = _BACKEND_ROOT / "data" / "edgar_cache"
_FIXTURES_DIR = _BACKEND_ROOT / "tests" / "fixtures" / "edgar"

# Empresas del cruzado: MCD (servicios, equity negativo, EBIT sourced), O (REIT,
# EBIT derivado), JNJ (impairments, cierre a 28-dic).
_CIKS = ("0000063908", "0000726728", "0000200406")


def _referenced_tags() -> tuple[set[str], set[str]]:
    """Conceptos us-gaap y dei que el mapeo referencia."""
    us_gaap: set[str] = set()
    dei: set[str] = set()
    for tags in CONCEPT_MAP.values():
        us_gaap.update(tags)
    for combined in COMBINED_MAP.values():
        us_gaap.update(combined.add)
        us_gaap.update(combined.sub)
    for net_line in NET_LINE_FALLBACKS:
        us_gaap.add(net_line.concept)
    for tags in DEI_MAP.values():
        dei.update(tags)
    return us_gaap, dei


def _prune_concept(concept: dict[str, Any]) -> dict[str, Any] | None:
    """Deja solo los datapoints de 10-K (los que el pipeline ancla)."""
    units = concept.get("units", {})
    pruned_units: dict[str, list[dict[str, Any]]] = {}
    for unit, points in units.items():
        kept = [p for p in points if p.get("form") == "10-K"]
        if kept:
            pruned_units[unit] = kept
    if not pruned_units:
        return None
    return {**{k: v for k, v in concept.items() if k != "units"}, "units": pruned_units}


def _prune(payload: dict[str, Any], us_gaap: set[str], dei: set[str]) -> dict[str, Any]:
    facts = payload.get("facts", {})
    out_facts: dict[str, dict[str, Any]] = {}
    for taxonomy, wanted in (("us-gaap", us_gaap), ("dei", dei)):
        concepts = facts.get(taxonomy, {})
        pruned: dict[str, Any] = {}
        for tag in wanted:
            concept = concepts.get(tag)
            if concept is None:
                continue
            pruned_concept = _prune_concept(concept)
            if pruned_concept is not None:
                pruned[tag] = pruned_concept
        if pruned:
            out_facts[taxonomy] = pruned
    return {
        "cik": payload.get("cik"),
        "entityName": payload.get("entityName"),
        "facts": out_facts,
    }


def main() -> None:
    us_gaap, dei = _referenced_tags()
    _FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for cik in _CIKS:
        source = _CACHE_DIR / f"CIK{cik}.json"
        if not source.exists():
            print(f"⚠ falta {source} — corre el smoke primero para poblar la cache")
            continue
        payload = json.loads(source.read_text(encoding="utf-8"))
        pruned = _prune(payload, us_gaap, dei)
        target = _FIXTURES_DIR / f"CIK{cik}.json"
        target.write_text(json.dumps(pruned, separators=(",", ":")), encoding="utf-8")
        kb = target.stat().st_size / 1024
        print(f"{payload.get('entityName')}: {kb:.0f} KB -> {target.relative_to(_BACKEND_ROOT)}")


if __name__ == "__main__":
    main()
