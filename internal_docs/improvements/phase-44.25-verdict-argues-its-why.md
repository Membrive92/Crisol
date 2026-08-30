# PHASE-44.25 — El veredicto argumenta su porqué (plan de mejora)

**Estado**: ⏳ plan aprobado a falta de revisión del usuario · **Fecha**: 2026-08-29
**Origen**: prueba manual del usuario sobre MCD — _«De estos indicadores, a la
hora de leer el veredicto no se entiende el porqué exactamente se debería
evitar»_. La captura enseña el hero «Evitar — Perfil a evitar: X-Score en rojo
(riesgo de quiebra). El dividendo está en riesgo.» y las cuatro preguntas con
sus tablas de señales, sin que ningún pixel conecte una cosa con la otra.

---

## 0. Cómo se hizo este plan (y qué cobertura tuvo)

Cinco lectores en paralelo (motor · presentación · UI web · capa
compartida+móvil · docs+crítica UX), cada afirmación con cita `fichero:línea`,
y dos diseñadores independientes con lentes distintas (argumento causal ·
contrafactual). **El tercer diseñador (divulgación progresiva), los tres jueces
y la síntesis automática murieron por límite de sesión y no llegaron a
ejecutarse**: el juicio y la síntesis los hizo el orquestador en el bucle
principal, verificando a mano contra el código las afirmaciones de más carga
(la regla de `_safety_profile`, el truncado `[:2]` del titular, el glifo
invertido, `isNegationOf`, `LOAD_BEARING`). Los dos diseñadores convergieron
por separado en la misma arquitectura — la matriz de seguridad como dato del
run — lo que es en sí una señal de robustez. La lente de divulgación progresiva
no quedó huérfana: sus preguntas (jerarquía, ruido, qué se ve sin abrir nada)
están respondidas por piezas concretas de las entregas D y E, y se dice dónde.

---

## 1. Diagnóstico — la cadena está rota en cuatro eslabones

El déficit **no es de información**: todas las piezas del argumento existen,
construidas cada una en una entrega distinta con su justificación. Lo que no
existe es la **cadena**: regla → condición cumplida → señal → número → corte →
ficha. El informe demuestra todo y no argumenta nada — el título de PHASE-44.24
(«el informe demuestra todo y explica poco») aplicado un nivel más arriba.

### 1.1 El motor sabe el porqué con precisión de señal y lo tira al serializar

`_safety_profile` (`engine/synthesis.py:792-848`) es la regla completa: cuatro
condiciones OR de «Evitar» — (M-Score Y accruals rojos) | Z'' rojo | X-Score
(FZ) rojo | B4 encendida — y seis comprobaciones de «Conservador». Para MCD
disparó la tercera: `if _band(fz) == "stressed"`. Pero lo único que persiste es
`label` + `blocking_reasons: tuple[str, ...]` — **prosa en español sin clave de
señal** (`synthesis.py:193`). El frontend tendría que parsear texto para saber
que «X-Score en rojo» es la fila `FZ`.

Peor: al entrar por la rama `avoid` se retorna **antes** de evaluar las
condiciones de Conservador (`synthesis.py:826-827`) — «qué tendría que cambiar
para salir de Evitar» **ni siquiera se calcula**.

### 1.2 La presentación trunca y no ensambla

- El titular une **sólo las 2 primeras** `blocking_reasons`
  (`narrative.py:267`, `[:2]`) — con 3+ motivos, el tercero desaparece en
  silencio.
- La frase de cada pregunta cita como máximo 2 etiquetas **sin valor ni
  distancia** (`report.py:130-146`, `_worst_labels` recibe `distances` y no lo
  usa).
- La frase de evidencia **desinforma activamente**: «Se evaluaron 8 señales, 0
  se comprobaron y salieron limpias y 0 no se pudieron comprobar» — `clear_count`
  sólo cuenta **banderas** comprobadas-limpias (`synthesis.py:414`) y la
  pregunta de resiliencia no tiene ninguna, así que sus ceros son estructurales.
  Se lee «las 8 salieron mal» cuando 6 de 8 están en Sano. El desglose que sí
  explicaría el color (6 verdes · 2 rojas) viaja por señal y ninguna plantilla
  lo agrega.
