# PHASE-44.27 — Primero lo que está MAL, luego lo que se explica mal, y sólo entonces lo que falta

**Estado**: ⏳ plan, sin código escrito
**Fecha**: 2026-08-30
**Origen**: dos auditorías del mismo día, lanzadas por dos preguntas del usuario
sobre el informe de McDonald's.

> **Este documento es una foto fechada, no un documento vivo.** Los números que
> lleva dentro (valores del caché de EDGAR, versiones del motor, recuentos) son
> lo que se midió el 30-ago-2026 y envejecen a propósito: su valor es decir cómo
> estaban las cosas cuando se decidió esto. No lo actualices — escribe otro.

---

## 0. El bloqueante: nada de esto empieza hoy

**Hay una pila de entregas verdes sin probar y sin commitear.** Ver
[`../HANDOFF.md`](../HANDOFF.md) para el inventario completo; en el módulo de
Inversión, sin commitear: 44.23, **44.24 entera** (A·M·C·B·D·E·F·G),
[44.25](phase-44.25-verdict-argues-its-why.md) y
[44.26](../phases/phase-44.26-dictamen-reads-top-down.md).

Motor en **1.9.0**, narrativa en **1.2.0**.

Y hay un paso previo que es **gratis y cambia de qué merece la pena discutir**:

> ### Paso 0 — Relanzar el análisis de MCD con el motor actual
>
> La pantalla del usuario muestra B1, B2 y B4 como **«no se comprobó»**. El motor
> de hoy, ejecutado sobre las fixtures reales, emite `clear` en las tres. Ese run
> vivo es anterior a PHASE-44.17, así que **media tabla se está leyendo mal** y
> parte del debate sería sobre un artefacto. Además el motor cambió de versión
> con 44.25, de modo que sin relanzar no se ven ni `FZ_P` ni la matriz del sello.

**Ninguna entrega de este plan debe empezar antes de la prueba manual del
usuario sobre 44.24/44.25/44.26.** Apilar más cambios de motor sobre una pila sin
probar convierte un fallo en una búsqueda a ciegas entre once entregas.

---

## 1. De dónde sale este plan

### Auditoría A — «¿El dividendo de MCD está realmente en riesgo?»

Pregunta literal del usuario: _«Tengo dudas que en el caso de MCD el dividendo
esté en riesgo. Revisa todas las métricas y su función real porque diría que esto
es demasiado estricto en la práctica de las empresas»_.

Workflow de 4 agentes (mapa + 2 lentes + crítico adversarial), **4/4 vivos**, con
un antídoto explícito en el encargo: el riesgo real era aflojar umbrales para que
a McDonald's le saliera bonito, así que cada hallazgo tenía que clasificarse como
**(A)** umbral mal calibrado *con argumento independiente de MCD*, **(B)** defecto
de agregación, o **(C)** correcto pero incómodo — y (C) era el default.

**Veredicto: el rojo es CORRECTO como color y DEFECTUOSO como explicación. No se
toca ni un corte.**

Lo que lo decide: **el rojo está sobredeterminado por tres mecanismos
independientes.**

| Mecanismo | Valor medido | Qué tiñe |
| --- | --- | --- |
| `B3` años de dividendo en caja | 0,1513 años | la pregunta 3, él solo |
| `FZ` X-Score de Zmijewski | 0,8684 → P = 80,7 % | la pregunta 4 |
| Escenario `ST1` −20 % | cobertura 0,78× | la pregunta 4, **otra vez** |

Borrar `B3` entero deja la pregunta 3 en `caution` y **el badge sigue en Riesgo**.
Borrar además `FZ` deja la pregunta 4 roja por el stress. **No existe ninguna
versión de "aflojar el bloque de dividendo" que cambie el badge de MCD**, y eso es
justo lo que hace segura cualquier decisión posterior: nada se puede justificar
diciendo «es que a McDonald's le sale mal».

El hecho de fondo está bien medido: MCD repartió **5.115 M$ de dividendo + 2.056 M$
de recompra contra 7.186 M$ de caja libre — el 99,79 %**, cerrando con 774 M$ de
caja y patrimonio contable de **−1.791 M$**. Un informe que ahí dijera «sin
señales en contra» estaría mintiendo.

**Donde el informe sí falla es en el RECUENTO**, que es lo que el usuario
experimentó como «demasiado estricto»: la pregunta 3 presenta *cuatro* ámbares que
son *dos hechos*.

### Auditoría B — cobertura de [`Check-metrics.md`](Check-metrics.md)

Pregunta literal: _«dime si todas las métricas las estamos usando en el análisis,
también hay uno de MCD específico al final del documento»_.

Workflow de 13 agentes (4 mapas por bloque + 8 verificadores en dos lentes
adversariales + síntesis), **13/13 vivos**. Antídoto: los dos modos de fallo eran
el **falso ausente** (declarar que falta algo que ya calculamos con otra clave —
el documento está en inglés y el motor en español) y el **falso presente**
(declarar cubierta una métrica cuya fórmula difiere).

El documento propone **57 conceptos únicos** en 73 filas.

| Veredicto | Nº | Dónde se concentra |
| --- | --- | --- |
| Cubierta con la fórmula exacta | 15 | §2 contable, §5 dividendo |
| Cubierta con divergencia de fórmula | 12 | ROIC, S2, S4, S1, T2, múltiplos |
| Parcial | 3 | |
| **Hueco que sí se puede cerrar** | **11** | |
| Imposible con esta fuente | 15 | §3 QSR entero, Beta/drawdown |
| No es una métrica | 1 | MyMcDonald's Rewards |

**El motor ya responde a 30 de 57, y otras 11 están al alcance.** Donde cubrimos,
va por delante del cuaderno: donde el documento pide 4 métricas de dividendo, el
motor calcula 15.

---

## 2. La regla de orden de este plan

Las dos auditorías juntas dictan la secuencia, y no es la que uno elegiría por
entusiasmo:

1. **Lo que está MAL** — un número que hoy es falso y nadie detecta.
2. **Lo que se explica MAL** — el color es correcto y la razón no llega.
3. **Lo que FALTA** — métricas nuevas, que es lo único divertido y va lo último.

Dentro de cada bloque, lo que **no exige decisión de producto** va antes que lo
que sí.

---

## BLOQUE 1 — Lo que está mal

### E1. La amortización parcial que infla el apalancamiento — BUG VIVO

**Prioridad máxima. Es el hallazgo más caro de las dos auditorías y no estaba en
ninguna de las dos preguntas.**

`concept_map.py:156-160` pide `DepreciationDepletionAndAmortization` como primer
candidato de `depreciation_amortization`. En McDonald's **ese tag es un valor
PARCIAL**, y el motor lo persiste marcado como dato auditado.

Medido ejecutando el pipeline completo sobre `data/edgar_cache/CIK0000063908.json`
(23.466 hechos → 17 ejercicios):

| Ejercicio | D&A que ingiere el motor | D&A real (estado de flujos) | `S4` motor | `S4` real |
| --- | --- | --- | --- | --- |
| FY2022 | 370 M$ | 1.871 M$ | **3,42** | 2,96 |
| FY2023 | 382 M$ | 1.978 M$ | 2,89 | 2,55 |
| FY2024 | 447 M$ | 2.097 M$ | 3,07 | 2,70 |
| FY2025 | **457 M$** | **2.199 M$** | **3,17** | 2,79 |

El corte de alarma de `S4` es **3,5** (`high_ok=2`, `high_alarm=3.5`). **En FY2022
el motor calculó 3,42 — a ocho centésimas de pintar sobreendeudamiento** en una
empresa que estaba en 2,96.

**Contamina cinco consumidores**: `S4` (deuda neta/EBITDA), `R2` (margen EBITDA),
`Q2` (conversión FCF/EBITDA), el múltiplo `V5` (EV/EBITDA) y `fcf_maintenance`
(inflada ~20 % cada año, entre 1.500 y 1.750 M$).

**El testigo que lo prueba está en los propios datos y es gratis.** MCD publica
también `Depreciation` a secas: 1.600 M$ en 2025. **Una amortización sola no puede
ser MENOR que la depreciación sola**, y 457 < 1.600 se incumple en los ocho
ejercicios.

| Tag | FY2025 |
| --- | --- |
| `DepreciationDepletionAndAmortization` (1.º candidato, el que gana) | 457 M$ |
| `DepreciationAndAmortization` (3.º candidato) | **2.199 M$** |
| `Depreciation` (no mapeado — el testigo) | 1.600 M$ |

**Cómo se arregla**: un cuadre en `fundamentals/validation.py` que compare los tres
tags y, si el elegido es menor que `Depreciation` sola, tome el mayor o marque la
partida como no fiable. **No es reordenar candidatos**: en las otras cuatro
empresas del caché (JNJ, Realty Income, Nike, PepsiCo) el primer candidato **sí**
es el total correcto. Lo que falta es la comprobación que distingue un total de un
parcial.

**Familia de lecciones**: es exactamente [PHASE-44.12] («un emisor puede cambiar la
ESCALA de presentación sin que el fichero lo diga, y ningún cuadre contable lo
detecta») y el comentario que `concept_map` **ya tiene escrito** para
`pretax_income`: _«un valor PARCIAL presentado como total, que es peor que un
hueco»_. La doctrina estaba; faltaba aplicarla aquí.

