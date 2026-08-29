# Dónde estamos — 2026-08-27

Punto de continuación tras las sesiones del 20-23 de agosto. Se lee de arriba
abajo; lo que hay que decidir está al final.

---

## Lo primero al retomar

**Hay siete entregas verdes esperando tu prueba manual, y sólo tres están
commiteadas.** Commiteadas: 47.I, 47.J y 48 (`a6bd7aa`, `c49ba05`, `9b09c0f`).
**Sin commitear, en el árbol de trabajo**: 47.H-2ª, 47.E4, 44.23 y **PHASE-44.24
entera** (siete entregas: A · M · C · B · D · E · F · G). Nada se ha probado
contra la app en marcha.

> **44.24 toca sólo el módulo de Inversión** salvo dos cosas: `item_label()` en
> el engine y una regla `@media print` en `globals.css` (que no existía y por
> tanto no puede regresar nada). Las finanzas domésticas no se tocan.

| Entrega                                                          | Qué                                                                                                                                 |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| [47.I](phases/phase-47.I-declarations-survive-reimport.md)       | Una declaración manual sobrevive a una reimportación · el cargo de tarjeta sabe de cuál viene                                       |
| [47.J](phases/phase-47.J-a-statement-date-is-a-civil-date.md)    | Una fecha de extracto es una fecha CIVIL (469 de 491 filas estaban desplazadas un día)                                              |
| [48](phases/phase-48-the-user-defines-the-month.md)              | El día en que cobras REDEFINE qué es un mes en toda la app                                                                          |
| [47.H · 2ª entrega](phases/phase-47.H-a-refund-is-not-income.md) | El signo de una devolución llega a la pantalla: la lista de movimientos ya no suma distinto que su total                            |
| [47.E4](phases/phase-47.E-deferred-receipt.md)                   | El desglose dice QUÉ categorías están aplazadas (asterisco por fila) y su aviso describe lo que hay en pantalla, también con filtro |
| [44.23](phases/phase-44.23-report-glossary.md)                   | **Inversión**: una «i» por fila en todo el informe — 113 definiciones escritas contra la fórmula del motor                          |
| **[44.24](improvements/phase-44.24-report-legibility-implementation-plan.md)** | **Inversión**: el informe deja de demostrar sin explicar. Motor **1.7.0**. Ver abajo                                  |

> La 2ª entrega de 47.H pasó por revisión adversarial (**4/4 lentes vivas**, 26
> hallazgos brutos, 8 confirmados). Encontró un TERCER emisor del cubo de gasto
> que se me había escapado y que su gate no podía ver, y demostró —ejecutándolas—
> cuatro formas normales de reintroducir el defecto con el gate en verde. Todo
> arreglado; el detalle está en la phase doc.

### Cómo probarlo

1. `.\dev.ps1` — **reinicia**: el backend en marcha puede ser anterior a estos
   cambios, y eso ya nos costó una sesión entera de diagnóstico.
2. Ajustes → desmarca «Modo predeterminado» → elige tu día → Guardar. La
   previsualización enseña qué cae a cada lado ANTES de guardar.
3. Análisis: el toggle es «Mes / Año / Personalizado», sin chip. Comprueba que
   cuadran entre sí la proyección de fin de mes (los días restantes cuentan
   hasta TU corte), los presupuestos, el DTI de Deuda y el chart.
4. Transacciones: pulsa un chip de mes — debe darte tu período, no del 1 al 31.
5. Análisis → pincha una categoría con devoluciones (p. ej. «Suscripciones» en
   tu período de julio): el reembolso de 1,50 € sale en verde, marcado
   «Devolución» y **con su signo**, y ahora la columna suma los 184,95 € del
   total de arriba en vez de 187,95 €.
   La misma marca aparece ahora en «Top movimientos del periodo» de Análisis,
   que salía sin ella: esa tarjeta también lista el cubo de gasto, y una
   devolución tuya se quedó a **dos euros** de encabezarla en junio.
6. Análisis → junio, «Desglose de gastos»: las categorías con gasto aplazado
   llevan ahora un **asterisco** (pasa el ratón por encima para ver cuánto).
   Y el aviso de arriba cambia al pulsar Fijo o Variable, porque describe lo
   que hay en pantalla: 496,67 € en «Todo», 245,53 € en «Fijo», 251,14 € en
   «Variable». Antes decía 496,67 € en las tres.