- El número que decidió la señal de stress **existe persistido con frase
  humana incluida** en `verdict["stress"]` (`service.py:237`,
  `stress.py:48-57`) y nadie lo cruza con la fila que sale «Valor — ·
  Distancia —».
- `dividend_verdict` es el peor de las preguntas dividend y resilience
  (`synthesis.py:870-876`): «El dividendo está en riesgo» puede venir SOLO de
  la resistencia, y el payload no dice cuál lo decidió.

### 1.3 La pantalla reconstruye adivinando — y fabrica afirmaciones falsas

La regla **sí se enuncia** (la hipótesis inicial «no se enuncia en ningún
sitio» resultó falsa): `RuleChecklist` es la primera card del Dictamen
(`tab-verdict.tsx:176-189`), con las 4 reglas de Evitar y 5 de Conservador.
Pero está construida sobre una copia a mano casada por cadena, y tiene cuatro
defectos verificados:

1. **Glifo invertido sin leyenda**: la condición CUMPLIDA (la causa del Evitar)
   pinta `✕` y las no cumplidas `✓` verde (`tab-verdict.tsx:322`). Junto a una
   proposición, ✕ se lee «no es verdad»: la línea causal sale literalmente
   negada.
2. **✓ fabricados bajo un perfil «avoid»**: `safetyRules` deriva `met` de
   `blocking_reasons` con `includes()` + `isNegationOf` por primera palabra
   (`investment-verdict-labels.ts:89,109-111`), pero en un avoid esa lista
   contiene motivos de EVITAR, no negaciones de Conservador — y el motor ni
   evaluó esos checks (retorno temprano). «F-Score ≥ 7» sale ✓ **siempre** en
   un avoid; un M-Score ámbar mostraría «M-Score en verde ✓». La checklist que
   existe para auditar el sello afirma cosas que los datos contradicen, justo
   debajo del badge «Evitar».
3. **«LAS CINCO» vs seis**: el motor evalúa SEIS condiciones de Conservador
   (la sexta: B4 sin poder comprobar bloquea el sello, `synthesis.py:838-845`);
   la lista compartida declara cinco. El recuento en prosa ya caducó una vez.
4. **Acoplamiento por cadena sin gate**: el test sólo afirma longitudes 4/5
   (`investment-verdict-labels.test.ts:64-67`). Reformular un motivo en el
   motor apaga el marcado en silencio.

### 1.4 Los datos que llegan al cliente y mueren sin pintarse

- `ReportSignal.status` — publicado expresamente «para que la pantalla imprima
  la marca de aproximación» (`report.py:48-51`); `signal-table.tsx` **no lo lee
  nunca**.
- `severity_rank` — se consume sólo como orden invisible; su significado («la
  peor») no se pinta.
- La ficha de FZ, con la explicación EXACTA de la contradicción Z''-sano /
  X-rojo — _«cuando discrepan, la discrepancia es el hallazgo»_
  (`glossary.py:781-785`) — está cargada en la página e inalcanzable desde el
  veredicto: `SignalTable` no tiene ⓘ, y FZ además está en
  `NO_BREAKDOWN_BY_DESIGN`.
- La paridad móvil de la capa de lectura de señales quedó **prometida en
  44.24.C y nunca entregada** (`phases/phase-44.24.C-signal-gradient.md`,
  «va con la entrega E» — y la lista de paridad de E no la incluye): móvil
  pinta las señales en el orden crudo del run, sin distancia ni procedencia.
- Otras arrugas: la evidencia se pinta DOS veces con redacciones distintas
  (frase del servidor + `evidenceBreakdown`); prosa duplicada a mano entre
  apps con una copia ya divergida (la nota FFO del stress); la columna
  «¿Puntúa?» sin explicación in situ ni entrada en la guía;
  `LOAD_BEARING["resilience"] = ("z_score", "S2")` — **FZ no es portante de su
  propia pregunta y sin embargo decide él solo el veredicto global**
  (`synthesis.py:424` vs `:822`): dos sistemas causales que no se referencian.

