# PHASE-44.26 — El Dictamen se lee de arriba abajo

**Estado**: 🚧 pendiente prueba manual del usuario
**Fecha**: 2026-08-30
**Origen**: prueba manual sobre la card de PHASE-44.25 — _«El veredicto es
demasiado técnico. La idea es que esto sea un sumario final que resuma qué está
bien y qué riesgos corre la empresa, con enlaces a los datos. Ahora mismo son
solo apuntes técnicos que hacen inviable su entendimiento de forma rápida»_.

## El diagnóstico

El problema era de **jerarquía, no de falta de prosa**. Las frases legibles ya
existían —el titular, las cuatro frases de pregunta, el contrafactual, la
discrepancia, «qué miraría a continuación», todas compuestas en el servidor con
goldens— pero estaban enterradas: lo primero que se veía era la matriz de
reglas de 44.25, y las frases vivían dentro de cards colapsables más abajo. El
mapa del workflow lo midió: **casi todo el sumario pedido se compone reordenando
y reusando**, con cero plantillas nuevas y `NARRATIVE_VERSION` intacta en 1.1.0.

Dos diseños independientes (re-jerarquizar vs. sumario redactado en servidor) y
una crítica adversarial que eligió el primero: el segundo compraba «nombrar lo
sano en prosa» al precio de un bump de narrativa, 12-17 goldens y **dos pares de
redacciones paralelas del mismo hecho** — el patrón que PHASE-46 cerró.

## El orden nuevo (web y móvil, desde la misma capa)

1. **§1 El dictamen** — las cuatro preguntas con su frase del servidor, primero.
2. **§2 Qué preocupa** — toda señal roja o ámbar que puntuó, rojas primero, con
   valor, banda, distancia y enlace; más las banderas encendidas. Fallback a
   `next_checks` para runs sin señales estructuradas (conserva el «no se puede
   decir qué vigilar» honesto).
3. **§3 Qué está bien (sólo lo comprobado)** — verdes de preguntas AUDITADAS,
   escenarios de stress que siguen cubriendo, banderas comprobadas-y-limpias
   con su razón persistida, y condiciones de «Evitar» descartadas.
4. **§4 Qué cambiaría el sello** — discrepancia + contrafactual (servidor).
5. Escenarios de stress (card existente).
6. **§5 La auditoría del sello** — la matriz de 44.25 entera, PLEGADA por
   defecto. En el dictamen imprimible va siempre abierta y su control no se
   renderiza (44.24.H). Aquí aterriza el «Ver el porqué» del hero — movido a
   esta card porque es la única que existe en TODOS los runs.
7. Alcance + pie de versiones.

## Las reglas de selección (packages/ui/src/investment-dictamen.ts)

Deterministas y escritas con sus porqués — elegir «lo bueno» a mano sería una
opinión disfrazada de resumen:

- **Permanentemente no auditable** (`not-audited` sin portantes): sus señales no
  entran en NINGUNA lista — es el predicado de `next_checks` del servidor,
  espejado UNA vez y consumido por las dos.
- Un riesgo bajo una pregunta **temporalmente** no auditada SÍ se lista, con la
  etiqueta de evidencia al lado (regla 2 de next_checks: se dice con su matiz).
- Un verde bajo una pregunta sin auditar o sin evidencia **no** es fortaleza.
- Tope `max(6, nº de rojas)`: una roja no se esconde JAMÁS por un tope; el
  resto se cuenta («…y n más»).
- Los escenarios que cubren sólo aparecen si la resistencia está evaluada.
- «Comprobado y limpio» usa la razón PERSISTIDA por señal; «comprobado y
  descartado» sale de la matriz del run (motor ≥ 1.8.0), jamás se infiere.

## Renegociación del invariante «un sello sin sus reglas no es auditable»

La matriz no desaparece: se abre. Los ~9 tests que la clavaban visible en
síncrono pasan a abrir la auditoría primero — el mismo gesto que el usuario. El
test «sin flecha no hay trampa» (runs legacy) pasa a afirmar que el ÚNICO
desplegable es la auditoría.

