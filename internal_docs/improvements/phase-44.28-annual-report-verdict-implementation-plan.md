# PHASE-44.28 — El Veredicto es el informe del ejercicio

**Estado**: ⏳ plan aprobado por el usuario, sin código escrito
**Fecha**: 2026-08-30 · revisado 2026-08-31 (§11)
**Origen**: tercera iteración del feedback sobre el Veredicto. Literal del
usuario: _«El veredicto debería recorrer todas las métricas y comparativas por
años hasta el último año del análisis y dar un veredicto del estado actual de
esa empresa. […] Es necesario un informe para que el usuario vea qué ha pasado
con la empresa en ese año para decir: la mantengo, o me tengo que preocupar —
y si ya tiene dudas, que mire él mismo las métricas.»_

> **Este documento es una foto fechada, no un documento vivo.** Los números
> (series de PepsiCo, versiones, recuentos de la BD) son del 30/31-ago-2026 y
> envejecen a propósito. No lo actualices — escribe la phase doc al terminar.

> **Para el modelo que implemente esto**: lee ANTES
> [`../lessons.md`](../lessons.md) entero y §9 de este plan. Este proyecto
> verifica los tests ROMPIENDO la línea que dicen proteger y comprobando que la
> rotura ENTRÓ. La suite de backend comparte UNA base (`crisol_test`): jamás
> dos pytest a la vez, jamás pytest desde un subagente. Intérprete:
> `backend/.venv/Scripts/python.exe` (3.12, el de CI) — el del PATH es 3.13 y
> su verde no vale. `prettier --write <fichero>`, nunca `pnpm format`.

---

## 0. Por qué tres rediseños «se quedaron igual»

PHASE-44.24, 44.25 y 44.26 reorganizaron **el mismo inventario de señales**
tres veces: cambiaba de sitio y de tipografía, nunca se convertía en un texto
que se lee. La causa: el Veredicto **juzga** (bandas, sellos, recuentos) pero
**no narra el año** — ninguna pantalla dice cuánto vendió la empresa, si el
margen aguantó, cuánta caja hizo y qué hizo con ella. Las 4 preguntas evalúan;
no cuentan qué pasó.

Lo que se construye es **el informe anual de un analista**: siete secciones
fijas que recorren el ejercicio con su comparativa plurianual, y un veredicto
final argumentado. Las 4 preguntas no desaparecen: **cada una se pliega como
chip de estado en la sección que le corresponde**.

**Decisión del usuario que cierra el debate**: _«vamos a implementar este
estilo y después lo vamos refinando»_. La primera entrega busca la ESTRUCTURA
correcta con frases honestas, no la redacción perfecta.

---

## 1. El contrato de aceptación — el mockup aprobado (PepsiCo, run real `e7053fd6`, motor 1.9.0)

El usuario aprobó este texto. Es la vara de **ESTILO** — no de cobertura
(§5.1 mide la diferencia y la declara esperada). **Correcciones aplicadas tras
la revisión del 31-ago**: la atribución de deuda/EBITDA estaba invertida, dos
rachas contaban de más, el chip de §5 era del color equivocado y cinco cifras
no casaban con el formateador vigente.

