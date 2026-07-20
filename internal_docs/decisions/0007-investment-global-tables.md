# ADR-0007 — Tablas globales (sin `user_id`) en el módulo Inversión

**Estado**: aceptado — PHASE-44.1 (cimientos del módulo).
**Fecha**: 2026-07-19
**Ámbito**: excepción explícita al patrón multi-tenant para las tablas de
datos de mercado/regulatorios del módulo `investment`. Sin impacto en el
resto de Crisol.
**Contexto de diseño**:
[`improvements/DESIGN-v2-investment-module.md`](../improvements/DESIGN-v2-investment-module.md)
(§3, Dec.11) y
[`improvements/ARCHITECTURE-investment-module.md`](../improvements/ARCHITECTURE-investment-module.md)
(§2.1).

## Contexto

La regla de arquitectura de Crisol es **aislamiento multi-tenant duro**: toda
tabla de dominio lleva `user_id NOT NULL` y **toda** query filtra por él, con
tests de aislamiento obligatorios (ver `architecture.md` §2.3 y las lecciones
recurrentes sobre fugas entre usuarios).

El módulo Inversión introduce una clase de datos que **no pertenece a ningún
usuario**: son objetivos y verificables contra una fuente externa.

- La **identidad de un valor** (`securities`: ticker, CIK, sector, norma
  contable) es la misma para todos.
- Los **estados financieros** (`financial_statements`, `restatement_flags`)
  provienen de un filing SEC concreto (`filing_accession`). El 10-K de una
  empresa es el mismo dato lo mire quien lo mire.
- Los **umbrales de scoring** (`scoring_thresholds`) son parámetros del modelo
  forense por (sector × norma), no preferencias de usuario.
- Las **cotizaciones** (`price_quotes`) son una fila viva por security, cacheada
  con TTL; el precio de AAPL no es "de un usuario".

Duplicar estas filas por usuario significaría: (a) re-descargar el mismo filing
EDGAR N veces (el rate limit SEC es un recurso escaso, [Dec.18]); (b)
almacenar N copias idénticas de ~50 partidas × 5 años; (c) arriesgar que dos
usuarios vean números distintos para la misma empresa por una descarga en
momentos distintos. La objetividad del dato es justamente lo que da valor al
análisis: si fuese "por usuario", no sería auditable contra el regulador.

## Decisión

Cuatro tablas del módulo son **GLOBALES** (sin `user_id`) [Dec.11]:

| Tabla | Por qué global |
|---|---|
| `securities` | Identidad de mercado; una por (ticker, exchange) |
| `financial_statements` + `restatement_flags` | Derivadas de un filing oficial concreto |
| `scoring_thresholds` | Parámetros del modelo, no del usuario |
| `price_quotes` | Cotización objetiva; una fila viva por security |

El resto del módulo **sí** es scoped por usuario y sigue el patrón normal:
`inv_lots`, `inv_sales`, `inv_sale_allocations`, `inv_dividends_received`,
`inv_corporate_actions`, `inv_lot_adjustments` (la cartera es de cada uno) y
`analysis_runs` (un run es "el análisis que YO ejecuté", con su
`engine_version`/`thresholds_version`, aunque lea statements globales).
`ingestion_jobs` es un caso mixto: la tabla-destino es global, pero el job se
**atribuye** a un `user_id` por auditoría (quién pidió la descarga).

## Consecuencias

- **Los tests de aislamiento NO aplican a las tablas globales** (no hay nada
  que aislar). Sí aplican, con el rigor de siempre, a las 7 tablas scoped:
  ningún usuario puede ver lotes/ventas/dividendos/runs de otro.
- Las queries a tablas globales **no llevan** `WHERE user_id = ...`. Esto es
  deliberado y debe documentarse en el repository correspondiente para que no
  se lea como el bug clásico de "olvidé el filtro" — es lo contrario: meter un
  `user_id` aquí sería el error.
- Escritura controlada: las tablas globales sólo las escribe la ingesta
  (`fundamentals/`) o el pricing (`pricing/`), nunca un endpoint de usuario
  arbitrario. Un usuario dispara una ingesta, pero el dato resultante es común.
- Integridad referencial: las tablas scoped referencian `securities.id`
  (FK global). Borrar un `user` arrastra su cartera y sus runs (CASCADE), pero
  **no** toca `securities`/`financial_statements` (el dato de mercado sobrevive).

## Alternativas descartadas

- **`user_id` en todo, duplicando datos de mercado**: coherente con la regla
  general, pero desperdicia el rate limit SEC, multiplica almacenamiento
  idéntico y permite divergencias entre usuarios para la misma empresa. El
  aislamiento no aporta nada cuando el dato es público y objetivo.
- **Una tabla `securities` por usuario con dedup lógico**: complejidad sin
  beneficio; seguiría necesitando una fuente canónica global.