**Coste**: bajo de código, pero **cambia números ya persistidos** → bump de motor
y, si se quiere el histórico coherente, reejecutar los `AnalysisRun` afectados.
Los umbrales sembrados no se tocan.

**Sin resolver, y hay que hacerlo antes de cerrar la entrega:**

- ¿A cuántos emisores más afecta? Se contrastaron **5 de las 9** empresas del
  caché. Sé que cuatro no lo están y una sí.
- **No se ha rastreado hasta el informe**: no está comprobado si mueve alguna de
  las cuatro preguntas del veredicto, ni si contamina la tasa de amortización del
  **M-Score**, que también consume esta partida.

**Verificación exigida**: el cuadre se prueba rompiéndolo, y con **las dos
direcciones** — un emisor sano cuyo primer candidato es correcto NO debe
dispararlo (si no, el arreglo rompe a las otras cuatro empresas del caché).

---

### E2. Un saldo de cierre que sólo se etiqueta en un 10-Q se tira

El filtro de ingesta (`annual.py:73`) exige `form_type in ANNUAL_FORMS` y
`fiscal_period == "FY"`, y lo aplica **igual a los FLUJOS que a los SALDOS**. Para
los flujos tiene todo el sentido: un trimestre no es un año. Para un saldo **no**:
un saldo con fecha 31-dic significa lo mismo lo reporte quien lo reporte.

Verificado sobre el caché de MCD:

| Tag | Filas anuales 10-K | Filas en 10-Q | Último anual |
| --- | --- | --- | --- |
| `OperatingLeaseLiabilityNoncurrent` | 8 | 44 | **2022-12-31** |

O sea: para **2023, 2024 y 2025** el arrendamiento operativo a largo plazo sólo
llega por 10-Q y se descarta. La línea de balance «Arrendamientos a largo plazo»
se publica con el financiero solo (1.770 y 2.329 M$ en 2024-2025) cuando el
operativo son ~12.900 y ~14.100 M$ — **silenciosamente incompleta y marcada como
dato auditado**.

**Cómo se arregla**: en `_is_annual`, aceptar los hechos **INSTANTE** cuya fecha
coincida exactamente con un cierre de ejercicio ya identificado, venga del
formulario que venga. La función ya distingue instante de duración, así que la
costura existe. **Los flujos siguen exigiendo 10-K/FY, sin excepción.** Hace falta
un desempate explícito cuando el mismo saldo llegue por dos formularios.

**Coste**: medio y delicado — toca la frontera de ingesta y puede mover saldos ya
persistidos. Verificar contra varias empresas del caché antes de darlo por bueno.

**Nota de método**: dos de los cuatro mapas atribuyeron esto al **orden de los
candidatos** y proponían un arreglo que habría dado exactamente el mismo número.
Lo corrigió una lente que **ejecutó el pipeline** en vez de leer el mapeo.

---

## BLOQUE 2 — Lo que se explica mal

> Recordatorio del veredicto de la auditoría A: **no se toca ni un corte**. Todo
> este bloque es honestidad y recuento, no calibración.

### E3. Persistir `stress_params` en el `AnalysisRun` — sin decisión, no cambia ningún veredicto

Los parámetros de stress son **editables por la API** (`schemas.py:128-138` →
`router.py:56-68` → `service.py:149,200`) y **no se persisten**. El `AnalysisRun`
guarda `engine_version`, `thresholds_version` y `thresholds_used` —todo el aparato
de reproducibilidad— y ni una traza de `stress_params`. Y `_method_changes`
(`presentation/diff.py:213-222`) sólo compara esos dos campos.

Con `revenue_drops=[0.05]` el escenario deja de bajar de 1,0, la pregunta 4 deja
de ser roja y **el badge cambia**, sin que el run guarde ninguna huella de por qué.
Dos runs de la misma empresa sobre los mismos datos pueden traer veredictos
distintos y el comparador los presenta **como cambio de la empresa**.

Es literalmente la familia que el proyecto ya nombró en **[PHASE-44.24.F]**
—«presentar juntos un cambio de la empresa y uno del método es peor que no
comparar»— y `comparable` se declaró **precondición** justo para esto.

**Dos salidas, las dos válidas**: (a) persistir `stress_params` (o su hash) e
incluirlo en la clave de comparabilidad; (b) más barato: **prohibir el override en
el endpoint que PERSISTE** un run y dejarlo sólo para una simulación no guardada.

**Decidir a la vez**: qué se hace con los runs viejos sin el campo. `None` como
«defaults» es razonable (hoy el 100 % de los runs de producción se lanzaron sin
overrides); `None` como «desconocido» dejaría **todo el histórico incomparable de
golpe**.

---

### E4. `FZ` recibe el tratamiento del Z''-REIT cuando el patrimonio es negativo

La advertencia que explica `FZ` **ya está escrita en el motor** —`glossary.py:785`:
_«aquí el apalancamiento pesa tanto que un patrimonio negativo por recompras lo
dispara sin tensión real»_, repetida en `glossary.py:806-808` y
`score_help.py:362-365`— y **no llega nunca al sello que ese mismo número fuerza**:
`_safety_profile` (`synthesis.py:1091-1092`) enciende `avoid_bankruptcy` desde
`fz_red` sin ninguna condición. MCD sale con sello `avoid` y **una única razón**:
«X-Score en rojo (riesgo de quiebra)».

La condición es **máquina-comprobable y el motor ya la tiene calculada**:
`leverage = total_liabilities / total_assets` (`forensic.py:721`) sólo pasa de 1,0
cuando el patrimonio contable es negativo. En MCD vale **1,0301** (61.306/59.515,
patrimonio −1.791) y el término aporta **+5,8499** de los 0,8684 finales.

**Hay precedente EXACTO en el propio fichero**: el `Z''` de una socimi recibe una
bandera ámbar con `model_variant="uncalibrated"` y la frase «Léelo como
orientación, no como veredicto» (`forensic.py:775-790`) **sin tocar la banda**. El
proyecto sabe tratar esta familia, lo hace dos módulos más allá, y aquí deja la
advertencia en prosa junto a un número que fuerza «Evitar».

Aritmética que da la escala del problema: con el ROA de MCD (14,39 %) haría falta
un patrimonio del **16,7 % del activo (~9.960 M$)** sólo para llegar a ÁMBAR, y del
**30,5 % (~18.160 M$)** para el verde — en una empresa con 8.563 M$ de beneficio y
7,74× de cobertura de intereses.

**Cambio**: bandera con `model_variant='uncalibrated'` + su motivo, y que el sello
y el badge **la citen**. NO cambia la banda, NO cambia el color, NO deja pasar a
nadie. Es adición de honestidad pura.

> **DECISIÓN EXPLÍCITA, y NO por inercia**: ¿un modelo declarado no calibrado debe
> seguir forzando `avoid`? El precedente vigente del Z''-REIT dice que **sí** (la
> bandera no toca `avoid_insolvency`). Cambiarlo para `FZ` crearía una asimetría
> que **necesita su propio argumento escrito**.

**Coste**: toca engine (clave de bandera nueva + entrada en `flag_catalog` + los
gates de cobertura de 44.17 y 44.24.A) → bump de motor.

---

### E5. `D2` y `D3` son la misma cifra leída al revés

La pregunta 3 cuenta **cuatro ámbares que son dos hechos**:

- `D3` es el **recíproco EXACTO** de `D2` sobre el mismo par:
  `divide(dividends, cash)` frente a `divide(cash, dividends)`
  (`dividend.py:737-738`). Medido: `D2` = 0,71180 y `D3` = 1,40489 = 1/0,71180.
- `D4` comparte numerador con `D2` y su denominador es `fcf − sbc ≤ fcf`, **con
  cortes IDÉNTICOS** (0,60/0,85 en ambas, `dividend.py:107-116` y `:126-135`).
  Medido: `D4` = 0,72853 (la SBC son 165 M$ sobre 7.186 M$).

Y tiene una **consecuencia estructural que ningún análisis previo había visto**: la
regla «≥2 ámbar» (`synthesis.py:479-480`) existe para exigir **corroboración**, y
en esta pregunta **es matemáticamente inalcanzable**, porque `D2` ámbar implica
`D4` ámbar o peor con los mismos cortes. **La regla nunca puede ejercer su función
aquí.**

El motor ya tiene el mecanismo y lo aplica un módulo más allá:
`SCALE_COMPANIONS = {"FZ": "FZ_P"}` (`forensic.py:191-203`), con un docstring que
describe este fallo exacto.

**Cambio**: declarar `D2` y `D3` como pareja de escala **junto a la fórmula**, para
que sólo una entre en el semáforo y se pinten en una fila.

**No cambia el color de MCD** (`D2` es portante y un portante en ámbar ya impide el
verde solo, `synthesis.py:614-615`), y **nadie se escapa**: el único caso donde la
fusión podría cambiar un color sería `D2` verde con `D3` ámbar, y es imposible
—`D2` ≤ 0,60 implica `D3` ≥ 1,667 > 1,60, o sea `D3` verde—.

