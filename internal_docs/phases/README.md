# `phases/` — un documento por fase entregada

Cada fichero es una **foto fechada** de una fase tal como se entregó
(_as-built_): objetivo, qué se implementó, ficheros clave, endpoints y
migraciones, verificación, decisiones, limitaciones. Los recuentos y las
versiones que contienen son los de aquel momento y envejecen a propósito — no
se actualizan; si algo cambia, lo cuenta la fase siguiente.

- **Índice con el estado de cada fase**: la tabla de
  [`../README.md`](../README.md).
- **Plantilla** para una fase nueva: [`../development-spec.md`](../development-spec.md) §4.
- **Planes** (lo que se pensó ANTES de construir): [`../improvements/`](../improvements/).
  Un plan cuyo alcance cambió al construir lleva un aviso de re-alcance al
  principio, no se reescribe.
- Convención de nombre: `phase-<número>-<slug-en-inglés>.md`; las sub-entregas
  de una fase grande llevan letra (`phase-44.24.A-…`, `phase-47.E-…`).

Ficheros que no son una phase doc pero viven aquí por historia:
[`phase-7-roadmap.md`](phase-7-roadmap.md), [`phase-8-roadmap.md`](phase-8-roadmap.md)
y [`phase-30-31-plan.md`](phase-30-31-plan.md) (plan ejecutivo conjunto de
PHASE-30 y PHASE-31; hasta 2026-09-02 era el `README.md` de este directorio).