---

## 2. Decisiones de diseño (con sus porqués)

**D1 — La causalidad la emite el MOTOR y se persiste en el run.** Es la lección
[PHASE-34] («si parcheas la misma raíz ≥2 veces, mueve la fuente de verdad»)
aplicada aquí: el puente por cadenas ya produjo tres defectos (✓ fabricados,
glifo bimodal, 5-vs-6). Reconstruir la matriz al servir con la regla de HOY
mentiría sobre runs de motores con otra regla — familia «comparable es
precondición» (44.24.F). Como `thresholds_used` en 44.9.

**D2 — La matriz vive como catálogo junto a la fórmula** (44.23):
`SAFETY_MATRIX` en el engine, hermana de `METRIC_CATALOG`, con por condición:
`key`, `rule` (avoid/conservative), `text` (byte-igual al literal de hoy),
`unmet_text`, `inverse` (el giro contrafactual sin números) y `signal_keys`
(las claves REALES: `("FZ",)`, `("m_score","accruals")`,
`("B4_dividend_funded_externally",)`).

**D3 — Tri-estado honesto en cada condición** (`met: True | False | None` con
motivo obligatorio si `None`): hoy una banda ausente hace que la regla «no
dispare» y la UI lo pinta como «✓ no se cumple» — el falso limpio de 44.17
aplicado a la matriz. En una financiera, las condiciones sobre scores apagados
salen «sin poder comprobar», no «no se cumple».

**D4 — Desaparece el retorno temprano**: las 10 condiciones se evalúan siempre.
`label` y `blocking_reasons` se **derivan** de las condiciones con la misma
lógica, byte-iguales a los del motor 1.7.0 (golden de equivalencia). Es lo que
hace posible el contrafactual «qué lo sacaría de Evitar».

**D5 — El contrafactual es composición de datos, nunca opinión.** El servidor
afirma lo estructural con plantilla versionada («Dejaría de ser «Evitar» si
{cambios}») usando los `inverse` de las condiciones cumplidas Y evaluables —
una condición `met=None` **jamás** entra en `{cambios}` (44.17). El número
exacto («volvería a pesar si bajara de −0,25 — hoy 0,87») lo compone la capa
compartida con `effectiveThreshold` + formato por unidad, igual en las tres
superficies — precedente de `_distance_phrase` (`report.py:241-252`). Redacción
por inversión de regla («dejaría de pesar si…»), nunca «debería»: P5 sigue
vigente (sin recomendaciones), con el disclaimer compartido al lado.

**D6 — «Decisiva» ≠ «roja».** La marca «decidió el veredicto» sale de las
condiciones avoid cumplidas (`signal_keys`), no del color: el stress es rojo y
NO está en la matriz — confundir «tiñó la pregunta» con «disparó el perfil» es
exactamente la costura que el usuario no podía coser. Y NO se reutiliza
`LOAD_BEARING` (en MCD marcaría el Z'' verde y no el FZ).

**D7 — La discrepancia entre los dos modelos de insolvencia se SEÑALA, no se
re-redacta.** Frase de servidor factual («Los dos modelos de insolvencia no
coinciden: {rojo} está en rojo y {sano} en sano. La discrepancia es el
hallazgo…») condicionada a que las señales persistidas lo muestren; la
explicación de fondo sigue viviendo en la ficha de FZ del glosario, que la
frase apunta — una definición en pantalla es la que acaba mintiendo (44.23).
El PAR de scores «segunda opinión» se declara en el engine junto a los scores.

**D8 — La fila del stress se rellena desde lo YA persistido.** Las frases de
los escenarios (`verdict["stress"]`, con `coverage_before/after` y `sentence`
redactada por el motor del run) se adjuntan a la señal al servir — es un hecho
del run, así que **beneficia también a los runs viejos**. Rechazado darle
`value=coverage_after` a la señal: la convertiría en pseudo-métrica con
distancia contra un corte que no existe — un hueco con forma de dato.

