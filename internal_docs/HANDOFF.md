# Dónde estamos — 2026-07-31

Punto de continuación tras la sesión del 30-31 de julio. Se lee de arriba abajo;
lo que hay que decidir está al final.

---

## Lo primero al retomar

**Hay trabajo terminado y SIN COMMITEAR: 63 ficheros.** Es PHASE-44.9 entera
(backend + web). Está verde en todas las verificaciones automáticas, pero **falta
tu prueba manual** — y la convención del proyecto es no commitear hasta que la
des por buena.

`origin/main` sigue en `d98c96f`. El árbol de trabajo tiene 35 ficheros
modificados y 28 nuevos.

Si al abrirlo algo no cuadra, **no empieces por el código**: la migración nueva
ya está aplicada a la BD local y Docker quedó levantado.

---

## Qué se hizo en esta sesión

### 1. Se transcribió el cuaderno del usuario

El Excel `Analisis empresas.xlsx` resultó ser una **guía de metodología, no un
modelo**: no tiene ni una fórmula viva sobre cifras de empresa (las dos únicas
son los *checks* de DuPont) y las series de sus 10 gráficos apuntan a un libro
del escritorio del usuario. Sus 10 hojas están transcritas —imágenes incluidas,
que la hoja de Valoración es sólo capturas— en
[`ai-context/excel-analisis-empresas.md`](ai-context/excel-analisis-empresas.md).

**El `.xlsx` NO se versiona**: era material de referencia, no del proyecto. Se
añadió al `.gitignore` junto al patrón `~$*` de los bloqueos de Office (el `*~`
que había casa por sufijo, no por prefijo, así que el fichero de bloqueo estaba
a un `git add .` de entrar en el commit).

### 2. PHASE-44.9 — el informe con pestañas

**Backend** (E1): el catálogo de las 52 métricas y las 49 partidas viajan por API
con etiqueta y unidad · `analysis_runs.thresholds_used` persiste los cortes
efectivos · `QuestionVerdict.signals[]` con valor, banda y motivo de las que no
puntúan · `GET /runs/latest` · `DUPONT_EM` catalogada · gate de `ENGINE_VERSION`
(que el docstring afirmaba desde 44.2 y **no existía**) · `ENGINE_VERSION` a
**1.1.0**.

**Web** (E2-E4): hero persistente + seis pestañas en la URL (Estados · Ratios ·
Evolución · Forense · Dividendo · Veredicto) · matriz métrica × ejercicio
multi-año · formato por unidad · el perfil como checklist auditable. Retirados
`analysis-report`, `metrics-card`, `metric-row` y `verdict-card`.

Detalle completo en
[`phases/phase-44.9-analysis-report-contract.md`](phases/phase-44.9-analysis-report-contract.md).

### 3. `docs-check` — el detector de podredumbre documental

Al revisar si la deuda estaba documentada salió que `backlog.md` llevaba días
afirmando cosas falsas. Es la **séptima** vez que pasa lo mismo en este proyecto,
y la lección ya estaba escrita dos veces, así que se aplicó la otra regla del
fichero: mover la fuente de verdad en vez de añadir otro guardarraíl.

`scripts/check_docs.py` (stdlib pura) comprueba en cada `make verify`, en
`pnpm docs:check` y en CI: enlaces relativos que resuelvan · revisiones de
Alembic citadas que existan · que quien declare un head nombre el head real ·
que los documentos **vivos** no lleven números volátiles.

La distinción que lo hace útil: una phase doc es una **foto fechada** y tiene
derecho a envejecer; `backlog.md` y este fichero describen el AHORA y no.

### 4. Documento de divergencias de umbrales

Decisión del usuario: **manda el motor**, pero las 13 divergencias con su
cuaderno quedan escritas en
[`investment-threshold-divergences.md`](investment-threshold-divergences.md),
ordenadas por coste de adopción — cuatro son gratis (una fila en
`scoring_thresholds`), dos exigen ADR porque cambiarían veredictos.

---

## Los defectos que esta fase cerró

Sirven para entender por qué el cambio es tan grande:

| Defecto | Estado |
|---|---|
| La pantalla pintaba **22 de 52** métricas, y todas del último ejercicio | ✅ matriz multi-año completa |
| El informe vivía en una **mutación** y desaparecía al recargar | ✅ lee el run persistido |
| Tres etiquetas **mentían** sobre su número (F5, F6, D8) | ✅ catálogo por API + test |
| Un margen del 42 % se imprimía **`0,42`** | ✅ formato por unidad |
| Ocho señales del veredicto salían como **clave cruda** en pantalla | ✅ con test de regresión |
| Los cortes de un run pasado eran **irrecuperables** | ✅ `thresholds_used` |
| Una financiera pintaba **verde por ausencia de prueba**, indetectable | ✅ «Sin evidencia» |
| El stress perdía 3 de 6 escenarios **sin decir por qué** | ✅ motivo por familia |
| El gate de `ENGINE_VERSION` estaba **declarado y no existía** | ✅ huella de la forma |

---

## Estado de verificación

**Todo verde**, con el intérprete del proyecto (`.venv`, Python 3.12.10 — el
mismo que CI):

- Backend: la suite completa · `ruff` · `black` · `mypy` · `alembic
  upgrade`/`downgrade`/`upgrade` reversibles, **una sola cabeza**, sin drift.
- Frontend: `typecheck` · `lint` · `knip` · los tests de web, móvil, services,
  ui y store.
- Documentación: `make docs-check` (enlaces, migraciones citadas, head declarado
  y números volátiles).

