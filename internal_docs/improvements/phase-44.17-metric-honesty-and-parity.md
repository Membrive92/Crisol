# Plan — honestidad y paridad de las métricas (PHASE-44.17 → 44.20)

**Estado**: propuesta, sin implementar
**Fecha**: 2026-08-08
**Origen**: revisión pedida por el usuario («revisa que todas las métricas se
están calculando»). 41 comprobaciones auditadas, **23 defectos confirmados**.
**Depende de**: [PHASE-44.16](../phases/phase-44.16-legacy-run-tolerance.md), sin
commitear todavía.

---

## 0. Lo que NO hay que arreglar: el cálculo

Conviene empezar por aquí porque acota el plan. **El motor cumple.** Verificado
contra la BD real y ejecutándolo:

| | |
|---|---|
| Catalogadas en `ALL_METRIC_DEFINITIONS` | **64** |
| Emitidas dentro del `AnalysisRun` (JNJ, motor 1.3.0) | **57** |
| Calculadas al vuelo (V1–V7, valoración) | **7** — probadas, 7/7 correctas |
| Catalogadas que ninguna capa produce | **0** |
| Emitidas sin catalogar | **0** |

Las 7 de valoración están fuera del run **por diseño de PHASE-44.12**: un
múltiplo se mueve con el precio y un run tiene que poder reejecutarse dando lo
mismo.

Los huecos de McDonald's también son legítimos y quedan **descartados como bug**:
no publica coste de ventas anual en su XBRL (0 hechos anuales frente a 21 de
JNJ), porque presenta gastos **por naturaleza** (Food & paper, Payroll,
Occupancy). El adapter acierta al no cogerlo; sumar trimestres sería inventarse
el dato — y el concepto que sí etiqueta (`CostOfGoodsAndServicesSold`, sólo
trimestral, ~10 % de los ingresos) es un componente, no el total.

**Los 23 defectos están todos entre el cálculo y la pantalla.**

---

## 1. El principio que ordena el plan

> Una ausencia nunca se presenta como un valor, y menos como un aprobado.

Es la convención «hueco ≠ 0» que el motor aplica desde PHASE-44.2 §4.5 —
y que el propio motor incumple sobre su salida. Es también la raíz de
PHASE-44.16, que se arregló ayer para los runs viejos. Aquí reaparece en **cuatro
formas más**, y por eso la primera fase es ésa y no la más grande.

El segundo principio, subordinado: **una métrica calculada que no se ve es
trabajo tirado**. Es el patrón de PHASE-44.10 (tres piezas del motor que nadie
llamaba) y explica el resto del plan.

---

## 2. Inventario de los 23

Agrupados por la fase que los cierra, no por la lente que los encontró.

