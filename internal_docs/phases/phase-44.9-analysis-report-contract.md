# PHASE-44.9 — Informe de análisis fundamental con pestañas

**Estado**: ✅ E1 (backend) + E2-E4 (web) completadas. Pendiente la prueba manual
del usuario.
**Rama**: trabajo directo sobre `main` (convención del proyecto: push directo).
**Fecha**: 2026-07-31
**Plan completo**: [`improvements/phase-44.9-investment-analysis-report.md`](../improvements/phase-44.9-investment-analysis-report.md)

## Objetivo

Que el backend deje de guardarse el porqué. La pantalla de informe con pestañas
(E2-E4) necesita tres cosas que el backend **calculaba y no publicaba**: cómo se
llama cada métrica, contra qué corte se la juzgó, y qué señales produjeron cada
veredicto. Sin eso, la web tendría que volver a escribir 100 etiquetas a mano —
que es exactamente el mecanismo que hizo que tres de ellas mintieran.

## Por qué esta fase existe

Auditoría del estado real de la pantalla de análisis (verificada fichero a
fichero):

- Se pintan **22 de 52** métricas, y todas del **último ejercicio**, mientras el
  JSONB trae todos los años ya con su banda calculada.
- El informe vive en una **mutación** (`useRunAnalysis`) y desaparece al
  recargar. Los dos hooks que leen el histórico existían y no los llamaba nadie.
- **Tres etiquetas mentían** sobre el número que enseñaban:

  | La web decía | El motor calcula |
  |---|---|
  | `F5 — deuda emergente` | Riesgo de fondo de comercio (goodwill/activo) |
  | `F6 — dilución` | Anomalía del circulante |
  | `Rentabilidad por dividendo` (D8) | Margen de seguridad = (caja − dividendos)/ventas |

  La tercera es la peor: una rentabilidad por dividendo exige precio de mercado,
  y el run no lo tiene por diseño.

## Qué se implementó

### 1. El catálogo de métricas viaja por API

- `MetricDefinition` gana **`unit`** (`MetricUnit`: percent · times · days ·
  years · pp · score · count · currency_per_share). Es **obligatorio y sin
  default**: con default, añadir una métrica sin pensar su unidad la etiquetaría
  mal en silencio. Sin unidad, un `0,42` es indistinguible entre 42 %, 0,42
  veces y 42 días — por eso la web imprimía márgenes como `0,42`.
- **`DUPONT_EM` entra en el catálogo** (52 métricas, 28 en la capa 1). Se
  calculaba desde PHASE-44.2 pero vivía **fuera**, así que viajaba sin etiqueta
  ni unidad. Ahora se emite dentro de `_compute_year`, de modo que la fila de la
  matriz y la de la descomposición DuPont son **el mismo `MetricResult`** y no
  pueden divergir. Entra **sin `direction`**: no añade ni una fila al seed y el
  `thresholds_version` de los runs **no se mueve**.
- `GET /investment/analysis/metrics` → las 52 con `label`, `family`, `unit`,
  `direction`, los 4 cortes y su `note`.

### 2. Las 49 partidas canónicas, con nombre y bloque

`GET /investment/fundamentals/items`. Los bloques (activo corriente, explotación,
flujo de financiación…) existían **como comentarios de Python** sobre las tuplas
de `canonical.py`: invisibles desde fuera. Ahora son datos
(`CanonicalItemDefinition`, `StatementKind`, `ItemGroup`), en el mismo fichero
que define las claves para que no puedan divergir.

### 3. Los umbrales efectivos se persisten con el run

Nueva columna `analysis_runs.thresholds_used` (JSONB). Los cortes de un run
pasado eran **irrecuperables**: la unique de `scoring_thresholds` no tiene
versión ni vigencia, el seed **muta la fila in situ**, y `thresholds_version` es
un SHA-256 (detecta deriva, no la reconstruye). Sin esto la pantalla no puede
decir «6,8× frente a un mínimo de 6».

Va en columna propia y no dentro de `verdict` porque son cosas ortogonales: el
dictamen y la vara de medir (lección PHASE-23.1).