> ## Informe del ejercicio 2025 — PepsiCo
>
> **Vigilar** _(con 1B aplicada: los dos modelos de insolvencia no coinciden,
> así que ninguno fuerza «Evitar» en solitario)_
>
> ### 1 · El negocio — vende algo más, gana menos
>
> Las ventas crecieron un 2,3 %, hasta 93.925 M$ — el cuarto año consecutivo de
> crecimiento (los cuatro que la serie permite comparar), un +18 % acumulado
> desde 2021. Pero el beneficio fue en dirección contraria: el resultado
> operativo cayó un 10,8 % (11.498 M$) y el neto un 14,0 % (8.240 M$). El
> margen operativo baja de 14,0 % a 12,2 %, el peor de los cinco ejercicios
> salvo 2022: el margen bruto pierde 0,41 pp y el operativo 1,79, así que tres
> cuartas partes del deterioro están por debajo del bruto.
>
> ### 2 · La caja — real, pero la mejora de este año viene de invertir menos 🟢
>
> El negocio convierte beneficio en caja de sobra (146,7 %, verde los cinco
> años). La caja libre subió un 6,7 % hasta 7.672 M$ — pero no por ganar más:
> la explotación generó un 3,4 % menos y lo que subió la caja libre fue el
> recorte de inversión (4.415 M$ de capex, −17,0 %). La divergencia entre las
> dos formas de medir la caja libre entra en ámbar este año.
>
> ### 3 · El balance — tenso desde siempre, y este año un punto más
>
> La estructura es crónica: el pasivo pesa el 81 % del activo los cinco
> ejercicios (rojo), con un patrimonio del 19 %. Eso no es la noticia del año.
> La noticia es que deuda neta/EBITDA sale del verde por primera vez: de 2,18×
> a 2,65×, y por las dos puntas — la deuda neta sube un 13,2 % (35.040 →
> 39.652 M$) y el EBITDA cae un 6,8 % (16.047 → 14.949 M$); pesa más la deuda,
> un 64 % del deterioro. A favor: los intereses se cubren 10,26 veces (mejor
> que el 5,99 de 2021) y no hay muro de vencimientos (2,51×, verde). La
> liquidez lleva cinco años en ámbar (ratio corriente 0,85) y el ciclo de caja
> es de −7 días.
>
> ### 4 · La rentabilidad — el negocio renta; el ROE exagera
>
> El capital invertido rinde un 16,3 % (verde los cinco años). El ROE del
> 42,9 % es real pero está inflado por el propio balance: con un apalancamiento
> de 5,38×, cada punto de rentabilidad del negocio se multiplica. Sobre
> activos, un 8,0 %. Léase: empresa rentable, no milagrosa.
>
> ### 5 · La contabilidad — sin manipulación, pero el año operativo es peor 🔴
>
> Los accruals están limpios los cinco ejercicios y el M-Score los cuatro en
> que se puede calcular (2021 no tiene ejercicio anterior con el que
> compararse). Lo que empeora es la calidad del ejercicio: el C-Score sube de 2
> a 4 (rojo) porque se encienden «Suben los días de cobro» y «Suben los días de
> inventario», que se suman a las dos que ya estaban (42 y 47 días; +2,6 y
> +4,5 en cinco años), y el F-Score de Piotroski baja de 6 a 4 tras tres años
> estable.
>
> ### 6 · El dividendo — crece por encima de sus posibilidades 🔴
>
> 5,58 $ por acción, +6,0 % — al menos cuatro ejercicios seguidos sin recorte,
> creciendo al +7,1 % anual. El problema es de dónde sale: este año se llevó el
> 92,7 % del beneficio (rojo por primera vez; era el 75,5 %) y el 99,6 % de la
> caja libre. Contando recompras, se devolvió al accionista el 112,6 % de lo
> generado — y la comprobación encendida lo dice sin rodeos: _«Dos años
> seguidos (2024-2025) se ha devuelto al accionista más de lo que genera el
> negocio, y a la vez ha aumentado la deuda: el dividendo se está sosteniendo
> pidiendo prestado.»_ Consecuencia aritmética: la tasa de crecimiento
> autofinanciable cae del 12,9 % al 3,1 %, menos de la mitad de lo que el
> dividendo lleva creciendo.
>
> ### 7 · La resistencia — sin colchón 🔴
>
> La caja libre puede caer 34 M$ (un 0,4 %) antes de dejar de cubrir el
> dividendo. En el escenario de ventas −10 %, la cobertura pasa de 1,00× a
> 0,93×. De los dos modelos de insolvencia, el de Altman da verde los cinco
> años (2,88) y el de Zmijewski rojo los cinco (−0,09): no coinciden, y la
> discrepancia es en sí el hallazgo.
>
> ### El veredicto
>
> **PepsiCo es un negocio sano con el balance tenso y un dividendo al límite.**
> El deterioro de 2025 no está en las ventas sino en el margen y el beneficio,
> y el dividendo siguió creciendo como si eso no hubiera pasado: hoy consume
> casi todo lo que la empresa gana y genera. No hay señal de manipulación ni
> problema de vencimientos — hay falta de holgura. Mantenerla es razonable si
> el margen operativo vuelve hacia el 14,0 % del que viene; preocuparse es
> razonable si el payout sobre caja sigue por encima de su corte, porque no
> queda de dónde pagar el crecimiento del dividendo sin más deuda. Qué vigilar
> el año que viene: el margen operativo, el payout sobre caja libre y deuda
> neta/EBITDA.

---

## 2. Decisiones cerradas por el usuario (no reabrir)

**1B — «Evitar» por insolvencia exige que los DOS modelos coincidan.** Las dos
condiciones se **FUSIONAN en una**: `avoid_insolvency_corroborated`,
`signal_keys=('z_score','FZ')`, texto «los dos modelos de insolvencia en rojo».
Endurecer sólo `avoid_bankruptcy` dejaría `avoid_insolvency` disparando en
solitario — la O sigue viva por el otro lado, que es justo lo que la decisión
quita. `SafetyConditionDef` ya admite varias claves y la lógica AND-con-`None`
está escrita en `avoid_manipulation` (`synthesis.py:898-904` y `:1079-1087`):
se copia, incluida su regla de que un `False` hace falsa la conjunción aunque
la otra sea `None`. Con 1B, PEP y MCD bajan de «Evitar» a «Vigilar». Coste
aceptado: una apalancada en apuros que sólo cace Zmijewski baja a «Vigilar»
(que no es verde: sigue avisando).

**Secciones.** _«Las 4 preguntas podemos añadirlas en cada sección que
aplique»_: contabilidad→§5 · caja→§2 · dividendo→§6 · resistencia→§7, como
**chip de la sección**. §1 negocio, §3 balance y §4 rentabilidad no tienen
pregunta: sin chip.

**Cobertura.** Toda métrica en rojo/ámbar **o que cambió de banda** se nombra;
las verdes agrupadas. _«Si ya tiene dudas, que mire él mismo las métricas.»_
Acotado por familias de redundancia (§5.1).

**Veredicto al final.** Las secciones narran, el veredicto cierra. El sello y
el badge siguen en el hero de la página.

**Iterativo.** _«Implementamos este estilo y después lo vamos refinando.»_

**Este plan SUSTITUYE al diseño «La Lectura»** (workflow del 30-ago): no se
implementa. Sobreviven, absorbidas aquí: las identidades numéricas como única
forma de causalidad (§5.3), la racha como atributo (§5.2), las ausencias
honestas (§5.4), el breakeven **en la divisa de las cuentas**, y las retiradas
(§7).

**Relación con [PHASE-44.27](phase-44.27-data-integrity-and-metric-coverage.md)**:
sigue vivo entero. Su E1 es **prerrequisito para leer MCD** (§8). Sus E18/D2/E5
son un lote de motor SEPARADO: cuando aterricen, los chips los heredan solos.
E4 pierde urgencia con 1B pero sigue siendo honestidad válida.

---

## 3. Invariantes que este plan NO puede romper

1. **Cero LLM.** Plantillas-como-DATO en `presentation/narrative.py`, goldens
   de texto exacto y `templates_fingerprint()`. Mismo run + misma
   `NARRATIVE_VERSION` ⇒ mismo texto byte a byte.
2. **El engine es puro** (test de pureza por AST). La composición vive en
   `presentation/`, al servir. El único cambio de engine es 1B.