| # | Dónde | Qué |
|---|---|---|
| **44.17 — lo que no se pudo medir, se dice** ||
| 20 | `engine/synthesis.py:229` | 7 cruces publican «no se ha encendido» cuando **no se pudieron evaluar** |
| 19 | `packages/ui/investment-metric-rows.ts:105` | se pinta el motivo del ejercicio **más antiguo**: manda a ingerir historia que no arregla nada |
| 22 | `engine/base_ratios.py:519` | L4 dice «denominador cero» cuando es el **mejor resultado posible** |
| 23 | `web/tab-forensic.tsx:89` | leyenda escrita a mano, falsa para MCD en los cinco años |
| — | `engine/synthesis.py:279` | `unavailable_count` mezcla cuatro significados (hallazgo propio) |
| 21 | `concept_map.py:150` | el motivo «falta la partida 'cogs'» es cierto pero se lee como fallo de carga |
| **44.18 — la banda que no llega** ||
| 16 | `thresholds/service.py:115` | **40 sembradas, 42 con banda**: S7 y S8 nunca entraron |
| 17 | `packages/ui/investment-metric-index.ts:100` | `applies` y `model_variant` se descartan al llegar al cliente |
| **44.19 — las métricas que un gate escondía** ||
| 6 | `web/tab-dividend.tsx:33` | D1, D8, T2, T3 ocultas para toda financiera, **aunque reparta** |
| 7 | `web/tab-dividend.tsx:33` | Q1, Q2, Q3, Q5 (calidad de la caja) ocultas por un gate del que **no dependen** |
| **44.20 — paridad móvil real** ||
| 8 · 18 | `packages/ui/investment-report-sections.ts:25` | la capa compartida cubre **57 de 64**; 7 escritas a mano en web |
| 9 | `mobile/report-tabs.tsx:222` | el **DuPont entero** no existe en móvil (4 bloques donde web tiene 5) |
| 1 | `mobile/report-tabs.tsx:325` | **Trayectoria del dividendo** ausente (incluida la serie de DPS) |
| 10 | `mobile/report-tabs.tsx:245` | **Evolución sin una sola métrica** (E3, E4) |
| 11 | `mobile/analysis.tsx:159` | «Evitar» sin sus `blocking_reasons` |
| 12 | `mobile/report-tabs.tsx:439` | sin sub-pestaña «Confianza y datos» |
| 3 · 13 | `mobile/report-tabs.tsx:370,402` | Valoración sin `notes[]`, sin `reason`, sin capitalización ni FX |
| 4 | `mobile/report-tabs.tsx:379` | «puedes introducir un precio a mano» **sin campo para hacerlo** |
| 14 | `packages/ui/investment-run-version.ts:75` | móvil no tiene el aviso de run caducado de 44.16 |
| 2 | `mobile/security-search.tsx:37` | sin `intent`: SPY elegible en Análisis → el callejón que 44.15 cerró en web |
| 15 | `mobile/analysis.tsx:67` | pide `view='all'` (web pide `'latest'`): con una reexpresión, dos columnas del mismo año |
| — | `mobile/year-matrix.tsx:46` | **nunca pinta `cell.title`**: en móvil ningún motivo por celda se ve jamás |
| **Suelta** ||
| 5 | `engine/valuation.py:145` | `quote_currency` se rellena y no lo lee nadie: «Tipo aplicado 1,08» sin decir de qué par |

---

## 3. PHASE-44.17 — «Lo que no se pudo medir, se dice» (motor **1.4.0**)

La primera porque es la que corrige **afirmaciones falsas sobre datos reales**.
Las otras tres ocultan información; ésta la tergiversa, que es peor.

### 3.1 Las banderas que no se pudieron comprobar (#20)

`evolution.py:389` hace `continue` cuando falta un dato de entrada. Sin `cogs`,
el cruce C3 (*inventario vs coste de ventas*) **no se ejecuta jamás**, no emite
bandera, y `synthesis.py:_flag_signal` traduce «no hay bandera» a **«no se ha
encendido»** — que se lee como *comprobado y limpio*.

Afecta a 7 señales: C1, C2, C3, Q4, B1, B2, B4.

**Cambio**: la capa de coherencia deja de tragarse el hueco y devuelve, además de
las banderas encendidas, **qué comprobaciones no pudo hacer y por qué**. La
síntesis las emite con `counted=False` y un motivo real («no se pudo comprobar:
falta el coste de ventas») en vez del «no se ha encendido» actual.

> **Corrección de alcance: es más grande de lo que parecía.** Mi primera lectura
> dijo «contenido, sólo dos sitios». Falso — ésos eran sólo los que abortan con
> `continue`. Verificados **cinco** puntos de aborto silencioso: dos con
> `continue` (`evolution.py:389` en `_gap_rule`, y `:488` en la regla de fondo de
> comercio) y tres con `return ()` (`evolution.py:660`, `dividend.py:312` para la
> anomalía fiscal Q4, y `dividend.py:367`). La revisión sostiene además que los
> afectados son **8 de las 10 señales de bandera** de la síntesis (C1–C8 más Q4 y
> B1/B2/B4); eso no lo he contado uno a uno, pero los cinco abortos sí están.
>
> Las capas forense y base **sí** devuelven `not_computable` con motivo — por eso
> los huecos de las métricas sí se ven, y los de las banderas no.

