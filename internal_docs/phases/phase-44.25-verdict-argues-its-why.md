# PHASE-44.25 — El veredicto argumenta su porqué

**Estado**: 🚧 pendiente prueba manual del usuario
**Rama**: `main` (push directo, ver [memoria del proyecto])
**Fecha**: 2026-08-29
**Plan**: [`improvements/phase-44.25-verdict-argues-its-why.md`](../improvements/phase-44.25-verdict-argues-its-why.md)

## Objetivo

Que un lector pueda reconstruir el argumento del sello. El usuario, mirando el
informe de McDonald's: _«De estos indicadores, a la hora de leer el veredicto no
se entiende el porqué exactamente se debería evitar»_.

## El diagnóstico

El déficit **no era de información**: todas las piezas del argumento existían,
cada una construida en una entrega distinta con su justificación. Lo que no
existía era la **cadena**.

1. **El motor sabía el porqué y lo tiraba al serializar.** `_safety_profile`
   evalúa la banda del X-Score con el `MetricResult` en la mano
   (`synthesis.py:822` antes del cambio) y sólo persistía `blocking_reasons`:
   prosa en español sin ninguna clave. Para marcar «esta fila decidió el sello»
   había que emparejar cadenas de texto.
2. **En «Evitar» ni siquiera se calculaba la salida.** Se retornaba antes de
   evaluar las seis condiciones de «Conservador», así que «qué tendría que
   cambiar» no existía como dato.
3. **La pantalla lo rellenaba adivinando** — y afirmaba cosas falsas: bajo un
   perfil «Evitar», `safetyRules` marcaba como cumplidas condiciones que el
   motor no había llegado a evaluar («F-Score ≥ 7 ✓» salía **siempre**), con un
   glifo bimodal (en «Evitar», cumplir pintaba ✕, que junto a una proposición se
   lee como «no es verdad») y con cinco condiciones cuando el motor comprueba
   seis.
4. **Datos que llegaban al cliente y morían**: `ReportSignal.status` (publicado
   «para que la pantalla imprima la marca de aproximación» y nunca leído), el
   número del escenario de stress (persistido con su frase ya redactada, tres
   cards más abajo de la fila que salía «Valor — · Distancia —»), y la ficha que
   explica la contradicción X-Score rojo / Z''-Score verde, inalcanzable desde
   donde se ve.

## Qué se implementó

### A — Motor 1.8.0: la matriz de seguridad como dato

- `SAFETY_MATRIX`: las diez condiciones declaradas junto a la fórmula, con su
  texto, su giro contrafactual **sin números** (los cortes se calibran por
  sector) y las CLAVES de las señales implicadas.
- Las diez se evalúan SIEMPRE y viajan en `SafetyProfile.conditions`, cada una
  con sus señales y su lectura — la card se auto-contiene.
- `met` es **tri-estado**: `None` es «no se pudo comprobar», con motivo
  obligatorio. Colapsarlo en `False` se lee, en la lista de «Evitar», como una
  comprobación superada (familia PHASE-44.17).
- `label` y `blocking_reasons` se **derivan** de las condiciones, byte-iguales a
  los de 1.7.0 (golden de equivalencia con los textos copiados del motor
  anterior, no generados por el nuevo).
- `dividend_verdict_source`: cuál de las dos preguntas decidió el veredicto del
  dividendo.

### B — Presentación: el porqué se ensambla al servir

- `ReportLayer.why` — **`None` para runs sin la matriz**: precondición, no
  etiqueta. Componerlo con la regla de HOY afirmaría sobre aquel análisis algo
  que su motor no comprobó (familia 44.24.F).
- `ReportSignal.drove_verdict` — **decisiva ≠ roja**: el escenario de stress
  tiñe su pregunta y no está en la matriz del sello.
- `ReportSignal.evidence_sentences` — las frases persistidas de los escenarios
  que dejan de cubrir. Es un hecho del run, así que **también llega a los runs
  viejos**.
