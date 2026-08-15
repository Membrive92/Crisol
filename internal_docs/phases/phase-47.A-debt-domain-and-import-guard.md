# PHASE-47.A — Cimientos: el dominio deuda en su sitio, quién cobra qué, y el portero del import

**Estado**: 🚧 pendiente de prueba manual
**Rama**: trabajo directo sobre `main` (convención del proyecto)
**Fecha**: 2026-08-13

## Objetivo

Poner los cimientos de PHASE-47 sin estrenar comportamiento salvo un
guardarraíl: consolidar el dominio deuda, crear el dato que hoy no existe y sin
el cual no hay bandeja (quién cobra cada pasivo), y cerrar el agujero por el que
entró el lío de julio. Plan en
[`improvements/phase-47-implementation-plan.md`](../improvements/phase-47-implementation-plan.md).

## Qué se implementó

### A1 · El dominio deuda vive en `debt/`

Seis módulos se mudan de `accounts/` a `debt/` conservando `__tablename__`
(cero migraciones):

```
accounts/debt_health.py             → debt/health.py
accounts/debt_history.py            → debt/history.py
accounts/debt_reconciliation.py     → debt/reconciliation.py
accounts/amortization.py            → debt/amortization.py
accounts/installments_model.py      → debt/installments_model.py
accounts/installments_repository.py → debt/installments_repository.py
```

Con ellos, los 13 schemas que sólo usaban esos seis y sus routers
(`DebtHealthKpis`, `AmortizationRowResponse`, `Installment*`, `Reconcile*`,
`DebtHistory*`, `DebtTypeSlice`, `AmortizationScheduleResponse`) pasan a
`debt/schemas.py`. Se quedan en `accounts/schemas.py` los `Account*`, los
`Position*` y `ReconcileBalanceRequest` — que es el cuadre de saldo, no de
deuda.

**Las URLs no cambian** (D6): los endpoints siguen registrados en
`accounts/router.py`; sólo cambia de dónde importan. Cambiarlas a `/debt/*`
rompería contrato a cambio de nada que el usuario note, y el backlog ya lo
había decidido así.

Lo que hace viable el movimiento es una asimetría: `debt/*` depende de
`accounts` **por sus hojas** (`models`, `repository`, `schemas`) y nunca de
`accounts.service`, mientras que `accounts.service` sí necesita el cuadro. Esa
asimetría no sobrevive en un comentario, así que la afirma
`tests/test_debt_module_layering.py` recorriendo el AST — con un tercer test
que exige imports absolutos, porque uno relativo se le escaparía a la
comprobación y el guardarraíl dejaría de guardar sin dejar de pasar.

### A2 · `accounts.settlement_account_id` — desde qué cuenta se cobra un pasivo

El cargo que paga una deuda vive en la cuenta corriente, no en la deuda. Sin
declararlo no se puede saber qué cargo cierra el ciclo de qué tarjeta: en julio
de 2026 había **4 cargos y 6 pasivos**. Sin esto no hay invariante de
conservación, ni detección automática, ni caso A.

- Columna nullable con `ON DELETE SET NULL` (borrar el banco no borra la deuda).
- Validación en `create`/`update`: sólo en pasivos, apuntando a una cuenta de
  **activo** del propio usuario y nunca a sí misma. Siempre `400` con motivo,
  nunca `404` — un 404 filtraría la existencia de cuentas ajenas.
- **Se propone, no se adivina**: `GET /accounts/{id}/settlement-candidate`
  cuenta los **cargos** que el usuario ya enlazó a mano en PHASE-45 —en sus
  **dos** formas, contrapartida (`amortization_source_id`) para un pasivo sin
  cuadro y cuota marcada (`paid_transaction_id`) para uno con cuadro— y devuelve
  la cuenta mayoritaria con su recuento dentro del motivo. Se deduplica por id
  de cargo: un pago que cubre cinco cuotas es UN cargo, no cinco votos. Sin
  evidencia, o con **empate**, no propone nada: elegir entre dos cuentas igual
  de respaldadas sería una moneda al aire disfrazada de dato.
- Si la cuenta apuntada deja de ser un activo, los pasivos que la declaraban se
  **desvinculan solos**. Nadie revalida las referencias entrantes, así que sin
  eso quedaba un estado que el propio validador rechaza y que no se podía
  arreglar desde la interfaz.
- Formulario de cuenta en web y móvil, visible sólo en pasivos. La propuesta se
  **ofrece con un botón**, no se preselecciona: una preselección se persiste en
  el siguiente guardado y volvía a colarse al reabrir la edición aunque el
  usuario la hubiera borrado a propósito.

### A3 · El portero del import

En julio el extracto de la TARJETA se importó eligiendo la cuenta del BANCO.
19 filas OK, cero errores. La señal que lo destapó fue comparar el recuento de
compras entre meses.