3. **Nunca afirmar lo que el motor no calculó** (44.25). Un dato ausente se
   DICE; jamás se infiere ni se rellena.
4. **Un `AnalysisRun` es la unión de todas las versiones escritas** (44.16): el
   compositor tolera runs viejos campo a campo y los campos nuevos del response
   son opcionales en TS.
5. **Sin recomendación de compra/venta.** El veredicto presenta SIEMPRE las dos
   lecturas en simetría (§5.5) — nunca una rama sola.
6. **Los cortes que se citan son los DEL RUN** (`thresholds_used`), nunca la
   resolución de hoy.
7. **Qué se muestra y en qué orden es capa compartida** (`packages/ui`).

> **44.28 reversa una regla escrita de 44.26: «los números NO van en la
> prosa».** El informe los lleva dentro porque una narración sin cifras no
> cuenta el año. El enlace a la métrica no se pierde: viaja por
> `ReportParagraph.metric_keys`, igual que `concern_keys`. **Actualizar el
> comentario de `SUMMARY_TEMPLATES` (`narrative.py:174-176`) en el mismo
> commit**, o queda un comentario prohibiendo lo que la fase acaba de hacer.

---

## 4. El material — verificado contra la BD (31-ago)

Todo lo que el informe necesita **ya está persistido**. Las series son listas
PLANAS de `{key, band, value, reason, status, provenance, fiscal_year}`,
indexadas por `(key, año)`.

| Campo JSONB                                                                               | Alimenta                                          |
| ----------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `evolution.horizontal` (10 items con `points[{fiscal_year,value,yoy,index_100}]` y `cagr`) | §1, §2, §6                                        |
| `scores_detail.base_ratios.metrics` (33 claves × 5 años)                                   | §1, §3, §4                                        |
| `scores_detail.base_ratios.dupont`                                                         | §4                                                |
| `scores_detail.forensic.metrics` (9)                                                       | §5, §7                                            |
| `scores_detail.forensic.breakdowns`                                                        | §5 (qué comprobación se encendió, por año)        |
| `dividend_analysis.metrics` (14)                                                           | **§2 (Q1-Q3)**, **§5 (Q5)**, §6 (D\*, B3, T2, T3) |
| `dividend_analysis.dps_series` · `trajectory`                                               | §6                                                |
| `evolution.metrics` (2)                                                                    | **§1 (E3)**, §6 (E4)                              |
| `verdict.stress`                                                                            | §7                                                |
| `verdict.questions`                                                                         | chips de sección                                  |
| `verdict.safety_profile`                                                                    | pliegue de auditoría + veredicto                  |
| `flags` (con `message` en español)                                                          | §6 (cita verbatim, ver §5.6)                      |
| `confidence`, `data_completeness`                                                           | pie del informe                                   |

**Tres formas que ya mordieron**: (a) las Q\* viven en `dividend_analysis`, no
en `base_ratios` — la columna de arriba está corregida; (b) R1-R4, A1-A5,
DUPONT\_\*, E4 y R8 **no llevan banda**: se narran como hechos y NO entran en el
gate de cobertura; (c) T2/T3 sólo tienen valor en el último año.

---

## 5. Reglas de composición

### 5.1 Cobertura, con su gate

- **Entra en prosa**: toda métrica CON BANDA cuyo último año sea `stressed` o
  `caution`, y toda la que haya cambiado de banda respecto del anterior.
- **Se agrupa**: las verdes, por familia con recuento.
- **El mapa métrica→sección** (43 claves con banda, verificado contra
  `ALL_DEFAULT_THRESHOLDS`; suma 43 sin duplicados):

  | Sección        | Claves                                                            |
  | -------------- | ----------------------------------------------------------------- |
  | 1 negocio      | `E3`                                                              |
  | 2 caja         | `Q1` `Q2` `Q3` `R7`                                               |
  | 3 balance      | `L1` `L2` `L3` `L4` `S1` `S2` `S3` `S4` `S4b` `S5` `S6` `S7` `S8` |
  | 4 rentabilidad | `R5` `R6` `R9` `R9b` `R10`                                        |
  | 5 contabilidad | `m_score` `accruals` `F5` `F6` `F7` `Q5` `f_score`                |
  | 6 dividendo    | `D1` `D2` `D3` `D4` `D5` `D6` `D8` `B3` `T2` `T3`                 |
  | 7 resistencia  | `z_score` `FZ` `FZ_P`                                             |

  La colocación es **editorial** y no coincide 1:1 con las preguntas
  (`f_score` es señal de la pregunta de caja y se narra en §5). El chip sale de
  la PREGUNTA; la prosa y el desplegable, de esta tabla.

- **Dónde vive el mapa**: copia CANÓNICA en **Python**, junto a las plantillas
  y dentro de `templates_fingerprint()` (la prosa la compone el servidor y el
  gate corre en pytest). El view-model de `packages/ui` lleva **su copia** para
  agrupar y enlazar, y **el gate de I5 las ata clave a clave** — el patrón de
  `test_investment_screen_coverage.py`. Dos copias con un gate; nunca dos
  copias a secas.

- **Recuento medido (PEP, 31-ago)**: la regla obliga a **24** claves y el
  mockup nombra **11**. El mockup NO cumple el gate: es la vara de ESTILO. Dos
  consecuencias:

  **(a) Familias de redundancia.** `{S1, S3, S7}` describen la misma
  estructura —el propio motor lo declara en `base_ratios.py:181`— y
  `{D2, D3, D4, D5, D8}` el mismo payout sobre caja. El gate exige **UN
  representante por familia**, el de mayor severidad, desempatando por
  distancia al corte; las hermanas quedan en el desplegable. Con eso PEP baja
  de 24 a **16** obligatorias.

  **(b) El ancla del gate es la CLAVE, no la etiqueta.** Cada sección emite
  `covered_keys: tuple[str, ...]` y el test compara ESA lista. Buscar la
  etiqueta como subcadena penaliza la buena redacción: el mockup escribe «el
  pasivo pesa el 81 % del activo» donde la etiqueta es «Apalancamiento», y un
  gate literal lo tumbaría.

