# PHASE-44.17 — Lo que no se pudo medir, se dice

**Estado**: ✅ implementada (pendiente de prueba manual)
**Rama**: `main` (push directo, [ADR de flujo](../README.md))
**Motor**: 1.3.0 → **1.4.0** (piezas contrastadas) → **1.5.0** (evaluabilidad)
**Origen**: [`improvements/phase-44.17-metric-honesty-and-parity.md`](../improvements/phase-44.17-metric-honesty-and-parity.md) §3

## Objetivo

Corregir las afirmaciones FALSAS del informe. Las otras tres fases del plan
(44.18–44.20) ocultaban información; ésta la tergiversaba, que es peor: un hueco
se ve, y una frase con aspecto de dato se cree.

---

## 1.4.0 — Las tres piezas contrastadas

### El motivo del ejercicio equivocado

`metricRow` elegía qué explicación enseñar con `Array.find` sobre una serie
ordenada de más antiguo a más reciente, así que enseñaba la del PRIMER año. En
McDonald's el M-Score falla en 2021 porque no hay 2020 con el que comparar y en
2022-2025 porque la empresa no publica coste de ventas anual: el informe decía
«sin ejercicio anterior» e invitaba a ingerir más historia, **que no arregla
nada**.

Ahora manda el ejercicio más reciente (`gapSentence`, regla 8 de honestidad), y
si los motivos difieren entre años se declara en vez de dejar que uno hable por
todos.

### La leyenda del forense, escrita a mano y falsa

`tab-forensic.tsx` afirmaba que «el primer ejercicio de la serie sale sin M-Score
ni F-Score: ambos comparan contra el año anterior». Cierto en la empresa que su
autor tenía delante; falso en McDonald's, que se queda sin M-Score en los cinco
por una razón distinta. Es la séptima aparición de la misma familia —una premisa
escrita a mano que caduca— así que la respuesta no es corregir la frase: la
leyenda se **deriva del run** (`metricGapLegend`, compartida) y se recalcula en
cada render. Sin huecos, no se pinta: no decir nada y afirmar algo que no pasa
son cosas distintas.

Móvil la gana también, que hasta ahora no tenía ninguna.

### L4: no tener deuda no es un hueco

No tener deuda venciendo a doce meses es el **mejor** resultado posible del muro
de vencimientos, y salía como «denominador cero (deuda que vence en 12 meses)» —
que la pantalla presenta igual que un dato ausente. Una empresa que lo tiene todo
pagado perdía una señal de resiliencia **por tenerlo pagado**.

Va con un estado nuevo de métrica, `not_applicable`, distinto de
`not_computable`: «la pregunta no se plantea aquí» no es «no se ha podido
responder». Y con la distinción que decide si se puede dar el verde:

| El cero de la deuda a corto | Qué sale |
|---|---|
| **Publicado** por la empresa (`sourced`) | verde: está comprobado |
| **Imputado** por la ingesta (§4.5, el filing no etiqueta el concepto) | sin banda, diciendo exactamente eso |

El verde se gana; no se hereda de que un emisor no etiquete un concepto.

### El gate que no habría exigido este bump

Al subir a 1.4.0, la huella de la forma del engine salió **idéntica** a la de
1.3.0: `ENGINE_SHAPE_FINGERPRINTS` compara nombres de campo de dataclass, y aquí
lo que cambió fue el dominio de un `Literal`. O sea que el gate que existe para
impedir tocar el motor en silencio no habría dicho nada.

Se cierra: la huella pasa a incluir los **dominios de los alias `Literal`** que el
engine publica (`MetricStatus`, `Band`, `Severity`, `FlagOutcome`…), indexados por
nombre y no por módulo para que mover un import no la mueva. Probado
rompiéndolo: añadir un valor a `Band` hace fallar el test.

---

## 1.5.0 — Las banderas publican si se pudieron comprobar

### El defecto

Una `Flag` sólo existe cuando SALTA. La síntesis preguntaba «¿hay bandera con
esta clave?» y traducía el no a **«no se ha encendido»** — que se lee como
*comprobado y limpio*. Pero una regla que aborta por falta de un dato responde
que no exactamente igual: sin coste de ventas, el cruce C3 (inventario vs coste
de ventas) **no se ejecuta ni un año**, no emite bandera, y salía como limpio.

Afecta a las 8 banderas que la síntesis usa como señal: `C1`, `C2`, `C3`, las dos
de `Q4` y `B1`/`B2`/`B4`.