### 4. Las señales del veredicto, estructuradas

`QuestionVerdict` gana `signals[]`, `evaluated_count` y `unavailable_count`.
Cada `QuestionSignal` trae `key`, `label`, `kind`, `band`, `value`, `status`,
`counted` y el `reason` de por qué no puntuó — con un invariante en
`__post_init__`: **una señal que no cuenta está obligada a explicarse**.

Resuelve tres cosas de golpe:

1. Antes 8 de las señales eran **la clave en crudo**: el usuario leía literalmente
   `M-Score · B4_dividend_funded_externally` en pantalla.
2. El valor no se podía cruzar con la métrica — ni por clave (no viajaba) ni por
   etiqueta (ya divergían: «M-Score» aquí vs «M-Score de Beneish» en el catálogo).
3. **Verde vs. sin evidencia.** En una financiera los 8 forenses salen
   `not_computable`, ninguna señal de contabilidad se evalúa, y el semáforo cae
   al `else` → la pregunta «¿La contabilidad es de fiar?» pinta **verde por
   ausencia de prueba**. El veredicto no cambia (es la regla del DESIGN), pero
   ahora el cliente **puede detectarlo** y pintarlo gris.

Se conservan `red_signals` / `amber_signals`: los runs ya guardados las tienen.

Nuevo `flag_catalog.py` con las 18 claves de bandera y su nombre legible — hace
falta también cuando la bandera **no** ha saltado, porque «se comprobó y no se
encendió» es justo lo que sostiene un verde.

### 5. El informe deja de morir al recargar

`GET /investment/analysis/{security_id}/runs/latest` devuelve el último run **con
todo el desglose**, misma forma exacta que `runs/{run_id}`. Sin él, aterrizar en
el informe exigía dos peticiones encadenadas: el histórico no trae ningún JSONB.

### 6. Dos arreglos que salieron de la verificación adversarial

- **`stress.not_computable_reason` sólo se rellenaba con la serie vacía.** Cuando
  no se podía estimar el margen de contribución, desaparecían **3 de los 6
  escenarios** y el motivo llegaba `null`: la pantalla no tendría nada que
  pintar. Ahora cada familia que no se puede calcular deja escrito por qué.
- **El gate de `ENGINE_VERSION` no existía.** `version.py` afirmaba desde 44.2
  que *«el golden test falla si el output cambia sin mover esta constante»*; el
  único test que la tocaba comprobaba que fuese semver. La prueba de que hacía
  falta: las capas 1.5, 2, 3, 3.5 y 4 entraron enteras sin moverla de 1.0.0.
  `test_investment_engine_contract.py` fija ahora una **huella de la forma** de
  salida (claves de métrica, de bandera y campos de cada dataclass). Es forma, no
  valores: una fixture actualizada no da rojo espurio, pero renombrar un campo o
  añadir una métrica sí.

`ENGINE_VERSION` → **1.1.0**, con su entrada de historial.

## Archivos clave

| Fichero | Qué |
|---|---|
| `engine/metrics.py` | `MetricUnit` + `unit` obligatorio en `MetricDefinition` |
| `engine/base_ratios.py` | `DUPONT_EM` catalogada y emitida en `_compute_year` |
| `engine/flag_catalog.py` | **nuevo** — las 18 banderas con nombre |
| `engine/synthesis.py` | `QuestionSignal` + señales por clave, no por etiqueta |
| `engine/stress.py` | motivo por familia de escenario no calculable |
| `engine/version.py` | 1.1.0 + historial honesto |
| `fundamentals/canonical.py` | `CanonicalItemDefinition` × 49, `StatementKind`, `ItemGroup` |
| `analysis/{router,schemas,service,repository,models}.py` | 3 endpoints nuevos + `thresholds_used` |
| `alembic/versions/d4e15f9a3b7c62_*.py` | la única migración |
| `tests/test_investment_engine_contract.py` | **nuevo** — el gate de versión y el de banderas |

## Endpoints añadidos

- `GET /investment/analysis/metrics`
- `GET /investment/analysis/{security_id}/runs/latest`
- `GET /investment/fundamentals/items`