**Diseño propuesto** (bifurcación 1 de la revisión, que doy por buena con la
salvedad de abajo): un tipo nuevo `FlagEvaluation` con
`outcome: fired | clear | not_computable`, **uno por regla y por serie** —no por
año, porque las reglas ya exigen rachas—, llevando qué ejercicios se pudieron
mirar y cuáles no. `Flag` no se toca: un `Flag` sólo existe cuando salta, y uno
«que no ha saltado» acabaría en la matriz de banderas pintando dieciocho tarjetas
de «esto no ha pasado».

Dos detalles del diseño que son los que de verdad cierran el defecto:

1. **El default tiene que ser pesimista.** Si la síntesis no encuentra evaluación
   para una clave, la señal sale «no se ha podido comprobar», no «limpia». Hoy el
   default es el optimista y *ése* es el bug; con el pesimista, añadir una regla
   nueva y olvidar publicar su evaluación **se ve** en vez de pintar verde.
2. **Un solo sitio decide qué significa «no se pudo comprobar».** Cinco abortos
   parcheados con cinco `if` es escribir la misma decisión cinco veces y
   garantizar que divergen — el argumento que ese mismo fichero ya usa para que
   C1 y C3 compartan `_gap_rule`.

Y un aviso fino de la propuesta que vale su peso: `_growth` devuelve `None` por
**dos** motivos distintos —falta el dato, o el ejercicio anterior valía cero— y
confundirlos haría que el motivo mintiera («falta el coste de ventas» cuando lo
que pasó es que valía 0). Hay que separarlos antes de redactar la razón.

### 3.1.b Lo que la crítica tumbó (revisión del 2026-08-09)

La primera pasada se quedó sin crítica (el agente murió por límite de sesión). Se
relanzó con tres lentes y encontró **ocho problemas de severidad alta**. El
diseño se sostiene en lo esencial —tipo aparte, default pesimista, una sola
decisión centralizada— pero **no se puede implementar tal cual**:

1. **El inventario de sitios está mal, en las dos direcciones.** Hay exactamente
   **8** llamadas a `_flag_signal`, no 10 (mi «8 de 10» era falso). Y de los
   cinco abortos que verifiqué, **dos ni siquiera son señales de la síntesis**
   (`evolution.py:488` es C5; `:660` es la financiación externa). Quedan sin
   cubrir C2 (`evolution.py:440`) y las guardas reales de B1/B2/B4
   (`dividend.py:374`, `:390`, `:408`). Implementado tal cual, **5 de las 8
   seguirían diciendo «no se ha encendido»**.
2. **El default pesimista sin gate de cobertura convierte el falso verde en un
   falso gris universal.** Si una clave no está en el mapa de evaluaciones, todas
   las empresas verían «no se ha podido comprobar», incluidas aquellas donde sí
   se comprobó limpio. Hace falta el gate simétrico al que ya existe para
   banderas sin nombre (`test_investment_engine_contract.py:132`): *toda clave
   usada en `_flag_signal` tiene evaluación*.
3. **`_runs` no cuenta años, busca ventanas CONSECUTIVAS.** Con años evaluables
   {2016, 2018, 2020, 2022} y `sustained=2`, el criterio propuesto
   («evaluables ≥ sustained») diría «limpio» cuando la regla **no puede
   encenderse jamás**. El criterio correcto es «existe una racha de `sustained`
   años evaluables **seguidos**».
4. **C7 dispara con UN solo año** (`evolution.py:548`), y C4 cuenta sobre todos
   los statements, no sobre pares. Centralizar la **decisión** es correcto;
   centralizar el **umbral** rompería esas dos.