7. Inversión → Análisis → cualquier pestaña: cada fila lleva un `ⓘ` que
   despliega qué es esa métrica o esa partida. Empieza por Estados → Balance,
   que es donde más falta hacía: 49 filas de las que varias son deducidas por
   la app y no vienen del filing, y ahora lo dicen.

### Lo que ya sabemos que verás distinto

- El chart de Ingresos vs Gastos son **12 barras de tu año** (12-ene → 11-ene),
  no del año natural. Los días 1..D−1 de enero caen en tu año anterior.
- **Un solo aviso** en Análisis de móvil, bajo la evolución de patrimonio: es la
  única tarjeta que sigue en meses naturales (su serie son 12 meses fijos).
- El tooltip de cada barra dice el rango exacto («12 dic – 11 ene»).
- Un reembolso sale con **signos distintos** en dos sitios, y es a propósito: en
  Transacciones con `+` (ese dinero entró en la cuenta, y así cuenta al saldo) y
  en el desglose de su categoría con `−` (deshace una compra). Las dos salen del
  mismo `flow`; lo que cambia es la pregunta.

### Lo que sigue pendiente de antes

1. **Un clic**: «Es una financiación» para re-enlazar el abono de 700,26 € del
   6-jul con su deuda. No mueve ningún número; deja declarado el origen.
2. **Importar agosto** cuando esté.
3. **Las tablas de respaldo** `_bak_civil_dates_20260822` y
   `_bak_civil_paid_at_20260822` guardan las fechas anteriores al arreglo de
   47.J. Bórralas cuando lo des por bueno.
4. **Orden obligatorio si se tocan datos**: arreglar → re-anclar → y sólo
   entonces reimportar.

### La lección de estas sesiones

Una revisión adversarial encontró **nueve defectos** en el trabajo de 48, cinco
de ellos introducidos en ese mismo trabajo y cuatro en cosas ya declaradas
arregladas. Ninguno era visible con la suite en verde. Y la primera vez que se
lanzó **no llegó a ejecutarse** —las cinco lentes murieron por límite de
sesión— devolviendo un resultado indistinguible de una revisión limpia; el
script ahora reporta cuántas lentes trajeron resultado, para que «cero
hallazgos» y «cero ejecuciones» no se confundan.


### PHASE-44.24 — qué mirar cuando la pruebes

Abre un valor analizado (MCD es el que tiene un run **viejo**, de motor 1.0.0:
sirve para ver que el informe tolera lo que no trae).

1. **Las fichas.** Pulsa la `ⓘ` de una fila cualquiera: debe abrir «qué mide»,
   «por qué importa» y «cómo se lee», en tres tramos. En móvil se abre **tocando
   la etiqueta**, que es el único afordance sin ratón.
2. **La distancia al corte.** En el Veredicto, cada señal dice a cuánto está de
   su umbral y **con qué vara** se mide (genérica, del sector, de financiera…).
   Las rojas van primero.
3. **La tendencia.** Cada matriz tiene una columna nueva a la derecha. Una serie
   de menos de tres ejercicios debe decir «serie corta», no quedarse en blanco.
4. **El desglose de scores.** En Forense, cada score enseña sus variables con
   cuánto se han movido desde el ejercicio anterior. **En móvil esto es nuevo
   entero**: antes no había ningún desglose.
5. **«Cómo leer este informe».** Enlace en el hero (web) / hoja modal (móvil).
6. **Qué ha cambiado.** Veredicto → tercera sub-pestaña. Con un solo análisis
   debe decir que todavía no hay con qué comparar; con dos, la lista de cambios,
   y si se hicieron con motores distintos **no debe listar ni un cambio de la
   empresa** — sólo qué cambió del método.
7. **El dictamen imprimible.** Botón en el hero → `?print=1` → Ctrl+P. Sin barra
   lateral, sin pestañas, fondo blanco, y con las tres versiones en la cabecera.

> **Seis defectos ya corregidos por una revisión adversarial** cuyos
> verificadores murieron por límite de sesión (devolvió `confirmados: 0`, que es
> lo mismo que devuelve una revisión limpia — los verifiqué a mano y los seis
> eran reales). Los que más te tocan al probar: elegir un análisis del histórico
> ya no dice «todavía no se ha ejecutado ninguno», el dictamen imprimible
> conserva el análisis que estás mirando, y cuando no se puede comparar te dice
> POR QUÉ en vez de una frase fija. Detalle en la phase doc.