**Pero arregla justo lo que el usuario experimentó como «demasiado estricto»: el
recuento de evidencia.**

> Dejar la **rebandeada de `D4` por SPREAD** contra `D2` como decisión SEPARADA. Es
> un cambio mayor y necesita su propio argumento.
>
> Nota que se pliega aquí en vez de inflar la lista: `ST3` es `1 − 1/cobertura`
> (`stress.py:228-237`), o sea `D3` disfrazado, y vive en la pregunta 4 — **el
> mismo cociente entra en las dos mitades del worst-of**. Impacto medido: nulo
> (sólo se consulta `if worst is None`).

---

### E6. Dos divergencias silenciosas entre el DESIGN y el código

`Q5` y `T3` emiten **ROJO** donde
[`DESIGN-v2-investment-module.md`](DESIGN-v2-investment-module.md) escribió
**ÁMBAR**. Las dos se definen con `high_ok == high_alarm` (`dividend.py:194-203` y
`:225-234`) y `band_for` para LOWER_BETTER comprueba `> high_alarm` antes que
`> high_ok` (`types.py:266-272`), así que **el ámbar es inalcanzable**. `Q5` es
señal de la pregunta 1 y un rojo la tiñe ella sola.

**Lo que lo hace incontestable: no tiene NINGÚN efecto sobre MCD** — medidos sobre
las fixtures reales, `Q5` = 0,0137 y `T3` = 8,30 pp, los dos verdes y lejísimos del
corte. Es un hallazgo encontrado por el camino, imposible de confundir con un favor
a McDonald's.

> `T2` tiene la misma forma degenerada (`low_alarm = low_ok = ZERO`) pero ahí es
> **INTENCIONADA** y coincide con el DESIGN. **Ésa no se toca.**

**Dos salidas**: (a) separar los cortes para que exista el ámbar que el diseño
especifica — **afloja**, y hay que decirlo: se escaparía el emisor que sostiene el
EBT con ventas de negocios justo por encima del 20 %; o (b) **corregir el
DOCUMENTO** para que diga «rojo», con su motivo y su test dentro.

**(b) es la conservadora y probablemente la correcta.** Lo que no puede quedarse es
que especificación y código digan cosas distintas sin que nada lo vea.

---

### E7. El motivo de la exención de `B3` en financieras es FALSO

`sector_profiles.py:193` mapea `"B3": _FIN_CASH`, y `FIN_CASH_REASON`
(`flag_rules.py:48-51`) dice _«el esquema de caja libre (CFO − capex) no describe a
una financiera»_. Pero `B3` es `(cash + current_financial_assets) / dividends_paid`
(`dividend.py:787-794`): **no contiene caja libre por ningún lado**.

El texto es user-facing **por decisión explícita**:
`ThresholdSpec.not_applicable_reason` «viaja al run y de ahí a la pantalla»
(`types.py:246-249`), y el `__post_init__` obliga a que exista precisamente para
que un N/A mudo no se confunda con un fallo de cálculo. **Un motivo FALSO es peor
que uno mudo.**

La exención puede seguir siendo correcta —por **otra** razón: el efectivo en un
banco es materia prima, no colchón— pero eso hay que escribirlo.

**Coste**: sólo texto y un test. Nadie queda mejor ni peor clasificado. Trivial y
user-facing.

---

### E8. El rótulo de la racha de dividendo — la entrega más barata de todo el plan

El motor calcula y pinta la racha de años consecutivos sin recorte. Tiene **cuatro
techos**, en orden de dureza:

1. La ventana de ejercicios está capada a **10**, así que la racha máxima
   aritmética es **9** — y con el valor por defecto de 5, **cuatro**.
2. Es una **cota inferior** y el código lo declara.
3. Mide el DPS **DERIVADO** del pago, no el declarado, así que **un hueco de datos
   corta la racha igual que un recorte real**.
4. Aunque se levantara el cap, los hechos XBRL de la SEC arrancan hacia **2009**
   (el caché de MCD da 17 ejercicios, 2009-2025), así que el techo real serían
   unos 15 años.

**Sin el rótulo, un «4 años seguidos sin recortar» junto a una empresa que lleva
cuatro décadas subiéndolo se lee como un ERROR DEL MOTOR en vez de como su
alcance.**

**Cambio**: una frase — que la racha es *un mínimo verificado sobre los N
ejercicios ingeridos*. Trivial, sin bump.

---

## BLOQUE 3 — Lo que falta

> Todo este bloque es **opcional** y va después de los dos anteriores. Ninguna de
> estas entregas arregla nada roto: añaden cobertura.

### E9. Rentabilidad por dividendo (yield) — el hueco que más se nota

Es la **primera cifra que mira cualquiera que compre por dividendo**, y la única
del bloque §5 del documento que falta. El motor calcula **quince** métricas de
dividendo —si el reparto cabe en el beneficio, si cabe en la caja, si lo financia
deuda, si la racha aguanta— y no la que responde a «¿cuánto me renta a este
precio?».

**Cómo**: una métrica `V8` en `engine/valuation.py`: dividendos pagados /
capitalización. Los tres insumos ya existen (la partida de dividendos, el recuento
de acciones y el precio vivo del adapter, que ya construye la capitalización para
los cinco múltiplos actuales).

**Debe vivir FUERA del `AnalysisRun`** como `V1`-`V7` —se mueve con el precio y el
run tiene que reejecutarse dando lo mismo— y **sin banda**, por el mismo invariante
que gobierna los múltiplos.

**Coste**: bajo. Sin ingesta, sin migración.

---

### E10. Retribución total al accionista sobre capitalización (shareholder yield)

Una empresa puede devolver más por recompra que por dividendo, y quien mire sólo el
dividendo la juzga mal. El motor tiene la pieza **contable** —`D5`, dividendo más
recompras sobre la caja libre, que responde a «¿cabe?»— y le falta la pieza de
**mercado**, que responde a «¿cuánto me devuelven por lo que pago?».

**No son la misma métrica**: comparten numerador y difieren en el denominador, que
es justo lo que las define. Además el motor **no neta la emisión de acciones**, que
ya está ingerida (`share_issuance`).

**Cómo**: junto al yield, `(dividendos + recompras − emisión) / capitalización`.
Fuera del run y sin banda. **Misma entrega que E9.**

---

### E11. Deuda neta / patrimonio

`S7` se llama **«Ratio de endeudamiento»** y divide el **PASIVO TOTAL**
—proveedores, provisiones e impuestos diferidos incluidos— entre el patrimonio. La
vara de apalancamiento más usada fuera de los ratios sobre EBITDA es **deuda NETA /
fondos propios**, y **no existe**. En una empresa con mucho circulante operativo
los dos números se separan de largo, y quien lea la etiqueta va a creer que está
viendo lo primero.

**Cómo**: una línea — dividir la derivación `net_debt`, que ya existe, entre el
patrimonio, con la misma guarda de denominador positivo que ya lleva `S7`.

**Coste**: bajo de código, pero **necesita banda propia** (la de `S7` no vale: no
es la misma magnitud) → sembrar un umbral nuevo y bump de motor.

---

### E12. Arrendamientos como deuda — pieza terminada y descableada

Desde ASC 842 / IFRS 16, un arrendamiento operativo es una **obligación de pago
contractual e ineludible**: para un minorista, una aerolínea o una cadena de
restauración puede ser del orden de la deuda financiera entera. Excluirlo hace que
las tres métricas de apalancamiento (`S4`, `S5`, `L4`) **subestimen la carga real
justo en los sectores donde más pesa**.

**El motor ya tiene la derivación construida** —`total_debt_incl_leases`
(`derivations.py:57`)— **y no la llama nadie**: único uso en todo el backend, un
test. Es la señal de [PHASE-43] sobre features construidas y perdidas.

**Cómo**: una variante `S4-leases` **junto a** `S4`, **no sustituyéndola** — los
cortes de banda se calibraron sobre deuda financiera, y sustituir invalidaría la
calibración sectorial de [PHASE-44.21](../phases/phase-44.21-sector-calibration.md).

**Depende de E2**: sin arreglar el filtro de formulario, el arrendamiento operativo
de los últimos tres ejercicios de MCD ni siquiera está ingerido.

**Coste**: medio. Sin ingesta nueva. Bump de motor + decidir bandas para la
variante.

---

### E13. El DPS declarado, por un canal de ingesta aparte

El dividendo por acción **declarado** es un hecho anual estructurado, limpio y rico
en historia —verificado en el caché de MCD: **113 filas anuales 10-K**, 7,17 $ en
2025 con unidad `USD/shares`— y el motor **no lo lee nunca**: lo reconstruye
dividiendo la caja pagada entre las acciones medias.

De ahí salen tres consecuencias que el usuario ve:

1. `T2` (crecimiento del dividendo) mide otra cosa que la que anuncia.
2. La racha de años sin recortar **se rompe por un hueco de datos igual que por un
   recorte real** (ver E8).
3. No hay forma de dar una rentabilidad sobre dividendo **declarado**.

**El bloqueo no es el mapa de conceptos**, sino el filtro que descarta toda unidad
«por acción» — y ese filtro **existe por una razón buena y documentada**: que un
beneficio por acción no se cuele como si fuera un importe (es la lección
[PHASE-44.12] sobre el testigo de escala).

