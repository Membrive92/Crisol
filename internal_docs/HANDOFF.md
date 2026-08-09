# Dónde estamos — 2026-08-08

Punto de continuación tras las sesiones del 7 y el 8 de agosto. Se lee de arriba
abajo; lo que hay que decidir está al final.

---

## Lo primero al retomar

**Hay trabajo terminado y SIN COMMITEAR: cuatro fases.** Está verde en todas las
verificaciones automáticas, pero **falta tu prueba manual** — y la convención del
proyecto es no commitear hasta que la des por buena.

- **PHASE-44.13**: el cron de tasas, la Entrega 2 del buscador y la paridad
  móvil del informe.
- **PHASE-44.14**: el directorio oficial UE/UK (FIRDS) y el alta validada — la
  Entrega 5 del buscador.
- **PHASE-44.15**: las Entregas 3 y 4 (combobox accesible + alta de compra en
  móvil), que **cierran PHASE-44.8 entera**, y cuatro deudas — entre ellas la
  mina del `accounting_std`, que llevaba tres fases con un «arréglalo el día que
  alguien toque `ANNUAL_FORMS`».
- **PHASE-44.16**: el informe tolera análisis de motores anteriores. Sale del
  404 que reportaste en McDonald's. Sólo frontend — el backend no se toca.

**Y hay más pendiente de lo que decía esta línea antes.** El `main` local está en
`926ae61` y va **5 commits por delante de `origin/main`**: PHASE-44.9 a 44.12
están commiteadas pero **nunca se empujaron**. Así que lo pendiente de subir son
esas cinco más las cuatro fases sin commitear. (El ref de `origin` es del
26-jul; conviene un `git fetch` antes de dar por buena la comparación.)

**Se han tocado tus datos reales**, con tu autorización y de forma auditada:

1. `exchange_rates` gana las tasas del 24-jul, 06-ago y 07-ago, que faltaban.
2. El lote de JNJ pasa de `fx_rate_at_trade = 1` a `0.87896634` — el tipo real
   del BCE del día de la compra.
3. `listing_directory` sembrada con **3.012 valores** de ESMA y la FCA (tabla
   nueva, no toca nada existente). **Hay migración**: `alembic upgrade head`.

---

## Qué se hizo en esta sesión

### 1. El cron de tasas llevaba mudo desde PHASE-11.1

Dos defectos independientes que hacían inútil el job: un canario que se conforma
con cualquier tasa de los 14 días anteriores, y un timeout de 10 s cuando una
petición histórica tarda 13-17. La huella estaba en tu BD: **una fecha cada ~15
días**, el ancho exacto de la ventana de fallback.

### 2. Buscador — Entregas 2 y 5

- **E2**: índice en memoria de los **10.365 emisores** de la SEC, sin red.
  `Macdonald` encuentra McDonald's.
- **E5**: directorio **FIRDS** (ESMA + FCA) en tabla propia, sembrado por un
  comando idempotente. Inditex, Iberdrola y Allianz **salen de verdad**, y el
  alta valida la identidad registral contra una cotización real antes de
  persistir nada. Twelve Data descartada: su licencia prohíbe cachear y el uso
  comercial ([ADR-0010](decisions/0010-identity-official-registers.md)).

Esto cierra la mitad que faltaba del multi-mercado: cotizar un valor de Madrid
existía desde 44.11, pero **no había forma de crearlo**.

### 3. Paridad móvil del informe

El móvil pintaba las señales del veredicto **en crudo** y los márgenes como
`0,42`. Ahora tiene las siete pestañas, consumiendo la misma capa pura que la
web desde `packages/ui` — no hay dos implementaciones que puedan divergir.

### 4. El 404 de McDonald's (PHASE-44.16)

Lo reportaste probando la app: pulsar una de «Las cuatro preguntas» en MCD tiraba
la pantalla. Es el único valor analizado antes de PHASE-44.9, con el motor
**1.0.0**, y su run no trae los campos que la pantalla daba por seguros.

El crash resultó ser lo de menos. La misma ausencia hacía que el cuadre del
DuPont pintara **«NaN» en rojo** afirmando «hay un problema en los datos o en una
fórmula» —un descuadre contable inexistente en cuentas reales— y que seis
métricas que aquel motor no emitía se anunciaran como «no calculable con los
datos disponibles», **culpando a los balances de McDonald's** de un hueco del
motor. Un crash se reporta; una frase con aspecto de dato se cree.

Ahora el informe declara que el análisis es de una versión anterior, ofrece
reejecutarlo, y cada hueco dice de quién es la carencia. Los tipos pasan a
describir la unión de todas las versiones guardadas, que es lo que de verdad hay
en la tabla — con eso el compilador enumeró él solo los ocho accesos inseguros.

---

## Estado de verificación

**Todo verde**, con el intérprete del proyecto (`.venv`, el mismo que CI):

