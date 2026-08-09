# PHASE-44.21 — La vara depende del negocio

**Estado**: ✅ implementada (pendiente de prueba manual)
**Rama**: `main` (push directo)
**Motor**: 1.5.0 → **1.6.0**
**Migración**: `g3c95b7d2e8f41` (aditiva y reversible)
**Origen**: [`improvements/sector-calibration-investment.md`](../improvements/sector-calibration-investment.md)

## Objetivo

Una eléctrica con deuda neta 4,8× EBITDA es normal —caja regulada, activos de
cuarenta años, mediana de grado de inversión del sector 5,1×—; una tecnológica
con 4,8× está en problemas. El motor aplicaba UNA vara a las dos, así que media
docena de semáforos de un sector regulado salían en rojo permanente. **Un rojo
que no informa se aprende a ignorar, y entonces deja de informar también el que
sí importa.**

---

## Qué cambia para quien lee un informe

| Perfil | Antes | Ahora |
|---|---|---|
| Eléctrica, deuda neta 4,8× | rojo | **ámbar** (banda 4 / 5,5) |
| Tecnológica, deuda neta 2,5× | ámbar | **rojo** (banda 1 / 2) — el perfil no es «relajar» |
| Banco | 33 métricas con semáforo que no significa nada | **apagadas con su motivo**, y ROA/ROE/S3 re-bandeadas |
| Retail que cobra antes de pagar | rojo de liquidez permanente | **sin rojo**, con la explicación (RC-1) |
| Regulada con payout alto | «paga mucho» | + la pregunta que decide: **quién financia el exceso** (RC-2) |
| Sector sin inventario | F7 podía perderse entero | el check de inventario sale del cómputo |

## Las cuatro preguntas declaran de qué dependen

La guarda anterior era todo-o-nada (`evaluated_count === 0`) y McDonald's salía
**verde confiado con 3 señales de 10**, con las dos que responden la pregunta
—M-Score y accruals— muertas.

No se sustituye por una proporción, y ésa es la decisión: un ratio trataría igual
una señal cualquiera que el M-Score. Cada pregunta declara sus **portantes**, y
si falta uno sale **no auditada** (el cuarto estado, gris, con la lista de lo que
falta) en vez de verde. Un portante en ámbar impide el verde aunque sea el único
ámbar; las no-portantes siguen modulando por acumulación.

| Pregunta | Portantes genéricos | En financieras | En socimis |
|---|---|---|---|
| ¿La contabilidad es de fiar? | M-Score, accruals | Q1, C2 (+ aviso de cobertura forense limitada) | M-Score, Q1 |
| ¿Genera caja de verdad? | Q1, tendencia del FCF | Q1 | — |
| ¿El dividendo cabe? | D2, B4 | D1, B4 | D6, B4 |
| ¿Aguanta un golpe? | Z'', S2 | **no auditable, permanente** | — |

Los portantes se buscan en TODAS las señales del run, no sólo en las de su
pregunta: en un banco la contabilidad se audita con Q1, que se pinta en el bloque
de la caja. Lo que importa es si esa comprobación se hizo, no dónde se dibuja.

La pregunta 4 en una financiera es gris permanente y honesto: la resiliencia
bancaria es capital regulatorio (CET1, LCR) y eso no está en un 10-K. Fingir que
se audita con un Z''-Score sería calcular basura y pintarle un semáforo.

## Dónde vive la calibración, y por qué ahí

En el **engine** (`analysis/engine/sector_profiles.py`), no en la tabla. Si
viviera sólo en `scoring_thresholds`, una base recién creada —o una fila que
nadie sembró— devolvería el catálogo genérico y juzgaría a un banco con cortes
industriales sin decir nada. Es exactamente lo que le pasó a la exención de S7:
razonada, documentada e **inerte durante ocho fases** porque dependía de una fila
que no existía.

La tabla sigue existiendo para lo que sirve —que un run guarde la vara con la que
se midió (`thresholds_used`)— y el seed **refleja** lo que el engine resuelve, así
que las dos no pueden divergir.

Tres decisiones de implementación que sostienen esto:

1. **Los perfiles son deltas.** Lo que un sector no dice, lo hereda del catálogo:
   una métrica nueva entra a la vez en los doce y no hay doce copias que
   sincronizar.
2. **La geometría del corte se declara** (`higher`/`lower`/`central`). En
   `higher_better` los cortes son el suelo y en `lower_better` el techo: los
   mismos dos números invierten el semáforo, y escribir un delta con la forma
   equivocada revienta al arrancar en vez de mentir en silencio.
3. **Las hermanas se derivan.** S6 es S2 medida con caja y L2 es L1 sin
   inventario: si un sector mueve una y la otra se queda en el corte genérico,
   dejan de contar la misma historia sobre la misma empresa. Se escalan por el
   mismo factor, en código, en vez de en una segunda tabla que envejece sola.

## El seed vuelve a actualizar, y es seguro

PHASE-44.18 hizo el arranque sólo-inserción para no reescribir filas bajo los
pies de un run guardado. Esa preocupación está resuelta desde PHASE-44.9: cada
run persiste su `thresholds_used`, así que un análisis viejo se explica con SU
vara aunque la tabla cambie.

Sin actualizar aparece el defecto **simétrico** al de 44.18: una calibración nueva
llegaría a las bases recién creadas y **nunca** a la que lleva meses funcionando,
que es justo la que se usa. `sync_thresholds` inserta lo que falta y reescribe
sólo lo que difiere; en régimen estacionario son cero UPDATEs.

## Migración

