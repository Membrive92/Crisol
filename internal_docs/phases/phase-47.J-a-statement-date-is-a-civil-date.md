# PHASE-47.J — Una fecha de extracto es una fecha CIVIL

**Estado**: 🚧 pendiente prueba manual
**Rama**: trabajo directo sobre `main`
**Fecha**: 2026-08-22

## Objetivo

Que el día en que ocurrió un movimiento deje de depender del ordenador que hizo
la importación y de la estación del año.

## El problema, medido

`transactions.occurred_at` es `TIMESTAMPTZ`, pero lo que se guarda ahí es una
fecha CIVIL: el día que imprime el banco. `_parse_datetime` devolvía un
`datetime` **naive**, y asyncpg codifica un naive con `astimezone(utc)`, que
sobre un naive asume la zona **del proceso**. Con el backend en Europe/Madrid,
«13/02/2026» se persistía como `2026-02-12T23:00:00Z`.

Medido en la base real antes del arreglo:

- **469 de 491** filas vivas desplazadas un día.
- **14 cambiaban de mes natural**, entre ellas una transferencia de **4.267,47 €**
  que contaba en marzo siendo del 1 de abril, y un cargo de amortización de
  232,27 € que contaba en mayo siendo del 1 de junio.
- La firma en los datos era inequívoca: **276 filas a las 22:00 UTC y 193 a las
  23:00** — las dos medianoches de Madrid, verano e invierno.

**Por qué nadie lo vio en cuatro fases.** La pantalla formatea en hora local, así
que mostraba el día correcto y cuadraba con el extracto. El desajuste sólo asoma
en los BORDES, porque los filtros de rango se construyen en UTC: un movimiento
que la app muestra el día 13 vivía a las 23:00Z del 12 y quedaba fuera de un
rango que empieza el 13. Con el mes natural el borde cae el día 1, que suele
tener poco movimiento. Lo destapó el ciclo del usuario con corte el 13, que puso
el borde en medio de datos densos: 3 movimientos en febrero y 6 en marzo.

## Qué se implementó

- **El parser ancla en UTC.** Anclar, no convertir: convertir asumiría que venía
  expresado en local, que es exactamente la suposición que causó el
  desplazamiento. Lo que sí trae zona (un ISO con offset) se traslada a UTC.
- **`core/civil_dates.py`** con el tipo anotado `CivilDatetime`, aplicado a los
  schemas de ENTRADA (transacciones, tickets, transferencias) para que ninguna
  otra ruta reintroduzca un naive — los tickets lo hacían.
- **`debt/repository.py`**: el único agrupador por mes que no fijaba la zona y
  dependía de la TZ de sesión de PostgreSQL.
- **Frontend**: `formatCivilDate` (lee en UTC) para las fechas de movimiento;
  `toDateInputValue` pasa a leer en UTC —**escribía**, y en cualquier huso
  negativo habría restado un día en cada guardado—; `formatShortDate` del
  titular del rango, ídem.

## El arreglo de datos

`scripts/normalize_civil_dates.py`, con `--dry-run` por defecto. No se fía de la
hora: usa un **testigo**. El `import_hash` se calculó con la fecha civil que el
parser leyó del extracto, así que recomputarlo con la fecha candidata PRUEBA que
la candidata es la que venía en el fichero.

Aplicado sobre la base real: **548 fechas normalizadas** (536 con el testigo
delante) y **10 cuotas** re-derivadas. Las 21 filas ya correctas no se tocaron —
no eran casualidad: editar y guardar una transacción ya las arreglaba de una en
una, porque el formulario emite medianoche UTC.

Verificado después: **569 filas todas a 00:00 UTC**, **557/557 hashes siguen
válidos**, `make audit-balances` limpio (BBVA 1.778,19 € = extracto) y el ciclo
con D=13 incluye por fin los movimientos del propio día 13.

## Archivos clave

- `backend/app/core/civil_dates.py` — el tipo de entrada.
- `backend/app/modules/personal_finance/imports/service.py` — el parser y el hash.
- `backend/scripts/normalize_civil_dates.py` — el arreglo de datos.
- `packages/ui/src/format.ts` — `formatCivilDate` y `toDateInputValue`.

## Migraciones

Ninguna. El arreglo de datos va en un script auditado con dry-run, no en una
migración (lección [PHASE-34]).

## Verificación

- BE 1478 tests · mypy · ruff · black. FE typecheck · lint · knip.
- Los tests nuevos **verificados rompiendo el código**, incluida una sonda que
  no llegó a aplicarse (black había reformateado la línea) y estuvo a punto de
  dar un verde falso.
- El test que faltaba y que ahora existe: importar `13/02/2026` y afirmar que la
  fila cae dentro del día 13. **Toda la suite creaba transacciones con
  `...T00:00:00Z` explícito**, o sea viviendo ya en el mundo donde la fecha está
  bien; ninguna recorría el camino del importador.

## Red de seguridad

Las tablas `_bak_civil_dates_20260822` y `_bak_civil_paid_at_20260822` guardan
las fechas anteriores. Borrarlas cuando el usuario dé el arreglo por bueno.
