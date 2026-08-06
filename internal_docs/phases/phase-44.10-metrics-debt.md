# PHASE-44.10 — Las métricas que el cuaderno pedía

**Estado**: ✅ completada (backend + web). Pendiente la prueba manual del usuario.
**Fecha**: 2026-08-01
**Origen**: dos entradas de deuda del backlog, de la misma familia — piezas del
motor construidas y sin consumidor, y métricas del cuaderno del usuario que el
motor no calculaba.

## Objetivo

Cerrar el hueco entre lo que el cuaderno de metodología del usuario pide y lo
que el motor calcula, sin inventar nada.

## Qué se hizo

### 1. El DuPont extendido, con la identidad que cierra

Tres factores nuevos —`DUPONT_OM` (margen operativo), `DUPONT_TAX` (efecto
fiscal) y `DUPONT_FIN` (coste financiero)— que, con la rotación y el
apalancamiento ya existentes, completan la descomposición de cinco factores:

```
ROE = margen operativo × efecto fiscal × coste financiero × rotación × apalancamiento
```

**La decisión que gobierna todo lo demás: qué EBIT usar.** El motor tiene dos, y
el margen operativo y el coste financiero tienen que usar **el mismo** para que
se cancele. Se eligió el **EBIT reportado** en ambos.

Con `ebit_clean` arriba (que es lo que usa R3) y el reportado abajo, el error no
es teórico. Medido sobre JNJ real:

| Ejercicio | ROE real | ROE reconstruido | Error |
|---|---|---|---|
| 2018 | 25,60 % | 27,30 % | +1,69 pp |
| 2022 | 23,79 % | 25,26 % | +1,47 pp |
| **2023** | **48,29 %** | **52,24 %** | **+3,95 pp** |

El error es exactamente el factor `limpio/reportado`, así que varía cada año con
el peso de los deterioros y **no lanza ninguna excepción**: simplemente infla el
ROE reconstruido justo en los años en los que uno mira el DuPont.

La alternativa —usar el limpio en los dos— también cierra, pero el «coste
financiero» pasaría a absorber los deterioros y dejaría de significar lo que dice
su nombre. Un DuPont existe para descomponer en piezas **interpretables**; un
factor que se mueve por razones ajenas a su etiqueta no lo es.

Verificado con las fixtures reales: la identidad cierra con residuo ~1e-29 (puro
redondeo de `Decimal`) en Realty Income y JNJ. En MCD sale `None` — patrimonio
neto negativo — y eso se reporta como **no verificable**, nunca como cuadrado.

### 2. Dos métricas de solvencia

| Clave | Métrica | Fórmula | Banda |
|---|---|---|---|
| `S7` | Ratio de endeudamiento | pasivo total / patrimonio neto | banda central **1-2**, rojo > 3 |
| `S8` | Calidad de la deuda | (deuda a corto + vencimiento corriente) / deuda total | `lower_better`, sano ≤ 40 %, rojo > 80 % |

Dos decisiones de calibración:

- **Por debajo de 1, S7 sale ámbar y no rojo.** Poca deuda no es un riesgo; como
  mucho es capital ocioso. El corte rojo (3) no es inventado: es la traducción
  exacta del corte de S1 (pasivo/activo 0,75 ⟹ pasivo/patrimonio 3,0), para que
  las dos métricas no se contradigan.
- **`S7` se siembra con `applies=False` en financieras.** La banda 1-2 sale de
  que el pasivo financie entre la mitad y dos tercios del activo; en un banco el
  apalancamiento **es** el negocio y un 10× es normal. Mostrar el número sin
  semáforo es más honesto que un rojo permanente. Reutiliza el mecanismo que ya
  existía para los ocho scores forenses.

`S8` sí aplica en financieras: qué parte de la deuda vence a menos de un año
significa lo mismo en un banco que en una fábrica.

### 3. Tres piezas huérfanas, cableadas

`maintenance_capex`, `wc_operating` y `wc_total` existían en `derivations.py` y
no las llamaba ninguna capa. Se exponen como **series de la capa evolutiva**, que
pasa de 7 a 10 magnitudes:

- **Caja libre de mantenimiento** (`fcf_maintenance = cfo − min(capex, D&A)`,
  derivación nueva) — la que el cuaderno marca como *recomendada* frente a la
  puritana, porque no castiga a una empresa por invertir en crecer.
- **Circulante operativo** — coincide **exactamente** con el working capital del
  cuaderno: existencias + cobros − pagos, sin efectivo.
- **Fondo de maniobra**.

**Por qué series y no métricas con banda**: son importes absolutos. No hay corte
global aplicable a un fondo de maniobra y las unidades del catálogo no admiten un
importe; forzarlas habría exigido inventar un denominador. Además lo que el
cuaderno pide de ellas es literalmente «mirar cuándo hay variaciones», que es una
serie.