- `NextCheck.signal_key` — los bullets se vuelven enlazables por clave; muere el
  `key="pregunta:ETIQUETA"`.
- Narrativa **1.1.0**: el contrafactual (que nunca nombra una condición sin
  comprobar), la discrepancia entre los dos modelos, la evidencia contada **por
  bandas** y el titular que deja de tragarse motivos.

### C — Tipos y capa compartida

- Campos nuevos **opcionales** (un run es la unión de todas las versiones).
- `verdictWhyRows` en `packages/ui`: las filas del porqué para las TRES
  superficies (web, móvil, dictamen imprimible).
- Estados en **palabras**, no glifos. Un solo significado de «se cumple» en las
  dos listas.
- El fallback legacy deja de fabricar: bajo «Evitar», las de «Conservador» salen
  «sin registro en este análisis», que es la verdad.
- La guía gana la sección «Por qué el veredicto dice lo que dice», con la
  entrada de la columna **«¿Puntúa?»** que faltaba.

### D — Web: la cadena clicable

Card «Por qué este veredicto» con la condición que decidió marcada, su número y
su corte, enlace a la fila, el contrafactual y la discrepancia. El hero enlaza
al porqué y dice de dónde sale el veredicto del dividendo. La tabla marca la
señal decisiva, pinta las frases del escenario bajo la fila del stress y **por
fin lee `status`**. En modo dictamen los controles nuevos no se renderizan.

### E — Móvil: paridad primero

`SignalList` pasa a consumir `run.report` — orden por severidad, distancia y
procedencia—, la **deuda declarada en 44.24.C y nunca entregada**. Después, la
misma card desde las mismas funciones, con el número EN la fila (en móvil los
anclas no navegan).

### F — Gates

- `triggered_by` ⊆ claves reales de métrica ∪ bandera (gate en el backend, donde
  viven las claves).
- El contrafactual no escribe números a mano.
- **Todo grupo de plantillas entra en la huella**, comprobado por EFECTO: se
  toca un texto de cada grupo descubierto por introspección y se verifica que el
  hash se mueve. Un gate que nunca falla puede estar mirando a otro lado.

## Qué pasa con los runs viejos

| Pieza | Run ≥ 1.8.0 | Run anterior |
|---|---|---|
| Card «Por qué» | completa, con contrafactual | motivos persistidos + «sin registro» + aviso de reanalizar |
| Contrafactual / discrepancia | sí | **no se emite** |
| Chip «decidió el veredicto» | sí | no |
| Frases del escenario de stress | sí | **sí** (dato persistido del run) |
| Evidencia por bandas | sí | ramas legacy intactas |

## Verificación

- BE: **746 tests de inversión** + suite completa · ruff · black · mypy (239
  ficheros).
- FE: typecheck · lint · knip · **311 web + 216 ui + 106 services + 3 store +
  91 móvil**.
- **17 sondas** ejecutadas rompiendo la línea concreta que cada test dice
  proteger (5 en A, 7 en B, 5 en C/D), cada una afirmada antes de correr. Todas
  muerden.
- Dos huellas registradas: engine 1.8.0 y plantillas 1.1.0.

## Limitaciones conocidas

- **Pendiente la prueba manual del usuario.** El bump a 1.8.0 marca «motor
  anterior» todos los runs existentes: hay que **reanalizar MCD** para ver la
  card completa (la degradada lo dice en pantalla).
- La expansión automática de la pregunta al llegar desde una señal (el
  `openQuestionKey` que el plan describía en D.3) **no entra**: el enlace lleva
  a la pestaña y resalta la fila, pero si el desplegable de esa pregunta está
  cerrado sigue habiendo un gesto de por medio.
- El fallback legacy lista cinco condiciones de «Conservador», no seis: la sexta
  sólo aparece cuando la trae la matriz del motor.

## Próximo paso

Prueba manual sobre MCD reanalizado. La pregunta de aceptación es la del
usuario: **¿se entiende, leyendo el veredicto, por qué exactamente se debería
evitar?**