**D9 — Palabras, no glifos.** La checklist pasa a chips con palabra
(«SE CUMPLE» rojo / «no se cumple» tenue / «sin poder comprobar» gris). La
bimodalidad del ✕ ES el defecto; una leyenda lo parchearía, no lo arreglaría.

**D10 — El fallback legacy deja de fabricar.** Para runs sin `conditions`: las
4 de Evitar siguen casadas por `includes()` contra los `blocking_reasons`
**persistidos** (dato del run, no regla de hoy); las de Conservador bajo un
perfil avoid pasan a «sin registro en este análisis» — que es la verdad, el
motor retornó antes de evaluarlas. Se retira `isNegationOf` en ese camino.

**D11 — Móvil no es un follow-up.** La paridad de `SignalList` con `run.report`
(deuda declarada en 44.24.C) es **prerrequisito dentro de la fase**: cada
columna nueva sólo-web ensancha una divergencia ya abierta.

---

## 3. Entregas

Orden: **A → B → C → D → E**, con F transversal. Cada entrega deja la app
utilizable y verde (`make verify`); la prueba manual del usuario cierra la fase.

### A — Motor 1.8.0: la matriz de seguridad como dato del run · tamaño L

`engine/synthesis.py` · `engine/version.py` · `service.py` · tests.

- `SAFETY_MATRIX` (4 avoid + 6 conservative) con `key`, `rule`, `text`,
  `unmet_text`, `inverse`, `signal_keys` — literales byte-iguales a los de hoy.
- `SafetyConditionResult` (dataclass del engine — el bump de huella es
  deliberado): `key`, `rule`, `text`, `met: bool | None`, `reason` (obligatorio
  si `None`), `signals: tuple[ConditionSignal, ...]` con clave/banda/valor de
  cada métrica o bandera implicada — la card se auto-contiene.
- `_safety_profile` evalúa las 10 SIEMPRE; `label`/`blocking_reasons` derivados
  byte-iguales (golden). `SafetyProfile.conditions` aditivo.
- `SynthesisResult.dividend_verdict_source: "dividend" | "resilience" | "both"
  | None` — quién decidió el worst-of.
- Par de contraste de insolvencia declarado junto a los scores.
- **ENGINE_VERSION 1.7.0 → 1.8.0** + huella.

Criterios: golden de equivalencia sobre los fixtures existentes (las tres ramas
de label, incluida la interpolación del reason de B4 en la sexta); tri-estado
con bandas `None`; gate de integridad `signal_keys ⊆` claves publicadas.

### B — Presentación: el porqué se ensambla al servir · tamaño L

`presentation/report.py` · `presentation/narrative.py` · `schemas.py` · tests.

- `ReportLayer.why` — **`None` para runs sin `conditions`** (precondición, no
  etiqueta): condiciones + distancias/origen por señal (piezas de 44.24.C),
  `decided_by`, `exit_sentence`, `models_disagree`.
- `ReportSignal.drove_verdict` (sólo desde condiciones avoid cumplidas) y
  `ReportSignal.evidence_sentences` (frases persistidas de los escenarios de
  stress con `coverage_after < 1` — funciona en runs viejos).
- `NextCheck.signal_key` — los bullets de «Qué miraría a continuación» se
  vuelven enlazables por clave; muere el `key="pregunta:ETIQUETA"`.
- `narrative.py` → **NARRATIVE_VERSION 1.1.0**: `PROFILE_WHY_TEMPLATES`
  (`avoid_exit` / `avoid_exit_unknown` / `watch_exit` / `conservative_fall` /
  `models_disagree`), `EVIDENCE_TEMPLATES["with_bands"]` («Puntuaron
  {puntuaron} señales: {desglose}», segmentos omitiendo los cero — mata el
  «0 se comprobaron y salieron limpias»), variante `avoid_more` del titular
  para 3+ motivos («…y {mas} más») y `conservative` sin recuento que caduque
  («todas las condiciones»). Todo por el mecanismo existente: plantillas-DATO,
  `templates_fingerprint`, goldens de texto exacto, gate sin-dígitos.

### C — Tipos y capa compartida: filas del porqué para tres superficies · tamaño M