> **Tu primera pasada ya encontró cosas** —«enlaces que no llevan a ningún
> sitio, cards que no se ajustan»— y salió de ahí una auditoría con **33
> defectos reales** corregidos:
> [PHASE-44.24.H](phases/phase-44.24.H-ux-audit-fixes.md). Lo que debería
> haber cambiado a la vista: las banderas del veredicto **ya no son enlaces**
> (no llevaban a ninguna parte), las señales navegan sin recargar la página,
> la prosa de las cards mide lo mismo que en Deuda, el buscador de Análisis va
> a ancho completo, la guía tiene «← Volver al informe», y el dictamen
> imprimible **abre el diálogo de impresión solo** sin arrastrar el sidebar.
> En móvil: la pestaña activa siempre a la vista, elegir un análisis del
> histórico ya no hace desaparecer la pantalla, y las señales se tocan.

Lo que más me interesa que mires: **si alguna frase del informe suena a jerga
del motor**. La pasada de copy tradujo lo que encontré, pero el catálogo de
razones es largo y sólo se ve con datos reales delante.

---

## (anterior) Lo primero al retomar

**Hay dos entregas commiteadas y verdes esperando tu prueba manual: 47.A y
47.E.** La segunda es la que arregla el descuadre que destapaste el día 15 —el
recibo de la tarjeta que se financia y suma deuda sin restar nada— y su detalle
está en [`phases/phase-47.E-deferred-receipt.md`](phases/phase-47.E-deferred-receipt.md).

### 47.E, en una frase

Tu regla, tal cual la dijiste: _«no aparecen porque se han aplazado, pero se
cuentan en categorías porque el gasto existe, lo único que está aplazado»_. El
resultado del mes mide **caja** y excluye las compras aplazadas; el desglose por
categorías mide **gasto** y las mantiene; y la pantalla dice la diferencia,
porque a partir de aquí las dos cifras no cuadran a propósito.

Con tres cosas más que salieron del camino:

- El recibo que BBVA escribe de dos formas deja de entrar 2-4 veces. Medido en
  tu BD: **~20 filas que venías borrando a mano** en siete meses. Y sin comerse
  el par de financiación, que tiene la misma forma (mismo importe, mismo día) y
  es el hecho contrario.
- El cargo agregado de la tarjeta alcanza por fin al recibo aplazado.
- Eso destapó que **tu préstamo amortiza sólo porque el recibo de junio está
  archivado**: con dos deudas de tipo préstamo, el cargo de amortización se
  vuelve ambiguo y el préstamo real se para sin decir nada. Ya está arreglado.

Lo que **no** cierra: el recibo de 990,02 € de junio. Le faltan compras de mayo
en la app, así que el sistema se niega a marcar el ciclo y lo dice, en vez de
elegir «las que más se acerquen».

---

**PHASE-47.A sigue esperando su prueba manual.** Es la entrega de
cimientos del plan de recomposición de deuda que trajiste el día 13
([`improvements/phase-47-implementation-plan.md`](improvements/phase-47-implementation-plan.md)),
y no estrena comportamiento salvo un portero en el import. Detalle completo en
[`phases/phase-47.A-debt-domain-and-import-guard.md`](phases/phase-47.A-debt-domain-and-import-guard.md).

Tres cosas y un ADR:

1. **El dominio deuda vive en `debt/`.** Seis módulos mudados desde `accounts/`
   con sus 13 schemas, cero migraciones y las URLs intactas. Lo que garantiza
   que no se movió un céntimo es un golden byte a byte de `debt-health`,
   `balances` y `category-summary` tomado ANTES del movimiento — y sigue
   pasando. Un test de capas por AST impide que el ciclo vuelva.
2. **`accounts.settlement_account_id`**: qué cuenta de activo cobra cada pasivo.
   Es el dato que no existía y sin el cual no se puede saber qué cargo cierra el
   ciclo de qué tarjeta (en julio: 4 cargos, 6 pasivos). La app lo **propone**
   contando los cargos que ya enlazaste en PHASE-45; ante un empate, calla.