- **GATE bidireccional**: (1) toda clave obligatoria está en algún
  `covered_keys`; (2) ninguna sección declara una clave fuera del mapa.
  Verificarlo ROMPIENDO: quitar una clave del mapa y comprobar que cae.

### 5.2 La antigüedad es atributo obligatorio

Toda afirmación con banda lleva su racha **con denominador**: «rojo los cinco
ejercicios», «por primera vez», «tercero de los cinco».

**Hay DOS denominadores y no se mezclan.** Una racha sobre VARIACIONES (`yoy`,
`index_100`) se cuenta sobre los puntos con `yoy is not None` → tope `n−1`. Una
racha sobre BANDAS se cuenta sobre los ejercicios con `status` en
`{ok, approximation}` → tope `n`, y **nunca** `len(years_covered)`: en PEP,
`m_score`, `f_score`, `F6`, `F7` y `Q3` no tienen 2021. Test de propiedad en
I2: `streak_from_yoy(N) <= N-1` y `streak_from_band(N) <= N`, verificado
quitando el `-1`.

Racha sólo con ≥4 ejercicios de serie. Las métricas de VENTANA (`E3` — su serie
es la σ de la ventana, idéntica los 5 años) van en `WINDOW_STATISTIC_KEYS`, con
su motivo, y quedan fuera del eje temporal.

### 5.3 Causalidad sólo por identidad aritmética

Un «porque» sólo se compone si es una identidad declarada en el catálogo:

| Frase                                         | Identidad                                                                                                                                                                                                                                                            | Medido en PEP                                     |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| «la caja libre subió por invertir menos»       | `capex = cfo − fcf_cfo`; sólo si cfo bajó Y fcf subió                                                                                                                                                                                                                 | 12.087 − 7.672 = 4.415 M$ (−17,0 %)               |
| «el dividendo crece más que la caja»           | CAGR(`dividends_paid`) vs CAGR(`fcf_cfo`), ambos persistidos                                                                                                                                                                                                          | +7,06 % vs +2,35 %                                |
| «deuda/EBITDA empeora {atribución}»            | `S4 = ND/EBITDA`; la ATRIBUCIÓN se **calcula** (log-share entre t−1 y t), nunca se escribe la dirección en la plantilla. ND no está persistido: se recompone `ND = S4 × R2 × revenue` y el gate ejercita esa cadena                                                     | 64 % deuda / 36 % EBITDA                          |
| «la tasa autofinanciable cae por el payout»    | `E4 = (1−D1) × R5`                                                                                                                                                                                                                                                    | 0,0313158 vs E4 persistido, diferencia 0E-29      |
| «el ROE está inflado por el apalancamiento»    | DuPont persistido                                                                                                                                                                                                                                                     | EM 5,38×                                          |
| «el C-Score sube porque se encendieron X e Y»  | **delta de comprobaciones**: `checks(t) − checks(t−1)` sobre `forensic.breakdowns`                                                                                                                                                                                     | 2024 ON={C4,C5} → 2025 ON={C2,C3,C4,C5}           |

**Gate numérico**: cada identidad se recompone desde los campos persistidos y
reproduce el valor a 6 decimales sobre los goldens. Un mecanismo que no compile
contra un número no entra.

**Los «porqués» NO autorizados se retiran o se declaran**: «el deterioro está
en la estructura, no en el precio» → sustituido por la descomposición en pp (ya
hecho en §1); «mitigada porque cobra antes de pagar» y «empujado por el pasivo
del 81 %» → **retirados**, no hay identidad detrás.

### 5.4 Ausencias honestas y casos duros

- **Sin dividendo**: `pays_dividend = any(p.dps and p.dps > 0 for p in
  dps_series)` — NUNCA `dividend_verdict == 'not_applicable'`, que colapsa
  «financiera» y «no reparte» (44.19). Copia canónica en Python; el predicado
  SUBE a `packages/ui` y las dos copias de TS (`tab-dividend.tsx:44`,
  `report-tabs.tsx:639`) se retiran a favor de ella, o quedan tres.
  Consecuencias medidas ejecutando el motor con `dividends_paid=0`: (i) la
  pregunta 3 sale **`healthy` y `audited=True`**, así que la sección 6 **no**
  toma su chip de ella sino un estado propio «no reparte»; (ii) D1/D2/D4/D5/D8
  y T3 salen `healthy` con valor 0 — quedan fuera también del grupo de verdes,
  sus ceros son artefactos del denominador; (iii) `streak_no_cut` vale **4**
  para quien nunca ha repartido (`0 < 0` es falso, `dividend.py:290-303`), así
  que no se cita jamás sin comprobar `pays_dividend`.

- **Denominador negativo (regla nueva, transversal)**: toda métrica de cociente
  con denominador ≤ 0 se compone como «no interpretable: el denominador es
  negativo», sin banda y fuera del grupo de verdes, **aunque el motor le haya
  puesto `healthy`**. Caso real: Realty Income, `D4 = −427,1 %` y
  `D5 = −447,2 %`, los dos en VERDE, porque el ajuste FFO alcanza a D1/D2/D3/D8
  y **no** a D4/D5, que van sobre `fcf` crudo (`dividend.py:740,750`). La
  guarda no es `not_reit` sobre la etiqueta: **es el signo**.