5. **`outcome` sin default no compila**: `reason` ya lleva default, así que un
   campo obligatorio detrás revienta al definir la clase. Y haría fallar un test
   existente por el motivo equivocado (`TypeError` en vez del `ValueError` que
   espera `pytest.raises`).
6. **En el backend no hay riesgo de compatibilidad** —un `AnalysisRun` nunca se
   rehidrata a dataclasses; el `__post_init__` sólo corre al calcular— pero en
   TypeScript `outcome` **debe ser opcional**, por la misma regla de la unión de
   versiones de 44.16.
7. **Hay un TERCER modo de ausencia: el cero IMPUTADO.** `inventory`,
   `dividends_paid` y `acquisitions` están en `IMPUTABLE_ZERO_ITEMS` y llegan
   como `Decimal(0)` con procedencia `IMPUTED_ZERO` cuando el filing no los
   publica, mientras que `cogs` está **deliberadamente fuera** (su docstring: un
   cero ahí «convertiría un margen imposible en un número creíble»). Para una
   empresa cuyo inventario sea imputado, `_growth(0, 0)` devuelve `None` por
   «el anterior valía cero» y no por «falta el dato», así que redactar el motivo
   sin mirar la procedencia produciría una frase falsa. El precedente de que la
   procedencia importa ya está en el fichero: `_confidence` se niega a contar un
   `IMPUTED_ZERO` como sourced.

   > **Corrección (2026-08-09).** La revisión afirmaba que este caso se daba en
   > McDonald's, y **es falso**: verificado contra la BD, su inventario es dato
   > REAL (55,6 M · 52 M · 53 M · 56 M · 61 M, procedencia `sourced`) y lo que
   > falta es `cogs`. El motivo que se redactaría para MCD —«falta la partida
   > cogs»— sería **correcto**. El problema de diseño sigue en pie para otras
   > empresas; lo que no es cierto es que muerda en el caso que motivó la fase.
   > Baja de «el que más cambia las cosas» a «hay que mirar la procedencia».
8. **El perfil de seguridad se queda fuera** y es lo primero que se lee:
   `_safety_profile` sigue consultando el mapa optimista, así que una B4 no
   computable se lee como «no está en rojo» y no bloquea el sello que pinta el
   hero.

**Consecuencia para el plan**: 44.17 es más grande de lo estimado y su diseño
necesita otra pasada antes de escribirse.

Lo que de verdad bloquea, tras verificar los ocho uno a uno, son **(1), (2) y
(3)**: el inventario de sitios está mal en las dos direcciones, el default
pesimista sin gate de cobertura cambia un falso verde por un falso gris
universal, y el criterio de «suficientes años» es aritméticamente incorrecto
porque `_runs` busca rachas **consecutivas** y no un cardinal. Con (4) encima
—C7 salta con un solo año— queda claro que se puede centralizar la DECISIÓN pero
no el UMBRAL.

Los tres son de diseño, no de esfuerzo: implementarlos mal metería en el motor
exactamente la clase de defecto que esta fase viene a quitar.

### 3.2 Los contadores que mezclan cuatro cosas

`unavailable_count = len(signals) − len(counted)` mete en un cubo: (a) no se
pudo calcular, (b) **la bandera no saltó — buena noticia**, (c) informativa por
diseño, (d) no aplica.

Medido en MCD, *«¿La contabilidad es de fiar?»*: `evaluated=3, unavailable=7`.
De esas 7, **sólo 2 son huecos reales**; 5 son banderas limpias. La pantalla
**subestima** la evidencia mientras el veredicto **verde** la sobreestima.

**Cambio**: separar «comprobado y limpio» de «no se pudo». Los campos nuevos van
**opcionales** en `packages/types` — la lección de 44.16, aplicada de entrada
esta vez: la tabla seguirá conteniendo runs sin ellos.