## Verificación

- FE completo verde: 315 web + 233 ui + 106 services + 92 móvil · typecheck ·
  lint · knip · docs-check. BE (tras la segunda entrega): **762 tests de
  inversión** · ruff · black · mypy.
- **14 sondas** rompiendo la línea que cada test dice proteger: 5 en los
  selectores del cliente (una no mordía a la primera — el caso del test no
  llegaba a la guarda; se reescribió con el caso real: verdes bajo pregunta no
  auditada), 3 en web (plegado, printMode, valor en fila), 1 en móvil
  (plegado), 4 en la selección del servidor y 1 en el gate de dígitos.

## Segunda entrega (mismo día): el dictamen, razonado

La prueba manual pidió más: _«qué está bien, qué está mal y el escenario de
stress en una misma card… un informe en texto desarrollado… lo tienes pero
dividido y sin apenas explicar»_. Es la fase futura que el crítico dejó
condicionada — la lista de datos se quedó corta— y se paga como estaba
diseñado:

- **Narrativa 1.2.0** (`SUMMARY_TEMPLATES` + goldens): las entradas «Lo que más
  pesa en contra: …» y «Del lado bueno, con la comprobación superada: …», que
  NOMBRAN señales sin números (los números van en las filas, formateados por
  unidad en la capa compartida), y el margen de stress en frase («La caja libre
  podría caer un 7 %…»), que era la única pieza que el servidor no decía.
- **La selección se muda al servidor** (`ReportLayer.summary`): qué entra y en
  qué orden es parte de lo que la frase afirma, y dos capas decidiéndolo serían
  dos fuentes. El selector del cliente queda como fallback documentado para
  backends anteriores. Mismas reglas, ahora con test backend + sondas.
- **Prerrequisito pagado**: el gate de «cero dígitos en plantillas» enumeraba 7
  grupos a mano y era ciego a los 3 de 44.25 — pasa a introspección (mismo
  descubrimiento que el test de la huella) y se verificó mordiendo.
- **La card única** en web y móvil: entrada en prosa → filas enlazadas de «qué
  preocupa» → banderas → entrada + filas de «qué está bien» → comprobado y
  limpio / descartado → escenarios de stress (con dumbbell en web y el ancla
  `#escenarios` dentro) → discrepancia y contrafactual como cierre.
- **En HORIZONTAL, tres columnas** (web): la primera versión las metió en una
  card pero APILADAS, que es justo lo contrario de lo que pedía la petición
  («para aprovechar el espacio») — la card mide 2.400 px y el contenido bajaba
  en una columna de 640. `repeat(auto-fit, minmax(min(100%, 420px), 1fr))`:
  `auto-fit` colapsa las pistas vacías, así que con tres hijas salen tres
  columnas iguales en un monitor y UNA por debajo de ~1.300 px, sin media query
  (los estilos son inline). El cierre —discrepancia y contrafactual— va a ancho
  completo fuera del grid: es la conclusión, no una cuarta columna. En móvil se
  mantiene apilado: en un teléfono tres columnas de 420 px no caben.

No exige reanalizar: el sumario se compone AL SERVIR sobre las señales que los
runs persisten desde 44.9 (basta recargar con el backend nuevo).

## Limitaciones conocidas

- «Qué preocupa» duplica la etiqueta de una señal que también está en la tabla
  de su pregunta — deliberado: el sumario resume, la tabla audita.
- Las frases de entrada nombran las señales MOSTRADAS; el desbordamiento
  («…y n más») es un formatter-dato compartido, no prosa.
- El fallback del cliente ordena dentro de banda por el orden crudo del run; el
  servidor, por severidad. Divergencia sólo visible contra backends viejos.

## Próximo paso

Prueba manual. La pregunta de aceptación: ¿el Dictamen se entiende de forma
rápida — qué está bien, qué riesgos — sin abrir nada técnico?