- **Financiera**: la regla de enrutado pasa de BINARIA a TRIPLE, consultando el
  run: (a) con banda → prosa o verdes; (b) sin banda y `applies is False` →
  «no se audita aquí» + `not_applicable_reason`, **aunque haya valor** (en una
  financiera son 11 de 43: S1, S7, S2, L1-L3, Q2, Q3, R7, S6, B3); (c) sin
  banda y `applies is True` → hecho sin color.

- **Escalones de degradación (BD, 31-ago, 11 runs)** — son CUATRO, no dos:
  **1.0.0** (1 run) `thresholds_used` es `{}`, 7 de 10 series, 27 de 33
  base_ratios, sin FZ_P ni DUPONT, questions sin señales, safety sin
  `conditions`. **1.3.0** (1) 42 umbrales pero SIN `not_applicable_reason`,
  questions sin `audited`. **1.6.0-1.7.0** (5) completos salvo `conditions` y
  FZ_P. **1.8.0+** (3) con matriz; FZ_P sólo en 1.9.0.

  La regla es **POR SECCIÓN**, no «el informe entero degrada»: una sección se
  compone si tiene su material; lo que necesite banda o corte se omite con su
  variante de ausencia; el aviso global va arriba con `StaleRunNotice` (44.16).
  Sin `conditions`, el veredicto se compone sin contrafactual y lo DICE — no se
  reconstruye con la matriz de hoy (decisión de 44.25 para `why=None`).

  **Detección por VERDAD, no por `None`**: `if not thresholds_used` (en MCD
  1.0.0 es `{}`). Y el motivo se lee de
  `rehydrate_thresholds(...)[key].not_applicable_reason`, **nunca del dict
  crudo**: en JNJ 1.3.0 la clave no existe y el rehidratador ya la sustituye
  por la ausencia declarada.

### 5.5 El veredicto final

Cuatro piezas. Los dos ejes se evalúan por **primera coincidencia** sobre un
orden total.

**Eje NEGOCIO** (mitad izquierda): 1 `business_unauditable` «un negocio que
este análisis no puede juzgar» ← `q(cash).evidence != 'evaluated'` OR
`R9.band is None` · 2 `business_deteriorating` «un negocio en deterioro» ←
`q(cash)=='stressed'` OR `R9=='stressed'` · 3 `business_sound_but_tense` «un
negocio sano con el balance tenso» ← `q(cash)=='healthy'` AND `R9=='healthy'`
AND (`S1=='stressed'` OR `q(resilience)=='stressed'`) · 4 `business_sound` «un
negocio sano» · 5 `business_mixed` «un negocio con luces y sombras».

**Eje DIVIDENDO** (mitad derecha): 1 `dividend_none` «sin dividendo» ←
`not pays_dividend` · 2 `dividend_unauditable` ← `q(dividend).evidence !=
'evaluated'` · 3 `dividend_at_limit` «un dividendo al límite» ←
`q(dividend)=='stressed'` AND `D2.band=='stressed'` · 4 `dividend_at_risk` ←
`q(dividend)=='stressed'` · 5 `dividend_watch` ← `caution` · 6
`dividend_covered` ← `healthy`.

_(PEP cae en `business_sound_but_tense` + `dividend_at_limit`, que es la frase
del mockup.)_

**El contraste del año**, desde los cambios de banda.

**La simetría (obligatoria)**: cuatro pares, cada uno anclado a una métrica CON
banda y a su corte DEL RUN (invariante 6) — (a) margen operativo `R3` vs su
nivel de t−1, (b) payout sobre caja `D2` vs su corte, (c) `S4` vs su corte,
(d) el score de insolvencia peor. Se elige el par cuya métrica encabeza
`severity_key`; si ninguna cambió de banda ni está en ámbar/rojo, sobre la peor
ámbar; si no hay ninguna, la variante «no hay señal que obligue a cambiar de
opinión este año».

**Gates**: (i) la plantilla no se emite con una rama vacía; (ii) las dos ramas
citan métricas DISTINTAS, o el mismo corte por los dos lados — si no, la
simetría es cosmética; (iii) sin lectura aplicable en ambos ejes se emite
«situación no clasificada — ver secciones», nunca la más cercana.

**Qué vigilar**: las 2-3 ámbar o recién degradadas más severas, por
`severity_key`.

### 5.6 Números

**No existe formateador es-ES en Python** (`grep` da un único
`.replace(".", ",")` sobre un entero, `narrative.py:521`). Se escribe entero en
`presentation/numbers.py`: `pct(v, digits=1)`, `times(v)`, `days(v)`,
`years(v)`, `score(v)`, `count(v)`, `money_millions(v, currency)`, **todos con
`ROUND_HALF_UP` explícito** —que reproduce `toLocaleString` de JS, negativos
incluidos— y separador construido a mano (miles `.`, decimal `,`); nunca un
`.replace` sobre un f-string, que convierte 93.925,00 en «93,925,0».

**La prosa usa los mismos `DECIMALS` que la matriz**
(`packages/ui/src/investment-metric-format.ts:12-21`), o las dos superficies
dirán el mismo número con dos precisiones. Consecuencia medida: cinco cifras
del mockup se corrigieron antes de fijar goldens («42 días», «−7 días»,
«10,26×», «146,7 %», «5,38×»). Excepción única: si 0 decimales sobre un ciclo
de caja de −6,5 días pierde información real, se cambia `DECIMALS.days` a 1
**en TS**, no se abre una tabla paralela.

**No se cita verbatim nada que lleve cifras.** Los mensajes persistidos están
en formato US (`5.3%`, `9,821,000,000`, «de 1.00× a 0.93×»): la sección 7
RECOMPONE las coberturas desde `coverage_before`/`coverage_after` con el
formateador nuevo. La cita verbatim se reserva a mensajes SIN cifras — hoy sólo
C7 y las cualitativas. **El golden de C7 sale de la BD concatenando el campo,
no del texto de §1**: tecleado, la primera vez que el motor reescriba el
mensaje el golden dirá que el informe cita bien cuando ya no.