> **Depende de §3.1, y no es negociable.** La revisión adversarial lo marcó como
> bloqueante: «comprobado y limpio» es una afirmación que el motor **hoy no puede
> sostener**, porque el dato «¿se pudo evaluar esta regla?» no existe en ningún
> punto del flujo. Partir los contadores antes de que la capa de coherencia
> publique su evaluabilidad produciría un `clean` inventado.
>
> **Y hay una regresión concreta que evitar**: con el reparto ingenuo, una
> financiera pasa de `no-evidence` a **verde confiado** — el caso exacto que
> `synthesis.py:84-88` declara como motivo de existir de los contadores y que
> cubre un test («una financiera no puede pintar…»). El reparto tiene que dejar
> ese caso donde está.

### 3.3 La guarda «sin evidencia» es todo-o-nada

`questionEvidence` marca `no-evidence` sólo si `evaluated_count === 0`. Con MCD
en 3 de 10 pinta **verde confiado**, aunque las dos pruebas que responden esa
pregunta (M-Score y C-Score) estén muertas.

**Cambio**: que el estado degrade con la proporción de evidencia real, no con un
`=== 0`. Requiere decidir el corte — es la única decisión de esta fase que no es
mecánica.

### 3.4 El motivo del ejercicio equivocado (#19, #23)

`metricRow` hace `.find()` sobre una serie ordenada de más antiguo a más
reciente. En MCD el M-Score falla en 2021 por «sin ejercicio 2020» y en 2022–2025
por el coste de ventas: **se pinta el de 2021**, así que el informe sugiere
ingerir más historia, que no arreglaría nada.

En móvil es peor: `year-matrix.tsx` **nunca pinta `cell.title`**, así que el
motivo equivocado es el único visible.

Va con ello la leyenda de `tab-forensic.tsx:89`, que afirma a mano que sólo el
primer ejercicio se queda sin M-Score — falsa para MCD en los cinco años. **Se
deriva del run o se borra**; una premisa escrita a mano es lo que este proyecto
lleva siete lecciones documentando.

### 3.5 L4 y el «denominador cero» (#22)

No tener deuda venciendo a 12 meses es el **mejor** resultado del muro de
vencimientos, no un hueco. Hoy se pinta como dato ausente y la empresa pierde una
señal de resiliencia.

### 3.6 Consecuencias de esta fase

- **Sube `ENGINE_VERSION` a 1.4.0**, porque cambia lo que el run contiene.
- Los runs existentes quedan «caducados» → **se dispara el `StaleRunNotice` que
  construí en 44.16**, invitando a reejecutar. Encaja: el usuario reejecuta y
  recibe todo lo demás.
- Hay que **reejecutar JNJ y MCD** para ver el efecto.
- **Registrar la huella nueva en `ENGINE_SHAPE_FINGERPRINTS`.** Verificado:
  `test_investment_engine_contract.py:80-92` afirma que la forma del motor no
  cambia sin mover la versión, y falla si la versión nueva no tiene huella —
  dando en el mensaje la que hay que pegar. El gate **funciona**; sólo hay que
  saber que se activa. Aplica a **toda** fase que suba el motor (aquí y en 44.19).

---

## 4. PHASE-44.18 — «La banda que no llega»

Pequeña en código y con la mejor relación valor/esfuerzo, porque hoy es
**latente** y se activa sola en cuanto analices un banco — y Santander es
alcanzable desde 44.15.

### 4.1 S7 y S8 nunca se sembraron (#16)

`scoring_thresholds` tiene **1440 filas y 40 métricas**; el catálogo declara
**42 con banda**. `seed_if_empty` hace `if count > 0: return 0`: siembra una vez
y **toda métrica añadida después queda fuera para siempre**. S7 y S8 llegaron en
44.10, con la tabla ya llena.

No se ve hoy porque `load_thresholds` cae al catálogo. Lo que se pierde es lo
único que la tabla aporta: la diferenciación por (sector × norma). En concreto,
`seed.py:32` declara `NOT_FOR_FINANCIALS = {"S7"}` con un docstring que explica
que aplicarle la banda 1–2 a un banco *«pintaría un rojo permanente que no
informa de nada»*… y esa exención es **inerte**, porque `applies` vale `True` por
defecto y S7 no tiene fila. Una decisión razonada y documentada que **nunca llegó
a funcionar**.

