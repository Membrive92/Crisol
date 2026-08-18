# El mes lo define el usuario: ciclo de seguimiento configurable en Ajustes

> Propuesta — no implementada. Escrita el 2026-08-18, el mismo día en que el
> caso motivador se midió con datos reales. Documento de diseño para una fase
> futura; decide el usuario cuándo entra.

## Qué se pide

Que el usuario pueda definir en Ajustes **cuándo empieza y acaba su mes** a
efectos de seguimiento de gastos, y que los agregados mensuales (resultado del
mes, navegación por períodos, series) se corten por ese ciclo en vez de por el
mes natural.

Caso del usuario, en sus palabras: *«yo cobro los días 14-15 de cada mes y mi
ciclo de pagos funciona en ese período y quiero que se clasifique de esa
forma»*.

## Por qué importa — medido, no supuesto

En la sesión del 2026-08-18 se reconstruyó agosto con las dos ventanas, contra
extractos reales:

| ventana | ahorro estimado a 15-ago |
|---|---|
| mes natural (1-ago → 15-ago) | **≈ +1.200 €** |
| nómina a nómina (14-jul → 15-ago) | **≈ +300/600 €** |

**La misma persona, el mismo dinero, 3-4× de diferencia** — sólo por dónde caen
la nómina y el recibo de la tarjeta respecto al corte. El usuario reportó «no
me cuadra el módulo» dos veces en una semana y ambas eran esto, no un bug.

Dos trampas concretas que la feature debe resolver, ya observadas:

1. **La nómina se fecha el 14, no el 15.** Un filtro manual 15→15 da
   `ingresos 0` — la nómina queda un día fuera. El corte tiene que definirlo
   el usuario viendo qué filas caen dentro, no adivinando la fecha-valor.
2. **El recibo de la tarjeta cae ~día 2-4**, así que el mes natural y el ciclo
   de nómina reparten recibo y sueldo en períodos distintos. Ninguno es «el
   bueno»: son dos preguntas distintas, y hoy la app sólo responde una.

## Invariante innegociable

**Esto es una convención de PRESENTACIÓN, no de dinero.** No toca `flow`, ni
saldos, ni anclas de extracto, ni el cuadro de deuda, ni el modelo del recibo
aplazado. Es la familia de lecciones PHASE-34/37/38: la fuente de verdad del
dinero no se mueve por una cuestión de etiquetas. Un test debe afirmar que
cambiar el ciclo **no mueve ni un céntimo** de ningún saldo (el guardarraíl del
diseño, como el de PHASE-47.H).

## Inventario de consumidores de «mes» (lección PHASE-47.E: el concepto, no la query)

Cambiar qué es «un mes» toca, como mínimo:

**Backend — bucketing mensual en SQL** (`to_char(...,'YYYY-MM')` /
`date_trunc('month')`):
- `dashboard/repository.py` — series by-month, `get_transaction_month_bounds`
  (flechas del navegador de período)
- `analytics/repository.py` — medias estructurales, runway, recurrencia,
  month-outlook (proyecta a FIN DE MES natural)
- `budgets/service.py` — presupuestos con clave `YYYY-MM`
- `debt/history.py`, `debt/router.py` — historia mensual de deuda, DTI con
  medias de ingreso mensual (¡ojo AUDIT-2026-08: ventanas de meses observados!)

**Backend — rango libre**: `date_from/date_to` día-exacto YA llega a 5 routers
(dashboard, analytics, debt, accounts, transactions) desde PHASE-42. Este es el
cimiento que abarata la V1.

**Frontend**: `ui/time-selector.tsx` (PHASE-27), `analysis/stitch-period-toggle.tsx`,
`debt/period-navigator.tsx` — y sus gemelos de móvil vía capa compartida.

## Diseño propuesto, por entregas

### V1 — el preset «Mi ciclo» (barata: cero SQL nuevo)

- **Dato**: `users.cycle_start_day` (1–28; NULL = mes natural). Se guarda en
  Ajustes con una **previsualización** que enseña los últimos movimientos y
  dónde caería el corte — es lo que resuelve la trampa del 14 vs 15: el
  usuario VE que su nómina entra.
- **Comportamiento**: el TimeSelector y los navegadores de período ganan el
  preset «Mi ciclo»; cada período se traduce a `[día D del mes M, día D del mes
  M+1)` y viaja por el `date_from/date_to` de PHASE-42 que ya existe. Las
  flechas ◀▶ saltan de ciclo en ciclo.
- **Etiquetado**: pregunta abierta (ver abajo).
- **NO entra en V1**: series by-month, presupuestos, month-outlook, insights —
  siguen en mes natural, y la pantalla lo dice donde conviva con el preset.

### V2 — las series mensuales cortan por ciclo

El bucket SQL pasa de `date_trunc('month', occurred_at)` a
`date_trunc('month', occurred_at - (cycle_start_day - 1) * interval '1 day')`
— cada ciclo se etiqueta por el mes en que empieza. Cuidados:

- **Días 29-31 no se ofrecen** (el clamp de febrero convierte el ciclo en una
  charca de bugs; 1–28 cubre el caso real y evita la aritmética).
- El month-outlook proyecta a fin de CICLO, y el runway/DTI recalculan sus
  ventanas de «meses observados» en ciclos (releer la lección AUDIT-2026-08
  antes: una media con un mes a medias domina la fórmula).
- La recurrencia de gastos fijos agrupa por estabilidad mensual — verificar
  equivalencia numérica o dejarla en mes natural a propósito (documentado).

### V3 — presupuestos por ciclo (decisión aparte)

Los presupuestos usan clave `YYYY-MM` y el usuario los declaró zona no probada
(PHASE-47.H: «no los toques»). Migrarlos a ciclo es una decisión suya con su
propia fase; V1/V2 no los tocan.

## Preguntas abiertas (decide el usuario)

1. **Etiqueta del ciclo**: `[14-ago → 13-sep]` ¿se llama «Agosto» (mes del
   cobro que lo abre) o «14 ago – 13 sep» (explícito)? Recomendación:
   explícito en V1 («Ciclo del 14 ago»), porque un «Agosto» que no es agosto
   genera los mismos «no me cuadra» que esto viene a matar.
2. **¿Cambiar el ajuste re-corta la historia entera?** Recomendación: sí — es
   presentación pura y recalcular es gratis; pero el selector debe avisar de
   que las comparativas «vs mes anterior» cambian de base.
3. **¿El día del corte es fecha-valor o fecha contable?** La nómina del caso
   real se fecha el 14 cobrándose «el 15». La previsualización de Ajustes
   existe para que esta pregunta no necesite respuesta teórica.

## Qué NO es esta feature

- No es el rango personalizado de PHASE-42 (eso es un filtro puntual; esto es
  la definición persistente de «mes» del usuario).
- No cambia cuándo cuenta el gasto de tarjeta (convención de PHASE-38:
  cuenta el día de la compra) ni el modelo del recibo financiado (PHASE-47.E).