- Backend: la suite completa · `ruff` · `black` · `mypy` · migración
  `upgrade`/`downgrade` reversible, cabeza única, `alembic check` sin drift, y
  **la cadena entera aplicada sobre una base creada desde cero** (lo que suele
  verse sólo en CI; la extensión `pg_trgm` es nueva y era el candidato a fallar
  allí por permisos).
- Frontend: `typecheck` · `lint` · `knip` · los tests de web, móvil, services,
  ui y store.
- La cadena del alta europea, contra los proveedores **reales**: `ES0148396007`
  → `ITX.MC` → cotización en EUR, que es la divisa que dice el registro.

Los recuentos exactos salen de `make verify`; aquí no se escriben a propósito.
Las cifras de cada fase están en su phase doc, que sí es una foto fechada.

**Lo que NO se ha verificado**: tu prueba manual, y el CI de GitHub Actions
(`gh` sigue sin estar instalado en esta máquina). **Y una cosa más**: la revisión
adversarial multi-agente de la E5 **no llegó a ejecutarse** — los cinco agentes
murieron por límite de sesión. Se sustituyó por una autorrevisión, que encontró
un hueco real de cobertura (el borrado del sync no se ejecutaba en ningún test) y
lo cerró con tres tests. No es lo mismo que la revisión cruzada: si quieres esa
red, se puede lanzar en otra sesión.

---

## Decisiones abiertas (ninguna resuelta)

Se plantearon el 2026-08-09 con recomendación y quedaron sin respuesta. Las dos
primeras desbloquean trabajo; las otras tres no frenan nada.

| # | Decisión | Recomendación |
|---|---|---|
| 1 | **Q2 y Q3 en financieras.** 44.19 eximió D2-D5 y D8 por dividir entre caja libre. `Q2` = caja libre/EBITDA tiene el mismo problema. `Q3` es una comprobación de *consistencia* entre dos cálculos, no un nivel | Eximir **Q2**; **Q3 la decides tú**. `Q1` y `Q5` son válidas en un banco |
| 2 | **Subir `ENGINE_VERSION` a 1.4.0.** 44.19 cambió lo que un run significa para una financiera sin mover la versión, y eso dejó escrita una premisa que caduca | **Subir y reejecutar JNJ y MCD.** Si no, JNJ enseña un aviso de run caducado por un cambio que no le afecta. Reejecutar MCD **es** la prueba manual de 44.16 |
| 3 | **Cuándo una pregunta deja de presumir de verde.** Hoy es `evaluated_count === 0`, todo o nada; MCD sale verde con 3 señales de 10 | **No una proporción**: declarar qué señales son *portantes* por pregunta. Cuáles, lo decides tú |
| 4 | **`knip` y `make verify` en CI.** CI **no los ejecuta**, pese a que la lección de PHASE-43 dé knip por cableado | Arreglarlo como fase aparte y pequeña |
| 5 | **Partir PHASE-44.17.** Tres piezas suyas están contrastadas y no dependen del rediseño de las banderas | Entregar esas tres ya; banderas y contadores, después |

Detalle de la 5 y de por qué 44.17 está bloqueada:
[`improvements/phase-44.17-metric-honesty-and-parity.md`](improvements/phase-44.17-metric-honesty-and-parity.md) §3.1.b.

---

## Lo siguiente, por orden

### 1. Probar (es el paso que bloquea el commit)

```bash
docker compose up -d
cd backend && .venv/Scripts/python.exe -m alembic upgrade head
cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8002
pnpm dev:web
```

El backend va en **8002**, no en 8000: es lo que espera `BACKEND_ORIGIN` de
`apps/web/.env.local`.

**Buscador** (web y móvil): teclea `Macdonald`, `santander`, `inditex`, `ITX`,
`iberdrola`, `allianz`, `Iberdola` (con errata) y `NESN`. Lo que debe pasar:
McDonald's aparece pese a la falta de ortografía · Inditex sale con XMAD/EUR/ISIN
y sin ticker inventado · la errata encuentra igual · `NESN` explica la frontera
suiza en vez de dejar el hueco en blanco.

**Alta europea**: elige Inditex → debe crear el valor con ticker `ITX`, plaza
`XMAD`, divisa `EUR` y sin análisis disponible (no tiene CIK). Si el proveedor no
resuelve el ISIN, aparece el formulario pidiendo el símbolo local.

**Buscador con teclado** (web, sin tocar el ratón): teclea, baja con ↓ y elige
con Enter. En **Análisis**, `spy` debe salir apagado con el motivo escrito
debajo y no dejarse elegir; en **Cartera**, el mismo `spy` sí.

**Informe en móvil**: elegir un valor, ejecutar el análisis y recorrer las siete
pestañas. Ninguna señal debe salir como clave cruda; los porcentajes se leen como
porcentajes. En Estados, probar los tres modos (Importe / % común / Variación).