**Cómo**: un canal de ingesta **APARTE** para magnitudes por acción —no relajar el
filtro, que protege de un fallo peor— con la partida marcada como *per-share* para
que ninguna derivación la sume con importes. Tag:
`us-gaap:CommonStockDividendsPerShareDeclared`.

**Coste**: medio-alto. Es **la primera partida no monetaria del canónico**, así que
abre una categoría nueva en el modelo de datos. Migración probable si se persiste;
bump de motor seguro.

---

### E14. Cobertura de cargos fijos — con un aviso que la puede tumbar

Para una empresa que **alquila** su red en vez de comprarla, la renta es tan
ineludible como un cupón, y una cobertura de intereses que la ignora exagera el
margen de maniobra. Es el complemento natural de E12: uno mira el **stock**, éste
el **flujo**.

El documento se equivoca al decir que hace falta extraer las obligaciones de
arrendamiento —el **pasivo** ya se ingiere por dos vías—; lo que falta es el
**GASTO** anual, que es una línea de la cuenta de resultados.

**Cómo**: partida canónica `lease_expense` con `us-gaap:OperatingLeaseCost` como
candidato principal (va *detail-tagged* en Inline XBRL desde 2019), más
`ShortTermLeaseCost` y `VariableLeaseCost` para el coste total, y
`OperatingLeasesRentExpenseNet` / `LeaseAndRentalExpense` para los ejercicios
anteriores a la norma. Después la métrica:
`(EBIT limpio + renta) / (intereses + renta)`.

> **AVISO VERIFICADO POR MÍ, y es el que decide si esta entrega vale la pena:
> McDonald's NO publica `OperatingLeaseCost`** (0 filas en el caché). Así que ahí
> saldría *no computable*. **Antes de planificar esto hay que validar la cobertura
> del tag contra varias empresas**, o se construye una fila que casi nunca da
> número.

**Coste**: medio. Partida nueva, métrica nueva, banda nueva, bump de motor.

---

### E15. Ingreso por arrendamiento

Para una socimi o cualquier empresa cuyo negocio es alquilar, la renta cobrada
sobre el valor del inmueble es la métrica central, y el motor **ya tiene el
denominador ingerido** (`ppe_net`).

**Cómo**: partida `lease_income` con candidatos `LeaseIncome` y
`OperatingLeasesIncomeStatementLeaseRevenue`, más una métrica
`ingreso por arrendamiento / ppe_net`. Escribir **en su propia definición** que el
denominador es coste contable neto y **no** valor de mercado, o el número se leerá
como una rentabilidad económica que no es.

> **VERIFICADO POR MÍ: MCD no publica `LeaseIncome`** (0 filas). Realty Income sí
> (21 filas anuales, 5.437 M$ en 2025). O sea: **es implementable de verdad, pero
> no para cualquiera** — y para McDonald's saldría *no computable con motivo*, que
> es lo correcto, no un fallo.

**Coste**: bajo-medio. Sin banda (no hay corte universal para una rentabilidad
inmobiliaria sin comparables). Bump de motor.

---

### E16. Recuento de unidades — la primera partida no monetaria y sectorial

Para cualquier negocio que crece abriendo puntos de venta, el número de unidades y
su variación interanual **separan el crecimiento por volumen del crecimiento por
precio**.

Aquí el documento **se equivoca en la dirección buena**: sitúa el dato en una tabla
en prosa del Item 1 cuando en realidad es un **hecho XBRL estructurado que YA llega
al pipeline y se tira en silencio** porque no hay partida que lo recoja.

> **VERIFICADO POR MÍ**: `us-gaap:NumberOfRestaurants`, **45 filas anuales 10-K**,
> unidad `Restaurant`, último valor **45.356 al 31-dic-2025** (32.478 en 2009).

**Cómo**: partida canónica nueva + entrada en el mapa de conceptos (candidatos
`NumberOfRestaurants` y el genérico `NumberOfStores`), y una entrada en
`HORIZONTAL_ITEMS` de la evolutiva, que **ya calcula variación interanual, índice
base 100 y CAGR sin escribir fórmula**.

Va como **SERIE y no como métrica con banda**: un recuento de locales no admite un
corte universal.

**Dos cautelas medidas**: el concepto convive con tres unidades distintas que
colapsan bajo la misma clave, y sería **la primera partida sectorial del catálogo**
(saldría vacía para la inmensa mayoría de empresas).

**Coste**: medio — abre dos categorías que el módulo hoy no tiene (partidas no
monetarias y partidas sectoriales). Se solapa con E13, que abre la primera.

---

### E17. Publicar `divestitures` como serie — la entrega barata del refranquiciado

El **porcentaje** de parque franquiciado exige el desglose propios-vs-franquiciados,
que es un hecho **DIMENSIONADO** y la fuente no sirve dimensiones (medido: de los
23.466 hechos del caché **no hay ni una colisión anual**, lo que lo confirma).

Pero el **efecto de caja** del refranquiciado **sí se ingiere**: `divestitures` está
mapeada con el comentario del emisor puesto a mano en el código, y **no la consume
nadie** — ni series de la evolutiva ni métrica catalogada.

**Cómo**: añadirla a `HORIZONTAL_ITEMS`. Enseñaría la **intensidad** del
refranquiciado año a año, aunque nunca su porcentaje.

**Coste**: trivial. Una línea.

---

## 3. Decisiones de producto — D1 y D2 CERRADAS, D3 propuesta

Ninguna de estas se toma por inercia.

**D1 quedó resuelta el 30-ago-2026** y su decisión está abajo, con la corrección
de dónde había que tocar. Siguen abiertas **D2** y **D3**.

### D1. El gate de stress — ✅ RESUELTA por el usuario (30-ago-2026)

**Decisión literal**: _«Los stress están bien pero hay que modificar que nunca
condicionen un evitar, eso es decisión del inversor. Que un stress de un 30 %
marque un "evitar" creo que no es viable, pues casi ninguna empresa sería
viable»_.

**Es una cuarta opción, mejor que las tres que se habían planteado**: no se
cambia QUÉ escenario dispara, se cambia QUÉ PUEDE HACER el disparo. Los seis
escenarios se quedan como están —incluido el −30 %, que sigue calculándose y
pintándose— y lo que se retira es su capacidad de dictar un veredicto.

#### El principio que queda escrito

> **Una hipótesis informa; no dictamina.**
>
> Todas las demás señales de la pregunta 4 miden algo que **OCURRIÓ** y está
> reportado en un 10-K. El escenario de stress mide algo que el motor **se
> inventa**, con parámetros que además el usuario puede editar por la API (ver
> E3, donde ni siquiera se persisten). Un número hipotético y un número
> auditado no pueden tener el mismo poder sobre un veredicto.

Esto refuerza E3 en vez de sustituirlo: un cálculo cuyos parámetros no se
registran es, con más razón, un cálculo que no debe dictaminar.

#### CORRECCIÓN IMPORTANTE sobre dónde hay que tocar

**La señal de stress NO alimenta hoy el sello «Evitar».** Verificado leyendo
`SAFETY_MATRIX` (`synthesis.py:897-968`): las cuatro condiciones de `avoid` son
`avoid_manipulation` (m_score + accruals), `avoid_insolvency` (z_score),
`avoid_bankruptcy` (`FZ`) y `avoid_dividend_funding` (`B4`). **El stress no está
entre ellas** — es justo lo que [PHASE-44.25] anotó como «decisiva ≠ roja: el
stress tiñe su pregunta sin estar en la matriz». El «Evitar» de MCD sale
íntegramente de `FZ`.

Lo que el stress SÍ condiciona hoy:

1. La pregunta 4 «¿aguanta un golpe?» → **roja** (`_stress_signal`,
   `synthesis.py:838-843`: devuelve `stressed` con el PRIMER escenario cuya
   cobertura baje de 1,0).
2. Y de ahí, por el `worst-of` de `_dividend_verdict` (`synthesis.py:1177-1181`),
   el badge **«El dividendo está en riesgo»**.

Así que **arreglar el sello no habría arreglado nada**: hay que tocar la
pregunta 4. El razonamiento del usuario se aplica igual —una hipótesis
produciendo un veredicto— pero el sitio es otro. Anotarlo importa porque
implementar la instrucción al pie de la letra («que no condicione el evitar»)
habría sido un no-op con forma de arreglo.

---

### E18. El escenario de stress deja de puntuar

**Cambio**: `_stress_signal` pasa a ser **display-only** dentro de la
agregación de la pregunta 4 — exactamente el tratamiento que ya tienen `D1` y
`D8`. Conserva su banda, su color, su fila en la tabla y su frase en la
narrativa; lo que pierde es entrar en el recuento del semáforo.

**Por qué display-only y no «tope en ámbar»**, que era la alternativa obvia: el
semáforo tiene una regla «≥2 ámbar → rojo» (`synthesis.py:479-480`), así que un
stress capado en ámbar **seguiría pudiendo empujar la pregunta a roja** en
combinación con otra señal. Sería cumplir la instrucción a medias. Display-only
es lo único que garantiza que una hipótesis no dictamine.

**Qué NO se toca**:

