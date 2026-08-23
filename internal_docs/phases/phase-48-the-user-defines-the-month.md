# PHASE-48 — El mes lo define el usuario

**Estado**: 🚧 pendiente prueba manual
**Rama**: trabajo directo sobre `main`
**Fecha**: 2026-08-22 / 2026-08-23

## Objetivo

Que el día en que el usuario cobra REDEFINA qué es un mes en toda la app, en
vez de ofrecerse como una vista más al lado del mes natural.

## De dónde viene, y por qué el alcance cambió a mitad

El plan original
([`improvements/user-defined-month-cycle-implementation-plan.md`](../improvements/user-defined-month-cycle-implementation-plan.md))
lo diseñó como un **preset**: un chip «Mi ciclo» junto a «Mes», un `PeriodKey`
con cuatro valores y un `cycle=true` que el cliente decidía mandar. Se construyó
así, y el usuario lo probó:

> *«sigue siendo raro e incómodo… que se cambie todo directamente»*

Tenía razón, y la causa era de diseño. El día de cobro no es una opción de
visualización: es la respuesta a «¿qué es un mes para ti?», una pregunta que el
producto ya respondía por defecto. Ofrecer las dos a la vez obliga a mantenerlas
sincronizadas para siempre — y no lo estaban: **sólo cinco endpoints entendían
el ciclo** y el resto del backend cortaba por mes natural aunque el ajuste
estuviera puesto.

El plan lleva ahora un aviso de re-alcance al principio, porque su cuerpo
describe el diseño que el usuario rechazó y sin ese aviso alguien lo
reconstruiría.

## Qué se implementó

**En Ajustes**: un check «Modo predeterminado» (marcado = mes natural) con un
icono de información. Sustituye a la opción «Mes natural» que estaba mezclada
dentro del desplegable de días: no era un día de corte, era la ausencia de uno.
En móvil el icono DESPLIEGA el texto al pulsarlo — en táctil no existe el hover.

**En la interfaz**: el chip desaparece de las dos familias donde vivía (el
toggle de período y el `CycleModeChip` del `TimeSelector`, que gobierna
Transacciones y el drill-down y era fácil de pasar por alto). El toggle vuelve a
ser «Mes / Año / Personalizado» y el período se llama por el mes que lo ABRE —
«Julio 2026» va del 12 de julio al 11 de agosto, decisión del usuario.

**El año también se desplaza.** Su año 2026 va del 12-ene-2026 al 11-ene-2027.
Esto llegó al final, y llegó porque el usuario vio el efecto de no hacerlo: la
serie anual necesitaba un bucket «Dic 25» para no perder los días 1–11 de enero,
y él lo cortó de raíz — *«si estoy viendo gastos de 2026, no debería salir ese
diciembre de 2025»*. Lo que faltaba no era una barra: era desplazar el año.

**En el backend**: seis agregados que derivaban su propio mes pasan a cortar por
el del usuario — la proyección de fin de mes, el runway, los presupuestos, la
ventana que decide qué gasto es estructural, el DTI y la serie mensual de deuda.

**Una declaración por capa**: `packages/services/src/period/user-month.ts` y
`backend/app/modules/personal_finance/user_month.py`, en vez de un ternario de
tres ramas repetido en seis pantallas y un mes natural derivado a mano en seis
agregados.

## El método, que es la mitad de la entrega

Se borró `cycle` de `PeriodKey` **primero** y se dejó que el compilador dictara
la lista: ~35 puntos exactos. Escribirla a mano habría dejado ramas fuera, y una
rama olvidada aquí devuelve el mes natural **en silencio** — mismo tipo, rango
distinto, ningún error.

De paso, esa lista destapó tres defectos que llevaban tiempo ahí: el Dashboard
afirmaba recibir sus bounds en ciclos sin pedirlos nunca así, la semilla de
«Personalizado» se construía con el mes de calendario, y la serie diaria de
Deuda se habría pintado vacía porque el backend sólo la calcula con
`range=month`.

## Lo que encontró la revisión adversarial

Nueve defectos confirmados, **cinco introducidos durante este mismo trabajo** y
cuatro en cosas ya declaradas arregladas. Ninguno lo vio la suite en verde. Los
más caros:

- La serie mensual de deuda quedó a medias: la ventana desplazada un bucket
  (**el último salía a 0,00 € siempre**) y cada punto mezclando dos calendarios.
  Y se había retirado el aviso que nombraba el descuadre.
- El reanclaje al período en curso de /debt era **código muerto**: el navegador
  pisaba el ancla que la página acababa de fijar, en el mismo evento.
- El `TimeSelector` emitía rangos de ciclo con chips de mes natural, dejando
  movimientos **inalcanzables** desde la interfaz. El tipo de la query ni
  siquiera declaraba el campo, así que la pantalla no podía pedirlo.

Todos arreglados y con regresión. El gate de cableado creció a seis casos y
ahora recorre las dos apps.

## Archivos clave

- `packages/types/src/models/period.ts` — `PeriodKey` sin `cycle`.
- `packages/services/src/period/user-month.ts` — bounds, ancla y año del usuario.
- `backend/app/modules/personal_finance/user_month.py` — la declaración del backend.
- `apps/web/app/period-preset-wiring.test.ts` — el gate de cableado.
- `apps/{web,mobile}/components/settings/cycle-settings.tsx` — el check.

## Migraciones

Ninguna nueva: `users.cycle_start_day` ya existía (`l8h51g3c6d4f07`).

## Limitaciones conocidas

- **La evolución de patrimonio sigue en meses naturales** (su serie son 12 meses
  de calendario fijos). Es la única tarjeta que lo hace, y lleva el único aviso
  que queda en pantalla.
- Los días 1..D−1 de enero pertenecen al año ANTERIOR del usuario. Es la misma
  consecuencia que ya acepta a nivel de mes, dicha en voz alta.

## Verificación

- BE 1494 tests · mypy 227 · ruff · black.
- FE typecheck · lint · knip · web 229 · móvil 75 · ui 99 · services 106 · store 3.
- Los tests de propiedad del helper compartido (contigüidad, degeneración exacta
  en el mes natural, y que la aritmética de Python y la de SQL coinciden para
  todos los días de un año) son la red que hizo que 62 tests de presupuestos,
  proyección y estructura pasaran sin tocarles una línea.