Dos señales que cubren casos **distintos**:

| Señal | Qué caza | ¿Julio? |
|---|---|---|
| **F.1** huella de cabecera (`import_jobs.header_fingerprint`) | un fichero con el formato de otra cuenta | ✅ sí — era la primera vez que entraba |
| **F.2** solape de dedup cruzado | una RE-importación de algo ya presente en otra cuenta | ❌ no |

La huella es SHA-256 de la cabecera normalizada (trim + casefold + orden), y
**sale del parser por un canal aparte**, no de las claves de las filas. Esto es
la corrección de un defecto que la revisión adversarial destapó y que dejaba F.1
completamente ciega: `parse_pdf_smart` y `parse_xlsx_smart` emiten filas con
**cinco claves fijas por contrato** (`SMART_FORCED_MAPPING`), así que
`rows[0].keys()` era la misma constante para todo PDF y todo XLSX de cualquier
banco. Con ambas cuentas importando en PDF —el caso de julio—, la guarda «este
formato ya entró aquí» se activaba siempre y **el aviso no salía nunca**. Ahora
los dos smart-parsers devuelven `(filas, cabecera)`; el camino de visión declara
`None`, porque ahí no hay columnas que comparar.

F.2 se apoya en que `_compute_hash` **no incluye `account_id`**: el mismo fichero
produce los mismos hashes lo importes donde lo importes. Eso, que como dedup es
un problema conocido, aquí es justo la señal.

Los dos son **avisos bloqueables, no prohibiciones**: viajan en
`ImportPreviewResponse.warnings[]`, el botón de importar está apagado hasta que
cada uno lleve su tick, y el commit exige `acknowledged_warnings[]` o devuelve
**409** con los pendientes dentro. La revalidación en el servidor no es
decorativa: un cliente que no la implemente no puede saltarse la parada.

**Backfill fuera de la migración** (`scripts/backfill_header_fingerprint.py`,
con `--dry-run`): sin él la señal nace ciega hasta que cada cuenta tenga un
import posterior a 47.A. Una migración reproduce, no corrige ([PHASE-34]).

El backfill **sólo deriva la huella de los jobs cuyo parseo indexa por la
cabecera real** (CSV y los caminos legacy). Para los smart-parseados y los de
visión la cabecera original es irrecuperable —el `preview_payload` guarda las
filas ya normalizadas— y se deja NULL. Escribir ahí la constante de las claves
fijas estamparía el mismo valor en todas las cuentas y **apagaría el guardarraíl
por completo**, que es exactamente lo que hacía la primera versión.

### A4 · ADR-0011

[«La traducción movimiento→evento de deuda la INICIA el sistema; la declaración
sigue siendo del usuario»](../decisions/0011-system-initiated-debt-event-translation.md).
Recoge el orden de la cascada como contrato, el silencio-con-rastro, el único
camino en que el sistema actúa solo (cuando la respuesta es **aritmética**, no
de criterio) y la reformulación honesta del principio del texto: *la redacción
puede añadir confianza; nunca seleccionar ni descartar candidatas*.

## Archivos clave

- `backend/app/modules/personal_finance/debt/{health,history,reconciliation,amortization,installments_model,installments_repository,schemas}.py` — el dominio consolidado.
- `backend/app/modules/personal_finance/debt/attribution.py` — la propuesta de cuenta de cargo, con su evidencia.
- `backend/app/modules/personal_finance/imports/fingerprint.py` — la huella (pura).
- `backend/scripts/backfill_header_fingerprint.py` — el backfill auditado.
- `apps/web/components/imports/preview-step.tsx` — los avisos con su tick.

## Endpoints añadidos

- `GET /accounts/{account_id}/settlement-candidate`

Y dos contratos ampliados: `POST /imports/preview` devuelve `warnings[]`;
`POST /imports/{id}/commit` acepta `acknowledged_warnings[]` y responde 409 sin
ellos.

## Migraciones

- `i5e28d0f3a1c74` — `accounts.settlement_account_id`
- `j6f39e1a4b2d85` — `import_jobs.header_fingerprint`

Las dos aditivas, sin backfill y con `downgrade` de un solo `DROP`.

## Verificación

- [x] **Golden byte a byte** de `debt-health`, `balances` y `category-summary`
      generado ANTES del movimiento e idéntico después
      (`tests/fixtures/debt/golden_47a_debt_domain.json`).
- [x] `pytest` completo verde **sin tocar un solo assert** — 1363 antes del
      movimiento, y la suite ampliada después.
- [x] `mypy` · `ruff` · `black` · `pnpm typecheck && lint && test && knip` ·
      `scripts/check_docs.py`.
- [x] `alembic upgrade`/`downgrade` reversibles, `alembic check` sin drift,
      cabeza única.
