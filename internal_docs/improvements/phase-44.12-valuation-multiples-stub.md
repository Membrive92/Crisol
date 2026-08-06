# PHASE-44.12 — Valoración por múltiplos (stub — bloqueada hasta cerrar 44.11.G)

**Estado**: 🔒 anotada, NO planificada en detalle. Este stub existe para
que la fase no se diseñe desde cero olvidando los guardarraíles ya
decididos (usuario, 2026-08-01, sobre la Decisión 5 de
`phase-44.11-pricing-decisiones.md`).
**Desbloqueo**: precios de 44.11 validados por el usuario contra su bróker
(sub-fase G). No antes.

## Objetivo

La "hoja 10 del cuaderno": múltiplos de valoración cruzando **cotización
viva × último estado financiero canónico** — PER, precio/ventas,
precio/valor contable, precio/FCF, EV/EBITDA (con `net_debt` ya derivado).

## Guardarraíles YA DECIDIDOS (no reabrir al planificar)

1. **Vive fuera del `AnalysisRun`.** Se calcula al vuelo y **no se
   persiste** en el run. El motor forense es book-based a propósito: un
   score que se mueve con la cotización no sería reproducible al
   reejecutar un run antiguo (`forensic.py:3-6`). La valoración es una
   capa aparte que consume el run vigente + la quote viva.
2. **La UI la separa visualmente del veredicto forense.** "¿Es seguro?"
   (forense, book-based, reproducible) y "¿está cara?" (valoración,
   dependiente del precio del día) son preguntas distintas. Mezclarlas
   contaminaría el juicio de seguridad que el módulo existe para dar.
3. **Doble staleness visible**: fecha de la quote (`quote_as_of`) Y fecha
   del último cierre fiscal usado. Un PER con precio de hoy sobre
   beneficio de hace 14 meses debe decirlo.

## Pendientes de decisión (cuando se planifique)

- **Gordon**: requiere beta y prima de riesgo — decidir fuente (yfinance
  trae beta a veces; calidad sin verificar) o descartar el modelo.
- **Comparables de sector**: sin fuente gratuita — probablemente fuera.
- Qué múltiplos entran en MVP y sus bandas orientativas (si es que llevan
  banda: la valoración relativa sin comparables quizá no deba tener
  semáforo, solo el número y su serie histórica book-based).