`packages/types/src/models/investment.ts` · `packages/ui/src/investment-verdict-why.ts`
(nuevo) · `investment-verdict-labels.ts` · `investment-report-guide.ts` ·
`investment-signal-read.ts`.

- Campos nuevos **todos opcionales** (un run es la unión de todas las versiones,
  44.16; un backend anterior tampoco los manda, 47.E).
- `verdictWhyRows(run, catalog)`: las filas de la card para web + móvil +
  dictamen imprimible — las copias que existirán DESPUÉS. Chips con palabra
  (D9). `counterfactualLine(cond, threshold, value)` con patrones como dato y
  escáner sin-dígitos espejo del gate del backend.
- Fallback legacy honesto (D10). `AVOID/CONSERVATIVE_RULES` pasan a fallback,
  atadas al catálogo del motor por **fixture-contrato en dos direcciones**
  (mecanismo del fixture de `evidence.py`: pytest contra `SAFETY_MATRIX`,
  vitest contra las listas).
- Sexta condición de Conservador por fin con fila; título «…se cumplen TODAS».
- Guía: entradas «¿Puntúa?» y «Por qué este veredicto». La tabla pinta la de
  «¿Puntúa?» como nota al pie DESDE la guía (una copia, tres superficies).
- Regla de dedupe: `evidenceBreakdown` del cliente sólo cuando la frase del
  servidor no trae recuentos.
- Suben las copys duplicadas a mano entre apps (semáforo, «no es una nota
  media», aviso legacy, la nota FFO del stress **ya divergida**, prosa de
  frescura).

### D — Web: la card «Por qué este veredicto» y la cadena clicable · tamaño M

`tab-verdict.tsx` · `analysis-hero.tsx` · `signal-table.tsx` · `page.tsx` ·
`report-links.ts` · tests.

- La card del perfil (primera del Dictamen) se convierte en **«Por qué este
  veredicto»**, cuatro bloques desde `verdictWhyRows`:
  1. *Lo que lo decidió* — condiciones avoid cumplidas con número, corte,
     procedencia de la vara, chip `DECIDIÓ EL VEREDICTO` y enlace a la fila.
  2. *Las demás reglas de Evitar* — aquí el Z'' 5,20 sano queda JUNTO al
     X-Score rojo, y debajo la frase `models_disagree` cuando aplica.
  3. *El contrafactual* — `exit_sentence` + líneas numéricas compartidas +
     disclaimer (comprobación de reglas, no recomendación).
  4. *El camino hasta Conservador* — las 6 condiciones con su estado.
- Hero: enlace «Ver el porqué» bajo el titular; los puntos de las cuatro
  preguntas (hoy spans muertos) enlazan a sus cards; procedencia del dividendo
  («por la resistencia a un golpe») cuando `dividend_verdict_source` viaja.
  En `printMode` estos controles **no se renderizan** (44.24.H).
- Expansión controlada: la página lee `?senal=FZ`, localiza la pregunta, baja
  `openQuestionKey`/`highlight` por props — el enlace no puede morir contra un
  disclosure colapsado. Cero hooks de router en componentes.
- `SignalTable`: chip decisiva; `evidence_sentences` bajo la fila del stress
  (deja de ser la más hueca); **por fin lee `ReportSignal.status`** (la marca
  `*` publicada y nunca leída); ⓘ de ficha en señales de tipo score (la
  explicación de la discrepancia se vuelve alcanzable desde donde se ve);
  nota al pie «¿Puntúa?».
- Se retira la línea de evidencia duplicada; bullets de next_checks enlazados.

*(Aquí responde la lente de divulgación que faltó: qué se ve sin abrir nada —
hero + card del porqué con el número arriba; qué al abrir — la tabla ordenada
con la decisiva marcada; qué al pedir más — ficha ⓘ y Forense. Las filas
grises NO se ocultan: son la otra mitad del porqué, decisión de 44.9.)*

### E — Móvil: paridad primero, después la misma cadena · tamaño L

`apps/mobile/components/investment/report-tabs.tsx` · `analysis.tsx` · tests.