**Cambio**: sembrado **incremental** — insertar sólo las `metric_key` ausentes,
sin tocar las presentes. Un reseed completo no vale: el seed muta las filas in
situ y el hash es irreversible (por eso 44.9 tuvo que persistir
`thresholds_used`).

**Y un detector**, que es lo que impide la recurrencia: una comprobación que
afirme *«toda métrica con banda en el catálogo tiene filas sembradas»*. Hoy
fallaría — que es la prueba de que detecta. Es la lección de 44.9: a la enésima
premisa caducada, un gate, no otra nota. Sobre **dónde** vive, ver §7.1: no en
`make verify`.

> **Corrección de la revisión: el arreglo puede que no vaya en la tabla.** La
> exención de S7 no es *calibración*, es **aplicabilidad** — la misma categoría
> que la de los forenses, que vive en el **engine** y no en el seed. Si S7 lleva
> la guarda `is_financial` en `base_ratios.py` (como ya la llevan los forenses),
> la honestidad deja de depender de que exista una fila en la BD. Eso importa
> porque `load_thresholds` cae a `ALL_DEFAULT_THRESHOLDS` cuando falta la fila:
> con el arreglo sólo en la tabla, **una BD recién creada reintroduce el bug**.
> Conclusión: sembrar S7/S8 igualmente (la tabla debe estar completa), pero poner
> la aplicabilidad donde no se pueda perder.

> **§4.1 sin §4.2 no entrega nada.** Tras sembrar, S7 de un banco viaja en
> `thresholds_used` con `applies=false`… y `effectiveThreshold` lo descarta antes
> de llegar a la pantalla. Las dos mitades van juntas o la fase no se nota.

### 4.2 `applies` y `model_variant` mueren en el último tramo (#17)

`effectiveThreshold` copia de `thresholds_used` la dirección y los cuatro cortes,
y **descarta los dos únicos atributos por los que la tabla se diferencia del
catálogo**. Consecuencia doble: una financiera vería el número sin semáforo pero
indistinguible de «no se pudo colorear», y una empresa IFRS se juzga con cortes
US-GAAP **sin que nada lo declare en pantalla** — justo la deuda que 44.15 cerró
en el backend.

---

## 5. PHASE-44.19 — «Las métricas que un gate escondía»

Ocho métricas ya calculadas, con valor y banda, recuperadas cambiando un `if`.

`synthesis.py:520` decide:

```python
if series.security.is_financial:
    return "not_applicable"          # ← un banco que SÍ reparte
...
if dividends is None or dividends == 0:
    return "not_applicable"          # ← no reparte
```

Dos situaciones distintas colapsadas en una etiqueta, y `tab-dividend.tsx:33`
oculta la pestaña entera con ella.

| Caso | Qué tiene sentido enseñar |
|---|---|
| **No reparte** | D1/D8/T2/T3 no aplican de verdad. Q1–Q3/Q5 (calidad de la caja) **sí**: no dependen del dividendo |
| **Financiera que reparte** | D1 (payout sobre beneficio) es **perfectamente válido** para un banco, y T2/T3 también. Lo que no aplica es la cobertura sobre caja libre (D2–D6) |
| **Socimi** | ya cubierto por el ajuste sobre FFO |

**Cambio**: separar el motivo de la etiqueta —«no aplica el modelo de caja libre»
no es «no hay dividendo»— y enseñar los bloques que sobreviven en cada caso.
Q1–Q3/Q5 dejan de estar tras el gate en cualquier escenario.