`total_debt_incl_leases` **sigue sin consumidor, a propósito**: existe para
comparabilidad IFRS16 y el cuaderno no la pide. Queda anotada en el backlog, que
es distinto de olvidada.

## Radio de impacto

- **57 métricas** (antes 52) · **42 con banda** (antes 40) · **1512 filas** de
  seed (antes 1440).
- **`ENGINE_VERSION` → 1.2.0** y huella del test de contrato actualizada.
- **`thresholds_version` de los runs futuros cambia**, porque S7 y S8 llevan
  banda. Es correcto: la calibración es genuinamente otra. Los runs guardados
  conservan el suyo. Los tres factores del DuPont van sin banda, así que no
  contribuyen a ese cambio.
- Ningún valor de ninguna métrica existente se mueve.
- Sin migración: nada de esto toca el esquema.

## Archivos clave

| Fichero | Qué |
|---|---|
| `engine/derivations.py` | `fcf_maintenance` |
| `engine/base_ratios.py` | S7, S8, los 3 factores, `_identity_check`, la descomposición ampliada |
| `engine/evolution.py` | de 7 a 10 series |
| `engine/version.py` | 1.2.0 |
| `thresholds/seed.py` | `NOT_FOR_FINANCIALS` |
| `tests/test_investment_engine_dupont.py` | **nuevo** — 17 tests |
| `apps/web/components/investment/tab-ratios.tsx` | S7/S8 en solvencia, DuPont de 3 y 5 con sus filas de comprobación |
| `apps/web/components/investment/tab-evolution.tsx` | aviso de las series nuevas |
| `packages/types/src/models/investment.ts` | `DuPontDecomposition` ampliada |

## Verificación

- [x] BE: suite completa · ruff · black · mypy · `docs:check`
- [x] FE: typecheck · lint · tests
- [x] Identidad verificada **con datos reales** (Realty Income y JNJ) y con
      sintéticos calculados a mano
- [x] Regresión que fija la trampa: un test demuestra que con `ebit_clean` el
      ROE reconstruido se desvía 3 puntos porcentuales

### Un bug ajeno, encontrado y arreglado de camino

La suite destapó un fallo en el módulo de **deuda**, no causado por esta fase
(los ficheros implicados llevaban sin tocarse desde `d98c96f`; deuda no importa
nada de inversión).

**La tasa de esfuerzo ampliada se inflaba con los meses sin datos.** Promediaba
el ingreso y la cuota sobre todos los meses cerrados del rango, incluidos los
anteriores a que el usuario tuviera datos. Con `range=year` el 1 de agosto y
datos desde febrero: ingreso medio 12.000/**7** = 1.714,29 en vez de 2.000, y el
ratio ampliado de 0,350 a 0,367 — cruzando el 35 % del Banco de España e
**inventando sobreendeudamiento cada principio de año**.

Pasó desapercibido porque el ratio **estricto** sale bien: es un cociente de dos
medias, así que el `n` incorrecto se cancela. Sólo asoma en el ampliado, donde se
suma un gasto fijo mensual real que no se divide por nada.

Arreglado acotando la ventana por su extremo izquierdo (`first_income_month`) —
el caso simétrico del que el autor ya había resuelto al excluir el mes en curso.
La regresión que lo fija usa un **rango fijo y pasado**: el test original fallaba
de agosto a diciembre y pasaba de febrero a julio, y un test que depende del mes
en que se ejecuta es una bomba de relojería.

> Además, la **primera** ejecución de la suite salió con 406 fallos falsos porque
> dos agentes de un workflow ejecutaron `pytest` en paralelo sobre la base
> compartida `crisol_test`. Las dos lecciones, en [`lessons.md`](../lessons.md).

## Decisiones tomadas

- **EBIT reportado en el DuPont extendido** (Opción B), decidida por el usuario
  tras ver el análisis algebraico y el error cuantificado.
- **La banda 1-2 de S7 se aplica ya**, sabiendo que está calibrada para negocios
  con activo tangible. El usuario lo pidió así: rangos por sector cuando el motor
  madure. Mitigado con `applies=False` en financieras.
- **Las tres piezas huérfanas van como serie, no como métrica.**

## Limitaciones conocidas

- `S7` sigue mal calibrada para **intensivas en intangibles** (software,
  farmacia), donde el rango también se queda corto pero sí se aplica. La solución
  es calibrar por sector: filas de `scoring_thresholds`, no código.
- `total_debt_incl_leases` sin consumidor.
- Sin paridad móvil.

## Próximo paso

La prueba manual pendiente de PHASE-44.9, ahora con estas métricas dentro.