- Los seis escenarios y sus parámetros por defecto, incluido el −30 %.
- La card de escenarios, el dumbbell y las frases del servidor
  (`stress_margin_sentence`).
- `ST3` (breakeven) y su margen.
- La pregunta 4, que sigue funcionando con sus señales **medidas**: sus
  portantes son `z_score` y `S2` (`LOAD_BEARING["resilience"]`), los dos hechos
  reportados sobre la capacidad real del balance de aguantar.

**Efecto medido sobre MCD**: **ninguno en el badge.** La pregunta 4 sigue roja
por `FZ`, que es una señal medida y sí puntúa. Es la consecuencia directa de que
el rojo esté sobredeterminado (ver §1), y es una buena noticia para la decisión:
significa que el cambio **no se está haciendo para favorecer a McDonald's**, que
era el riesgo que el antídoto de la auditoría A vigilaba.

**Dónde SÍ cambia algo**: en la empresa cuyo único rojo de la pregunta 4 era el
escenario. Ésa pasa de «Riesgo» a lo que digan sus señales medidas — y el
escenario sigue ahí, pintado, para que el inversor decida. Que es exactamente lo
que pide la decisión.

**Coste**: toca engine → **bump de motor**, y los runs guardados dejan de ser
comparables con los nuevos. No toca ninguna banda ni ningún umbral sembrado.

**Verificación exigida**:

- Un test que afirme la decisión **con su motivo dentro** ([PHASE-44.21]: «una
  decisión razonada sin test se revierte sola»). El motivo va en el docstring:
  *una hipótesis informa, no dictamina*.
- El caso que lo prueba de verdad: una empresa cuya **única** señal roja de la
  pregunta 4 sea el escenario. Con MCD el test pasaría por la razón equivocada
  —`FZ` la mantiene roja igual— que es el fallo de [PHASE-47.A] («un test que
  pasa por un camino distinto del que dice medir»). **Hace falta un caso
  sintético construido a propósito.**
- Y el gemelo: que la fila del escenario **sigue apareciendo** con su banda. Si
  desaparece de la pantalla, no es display-only, es borrado.

#### Las tres opciones que se plantearon, y que la decisión descarta

`_stress_signal` (`synthesis.py:838-843`) recorre **TODOS** los escenarios y
devuelve rojo con el **PRIMERO** cuya cobertura baje de 1,0, y `revenue_drops`
incluye **−30 %** por defecto (`stress.py:42`). Su propio docstring dice «si algún
shock **RAZONABLE** deja de cubrir el dividendo» (`synthesis.py:812-816`).

Medido en MCD: −10 % → 1,09× (ámbar) · −20 % → **0,78× (rojo)** · −30 % → 0,47×.

El argumento es **aritmético y no mira a MCD**: con
`FCF_after = FCF − margen_contribución × caída × ventas × (1−ETR)`, superar el
escenario −30 % exige una caja libre que supere al dividendo en ~18 puntos de
ventas cuando el margen de contribución ronda 0,75. **El listón efectivo no es
«¿aguanta un golpe razonable?» sino «¿cubre el dividendo tras un colapso de ventas
del 30 %?»**, que casi ninguna empresa intensiva en capital pasa.

Dato adicional verificado por el crítico: el margen de contribución que multiplica
el shock se estima como **mediana de 5 observaciones útiles**, y la mediana de MCD
(0,7551) **ES la observación del rebote de 2021** — un episodio de pandemia
proyectado como respuesta estructural a una pérdida permanente de ventas. Nada en
la salida dice de cuántos puntos sale ni cuáles.

| Opción | Coste declarado |
| --- | --- |
| Dejarlo como está (era mi recomendación) | La señal sigue viva en cíclicas —energía, materiales, minería, ocio, automoción—, que es donde el propio motor escribe que el shock ES el punto (`sector_profiles.py:294-297`). Contra: informa poco fuera de ellas. |
| Sólo el −10 % puede teñir | **AFLOJA.** Se escaparía la cíclica con alto apalancamiento operativo que pasa el −10 % y revienta en el −30 %. Bump de motor + runs viejos incomparables. |
| El semáforo sale de `ST3` (breakeven) | Continuo y sin parámetros editables. Pero `ST3` es `D3` disfrazado: el mismo cociente entraría en las dos mitades del worst-of. |

**Si se toca, el corte tiene que ser sector-consciente y no global.** Y va
acompañado de un test que lleve la razón dentro ([PHASE-44.21]).

**Ninguna de las tres se toma.** La decisión del usuario no está en esta
tabla: las tres movían el UMBRAL del disparo, y él retiró el disparo.

---

### D2. `B3` — ✅ RESUELTA por el usuario (30-ago-2026): **(a) display-only**

**Decisión**: `B3` se sigue calculando y enseñando con su número y su banda, y
**deja de puntuar** en el semáforo de la pregunta 3.

#### El argumento que la sostiene, y no menciona a McDonald's

**El numerador está estructuralmente ciego.** `B3` es
`(cash + current_financial_assets) / dividends_paid` (`dividend.py:787-794`), y
las **líneas de crédito comprometidas y los pagarés no existen en el modelo
canónico** (`grep 'credit|revolv|undrawn|committed' fundamentals/canonical.py`
no devuelve nada). Así que una empresa con un crédito de 5.000 M$ firmado y sin
disponer **puntúa exactamente igual que una que no tiene nada**.

Un rojo de `B3` no demuestra «no tiene liquidez». Demuestra «tiene poca caja en
el balance», que es otra afirmación — y la diferencia entre las dos es
justamente lo que decide si el dividendo está en riesgo.

> **Una métrica que no puede distinguir «sin liquidez» de «con la liquidez en un
> crédito sin disponer» no puede dictar un veredicto ella sola.** Enseñarla, sí:
> el número es real y el inversor debe verlo.

Dos argumentos de refuerzo, los dos independientes del emisor:

1. **Su verde se compra empeorando otras dos métricas del propio motor.**
   Aparcar el efectivo que exige el corte sube el activo total, y `R6` (ROA) y
   `R5` (ROE) bajan. El motor tiene una métrica cuyo verde **exige** deteriorar
   otras dos, y esa tensión no está declarada en ningún sitio. (Corregido
   respecto de la cartografía inicial: **NO** empeora `R9`/`R9b`, porque
   `invested_capital = equity + total_debt − cash` resta la caja,
   `derivations.py:222-228`.)
2. **Su propia ficha la describe con las palabras de la OTRA pregunta** — «el
   margen para AGUANTAR UN MAL EJERCICIO» (`glossary.py:1026-1031`), que es
   literalmente `stress.py:3`.

#### El coste, aceptado explícitamente

Pierde señal la población para la que `B3` sí sirve:

- **La mid-cap sin acceso a papel comercial**, cuya caja contable ES toda su
  liquidez — para ella, `B3` rojo sí significa lo que dice.
- **La cíclica en el pico del ciclo con el dividendo recién subido**, que es el
  caso canónico de recorte a dos años vista.

Se acepta porque en ambos casos la señal **sigue en pantalla con su color**: lo
que se retira es que decida sola, no que se vea.

#### La salvaguarda que hace segura la decisión

**Arreglar `B3` NO cambia el badge de MCD.** La pregunta 3 pasa de `stressed` a
`caution` y el `worst-of` de `_dividend_verdict` la ignora, porque la pregunta 4
sigue roja por `FZ`. O sea que **la decisión no puede estar motivada por
McDonald's** — que era exactamente el riesgo que vigilaba el antídoto de la
auditoría A.

#### Serie medida (verificada ejecutando el pipeline)

| FY | Caja | Financieras corrientes | Dividendo | `B3` |
| --- | --- | --- | --- | --- |
| 2018 | 866 M$ | **0** | 3.256 M$ | 0,2660 |
| 2019 | 898 M$ | **0** | 3.582 M$ | 0,2508 |
| 2020 | 3.449 M$ | **0** | 3.753 M$ | 0,9190 |
| 2021 | 4.709 M$ | **0** | 3.919 M$ | 1,2018 |
| 2022 | 2.584 M$ | **0** | 4.168 M$ | 0,6199 |
| 2023 | 4.579 M$ | **0** | 4.533 M$ | 1,0101 |
| 2024 | 1.085 M$ | **0** | 4.870 M$ | 0,2228 |
| 2025 | 774 M$ | **0** | 5.115 M$ | **0,1513** |

Roja en seis de ocho: **es casi una constante del emisor**, lo que es evidencia
de que mide la política de tesorería y no la seguridad del dividendo. (Nota:
`current_financial_assets` vale **0 los ocho años** — MCD no mantiene cartera de
corto plazo, así que el numerador es caja pura.)

#### Lo que NO se hace, y queda cerrado

- **No se baja el corte.** Sigue en 1/2 años para quien lo mire.
- **No se calibra por sector**: no hay ninguna fuente publicada para un corte
  sectorial de «años de caja», e inventar doce es inventar doce.
- **No se borra la métrica** ni su ficha ni su banda.

#### Deuda que se paga en la misma entrega

Escribir en la `note` de `B3` que **el numerador excluye por construcción las
líneas comprometidas y los pagarés**. Sin esa frase, un lector que vea el número
en verde creerá que ha comprobado algo que nadie ha comprobado.

