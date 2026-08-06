# Umbrales y fórmulas — tu cuaderno vs. el motor

> **Decisión vigente (2026-07-30): manda el motor.** Este documento existe para
> que la divergencia sea visible y reversible: si algún día quieres adoptar un
> corte del cuaderno, aquí está qué tocar y qué se rompe.
>
> **Fuentes**
> - Cuaderno: [`ai-context/excel-analisis-empresas.md`](ai-context/excel-analisis-empresas.md)
>   (transcripción de `improvements/Analisis empresas.xlsx`).
> - Motor: `backend/app/modules/investment/analysis/engine/`. Todas las citas
>   `fichero:línea` se verificaron leyendo el código el 2026-07-30.
>
> **Cómo cambiar un umbral, si algún día decides hacerlo**
> 1. Los cortes por defecto viven en el catálogo de cada capa
>    (`base_ratios.METRIC_CATALOG` y hermanos). Cambiarlos ahí cambia **todos**
>    los runs futuros.
> 2. Alternativa sin tocar el engine: una fila en `scoring_thresholds` para el
>    `(sector × norma)` que quieras — `load_thresholds` fusiona BD **sobre** los
>    defaults (`thresholds/service.py:48-51`).
> 3. En ambos casos cambia `thresholds_version` (SHA-256 del juego,
>    `thresholds/service.py:58-78`), así que los runs viejos y los nuevos dejan
>    de ser comparables. **Cambiar una banda es cambiar el veredicto**: exige ADR.
>
> **Aviso sobre el propio cuaderno**: no es un modelo con datos. Sus umbrales son
> reglas generales de un curso, sin sector ni norma contable. El motor calibra
> por `(sector × accounting_std)` — por eso varios cortes «no coinciden»: no
> pretenden hacerlo.

---

## Resumen

| Situación | Cuántas |
|---|---|
| Coinciden exactamente | 1 |
| Divergen en los cortes | 6 |
| El cuaderno pone umbral y el motor **no tiene banda** | 5 |
| El cuaderno pide una métrica que el motor **no calcula** | 0 *(las 3 se añadieron en PHASE-44.10)* |
| Divergen en la **fórmula**, no sólo en el corte | 5 |

---

## 1. Coincidencias

| Métrica | Cuaderno | Motor | Cita |
|---|---|---|---|
| **ROE (R5)** | óptimo **12 %** | `low_ok = 0.12` (y `low_alarm = 0.08`) | `base_ratios.py:135` |

El cuaderno añade *«si es financiero, debe ser más»*. El motor no sube el corte
en financieras — pero tampoco las analiza a fondo: `is_financial` apaga los ocho
scores forenses (`forensic.py:50-52`).

---

## 2. Divergencias de corte

### 2.1. Prueba ácida (L2) — difieren **los dos** cortes

| | Alarma | Óptimo |
|---|---|---|
| Cuaderno | 0,8 | 1,5 |
| Motor | **0,7** | **1,0** |

`base_ratios.py:62`. El motor es más permisivo en ambos extremos. Es la
divergencia más grande de liquidez: una empresa con quick ratio 1,1 sale
**verde** en la app y «por debajo del óptimo» en tu cuaderno.

### 2.2. Ratio de caja (L3)

| | Alarma | Óptimo |
|---|---|---|
| Cuaderno | 0,2 | 0,3 |
| Motor | **0,15** | 0,3 |

`base_ratios.py:63`. Sólo difiere la alarma, y por poco.

### 2.3. Ratio corriente (L1) — el cuaderno acota **por arriba**

Cuaderno: mínimo 1, **ideal 1,5–2**. Motor: `higher_better` con 1,0 / 1,5 y
**sin techo** (`base_ratios.py:61`).

La diferencia no es numérica sino de **forma**: tu cuaderno dice que pasarse
también es malo (circulante ocioso, caja sin rentabilizar); el motor sólo premia
subir. Adoptar tu criterio significa cambiar `direction` a `BAND`, no mover un
número — y entonces una empresa con mucha caja pasaría a ámbar.

### 2.4. Ratio de deuda (S1) — mismo caso, banda vs. dirección

Cuaderno: **banda 50–70 %** (y una anotación lateral con 40–60 % para «deuda
total / activos totales», que es otra métrica). Motor: `lower_better` con
`high_ok = 0.6`, `high_alarm = 0.75` (`base_ratios.py:89-91`).