Total del módulo: **28**, documentados por primera vez en
[`api/endpoints.md`](../api/endpoints.md) (cubre también la deuda de 44.7/44.8).

## Migraciones

`d4e15f9a3b7c62` — `analysis_runs.thresholds_used` JSONB NOT NULL DEFAULT `'{}'`.
Aditiva. Los runs anteriores quedan con `{}` y **no se pueden explicar
retroactivamente**; la UI lo declarará en vez de fingirlo.

## Verificación

- [x] `pytest -k investment` → **409 passed**
- [x] `ruff` · `black --check` · `mypy app/` (212 ficheros) verdes
- [x] `alembic upgrade head` / `downgrade -1` / `upgrade head` reversibles
- [x] `alembic heads` → **una sola línea** · `alembic check` sin drift
- [x] `pnpm typecheck` verde (el frontend no se ha tocado; los cambios de API son
      aditivos)
- [x] Intérprete del proyecto (`.venv`, Python **3.12.10**), no el del PATH
      (lección PHASE-44.6)

## Decisiones tomadas

- **Manda el motor en los umbrales**, no el cuaderno del usuario. Las 13
  divergencias quedan documentadas en
  [`investment-threshold-divergences.md`](../investment-threshold-divergences.md)
  con qué tocar si algún día se cambian. Decisión del usuario, 2026-07-30.
- **La valoración por múltiplos (hoja 10 del cuaderno) no entra**: el engine no
  recibe precio **por diseño** («un score que se mueve con la cotización no sería
  reproducible al reejecutar un run antiguo», `forensic.py:3-6`) y
  `FINNHUB_API_KEY` está vacía. Se declarará como alcance en la pestaña de
  veredicto, no se fingirá una pestaña vacía.
- `unit` obligatorio sin default, aun a costa de tocar las 52 definiciones: es la
  diferencia entre un catálogo que no puede mentir y uno que sí.

---

# E2-E4 — La pantalla (web)

## Arquitectura

Un **hero persistente** con el titular (identidad, perfil, las cuatro preguntas
de un vistazo, confianza) y **seis pestañas en la URL**:

```
Estados · Ratios · Evolución · Forense · Dividendo ┊ VEREDICTO
```

Se aterriza en **Veredicto**: es lo que el usuario viene a ver, y desde ahí baja
a la evidencia. La pestaña viaja como **query param** (`?tab=&sub=&view=`), no
como segmento de ruta: así F5 conserva dónde estabas, la URL se comparte, y
cambiar de pestaña no desmonta la página ni tira la caché del análisis.

| Pestaña | Contenido | Hoja del cuaderno |
|---|---|---|
| **Estados** | Balance · Cuenta de resultados · Flujo de caja, con conmutador millones / % común / variación | 2, 3 y 4 |
| **Ratios** | Liquidez · Actividad · Solvencia · Rentabilidad · DuPont | 5 a 9 |
| **Evolución** | Las 7 magnitudes año a año, variación interanual, estabilidad y los cruces C1-C8 | los «Vigilar» |
| **Forense** | Los 8 scores con su desglose (M-Score 8 variables, Z'' X1-X4, F-Score 9 tests, C-Score 6 checks) | — |
| **Dividendo** | Cobertura · Calidad de la caja · Soporte del balance · Trayectoria | — |
| **Veredicto** | Dictamen auditable + Confianza y datos | — |

## Las seis reglas de honestidad

Idénticas en las cuatro pestañas que pintan métricas, concentradas en
`metric-rows.ts` para que no puedan divergir:

1. Un `null` en una partida es **HUECO**, nunca 0.
2. Un `not_computable` muestra su razón **visible**, no escondida en un `title=`.
3. Una banda `null` es **gris con «sin banda»**, nunca verde.
4. `approximation` se marca con `*` (input degradado, típicamente sin t−1).
5. Una procedencia distinta de `sourced` se marca (`·` imputado, `†` derivado,
   `≈` estimado).
6. Lo que el cuaderno pide y el motor no calcula se lista **en gris con motivo**,
   nunca se omite: un hueco silencioso se lee como «no aplica».