---

### D3. Los runs viejos cuando E3 entre en la clave de comparabilidad

**Propuesta técnica registrada. Sin objeción del usuario; se implementa así
salvo indicación contraria** — se anota como propuesta y no como decisión suya
porque no se le ha planteado por separado.

`stress_params` ausente en un run guardado se interpreta como **«se usaron los
valores por defecto»**, no como «desconocido».

**Por qué**: hoy el **100 %** de los runs de producción se lanzaron sin
overrides —el override existe en el schema y ningún camino de la UI lo usa—, así
que «defaults» es la lectura verdadera y no una conveniencia. La alternativa
(«desconocido») dejaría **todo el histórico incomparable de golpe**, que es un
coste real a cambio de proteger de un caso que no ha ocurrido nunca.

**Condición para que esto sea honesto**: hay que **comprobarlo antes de
implementarlo**, no asumirlo. Una consulta que cuente cuántos `AnalysisRun`
existen y por qué endpoint entraron. Si aparece uno con overrides, la propuesta
decae y se pasa a «desconocido».

---

#### El análisis completo que llevó a esta decisión

`B3` («años de dividendo en caja», verde ≥2 años, rojo <1) es **el corte peor
respaldado del bloque**, y esto es lo que lo dice:

| Procedencia de los 14 cortes del bloque de dividendo | Cuántos |
| --- | --- |
| Del cuaderno del usuario | **0** |
| De literatura citada en el repo | **0** |
| Con razón editorial escrita | **1** (`D2`, y sólo para sus deltas sectoriales) |
| Sólo de la tabla de `DESIGN-v2` «pendiente de veto por número» | **14** |
| Calibrados para el sector de MCD (`CONSUMER_DISCRETIONARY`) | **0** |
| Con un test que afirme su razón | **0** |

Contraste dentro del mismo motor: la capa forense cita autores en su docstring
(Beneish, Altman 1995, Piotroski, Sloan, Zmijewski, Montier) y los cortes de `FZ`
**se derivan aritméticamente** de dos probabilidades declaradas. El bloque de
dividendo no cita nada.

El argumento independiente de MCD: exigir dos años de dividendo en caja **ociosa**
premia acumular tesorería y **deprime `R5` y `R6`** del propio motor — hay una
métrica cuyo verde se compra empeorando otras dos, y **esa tensión no está
declarada en ningún sitio**. Su propia ficha además la describe con las palabras de
la OTRA pregunta («el margen para AGUANTAR UN MAL EJERCICIO», `glossary.py:1026-1031`),
que es literalmente `stress.py:3`. Y en serie, `B3` de MCD ha valido
0,27 · 0,25 · 0,92 · 1,20 · 0,62 · 1,01 · 0,22 · 0,15 en ocho años, roja en seis:
**es casi una constante del emisor**, o sea que mide la política de tesorería y no
la seguridad del dividendo.

| Opción | Coste declarado |
| --- | --- |
| **Display-only, fuera del agregado** (como ya están `D1` y `D8`) | Pierde señal la mid-cap sin papel comercial —su caja contable ES toda su liquidez— y la cíclica en el pico con el dividendo recién subido, **el caso canónico de recorte a dos años vista**. |
| Calibrarla por sector | No hay ninguna fuente publicada para un corte sectorial de años de caja: **inventar doce es inventar doce**. |
| No tocarla | Sólo documentar que el numerador **excluye por construcción** las líneas de crédito comprometidas y los pagarés (no existen en el canónico) y la tensión con `R5`/`R6`. Es la opción (C): incómoda pero defendible. |

**La reserva que gobierna las tres**: arreglar `B3` entero **NO cambia el badge de
MCD** (la pregunta 3 pasaría de `stressed` a `caution` y el worst-of la ignora), así
que **no puede justificarse con este caso**. Si no hay un argumento que se sostenga
sin mencionar a McDonald's, no se hace.

---

## 4. NO HACER — y queda escrito para que nadie lo reabra

### De la auditoría A (calibración)

Los cinco atajos cómodos, y **ninguno cambiaría el badge de MCD de todos modos**:

| Atajo | Por qué no |
| --- | --- |
| Bajar el corte de `B3` | `B3` de MCD es **0,1513**: para dejar de morder, `low_alarm` tendría que bajar de 0,15, o sea **dejar de existir**. Cualquier número que ayude a MCD mata la métrica. |
| Delta de `D2` para `CONSUMER_DISCRETIONARY` | MCD reparte el 71,18 % de su caja libre contra un corte del 60 %. **Es un hecho y el ámbar es su lectura correcta.** Los sectores donde el payout alto es estructural YA tienen su delta con la razón escrita (UTILITIES 0,75/0,95; CONSUMER_STAPLES 0,70/0,90). `CONSUMER_DISCRETIONARY` absorbe textil, mobiliario, edición, mayorista y ocio: mover su vara para que encaje un franquiciador **la mueve también para un minorista cíclico**. Es la definición de tunear. |
| «≥1 rojo» → «≥2 rojos», o una lista de «métricas núcleo» | La divergencia con el DESIGN (:483-486) **es real y merece quedar escrita**, pero el remedio es peligroso: `B2` (`interest_priority`) es una bandera ROJA y **no** es portante, así que un núcleo mal construido dejaría escapar exactamente a la empresa que el bloque existe para cazar. |
| Invertir «el verde se gana» (que una bandera limpia sume verde) | `counted=False` para una bandera limpia es **deliberado y razonado** (`_audit`, `synthesis.py:590-596`). Y la parte defendible **ya está implementada**: `clear_count` se publica y la narrativa lo imprime; en MCD la pregunta 3 sale con `clear_count=3`. |
| Mover el denominador del bloque a `fcf_maintenance` | Es **la forma exacta que tendría el atajo**: bajaría el payout de cualquier empresa con capex de crecimiento sin haber demostrado nada. Y no procede: `fcf_maintenance` está declarada ESTIMATED (proxy `min(capex, D&A)`) y se expone a propósito **sin banda**. Bandear un payout sobre un denominador estimado importaría el error de la estimación al veredicto. |

### De la auditoría B (cobertura)

| Propuesta del documento | Por qué no |
| --- | --- |
| **Raspar el MD&A** para SSSG, guest counts, ticket, mix digital, penetración del reparto, ventas del sistema y % de refranquiciado (§3 entera, **8 métricas**) | Pozo sin fondo de mantenimiento, y este repo **ya tiene la lección con nombre**: **[PHASE-46]** — «un catálogo de redacciones ajenas no es una regla: es una lista de las veces que has mirado», donde el banco cambió dos frases y la app se inventó 700 € de ingreso que nadie cobró. Aquí es **peor**: el emisor cambia la redacción, la definición **y la forma del dato** (el mix digital se publica unos años como porcentaje y otros como importe absoluto), así que **ni una expresión regular fija serviría**. Y choca con tres cosas del diseño: la ingesta descarga JSON de hechos, el adapter devuelve nulo para todo lo que no sea un importe, y el motor es puro. Modo de fallo: **silencioso y con forma de dato**. |
| Añadir **8-K y DEF 14A** como fuentes (§5.2), o el Item 5 / Item 1 como texto | Documentos **narrativos**, no hechos estructurados. Y para lo único que aportarían —el DPS declarado— **existe el camino estructurado** (E13). Ampliar la fuente a formularios narrativos por un dato ya tagueado es pagar el coste alto por la puerta equivocada. |
| El tag `//DividendPolicy` (§5.3) | **No existe** en la taxonomía us-gaap. Es una descripción en prosa. |
| La fila **MyMcDonald's Rewards** | **No es una métrica**: es el nombre de un programa, sin fórmula ni magnitud. Lo más cercano con forma de dato sería el pasivo por puntos no consumidos, que no es lo que la fila pide. Una app de análisis forense no debería fingir que lo mide. |
| **Beta, downside capture, drawdown** | **Cambian de eje**: las 65 métricas describen el riesgo del **NEGOCIO** y éstas la volatilidad del **PRECIO**. Exigen series históricas alineadas del valor y de un índice, y el proveedor de precios es de **cotización puntual por contrato**. Aunque se añadiera, no podría vivir en el motor (puro, sin red ni reloj). Mucha maquinaria para tres números que cualquier pantalla de mercado da gratis. |
| **Franchise Mix** con `FranchiseRevenue` / `SalesRevenueGoodsNet` (§3.2) | **Trampa que parece un acierto**: las dos etiquetas suman exactamente el ingreso total… **hasta 2017**. En 2018 descuadra por el cambio de norma de reconocimiento de ingresos y de 2019 en adelante el ingreso total viaja solo. Sobre una ventana moderna de cinco ejercicios **saldría no computable en los cinco**. |
| Bandas para el «Digital Mix >30 %» y la «tasa de royalty ~4-5 %» que el propio documento propone | Un corte propio de **una empresa concreta** no cabe en un catálogo genérico, y ya existe un gate que **prohíbe umbrales escritos a mano** en la prosa de las definiciones (44.24.A). Además la tasa de royalty **no es una medición**: es un dato de contrato que el propio texto se responde a sí mismo. |
| Forzar el tratamiento de socimi por el «REIT-híbrido» (línea 171) | El motor tiene la maquinaria (FFO, `D6`) y **la enciende sólo con evidencia documental**. Eso es correcto. El FFO existe porque en una socimi la amortización del inmueble no refleja deterioro económico; **en una empresa que además opera cocinas y equipos, sí lo refleja**, así que sumarla inflaría la base repartible y haría que el dividendo pareciera **más seguro de lo que es**. El «REIT-híbrido» es una **analogía de tesis de inversión, no una premisa contable**. |
| Meter cualquier múltiplo —incluidos el yield de E9 y E10— **dentro** del `AnalysisRun` | Un múltiplo se mueve con el precio y **el run tiene que poder reejecutarse dando exactamente lo mismo**. Los múltiplos se calculan al servir y la pantalla los separa del veredicto a propósito: «¿es seguro?» y «¿está cara?» son preguntas distintas. |