- **Prerrequisito**: `SignalList` consume la capa de lectura (`orderedSignals`,
  `distanceSentence`, `originSentence`) — la deuda declarada en 44.24.C.
- Después, lo mismo que web desde las MISMAS funciones: card desde
  `verdictWhyRows` (en móvil los anchors no navegan → el número va EN la fila),
  chips, frases del stress, dedupe, procedencia del dividendo. Tocar una regla
  expande la pregunta en pantalla (estado local, no URL).

### F — Gates de mordida y fixture real (transversal) · tamaño S

- Fixture del run REAL de MCD extraído de BD (no escrito a mano — 44.16), en
  sus dos épocas (pre y post 1.8.0), para los tests de tolerancia.
- Gate de introspección: todo Mapping de plantillas del módulo narrative está
  en `templates_fingerprint` (roto: grupo nuevo sin registrar → falla).
- Cross-gate de claves donde viven las claves reales (backend): toda
  `signal_key` de `SAFETY_MATRIX` ∈ claves de métrica ∪ claves de bandera.
- **Método**: cada sonda afirmada antes de correr (47.E) y cada gate tumbado
  reintroduciendo el defecto concreto — el ✓ fabricado se valida reintroduciendo
  `isNegationOf` bajo avoid y viendo caer el test; el chip decisiva, marcando
  toda señal roja; la expansión, quitando el efecto de apertura. Una sonda que
  no muerde significa otro camino al verde (44.24). Nunca dos pytest a la vez.

---

## 4. Qué pasa con los runs viejos

| Pieza | Run ≥ 1.8.0 | Run 1.1.0–1.7.0 | Run 1.0.0 (el MCD actual) |
|---|---|---|---|
| Card «Por qué» | completa, con contrafactual | motivos persistidos + checklist legacy honesta («sin registro» bajo avoid) + aviso reanalizar | igual + StaleRunNotice existente |
| `exit_sentence` / `models_disagree` | sí | **no se emite** (no se fabrica con la regla de hoy) | no |
| Chip «decidió el veredicto» | sí | no (ausencia honesta) | no |
| Frases del stress en su fila | sí | **sí** (dato persistido desde siempre) | sí, si `verdict.stress` existe |
| Evidencia `with_bands` | sí | sí (usa `signals[]`, presentes desde 44.9) | plantilla legacy intacta |
| Procedencia del dividendo | sí | no | no |

El único usuario reanaliza MCD en un clic; la card degradada se lo dice en
pantalla.

## 5. Textos exactos para el caso MCD (números reales de la captura)

```
── CARD «POR QUÉ ESTE VEREDICTO» ──
LO QUE LO DECIDIÓ (1 de 4 reglas de Evitar se cumple)
[SE CUMPLE] X-Score en rojo (riesgo de quiebra)        [DECIDIÓ EL VEREDICTO]
  X-Score de Zmijewski: 0,87 · el rojo empieza en −0,25 · banda genérica
  → Ver la señal (¿Aguanta un golpe?) · Desglose en Forense
  «Dejaría de pesar si el X-Score volviera por debajo de −0,25 (hoy 0,87).»

LAS OTRAS TRES REGLAS DE EVITAR
[no se cumple] Z''-Score en rojo (riesgo de insolvencia) — Z'' 5,20 · Sano
[no se cumple] M-Score y accruals ambos en rojo (manipulación probable)
[no se cumple] dividendo financiado con deuda o emisión — se comprobó y no se encendió

«Los dos modelos de insolvencia no coinciden: el X-Score está en rojo y el
Z''-Score en sano. La discrepancia es el hallazgo — su desglose está en la
pestaña Forense.»

«Dejaría de ser «Evitar» si el X-Score saliera del rojo. Pasaría a «Vigilar»;
«Conservador» exige además sus seis condiciones.»

── FRASE DE LA 4ª PREGUNTA (antes / después) ──
Antes:  «…Se evaluaron 8 señales, 0 se comprobaron y salieron limpias y 0 no
         se pudieron comprobar.»
Después: «…Puntuaron 8 señales: 6 en verde y 2 en rojo.»

── FILA DEL STRESS (deja de estar hueca) ──
Escenario de stress (deja de cubrir)   Valor — · Riesgo · Distancia — · Sí
  «Con las ventas cayendo un 10 %, la cobertura del dividendo por caja libre
   pasa de ⟨1,08×⟩ a ⟨0,92×⟩.»  ← la frase PERSISTIDA del escenario, verbatim

── PIE DE TABLA ──
«¿Puntúa? — si la señal contó para el color de la pregunta. “No” no significa
que esté bien: significa que no pudo contar, y la fila dice por qué.»
```

