# Dónde estamos — 2026-08-13

Punto de continuación tras la sesión del 13 de agosto. Se lee de arriba abajo;
lo que hay que decidir está al final.

---

## Lo primero al retomar

**PHASE-47.A está escrita y verde, y espera tu prueba manual.** Es la entrega de
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

| # | Decisión | Recomendación |
|---|---|---|
| 1 | **¿Se adopta algún umbral del cuaderno?** Ver [`investment-threshold-divergences.md`](investment-threshold-divergences.md) | Revisarlo con la calibración v1 delante |
| 2 | **Los cortes de C2 y C6** (inversión) | Esperar a tener más empresas: con dos no se distingue «el corte es bueno» de «no hay casos» |
| 3 | **Las dos verdades del saldo de deuda** (MUX cuadro-vs-movimientos de PHASE-36) | No se responde aquí. PHASE-48 §48.1 propone nombrarlas en vez de reducirlas: `outstanding_principal` para el patrimonio, `pending_total` como informativo |

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