### El diseño, y los tres problemas que la crítica tumbó

El plan proponía un tipo `FlagEvaluation` con default pesimista. La crítica
adversarial encontró que, implementado tal cual, **5 de las 8 seguirían diciendo
«no se ha encendido»** (el inventario de sitios estaba mal en las dos
direcciones), que el default pesimista sin gate cambia un falso verde por un
falso gris universal, y que el criterio de «suficientes años» era
aritméticamente incorrecto. Las tres están cerradas:

1. **Inventario correcto.** Las claves salen de `QUESTION_FLAG_KEYS` y las
   preguntas se construyen desde esa tupla; un test estático prohíbe
   `_flag_signal("clave", …)` con la clave escrita a mano, que es la puerta por
   la que una señal se saltaría el gate.
2. **Gate de cobertura**, simétrico al default pesimista: toda clave usada tiene
   evaluación publicada, comprobado sobre dos series (una completa y una sin
   coste de ventas). Probado rompiéndolo: quitar la publicación de C3 lo hace
   fallar.
3. **Rachas consecutivas, no cardinales.** `runs` busca ventanas seguidas, así
   que con años evaluables {2016, 2018, 2020} y `sustained=2` la regla **no puede
   encenderse jamás**: decir «comprobado y limpio» ahí afirmaría una comprobación
   imposible. Lo que se centraliza es la DECISIÓN, no el umbral — C7 salta con un
   año y C4 exige tres.

### El tercer modo de ausencia

`_growth` devolvía `None` por dos motivos distintos (falta el dato / el ejercicio
anterior valía cero) y hay un tercero que sólo se ve mirando la procedencia: el
**cero imputado**. `growth_of` los separa, porque redactar el motivo sin mirarlo
produce una frase falsa: «falta la partida inventory» cuando lo que pasa es que
el filing no la publica y la ingesta la supone cero.

### Los contadores y el sello

`unavailable_count` metía en un cubo cuatro cosas. Medido en McDonald's, la
pregunta sobre la contabilidad decía `evaluated=3, unavailable=7`, y de esas 7
**sólo 2 eran huecos reales**: las otras 5 eran banderas comprobadas y limpias.
La pantalla **subestimaba** la evidencia mientras el veredicto verde la
**sobreestimaba** — los dos errores a la vez y en direcciones opuestas. Ahora
`clear_count` y `unchecked_count` los separan (opcionales, que la tabla guarda
runs de todas las versiones) y `evidenceBreakdown` los redacta para las dos apps.

Y `_safety_profile` deja de leer una B4 no evaluable como «no está en rojo»: es
una de las cuatro condiciones que fuerzan «Evitar», así que sin comprobarla no se
concede el sello de «Conservador».

---

## Archivos clave

| Fichero | Qué |
|---|---|
| `packages/ui/src/investment-metric-rows.ts` | reglas 8 y 9 de honestidad, `gapSentence`, `metricGapLegend` |
| `engine/base_ratios.py` | `_maturity_wall` (L4 sin muro) |
| `engine/flag_rules.py` | **nuevo**: la decisión de evaluabilidad, en la hoja del grafo de imports |
| `engine/evolution.py` | `growth_of` con los tres modos de ausencia; C1/C2/C3 publican evaluación |
| `engine/dividend.py` | Q4 y B1/B2/B4 publican evaluación |
| `engine/synthesis.py` | default pesimista, `SignalOutcome`, contadores partidos |
| `tests/test_investment_engine_contract.py` | huella con dominios `Literal` + gate estático |

## Verificación

- Los dos gates nuevos **probados reintroduciendo el fallo** (el de la huella y
  el de cobertura de evaluaciones).
- El de la regla 8 también: revertir a `withReason[0]` tumba tres tests.
- Suite completa del backend, `ruff`, `black`, `mypy`, `typecheck`, `lint` y los
  tests de las cinco apps/paquetes en verde.

## Limitaciones conocidas

- **Sin prueba manual todavía.** El efecto se ve reejecutando un análisis.
- Móvil sigue sin pintar `cell.title`, así que el motivo por celda de una métrica
  con años mixtos no se ve en táctil. El de la fila y el de la leyenda sí.
- Las banderas que NO son señal de ninguna pregunta (C4–C8) no publican
  evaluación: no hace falta hoy, y el gate sólo exige las que se usan.

## Próxima fase

PHASE-44.21 — calibración sectorial.