> **Dos avisos de la revisión, los dos verificables antes de escribir código.**
>
> 1. **`is_financial` es una columna PERSISTIDA**, no algo que se derive del SIC
>    en tiempo de análisis. Así que arreglar la lógica del veredicto puede quedar
>    **inerte sobre los datos existentes** si la columna está mal puesta. Primer
>    paso de la fase: mirar qué hay en esa columna para los valores del catálogo,
>    igual que se hizo con `fx_rate_at_trade` en 44.11.
> 2. **`dividend_verdict` puede ser `null`** (`investment.ts:561` lo tipa
>    `DividendVerdict | null`). Hoy el `=== 'not_applicable'` lo deja pasar por
>    casualidad; un switch de casos sin rama para `null` lo rompería.
>
> Y una tercera del mismo orden: si la pestaña pivota sobre `run` (JSONB de
> cualquier versión) **y** sobre `security` (fila viva de otra query), hay que
> decidir cuál manda cuando se contradicen. Es literalmente el problema de 44.16
> otra vez, y la respuesta debería ser la misma: manda el run, que es la foto.

---

## 6. PHASE-44.20 — «Paridad móvil real»

El bloque más grande y el menos urgente si sigues probando en web. Trece
hallazgos, pero **un solo punto de apalancamiento**.

### 6.1 La capa compartida cubre 57 de 64

Las 7 restantes (`DUPONT_OM/TAX/FIN`, `E3`, `E4`, `T2`, `T3`) están **escritas a
mano en los tabs de web**, y móvil renderiza estrictamente desde el fichero
compartido. Es literalmente lo que el docstring de ese fichero dice prevenir,
reintroducido por la puerta de las claves hardcodeadas.

La dificultad real es menor de lo que parecía. Esas secciones **no son listas
planas** —la Trayectoria mezcla dos escalares, una serie y dos métricas; el
DuPont añade dos filas de comprobación que no son métricas—, así que lo
compartido necesita **filas tipadas** y no un `string[]`. Pero ADR-0001 sigue
mandando: describe **qué** se muestra y en qué orden, nunca **cómo**.

> **Una premisa mía era falsa, y ahorra trabajo.** Había asumido que el DuPont
> necesitaba un índice propio porque sus `MetricResult` vivían sólo en
> `dupont[]`. **No es cierto**: `DUPONT_OM`, `DUPONT_TAX` y `DUPONT_FIN` están
> también en `metrics[]` (`base_ratios.py:425-427`, y lo confirma mi volcado de
> JNJ, donde aparecen entre las claves de `base_ratios.metrics`). Así que el
> índice global que ya existe sirve, y **toda la maquinaria de `MetricSource` /
> `dupontIndex` sobra**. Lo único que `dupont[]` aporta en exclusiva son
> `check_three` y `check_five`, que no son métricas.

### 6.2 El test que no podía cazarlo

`report-tabs.test.tsx:190` comprueba que móvil lista *«las mismas familias de
ratios que la web»*… contra la **lista compartida**, que es justo donde el DuPont
no está. Su comentario describe el modo de fallo contrario al que ocurrió.

**Cambio**: el test se ata al **catálogo del motor (las 64)**, no a la lista
compartida, de modo que añadir una métrica sin darle sitio en pantalla **falle en
CI**. Hoy fallaría con 7 — la prueba de que detecta.

### 6.3 El resto

Tarjetas ausentes (Trayectoria, DuPont, Evolución, Confianza,
`blocking_reasons`), Valoración sin contexto (`notes[]`, `reason`, FX,
capitalización), el callejón del precio manual **sin campo**, el aviso de run
caducado de 44.16, la prop `intent` del buscador, y el `view='all'` que
duplicaría columnas ante una reexpresión (latente: 0 filas hoy).

Y transversal: **`year-matrix.tsx` de móvil nunca pinta `cell.title`**. Sin
tooltips en táctil hace falta otro afordance; sin él, ningún motivo por celda se
ve en móvil.

---

## 7. Los detectores tienen que vivir donde CI los ejecute

Este plan propone **dos gates nuevos** (§4.1 «toda métrica con banda está
sembrada» y §6.2 «toda métrica del catálogo tiene sitio en pantalla»). La
tentación es cablearlos a `make verify`, como se hizo con `knip` en PHASE-43.