---

## 5. Cobertura de estas auditorías — qué NO está verificado

Escrito aparte a propósito: **un agregado que no distingue «no hay nada» de «no se
miró» es peor que no dar el dato** ([PHASE-44.14]).

### Verificado por mí, ejecutando

- Las 65 métricas del catálogo y sus bandas (`S4`: `high_ok=2`, `high_alarm=3.5`).
- `ANNUAL_FORMS = frozenset({"10-K"})` y el filtro `fiscal_period == "FY"`.
- El orden de candidatos de `depreciation_amortization` en `concept_map.py`.
- **El defecto E1 entero**: los tres tags de D&A con sus valores, y el efecto sobre
  `S4` en cuatro ejercicios, ejecutando el pipeline real (23.466 hechos → 17
  ejercicios).
- **Los cuatro datos que sostienen entregas del bloque 3**: `NumberOfRestaurants`
  (45 filas anuales, 45.356 en 2025), `CommonStockDividendsPerShareDeclared` (113
  filas, 7,17 $), `OperatingLeaseLiabilityNoncurrent` (último anual **2022**), y los
  dos **negativos** que limitan E14 y E15 — MCD **no publica** `OperatingLeaseCost`
  ni `LeaseIncome`.

### Reportado por los agentes contra fixtures reales, NO re-verificado por mí

`B3` = 0,1513 · `FZ` = 0,8684 (P = 80,7 %) · `ST1` −20 % = 0,78× · `D2`/`D3`/`D4` ·
`Q5` = 0,0137 · `T3` = 8,30 pp · `leverage` = 1,0301 · las cifras de reparto de
FY2025 · las 21 filas de `LeaseIncome` de Realty Income · el desglose de franquicia
muriendo en 2018.

### Lo que NO se miró en absoluto

1. **No se ejecutó la suite de tests** en ninguna de las dos auditorías (regla del
   proyecto sobre pytest concurrente, y estaba prohibido en los encargos). Nada de
   esto está respaldado por la suite.
2. **No se tocó la red.** Todo sale del caché local: **9 empresas**, el de MCD con
   fecha de **julio**. Un cambio posterior en sus filings no se ve.
3. **E1 sólo se contrastó contra 5 de las 9 empresas.** No se sabe cuántos emisores
   más están afectados.
4. **E1 no se ha rastreado hasta el informe**: sin comprobar si mueve alguna de las
   cuatro preguntas del veredicto ni si contamina el **M-Score**.
5. **No se auditó el frontend** en la auditoría B. Qué pinta cada pestaña y con qué
   rótulo se tomó de las citas de los mapas, sin abrir un componente.
6. **El bloque inmobiliario de la auditoría B se auditó con un rango de líneas
   equivocado**: los cuatro tags de dividendo llegaron por la vía de las omisiones
   de un verificador, no por un mapa propio. Su cobertura es **más fina que la del
   resto**.
7. **Dos afirmaciones del documento sobre MCD quedan sin resolver, ni a favor ni en
   contra**: que su ciclo de conversión de caja es de −40 a −60 días (el motor no
   puede calcularlo sin coste de ventas anual) y que su cartera inmobiliaria vale
   ~40.000 M$ (lo ingerido es coste **neto**: 28.241 M$, con un bruto de 49.290 que
   no está mapeado).
8. **Ningún coste de este plan es una estimación de esfuerzo.** Son tamaños
   relativos y señalan si hay bump de motor o migración. Nada se ha prototipado.

---

## 6. Orden de ejecución propuesto

| # | Entrega | Bloqueada por | Decisión previa | Bump |
| --- | --- | --- | --- | --- |
| 0 | Prueba manual 44.24/44.25/44.26 + relanzar MCD | — | — | no |
| 1 | **E1** amortización parcial | 0 | — | **sí** |
| 2 | **E7** motivo falso de `B3` en financieras | 0 | — | no |
| 3 | **E8** rótulo de la racha | 0 | — | no |
| 4 | **E6** divergencias `Q5`/`T3` | 0 | elegir (a) o (b) | sólo si (a) |
| 5 | **E3** persistir `stress_params` | 0 | **D3** | sí |
| 6 | **E5** pareja de escala `D2`/`D3` | 0 | — | sí |
| 7 | **E4** `FZ` no calibrado | 0 | **decisión de E4** | sí |
| 8 | **E2** saldos de 10-Q | 1 | — | sí |
| 9 | **E9 + E10** yield y shareholder yield | 0 | — | no |
| 10 | **E11** deuda neta / patrimonio | 0 | — | sí |
| 6a | **D2** `B3` deja de puntuar (decisión tomada) | 0 | ✅ resuelta | **sí** |
| 6b | **E18** el stress deja de puntuar (decisión tomada) | 0 | ✅ resuelta | **sí** |
| 11 | **E17** `divestitures` como serie | 0 | — | sí |
| — | E12 · E13 · E14 · E15 · E16 | varias | — | sí |

**E5 → D2 → E18 van en ese orden y con la suite verde entre cada una** — las tres
tocan el recuento de las mismas dos preguntas y juntas en un commit hacen
imposible saber cuál movió qué (ver §7.4).

**E1 va primero y sola**: es lo único que hoy da un número falso, y hasta que esté
arreglada cualquier medición de `S4`, `R2`, `Q2`, `V5` o `fcf_maintenance` sobre un
emisor afectado es ruido.

Del 2 al 4 son **texto y tests, sin cambiar ningún número** — se pueden agrupar en
una entrega.

---

## 7. Especificación de implementación

Escrito para que quien implemente **no tenga que volver a derivar nada**. Cada
apartado lleva el mecanismo real —verificado leyendo el código, no supuesto— y
la trampa que tiene al lado.

### 7.1 El mecanismo de «display-only», que NO es el que parecía

Las dos decisiones tomadas (E18 el stress, D2 `B3`) se implementan con el mismo
mecanismo, y hay que empezar corrigiendo una premisa falsa que estuvo a punto de
colarse en este plan:

> **`D1` y `D8` no son display-only por estar marcadas de alguna forma: es que
> NO ESTÁN en la lista de señales.** `_question_dividend`
> (`synthesis.py:759-767`) pasa a `_aggregate` exactamente
> `D2, D3, D4, D5, D6, B3` más las banderas. `D1` y `D8` no aparecen.

Copiar ese patrón para `B3` y el stress **sería un error**: desaparecerían de la
pregunta en pantalla, y lo decidido es que **se sigan viendo** y dejen de
puntuar. No es lo mismo.

**El mecanismo correcto ya existe, está tipado y en uso en tres sitios**:

```python
QuestionSignal(
    ...,
    counted=False,          # no entra en el semáforo (synthesis.py:474)
    outcome="informational",# ≠ "unchecked": SÍ se comprobó, no puntúa por diseño
    reason="…",             # OBLIGATORIO si counted es False (synthesis.py:129-130)
)
```

`SignalOutcome = Literal["scored", "clear", "unchecked", "informational"]`
(`synthesis.py:73`). El valor `informational` ya lo usan `synthesis.py:343`
(métrica sin banda), `:391` (bandera informativa) y `:403` (no aplica en este
sector), y está tipado en el frontend
(`packages/types/src/models/investment.ts:472`). **No hay que inventar nada.**

#### La trampa: `unavailable_count` se lo traga todo

`_aggregate` calcula `unavailable_count = len(signals) - len(counted)`
(`synthesis.py:491`). Una señal **deliberadamente informativa** cae ahí dentro,
en el mismo cubo que «no se pudo comprobar».

Eso importa porque la narrativa lo imprime: `narrative.py:314` interpola
`sin_puntuar=unavailable_count`. Si no se revisa, la frase pasaría a decir que
hay una señal más «sin puntuar» **sin distinguir el motivo**, que es exactamente
la familia de [PHASE-44.17] («una regla que aborta y una comprobada y limpia
producen la misma ausencia»).

**Mitigación disponible sin tocar el modelo**: `unchecked_count` cuenta sólo
`outcome == "unchecked"` (`synthesis.py:493`), así que un `informational` **no**
se cuela ahí. Es decir: la separación ya existe, hay que **usarla en la frase**.

**A decidir en la implementación** (no está resuelto aquí): si `_aggregate`
publica un contador propio para lo informativo, o si basta con que la frase deje
de usar `unavailable_count` a pelo. Lo primero mueve la forma del
`QuestionVerdict` y **dispara el gate de huella**; lo segundo no.

