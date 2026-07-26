# Dónde estamos — 2026-07-26

Punto de continuación tras la sesión del 25-26 de julio. Se lee de arriba abajo;
lo que hay que decidir está al final.

---

## Lo que ha quedado en `origin/main`

Push directo, fast-forward `f34d580..140725d`. Subieron **10 commits de golpe**:
`origin/main` llevaba parada desde PHASE-43, así que con este push viajó la
familia entera del módulo de Inversión, de los cimientos de 44.1 al buscador de
hoy.

Los tres de esta sesión:

| Commit | Qué |
|---|---|
| `8c2927c` | `fix(web)`: pase responsive — rejillas `auto-fit`, `overflowX` en la tabla, formulario de reglas a flex-wrap (19 ficheros) |
| `53f537b` | `chore(dev)`: permisos de herramientas del ciclo |
| `140725d` | `feat(investment)`: módulo completo (44.7) + buscador que deja de adivinar el mercado (44.8 E1) — 102 ficheros |

**Por qué 44.7 y 44.8 comparten commit**: no se podían separar en dos commits
sanos. La E1 modificó ficheros que 44.7 nunca había commiteado —
`catalog/service.py` y `schemas.py` son nuevos y ya importan `capabilities.py` y
leen `analysis_status` — así que un commit de 44.7 «puro» no habría compilado.
Se prefirió un commit honesto con el cuerpo explicando las dos partes a dos
commits de los cuales uno estaría roto.

**Sin verificar**: el CI. `gh` no está instalado en esta máquina, así que **hay
que mirar GitHub Actions**. Dos cosas sólo se ven allí: la migración nueva
aplicada sobre una base limpia desde `f34d580` (en local es reversible, cabeza
única y sin drift) y la instalación de `edgartools==5.43.0` con sus transitivas,
que entran en este push y nunca se han instalado en el runner.

---

## Estado del módulo de Inversión

**El motor está cerrado y funciona.** Seis capas puras, 51 métricas con banda,
y el análisis de MCD verificado a mano en la web: veredicto Evitar por X-Score,
confianza 100%, cinco ejercicios (2021-2025).

**El buscador va por la Entrega 1 de cinco.** Plan completo en
[`improvements/phase-44.8-investment-search-hybrid.md`](improvements/phase-44.8-investment-search-hybrid.md),
decisión en [`decisions/0008-investment-symbol-search.md`](decisions/0008-investment-symbol-search.md).

Verde al cerrar: BE **1091 tests** · mypy 211 ficheros · ruff · black ·
`alembic upgrade/downgrade` reversibles, cabeza única, sin drift · web **105
tests** · móvil 18 · typecheck · lint · knip.

### Datos reales en la BD local

Dos valores, ambos normalizados a su plaza real en esta sesión (estaban con
`exchange='US'`, que es un país):

```
 ticker | exchange |    cik     | analysis_status
--------+----------+------------+-----------------
 JNJ    | NYSE     | 0000200406 | (NULL, anterior a la columna)
 MCD    | NYSE     | 0000063908 | (NULL, anterior a la columna)
```

`NULL` = no comprobado, y la regla responde entonces igual que antes de existir
la columna. Se rellenará solo la próxima vez que se resuelva cada valor.

---

## Lo que sigue, por orden de valor

### 1. Pantalla de estados financieros + DuPont + evolutiva

**Es la petición del usuario y es casi todo frontend.** Verificado contra el run
real de MCD: el motor ya calcula, guarda y sirve mucho más de lo que la pantalla
pinta.

| Ya en la BD y en la API | ¿Se pinta? |
|---|---|
| **DuPont** año a año (`scores_detail.base_ratios.dupont`): margen × rotación × apalancamiento, con sus notas de aproximación | ❌ |
| **Vertical** (common-size) y **horizontal** (año contra año), en `evolution` | ❌ |
| **Stress** (shock de ingresos, de tipos, breakeven), en `verdict.stress` | ❌ |
| **49 partidas** por ejercicio en `financial_statements`, con `GET /investment/fundamentals/{id}/statements` que la web **ya llama** | ❌ |
| Banderas de divergencia y completitud por partida | ❌ |
| 51 métricas con banda | **22** |

O sea: la pantalla muestra ~40% de lo calculado. **Falta el Excel del usuario**
(lo va a pasar) para tres cosas que no se deducen del código: qué fórmulas usa
que el motor no tenga, en qué orden las leía, y si sus umbrales discrepan de los
1.440 sembrados.