Tu cuaderno penaliza **poca** deuda; el motor no. Mismo cambio estructural que
L1 (`direction` a `BAND`) y, por tanto, cambio de fórmula → `ENGINE_VERSION`.

> ⚠️ **No confundir**: el motor llama «Apalancamiento» a S1 (pasivos/activos).
> Lo que tu cuaderno llama «apalancamiento financiero» (activos/patrimonio, ≤3)
> es otra métrica: `DUPONT_EM`. Ver §4.4.

### 2.5. Cobertura de intereses (S2) — el motor es **más exigente**

Cuaderno: óptimo **> 5**. Motor: `low_alarm = 3`, `low_ok = **6**`
(`base_ratios.py:92`).

Una cobertura de 5,5× sale **ámbar** en la app y «óptima» en tu cuaderno. Esta
divergencia juega a tu favor, así que la recomendación es dejarla.

### 2.6. Deuda / EBIT — divergen el numerador **y** el corte

Cuaderno (hoja Deuda, «Vigilar»): **deuda no más de 3,5 × EBIT**, con **deuda
total**. Motor: **S4b** = deuda **neta** / EBIT limpio, `high_ok = 3`,
`high_alarm = **5**` (`base_ratios.py:97-107`).

> ⚠️ **Trampa verificada**: es tentador emparejar tu 3,5 con **S4**, que tiene
> `high_alarm = 3.5` (`base_ratios.py:94-95`). **No es la misma métrica**: S4
> está sobre **EBITDA**, no sobre EBIT. La coincidencia es del número, no del
> concepto. Tu límite de 3,5×EBIT corresponde a **S4b**, cuyo corte rojo es 5.

Y el numerador tampoco es idéntico: tu deuda neta se define como *«deuda a largo
plazo + deuda de largo en pasivos corrientes − efectivo»*; la del motor es
`short_term_debt + ltd_current_portion + long_term_debt − cash −
current_financial_assets` (`derivations.py:43-54`, `:71-77`) — o sea, incluye
además la deuda a corto puro y resta los activos financieros corrientes.

---

## 3. El cuaderno pone umbral y el motor **no tiene banda**

Estas cinco métricas **se calculan** y salen con `band = null`. Y `null` **no
significa sana**: `ThresholdSpec.band_for` lo documenta explícitamente
(`types.py:185-190`). En la pantalla salen en gris, sin semáforo.

| Métrica | Cuaderno | Motor | Cita |
|---|---|---|---|
| **Margen bruto (R1)** | óptimo **40 %** | sin banda | `base_ratios.py:131` |
| **Margen neto (R4)** | óptimo **10 %** | sin banda | `base_ratios.py:134` |
| **Rotación de activos (A4)** | **> 1** | sin banda | `base_ratios.py:81` |
| **Apalancamiento financiero** | **≤ 3** | `DUPONT_EM`, sin banda **y fuera del catálogo** | `base_ratios.py:262` |
| **Días de cobro/inventario/pago (A1-A3)** | «cuanto más bajo mejor» | sin banda, por diseño | `base_ratios.py:78-80` |

**Por qué el motor no las bandea**, y es una decisión defendible: *«un DSO de 45
días es excelente en retail y pésimo en software»* (`metrics.py:28-31`). Un
margen bruto del 40 % es malísimo en software y excelente en distribución
alimentaria. Un corte global sería ruido; el corte correcto es por sector, y eso
es una fila de `scoring_thresholds`, no una constante del engine.

**Si quieres tus cortes**: para R1, R4 y A4 son tres filas de
`scoring_thresholds` por cada sector donde tengan sentido. No hace falta tocar el
engine.

---

## 4. El cuaderno pide una métrica que el motor **no calcula**

| Métrica del cuaderno | Fórmula | Estado |
|---|---|---|
| **Ratio de endeudamiento** | pasivo total / patrimonio neto, óptimo **1–2** | ✅ **Añadida en PHASE-44.10** como `S7`, con la banda del cuaderno y sobre saldos PUNTUALES (no medias), que es como la define. En financieras se siembra `applies=False`: el rango 1–2 está calibrado para negocios con activo tangible |
| **Calidad de la deuda** | deuda a corto / deuda total, óptimo **20–40 %** (80 % máx.) | ✅ **Añadida en PHASE-44.10** como `S8`, `lower_better` con cortes 40 % / 80 %. Sin deuda sale no calculable —no 0 %—, que es la verdad |
| **DuPont extendido (5 factores)** | margen operativo × efecto fiscal × coste financiero × rotación × apalancamiento, con fila «Check» = 0 | ✅ **Añadido en PHASE-44.10** con sus tres factores nuevos (`DUPONT_OM`, `DUPONT_TAX`, `DUPONT_FIN`) y las dos filas de comprobación. Los tres van **sin banda**: son piezas de una identidad aritmética, no ratios de salud |