Los recuentos exactos salen de `make verify`; aquí no se escriben a propósito —
un número que cambia cada fase no puede vivir en un documento que describe el
presente, y este fichero es justo eso. Las cifras de una fase concreta están en
su phase doc, que sí es una foto fechada.

Head de Alembic: `d4e15f9a3b7c62`. Engine: `1.1.0`.

**Lo que NO se ha verificado**: la prueba manual, y el CI de GitHub Actions —
`gh` sigue sin estar instalado en esta máquina, así que el push anterior
(`140725d`) tampoco se llegó a comprobar allí. Dos cosas sólo se ven en el
runner: la migración sobre base limpia y la instalación de `edgartools` con sus
transitivas.

---

## Lo siguiente, por orden

### 1. Probar la pantalla (es el paso que bloquea el commit)

```bash
docker compose up -d                      # ya estaba levantado al cerrar
cd backend && .venv/Scripts/python.exe -m alembic upgrade head   # ya aplicada
cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8002
pnpm dev:web                              # http://localhost:3000
```

El backend va en **8002**, no en 8000: es lo que espera `BACKEND_ORIGIN` de
`apps/web/.env.local`. Con el 8000 del Makefile, `/api/*` devuelve 500.

Recorrido sugerido: **MCD** (le falta `cogs`, así que varias métricas salen no
calculables con su motivo), **Realty Income** (socimi: balance no clasificado, la
liquidez casi entera cae) y **JNJ**. En cada uno: las seis pestañas, recargar en
cada una, y comprobar que ninguna métrica ausente aparece como hueco mudo.

**Importante**: los análisis ya guardados salen sin señales ni umbrales — se
ejecutaron antes de que el motor los publicara. Hay que pulsar «Volver a
analizar» para ver el dictamen completo. La pantalla lo declara en vez de
fingirlo.

### 2. Commit

Cuando dé el visto bueno. Mensaje en inglés, `— Refs: PHASE-44.9`.

### 3. Después, a elegir

- **Paridad móvil** de la pantalla nueva (hoy el móvil conserva su vista
  resumida).
- **Entrega 2 del buscador** (PHASE-44.8): el índice en memoria de los ~10.400
  emisores de la SEC. Hoy buscar «Macdonald» da cero; sólo funciona el ticker
  exacto. Plan en
  [`improvements/phase-44.8-investment-search-hybrid.md`](improvements/phase-44.8-investment-search-hybrid.md).
- **Capa de valoración**, si se activa una API key de precios (ver decisiones).

---

## Decisiones abiertas

1. **¿Twelve Data para el multi-mercado?** (E5 del buscador, viene de la sesión
   anterior). Única fuente verificada con símbolo + nombre + bolsa + MIC + divisa
   sin API key, pero su ToS prohíbe cachear en local y el uso comercial del plan
   gratis. Para uso personal es defendible; condiciona la feature a que Crisol no
   se comercialice. Canje verificado: EODHD, €399/mes uso interno.
2. **¿Se activa Finnhub para la valoración?** La hoja 10 del cuaderno (PER,
   P/Ventas, P/VC, P/FCF, EV/EBITDA, Gordon) necesita precio de mercado. El
   engine **no lo recibe por diseño** —un score que se mueve con la cotización no
   sería reproducible— así que tendría que ser una capa **fuera** del
   `AnalysisRun`. Además la comparativa «vs sector» del ejemplo
   Donaldson/Evoqua no tiene fuente en el proyecto.
3. **¿Se adopta algún umbral del cuaderno?** Ver el documento de divergencias.
   Cambiar una banda cambia el veredicto de los runs futuros: exige ADR.

---

## Deuda declarada

**Vive en [`backlog.md`](backlog.md), sección «Módulo Inversión»** — ese es el
sitio durable. Este fichero se reescribe entero cada sesión, así que lo que sólo
se anote aquí se pierde; el 2026-08-01 se descubrió que dos entradas del backlog
llevaban días diciendo cosas que habían dejado de ser ciertas.

Lo más punzante, para no tener que abrirlo:

- **`resolve_security` escribe `currency='USD'` y `accounting_std=GAAP` para
  todo.** Inocuo hoy, **load-bearing el día que alguien admita `20-F`** en
  `annual.ANNUAL_FORMS`: se analizarían cuentas IFRS con cortes calibrados en
  US-GAAP sin decirlo. Quien lo toque, lo arregla en el mismo commit.
- **Cuatro piezas del motor construidas y sin cablear** (`maintenance_capex`,
  `wc_operating`, `wc_total`, `total_debt_incl_leases`). El cuaderno del usuario
  pide tres de ellas. Es el arreglo más barato de la lista.
- Las **13 tablas del módulo** siguen fuera de `data-model/schema.md`.

---

## Comprobado y cerrado (para no repetirlo)

- **jest-dom no está en el proyecto.** Los tests web usan `toBeTruthy()`,
  `toBeNull()` y `getAttribute()`, no `toBeInTheDocument()`.
- **`exactOptionalPropertyTypes` sigue mordiendo**: una prop opcional que vaya a
  recibir `undefined` explícito del padre se declara `prop?: T | undefined`.
- **La forma del JSONB del run se comprobó ejecutando el motor**, no leyendo las
  dataclasses. Los tipos TS de `AnalysisRun` ya no son un saco con index
  signature.

---

## Verificación completa

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q    # ~12 min
cd backend && .venv/Scripts/python.exe -m mypy app/
cd backend && .venv/Scripts/python.exe -m ruff check app tests scripts
cd backend && .venv/Scripts/python.exe -m black --check app tests scripts
pnpm typecheck && pnpm lint && pnpm test && pnpm knip
```

Nunca dos `pytest` a la vez: `crisol_test` es una sola base compartida.