**Fixture de paridad Python↔TS: hay que CREARLO** — no existe (el único
compartido es `question-evidence.json`, que ata el tri-estado, no números).
8 unidades × 3 casos (positivo, negativo y **empate exacto**) = 24. El caso de
empate es el que prueba que se eligió `ROUND_HALF_UP`; sin él el fixture no
muerde. Patrón: JSON en `packages/ui/src/__fixtures__/` consumido por un test
pytest **y** uno vitest.

---

## 6. Entregas

**I1 — 1B en el motor.** Fusionar las dos condiciones de insolvencia (§2).
Goldens de titular y `blocking_reasons` regenerados A PROPÓSITO. Tests:
PEP/MCD → «Vigilar»; sintético con ambos rojos → «Evitar»; y **sintético con
`z_score` ROJO y `FZ` VERDE ⇒ «Vigilar»**, que es el ÚNICO que distingue
«fusiono las dos» de «endurezco sólo `avoid_bankruptcy`» —PEP y MCD tienen
`z_score` verde y no lo ejercitan—; verificarlo restaurando `avoid_insolvency`
a su forma actual: el test tiene que caer.
**AVISO**: `_engine_shape` (`test_investment_engine_contract.py:135-155`) NO
cubre el contenido de `SAFETY_MATRIX`, así que **el bump a 1.10.0 es manual**.
Lo que sí caza el cambio son los goldens de
`test_investment_engine_synthesis.py` :428/:446/:463/:485 (eran de equivalencia
en un refactor; 1B es semántico, así que se reescriben clavando la matriz
nueva). Fusionar cambia las claves: los runs ≥1.8.0 guardados traen
`avoid_insolvency`/`avoid_bankruptcy`, y la pantalla debe tolerar las dos
formas (invariante 4).
→ `engine/synthesis.py`, tests · **ENGINE 1.9.0 → 1.10.0 (manual)**

**I2 — La capa de historia.** **Recibe el run entero** (los seis bloques de §4)
más un `SecurityContext(name, currency, is_financial, is_reit)` que compone
`build_report_layer` —ya carga el `Security`; le falta UNA consulta a
`financial_statements` para la divisa del ejercicio más reciente; **la divisa
es la de REPORTE, no la de cotización**: son distintas en cuanto entre un ADR,
y etiquetar en $ unas cuentas en € es el error de escala de 44.11—. Construye
**UN índice** `(key, año) → (valor, banda, status, provenance)` fusionando los
CUATRO bloques: ningún compositor sabe de qué bloque salió su métrica, y así el
mapa de §5.1 es la única fuente de «dónde va cada clave». Rachas con sus dos
denominadores (§5.2), cambios de banda, `WINDOW_STATISTIC_KEYS`, las 6
identidades de §5.3 con su gate numérico. Fixture de PEP **extraída de la BD**.
→ `presentation/history.py` (nuevo), tests · sin bump

**I3 — Plantillas y compositores.** **`ANNUAL_TEMPLATES` se declara en
`narrative.py`, en MAYÚSCULAS y como `Mapping[str, str]` PLANO** (claves
compuestas `'negocio.ventas_suben'`, nunca anidado): es la única forma de que
los dos guardias introspectivos lo vean —escanean `vars(narrative)` y exigen
`dict[str,str]`, así que un módulo aparte o un dict anidado los deja ciegos EN
SILENCIO, con sus asserts `>=7`/`>=10` satisfechos por los grupos viejos—. Si
se prefiere módulo aparte, la entrega incluye ampliar los guardias a
`vars(annual_report)`, **verificándolo rompiéndolo** (un gate sin entrada pasa
por vacuidad). Para el mapa y `WINDOW_STATISTIC_KEYS`, que no son
`dict[str,str]`, sonda propia: tocar una entrada y afirmar que
`templates_fingerprint()` cambia. Singular y plural en plantillas SEPARADAS.
Los 7 compositores + veredicto (§5.5) + variantes de §5.4 + `numbers.py`
(§5.6). Gates: cobertura (§5.1), identidades (§5.3), y **gate de chip** — para
las CUATRO secciones con pregunta, `chip == questions[key].verdict` con
evidencia evaluada, con las cuatro claves y no con una (con una sola, el caso
que falla puede ser justo el que no se prueba: aquí lo era). Goldens:
**PEP 1.9.0** (camino completo con matriz) · **JNJ 1.7.0** (con señales, sin
matriz, `why is None`) · **MCD 1.0.0** (sin señales ni umbrales) · sintético
sin dividendo.
→ `presentation/annual_report.py` (nuevo), `narrative.py`,
`presentation/numbers.py`, fixtures · **NARRATIVE 1.2.0 → 2.0.0**

**I4 — API y web.** El contrato de salida:

```python
@dataclass(frozen=True)
class ReportParagraph:
    text: str                      # prosa YA formateada, es-ES
    metric_keys: tuple[str, ...]   # lo que esta frase afirma, para enlazar

@dataclass(frozen=True)
class ReportSection:
    key: str                       # negocio|caja|balance|rentabilidad|contabilidad|dividendo|resistencia
    ordinal: int                   # 1..7
    title: str
    question_key: str | None       # accounting|cash|dividend|resilience, o None (§1,§3,§4)
    chip_band: Band | None
    chip_evidence: str | None      # evaluated|no-evidence|not-audited|not-recorded
    paragraphs: tuple[ReportParagraph, ...]
    covered_keys: tuple[str, ...]  # lo que comprueba el gate de §5.1
    grouped_green: tuple[str, ...]
    degraded_reason: str | None    # §5.4
```

con `ReportLayer.sections: tuple[ReportSection, ...] = ()` — **vacío, no
`None`**, para distinguir «backend anterior» de «no hubo material».