> ⚠️ **La trampa del DuPont extendido, y cómo se resolvió.** R3 usa `ebit_clean`
> (EBIT ajustado de deterioros y plusvalías). Si el margen operativo usara el
> limpio y el coste financiero el reportado, el EBIT **no se cancela** y la fila
> Check sale ≠ 0 **por construcción**, no por un error de datos.
>
> Medido sobre JNJ real: el ROE reconstruido salía inflado por el factor
> `limpio/reportado`, hasta **+4 puntos porcentuales en 2023** (52,24 % frente al
> 48,29 % real), y variando cada año con el peso de los deterioros.
>
> **Se eligió el EBIT REPORTADO en los dos factores** (PHASE-44.10). Cierra
> exacto —residuo ~1e-29, puro redondeo de `Decimal`— y, sobre todo, cada factor
> conserva su significado: el coste financiero dice cuánto se llevan los
> intereses, no cuánto se llevan los intereses *más los deterioros*. Con el EBIT
> limpio en ambos también cerraría, pero el factor absorbería lo extraordinario y
> dejaría de ser interpretable, que es justo lo que un DuPont viene a dar.

---

## 5. Divergencias de **fórmula** (más importantes que las de corte)

Aquí no discrepa un número: discrepa qué se está midiendo. Son las que hay que
tener presentes al comparar la app con tu cuaderno.

### 5.1. Free cash flow — definiciones distintas

| | Fórmula |
|---|---|
| Cuaderno | **EBITDA − intereses − Capex − Impuestos** |
| Motor (primaria) | `fcf_cfo = cfo − capex` (`derivations.py:260-262`) |
| Motor (contraste) | `fcf_ebitda = EBITDA − capex − Δcirculante operativo − impuestos pagados` (`derivations.py:265-292`) |

La del motor que más se te parece es `fcf_ebitda`, pero **no resta intereses** y
**sí resta la variación del circulante**. Y la primaria —la que alimenta D2, D3,
Q1-Q5, R7, R8, R9b, S5, S6 y todo el stress— es `fcf_cfo`, que parte del flujo
de explotación publicado.

No es un descuido: el motor calcula las dos a propósito y compara la divergencia
(métrica **Q3**, `dividend.py:160-168`). Cuando las dos formas de medir la caja
no cuadran, eso es la señal.

### 5.2. Cobertura de intereses — tu cuaderno da **dos** definiciones

- Cuerpo de la hoja de solvencia: **EBIT / pago de intereses**.
- Anotación lateral: **beneficios antes de impuestos / gastos por intereses**.

El motor implementa `ebit_clean / interest_expense` (`base_ratios.py:403-406`) —
o sea, la primera, y con el EBIT limpio.

**No son intercambiables**, y el propio motor lo demuestra: existe una bandera
`ebt_divergence` (`derivations.py:154-196`) precisamente porque
`EBIT − intereses ≠ BAI` cuando hay otro resultado financiero. Habría que
decidir cuál de las dos querías.

### 5.3. Ratios de actividad — el motor usa **medias**, tú saldos puntuales

Tu cuaderno: `(Inventario / Coste de ventas) × 365`, con el saldo de cierre.
Motor: mismo `×365` pero sobre el **saldo medio** t/t−1
(`base_ratios.py:365-388`), y el primer año de la serie sale marcado
`approximation` porque no hay t−1 (`conventions.py:172-181`).

Los números **no van a coincidir** con los de tu cuaderno, y la diferencia es
mayor cuanto más haya crecido el balance. La media es la práctica estándar
(mezclar un saldo de cierre con un flujo de todo el año infla la rotación).

### 5.4. «Ratio de activos» — magnitudes inversas

Tu cuaderno lo pide **dos veces y al revés**:

- Hoja 7 (actividad): `(Activos totales / Ventas) × 365` → en **días**, cuanto
  más bajo mejor.
- Hoja 9 (rentabilidad): `Ventas / Total activos` → **> 1**, cuanto más alto
  mejor.