`g3c95b7d2e8f41` — una columna `not_applicable_reason TEXT NULL`. **Sin
backfill**: las filas existentes quedan en `NULL` hasta que la sincronización del
arranque las reescriba desde la calibración del engine. Inventar aquí una razón
para 1.500 filas sería escribir a mano lo que el motor sabe derivar.

## Taxonomía: el vocabulario del enum manda

El documento de calibración habla de `TELECOM`, `REAL_ESTATE_REIT` y `GENERIC`;
el enum persistido los llama `COMMUNICATION`, `REAL_ESTATE` y `UNKNOWN`. Se usa
el del enum —renombrar un tipo Postgres para ganar sinónimos es una migración
irreversible a cambio de nada—, y a cambio `sic_mapping` **estrecha**
`COMMUNICATION` a los SIC 4800-4899: sin eso, las bandas de telecomunicaciones
(deuda alta, liquidez baja, ingresos por suscripción) caerían también sobre
editoriales y ocio, que se mudan a consumo discrecional. Con ellos, metalurgia
primaria a materiales, oleoductos y mayoristas de petróleo a energía, ingeniería
a industriales y distribución farmacéutica a consumo básico.

## Una desviación del documento, corregida por un test

Había apagado **S8** (qué parte de la deuda vence a menos de un año) en
financieras. El documento no la lista, y un test que ya existía desde PHASE-44.10
explicaba por qué: *«eso significa lo mismo en un banco que en una fábrica»*. El
test falló y la desviación se revirtió. Es el argumento entero a favor de que las
decisiones razonadas lleven test: la razón sobrevive a quien la escribió.

## Archivos clave

| Fichero | Qué |
|---|---|
| `engine/sector_profiles.py` | **nuevo**: los doce perfiles, la resolución y la whitelist financiera |
| `engine/flag_rules.py` | aplicabilidad de reglas por sector (vive en la hoja del grafo: las capas que las evalúan no pueden importar `sector_profiles` sin ciclo) |
| `engine/base_ratios.py` | RC-1 (circulante negativo) |
| `engine/dividend.py` | RC-2 (payout de regulada) + B1/B2 por sector |
| `engine/forensic.py` | F7 con denominador variable |
| `engine/synthesis.py` | portantes, `audited`, notas de alcance |
| `thresholds/seed.py` · `service.py` | la tabla refleja el engine; `sync_thresholds` converge |
| `catalog/sic_mapping.py` | el contenido de cada cubo, alineado con las bandas |

## Verificación

- 14 goldens nuevos (`tests/test_investment_sector_calibration.py`), uno por
  decisión: utility apalancada, tecnológica apalancada, retail con circulante
  negativo, banco (apagado + núcleo que sobrevive), REIT, portante ausente,
  portantes presentes, resolución con y sin perfil, F7 con y sin check, geometría
  equivocada.
- `alembic upgrade`/`downgrade` reversibles, cabeza única, `alembic check` sin
  drift.
- Backend **1327 tests** en verde, `ruff`, `black`, `mypy` (221 ficheros);
  frontend `typecheck`, `lint`, `knip` y los tests de web (147), móvil (28),
  services (60), ui (55) y store (3). `check_docs.py` sin podredumbre.

## Deuda saldada al cerrar (2026-08-09)

Siete entradas del backlog, todas mecánicas —sin decisiones de calibración— y
todas con su test:

| Qué | Por qué importaba |
|---|---|
| **`knip` entra en CI** y `scripts/` en `ruff`, `black` y `mypy` | La lección de PHASE-43 daba knip por cableado: lo estaba en `make verify`, y `make verify` no es CI. Entre PHASE-43 y hoy no corrió en ningún push. Los scripts son los data-fix y los seeds, que se ejecutan **contra los datos del usuario** |
| **El sector y sus flags se refrescan al re-resolver** + `scripts/reclassify_securities.py` | Congelarlo el día del alta hacía que corregir `sic_mapping` no alcanzara a lo que ya está en el catálogo |
| **Docstring de `classify_sic`** | Abría con «ante la duda NO se marca» y luego argumentaba lo contrario |
| **Test de componente de la tabla de cartera** | Era la única pantalla del módulo sin uno, y la que más formas tiene de mentir con dinero |
| **Date-picker nativo en el alta móvil** | La fecha fija el tipo del BCE que deriva el servidor: un dedazo en el año movía el coste en euros |
| **Auto-scroll del combobox** | Con 20 resultados, bajar con ↓ movía una selección fuera de la ventana |
| **El motivo por celda en móvil** | `cell.title` no se pintaba NUNCA: sin tooltips en táctil, el porqué de cada ejercicio se perdía entero |

El gate de knip se probó rompiéndolo (un fichero muerto lo tumba y sale limpio al
quitarlo) y el del refresco del sector también (desactivarlo hace fallar su test).

## Limitaciones conocidas

- **Sin prueba manual todavía**, y aquí importa más que en otras fases: los
  veredictos de JNJ y MCD pueden moverse al reejecutar.
- **No hay ninguna financiera ni ninguna utility en el catálogo del usuario**, así
  que casi todo esto es latente hasta que se analice una. Los goldens son
  sintéticos por eso.
- La calibración es **v1**: anclas editoriales, no un backtest. La regla
  anti-tuning sigue: una banda no se ajusta para que salga verde una posición
  propia.
- El motor bancario de verdad (NIM, CET1, morosidad, LCR) sigue fuera: exige un
  canónico ampliado.

## Próxima fase

Prueba manual y reejecución de JNJ y MCD.