## 6. Riesgos

1. El bump a 1.8.0 marca «motor anterior» todos los runs y el comparador no
   emitirá cambios de empresa contra runs viejos (comportamiento diseñado,
   44.24.F) — decirlo en la entrega.
2. Quitar el retorno temprano toca la función más sensible del veredicto: el
   golden de equivalencia byte a byte de `blocking_reasons` (tres ramas de
   label, incluida la interpolación de B4) es la red.
3. El contrafactual puede leerse como consejo de inversión pese a redacción y
   disclaimer — riesgo de producto que sólo la prueba manual valida.
4. Los ✓ fabricados de runs legacy desaparecen: puede percibirse como regresión
   visual hasta reanalizar (eran falsos; la card lo explica).
5. La expansión por URL se suma a `tab/sub/metric/print`: familia del bug
   «noRunYet» — el test de cableado cubre la combinación con printMode y con
   run legacy.
6. Si E (móvil) se recorta, la divergencia de señales se ENSANCHA — por eso es
   prerrequisito dentro de la fase, no follow-up.

## 7. Qué NO entra (y por qué)

- **Score global o «distancia agregada al perfil»** — P5; agregar distancias
  heterogéneas es una opinión disfrazada de dato.
- **Ocultar o colapsar las filas que no puntúan** — decisión deliberada de
  honestidad (44.9: «la otra mitad del porqué»); se jerarquiza, no se borra.
- **Renombrar «¿Puntúa?» o los valores de `dividend_verdict`** — vocabulario
  del motor es contrato (runs viejos, summary, goldens); dos vocabularios para
  la misma pregunta es la lección de PHASE-48.
- **Meta-juicio de la contradicción Z''/FZ** («gana el peor») — opinión.
- **Valor numérico para la señal derivada del stress** — pseudo-métrica con
  distancia contra un corte inexistente.

## 8. Registro de alternativas rechazadas (consolidado de los dos diseñadores)

1. Reconstruir la matriz al servir para runs viejos → mentiría con la regla de
   hoy (44.24.F). 2. Contrafactual numérico entero en servidor → duplicaría en
   Python el formateo por unidad de `packages/ui`; se sigue el precedente de
   `_distance_phrase`. 3. Reutilizar `LOAD_BEARING` como marca de decisiva →
   marcaría el Z'' verde en MCD. 4. Marcar decisiva toda señal roja → confunde
   «tiñó la pregunta» con «disparó el perfil». 5. Gate de strings como solución
   principal → enésimo guardarraíl sobre la fuente equivocada (PHASE-34).
   6. Leyenda para el ✓/✕ → la bimodalidad es el defecto. 7. Enlaces hero→fila
   con anclas de hash → un hash no expande un disclosure y en móvil los anchors
   no navegan. 8. Escribir la explicación de la discrepancia en la card →
   44.23. 9. Auto-expandir siempre la 4ª pregunta → inundar en vez de
   jerarquizar. 10. Meter valor/corte dentro de `blocking_reasons` → dígitos en
   prosa persistida que caducan al recalibrar (44.21).

## 9. Verificación

Por entrega: `make verify` completo (BE + FE) con la suite del backend en
solitario. Los goldens nuevos de narrative con texto EXACTO. Todos los gates
tumbados reintroduciendo su defecto antes de darse por buenos. La fase se
cierra con la prueba manual del usuario sobre MCD reanalizado (motor 1.8.0):
la pregunta de aceptación es literalmente la suya — _¿se entiende, leyendo el
veredicto, por qué exactamente se debería evitar?_