El motor sólo tiene la segunda (A4). No son comparables sin invertir.

### 5.5. Intereses ≤ 20 % del EBIT

Tu cuaderno lo enuncia como porcentaje; el motor lo mide invertido, en veces de
cobertura (S2). **20 % del EBIT ⇔ cobertura de 5×.** El motor exige 6× para el
verde, así que tu límite cae en **ámbar**. Es equivalencia, no divergencia: no
hace falta métrica nueva.

---

## 6. Piezas que el motor tenía construidas y no consumía nadie

| Concepto del cuaderno | En el motor | Estado |
|---|---|---|
| **FCF de mantenimiento** («recomendado» frente al puritano) | `fcf_maintenance = cfo − min(capex, D&A)`, `provenance=ESTIMATED` | ✅ **Cableado en PHASE-44.10** como serie de la capa evolutiva |
| **Working capital** = inventarios + cobrar − pagar, **sin efectivo** | `wc_operating` — coincide **exactamente**, «sin efectivo» incluido | ✅ **Cableado** como serie. Tu cuaderno pide «mirar cuándo hay variaciones», y eso es una serie, no un ratio con banda |
| **Fondo de maniobra** | `wc_total = current_assets − current_liabilities` | ✅ **Cableado** como serie |
| Deuda con leases | `total_debt_incl_leases` (`derivations.py:57-68`) | **Sigue sin consumidor, a propósito.** Existe para comparabilidad IFRS16/ASC842 y tu cuaderno no la pide; exponerla sin que nadie la mida sería ruido. Se deja anotada, que es distinto de olvidada |

**Por qué series y no métricas con banda**: las tres son **importes absolutos**.
No hay corte global que aplicar a un fondo de maniobra —depende del tamaño de la
empresa— y las unidades del catálogo (veces, días, %, años…) no admiten un
importe. Forzarlas a métrica habría exigido inventar un denominador.

---

## 7. Lo que no se puede sacar del 10-K

| Concepto del cuaderno | Por qué no |
|---|---|
| **Divisa en que se recibe y paga la deuda** | El canónico guarda una sola `currency` por estado (`canonical.py:179`). El desglose por divisa está en las notas, no en XBRL estructurado |
| **Pago a directivas** | Vive en el **DEF 14A** (proxy statement), no en el 10-K que ingiere el adapter |
| **Calendario de vencimientos de deuda** | Sólo se captura el tramo corriente (`ltd_current_portion`); el escalonado a 5 años está en las notas |
| **Brecha básicas vs. diluidas** | Las dos partidas se ingieren (`shares_basic`, `shares_diluted`) pero **ninguna métrica del catálogo consume `shares_diluted`** |
| **Todos los múltiplos de valoración** (PER, P/S, P/BV, P/FCF, EV/EBITDA) y el **DDM de Gordon** | Necesitan precio de mercado. El engine **no recibe precio por diseño**: *«ninguno depende del precio de mercado, porque un score que se mueve con la cotización no sería reproducible al reejecutar un run antiguo»* (`forensic.py:3-6`). Además `FINNHUB_API_KEY` está vacía (`core/config.py:135`) |
| **Comparativa «vs sector»** de tu ejemplo Donaldson/Evoqua | No hay fuente de múltiplos sectoriales en el proyecto. El sector sólo sirve hoy para elegir umbrales |

---

## 8. Si algún día quieres adoptar tus cortes

Por orden de coste, de más barato a más caro:

1. **Gratis, sin tocar código** — L2, L3, S2, S4b: son filas de
   `scoring_thresholds` para el sector que corresponda.
2. **Barato** — R1, R4, A4, `DUPONT_EM`: darles banda. Requiere primero meter
   `DUPONT_EM` en `METRIC_CATALOG` (hoy se emite con una clave que el catálogo no
   conoce, `base_ratios.py:262`).
3. **Métrica nueva** — calidad de la deuda (corto/total) y ratio de
   endeudamiento: las partidas ya están, es sumar la definición y el cálculo.
   Sube `ENGINE_VERSION`.
4. **Cambio de fórmula** — L1 y S1 a banda central: cambia el veredicto de runs
   pasados si se reejecutan. Exige ADR.
5. **Caro y con dependencia externa** — toda la hoja 10 (valoración): API key de
   precios + una capa nueva **fuera** del `AnalysisRun` para no romper la
   reproducibilidad.