Cada sección lleva su desplegable con **las señales cuya CLAVE pertenece a esa
sección** según §5.1, **no las de su pregunta**: medido en PEP, el criterio por
pregunta descoloca 10 de 43 (`f_score`, `R9b`, `R10`, `E3` bajo la caja; `L4`,
`S2`, `S4`, `S5`, `S6` bajo la resistencia; `Q3` bajo la contabilidad). Así el
desplegable y la prosa hablan siempre de lo mismo, §1/§3/§4 ganan su tabla y §7
deja de contener el balance. `SignalTable` no cambia: recibe una lista filtrada
y el `Map` fusionado de las cuatro preguntas (las claves no se repiten entre
preguntas en ninguno de los 11 runs). Las derivadas (`stress`, `fcf_trend`,
banderas) van en `DERIVED_PLACEMENT`, que ya existe para eso. El chip sigue
saliendo de la PREGUNTA. Más las retiradas de §7.
→ `analysis/schemas.py`, `presentation/report.py`,
`packages/ui/src/investment-annual-report.ts`, `apps/web` · sin bump

**I5 — Paridad.** Móvil y el imprimible pintan desde la MISMA lista compartida.
El gate de paridad se amplía con un **TEST NUEVO**, no extendiendo los
existentes: `_SECTIONS` (líneas 33-40) es un `Path` clavado a
`investment-report-sections.ts` y su test reverso
(`test_la_pantalla_no_pinta_claves_que_el_motor_no_calcula`) trata como métrica
todo lo *metric-shaped* dentro de un array, así que al escanear el fichero
nuevo declararía **8 claves fantasma** (`ebit_clean`, `fcf_cfo`, `net_income`…
de `HORIZONTAL_ITEMS`, ausentes de `ALL_METRIC_KEYS`). El test nuevo lleva su
propio path, compara las claves de sección TS contra la lista Python de
`presentation/annual_report.py` y, si escanea métricas, resta la whitelist
horizontal. Más la revisión de MODO del imprimible, enumerando TODOS los
controles que ignora (44.24.H: hubo que hacerlo dos veces).
→ `apps/mobile`, `apps/web`, gate · sin bump

**I6 — Aceptación.** (a) el usuario lee PEP y MCD; (b) socimi en frío con
`tests/fixtures/edgar/CIK0000726728.json` (Realty Income) — atención al
denominador negativo de §5.4; (c) **un banco**: ver §8, exige red o fixture
nueva; (d) ronda de refinamiento de redacción.

Orden **I1 → I2 → I3 → I4 → I5 → I6**, verify verde y un commit por entrega.

### Tests que caen A PROPÓSITO en I4

**Web**: `tab-verdict.test.tsx:226` («las tres partes van EN HORIZONTAL» —
clava el grid de 3 `<section>` de 44.26; el informe es vertical), `:259` y
`:286` («Qué preocupa» / «Qué está bien», cuya fuente `_build_summary` se
retira), y el bloque `dictamenLists` de `investment-dictamen.test.ts`.

**Backend (14)**, al retirar `NEXT_CHECK_TEMPLATES` y `SUMMARY_TEMPLATES`:
entre ellos `test_investment_narrative.py:162` (golden de las entradas del
sumario) y `:184` (golden del margen de stress). **Tres son la única
afirmación de reglas que §5.4 hereda** —`narrative:341`
(`test_una_pregunta_permanentemente_no_auditable_no_aporta_nada_que_vigilar`),
`narrative:376`
(`test_nada_que_vigilar_esta_prohibido_si_algo_no_se_pudo_auditar`) y
`presentation:781`
(`test_un_verde_sin_evidencia_no_es_fortaleza_en_el_servidor`)—: **se
reescriben contra el compositor de secciones ANTES de retirar su función**, no
después.

**Deben seguir pasando SIN tocar** (guardarraíles que 44.26 compró y este plan
NO renegocia): `tab-verdict.test.tsx:217` (la auditoría nace plegada), `:241`
(en el imprimible va abierta y sin control) y `report-tabs.test.tsx:117`. Si
alguno cae, el cambio se pasó de alcance.

**Decisión pendiente antes de I4**: si el desplegable conserva el nombre
accesible de la pregunta («¿La contabilidad es de fiar?»). Si lo conserva,
`tab-verdict.test.tsx:369` y `:378` siguen pasando; si no, caen. Hoy el
implementador no puede saber cuál de las dos es a propósito.

---

## 7. Retiradas y estado final (en I4)

**Se va**: `next_checks` entero (`NEXT_CHECK_TEMPLATES`, `NextCheck`, su
response y su render en tres superficies) — arrastra el bug vivo de
`report.py:523`, que dice «ya ha cruzado hacia el rojo» de métricas en ÁMBAR ·
`concerns_intro`/`strengths_intro` y `_build_summary` · la cláusula de recuento
de las frases de pregunta (sus plantillas se conservan, sólo dentro del pliegue
de auditoría) · `stress_margin_sentence` (y su `quantize` que imprime «0 %») ·
`models_disagree` como frase suelta · el fallback de selección del cliente · la
card de las 4 preguntas como bloque principal (sus tablas bajan a los
desplegables; **«La auditoría del sello» SE CONSERVA**).

**Lo que QUEDA**: `ReportLayer = {threshold_profile, questions,
narrative_version, headline, why, sections}` — `next_checks` y `summary` fuera
de la dataclass, de `ReportLayerResponse` (`schemas.py:257-274`) y del tipo TS
(`packages/types/src/models/investment.ts:930-955`).

**Piezas huérfanas de `dictamenLists`, hoy vivas en las dos apps**:
`stress_sentences` y `scenariosHolding` → párrafos de §7 (el mockup ya los
usa); `clean` (banderas comprobadas y limpias, con su razón persistida) y
`discarded` (condiciones de «Evitar» descartadas) → el pliegue de auditoría.
Ninguna se retira en silencio.