## El veredicto y su porqué

- **El perfil es un checklist auditable**, no un sello: se imprimen las nueve
  reglas (4 de «Evitar» + 5 de «Conservador») con su ✔/✘ y lo que pasó.
- **Cada pregunta se abre** y enseña la **regla del semáforo impresa** más
  **todas** sus señales candidatas con valor, banda y corte — incluidas las que
  no puntuaron, con su motivo.
- **Verde vs. sin evidencia**: si `evaluated_count` es 0, la pregunta se pinta
  gris con «Sin evidencia» y se dice que el verde sería por ausencia de prueba.
  Es el caso de una financiera, y hasta ahora era indetectable.
- **Alcance declarado**: un bloque que dice qué NO cubre el informe (valoración,
  comparación sectorial, reexpresiones, retribución de directivos) y por qué.

## Componentes nuevos

| Fichero | Qué |
|---|---|
| `components/ui/tabs.tsx` | Nivel 1 accesible (`tablist`, ←/→/Inicio/Fin), scroll interno; sólo monta el panel activo |
| `components/ui/segmented.tsx` | Nivel 2 genérico — el repo tenía 4 `role="tablist"` ad-hoc |
| `investment/year-matrix.tsx` | Matriz concepto × ejercicio, 1ª columna fija, scroll interno |
| `investment/metric-format.ts` | Formateo **por unidad**: un margen se lee «42 %», no «0,42» |
| `investment/metric-index.ts` | Índices O(1) + el corte EFECTIVO (prioriza `thresholds_used` sobre el catálogo) |
| `investment/metric-rows.ts` | Las seis reglas de honestidad, en un solo sitio |
| `investment/band-chip.tsx` | El semáforo, con `null` en gris |
| `investment/flag-list.tsx` | Banderas **agrupadas por clave** — el motor las emite por ejercicio y una dilución de 7 años daba 7 tarjetas idénticas |
| `investment/signal-table.tsx` | Señales de una pregunta con valor, banda y corte |
| `investment/degraded-panel.tsx` | Estados degradados de primera clase |
| `investment/score-breakdown-card.tsx` | Desglose forense, distinguiendo «no tiene por diseño» de «no se pudo calcular» |
| `investment/analysis-hero.tsx` | El titular persistente |
| `investment/tab-*.tsx` | Las seis pestañas |

**Retirados**: `analysis-report.tsx`, `metrics-card.tsx`, `metric-row.tsx`,
`verdict-card.tsx` (grep de consumidores previo en web y móvil; `knip` verde
después).

## Verificación de E2-E4

- [x] `pnpm typecheck` · `pnpm lint` · `pnpm knip` verdes
- [x] `pnpm test`: **133 tests web** (24 ficheros) + 18 móvil + services/ui/store
- [x] Tests nuevos: `tabs.test.tsx` (6 — teclado completo, aria, sólo el panel
      activo montado), `metric-format.test.ts` (13 — las 8 unidades y los
      cortes), `tab-verdict.test.tsx` (9 — checklist, regla del semáforo, señales
      con valor, «ninguna clave cruda», «Sin evidencia», hash completo, motivo
      del stress ausente)

## Limitaciones conocidas

- **Sin paridad móvil.** La pantalla es sólo web; el móvil conserva su vista
  resumida.
- Los runs anteriores a esta fase tienen `thresholds_used = {}` y `signals = []`:
  no se pueden explicar retroactivamente. Basta con reejecutar el análisis — la
  pantalla lo dice en vez de fingirlo.
- El conmutador «% común» no cubre el flujo de caja ni 4 partidas del P&L; se
  avisa en pantalla.
- Las 13 tablas del módulo Inversión siguen sin recoger en
  `data-model/schema.md` (deuda de 44.1, anotada allí).

## Próximo paso

Prueba manual con MCD, Realty Income (socimi) y JNJ: recorrer las seis pestañas,
recargar en cada una, y comprobar que ninguna métrica ausente aparece como hueco
mudo. Después, decidir si se aborda la paridad móvil o la capa de valoración
(que exige API key de precios).