---

### 7.2 E18 — el escenario de stress deja de puntuar

**Fichero**: `engine/synthesis.py`, `_stress_signal` (línea ~812).

**Cambio**: donde hoy devuelve `_derived_signal("stress", …, "stressed", None)`
—el camino de `coverage < 1,0`— y el de `"caution"`, la señal se emite igual
**con su banda** pero con `counted=False`, `outcome="informational"` y el motivo.

**El motivo va escrito, y es la decisión del usuario**:

> «Un escenario es una hipótesis del motor, no un hecho reportado: informa, no
> dictamina. Si el dividendo aguanta o no un golpe del 30 % es una lectura del
> inversor.»

**Lo que NO se toca**: los seis escenarios y sus parámetros por defecto
(incluido el −30 %), `stress.py` entero, `ST3` y su margen, la card de
escenarios, el dumbbell, y `stress_margin_sentence` de la narrativa.

**Qué sigue puntuando en la pregunta 4**: `z_score`, `FZ`, `L4`, `S2`, `S4`,
`S5`, `S6` (`synthesis.py:779-788`) — todos hechos **medidos**. Sus portantes
son `z_score` y `S2` (`LOAD_BEARING["resilience"]`), así que la pregunta no se
queda sin sustancia.

**Interacción con la financiera**: `_stress_signal` ya devuelve `unchecked` con
motivo en financieras (PHASE-44.24.M). Ese camino **no cambia**: sigue siendo
«no se pudo comprobar», que es distinto de «no puntúa por diseño». Son dos
razones diferentes y tienen que seguir dando textos diferentes.

**Efecto medido en MCD**: **ninguno en el badge** — la pregunta 4 sigue roja por
`FZ`, que sí puntúa.

**Tests exigidos**:

1. El de la decisión, **con el motivo en el docstring** ([PHASE-44.21]).
2. **El caso que lo prueba de verdad: una empresa cuya ÚNICA señal roja de la
   pregunta 4 sea el escenario.** Con MCD el test pasaría por la razón
   equivocada (`FZ` la mantiene roja igual) — es el fallo de [PHASE-47.A]. Hace
   falta un **caso sintético construido a propósito**.
3. El gemelo: la señal **sigue apareciendo** en `question.signals` con su banda y
   su valor. Si desaparece, no es display-only, es borrado.
4. Que la financiera siga dando `unchecked` y no `informational`.

**Bump**: sí, de motor. Cambia un veredicto derivado.

---

### 7.3 D2 — `B3` deja de puntuar

**Fichero**: `engine/synthesis.py`, `_question_dividend` (línea ~759).

**Cambio**: `_band_signal("B3", …)` pasa a emitirse con `counted=False`,
`outcome="informational"` y motivo. **No se saca de la lista** (ver 7.1).

**El motivo va escrito**:

> «El numerador no puede ver las líneas de crédito comprometidas ni los pagarés
> —no existen en el modelo canónico—, así que un valor bajo no distingue "sin
> liquidez" de "con la liquidez sin disponer". Se enseña; no decide.»

**En la misma entrega**: añadir esa misma advertencia a la `note` de `B3` en su
definición del glosario, que es donde la ve quien pulsa la «i».

**Cuidado con `_band_signal`**: hoy es genérico para todas las métricas. Habrá
que darle una forma de marcar una métrica concreta como informativa **sin
escribir la clave a mano en seis sitios** — el patrón del repo para esto es una
constante declarada junto a la fórmula, como `SCALE_COMPANIONS`
(`forensic.py:191-203`) o `LOAD_BEARING` (`synthesis.py:499`).

**Efecto medido en MCD**: la pregunta 3 pasa de `stressed` a `caution`; **el
badge no se mueve** (`worst-of` con la pregunta 4, roja por `FZ`).

**Tests exigidos**:

1. El de la decisión con su motivo dentro.
2. **El caso sintético**: una empresa cuyo único rojo de la pregunta 3 sea `B3`.
   Con MCD el test pasaría por la razón equivocada.
3. Que `B3` **sigue en `question.signals`** con banda y valor.
4. **El que protege de la sobre-corrección**: que `D2`, `D4`, `D5` y las
   banderas **siguen puntuando**. Un `replace` demasiado generoso sobre
   `_band_signal` las apagaría todas y la pregunta se quedaría siempre verde —
   que es el modo de fallo silencioso de este cambio.

**Bump**: sí, de motor.

---

### 7.4 Interacción entre E5, E18 y D2 — el orden importa

Las tres tocan el recuento de las preguntas 3 y 4, y **si se hacen a la vez sin
mirar, la pregunta 3 se puede quedar sin señales que puntúen**:

| Señal de la pregunta 3 | Hoy | Tras E5 + D2 |
| --- | --- | --- |
| `D2` payout sobre FCF | puntúa | **puntúa** (portante) |
| `D3` cobertura FCF | puntúa | **no puntúa** (pareja de escala de `D2`, E5) |
| `D4` payout ajustado SBC | puntúa | puntúa |
| `D5` retorno total sobre FCF | puntúa | puntúa |
| `D6` payout REIT | puntúa | puntúa (o N/A) |
| `B3` años en caja | puntúa | **no puntúa** (D2) |
| `B1`/`B2`/`B4` banderas | puntúan | puntúan |

Quedan `D2`, `D4`, `D5`, `D6` y tres banderas: **suficiente**. Pero hay que
comprobarlo con un test explícito, porque `_aggregate` **devuelve VERDE cuando
ninguna señal puntúa** (`synthesis.py:481-482`) — el «verde por ausencia de
prueba» que [PHASE-44.9] cerró y que estos tres cambios pueden reabrir por otra
puerta.

**Test de guardarraíl**: que `evaluated_count` de la pregunta 3 siga siendo > 0
después de las tres entregas, y que una empresa sin ninguna señal evaluable
salga como *no auditada* y no como sana.

**Orden recomendado**: E5 → D2 → E18, con la suite verde entre cada una. Las tres
juntas en un solo commit hacen imposible saber cuál movió qué.

---

### 7.5 Política de versiones para este plan

`ENGINE_VERSION` está en **1.9.0** y `NARRATIVE_VERSION` en **1.2.0**.

- **Un solo bump por tanda**, no uno por entrega: un bump invalida la
  comparabilidad de los runs guardados, y hacerlo cinco veces seguidas no aporta
  nada y multiplica el ruido en el comparador.
- Las entregas **sin bump** (E7 motivo falso, E8 rótulo, E6 si se elige la
  opción documental, E9/E10 si van como `V*`) pueden ir en su propia tanda
  **antes**, porque no invalidan nada.
- **El gate de huella** (`ENGINE_SHAPE_FINGERPRINTS`) mira los campos de las
  dataclasses y los dominios de los `Literal` (ampliado en PHASE-44.17). Si una
  entrega añade un contador a `QuestionVerdict` (ver 7.1), la huella se mueve y
  **el gate exige el bump** — comprobar que efectivamente falla antes de
  subirlo, porque un gate que da verde en un cambio incompatible está mirando a
  otro lado.

---

### 7.6 Verificación transversal, no negociable

Vale para **todas** las entregas de este plan:

1. **Cada test se verifica ROMPIENDO la línea concreta que dice proteger** — y
   comprobando **que la rotura ENTRÓ** ([PHASE-47.E]: una sonda que no encuentra
   su objetivo devuelve verde igual que un guardarraíl sano). Afirmar el patrón
   antes de sustituir (`assert texto.count(patrón) == 1`).
2. **Nunca dos `pytest` a la vez.** La base `crisol_test` es una y compartida.
   Antes de lanzar la suite, comprobar que no hay ningún agente ni tarea de
   fondo viva. Y **`| tail` enmascara el código de salida**: redirigir a fichero
   con `EXIT=$?` dentro, y **borrar el fichero antes** ([PHASE-44.24]: leer el
   `tail` de un log que ya existía es creerse una suite que nunca corrió).
3. **El intérprete es `backend/.venv/Scripts/python.exe`**, el mismo 3.12 que
   CI. El `python` del PATH es 3.13 y da un verde que no vale.
4. **`prettier --write <fichero>`, nunca `pnpm format`**, que es
   `prettier --write .` y reformatea ~350 ficheros.
5. Antes de dar una entrega por cerrada: `make verify` + `make audit-balances`
   si toca datos.

---
## 8. Referencias

- Documento auditado: [`Check-metrics.md`](Check-metrics.md)
- Origen de los cortes de dividendo: [`DESIGN-v2-investment-module.md`](DESIGN-v2-investment-module.md) §410-448
- Calibración sectorial: [`sector-calibration-investment.md`](sector-calibration-investment.md) · [PHASE-44.21](../phases/phase-44.21-sector-calibration.md)
- Divergencias cuaderno vs. motor: [`../investment-threshold-divergences.md`](../investment-threshold-divergences.md)
- Lo que espera prueba manual: [`../HANDOFF.md`](../HANDOFF.md)
- Lecciones citadas: [`../lessons.md`](../lessons.md) — PHASE-43, PHASE-44.12,
  PHASE-44.14, PHASE-44.21, PHASE-46
