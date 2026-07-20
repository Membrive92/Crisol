"""Módulo de dominio Inversión (PHASE-44).

Green-field, desacoplado del resto de Crisol salvo el Dashboard (contrato de
agregación PHASE-43.4). Dos tabs sobre un catálogo común de `Security`:

- **Cartera**: lotes, ventas FIFO, dividendos, corporate actions, P&L
  descompuesto en precio/divisa, métricas de broker con quotes EOD/horarias.
- **Análisis**: análisis fundamental forense multi-anual (riesgo contable +
  sostenibilidad del dividendo) sobre cualquier ticker.

Fuente de verdad del diseño: `internal_docs/improvements/DESIGN-v2-investment-module.md`
(qué/porqué) y `ARCHITECTURE-investment-module.md` (cómo).

PHASE-44.1 entrega solo los cimientos: enums, tablas, modelos y migración.
"""