3. **El portero del import.** Es el agujero por el que entró el lío de julio:
   el extracto de la tarjeta se importó a la cuenta del banco sin un solo error.
   Ahora avisa —y **bloquea el botón** hasta que marques la casilla— cuando el
   fichero tiene el formato de otra cuenta, o cuando más del 20 % de sus filas
   ya existen en otra.

   Esta pieza estuvo **rota y en verde** durante unas horas: la huella se
   calculaba sobre las claves de las filas parseadas, que los smart-parsers
   emiten fijas por contrato, así que era la misma constante para todo PDF y
   todo XLSX de cualquier banco — y con las dos cuentas importando en PDF, el
   caso de julio pasaba en silencio. Lo destapó una revisión adversarial, no la
   suite. Está corregido (la cabecera real viaja aparte desde el parser) y con
   los dos tests que faltaban.

4. **[ADR-0011](decisions/0011-system-initiated-debt-event-translation.md)**: la
   traducción movimiento→evento la INICIA el sistema; la declaración sigue
   siendo tuya.

**Nada de esto está commiteado** — esperando tu visto bueno, como siempre.

---

## Qué probar (es el paso que bloquea el commit)

```bash
docker compose up -d
cd backend && .venv/Scripts/python.exe -m alembic upgrade head
cd backend && .venv/Scripts/python.exe -m scripts.backfill_header_fingerprint   # dry-run
cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8002
pnpm dev:web
```

El backend va en **8002**, no en 8000. El backfill primero sin `--apply`: mira
qué haría y luego repítelo con `--apply`. **Sin él el guardarraíl nace ciego**
(no conoce el formato de tus imports anteriores) y no habría cazado julio.

1. **Ajustes › Cuentas → editar un pasivo**: aparece «¿Desde qué cuenta se
   cobra?». Si ya enlazaste cargos con el panel «¿Es una amortización?», debajo
   sale el motivo contado («3 de los 4 cargos que amortizan esta deuda salen de
   «BBVA»») con un botón **«Usar «BBVA»»**. No se preselecciona sola a
   propósito: una propuesta que se escribe sin que la pulses acaba persistida.
2. **La parada A, y es la que no puedo dar yo**: importa el extracto de la
   **tarjeta** eligiendo la cuenta del **banco**. Tiene que salir el aviso y el
   botón «Importar» apagado hasta marcar la casilla. **Si no sale**, es que las
   dos tablas de movimientos de BBVA comparten cabecera: dímelo antes de que
   invente heurísticas, porque entonces F.1 no sirve en tu caso. (Ojo: en un PDF
   lo que se compara es la cabecera de la TABLA de movimientos que detecta el
   parser, no la del documento.)
3. Importa el extracto de siempre en su cuenta de siempre: **sin avisos**. Un
   guardarraíl que salta cada mes se aprende a ignorar.
4. Cruza `/debt` y los saldos con lo que veías antes: A1 no puede haber movido
   ni un céntimo.

Sabido y aceptado: **estrenar un formato conocido en una cuenta nueva avisa una
vez**. Desde la cabecera es indistinguible del error de julio.

---

## Estado de verificación

**Todo verde**, con el intérprete del proyecto (`.venv`, el mismo que CI):

- Backend: suite completa · `ruff` · `black` · `mypy` · `alembic
upgrade`/`downgrade` reversibles, cabeza única (`j6f39e1a4b2d85`), `alembic
check` sin drift.
- Frontend: `typecheck` · `lint` · `knip` · tests de web, móvil, services, ui y
  store.
- `python scripts/check_docs.py` sin podredumbre.
- **Todos los tests nuevos probados rompiendo el código**, incluida la
  reintroducción del bloqueante: volver a calcular la huella sobre las claves
  del parser tumba los dos tests nuevos de F.1.
- **Una revisión adversarial de cinco dimensiones** (25 hallazgos en bruto, 9
  confirmados tras dos escépticos por hallazgo) encontró un bloqueante y cinco
  defectos importantes que la suite en verde no veía. Todos corregidos; el
  detalle está en la phase doc.

**Tres veces en esta sesión un test pasó por la razón equivocada**, y las tres
se destaparon rompiendo el código, nunca releyendo el test. Si vuelves sobre
esto, ésa es la práctica que hay que mantener.

**Lo que NO se ha verificado**: tu prueba manual, y el CI de GitHub Actions
(`gh` sigue sin estar instalado en esta máquina).

---

## Lo siguiente, por orden

### 1. Probar y commitear 47.A

