# PHASE-44.16 — El informe tolera análisis de motores anteriores

**Estado**: ✅ código completo y verde · ⏳ pendiente prueba manual del usuario
**Fecha**: 2026-08-08
**Origen**: un fallo reportado por el usuario en la app viva — *«Sólo en
McDonald's, cuando hago click en una de estas áreas, me lleva a un 404»*.

## Objetivo

Que el informe de análisis se pueda leer aunque lo haya calculado una versión
anterior del motor, sin reventar y —sobre todo— sin mentir.

---

## 1. Qué pasaba

Pulsar una de «Las cuatro preguntas» en el informe de MCD desmontaba el árbol de
React: `SignalTable` hacía `signals.length` sobre `undefined`. Sólo ocurría con
McDonald's porque es el **único valor analizado antes de PHASE-44.9**: su run es
del 2026-07-26 con el motor **1.0.0**, y JNJ es del 1.3.0.

Un `AnalysisRun` es JSONB persistido: se guarda con el motor de su día y se lee
tal cual meses después. La tabla contiene, a la vez, runs de todas las versiones
que han existido. `packages/types`, en cambio, describía sólo lo que produce el
motor de hoy — seis campos declarados **obligatorios** que los runs viejos no
tienen. Con el tipo mintiendo, `tsc` no podía señalar ninguno de los ocho
accesos inseguros.

## 2. El diagnóstico, y por qué el crash era lo de menos

Dos vías independientes, complementarias:

- Un **diff mecánico** del run viejo contra el nuevo, campo a campo sobre el
  JSONB real. Da las claves de diccionario ausentes.
- Una **auditoría multi-agente** (25 agentes, 7 lentes, 18 hallazgos → 13
  confirmados). Encontró lo que el diff era estructuralmente incapaz de ver:
  en `metrics[]` una métrica ausente es un **elemento de lista** que falta, no
  una clave. Así salieron las seis (S7, S8, DUPONT_EM/OM/TAX/FIN).

Ocho sitios distintos, y sólo **uno** reventaba. Los otros siete mentían en
silencio, que es peor porque nadie los reporta:

| Síntoma | Dónde | Qué afirmaba |
|---|---|---|
| `TypeError` al desplegar | `signal-table.tsx:25` | — (crash) |
| Contadores en blanco | `tab-verdict.tsx:339` | « señales evaluadas · sin poder evaluar» |
| Verde sin auditar | `tab-verdict.tsx:296` + hero | un verde por ausencia de prueba como verde verificado |
| **«NaN» en rojo** | `tab-ratios.tsx:183/209` | «la identidad NO cierra: hay un problema en los datos o en una fórmula» |
| Métricas que culpan al emisor | `investment-metric-rows.ts:88` | «no calculable con los datos disponibles» |

Las dos últimas son el motivo real de esta fase. La pantalla **denunciaba un
descuadre contable inexistente** en las cuentas de una empresa real, y **acusaba
a los balances de McDonald's** de una carencia del motor. Un crash se reporta;
una frase con aspecto de dato se cree.

Dos de los tres accesos que parecían crash se salvaban por cortocircuito
(`undefined === 0` es `false`, así que nunca se evaluaba `.length`) — de ahí que
la página cargara bien y sólo muriera al desplegar.

## 3. El arreglo, en tres capas

**Los tipos, honestos.** Los campos posteriores a 1.0.0 pasan a opcionales. El
compilador enumeró él mismo los ocho sitios. La regla general: el tipo de un
documento persistido describe la **unión de todas las versiones escritas**, no
la que produce el emisor de hoy.

**Un tri-estado compartido.** `questionEvidence` devuelve
`evaluated | no-evidence | not-recorded`, y vive en `@crisol/ui` porque la web lo
tenía **copiado en dos ficheros** (el hero y la pestaña) con la misma expresión.
`not-recorded` no se puede colapsar en `no-evidence`: no saber cuántas señales se
evaluaron no es lo mismo que saber que fueron cero.

**Regla 7 de honestidad** en `metricRow`: una métrica ausente de TODOS los
ejercicios dice «no existía en la versión del motor que produjo este análisis»,
reutilizando `missingRow` — que es la regla 6 aplicada a una causa nueva. Al
vivir en la capa compartida, arregla web y móvil a la vez.

**`StaleRunNotice`**, sobre `DegradedPanel`: compara `run.engine_version` con el
`engine_version` del catálogo (que ya viajaba por API desde 44.9 y nadie usaba) y
ofrece reejecutar. Tolerar los huecos evita el crash, pero deja al usuario ante
un informe agujereado sin causa común a la vista; esto es la otra mitad. No se
pinta si el run es POSTERIOR al catálogo — eso es un frontend en caché, y mandar
a reejecutar un análisis sano sería el consejo equivocado.

**Rescate**: los runs viejos SÍ traen `red_signals`/`amber_signals`, que hasta
ahora no se pintaban en ninguna parte de la web. `LegacySignals` las traduce con
el catálogo (nunca la clave cruda) y declara que el veredicto no es auditable.

## 4. Móvil

No reventaba, porque hacía `signals ?? []` — pero por eso mismo presentaba el
veredicto **como si estuviera auditado**, y le faltaba además el caso
`no-evidence`, que es previo a esta fase. Ahora usa el mismo tri-estado y tiene
su propio `LegacySignals`.

## Verificación

- `pnpm typecheck` · `lint` · `knip` verdes (6/6 tareas).
- **144 tests web** · 41 `@crisol/ui` · 28 móvil · 60 services · 3 store.
- **Todas las regresiones nuevas se validaron reintroduciendo el bug**: el test
  del clic reprodujo el `TypeError: Cannot read properties of undefined (reading
  'length')` literal del usuario, y el del DuPont falló con «Found multiple
  elements with the text: NaN».
- Comprobado contra la BD real: MCD (1.0.0) dispara el aviso, JNJ (1.3.0) no.

### La fixture

`__fixtures__/legacy-run-1.0.0.json` se **extrajo de la BD del usuario**
(MCD verbatim), no se escribió a mano. Una fixture inventada hoy llevaría la
forma de hoy y no probaría nada — que es exactamente por qué esto llegó a
producción con la suite en verde. Un test afirma que la fixture NO trae las
claves de 44.9, para que deje de pasar si alguien la «actualiza».

El fixture de móvil, casteado con `as unknown as AnalysisRun`, llevaba una forma
**imposible** (señales presentes y contadores ausentes). Corregido: los tres
campos de 44.9 viajan juntos o no viajan.

## Limitaciones conocidas

- El aviso invita a reejecutar, pero no lo hace solo. Es deliberado: un análisis
  es una foto y reejecutar sin pedirlo cambiaría el informe bajo los pies del
  usuario.
- No hay migración que reescriba los runs viejos, ni la habrá: reproducir la
  forma nueva exigiría recalcular con datos que el run no guardó.

## Próxima fase

Sin decidir. Sigue pendiente lo de más valor del backlog: los **gráficos del
informe**, lo único grande que continúa siendo «todo en tablas».