- [x] **Todos los tests nuevos verificados rompiendo el código.** El de capas
      con un import a `accounts.service`; el golden alterando un KPI; los de
      A2 apagando la guarda de empate y la de «debe ser activo»; los de A3
      quitando el gate del 409, bajando el umbral y desactivando la guarda de
      formato propio.
- [ ] **Prueba manual del usuario** (ver abajo).

## Lo que encontró la revisión adversarial (y por qué importa el método)

La fase se dio por verde una vez, con la suite completa pasando y los cuatro
gates probados rompiéndolos. Una revisión adversarial posterior —cinco
dimensiones, cada hallazgo contrastado por dos escépticos independientes—
devolvió 25 hallazgos en bruto, 9 confirmados y **uno bloqueante**: F.1 estaba
completamente ciega (detalle arriba). Correcciones aplicadas:

| Defecto | Corrección |
|---|---|
| La huella salía de las claves del parser, fijas por contrato → constante para todo PDF/XLSX | Los smart-parsers devuelven la cabecera real aparte; visión declara `None` |
| El backfill iba a estampar esa constante en todas las cuentas | Sólo deriva de los jobs con cabecera recuperable; el resto queda NULL |
| El test de capas no veía `from ...accounts import service` — la forma exacta que existe para prohibir | Detector que cubre las tres formas + un test del detector |
| La propuesta contaba CUOTAS: un pago que cubre 5 votaba 5 veces e inflaba el motivo | Se deduplica por id de cargo |
| Convertir en pasivo la cuenta apuntada dejaba un vínculo que el validador rechaza | Las referencias entrantes se limpian; y el reverso también |
| La propuesta precargada se persistía al reabrir, aunque la hubieras borrado | Se ofrece con un botón; no se escribe sola |

**Tres veces en la misma sesión** un test pasó por la razón equivocada: el de la
guarda de formato propio (una sola cuenta, la lista de «otras» sale vacía), los
de F.1 (la cuenta destino sin historial, así que el aviso salta aunque la huella
no discrimine) y el probe del propio detector de capas (`service` llegaba por
las dos formas a la vez, así que cegar una no cambiaba el resultado). Los tres
se leían perfectos. Los tres se destaparon **rompiendo el código a propósito**,
nunca releyendo el test.

Coste aceptado que quedó escrito de paso: estrenar un formato conocido en una
cuenta nueva **avisa una vez**, porque desde la cabecera es indistinguible del
error de julio.

## Cómo probarlo

1. `alembic upgrade head`, y `python -m scripts.backfill_header_fingerprint`
   (primero sin `--apply` para ver qué haría).
2. **Ajustes › Cuentas**: edita un pasivo. Debe aparecer «¿Desde qué cuenta se
   cobra?». Si ya habías enlazado cargos con el panel de PHASE-45, sale
   precargada con el motivo contado al lado.
3. **Importar** el extracto de la tarjeta eligiendo la cuenta del banco: tiene
   que salir el aviso y el botón «Importar» apagado hasta marcar la casilla.
4. Importar el extracto de siempre en su cuenta de siempre: **sin avisos**.
5. Cruzar `/debt` y los saldos con lo que veías antes del movimiento: A1 no
   puede haber movido ni un céntimo.

## Parada abierta

**Parada A del plan**: comprobar con los PDF reales de BBVA que la cabecera
**discrimina** banco de tarjeta. Ahora la pregunta tiene sentido —antes de la
corrección la respuesta estaba fijada por el código antes de mirar ningún
fichero—. Si los dos extractos comparten cabecera, F.1 no sirve en tu caso
concreto y hay que **preguntar** antes de inventar heurísticas.

Matiz que conviene tener presente al probarlo: un PDF pasa por
`parse_pdf_smart`, que elige **la tabla de movimientos** y devuelve SU cabecera.
Así que lo que se compara es la cabecera de esa tabla, no la del documento.

## Limitaciones conocidas

- **F.2 subestima el solape** cuando el fichero trae filas idénticas repetidas:
  no reproduce el ordinal de ocurrencia del dedup. Deliberado — un aviso que
  salta de más se aprende a ignorar, y con él el que sí importa.
- El aviso F.1 salta **una vez** al estrenar un formato conocido en una cuenta
  nueva. Es el precio de que sea la única señal capaz de cazar julio.
- La propuesta de cuenta de cargo necesita enlaces previos de PHASE-45: el
  primer mes de una tarjeta nueva no tiene nada que proponer.

## Próxima fase

**47.B** — la bandeja. Depende de A2 y, para cerrar, de la parada 2 (el mes
verde de mayo/junio y la calibración de las tres tolerancias). D5 ya está
respondida: los cuatro ADEUDO de julio son **liquidaciones anticipadas**
([PHASE-48](../improvements/phase-48-debt-early-settlement.md)), así que el
caso de regresión de julio son items `POSSIBLE_SETTLEMENT` del detector #4 —
**no** items de cuota, como decía el plan original.