Cuando des el visto bueno. Mensajes en inglés, `— Refs: PHASE-47.A`. Son cuatro
commits separables: consolidación · `settlement_account_id` · guardarraíl del
import · ADR.

### 2. 47.B (la bandeja) — bloqueada por datos tuyos

Necesita la **parada 2**, y es indelegable:

- **Un mes verde**: mayo o junio, con el extracto de la tarjeta importado donde
  toca (7 compras cada uno). Sirve de fixture del invariante del ciclo.
- **Calibrar tres tolerancias** con esos datos delante:
  `DEBT_QUOTA_MATCH_TOLERANCE_EUR`, `DEBT_QUOTA_DATE_WINDOW_DAYS` y
  `DEBT_CYCLE_TOLERANCE_EUR`. Sólo ahí — subirlas después «para que cuadre»
  sería tuning.

**D5 ya no bloquea**: el plan de PHASE-48 que trajiste confirma que los cuatro
ADEUDO de julio (406,33 · 384,38 · 164,94 · 143,99) son **liquidaciones
anticipadas de compras aplazadas**. Eso corrige el caso de regresión del plan
original de 47, que los daba por cuotas: deben salir como items
`POSSIBLE_SETTLEMENT` del detector #4, no como items de cuota. Escribirlo al
revés cementaría el bug que la fase existe para arreglar.

### 3. Julio sigue sin reimportar

Lo que dejó abierto PHASE-46: el extracto de la tarjeta está en la cuenta del
banco. Los scripts de `backend/scripts/` con `--dry-run` siguen ahí
(`undo_card_statement_into_bank.py`, `move_import_to_account.py`). Ahora, además,
el portero avisaría antes de que volviera a pasar.

---

## Decisiones abiertas

| #   | Decisión                                                                                                                   | Recomendación                                                                                                                                             |
| --- | -------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **¿Se adopta algún umbral del cuaderno?** Ver [`investment-threshold-divergences.md`](investment-threshold-divergences.md) | Revisarlo con la calibración v1 delante                                                                                                                   |
| 2   | **Los cortes de C2 y C6** (inversión)                                                                                      | Esperar a tener más empresas: con dos no se distingue «el corte es bueno» de «no hay casos»                                                               |
| 3   | **Las dos verdades del saldo de deuda** (MUX cuadro-vs-movimientos de PHASE-36)                                            | No se responde aquí. PHASE-48 §48.1 propone nombrarlas en vez de reducirlas: `outstanding_principal` para el patrimonio, `pending_total` como informativo |

---

## Deuda declarada

Vive en [`backlog.md`](backlog.md) — ése es el sitio durable; este fichero se
reescribe entero cada sesión. Lo punzante ahora mismo:

- **De la reorg de deuda quedan dos residuos**: extraer los helpers de fecha
  duplicados a `core/dates.py` y re-exportar `converted_amount_expr`. Los dos son
  deduplicación pura.
- **F.2 subestima el solape** cuando el fichero trae filas idénticas repetidas
  (no reproduce el ordinal del dedup). Deliberado: preferimos avisar de menos.
- **Inversión sigue sin prueba manual** desde 44.9: reejecutar MCD y JNJ, mirar
  los tres charts nuevos y cruzar precios con tu bróker.

---

## Comprobado y cerrado (para no repetirlo)

- **Nunca dos `pytest` a la vez**: `crisol_test` es una sola base compartida, y
  eso incluye los que lance un subagente.
- **No encadenes con `&&` un comando cuya salida pase por `| tail`**: el código
  de salida es el de `tail` y el `&&` deja de proteger.
- **jest-dom no está en el proyecto.** Los tests web usan `toBeTruthy()`.
- **`exactOptionalPropertyTypes` sigue mordiendo**: una prop opcional que vaya a
  recibir `undefined` explícito se declara `prop?: T | undefined`.
- **El padre de una migración sale de `alembic heads`**, nunca del último fichero
  por orden alfabético.

---

## Verificación completa

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q    # ~13 min
cd backend && .venv/Scripts/python.exe -m mypy app/
cd backend && .venv/Scripts/python.exe -m ruff check app tests scripts alembic
cd backend && .venv/Scripts/python.exe -m black --check app tests scripts alembic
pnpm typecheck && pnpm lint && pnpm test && pnpm knip
python scripts/check_docs.py
```