### 2. Entrega 2 del buscador — índice de la SEC

Lo que hace falta para que buscar por nombre funcione como la gente escribe. Hoy
sólo se encuentra por ticker exacto o por el nombre literal de la SEC: en la
sesión, `Mac` → `Macdi` → `Macdo` → `Macdod` → `Macdonadl` dieron **cero
resultados**, y sólo `MCD` encontró McDonald's. No es un bug: es `ILIKE` contra
`MCDONALDS CORP`.

Contenido: índice en memoria de los ~10.400 emisores desde el parquet que
`edgartools` ya empaqueta (sin red, sin key, sin tabla nueva), `ranking.py` con
relevancia y alias, colapso por CIK, y `POST /adopt` con `listing_key` opaco.
Criterios de aceptación concretos en el plan (§8, E2).

### 3. Entregas 3-5

El combobox accesible con fila rica (E3), la paridad móvil (E4) y la capa
externa multi-mercado (E5, la que responde a la petición original y la que
arrastra la decisión de licencia).

---

## Decisiones abiertas

1. **¿Twelve Data para el multi-mercado (E5)?** Es la única fuente verificada
   que da símbolo + nombre + bolsa + MIC + divisa + tipo, y funciona sin API
   key, pero su ToS prohíbe cachear en local y prohíbe el uso comercial del plan
   gratis. Para uso personal es defendible; condiciona la feature a que Crisol
   no se comercialice. El canje verificado si algún día se comercializa: EODHD,
   €399/mes uso interno o €2.499/mes con display a clientes.
2. **¿Por dónde seguir?** La pantalla de estados financieros y la E2 del buscador
   son independientes y no se pisan.

---

## Comprobado en esta sesión y cerrado (para no repetirlo)

- **La confianza al 100% con un cierre de hace 207 días NO es un bug.** La
  frescura sí entra en la fórmula (`completitud × factor`), y el corte de
  «fresco» son 274 días (~9 meses). Para datos anuales, el 10-K de 2025 es lo
  más reciente que existe.
- **El buscador no estaba roto en Cartera.** El componente es el mismo que en
  Análisis y funciona; lo que faltaba era feedback por debajo de 2 caracteres —
  se tecleaba una letra y no pasaba nada. Arreglado, con tres tests.
- **`backend/data/` entero se ignora ahora.** La regla anterior nombraba
  `edgar_cache/`, pero `EDGAR_CACHE_DIR` es configurable y las sondas habían
  escrito 5,8 MB de payloads crudos en `edgar_probe_cache/`, a punto de entrar
  en el commit.

## Deuda declarada (en ADR-0008, no se ha olvidado)

- `resolve_security` sigue escribiendo `currency='USD'` y `accounting_std=GAAP`.
  Hoy no mueve ningún número, **pero es un acoplamiento latente**: el 20-F de un
  ADR no entra en el pipeline porque `annual.ANNUAL_FORMS` sólo admite `10-K`. El
  día que alguien añada `20-F` para dar soporte a IFRS, esa etiqueta pasa a ser
  load-bearing de golpe y esos estados se analizarían con cortes calibrados en
  US-GAAP sin decirlo. **Quien toque `ANNUAL_FORMS` arregla `accounting_std` en
  el mismo commit.**
- `pandas` entra como transitiva de `edgartools` y no está declarada en
  `pyproject.toml`. La E2 la necesita para leer el parquet: importarla **dentro**
  de la función, no a nivel de módulo (~1 s en cada arranque).

---

## Arranque rápido

```bash
docker compose up -d                      # postgres + minio + ollama
cd backend && .venv/Scripts/python.exe -m alembic upgrade head
cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8002
pnpm dev:web                              # http://localhost:3000
```

El backend va en **8002**, no en 8000: es lo que espera `BACKEND_ORIGIN` de
`apps/web/.env.local`. Con el 8000 del Makefile, `/api/*` devuelve 500.

Verificación (siempre con el intérprete del proyecto, nunca el del PATH):

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q    # ~11,5 min
cd backend && .venv/Scripts/python.exe -m mypy app/ && .venv/Scripts/python.exe -m ruff check app tests scripts
pnpm typecheck && pnpm lint && pnpm test && pnpm knip
```