**Alta de compra en móvil**: la pestaña Cartera ya no manda a la web. Buscar un
valor, cantidad con **coma** (`12,5`), precio y fecha → debe aparecer la posición.

**El informe de McDonald's** (el 404 que reportaste): abre `/investments` → MCD →
Análisis. Arriba debe salir un aviso de que el análisis lo calculó el motor 1.0.0
con un botón para reejecutarlo. En **Veredicto**, las cuatro preguntas ya no
ofrecen flecha para desplegar —no hay nada detrás— y salen marcadas «No
auditable» con sus señales en rojo/ámbar traducidas. En **Ratios → DuPont**, la
fila «Comprobación» no puede decir «NaN» ni acusar de un descuadre, y las
métricas ausentes deben decir que no existían en aquel motor, no que falten datos
de la empresa. Si pulsas «Volver a ejecutar», el aviso desaparece y el informe
sale completo — ése es el contraste que lo prueba.

**Precios de 44.11 contra tu bróker** — sigue pendiente y no es delegable.

### 2. Commit

Cuando des el visto bueno. Mensaje en inglés, `— Refs: PHASE-44.13` y
`PHASE-44.14` (o dos commits, uno por fase: son separables).

### 3. Refrescar el directorio, cuando toque

```bash
cd backend && .venv/Scripts/python.exe -m scripts.seed_listing_directory
```

Manual, trimestral o a demanda. **Sin cron** (local-first). Una salida a bolsa
posterior al último seed cae en el alta manual hasta que lo re-ejecutes; la
pantalla declara la fecha del último seed.

---

## Decisiones abiertas

1. **¿ETFs en el directorio?** Ya decidido que NO ahora. Cuando entren: añadir
   `'CE'` a `INCLUDE_CFI_PREFIXES`, re-sembrar, ampliar el enum `security_type`
   y mantener el invariante de que ningún tipo entra en el motor de otro.
2. **¿Se adopta algún umbral del cuaderno?** Ver
   [`investment-threshold-divergences.md`](investment-threshold-divergences.md).
   Cambiar una banda cambia el veredicto de los runs futuros: exige ADR.

---

## Deuda declarada

**Vive en [`backlog.md`](backlog.md), sección «Módulo Inversión»** — ese es el
sitio durable. Este fichero se reescribe entero cada sesión.

Lo más punzante, para no tener que abrirlo:

- **Suiza es frontera documentada**: SIX no reporta a FIRDS, así que Nestlé,
  Roche y Novartis sólo entran por alta manual o por su ADR estadounidense.
- **Sin charts en el informe**, ni en web ni en móvil: es lo único grande que
  sigue siendo «todo en tablas» (evolución common-size, stress, heatmap de Δ%).
- El **alta `ext:` exige red** (resolución del símbolo + cotización real). Es
  deliberado —nada se persiste sin verla— pero sin conexión no hay alta europea,
  mientras que la búsqueda sí funciona offline.

Cerradas en esta sesión y ya fuera del backlog: la mina del `accounting_std`
(ahora se deriva de la evidencia), las 14 tablas en `schema.md`, `pandas`/`lxml`
declaradas y el ranking del buscador.

---

## Comprobado y cerrado (para no repetirlo)

- **jest-dom no está en el proyecto.** Los tests web usan `toBeTruthy()`,
  `toBeNull()` y `getAttribute()`, no `toBeInTheDocument()`.
- **`exactOptionalPropertyTypes` sigue mordiendo**: una prop opcional que vaya a
  recibir `undefined` explícito del padre se declara `prop?: T | undefined`.
- **El índice de emisores no hace red.** En los tests está VACÍO por defecto
  (`conftest`, `autouse`); quien lo necesite usa el marcador `real_symbol_index`.
- **Las fechas históricas de Frankfurter tardan 13-17 s.** No es un fallo de red:
  es la API. Por eso el camino de fondo tiene su propio timeout.
- **FIRDS reporta en MICs de SEGMENTO**, no operativos: Allianz está en `XETA`,
  nunca en `XETR`. La normalización vive en `catalog/firds.py` y hay un test que
  ata lo sembrable con lo cotizable.
- **El FULINS de la FCA trae venues europeos** (Commerzbank en XETR). La
  partición es jurisdiccional, no por fichero.

---

## Verificación completa

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q    # ~12 min
cd backend && .venv/Scripts/python.exe -m mypy app/
cd backend && .venv/Scripts/python.exe -m ruff check app tests scripts
cd backend && .venv/Scripts/python.exe -m black --check app tests scripts
pnpm typecheck && pnpm lint && pnpm test && pnpm knip
python scripts/check_docs.py
```

Nunca dos `pytest` a la vez: `crisol_test` es una sola base compartida. Y eso
incluye los que lance un subagente.