**`investment-dictamen.ts` NO se borra**: pierde
`dictamenLists`/`DictamenRow`/`CleanCheck` y conserva `DICTAMEN_TITLES`,
`overflowLabel` y `permanentlyUnauditable` — o los tres se mudan a
`investment-annual-report.ts`. `permanentlyUnauditable` pierde su espejo en el
servidor al morir `next_checks`: el predicado (`not-audited` AND `load_bearing`
vacío) **tiene que reaparecer en el compositor**, porque es exactamente lo que
§5.4 llama «no se audita aquí».

**`STRESS_ANCHOR` viaja con el stress** a §7 (`WHY_ANCHOR` se queda con la
auditoría). Test al estilo 44.24.H: para CADA señal con
`locateMetric(key)?.anchor`, existe un elemento con ese `id`.

---

## 8. Prerrequisitos de datos

**44.27-E1 antes de leer MCD.** El informe narra deuda neta/EBITDA, margen
EBITDA y caja libre de mantenimiento **en prosa y con confianza**. Para MCD esas
cifras están INFLADAS por el bug de la amortización parcial (S4 3,17 donde la
real es 2,79). Narrarlo convierte un dato corrupto en una frase creíble. PEP
está verificada como no afectada; si E1 se retrasa, I6 se hace sólo con PEP y
se dice.

**Defecto de motor preexistente que bloquea I6(c).** En una financiera la
pregunta 3 sale `audited=False` con «D1: el motor no publicó esta señal»
mientras D1 **está calculada**: `LOAD_BEARING_FINANCIALS['dividend']` exige D1
y `_question_dividend` no la publica. O se añade `_band_signal('D1', ...)` a
esa pregunta **en I1** (donde ya se regeneran goldens; cambia el recuento de
señales), o I6(c) se ejecuta sabiendo que ese gris es un artefacto y se dice en
la phase doc. Sin una de las dos, la aceptación del banco valida una frase
falsa.

**No hay ninguna financiera** en el catálogo ni en los 9 ficheros del caché
EDGAR: I6(c) exige red o una fixture nueva.

---

## 9. Método de verificación (no negociable)

1. **Cada test se verifica rompiendo LA LÍNEA que dice proteger**, comprobando
   que la rotura ENTRÓ (`assert` del patrón único antes de sustituir).
2. **Goldens extraídos de runs reales**, no escritos a mano.
3. **Gates probados haciéndolos fallar**: cobertura (§5.1), identidades (§5.3),
   chip (I3), simetría (§5.5), dígitos, paridad de secciones (I5).
4. **Suite**: nunca dos pytest a la vez; `rm -f log` antes de lanzar y
   `EXIT=$?` dentro; intérprete del venv; al final `make verify`.
5. **Prettier por fichero.**

---

## 10. Riesgos asumidos

- **Una frase creíble equivocada es más cara que un chip raro.** Intrínseco.
  Mitigación: identidades con gate, cobertura bidireccional, cortes del run, y
  toda afirmación enlazada por `metric_keys`.
- **El vocabulario de §5.5 se quedará corto** en empresas que no se parezcan a
  las 4 del catálogo. Asumido: se itera. Sin lectura aplicable se dice
  «situación no clasificada», nunca la más cercana.
- **Dos formateadores** y ningún fixture que los ate hasta que se cree (§5.6).
- **El informe alarga la pantalla.** Se acepta: es un informe.

---

## 11. Registro de la revisión del plan

**Primera pasada (30-ago)**: el workflow **no llegó a ejecutarse** (5 agentes
muertos por límite, 0 comprobaciones). Se dice por la lección de 44.14: su
resultado vacío es indistinguible de una revisión limpia. Verificado a mano:
`_engine_shape` no cubre `SAFETY_MATRIX`; los goldens de 44.25 sí cazan 1B;
`templates_fingerprint()` enumera a mano; `HEADLINE_TEMPLATES` ya tiene
`watch`; fixtures EDGAR de MCD, JNJ y Realty Income.

**Segunda pasada (31-ago)**: 1 de 5 agentes vivo. Aportó y se incorporaron: el
fixture de paridad de formato **no existe**; el gate de 44.20 **no es ampliable
por extensión** (8 claves fantasma); el mapa métrica→sección tenía **dos casas
contradictorias**; I4 no inventariaba los tests de 44.26 que tumba.

**Tercera pasada (31-ago)**: 4 de 4 agentes, **41 hallazgos brutos, 16
confirmados** (7 bloqueantes) y 6 descartados con motivo — uno de ellos por
usar los cortes de HOY en vez de los del run, que es el invariante 6. Todos
incorporados arriba. Los más caros: la atribución de deuda/EBITDA del mockup
**estaba invertida** (la deuda sube 13,2 % y el EBITDA cae 6,8 %: pesa más la
deuda), 1B tocaba una sola condición dejando la O viva por el otro lado, el
mockup incumplía su propio gate de cobertura, y los tres casos duros no tenían
mecanismo — con un **verde falso** en «sin dividendo» y **dos métricas en verde
con denominador negativo** en la socimi. Cobertura: ~32 comprobaciones
ejecutadas, sin pytest, con SELECTs de sólo lectura.

---

## 12. Criterio de aceptación

El del usuario, literal: abrir el informe y poder decir **«la mantengo»** o
**«me tengo que preocupar»** — y si duda, saber en qué pestaña mirar. La vara
concreta: el informe de PepsiCo producido por I4 cuenta la misma historia que
el mockup de §1 **y cubre las 16 claves obligatorias del gate**; el mockup
cubre 11 y esa diferencia es esperada, no un fallo.