**No sirve.** Verificado en `.github/workflows/ci.yml`: **CI no ejecuta `make
verify`**. Corre `pnpm lint`, `typecheck`, `test`, `build` en el job de frontend,
y `ruff`, `black`, `mypy`, `pytest` más `check_docs.py` en el de backend. Un
detector que sólo viva en `make verify` depende de que alguien lo lance a mano —
que es exactamente la definición de costumbre, no de invariante ([PHASE-44.11]).

Corolario incómodo que conviene anotar: **`knip` tampoco corre en CI**, aunque la
lección de PHASE-43 lo declare «cableado a `make verify`». Las dos cosas son
ciertas y no se contradicen; simplemente `make verify` no es CI.

Así que:

| Detector | Dónde va |
|---|---|
| Umbrales sembrados ↔ catálogo con banda | **test de `pytest`** (backend) |
| Catálogo del motor ↔ métricas con sitio en pantalla | **test de `vitest`** en `packages/ui` |

Los dos tienen que **probarse rompiéndolos**, como se hizo con las regresiones de
44.16: hoy fallarían (2 métricas sin sembrar, 7 sin sitio), y ésa es la prueba.
Y merece la pena decidir, aparte de este plan, si `knip` y `make verify` entran
en CI — pero eso es otra fase.

---

## 8. Orden, y por qué

```
44.17  motor 1.4.0 · mensajes honestos        ← primero: corrige afirmaciones FALSAS
  │                                             y su bump dispara el aviso de 44.16
  ├─ 44.18  umbrales                          ← independiente, pequeña, latente-pero-armada
  ├─ 44.19  gate del dividendo                ← independiente, 8 métricas por un `if`
  └─ 44.20  paridad móvil                     ← última: se apoya en las tres anteriores,
                                                y su capa compartida las hereda
```

44.18 y 44.19 **no dependen entre sí ni de 44.17**: si quieres resultado visible
rápido, cualquiera de las dos vale como primera. 44.20 va última a propósito —
mover una sección a la capa compartida **antes** de arreglar el gate del
dividendo obligaría a mover la misma sección dos veces.

**Antes de todo esto**: cerrar 44.16 con tu prueba manual. Son cuatro fases sin
commitear y añadir una quinta encima empeora la revisión.

---

## 9. Riesgos

- **El bump a 1.4.0 caduca los runs existentes.** Es el comportamiento correcto y
  ya está construido (44.16), pero verás el aviso en JNJ y MCD hasta reejecutar.
- **Cambiar los contadores toca el contrato de 44.9.** Campos nuevos opcionales,
  nunca renombrar los existentes; `questionEvidence` tiene que seguir leyendo
  runs que sólo traen los viejos.
- **El sembrado incremental no puede tocar filas existentes.** Si las toca,
  invalida la reproducibilidad que 44.9 compró con `thresholds_used`.
- **44.20 es un refactor de presentación, no de cálculo.** Ningún número puede
  moverse; si se mueve, es un bug introducido. Conviene una comparación
  antes/después de los valores pintados.

---

## 10. Criterios de cierre

- `make verify` verde, más los dos detectores nuevos (umbrales sembrados,
  catálogo ↔ pantalla) **probados reintroduciendo el fallo**.
- Reejecutar JNJ y MCD y comprobar sobre datos reales: ningún «no se ha
  encendido» sobre un cruce no evaluado, ningún motivo del ejercicio equivocado,
  y el veredicto de MCD en *«¿La contabilidad es de fiar?»* dejando de presumir
  de verde.
- Las 64 métricas con sitio en pantalla en **las dos** apps, afirmado por el test
  contra el catálogo.
- Documentación: una phase doc por fase y las lecciones que salgan — en especial
  la de la **exención documentada que nunca se ejecutó**, que es una variante
  nueva de la familia «premisa escrita a mano».
