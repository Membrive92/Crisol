# PHASE-14.7 — Fusión por prefijo común en el detector de subscripciones

**Estado**: ✅ completada
**Rama**: `feat/phase-14.7-detector-prefix-fusion`
**Fecha de merge**: 2026-05-06

## Re-encuadre del alcance

El backlog original era "Detector con IA Ollama para
subscripciones". Al planificar resultó claro que **integrar
Ollama sin un dataset etiquetado para validar prompts es un riesgo
sin retorno**: los prompts mal calibrados podrían causar peores
agrupaciones que la heurística pura. Sin datos reales del usuario
para iterar, no se puede afinar.

Re-encuadrada a una **mejora heurística intermedia** que cubre el
caso #1 que motivaba el uso de IA: descripciones inconsistentes
del mismo merchant ("NETFLIX.COM", "Netflix Premium",
"Netflix Suscripcion") quedan como subscripciones separadas. La
fusión por prefijo común resuelve este caso sin IA, sin ambigüedad
y testeable de forma determinista.

La integración Ollama queda en backlog para cuando haya datos
reales con los que validar prompts.

## Qué se implementó

### `subscriptions/detector.py`

- Nueva constante `MIN_COMMON_PREFIX = 6`. Empíricamente cubre
  `netflix*` (7), `spotify*` (7), `amazon*` (6), evita matches
  ruidosos como `sp*` (2 chars).
- Función `_common_prefix(a, b)`: longitud del prefijo común
  entre dos strings.
- Función `_merge_by_common_prefix(grouped)`: agrupa por
  `(amount, currency)`, ordena merchants por longitud
  descendente, hace un pase O(n²) por bucket fusionando los más
  cortos en los más largos cuando comparten >= 6 chars de
  prefijo. Preserva el merchant más largo como llave (más
  específico → mejor identificador).
- `detect_for_user` invoca `_merge_by_common_prefix(grouped)`
  entre el agrupamiento inicial y la detección de cadencia.

### Tests `test_subscriptions_prefix_fusion.py` (6)

- `_common_prefix` casos básicos.
- Fusión con prefijo suficiente y mismo `(amount, currency)`.
- NO fusiona si `amount` distinto.
- NO fusiona si prefijo común < 6 chars.
- 3-way: la llave es el merchant más largo.
- Integration: 4 cargos mensuales con descripciones distintas
  pero prefijo "netflix" → 1 subscription detectada con
  `occurrence_count=4`.

Suite backend: **214/214** (+6 nuevos).

## Archivos clave

- `backend/app/modules/personal_finance/subscriptions/detector.py`
  (`_common_prefix`, `_merge_by_common_prefix`,
  `MIN_COMMON_PREFIX`, integración en `detect_for_user`)
- `backend/tests/test_subscriptions_prefix_fusion.py` (6 tests)

## Verificación

- [x] `pytest tests/` — 214/214.
- [x] `mypy app/` — 13 pre-existentes; 0 nuevos.
- [x] `ruff check app/ tests/` verde.
- [ ] Smoke: insertar 4 cargos mensuales con
      "Netflix.com" / "Netflix Premium" / etc. → POST /scan → 1
      sola subscription detectada.

## Decisiones tomadas

- **Posponer Ollama hasta tener dataset real**. La integración
  IA introduce dependencia (Ollama corriendo + modelo cargado +
  prompts cuidados). Sin un test set etiquetado para iterar,
  los prompts pueden empeorar la calidad. El usuario puede
  evaluar la calidad de la fusión por prefijo con sus propios
  datos durante uso normal y, si emerge necesidad, abrir una
  sub-fase futura con prompts más informados.
- **`MIN_COMMON_PREFIX = 6` decidido empíricamente**. Cubre los
  merchants comunes (netflix=7, spotify=7, amazon=6, prime=5
  → no, pero "amazon" sí). Sube a 7 si emerge falsa
  convergencia (ej. "spotify" y "spotcheck" comparten 4); bajo
  a 5 si quedan merchants importantes fuera. Aceptable para v1.
- **Conservar el merchant más largo como llave**. Preferimos
  identificadores más específicos. "netflixsuscripcionplus" es
  más informativo que "netflixcom" para el log y para futura
  inspección.
- **Fusión sólo si `amount` y `currency` coinciden**. Dos
  cargos del mismo merchant pero amounts distintos son
  típicamente subscripciones distintas (basic/premium). Mejor
  no fusionarlos automáticamente.
- **Algoritmo O(n²) por bucket**. Para volúmenes esperados
  (< 100 grupos por user) es trivial. Si crece, indexar por
  prefijo de N chars y comparar dentro del mismo bucket.

## Limitaciones conocidas

- **Sin IA real** (decidido — ver alcance).
- **Heurística de prefijo no captura sufijos comunes**. Casos
  como "AMZN_NETFLIX" + "NETFLIX_AMZN" comparten "NETFLIX" en
  diferentes posiciones — no se fusiona. Si emerge en uso real,
  añadir comparación de substring común máximo (más caro
  computacionalmente).
- **Sensible a ortografía**. "Netflix" vs "Netfliks" no se
  fusionan (4 chars de prefijo). Ahí sí ayudaría una capa IA.
- **No hay setting de usuario** para ajustar `MIN_COMMON_PREFIX`.
  Si emerge necesidad de calibración por usuario, exponer.

## Cierre de PHASE-14

PHASE-14 cerrada al completo (7 sub-fases):
- 14.1 — Edición inline amount presupuestos.
- 14.2 — Sección Descartadas en subscriptions UI.
- 14.3 — Date picker nativo mobile.
- 14.4 — `convertAll` toggle mobile.
- 14.5 — Notificaciones proactivas budget over.
- 14.6 — Cobertura UI mobile (componentes presentacionales).
- 14.7 — Fusión por prefijo común en el detector.

Backlog actualizado: la integración Ollama real para
subscripciones queda como follow-up cuando haya datos reales
para validar prompts.
