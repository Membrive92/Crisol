# Lecciones aprendidas — Crisol

> Este archivo se actualiza CADA VEZ que se corrige un error que podría haberse
> prevenido. Leer al inicio de cada fase y añadir entradas durante la misma.

---

## Formato de una lección

```markdown
### [PHASE-X.Y] Título breve del error

**Error:** qué se hizo mal.
**Causa:** por qué ocurrió.
**Solución:** cómo se corrigió.
**Regla:** qué hacer siempre para evitarlo en el futuro.
```

---

## Lecciones

### [PHASE-41] Reutilizar una expresión SQL que referencia otra tabla exige replicar SUS joins (o sale un producto cartesiano que infla la suma en silencio)

**Error:** El nuevo `compute_position_as_of` (patrimonio a fecha) reutilizó
`signed_amount_expr(Account, paired_account)` pero su query sólo unía
`Account`, `paired_tx` y `paired_account`. El primer test dio
`net_worth=16400 €` en vez de `1700 €` (con `SAWarning: cartesian product
between "categories" and "transactions_1"`).
**Causa:** `signed_amount_expr` cae a `Category.kind` cuando `flow` es NULL
(vía `is_inflow()`/`is_outflow()`). Al no unir `categories`, SQLAlchemy la mete
en el FROM como producto cartesiano: cada tx se multiplica por TODAS las
categorías del usuario → la `SUM` se dispara. La serie histórica
(`compute_position_history`) ya unía `Category` con
`.outerjoin(Category, Category.id == Transaction.category_id)`; el nuevo código
copió la expresión pero no el join.
**Solución:** Añadir el mismo `.outerjoin(Category, ...)` a la query nueva. Un
test con importes conocidos lo cazó al instante (el warning de cartesian product
es la señal inequívoca).
**Regla:** Cuando reutilices una expresión SQL compartida (un `case`, un
`signed_amount_expr`) que referencia columnas de OTRA tabla, replica TODOS los
joins que esa expresión necesita, no sólo los de tu SELECT. Si SQLAlchemy avisa
de "cartesian product between X and Y", falta el join a X o Y y la agregación
está inflada. Escribe el test con importes concretos (no sólo "≥0"): un
cartesiano multiplica, no descuadra por poco.

### [tech-debt] CSS vars en design tokens → hidratación SSR consistente vía detección de RN

**Error:** Pensé en activar/desactivar `var(--color-…)` según `typeof document`, pero
Next.js SSR (Node) **también** tiene `document` undefined, igual que React Native. El
servidor habría emitido literales hex y el cliente CSS vars → mismatch de hidratación.
**Causa:** El detector "modo browser" no es exclusivo del browser real. Hay tres entornos:
RN, Node SSR y browser cliente.
**Solución:** Usar `navigator.product === 'ReactNative'` (canonical RN detection). Es
`false` tanto en Node SSR (no hay navigator) como en browser, así que ambos lados emiten
las mismas cadenas `var(--color-…, fallback)`. Sólo RN ve los literales.
**Regla:** Para cualquier rama de código que dependa del entorno y vaya en `<style>`
SSR-able, distinguir entre "no es browser" y "es React Native"; lo segundo se hace con
`navigator?.product === 'ReactNative'`, no con `typeof document`.

### [tech-debt] FastAPI con `response_class=Response` pierde cookies seteadas en la `Response` inyectada

**Error:** En el endpoint de logout (status 204) seteábamos `delete_cookie` sobre la
`Response` que FastAPI inyecta vía Depends, y luego devolvíamos `Response(status_code=204)`.
El `Set-Cookie` no aparecía en la respuesta.
**Causa:** Cuando un endpoint con `response_class=Response` devuelve una `Response` nueva,
ésta reemplaza por completo a la inyectada. Las cookies/headers que se hubieran añadido a
la inyectada se descartan.
**Solución:** Construir la `Response` final dentro del handler, setear las cookies sobre
ella y devolverla. No usar la `Response` inyectada cuando devuelves una nueva.
**Regla:** En endpoints `response_class=Response` que devuelven `Response(...)` directamente,
no inyectes `response: Response`; muta la que devuelves.

### [tech-debt] Cookie `Path=/auth` no llega al backend cuando el frontend usa rewrites

**Error:** Backend setea `Set-Cookie: ...; Path=/auth`. Frontend (Next.js) hace rewrite
`/api/auth/*` → backend. El navegador setea la cookie con `Path=/auth`, pero la siguiente
petición sale a `/api/auth/refresh`. El navegador no envía la cookie porque
`/api/auth/refresh` no empieza por `/auth`.
**Causa:** El navegador interpreta el `Path` con respecto a la URL que ve él, no la del
backend al otro lado del proxy. Con un rewrite el path observable cambia y el `Path` del
backend deja de aplicar.
**Solución:** Usar `Path=/` en cookies que vayan a viajar a través de un rewrite o reverse
proxy. Sigue siendo `httpOnly` + `SameSite=Lax`, así que la superficie no aumenta.
**Regla:** Si el frontend usa rewrites para llamar al backend, las cookies del backend deben
tener `Path=/` (o coincidir con el prefijo público del rewrite).

### [PHASE-2.2] `exactOptionalPropertyTypes` rechaza `undefined` explícito en props opcionales

**Error:** Al pasar `{ category_id: undefined, date_from: '' }` a un query o al declarar
`error?: string` en las props de un componente y luego pasarle `error={undefined}` desde el padre,
TS falló con `TS2375: Type 'undefined' is not assignable to type 'string'`.
**Causa:** Con `exactOptionalPropertyTypes: true`, una prop `error?: string` significa
"prop ausente **o** string", pero NO acepta `error: undefined` explícito.
**Solución:** Opción A — no pasar la prop si no hay valor (`{...(error && { error })}`).
Opción B — declarar la prop como `error?: string | undefined` cuando sí se vaya a pasar
`undefined` desde callers.
**Regla:** Si una prop puede recibir `undefined` desde el padre (muy común con estado React),
declarar `prop?: Tipo | undefined` explícitamente. Si sólo se omitirá, bastante con `prop?: Tipo`.

### [PHASE-2.2] Vitest sin `esbuild.jsx: 'automatic'` falla con "React is not defined"

**Error:** Los tests de componentes React con Vitest fallaban con `ReferenceError: React is not defined`
aunque el código no importaba React explícitamente (JSX transform automático).
**Causa:** Vitest usa esbuild internamente; sin configurarlo, esbuild usa el transform clásico
(`React.createElement`) en vez del automático (`jsx-runtime`).
**Solución:** En `vitest.config.mts`, añadir:

```ts
export default defineConfig({
  esbuild: { jsx: 'automatic' },
  test: { environment: 'jsdom', ... },
});
```

**Regla:** Todo `vitest.config` de un paquete con JSX debe llevar `esbuild.jsx: 'automatic'`.

### [PHASE-2.2] Añadir script de lint sin instalar `eslint` como devDep

**Error:** Añadí `"lint": "eslint ."` a `package.json` de paquetes que no tenían `eslint`
instalado; `pnpm lint` falló con "eslint no se reconoce como un comando".
**Causa:** En monorepo con `hoist-pattern` restrictivo, `eslint` no está disponible en cada
paquete a menos que se declare como devDep (el preset `@crisol/eslint-config` **usa** eslint
pero no lo arrastra para el binario del paquete).
**Solución:** Añadir `"eslint": "^9.17.0"` a los `devDependencies` de cada paquete que tenga
script de lint.
**Regla:** Si añades script de `lint` a un paquete, añade `eslint` a sus devDeps en el mismo commit.

### [PHASE-4.1] Endpoints con `status_code=204` y retorno `None` revientan en FastAPI ≥ 0.116

**Error:** Tras actualizar a FastAPI 0.116, los endpoints con
`@router.post(..., status_code=204)` y firma `-> None` lanzaban
`AssertionError: Status code 204 must not have a response body` al arrancar la app.
Bloqueaba todos los tests del backend, no solo los del módulo nuevo.
**Causa:** FastAPI 0.116 añadió un check estricto: cuando hay `response_model` implícito
(deducido del tipo de retorno) y el status code es 204, el assert falla. Antes era warning.
**Solución:** Importar `Response` de FastAPI, declarar `response_class=Response` en el
decorador, y devolver `Response(status_code=204)` explícitamente.
**Regla:** Cualquier endpoint que devuelva 204 debe tener `response_class=Response` y
retornar `Response(status_code=204)`. NUNCA confiar en el tipo `-> None` para indicar "sin body".

### [PHASE-4.1] `model_validate` falla con `MissingGreenlet` tras `flush` con `onupdate`

**Error:** `ImportJobResponse.model_validate(job)` devolvía `MissingGreenlet:
greenlet_spawn has not been called` al acceder a `updated_at` justo después de
`await db.flush()` cuando el service mutaba el job.
**Causa:** El campo `updated_at` tiene `onupdate=func.now()`. Cuando SQLAlchemy emite el
UPDATE, el valor calculado por la DB no se trae de vuelta al objeto en memoria; SA marca
el atributo como expirado. Al leerlo desde Pydantic (síncrono) intenta lazy load, pero
la sesión es async — y revienta. `expire_on_commit=False` no protege porque el atributo
no se "expira" tras commit, queda _stale_ tras el flush con `onupdate`.
**Solución:** Después del último `flush()` que mute el objeto, llamar a
`await db.refresh(job)` antes de devolverlo al router.
**Regla:** Si un service muta un objeto con campos `onupdate=func.now()` y el endpoint
serializa ese objeto post-mutación, hacer `await db.refresh(obj)` antes de retornar.

### [PHASE-4.2] `Blob.text()` y `Blob.slice().text()` no existen en jsdom

**Error:** Un detector de cabeceras CSV en el browser usaba
`file.slice(0, 8192).text()` (y luego `file.text()`). Los tests con `vitest` + `jsdom`
rompían con `TypeError: slice.text is not a function` y `file.text is not a function`,
aunque ambos métodos están en la spec moderna del DOM y funcionan en navegadores reales.
**Causa:** jsdom (la versión que usa vitest 2.x en este repo) no implementa el método
asíncrono `Blob.text()`. El código de producción funciona en Chrome/Firefox, pero los
tests caen.
**Solución:** Envolver `FileReader.readAsText(blob)` en una promesa. `FileReader` sí
está implementado tanto en jsdom como en todos los navegadores soportados. La
diferencia de API queda contenida en un helper privado.
**Regla:** Para leer Blobs/Files como texto desde código que tiene tests en jsdom, usar
`FileReader.readAsText` en lugar de `Blob.text()` o `Blob.slice().text()`.

### [PHASE-5.2] `Content-Type: application/json` por defecto en axios rompe `multipart/form-data`

**Error:** El cliente axios tenía `headers: { 'Content-Type': 'application/json' }` como
default. Cualquier `apiClient.post('/...', formData)` (receipts, imports) salía con
`Content-Type: application/json` en vez de `multipart/form-data; boundary=...`. El
backend recibía el FormData como un blob JSON malformado y devolvía 422.
**Causa:** axios sólo deduce el header del body cuando NO hay un Content-Type explícito.
Si lo fijas a JSON en `create({ headers })`, ese default gana sobre la inferencia y
nunca emite la cabecera multipart con el boundary correcto.
**Solución:** Quitar el default de `Content-Type` del `axios.create`. axios deduce
`application/json` para plain objects y `multipart/form-data` con boundary para
`FormData`.
**Regla:** No fijes `Content-Type` por defecto en clientes HTTP que vayan a subir
archivos. Deja que la librería lo deduzca por body. Si necesitas forzar JSON en una
ruta concreta, hazlo en esa request, no en el cliente compartido.

### [PHASE-5.2] Reintento tras refresh con `FormData` reutiliza el `boundary` viejo y revienta multipart

**Error:** El interceptor de axios refrescaba el access token tras un 401 y reintentaba
la petición original con `apiClient(originalRequest)`. Para uploads de tickets, el
reintento llegaba al backend pero uvicorn cerraba la conexión sin loguear nada (el
proxy de Next.js veía `socket hang up / ECONNRESET` ~10s después). El primer 401
no aparecía como problema — pero el reintento sí.
**Causa:** El primer envío grabó en `originalRequest.headers` un
`Content-Type: multipart/form-data; boundary=----WebKitFormBoundaryXXX`. axios
reutiliza esa cabecera en el reintento, pero el adapter genera un body NUEVO con
un boundary NUEVO. Resultado: el backend recibe multipart con boundary inconsistente,
`python-multipart` falla al parsear y uvicorn resetea la conexión sin pasar al handler
(de ahí el "missing log entry").
**Solución:** Antes de reintentar, borrar `Content-Type` de `originalRequest.headers`
si el body es `FormData`. Así el adapter (XHR en navegador, form-data en Node) regenera
la cabecera con el boundary correcto.
**Regla:** Cualquier interceptor que reintente peticiones tras refresh de token debe
limpiar `Content-Type` cuando el body es `FormData` (o `Blob` con su propio
boundary/encoding). Reutilizar headers de un envío previo asume que el body es
idempotente; con multipart NO lo es.

### [PHASE-28] Inferir la dirección de una transferencia desde `category.kind` falla cuando un import asigna la categoría equivocada

**Error:** El endpoint `POST /transfers/from-source` derivaba el lado
(ordenante / beneficiaria) de la tx origen mirando `category.kind`. Si la tx
era un abono (entró dinero a BBVA) pero el bank-mapping del import le había
puesto "Transferencias (Gasto)", el sistema asumía "salió de BBVA" y creaba
la contraparte al revés — el saldo de BBVA pintaba un cargo de 3.102€ en
lugar de un abono.
**Causa:** Una sola señal (category.kind) para decidir DOS cosas: signo en
el saldo de la cuenta + lado del par. Cuando la categoría miente sobre la
dirección, ambas decisiones salen mal.
**Solución:** Hacer la dirección **explícita** en la API.
`originating_account_id` + `beneficiary_account_id` viajan en el body; el
backend valida que la tx origen sea una de las dos y FUERZA la categoría
del origen al kind canónico (origen=EXPENSE si es ordenante, INCOME si es
beneficiaria). El modal web expone dos `Select` distintos para que el
usuario lo declare en vez de inferirlo.
**Regla:** Cuando una sola pista (categoría, descripción, signo del
importe) puede mentir y deriva varias decisiones distintas, exponer la
dirección como input explícito de la API y forzar el estado canónico
después; no inferir.

### [PHASE-32] Los bank-mappings aprendidos colapsan la dirección de las transferencias

**Error:** El usuario reportó "BBVA a 0 con ingreso neto". Una
`TRANSFERENCIA RECIBIDA DE Jose` (+5000 €) se persistió en la categoría
`Transferencias` (kind=EXPENSE) en lugar de `Transferencia a favor`
(kind=INCOME), restando 5000 € del saldo en vez de sumarlos. El seed de
reglas (PHASE-31.1) ya distinguía RECIBIDA→income / REALIZADA→expense,
pero un **bank-mapping aprendido** (auto-learn de un preview anterior)
tenía mayor prioridad que las reglas y mandaba el concepto entrante a la
categoría de gasto.
**Causa:** El auto-aprendizaje guarda `concepto_normalizado → category_id`
incluyendo el nombre de la contraparte, y colapsa las DOS direcciones de
una transferencia en una sola categoría. Para conceptos de transferencia,
"qué categoría" y "qué dirección" son ortogonales: la dirección la dice
el texto (RECIBIDA/REALIZADA), no la equivalencia aprendida una vez.
**Solución:** En el pipeline de imports, tras resolver la categoría
(mapping > lookup > regla), si es `is_transfer` se corrige la dirección
con `infer_transfer_kind(concepto + descripción)` y se reasigna a la
categoría hermana del kind correcto (`_load_transfer_categories`). No
crea categorías como efecto colateral: si falta la hermana, deja la
resuelta. Data-fix puntual: repuntados los 3 mapeos "recibida/abono" a la
categoría income + recategorizada la tx afectada (BBVA 0 → 10 000 €).
**Regla:** Para categorías cuyo signo depende de la dirección del
movimiento (transferencias), deriva la dirección SIEMPRE del texto de la
tx en el punto de uso; no confíes en una equivalencia aprendida que la
fija de una vez. Generaliza la lección de PHASE-28 a los bank-mappings.

### [PHASE-26] Cabeceras XLSX en la fila 1 fallan con extractos bancarios reales

**Error:** El parser XLSX asumía cabecera en la fila 1 (`next(iterator)`).
Los XLSX de BBVA / Santander / ING / CaixaBank llevan 5-10 filas iniciales
con logo, periodo, saldos resumen, etc., y la fila de cabecera real
("Fecha | Concepto | Importe | Saldo") aparece más abajo. Resultado: 422
"El XLSX no tiene cabecera" para imports legítimos que el usuario abría
sin problema en Excel.
**Causa:** Suposición rígida sobre el layout del fichero. Los bancos no
exportan tabular limpio; meten un preámbulo cosmético antes.
**Solución:** Escanear hasta 30 filas y usar como cabecera la primera con
≥2 celdas no vacías (un título suelto en una columna no se confunde con
cabecera). Además espejé el smart-parser del PDF en XLSX
(`parse_xlsx_smart`) que clasifica columnas por rol (concepto, importe,
fecha, descripción) usando los mismos hints — así un XLSX con "Concepto"
único se mapea tanto a description como a category_name y dispara el
autocompletado por bank-mapping igual que con PDF.
**Regla:** Para parsers de ficheros producidos por terceros, no asumas el
layout exacto. Heurística "primera fila con ≥N celdas con sentido" >
"fila 1". Si tienes un smart-parser en un formato, espéjalo en el otro
para que el usuario obtenga la misma UX cambie el formato que cambie.

### [PHASE-26] El backend silencia errores de PDF cifrados (mensaje vacío)

**Error:** Importar un PDF cifrado / corrupto devolvía 422 con detail
`"PDF inválido: "` — la parte después del colon estaba vacía. El usuario
no sabía si el problema era su fichero, una contraseña o un bug del
backend.
**Causa:** `pdfplumber.open()` lanza excepciones con `str(e) == ""` para
varios casos de PDFs cifrados o con headers corruptos. El handler hacía
`f"PDF inválido: {e}"` sin fallback.
**Solución:** Si `str(e)` viene vacío, caer al `type(e).__name__` con un
hint accionable: `"PDF inválido: <TipoExcepción> sin mensaje (probablemente
PDF cifrado o corrupto)"`.
**Regla:** Para excepciones de terceros propagadas como detail al usuario,
asume que `str(e)` puede ser vacío. Encadena con `type(e).__name__` y un
hint de qué suele ser. El usuario final no va a leer un stack trace, pero
"PDF cifrado o corrupto" le redirige el debug.

### [PHASE-26] Capital opcional en loan/mortgage permite crear cuentas en estado roto

**Error:** El form de "Nueva cuenta" marcaba "Capital (opcional)" para
todos los tipos liability. Si el usuario rellenaba TIN + plazo + fecha
pero olvidaba Capital, el backend persistía `opening_balance=0`,
`generate_installments_for_account` devolvía `[]` (porque
`principal <= 0`) y la cuenta quedaba sin cuadro de amortización, sin
saldo y sin contribuir al debt-health. Saldo "0,00 €" en el dashboard
incluso teniendo TIN/plazo/fecha bien rellenados.
**Causa:** El backend trataba todos los campos como independientes y
opcionales. Sin Capital se podía persistir, pero el resto del módulo
asume `principal > 0` y fallaba silenciosamente.
**Solución:** Validación en capas. Frontend: label "Capital" (sin
"opcional") cuando type=loan|mortgage + `validate()` rechaza Capital
vacío o ≤ 0 con mensaje claro. Backend: en `create_account`, 400 si
type∈{loan, mortgage} y `opening_balance <= 0` — defensa por si el
cliente se salta la validación. credit_card sí permite 0 porque su
deuda puede vivir en la tx contraparte (flujo convert-to-debt).
**Regla:** Si un módulo asume cierto invariante (ej. `principal > 0`
para que algo se genere), valida ese invariante en la frontera donde
los datos entran, no donde se consumen. Y si tres campos son
"un grupo" (Capital + TIN + plazo + fecha = "datos del préstamo"),
no los trates como independientes: el form debe insistir en el grupo
completo y el backend rechazar combinaciones rotas.

### [PHASE-23.1] No metas dos responsabilidades ortogonales en el mismo enum

**Error:** En PHASE-23 añadí `CategoryKind.TRANSFER` como tercer valor del enum
para señalar "esta categoría es transferencia interna, exclúyela del cashflow".
Pero `kind` ya tenía un trabajo: decidir el SIGNO con que la tx afecta al saldo
de la cuenta (asset+expense → -amount, asset+income → +amount). Las txs con
kind=TRANSFER cayeron al `else_=amount` del case statement de balance, inflando
el saldo BBVA del usuario en +10.120€.
**Causa:** Acoplar dos conceptos ortogonales en una misma columna. "Tipo de
movimiento" (signo) y "es transferencia interna" (exclusión del cashflow) son
independientes: una transferencia puede ser entrada (income) Y excluirse, o
salida (expense) Y excluirse.
**Solución:** Separar en dos columnas. `kind` sigue siendo `income | expense`
(determina signo del balance). Nueva columna `is_transfer` booleana en
`categories` (determina exclusión del cashflow). Migración restaura el kind
original (inferencia por nombre) + marca `is_transfer=true`.
**Regla:** Antes de añadir un valor a un enum, pregunta si el nuevo caso
comparte TODAS las responsabilidades del enum existente. Si introduce una
ortogonalidad nueva, es una columna separada, no un valor más. Aplica también
a `status` enums que mezclan "estado del workflow" con "es tipo X".

### [PHASE-5.2] El dev server de Next.js corta los rewrites a 30s — incompatible con IA local

**Error:** Subir un ticket en dev devolvía 500 con `socket hang up / ECONNRESET` exactamente
a los 30s, sin que la petición llegara a aparecer en el log de uvicorn. Ollama estaba
respondiendo correctamente pero la inferencia con `qwen2.5vl:7b` en CPU tarda 60–120s.
**Causa:** Next.js dev server cierra las conexiones de los rewrites a los 30s por
defecto. Cuando el upstream (uvicorn) sigue procesando pasados esos 30s, el dev server
resetea la conexión. uvicorn ve `ConnectionResetError` mientras espera a Ollama y aborta
el handler antes de loguear la línea de access.
**Solución:** Subir `experimental.proxyTimeout` en `next.config.mjs` a un valor que cubra
la inferencia local más holgura (300_000 = 5 min). Sólo afecta al dev server; en
producción detrás de un reverse proxy (Caddy/Traefik/Nginx) el timeout se configura ahí.
**Regla:** Cualquier endpoint que pase por el rewrite de Next.js dev y pueda tardar

> 30s (IA local, exports grandes, jobs síncronos) requiere subir `experimental.proxyTimeout`.
> Si una petición "muere" exactamente a los 30s sin trazas en uvicorn, el sospechoso es
> casi siempre el dev server.

### [PHASE-34] Cuando parcheas la misma raíz ≥2 veces, mueve la fuente de verdad

**Error:** PHASE-23.1, 28 y 32 arreglaron tres veces el MISMO defecto —la
dirección/clasificación del dinero se derivaba de la **categoría**, así que un
solo fallo de categoría (regla, bank-mapping, import) rompía saldo y cashflow
en silencio—. Cada fase añadió otro guardarraíl (separar `is_transfer` del
`kind`, dirección explícita en el modal, corrección de dirección en el import)
sin tocar la raíz.
**Causa:** Acoplar el dinero (signo + gasto/ingreso/transferencia) a una
columna **descriptiva** (la categoría) que cualquier mecanismo puede
equivocar. Mientras la categoría fuera la verdad del dinero, el bug era
estructural y reaparecía por otra vía.
**Solución:** Mover la verdad a la transacción con `transactions.flow`
(`IN|OUT|TRANSFER_*`). Saldo = `flow`+`account.nature`; cashflow = Σ por
`flow`. La categoría pasa a ser 100 % descriptiva. ADR-0004.
**Regla:** Si arreglas el mismo TIPO de bug en sitios distintos dos o más
veces, deja de parchear síntomas: el bug es estructural. Cambia DÓNDE vive la
fuente de verdad (o qué columna la define), no añadas otro guardarraíl sobre
la fuente equivocada.

### [PHASE-34] El backfill de una migración debe REPRODUCIR los datos (bugs incluidos), no corregirlos

**Error:** Tentación de "aprovechar" la migración que añade `flow` para
corregir de paso las filas rotas (transferencias-como-gasto, `ADEUDO`
contado como gasto).
**Causa:** Si el backfill corrige Y la query nueva cambia de fuente a la vez,
no hay forma de probar que la nueva matemática es **equivalente** a la vieja:
un test verde podría estar tapando un cambio de query con un cambio de datos.
**Solución:** El backfill (34.1) derivó `flow` de la interpretación actual por
categoría **tal cual**, reproduciendo los bugs. Eso permitió un golden test de
EQUIVALENCIA viejo↔nuevo en 34.2. La corrección de datos llega después, por
**reimportación** con el pipeline nuevo (el signo del extracto manda) — no en
la migración. Auditoría posterior confirmó que reimportar dejó los dos
doble-conteos ya resueltos sin tocar la BD a mano.
**Regla:** Una migración que cambia la fuente de verdad de un cálculo backfilea
para ser **idéntica** al comportamiento previo; la corrección de datos es un
paso separado y auditado (reimport o data-fix), nunca un efecto colateral de
la migración. Así el test prueba la query, no el parche de datos.

### [PHASE-37] Un dato IMPLÍCITO tiene su fuente de verdad en el modelo, no en transacciones — y no se agrega aditivamente

**Error:** El módulo de deuda calculaba "intereses pagados" sumando
transacciones en categorías `DEBT_INTEREST`. Esas categorías están
estructuralmente VACÍAS: el banco no desglosa el interés como un movimiento
aparte, va dentro de la cuota. Resultado: "Intereses YTD 0,00 €", card "Pagos
a deuda" vacía, barras de interés a 0 y trend con histórico=0 vs proyección≠0,
pese a tener TIN/TAE configurados.
**Causa:** Buscar un dato donde no se registra. El interés es IMPLÍCITO — vive
en el cuadro de amortización (`liability_installments.interest`), no en el
ledger de transacciones.
**Solución:** Leer el interés/capital del CUADRO, con **MUX por pasivo**
(schedule XOR transacciones, nunca la suma): una deuda con cuadro aporta desde
el cuadro; una sin cuadro, desde sus transacciones. Sumar ambos (aditivo)
reintroduce el doble conteo "dos fuentes de verdad" de [PHASE-34].
**Regla:** Si un dato es implícito (no se registra como movimiento propio), su
fuente de verdad es el modelo estructural que lo contiene (el cuadro, el plan),
no las transacciones. Al combinar dos fuentes para la misma entidad, elige una
por entidad (MUX), no las sumes.

### [PHASE-37] Un dedup por la clave equivocada over- y under-excluye a la vez

**Error:** En el month-outlook, para no doblar un pago de cuota que también
fuese gasto fijo, se excluían los gastos fijos cuyo `account_id` fuese un
pasivo con cuadro. La revisión adversarial mostró que esa clave es doblemente
mala: (a) NO captura el doble conteo real —un pago de préstamo modelado como
gasto fijo se cobra desde el BANCO, no desde el pasivo, así que su `account_id`
no es el pasivo— y (b) SÍ excluye cargos legítimos distintos —una suscripción
en una tarjeta financiada comparte `account_id` con el pasivo pero no es la
cuota.
**Causa:** La clave de dedup (`account_id`) no modelaba la relación buscada
(¿este cargo ES la cuota?). Una clave plausible pero incorrecta.
**Solución:** Eliminar el MUX por `account_id`. El solape real (un pago
modelado como cuota Y como gasto fijo) es raro y no se captura por cuenta;
mejor no dedup que uno que corrompe en dos direcciones.
**Regla:** Antes de dedup por una clave, comprueba con un caso concreto que la
clave capture la relación real en AMBOS sentidos. Una revisión adversarial con
escenarios concretos lo destapa; un test "verde" con el caso feliz, no.

### [PHASE-37] El autoaprendizaje no debe fijar categoría para un concepto de dirección ambigua

**Error:** Un bank-mapping aprendido `'bizum' → Bizum recibido` (ingreso)
etiquetaba como ingreso los BIZUM SALIENTES (flow=OUT): el autoaprendizaje fija
UNA categoría para un concepto que aparece con cargo y con abono. Los saldos
iban bien (por `flow`, ADR-0004), pero la etiqueta mentía y el desglose
mostraba un ingreso como gasto.
**Causa:** Generalización de [PHASE-32] al paso de APRENDIZAJE: una
equivalencia aprendida colapsa la dirección de un concepto que la tiene variable.
**Solución:** Al aprender, saltar los conceptos de dirección ambigua (que
aparecen con ambos signos en el lote). El override del usuario se aplica a esa
importación, pero no se persiste como equivalencia.
**Regla:** No fijes una equivalencia aprendida `concepto → categoría` para un
concepto que aparece con signos opuestos; su dirección la decide el signo del
extracto en el punto de uso, no una equivalencia grabada una vez.

### [PHASE-38] La cuota de una compra a plazos SÍ es gasto de caja; la liquidación de tarjeta NO — y ambas comparten prefijo

**Error:** `classify_import_flow` marcaba TODO lo que matchease "operación
financiada" como movimiento interno (`TRANSFER_OUT`, fuera del cashflow), igual
que el ADEUDO/liquidación de tarjeta. Efecto: la cuota mensual de una compra a
plazos ("OPERACIÓN FINANCIADA CON TARJETA") salía blanca/neutra y **el gasto
financiado no aparecía en el neto del mes por ningún sitio** — ni la compra
original (modelada como creación de deuda, `TRANSFER_*`) ni la cuota. El usuario
veía un movimiento "sin gasto ni ingreso" que en su cabeza era gasto real.
**Causa:** Meter en un mismo cubo ("movimiento interno") tres conceptos que
comparten el prefijo "operación financiada" pero son distintos: (a) la CREACIÓN
de la deuda ("operación financiada" a secas) → neutra; (b) la LIQUIDACIÓN de
tarjeta ("adeudo mensual de tarjeta") → neutra (las compras sueltas ya son
gasto); (c) la CUOTA de una compra a plazos ("...con tarjeta") → gasto de caja
real, porque su compra original no cuenta como gasto en ninguna otra parte.
Contar (b) como gasto doblaría; NO contar (c) esconde el gasto.
**Solución:** Carve-out en `classify_import_flow`: `is_card_financed_op(text)`
(exige "operaci"+"financiada"+"tarjeta"; excluye el ADEUDO y la creación a
secas) fuerza `flow=OUT`, ganando sobre `is_internal_movement_text` y sobre un
`category_is_transfer` mal puesto. Es la MISMA definición que usa la
reconciliación → clasificador y matcher no divergen. La deuda la sigue
descontando el cuadro vía reconciliación (independiente del `flow`), así que
`OUT` no rompe saldo ni patrimonio (`is_outflow()` cubre `OUT` y `TRANSFER_OUT`
igual para un ASSET) y el módulo de deuda no dobla el interés (excluye la
categoría vinculada al pasivo con cuadro). Es una vista de CAJA deliberada: el
capital de la cuota cuenta como gasto del mes (decisión del usuario).
**Regla:** Antes de meter varios conceptos bajo una misma etiqueta por compartir
un prefijo de texto, comprueba caso a caso si comparten el MISMO tratamiento de
dinero. "Pago de deuda" no es un tratamiento único: liquidar tarjeta (gasto ya
contado en las compras) ≠ amortizar una compra a plazos (gasto de caja que no
está en ningún otro lado). Y cuando dos módulos deben coincidir en "qué es X"
(aquí clasificador de `flow` y matcher de reconciliación), comparte UNA sola
definición del predicado, no dos que puedan divergir.

### [PHASE-41] "Dos cosas que parecen duplicadas": léelas antes de fusionar; un refactor que cambia una fuente de verdad no debe mover los números del core

**Error:** El análisis marcó los dos motores de recurrencia
(`fixed_expenses/detector.py` y `analytics/recurrence.py`) como duplicados y
candidatos a fusionar por una primitiva de "estimar cadencia" compartida.
**Causa:** Se juzgó por parecido superficial ("ambos detectan recurrencia") sin
leer los dos enteros. En realidad no comparten ni una línea ni la primitiva
asumida: `recurrence.py` NO calcula intervalos (agrupa por CATEGORÍA y mide
estabilidad de importe mensual); el detector agrupa por comercio+importe y mide
regularidad temporal. Sus outputs alimentan cosas distintas (uno la tasa de
ahorro/runway de Análisis, otro las sugerencias de gastos fijos).
**Solución:** Cancelar la fusión. Una revisión adversarial de scoping (leer
ambos + sus consumidores) lo destapó ANTES de tocar código.
**Regla:** Antes de "deduplicar" dos cosas que parecen iguales, LÉELAS enteras y
mapea qué número/consumidor depende de cada una — el mismo nombre-concepto no
implica compartir código ni propósito. Y un refactor que cambia la FUENTE de un
cálculo del core (aquí structural-vs-puntual) debe demostrar equivalencia
numérica o no hacerse (generaliza PHASE-34/37).

### [PHASE-41] No clasifiques código para borrar por su módulo/nombre — mapea los consumidores reales primero

**Error:** El plan inicial agrupó `POST /transfers/link` con la "maquinaria de
emparejado heurístico" (candidates/match/suspects/mark) para retirarla al quitar
la pestaña de transferencias.
**Causa:** `link` vive en el módulo transfers junto al matcher, así que por
proximidad parecía parte de lo mismo. Pero lo usa el **asistente de pago de
deuda** (web + móvil) para crear el par principal, y `unlink` lo usa el
"deshacer" desde la lista de transacciones. Borrarlos habría roto los pagos de
deuda.
**Solución:** El scoping (grep de consumidores por endpoint/hook con cita
`file:line`) lo detectó antes de borrar: `link`/`unlink` son load-bearing y se
conservaron; sólo se retiró `list/candidates/match/suspects/mark`.
**Regla:** Antes de borrar un símbolo/endpoint "porque pertenece al módulo que
retiro", grepea TODOS sus consumidores (otras apps, móvil, wizards, tests). La
pertenencia a un módulo no implica que el símbolo sea exclusivo de la feature
que retiras.

### [PHASE-43] `tsc` y ESLint NO ven el código muerto: son de ámbito fichero, y un `export` está "usado" por definición

**Error:** Tres rediseños consecutivos (PHASE-29 → 30 → 37) sustituyeron
componentes y dejaron los originales. Se acumularon **2.318 LoC muertas en 8
ficheros** (incl. `position-hero.tsx`, 855 LoC con una copia del gauge de tasa
de esfuerzo) sin que `lint` ni `typecheck` dijeran nada — teniendo el repo
`strict`, `noUnusedLocals`, `noUnusedParameters` y `no-explicit-any` como error.
**Causa:** `noUnusedLocals` y `@typescript-eslint/no-unused-vars` son de ámbito
**fichero**: preguntan "¿se usa este símbolo AQUÍ?". Si lleva `export`, la
respuesta es sí por definición — el compilador no puede saber que ningún módulo
lo importa (podrías ser una librería con consumidores externos). El rigor estaba
puesto, pero en un eje que no mide esto: **"¿alguien usa esto?" no es una
pregunta de tipos, es de alcanzabilidad de proyecto.**
**Solución:** `knip` (parte de los entrypoints y calcula alcanzabilidad global)
cableado a `make verify` vía `pnpm knip`. Encontró los 5 que un barrido manual
ya había visto **y 3 más en móvil que no**.
**Regla:** Un linter no sustituye a un detector de alcanzabilidad; son ejes
ortogonales. Si tu `verify` sólo corre lint + typecheck + tests, el código
muerto crece sin límite y en silencio. Corolario: la deuda que ninguna
herramienta mide es la que nadie ve, así que **antes de asumir que algo "se
habría detectado", comprueba qué eje mide cada herramienta que tienes**.

### [PHASE-43] Un detector de alcanzabilidad da por muerto todo lo que se resuelve por CONVENCIÓN — verifica el mecanismo antes de borrar

**Error:** El primer informe de knip (sin configurar) señaló como muerto
`packages/store/src/storage.native.ts`, los `.test.tsx` de móvil con su
`jest.config.js`, y las dependencias `react-dom` / `react-native-web` /
`@react-native-async-storage/async-storage`. Borrar cualquiera habría roto
móvil en silencio.
**Causa:** knip traza **imports**. Todo lo que se enlaza por otra vía le es
invisible: Metro resuelve `storage.native.ts` por **extensión de plataforma**
(nadie lo importa; `currency.ts` importa `./storage` y Metro sustituye el
`.native` en iOS/Android), jest recoge los tests por `testMatch`, y Expo exige
`react-dom`/`react-native-web` en runtime para su target web. La ironía: el
propio `storage.native.ts` documenta su mecanismo en el docstring — la
herramienta no lee prosa.
**Solución:** Configurar los entrypoints reales (Expo Router, `testMatch`) y
documentar **cada** exclusión con su motivo en `knip.config.ts` (por eso es
`.ts` y no `.json`: JSON no admite comentarios y una exclusión sin motivo la
borra alguien dentro de seis meses). Cada hallazgo se verificó a mano antes de
borrar; 6 de los 14 iniciales eran falsos positivos.
**Regla:** Un hallazgo de código muerto es una **hipótesis, no un veredicto**.
Antes de borrar, identifica por qué mecanismo vive el fichero: import, convención
de ruta (Next/Expo Router), extensión de plataforma (`.native.ts`, `.ios.tsx`),
`testMatch`, o runtime del bundler. Generaliza la lección de PHASE-41: no
clasifiques código para borrar sin mapear su consumidor **real**, aunque quien
lo señale sea una herramienta y no una corazonada.

### [PHASE-43] Una premisa escrita en un comentario caduca en silencio — y ninguna herramienta lo detecta

**Error:** `position-hero.tsx` no era un olvido: se mantenía **a propósito**,
con su motivo escrito — _"Las cards legacy (`BalancesCard`, `DebtHealthCard`) se
mantienen intactas porque siguen siendo válidas en `/dashboard`"_. Era cierto en
PHASE-29.5. Dejó de serlo en PHASE-37.2, cuando el rediseño se llevó
`/dashboard` por delante. Nadie mintió: la premisa caducó sola, y con ella 1.632
LoC pasaron de "decisión justificada" a "código muerto que parece vivo".
**Causa:** Un comentario fija una verdad en el tiempo, pero no se recalcula. Es
el mismo fenómeno que el README declarando PHASE-39 "pendiente de commit" tres
fases después de commitearla, o el análisis de 2026-07-17 citando un saldo que
la auditoría ya había retractado: **texto que era correcto y el mundo se movió
debajo**.
**Regla:** Cuando justifiques por escrito conservar algo ("lo mantengo porque X
lo usa"), estás creando una dependencia que ninguna herramienta verifica. Al
retirar X, busca los comentarios que lo nombran (`grep`). Y si la premisa es
"alguien lo usa", mejor que un comentario: que lo diga el detector de
alcanzabilidad, que sí se recalcula en cada `verify`.

### [AUDIT-2026-08] Una media mensual mezclada con un importe mensual REAL exige que la ventana no tenga meses sin observar

**Error:** La tasa de esfuerzo ampliada de Deuda promediaba el ingreso y la
cuota sobre **todos los meses cerrados del rango**, incluidos los anteriores a
que el usuario tuviera datos. Con `range=year` el 1 de agosto y datos desde
febrero, enero entraba en la ventana: ingreso medio 12.000/**7** = 1.714,29 en
vez de 12.000/**6** = 2.000. El ratio ampliado pasaba de 0,350 a 0,367 y cruzaba
el 35 % del Banco de España — **sobreendeudamiento inventado por un mes vacío**.
**Causa:** mezclar dos cosas de naturaleza distinta en la misma suma.
`avg_monthly_debt_payment` y `monthly_income` son **medias** sobre `n` meses;
`non_debt_fixed` es un **importe mensual real** que no se divide por nada. En el
ratio ESTRICTO la distorsión se cancela sola (numerador y denominador se dividen
por el mismo `n`, así que `n` desaparece) y por eso pasó desapercibida; en el
AMPLIADO, no. Lo llamativo: el autor **ya había razonado esto** —excluyó el mes
EN CURSO precisamente para no «romper la coherencia con el término de gastos
fijos»— pero sólo cerró un extremo de la ventana.
**Solución:** acotar la ventana también por la izquierda, al primer mes con
ingreso observado (`first_income_month`), y sumar el ingreso desde ahí y no desde
`range_start` — si se acota `n` pero no la suma, el error se invierte y la media
sale inflada.
**Regla:** cuando una fórmula sume una **media** y un **importe mensual real**,
la ventana de la media tiene que contener sólo meses REALMENTE observados; si no,
el término que no se diluye domina. Y cuidado con la señal: que el ratio
«hermano» salga bien no prueba nada — un `n` incorrecto se cancela en un cociente
de dos medias y sólo asoma cuando algo entra sin dividir. Corolario de test: el
que destapó esto **fallaba de agosto a diciembre y pasaba de febrero a julio**,
porque sembraba «6 meses hacia atrás» y consultaba un rango de año natural. Un
test cuyo resultado depende del mes en que se ejecute es una bomba de relojería:
la regresión que lo sustituye usa un rango **fijo y pasado**.

### [PHASE-44.10] «Nunca dos pytest a la vez» tiene un vector nuevo: los agentes que tú mismo lanzas

**Error:** Lancé la suite completa del backend en segundo plano y, mientras
corría, un workflow multi-agente que había arrancado antes seguía vivo. Dos de
sus agentes ejecutaron `pytest` para verificar sus hallazgos. Resultado: **406
failed, 902 errors** con `sqlalchemy.exc.ProgrammingError` — todos FALSOS. La
misma suite, relanzada sola, pasa entera.
**Causa:** los tests del backend comparten UNA base (`crisol_test`) y el fixture
recrea el schema; dos ejecuciones simultáneas se lo tiran mutuamente. La regla ya
estaba escrita, pero pensada para el caso obvio —dos terminales del humano— y no
para éste: **un subagente que ejecuta comandos también es un segundo pytest**, y
además invisible, porque corre en segundo plano y no aparece en la consola.
Agravante: el prompt del workflow decía «NO edites código: esto es análisis y
diseño», lo que impide escribir pero **no impide ejecutar**.
**Solución:** parar el workflow y relanzar la suite sola. Diagnóstico rápido
porque la firma es inconfundible: cientos de errores de SQLAlchemy en tests que
no se han tocado, incluidos módulos ajenos al cambio (`test_webauthn`).
**Regla:** antes de lanzar la suite completa, comprueba que **no hay ningún
agente ni tarea en segundo plano viva** que pueda tocar la BD. Y si delegas
verificación a subagentes, prohíbeles explícitamente ejecutar `pytest` (o dales
una base propia): «no edites código» no cubre «no ejecutes tests». Señal de
diagnóstico: si fallan tests de módulos que tu cambio no toca, sospecha del
entorno antes que del código — es la misma familia que el zoom del navegador y
que el intérprete equivocado.

### [PHASE-44.9] A la SÉPTIMA vez que una premisa caduca, la respuesta no es otra lección: es un detector — y la clave es qué documento tiene derecho a envejecer

**Error:** `backlog.md` —el fichero que el índice declara como sitio de la deuda
técnica— llevaba días afirmando cosas que habían dejado de ser ciertas: que el
módulo no tenía tests de componente FE (los tenía desde el día anterior), que el
informe era «veredicto + tablas de métricas», y citaba `BE 1042` y un head de
Alembic viejo.
**Causa:** la MISMA raíz que ya está escrita dos veces en este fichero
([PHASE-43] «una premisa escrita caduca en silencio») y que ya había mordido
cinco veces más: `position-hero.tsx`, el README declarando PHASE-39 pendiente,
un análisis citando un saldo retractado, las etiquetas F5/F6/D8 escritas a mano,
y el docstring de `version.py` afirmando un gate inexistente. Siete en total.
**Solución:** aplicar la regla que el propio fichero ya tiene ([PHASE-34]: «si
parcheas la misma raíz ≥2 veces, mueve la fuente de verdad») en vez de escribir
la lección por séptima vez. `scripts/check_docs.py`, cableado a `make verify`,
a `pnpm docs:check` y a CI, comprueba lo que SÍ es comprobable: que los enlaces
relativos resuelvan, que las revisiones de Alembic citadas existan, que quien
declare un head nombre el head real, y que los documentos **vivos** no lleven
números volátiles.
**Regla:** distingue **documento vivo** de **foto fechada**. Una phase doc es
historia: un recuento de tests o un head de Alembic allí envejece bien, porque su
valor es decir cómo estaban las cosas ENTONCES. `backlog.md`, `HANDOFF.md` y las
tablas de estado describen el AHORA: un número que cambia cada fase es
podredumbre garantizada, porque nadie vuelve a actualizarlo. Y cuando construyas
el detector, **acota su alcance a los documentos vivos**: marcar como error que
la phase doc de 44.1 diga que el head era `f9v25x7us9w8v4` genera ruido, y un
verificador ruidoso se ignora — que es la forma más cara de no tener verificador.
Corolario: prueba que el detector DETECTA (rompe un documento a propósito y
comprueba que sale exit 1); un gate que nunca falla no es un gate, es lo que le
pasaba al golden test de `ENGINE_VERSION` durante tres fases.

### [PHASE-43] En un backend declarativo (FastAPI/Pydantic/SQLAlchemy) un detector de llamadas da 95% de ruido — filtra por la CAPA, no por la confianza

**Error:** Correr `vulture app/` en el backend devolvió 273 hallazgos. Tomarlos
al pie de la letra habría borrado TODOS los endpoints (`*_endpoint`, los
registra un decorador, no una llamada), los campos de cada schema (los usa la
serialización de Pydantic), las columnas ORM (las usa SQLAlchemy) y hasta el
guard anti-bomba `Image.MAX_IMAGE_PIXELS = 50_000_000` (una asignación sobre un
global de Pillow).
**Causa:** vulture rastrea el grafo de llamadas de Python. Un framework
declarativo invoca tu código por reflexión/registro/decorador, no con una
llamada textual — así que TODO lo que el framework consume le es invisible. La
confianza que reporta (60/100) no distingue esto: un endpoint muerto y uno vivo
puntúan igual.
**Solución:** No subir el umbral de confianza — **excluir las capas
declarativas**: `--exclude "*/schemas.py,*/models.py,*/config.py"`,
`--ignore-decorators "@router.*,@field_validator,@app.*"`,
`--ignore-names "*_endpoint,model_config,cls"`. De 273 → 32 candidatos, cada uno
verificado a mano contando consumidores en `app/` **y** `tests/` **y**
`alembic/versions/` (vulture sólo mira `app/`). Falsos positivos que sobrevivían
al filtro: `load_snapshot` (la llama una migración Alembic), `count_pdf_pages`
(fallback de visión).
**Regla:** Antes de creer a un detector de código muerto, pregunta qué NO puede
ver por el paradigma del framework: en FastAPI son los endpoints; en
Pydantic/SQLAlchemy, todo lo declarativo (schemas, models, validators); en
Alembic, las migraciones (fuera de `app/`). Excluye esas capas de la herramienta
en vez de leerlas una a una, y verifica el resto contando consumidores en TODOS
los árboles (app + tests + migraciones), no sólo donde mira la herramienta.
Generaliza la lección de knip (PHASE-43): un hallazgo es una hipótesis; el
mecanismo invisible aquí es el registro por framework, allí la resolución por
convención de ruta.

### [PHASE-43] Una función "muerta" que se autodocumenta como "fuente ÚNICA de verdad" no es basura: es un invariante roto — repórtala, no la borres

**Error (evitado):** El barrido señaló 3 funciones sin llamadas que, leídas,
resultaron NO ser basura sino síntomas:

- `debt/service.resolve_period_end` — su docstring dice _"PHASE-30.8 — Fuente
  ÚNICA de verdad del as-of, compartida entre Capa 1 y Capa 2 para que los tres
  endpoints coincidan"_, y no la llama nadie. Verificado: `compute_debt_health`
  ni siquiera toma período (es snapshot de hoy) y `compute_debt_history` usa
  `months_back/ahead`. **El objetivo de diseño que declara la fase no está
  cableado.**
- `accounts/repository.get_net_savings_movement_for_account` — el doc de PHASE-32
  (HIGH#1) dice _"el ahorro neto de la principal es ahora display-only (`get_net_savings…`)"_.
  La función existe, `is_default` se valida, pero `get_balances` no la llama:
  **la feature "saldo de la cuenta principal = ahorro neto" está regresada.**
- Además, `mypy app/` fallaba en `main` con 5 errores de `rowcount` pese a que
  `lessons.md` (PHASE-38) declara que se añadió `type: ignore[attr-defined]` — el
  ignore nunca se commiteó. El README declaraba "mypy verde".
  **Causa:** Borrar código muerto es seguro sólo si es basura. Cuando el código
  huérfano es la IMPLEMENTACIÓN de un comportamiento documentado, su orfandad es
  la prueba de que el comportamiento se perdió; borrarlo cementa la regresión y
  destruye la evidencia.
  **Regla:** Al limpiar código muerto, LEE cada símbolo antes de borrarlo. Si su
  nombre/docstring afirma ser fuente de verdad, invariante, o la implementación de
  una feature con doc de fase, no es basura: es un bug de "feature construida y
  descableada". Sepáralo del borrado y repórtalo. La misma señal (0 llamadas)
  significa "basura" o "regresión" según lo que el símbolo DIGA que hace —
  distínguelo. (Los 3 se dejaron en el código y se reportaron; el `type: ignore`
  sí se aplicó porque su fix es el documentado.)

### [PHASE-44.1] El padre de una migración se elige por el HEAD real del DAG, no por el filename ordenado alfabéticamente

**Error:** Al crear la migración de cimientos del módulo Inversión puse
`down_revision = "z3p58r0on2q1p7"` porque era el último fichero que devolvía
`ls alembic/versions | tail`. No era el head: `z3p58r0on2q1p7` ya tenía un hijo
(`a4q70s2pn4r3q9`), así que parenté a un nodo intermedio y creé una SEGUNDA
cabeza. `alembic heads` pasó a mostrar dos heads → `alembic upgrade` habría
fallado con "multiple heads" y CI en rojo.
**Causa:** Los revision IDs de Alembic son cadenas aleatorias, NO secuenciales.
Ordenar los ficheros por nombre no refleja el orden del DAG. El head real era
`f9v25x7us9w8v4` (PHASE-43.2), cuyo fichero empieza por `f9` y quedaba MÁS
ARRIBA en el listado alfabético — invisible a `tail`.
**Solución:** Preguntar al propio Alembic. `alembic heads` da el/los head(s)
reales y `alembic history` reconstruye el DAG. Repunté `down_revision` a
`f9v25x7us9w8v4` y confirmé que `alembic heads` volvía a devolver UNA sola línea.
**Regla:** Antes de fijar `down_revision`, ejecuta `alembic heads` y usa ESE
valor; nunca deduzcas el head del nombre del fichero. Tras crear la migración,
`alembic heads` debe devolver exactamente un head; si devuelve dos, has
ramificado. Y verifica parity con `alembic check` sobre una BD a head (debe
decir "No new upgrade operations detected") — es el gate que corre CI.

### [PHASE-44.6] La forma de salida de una librería se PRUEBA, no se deduce leyendo su código — sobre todo si el desajuste falla en silencio

**Error:** Al escribir el adapter de `edgartools` deduje su contrato leyendo el
código fuente: `FinancialFact` tiene `taxonomy` y `concept` por separado, luego
la clave se compone `qualify(taxonomy, concept)`. Falso. La librería devuelve el
concepto **ya cualificado** (`'us-gaap:Assets'`) Y `taxonomy` aparte, así que la
composición daba `'us-gaap:us-gaap:Assets'`. Segundo fallo del mismo tipo: filtré
los ratios por acción con la unidad que escribe la SEC (`USD/shares`), pero la
librería la reetiqueta como `USD per share`, así que el filtro no cazaba nada.
**Causa:** Leer la fuente enseña qué campos EXISTEN, no qué valores CONTIENEN.
Los dos campos existían y sus nombres eran los esperados; lo que no era el
esperado era el formato del contenido.
**Solución:** Un probe de 40 líneas —payload sintético con la forma real de la
SEC → parser de la librería → imprimir cada campo con su `repr` y su tipo— destapó
las dos en un minuto. Después, un test que recorre el pipeline COMPLETO pasando
por el parser real, para que un cambio de contrato de la librería falle en CI y
no en producción.
**Regla:** Antes de escribir el código que consume una librería en una frontera
de datos, ejecútala una vez con un caso mínimo e imprime lo que devuelve. Es
especialmente crítico cuando el desajuste **no lanza excepción**: aquí no habría
saltado ningún error, simplemente NINGUNA partida habría encontrado su concepto y
la empresa entera habría salido en blanco — un fallo que se lee como "esta
empresa no publica datos", no como un bug. Y no bases un filtro en literales que
escribe un tercero (unidades, etiquetas): detecta por forma, que sobrevive a que
cambien la cadena.

### [PHASE-44.6] Verificar con el intérprete equivocado da un verde que no vale

**Error:** Corrí `pytest`, `mypy`, `ruff` y `black` con el `python` del PATH
(global, 3.13) durante toda la sesión. El proyecto tiene su venv en
`backend/.venv` con **Python 3.12 — el mismo que CI** y con los pines exactos de
`constraints.txt`. El verde de 984 tests era real, pero no era el verde que
importa. Peor: estuve a punto de regenerar `constraints.txt` con un `pip freeze`
del entorno global, que habría metido ~150 paquetes ajenos (torch, whisper,
celery) y **retrocedido** los pines de fastapi, SQLAlchemy y pydantic.
**Causa:** `python` en el PATH resolvía a un intérprete global que casualmente
tenía instaladas las deps del backend, así que todo "funcionaba" y nada avisaba.
**Solución:** Repetir la verificación con `.venv/Scripts/python.exe` y regenerar
el lock desde ahí; el diff quedó en adiciones puras (la rama de dependencias de
`edgartools`) sin mover un solo pin existente.
**Regla:** Antes de dar por verificada una fase, comprueba QUÉ intérprete estás
usando (`python -c "import sys; print(sys.prefix)"`) y que su versión coincide
con la de CI. Y un fichero generado por `pip freeze` se regenera SIEMPRE desde el
venv del proyecto: si el diff toca versiones que no has cambiado, el entorno está
mal, no el fichero.

### [PHASE-44.6] `getattr(obj, "metodo")` sin llamarlo es SIEMPRE truthy — un método leído como atributo apaga una feature en silencio

**Error:** El adapter decidía si una empresa es financiera con
`if getattr(company, "is_financial_institution", False): is_financial = True`.
En `edgartools`, `is_financial_institution` es un **método**, no un atributo, así
que `getattr` devolvía el objeto método sin llamar —un bound method es siempre
truthy— y **TODA** empresa salía `financiera=True`: McDonald's (SIC 5812,
restauración) y Johnson & Johnson (SIC 2834, farmacia) incluidas. Efecto: la capa
forense entera (Beneish M-Score, Altman Z, Piotroski F-Score) se apagaba para
todas ellas, porque los forenses no aplican a bancos.
**Causa:** Deducir el contrato de la librería leyendo su código (existe un
`is_financial_institution` → lo trato como flag) en vez de ejecutarlo y mirar qué
devuelve. Misma raíz que la lección de arriba sobre la forma de salida de la
librería, con un modo de fallo específico de Python: acceder a un método sin
paréntesis no es un error, es una verdad constante.
**Descubierto por:** el smoke EN VIVO contra empresas reales. Los tests con
hechos sintéticos no lo cazaban porque construían el `SecurityIdentity` a mano,
sin pasar por `resolve()` ni por el objeto `Company` de la librería. Los tests
sintéticos prueban el anclaje y el mapeo; sólo tocar la librería de verdad
destapa cómo se leen SUS objetos.
**Solución:** Llamar al método con guarda `callable` (sobrevive a que la librería
lo convierta en propiedad): `flag = getattr(company, "is_financial_institution",
False); flag = flag() if callable(flag) else flag`. Y una regresión con un
`Company` FALSO cuyo `is_financial_institution` es un método —la forma real—, que
es justo lo que ningún test tocaba.
**Regla:** Cuando leas un atributo de un objeto de terceros para usarlo como
bool, confirma si es dato o método antes de fiarte de su truthiness: un `getattr`
sobre un método siempre pasa el `if`. Y si un flag GOBIERNA qué se calcula
(aquí, si corren los forenses), su lectura tiene que estar cubierta por un test
que use la forma REAL del objeto, no un stub construido a mano que se salta la
frontera. Generaliza [PHASE-44.6] "la forma de salida se prueba, no se deduce" al
acceso a métodos, no sólo al contenido de los campos.

### [ui-diagnosis] Un "cambio visual regresó" es zoom del navegador hasta que un `git diff` demuestre lo contrario

**Error:** El usuario reportó que las cards de la web tenían "demasiado aire /
márgenes" y lo atribuyó al desarrollo del módulo de Inversión. Se dedicó una
sesión larga a arqueología de git (reflog, ramas, commits colgantes) y a editar
el padding del `Card` y de 10 componentes de Deuda —con reverts incluidos—
antes de descubrir que la causa era el **navegador a >100% de zoom**. Con
`Ctrl+0` volvió a verse idéntico a la referencia.
**Causa:** Asumir que un síntoma visual equivale a un cambio de código sin
descartar primero el entorno. Agravado por comparar capturas de **páginas
distintas** (Análisis, densa, vs Deuda, con cards hero aireadas por diseño) como
si fueran el mismo layout que "se ensanchó".
**Solución:** `git diff <commit-de-referencia> HEAD -- apps/web packages/ui` salió
**0 líneas** — el frontend no había cambiado desde el 19-jul; todo lo posterior
(20–22 jul) era backend de Inversión. Eso probó que no era código; el reset de
zoom del usuario lo confirmó.
**Regla:** Ante un "esto se ve distinto/peor" sin evidencia de commit, PRIMERO
descarta zoom (`Ctrl+0`) y prueba con `git diff <ref> HEAD -- <área>`; si sale
vacío, es entorno, no código — no toques nada. No compares capturas de páginas
distintas como prueba de regresión. Los estilos en px escalan con el zoom, así
que las proporciones se mantienen: el zoom no "rompe" el layout, solo agranda
todo de forma uniforme.

### [PHASE-44.11] Un valor por defecto es una AFIRMACIÓN dormida: despierta el día que alguien empieza a usar el campo

**Error:** `inv_lots.fx_rate_at_trade` tenía `Field(default=Decimal(1))`. Nadie
lo cuestionó durante cuatro fases porque el consumidor lo neutralizaba: el
summary hacía `current_fx = cost_fx`, así que `fx_effect` salía **siempre 0** y
daba igual qué valor tuviera. Al cablear el FX vivo en 44.11.E ese `1` pasó a
significar «la compra se hizo a 1 USD = 1 EUR» y la pantalla mostraba un efecto
divisa de cientos de euros que **nadie había introducido**. El único lote real
del usuario (JNJ/USD) estaba exactamente así.
**Causa:** un default rellena un hueco con un valor **plausible**, y eso lo hace
indistinguible de un dato real. Mientras el campo no se lee, el error no existe;
cuando se lee, ya no hay forma de saber si el `1` lo puso una persona o el
schema. La trampa es que el commit que introduce el bug **no toca el default**:
lo introduce el que cambia el consumidor, meses después y en otro fichero.
**Solución:** el campo pasa a ser opcional (`None` = «no lo sé», que es lo que
de verdad pasaba) y el servidor **deriva** el dato de la fuente que lo tiene
—el tipo del BCE a la fecha de la operación, vía `currency`—. Si el usuario lo
declara, manda él. La corrección de lo ya persistido va en un script auditado
con dry-run, no en una migración ([PHASE-34]).
**Regla:** un default numérico en un campo que describe un HECHO del mundo
(un tipo de cambio, una fecha, una cantidad) es deuda desde el minuto uno,
aunque hoy nadie lo lea. Distingue «ausente» de «cero/uno» con `None` y deriva
el valor de su fuente, o exígelo. Y cuando conectes un cálculo que empieza a
leer un campo que antes se ignoraba, **audita primero qué hay realmente en esa
columna** —una consulta de una línea— en vez de asumir que quien la rellenó lo
hizo a conciencia. Señal de alarma: un término de una fórmula que salía siempre
0 y de pronto no; ese 0 estaba tapando el dato, no confirmándolo.

### [PHASE-44.12] Un emisor puede cambiar la ESCALA de presentación sin que el fichero lo diga, y ningún cuadre contable lo detecta

**Error:** La caja libre por acción de McDonald's salía **9.515.610 $** en
pantalla. El valor real es **9,52 $**: un factor de 10⁶.
**Causa:** MCD pasó en su 10-K de 2023 a expresar las acciones medias en
MILLONES (`746.3`) donde antes usaba unidades (`746300000`), y **reexpresó los
ejercicios anteriores**. El XBRL declara la unidad `shares` en los dos casos:
nada en el fichero distingue una escala de otra. La política `is_latest_view`
—quedarse con la revisión más reciente, que es lo CORRECTO— importó toda la
serie en millones mientras el dinero seguía en unidades. Es decir: el bug lo
produjo una regla acertada aplicada a un dato que había cambiado de significado.
**Por qué no saltó nada.** Los tres cuadres existentes miran identidades DENTRO
de una magnitud: el balance cuadraba, los componentes no se pasaban de su total,
el margen neto estaba en rango. Ninguno compara si dos magnitudes RELACIONADAS
siguen siendo del mismo orden. Y el daño era parcial de una forma engañosa: todo
lo que es un ratio entre ejercicios (CAGR del dividendo, racha sin recorte,
crecimiento de acciones) sale BIEN porque el factor se cancela arriba y abajo.
Sólo mienten los valores absolutos, así que una revisión rápida no lo delata.
**Solución:** corregir en la ingesta con un testigo verificable —las acciones al
cierre del namespace `dei`, que siempre van en unidades reales y son la misma
magnitud— y sólo cuando el desfase es una potencia de 10 limpia; si no lo es, no
se toca, porque sería otro problema y corregirlo a ojo convierte un dato dudoso
en uno falso. Más un cuadre nuevo de coherencia de escala, con un test que
comprueba que un banco con 20× de apalancamiento NO lo dispara.
**Regla:** cuando ingieras datos de terceros, no des por hecho que la UNIDAD de
una partida es estable en el tiempo, aunque el formato la declare: un emisor
puede cambiar su presentación y reexpresar el histórico. Para toda magnitud que
vayas a mezclar con otra en una división, ten un testigo independiente de su
orden de magnitud. Y cuando escribas cuadres, incluye al menos uno que compare
magnitudes RELACIONADAS entre sí, no sólo identidades internas: el error que
respeta todas las identidades y aun así es falso es el que llega a producción.

### [PHASE-44.12] Elegir el testigo perfecto no sirve de nada si no llega hasta donde lo necesitas

**Error:** Implementé la detección de escala usando el BPA reportado, que es el
testigo ideal: `resultado / acciones = BPA` es una identidad exacta, no una
aproximación. Escribí la función, los tests con hechos sintéticos pasaron en
verde, y al ejecutar la re-ingesta real **no cambió ni un dato**. El job decía
`done` y los números seguían mal.
**Causa:** `EarningsPerShareBasic` nunca llega a la normalización.
`annual._is_per_share` descarta los ratios por acción a propósito —para que un
BPA no se cuele como si fuera un importe— y lo hace bien. O sea: asumí la forma
de los datos que recibe mi función en vez de comprobarla, y mis tests no lo
destaparon porque yo mismo fabricaba la entrada con el hecho dentro.
**Solución:** ejecutar el pipeline e imprimir lo que de verdad llega. En los 205
hechos de MCD 2021 el EPS no está. Cambio de testigo a `shares_outstanding_eop`,
que sí llega. La ironía: el filtro que me lo tapaba existe por la lección
[PHASE-44.6], la misma que yo estaba incumpliendo.
**Regla:** un test con entrada sintética prueba tu lógica, no tu integración. Si
tu función depende de que cierto dato esté presente, comprueba **ejecutando el
pipeline real** que ese dato llega — antes de escribir la lógica que lo usa. Y
desconfía especialmente cuando el modo de fallo sea «no hace nada»: un `done`
sin cambios se lee como éxito.

### [PHASE-44.11] «Cero red en los tests» no es cierto porque esté escrito: hay que impedirlo, y el día que lo impides descubres cuántos dependían de ella

**Error:** El plan exigía «sin red en CI; todo mockeado» y la suite lo cumplía
_de palabra_: el bloqueo de `client.fetch_rates` existía como fixture local en
**dos** ficheros de test, no en `conftest.py`. Al añadir a la cartera la
petición de tasa del día, tests que no mencionan divisas empezaron a salir a
Frankfurter — y **pasaban por eso**. Cuando puse el bloqueo global, un test que
llevaba verde toda la fase (1163 en verde) se cayó: dependía de que la red le
trajera la tasa real de hoy.
**Causa:** un requisito negativo («esto NO debe pasar») no se cumple
documentándolo ni mockeando en los sitios donde te acuerdas. Mientras el mock sea
local, cada test nuevo nace sin él y el fallo es **silencioso en la dirección
buena**: la red funciona, el test pasa, nadie mira. Sólo se manifiesta en CI sin
salida a internet, o el día que la API de terceros cambia.
**Solución:** subir el bloqueo a `conftest.py` como fixture `autouse` de toda la
suite, y sembrar tasas explícitas donde los tests las necesiten. El fallo que
apareció al hacerlo no era una regresión: era la prueba de que el bloqueo hacía
falta.
**Regla:** un invariante de la suite (no hay red, no hay reloj real, no hay
sistema de ficheros) se implementa en `conftest.py` con `autouse`, nunca fichero
a fichero — si depende de que alguien lo recuerde, no es un invariante, es una
costumbre. Y cuando lo actives por primera vez, **espera que algo se rompa**: lo
que se rompe es lo que llevaba tiempo mintiendo. Hermana de [AUDIT-2026-08]: un
test cuyo resultado depende del entorno o de la fecha de ejecución es una bomba
de relojería, y la red es entorno.

### [PHASE-44.11] El vocabulario de tu propia columna se comprueba contra la función que lo produce, no contra lo que suena natural

**Error:** El plan de la fase traía la tabla de sufijos de mercado escrita como
`{NYSE:'', LSE:'.L', BME:'.MC', XETRA:'.DE', EPA:'.PA', ...}`. Implementada tal
cual, no habría acertado **ni una fila** europea: `catalog/venues.normalize_venue`
sólo produce las cuatro etiquetas de la SEC, un MIC ISO 10383 de **4**
caracteres o `UNKNOWN` — así que `'LSE'` (3 caracteres) y `'XETRA'` (5) se
normalizan a `UNKNOWN` y nunca pueden estar en `securities.exchange`.
**Causa:** las etiquetas coloquiales de bolsa son las que uno escribe de memoria,
y el plan las heredó sin contrastarlas con el normalizador que gobierna la
columna. El fallo habría sido **silencioso y total**: toda posición europea
cayendo en «plaza sin mapeo» → excluida con un motivo que suena razonable.
**Solución:** reescribir la tabla sobre MIC (`XLON`, `XMAD`, `XETR`…) y dejar un
test que afirma que las coloquiales **no** son el vocabulario, para que nadie las
reintroduzca por parecer más legibles.
**Regla:** antes de escribir un diccionario cuyas claves son valores de una
columna, ejecuta la función que normaliza esa columna sobre las claves que ibas
a usar. Es la lección [PHASE-44.6] («la forma de salida se prueba, no se
deduce») aplicada hacia dentro: el contrato que no verificas no es sólo el de la
librería de terceros, también el tuyo de hace tres fases. Y desconfía
especialmente cuando el modo de fallo es «no encuentra nada»: eso se lee como
«no hay datos», no como un bug.

### [PHASE-44.13] Un job periódico cuya condición de «ya está hecho» es LAXA no es un job: es un no-op con log de éxito

**Error:** El cron nocturno de tipos de cambio (PHASE-11.1) llevaba desde que se
construyó **sin traer una sola tasa nueva**, loguendo «0 fechas refrescadas» como
si fuera lo normal. Llamaba a `ensure_rates_for_dates([ayer, hoy])`, cuyo canario
es `get_rate_with_fallback`: acepta cualquier tasa de los **14 días anteriores**
y hace `continue`. O sea que el día que entraba una tasa, el job se callaba dos
semanas. Efecto real: la compra de JNJ del viernes 24-jul se valoró con el tipo
del **sábado 18**, y el backfill de `fx_rate_at_trade` habría escrito ese dato
rancio como «el tipo de la operación».
**Causa:** reutilizar para «refrescar a diario» una función escrita para
«rellenar huecos históricos». Las dos parecen la misma pregunta —«¿tengo tasa
para esta fecha?»— y no lo son: para convertir un movimiento pasado, el último
día hábil publicado _es_ el dato bueno; para refrescar hoy, conformarse con lo de
hace 13 días es exactamente el fallo. La segunda parte, independiente: el timeout
global de 10 s. Medido, una fecha histórica tarda 13-17 s y la del día 9,3 —así
que la pata de «ayer» fallaba SIEMPRE y la de «hoy» aprobaba por tres décimas.
Hacían falta los dos defectos para que el job no sirviera de nada, y ninguno de
los dos levanta un error.
**Solución:** una hermana ESTRICTA (`ensure_exact_rates_for_dates`) con
`missing_exact_rates` como canario, sin tocar la política laxa —que sigue siendo
la correcta para su caso—, y un timeout propio para el camino de fondo, donde no
espera ningún usuario. El módulo de cartera ya había tenido que inventarse esa
política para sí mismo en PHASE-44.11; ahora hay una sola.
**Regla:** cuando compartas una función entre un camino de REQUEST y uno de
FONDO, comprueba que su condición de salida temprana significa lo mismo en los
dos. Y desconfía de un job cuyo modo de fallo sea «no hace nada»: un `0` en el
log se lee como «no había trabajo». La señal que lo destapa no está en el código
sino en los DATOS —aquí, una fecha cada ~15 días en `exchange_rates`, el ancho
exacto de la ventana de fallback—, así que ante la sospecha de un cron muerto,
mira la huella que deja en la tabla antes que su lógica. Hermana de
[PHASE-44.11] «cero red en los tests no es cierto porque esté escrito».

### [PHASE-44.13] Un script de data-fix con `--dry-run` está probado a la mitad: el camino que escribe es OTRO camino

**Error:** `scripts/backfill_trade_fx.py` se había ejecutado en dry-run y dado
por bueno. Al lanzarlo con `--apply` reventó dos veces seguidas: primero con
`UnicodeEncodeError` al imprimir su propio informe (un `→` no existe en cp1252,
la codificación por defecto de la consola de Windows), y después con
`NoReferencedTableError` en el `commit`, porque `inv_lots` tiene FK a `accounts`
y a `users` y esos modelos no estaban registrados en el metadata de SQLAlchemy.
**Causa:** el dry-run hace un `SELECT` con los joins explícitos, que **no
necesita resolver la FK**; el flush del `--apply` sí. Y el fallo de codificación
sólo aparece en la línea que informa de un cambio, que en un dry-run con 0 filas
no se imprime. Los dos son del camino que escribe, y ese camino no se había
recorrido nunca.
**Solución:** importar `app.main` por efecto lateral (registra todos los modelos;
la lista explícita ya está duplicada en `alembic/env.py` y `tests/conftest.py`, y
una tercera copia es una más que mantener) y pasar el informe a ASCII.
**Regla:** un `--dry-run` prueba la consulta, no la escritura. Antes de confiar
un script de data-fix, ejecútalo con `--apply` contra una copia o una fila de
prueba: el camino de escritura tiene sus propias dependencias (metadata completo,
transacción, `onupdate`, codificación de la salida) que el de lectura no ejerce.
Es la misma familia que [PHASE-44.12] «un test con entrada sintética prueba tu
lógica, no tu integración».

### [PHASE-44.13] Compartir el CÁLCULO no basta si cada app se guarda su propia lista de qué mostrar

**Error (evitado):** Al llevar el informe de análisis a móvil, la tentación era
copiar las listas de métricas por bloque (`RATIO_FAMILIES`, `FORENSIC_KEYS`,
`DIVIDEND_BLOCKS`) y traducir el renderizado. El cálculo se habría compartido y
aun así las dos pantallas podrían acabar enseñando **ocho scores forenses una y
seis la otra** sin que nada avise: añadir una métrica al motor exige tocar dos
sitios, y sólo uno lo recuerda.
**Causa:** confundir «capa pura» con «fórmulas». El view-model incluye QUÉ se
muestra y en qué orden, y eso es tan compartible —y tan divergible— como el
formato de un porcentaje.
**Solución:** `packages/ui/src/investment-report-sections.ts` con las familias,
sus notas y las claves de las seis pestañas; ambas apps las importan. Las claves
son las que YA viajaban en la URL de la web (`?tab=veredicto`), no unas nuevas:
inventar un segundo vocabulario para móvil habría sido el mismo error en pequeño
(pasó, y lo destapó comparar con el fichero real antes de cablear).
**Regla:** al partir una pantalla en «pura» y «renderizado», la línea va después
del contenido, no antes: listas de campos, órdenes, etiquetas y textos
explicativos son parte de lo compartido. Si un cambio en el motor obliga a editar
dos ficheros para que las dos pantallas digan lo mismo, la partición está mal
hecha. Corolario verificado aquí: `groupFlags` también, o el móvil pinta siete
tarjetas idénticas cuando una empresa diluye siete años seguidos.

### [PHASE-44.14] Un identificador oficial tiene NIVELES, y el que publica el regulador no es el que usa todo el mundo

**Error (evitado por poco):** El plan decía filtrar los ficheros FIRDS por «los
MICs del mapa de sufijos de pricing» — `XETR`, `XMAD`, `XPAR`…. Implementado
literalmente, **Alemania entera habría quedado fuera**: Allianz no aparece en
`XETR` en ningún registro de FIRDS, aparece en `XETA` (el segmento «Regulierter
Markt» de Xetra), `XETU` (off-book) y `XEMA` (midpoint). El fallo habría sido
silencioso y con forma de dato: «Alemania no cotiza acciones».
**Causa:** ISO 10383 define MIC **operativos** (`XETR`) y MIC de **segmento**
(`XETA`). Los reguladores reportan por segmento —es el nivel al que existe la
admisión a negociación—, mientras que los proveedores de precios y la gente
hablan en operativos. Los dos son «el MIC», y ninguno de los dos documentos lo
aclara: hay que mirar el registro. Peor: `XMAD` **parece** operativo y también
es un segmento (de `BMEX`), así que España habría funcionado por accidente y
reforzado la creencia equivocada.
**Solución:** un mapa curado segmento→operativo, construido contra el CSV
oficial de ISO 10383 y contra la distribución REAL de los ficheros (contando
filas por MIC), con colapso por prioridad cuando tres segmentos caen en el mismo
par. Y un test que ata las dos tablas: **todo MIC que el seed pueda almacenar
tiene sufijo en el proveedor de precios**, o CI para el commit.
**Regla:** cuando cruces dos sistemas por un identificador «estándar»,
comprueba que hablan del mismo NIVEL del estándar antes de escribir el mapeo —
ejecutando una consulta que cuente qué valores aparecen de verdad en cada lado,
no leyendo las dos especificaciones. Y cuando el mapeo una dos tablas que deben
cubrirse (aquí: lo que se puede sembrar ↔ lo que se puede cotizar), el test que
las ata vale más que las dos revisiones que no se harán.

### [PHASE-44.14] Un fichero «de la jurisdicción X» contiene filas de la jurisdicción Y — y el dry-run lo cazó

**Error:** El seed asumía que el FULINS de ESMA trae UE y el de la FCA trae UK,
así que sincronizaba cada fuente contra su lote como particiones disjuntas. El
fichero de la FCA trae también Commerzbank y Kontron en **XETR**, valores de
Oslo y de Estocolmo: cada regulador publica lo admitido en **las plazas que
supervisa más lo que sus entidades reportan**. El mismo `(isin, mic)` entraba
por las dos fuentes y la PK reventaba.
**Causa:** deducir el contenido de un fichero de su nombre y de su emisor. Es
la lección [PHASE-44.6] («la forma de salida se prueba, no se deduce») aplicada
al ALCANCE del dato, no a su forma: los campos eran exactamente los esperados;
lo inesperado era qué filas venían dentro.
**Solución:** partición **jurisdiccional explícita** (`UK_VENUES`): cada
registro se queda con el regulador de su plaza, no con el fichero del que salió.
**Lo destapó el `--dry-run` del seed** contra los ficheros reales, 24 horas
después de escribir la lección de que un dry-run prueba la consulta y no la
escritura — aquí sí la probó porque el choque de PK ocurre al construir el
INSERT, y por eso se corrió antes de aplicar.
**Regla:** antes de tratar dos fuentes como particiones disjuntas, **compruébalo
con los datos**: una consulta que cuente el solape. Y ejecuta el dry-run de un
seed contra los ficheros de verdad, no sólo contra el fixture — un fixture lo
construyes tú con lo que ya sabes, y por eso no puede sorprenderte.

### [PHASE-44.14] Un test que sólo verifica que el guardarraíl SALTA no prueba lo que el guardarraíl protege

**Error:** El sync del directorio elimina las filas ausentes (un fichero _full_
es el universo completo, así que lo que falta es un deslistado) con un suelo de
seguridad: si el lote nuevo trae menos de 100 filas, no se borra nada — un
fichero truncado parecería «todo deslistado». Escribí el test del suelo
(`removed == 0` con un lote de 1) y lo di por cubierto. Pero **el fixture real
tiene 5 filas**, así que TODOS los tests corrían por debajo del suelo: el camino
de borrado no se ejecutaba en ninguno. Podría haber estado roto de cualquier
forma —borrar de más, no borrar nunca, borrar la fuente equivocada— y la suite
habría seguido verde.
**Causa:** cubrir la rama defensiva y confundirla con cubrir la funcionalidad.
El `assert removed == 0` se lee como «probado» y es cierto: lo que no está
probado es el `removed > 0`.
**Solución:** un lote sintético por encima del suelo que borra de verdad
(asertando qué filas desaparecen), otro que comprueba que un cambio real SÍ se
escribe y mueve `seeded_at` —si no, «0 cambios» podría significar «no detecta
cambios» en vez de «no había»— y un tercero que verifica que sincronizar una
fuente no toca las filas de la otra.
**Regla:** cuando un umbral parta el comportamiento en dos, el test tiene que
caer a **los dos lados**. Y si tus fixtures viven todos de un lado del umbral,
el otro lado no está probado por mucho que exista un test que lo mencione —
mira los datos del fixture contra la constante antes de dar la rama por cubierta.

### [PHASE-44.14] Una revisión que NO se ejecuta devuelve exactamente la misma forma que una revisión limpia

**Error (a punto de cometerse):** La revisión adversarial de la fase se lanzó
como workflow de cinco agentes con verificación por hallazgo. Devolvió
`{"confirmed": [], "totals": {"raw": 0, "confirmed": 0}}` — que es, carácter por
carácter, lo que devuelve una revisión que ha leído todo el código y no ha
encontrado nada. Estuve a un paso de reportar «revisión adversarial: sin
hallazgos». Los cinco agentes habían muerto por límite de sesión sin leer una
sola línea.
**Causa:** el agregado (`filter(...).length`) no distingue «cero hallazgos» de
«cero ejecuciones». Es la misma familia que el cron mudo de [PHASE-44.13] —un
`0` en el log que se lee como «no había trabajo»— pero aplicada a la
herramienta que debería CAZAR ese tipo de fallo. Lo delató un bloque
`<failures>` aparte del resultado, no el resultado.
**Solución:** leerlo, decirlo en el HANDOFF («la revisión no llegó a
ejecutarse») y sustituirla por lectura crítica propia. Esa lectura encontró dos
defectos reales: el borrado del sync que no se ejecutaba en ningún test, y un
formulario que sobrevivía al cambio de consulta apuntando al listing anterior.
**Regla:** cuando una herramienta de verificación devuelva «nada que reportar»,
comprueba **cuántas comprobaciones se ejecutaron de verdad** antes de creerla:
un agregado vacío es ambiguo por construcción. Y en un harness propio, haz que
el resultado lleve el recuento de ejecuciones o falle ruidosamente cuando ningún
verificador haya corrido — el silencio de un revisor muerto es indistinguible
del de un revisor satisfecho.

### [PHASE-44.15] Un «arréglalo el día que toques X» escrito en un comentario es deuda que se paga sola sólo si alguien recuerda leerlo

**Error:** `resolve_security` escribía `accounting_std=GAAP` para todo, ADR
europeos incluidos, con esta nota al lado y otra copia en el ADR-0008 y una
tercera en el backlog: _«el día que alguien añada `20-F` a `ANNUAL_FORMS`, esta
etiqueta pasa a ser load-bearing de golpe y esas cuentas se analizarían con
cortes US-GAAP sin decirlo. Quien toque `ANNUAL_FORMS` lo arregla en el mismo
commit.»_ Tres avisos escritos, cero mecanismos: nada relaciona el fichero que
hay que tocar con la línea que hay que cambiar, y el que abra `ANNUAL_FORMS`
dentro de un año no va a grepear el backlog.
**Causa:** aplazar con nota en vez de aplazar con fecha o con gate. La nota era
correcta cuando se escribió —faltaban dos piezas para poder derivar la
etiqueta— pero al llegar esas piezas nadie recalculó si el motivo seguía en pie.
Es el mismo mecanismo de [PHASE-43] («una premisa escrita caduca en silencio»),
en su variante activa: no es que la premisa deje de ser cierta, es que **deja de
ser necesaria** y nadie lo nota.
**Solución:** derivar el valor de la evidencia que ya existía
(`analysis_status`, PHASE-44.8) en cuanto la segunda pieza (`thresholds_used`,
PHASE-44.9) hizo seguro moverlo. Y comprobar que el arreglo NO es cosmético:
`IFRS` hace que los umbrales se siembren `model_variant='uncalibrated'`, que es
la declaración honesta que faltaba.
**Regla:** cuando aplaces algo con un «arréglalo cuando pase X», anota **qué
tiene que existir** para poder arreglarlo, no sólo qué lo hará urgente. Lo
primero es comprobable en cada revisión de deuda («¿ya existe?»); lo segundo
depende de que el futuro lector encuentre tu nota justo cuando toca. Y si el
aplazamiento se justificaba en que el arreglo sería un no-op, revisa esa premisa
al cerrar la deuda: aquí había dejado de serlo.

### [PHASE-44.15] Un desempate alfabético es el desempate por defecto, no una decisión — y se nota justo en las consultas más obvias

**Error:** El buscador devolvía `Banco Santander (Chile)` y `(Brasil)` **antes**
que la matriz al teclear «santander». Los tres empatan a puntuación (token
exacto, misma plaza) y el último criterio del orden era el ticker: `BSAC` <
`BSBR` < `SAN`. Se documentó como limitación aceptable («cumple el criterio del
plan, top 3») en vez de como lo que era: la consulta más previsible del buscador
devolviendo lo que nadie busca.
**Causa:** poner `item.ticker` como desempate final para que el orden fuera
determinista —lo cual es correcto— y no volver a preguntarse si había un
criterio MEJOR antes de ese. Un desempate estable no tiene por qué ser el
primero que se te ocurre.
**Solución:** el criterio estaba en el dato: la matriz es **sólo** lo buscado
más su forma jurídica; las filiales añaden un calificativo. Contar tokens
significativos —descartando `S.A.`, `plc`, `Inc`, `Corp`— y ordenar por el menor.
Efecto no buscado que confirma la regla: `johnson` pasó a devolver JNJ primero,
que salía detrás de Johnson Controls por exactamente el mismo motivo.
**Regla:** si el criterio final de una ordenación es alfabético o por id, es que
no hay criterio — y en cuanto haya empates reales, el resultado será arbitrario
en el peor sitio. Antes de aceptar un empate como «aceptable», mira los datos
que empatan y pregunta qué los distingue de verdad; y cuando encuentres el
criterio, compruébalo en una consulta que NO estabas mirando (aquí, `johnson`),
porque un desempate bueno arregla casos que no sabías que estaban rotos.

### [PHASE-44.15] `cmd | tail` rompe el `&&`: la cadena sigue aunque el comando falle, y así se lanzan dos pytest a la vez

**Error:** Lancé la verificación como una sola cadena:
`ruff && black --check | tail -2 && mypy | tail -2 && pytest | tail -3`.
`black --check` **falló** (un fichero sin formatear), lo vi en la salida, formateé
y lancé la suite otra vez. Pero la primera cadena **no se había parado**: el
código de salida de una tubería es el del ÚLTIMO comando, y `tail` siempre
devuelve 0, así que el `&&` siguió y arrancó su propio `pytest`. Dos suites
concurrentes sobre `crisol_test`, que es una sola base compartida — o sea que
**ninguno de los dos resultados valía**, incluido el que iba a reportar como
verde.
**Causa:** dos cosas que ya estaban escritas, combinadas. La memoria del
proyecto dice literalmente «`| tail` enmascara el código de salida», y
`lessons.md` dice «nunca dos pytest a la vez»; lo que no estaba escrito es que
**lo primero causa lo segundo**. Y el fallo es silencioso en la dirección
peligrosa: la cadena parecía haberse detenido porque su última salida visible
era el error de black.
**Solución:** matar los dos, comprobar que no queda ningún proceso vivo
(`Get-Process python`), y relanzar UNA suite redirigiendo a fichero
(`pytest > log 2>&1; echo EXIT=$?`) en vez de a `tail`. El síntoma que lo
destapó: dos procesos python con horas de arranque distintas.
**Regla:** no encadenes con `&&` un comando cuyo resultado te importa si va a
pasar por una tubería — el `&&` deja de proteger. Para ver sólo el final de una
salida larga sin perder el código, redirige a fichero y consúltalo después, o
usa `set -o pipefail`. Y antes de lanzar la suite, **comprueba que no hay otro
pytest vivo** en vez de asumirlo por lo que crees que hizo tu comando anterior.

### [PHASE-44.15] Un buscador por capas ordena por CAPA, y eso pisa la calidad de la coincidencia — sólo se ve con los datos reales delante

**Error:** El buscador consulta tres capas (catálogo → índice SEC → directorio
UE/UK) y concatena sus resultados en ese orden. Con los datos reales apareció lo
que eso significa: **buscar «allianz» no devolvía Allianz**. La SEC no tiene
ninguna coincidencia exacta, así que su _fuzzy_ proponía `ALLIANT`, `RALLIANT` y
`ALLIANCE` —otras empresas— y esas cuatro filas llenaban el cupo antes de que el
directorio pudiera ofrecer `Allianz SE`, que casa exacto por nombre. Y un
segundo caso de la misma familia, preexistente: con McDonald's en el catálogo,
teclear `MC` devolvía `MCD` (prefijo, capa 1) en vez de Moelis, cuyo ticker
**es** `MC`.
**Causa:** el orden de las capas es una decisión de PRIORIDAD razonable («lo que
ya tienes primero»), pero se aplicó como orden ABSOLUTO. Una capa preferente
gasta el cupo con coincidencias débiles y las fuertes de las capas siguientes no
llegan a existir. El fuzzy, además, estaba pensado como «último recurso» y lo era
sólo dentro de su propia capa.
**Por qué la suite no lo veía:** los tests inyectan un índice de dos o tres filas
elegidas, y el defecto necesita el ruido de 10.365 emisores reales conviviendo
con un directorio sembrado. Un doble de test tiene justo los datos que el autor
imaginó, y por eso no puede sorprenderle.
**Solución:** el fuzzy pasa a ser el último recurso GLOBAL (exacto de la SEC →
directorio → fuzzy), y una coincidencia de ticker al 100 % se adelanta venga de
la capa que venga. Ambos con test de regresión, validados reintroduciendo el bug.
**Regla:** si compones resultados de varias fuentes, decide si el orden entre
ellas es una **prioridad** (desempata) o una **jerarquía** (manda siempre) — casi
nunca quieres lo segundo, porque una fuente preferente con una coincidencia mala
tapa a otra con la buena. Y **levanta la app con los datos de verdad**: un
buscador con tres filas de fixture no puede enseñarte lo que hace con diez mil.

### [PHASE-44.16] Un registro JSONB persistido es la UNIÓN de todas las versiones que has escrito nunca; el tipo describe sólo la última, y por eso el compilador no te salva

**Error:** Al abrir el informe de McDonald's y pulsar una de «Las cuatro
preguntas», la pantalla se caía entera —el usuario lo describió como «me lleva a
un 404»—. `SignalTable` hacía `signals.length` sobre `undefined`. Sólo pasaba con
MCD: es el único valor analizado antes de PHASE-44.9, con el motor **1.0.0**.
**Causa:** un `AnalysisRun` se guarda como JSONB y se lee tal cual meses después,
así que la tabla contiene a la vez runs de **todas** las versiones del motor que
han existido. Pero `packages/types` se escribió mirando lo que produce el motor de
HOY, declarando obligatorios seis campos que los runs viejos no tienen. Con el
tipo mintiendo, `tsc` no podía avisar de ni uno de los ocho accesos inseguros.
Y la señal estaba escrita: dos líneas más arriba, un comentario decía _«Vacío en
los runs anteriores a PHASE-44.9»_. Tres afirmaciones distintas en dos líneas —el
comentario avisa, el tipo lo niega, la realidad dice que la clave **no existe**—
y el compilador obedece a la del medio. «Vacío» y «ausente» no son lo mismo: el
empty-state escrito EXPRESAMENTE para este caso era inalcanzable, porque la
guarda que lo mostraba (`signals.length === 0`) reventaba antes de llegar a él.
**Lo que casi no se ve, y era peor.** El crash se reporta; las mentiras
silenciosas no. La misma ausencia hacía que (a) la fila de comprobación del
DuPont pintara **«NaN» en rojo** con el título «la identidad NO cierra: hay un
problema en los datos o en una fórmula» —la pantalla denunciando un descuadre
contable inexistente en las cuentas de una empresa real, porque la guarda era
`raw === null` y lo que llegaba era `undefined`—; (b) seis métricas que el motor
1.0.0 no emitía (S7, S8 y las cuatro DUPONT\_\*) se anunciaran como «no calculable
con los datos disponibles», culpando a los balances de MCD de un hueco del
motor; y (c) `evaluated_count === 0 && signals.length > 0` fallara **en abierto**
(`undefined === 0` es `false`), así que una pregunta verde por ausencia de prueba
se presentaba como verde verificado — justo la regresión que PHASE-44.9 cerró.
**Solución:** hacer honestos los tipos (`?` en los campos posteriores a 1.0.0) y
dejar que `tsc` enumere él mismo los ocho sitios —lo hizo, exactamente los ocho—.
Encima, tres piezas: un tri-estado compartido `questionEvidence`
(`evaluated | no-evidence | not-recorded`) porque los dos primeros no se pueden
colapsar con el tercero y la regla estaba **copiada en dos ficheros**; una regla
7 de honestidad en `metricRow` que separa «el motor no la calculaba» de «no se
pudo calcular»; y un aviso global `StaleRunNotice` que compara la versión del run
con la del catálogo, porque tolerar los huecos evita el crash pero deja al
usuario delante de un informe agujereado sin causa común a la vista.
**Regla:** cuando persistas un documento (JSONB, un blob, un fichero de estado)
y lo leas con código que evoluciona, el tipo tiene que describir la **unión de
todas las versiones escritas**, no la que produce el emisor de hoy; los campos
que llegaron después van opcionales, y entonces el compilador trabaja para ti.
Distingue siempre **ausente** de **vacío/cero** —es la convención «hueco ≠ 0»
que el propio engine aplica desde PHASE-44.2 §4.5, sin aplicarla a su propia
salida—. Y cuando un dato pueda faltar, comprueba qué FRASE sale: un «NaN» rojo
o un «no calculable» que acusa al usuario de un problema en sus datos es más
caro que un crash, porque el crash se reporta y la frase se cree. Corolario de
método: la fixture se extrae de la **BD real** (aquí, el run de MCD verbatim) —
una escrita a mano hoy llevaría la forma de hoy y no probaría nada, que es
exactamente por qué esto llegó a producción con la suite en verde. Y el fixture
de móvil, casteado con `as unknown as AnalysisRun`, llevaba una forma
**imposible** (señales presentes y contadores ausentes): un cast apaga la única
comprobación que tenías.

### [PHASE-44.17] Un gate que compara NOMBRES no ve un cambio de SIGNIFICADO — y el que más falta hace es el que nunca ha fallado

**Error:** Al subir el motor a 1.4.0 por un cambio de contrato —`MetricStatus`
gana `not_applicable`, un estado con reglas propias— la huella de
`ENGINE_SHAPE_FINGERPRINTS` salió **idéntica** a la de 1.3.0. O sea que el gate
que existe desde PHASE-44.9 para «impedir tocar el motor en silencio» no habría
exigido el bump: la fase entera dependía de que alguien se acordara.
**Causa:** la huella enumera `fields()` de cada dataclass y las claves de métrica
y bandera. El DOMINIO de un alias `Literal` no es un campo, así que añadirle un
valor —o quitárselo— no mueve el hash. El gate medía la forma de los
contenedores, no la de los valores que pueden contener.
**Solución:** la huella incluye ahora los dominios de los `Literal` que el engine
publica, indexados por NOMBRE y no por módulo (`MetricStatus` se importa en media
docena de sitios y clavarle el módulo haría que mover un import cambiara el
hash). Probado rompiéndolo: añadir un valor a `Band` lo tumba.
**Regla:** cuando escribas un gate que «congela un contrato», enumera qué partes
del contrato mira y cuáles NO — y escríbelo al lado. Un gate que nunca ha fallado
no está demostrando que el contrato es estable: puede estar mirando a otro lado.
Corolario de método: la ocasión de descubrirlo es justo cuando el gate te da
verde en un cambio que tú sabes que es incompatible; si eso pasa, el bug está en
el gate. Hermana de [PHASE-43] «un linter no sustituye a un detector de
alcanzabilidad: son ejes ortogonales».

### [PHASE-44.17] Una regla que ABORTA y una que se comprueba y no salta producen la misma ausencia — y el default decide cuál se cree

**Error:** La síntesis preguntaba «¿hay bandera con esta clave?» y traducía el no
a **«no se ha encendido»**, que se lee como _comprobado y limpio_. Pero el cruce
C3 (inventario vs coste de ventas) hace `continue` en cuanto falta un dato: sin
coste de ventas **no se ejecuta ni un año**, no emite bandera, y salía como
limpio. Ocho señales de las cuatro preguntas estaban así.
**Causa:** una `Flag` sólo existe cuando salta, así que el modelo tenía dos
estados para tres situaciones. Con dos estados, el tercero se cuela en el que
tenga el default — y el default era el optimista.
**Solución:** las reglas publican su evaluación (`FlagEvaluation`: encendida ·
comprobada y limpia · no se pudo · no aplica aquí) y el default pasa a ser el
PESIMISTA: sin evaluación, «no se ha podido comprobar». Con un matiz que la
crítica adversarial marcó como bloqueante y tenía razón: **el default pesimista
sin gate de cobertura cambia un falso verde por un falso gris universal**, así
que va acompañado de un test que exige que toda clave usada tenga evaluación
publicada, más uno estático que prohíbe colar una clave escrita a mano.
**Regla:** cuando un modelo tenga menos estados que la realidad, el que falta se
esconde en el que tenga el default — así que elige el default por lo que pasa
cuando te equivocas, no por lo que pasa cuando aciertas. Y un default pesimista
sólo es honesto **con un gate de cobertura**: sin él, el gris se vuelve universal
y tan poco informativo como el verde que sustituye. Corolario aritmético del
mismo arreglo: «hay suficientes años para comprobarlo» no es un cardinal si la
regla exige una racha — con años evaluables {2016, 2018, 2020} y «dos seguidos»,
la regla no puede encenderse JAMÁS, y decir «limpia» ahí afirma una comprobación
imposible.

### [PHASE-44.21] Una decisión razonada sin test se revierte sola, y el que la revierte eres tú mismo

**Error:** Al escribir la whitelist de métricas que no aplican a una financiera
apagué **S8** (qué parte de la deuda vence a menos de un año) por inercia — iba
en el bloque de liquidez y la liquidez bancaria no es comparable. El documento de
calibración no la lista, y la razón estaba escrita desde PHASE-44.10.
**Causa:** una lista larga escrita de una sentada arrastra elementos por
proximidad temática. La justificación de cada uno era buena; la de S8 no existía,
y nada en la lista lo distinguía.
**Solución:** lo cazó un test de PHASE-44.10 —`test_la_calidad_de_la_deuda_si_aplica_en_financieras`—
que afirmaba lo contrario CON su motivo en el docstring: _«eso significa lo mismo
en un banco que en una fábrica»_. Falló, y la desviación se revirtió en un minuto.
**Regla:** cuando tomes una decisión de producto razonada —esta métrica no aplica
aquí, esta exención sí—, **escribe el test que la afirma con su motivo dentro**.
No es cobertura: es la única forma de que la razón sobreviva a quien la escribió,
porque el que la va a contradecir dentro de seis meses puede ser el mismo que la
tomó, y no se acordará. Es el mecanismo que faltaba en [PHASE-43] «una premisa
escrita a mano caduca en silencio»: un comentario no se recalcula, un test sí.

### [PHASE-44.21] Un sembrado sólo-inserción tiene un defecto simétrico: llega a las bases nuevas y nunca a la que se usa

**Error (evitado):** PHASE-44.18 hizo el arranque sólo-inserción para no
reescribir umbrales bajo los pies de un run ya guardado, y era correcto entonces.
Aplicar la calibración sectorial con esa misma regla habría producido el defecto
inverso: las bandas nuevas llegarían a cualquier base recién creada —y a CI, que
crea una— y **nunca** a la del usuario, que lleva meses con las filas viejas. Los
tests habrían pasado enteros.
**Causa:** una regla defensiva escrita contra un riesgo concreto se conserva
después de que el riesgo desaparezca. El de 44.18 era que un run viejo dejara de
poder explicarse; PHASE-44.9 ya lo había resuelto persistiendo `thresholds_used`
en cada run, así que la defensa protegía de algo que ya no podía pasar.
**Solución:** el arranque vuelve a converger (inserta lo que falta, reescribe
sólo lo que difiere, cero escrituras en régimen estacionario) y un test comprueba
las DOS direcciones: que una métrica nueva entre en una tabla con historia, y que
una recalibración llegue a una fila que ya existía.
**Regla:** al conservar una regla defensiva, comprueba si el riesgo que la
motivó sigue vivo — y si no, quítala, porque una defensa obsoleta no es neutra:
bloquea el camino que ahora sí hace falta. Y cuando una operación de
sincronización pueda fallar en dos direcciones (falta / difiere), el test tiene
que caer a los dos lados: con fixtures que siempre parten de una base limpia, el
lado «difiere» no se ejecuta nunca. Hermana de [PHASE-44.14] «un test que sólo
verifica que el guardarraíl salta no prueba lo que el guardarraíl protege».

### [dev-tooling] Redirigir la stderr de un ejecutable nativo en PowerShell 5.1 lo convierte en un error TERMINANTE — callarlo es lo que lo vuelve fatal

**Error:** `.\dev.ps1 -Stop` abortaba a mitad: mataba el backend y moría antes de
parar la web y los contenedores, dejando el entorno en un estado intermedio que
nadie había pedido. El mensaje era `taskkill : ERROR: no se encontró el proceso
"46376"`.
**Causa:** dos cosas correctas que juntas fallan. `Stop-PortHolder` mata el árbol
con `taskkill /T` —lo que ya se lleva a los hijos— y después recorre la lista de
hijos que había capturado ANTES para rematarlos uno a uno; que `taskkill` no los
encuentre es el caso **normal**. Y en PowerShell 5.1, cuando se REDIRIGE la
stderr de un ejecutable nativo (`2>$null`, `2>&1`), cada línea se envuelve en un
`ErrorRecord`: con `$ErrorActionPreference = 'Stop'` en la cabecera del script,
el primero termina la ejecución. La ironía es exacta: **sin la redirección, esa
misma stderr habría ido a la consola y no habría pasado nada**. Redirigir para
«no hacer ruido» es lo que lo volvió mortal.
**Alcance:** los tres sitios que redirigían estaban en caminos de «algo va mal»
—parar procesos, Docker caído (`docker info 2>$null`), contenedor que aún no
existe (`docker inspect 2>$null`)—, es decir, justo donde el manejo amable
existía para dar un mensaje claro y donde en su lugar se caía. Los `docker
compose up/down`, que NO redirigen, funcionaban perfectamente.
**Solución:** un `Invoke-Quiet` que ejecuta el bloque con
`$ErrorActionPreference = 'Continue'` local (y lo restaura en `finally`),
devuelve stdout y deja el código de salida en `$script:QuietExit`.
**Regla:** en PowerShell, `$ErrorActionPreference = 'Stop'` y la stderr de un
nativo no se llevan bien, y el punto de fallo NO es donde el comando falla sino
donde escribes `2>`. Si silencias la stderr de un ejecutable, hazlo en un ámbito
con `Continue`. Y desconfía especialmente de los caminos de error: son los que
menos se ejecutan, los que más redirigen «para no ensuciar» y, por eso mismo,
donde este fallo se esconde hasta el día que hace falta. Hermana de [PHASE-44.15]
«`cmd | tail` rompe el `&&`»: en las dos, la fontanería que rodea al comando
cambia el resultado de una forma que el comando no puede ver.

### [PHASE-45] Una columna sobre la que alguien FILTRA no es un puntero: es una afirmación, y reutilizarla propaga esa afirmación a donde no toca

**Error (evitado):** Para enlazar el cargo del banco con la contrapartida que lo
amortiza en la cuenta de deuda, lo barato era reutilizar `transfer_pair_id` —
existe, es una self-FK, tiene índice y ya empareja las dos patas de un
movimiento—. Habría hecho desaparecer ese gasto del presupuesto del mes y del
gasto de deuda, en silencio, justo cuando el usuario acababa de declarar que
**sí** es gasto.
**Causa:** `transfer_pair_id` no significa «apunta a». Significa «esto es la
misma plata vista por los dos lados, fuera del cashflow», y ocho consultas de
`budgets/repository.py` y `debt/repository.py` lo aplican como
`WHERE transfer_pair_id IS NULL`. La semántica no está en el nombre ni en el
tipo: está repartida por los `WHERE` de otros módulos, que es donde nadie mira
al elegir dónde guardar un enlace nuevo.
**Solución:** una columna propia (`transactions.amortization_source_id`) con su
propio significado. Lo decidió un `grep transfer_pair_id backend/app`, no una
corazonada: leer las 20 líneas que lo usan tardó menos que discutirlo conmigo
mismo, y una de ellas resolvió el diseño.
**Regla:** antes de reutilizar una columna existente para una relación nueva,
**grepea quién FILTRA por ella**, no quién la lee. Una columna que aparece en un
`WHERE` de otro módulo lleva una afirmación pegada, y tu fila nueva la heredará
entera. Si tu caso no quiere esa afirmación —aquí: «esto no cuenta como
gasto»—, no es la columna, por mucho que la forma encaje. Corolario del mismo
arreglo: cuando dos ramas de una operación necesiten semánticas opuestas
(emparejar cuando es neutro, no emparejar cuando es gasto), esa asimetría es
información, no una inconsistencia que haya que limar — escríbela y ponle test.

### [PHASE-46] Un catálogo de redacciones ajenas no es una regla: es una lista de las veces que has mirado — y el hecho vuelve con otro nombre

**Error:** Julio de 2026 mostraba **700,26 € de ingreso que nadie cobró** (el
100 % del ingreso que la app atribuía al mes) y 700,26 € de gasto que doblaba
compras ya contadas una a una. BBVA había financiado el recibo de la tarjeta:
abona el importe y al día siguiente lo cobra —neto cero, y queda una deuda a 36
meses—, pero lo escribió `Recibo anterior jun-26 Otras financiaciones` y `Recibo
mes anterior`, dos redacciones que no estaban en ninguna lista. El **mismo hecho
en marzo**, escrito `Operacion financiada`, se había clasificado bien.
**Causa:** tres listas de conceptos bancarios escritas a mano gobernaban la
decisión, y dos de ellas —`_INTERNAL_MOVEMENT_PATTERNS` en el servicio y
`_CARD_SETTLEMENT_LIKE` en el repositorio— describían **lo mismo** en sitios
distintos, que es exactamente lo que PHASE-38 dejó dicho que no se hiciera. Al
divergir, el fallo fue doble y en direcciones opuestas: el clasificador contó la
liquidación como gasto nuevo **y** el buscador del cargo espejo no la reconoció
como espejo. Nadie escribió nada falso; el banco cambió de vocabulario.
**Solución:** la secuencia de tokens se declara UNA vez y cada consumidor deriva
su forma (subcadena ordenada en Python, `ILIKE '%a%b%'` en SQL, con la misma
semántica por construcción), más un gate que falla si alguien vuelve a enumerar
liquidaciones en un solo lado. Y la pregunta «¿a qué deuda pertenece este
abono?» se saca del texto y se lleva al **capital del cuadro de amortización**:
un aplazamiento y su cuadro nacen del mismo importe, así que coinciden al
céntimo — el usuario ya había creado el pasivo con los 700,26 € exactos y sólo
faltaba el enlace.
**Regla:** cuando clasifiques por el texto que escribe un tercero, asume que el
texto cambiará y que el fallo será **silencioso y con forma de dato** (un ingreso
de más, no un error). Pregúntate qué señal ESTRUCTURAL describe el mismo hecho
—un importe que tiene que coincidir, una fecha, una relación ya modelada— y
apoya en ella lo que puedas; deja el texto sólo para lo que ninguna otra señal
puede decidir. Y si dos módulos tienen que coincidir en «qué es X», que no haya
dos listas: una sola declaración y un test que ate a los consumidores, porque
duplicar la definición no falla el día que la escribes sino el día que sólo
actualizas una. Corolario medido aquí: al apagar un falso positivo, comprueba el
caso con el signo contrario — la MISMA redacción («otras financiaciones») es
ingreso falso como abono y gasto verdadero como cargo, así que la regla sin la
condición del signo habría escondido gasto real mientras arreglaba el ingreso.

### [PHASE-46] Antes de inventar una heurística, mira si la prueba ya estaba en la fila

**Error:** Un extracto sin signos dejó `Operación financiada 4940…` (700,26 €)
**sin clasificar** — la única de 40 filas. El clasificador deduce la dirección
del texto y, si falla, del kind de la categoría; esa línea no decía ni «abono»
ni «recibido» y no resolvió categoría, así que devolvió `None`. Honesto, pero
la app se quedó sin saber algo que sí sabía.
**Causa:** PHASE-39 llevaba desde su fase guardando `statement_balance` en cada
fila **por otro motivo** (anclar el saldo), y nadie volvió a preguntarse qué más
prueba ese dato. El saldo anterior era 717,10 y el de la fila 1.417,36: el salto
es exactamente el importe, y su signo ES la dirección. La tentación era la de
siempre —añadir «operación financiada» a otra lista de redacciones— y habría
arreglado esta fila sin arreglar la siguiente.
**Solución:** una segunda pasada sobre el lote que rellena las direcciones que
falten con el salto del saldo, exigiendo coincidencia EXACTA con el importe: si
entre dos saldos hay un movimiento sin saldo, el salto no cuadra y no se toca
nada. La fila resuelta vuelve a pasar por el clasificador con el signo deducido,
así que su transfer-ness sale de la misma regla que el resto.
**Regla:** cuando una clasificación se quede sin señal, inventaria primero qué
datos tienes YA en la misma fila y qué implican, antes de ampliar el catálogo de
textos. Un dato capturado para un fin suele probar más cosas de las que se
pensaron al capturarlo, y una prueba aritmética no caduca cuando el banco cambia
de vocabulario — que es exactamente lo que le pasa a las listas de redacciones.
Corolario verificado con un test: la deducción depende del ORDEN del extracto
(BBVA imprime el más reciente arriba); leyéndolo al revés el salto sale con el
signo cambiado y la fila entra **invertida**, que es peor que dejarla neutra.
Reutiliza la detección de orden que ya exista en vez de asumir uno.

### [PHASE-46] Un fichero importado en la cuenta equivocada no da error: da números que casi cuadran

**Error:** El extracto de la TARJETA se importó eligiendo la cuenta del BANCO.
No falló nada: 19 filas OK, cero errores. Pero 17 compras de tarjeta (609,14 €)
quedaron colgando del banco, y el aplazamiento del recibo entró **por partida
doble** —una vez desde el extracto de la tarjeta y otra desde el de la cuenta—,
con la propuesta de deuda enganchada a la copia equivocada.
**Causa:** la cuenta destino la elige el usuario en el asistente y nada la
contrasta con el contenido del fichero. Y el gasto TOTAL del mes seguía siendo
casi correcto —las compras se cuentan una vez, estén donde estén, porque la
liquidación de la tarjeta es neutra—, así que el error no asoma por donde uno
mira. Lo que sí asoma es una comparación entre meses: mayo 7 compras en la
tarjeta, junio 7, **julio 0**.
**Solución:** un script que deshace el import (papelera + desenlace + limpiar la
marca de espejo) para reimportar a la cuenta correcta. Y el diagnóstico salió de
mirar `import_jobs.filename`, no las transacciones: los nombres eran
`julio criedito.pdf` y `julio debito.pdf`, ambos a BBVA.
**Regla:** cuando los números de un mes no cuadren, comprueba **de qué fichero y
a qué cuenta** entró cada lote antes de auditar transacción a transacción; el
job guarda el nombre y la cuenta, y un fichero en la cuenta equivocada produce
datos plausibles en vez de un error. Señal barata y fiable: comparar el
RECUENTO de movimientos por cuenta entre meses consecutivos — un cero donde
antes había siete no se explica por casualidad. (Pendiente: que el import avise
cuando el contenido no encaje con la cuenta elegida.)

### [PHASE-47.A] Un test que comprueba que el guardarraíl NO salta puede no estar tocándolo — sólo romper el código lo distingue

**Error (cazado por el método):** el guardarraíl del import avisa cuando un
fichero tiene el formato de OTRA cuenta, con una guarda para no molestar cuando
ese formato ya ha entrado antes en la cuenta elegida. Escribí el test obvio —una
cuenta importa su extracto dos veces, la segunda no avisa— y lo di por cubierto.
Al romper la guarda a propósito, **el test siguió pasando**: con una sola cuenta
la lista de «otras cuentas con este formato» sale vacía, así que el aviso no
podía saltar por ningún camino. La guarda estaba sin probar y el nombre del test
decía lo contrario.
**Causa:** el test recorría el camino feliz por una razón DISTINTA de la que
creía. Para llegar a la guarda hacen falta dos cuentas con la misma huella; con
una, la comprobación anterior corta antes y el resultado es el mismo verde.
**Solución:** un test con dos cuentas del mismo banco. Y de paso obligó a
escribir el comportamiento real, que yo había supuesto mal: estrenar un formato
conocido en una cuenta NUEVA **sí** avisa una vez, porque desde la cabecera es
indistinguible del error que la fase existe para cazar. La premisa equivocada
era la mía, no el código.
**Regla:** cuando un test afirme que algo NO ocurre, rompe la línea que lo
impide y comprueba que el test se cae. Si sigue verde, tu escenario no llega
hasta ahí: hay una comprobación anterior que corta y estás midiendo otra cosa.
Es el reverso de [PHASE-44.14] («un test que sólo verifica que el guardarraíl
salta no prueba lo que protege») y sólo se ve rompiendo el código — leer el test
no basta, porque se lee exactamente igual esté ciego o no.
**Corolario, aprendido caro el mismo día:** esto pasó **tres veces** en una
sesión y las tres con la misma forma —el escenario del test llegaba al verde por
un camino distinto del que decía medir—, así que la práctica no es «romper el
código cuando dudes», es **romperlo siempre, y romper LA LÍNEA CONCRETA que el
test dice proteger**. El tercer caso fue un test _del propio detector_: el probe
traía el símbolo por las dos formas de import a la vez, así que cegar una no
cambiaba el resultado. Cuando un test enumera casos, cada caso tiene que ser
alcanzable por UNA sola vía; si dos vías producen el mismo verde, el test no
distingue nada.

### [PHASE-47.A] La huella de un fichero no puede salir de lo que tu parser decide emitir: el parser normaliza, y normalizar es justo borrar lo que querías comparar

**Error:** el guardarraíl «este fichero parece de otra cuenta» calculaba la
huella del FORMATO con `header_fingerprint(rows[0].keys())`, y lo documentaba
como «la cabecera real del fichero son las claves de las filas parseadas». Falso:
`parse_pdf_smart` y `parse_xlsx_smart` construyen cada fila como un literal de
**cinco claves fijas** (`amount`, `occurred_at`, `description`, `category_name`,
`statement_balance`) sea cual sea la cabecera de entrada — es su contrato, y por
eso existe `SMART_FORCED_MAPPING`. Como los dos son el camino PRIMARIO de su
formato, la huella era **una constante** para todo PDF y todo XLSX de cualquier
banco. Con las dos cuentas del usuario importando en PDF, la guarda «este formato
ya entró aquí» se activaba siempre y el aviso **no salía nunca**: el guardarraíl
era ciego exactamente en el caso que existía para cazar.
**Causa:** confundir la salida del pipeline con la entrada. El dato que se quería
comparar (¿qué columnas traía el fichero?) es justo el que el parser existe para
hacer desaparecer. Y el modo de fallo es el peor: no lanza, no avisa, se lee como
«no hay nada sospechoso».
**Por qué la suite no lo veía:** ningún test comparaba dos cabeceras distintas, y
el que sí avisaba lo hacía por otra razón —la cuenta destino no tenía imports
previos, así que la guarda `own` estaba apagada y el aviso saltaba aunque las dos
cabeceras fueran idénticas—. Cuatro tests en verde sobre una señal que no
discriminaba nada. Lo destapó una revisión adversarial, no la suite.
**Agravante que casi se cuela:** el script de backfill derivaba la huella de
`preview_payload.rows[0].keys()` con la misma premisa, y su docstring la llamaba
«la fuente buena». Ejecutarlo habría estampado la constante en el histórico de
TODAS las cuentas — o sea, el script escrito para que la señal funcionara desde
el primer día es lo que habría garantizado que no funcionara nunca.
**Solución:** los smart-parsers devuelven `(filas, cabecera_detectada)`; la
cabecera viaja por un canal aparte porque las claves son un contrato. El camino
de visión declara `None` (no hay columnas), y el backfill sólo deriva de los jobs
cuyo parseo indexa por la cabecera real, dejando NULL —«no se sabe»— en el resto.
**Regla:** cuando compares la FORMA de un fichero de terceros, toma el dato antes
de normalizar, y compruébalo con dos ficheros de forma distinta: un test que
afirme «huella(A) ≠ huella(B)» es de una línea y es el único que distingue una
señal viva de una constante. Corolario de documentación: la frase «X real son
las claves de Y» es una afirmación sobre el contrato de Y — si Y es un parser con
salida normalizada, es falsa por construcción, y escribirla en el comentario que
justifica el código convierte el bug en doctrina.

### [PHASE-47.E] Verificar rompiendo el código sólo vale si la rotura LLEGÓ: una sonda que no aplica se lee igual que un test que protege

**Error:** Para comprobar que el test defendía la mitad «el desglose por
categorías NO excluye lo aplazado», rompí esa mitad con un `replace` de cadena
y relancé: **8 passed**. Estuve a un paso de anotarlo como «verificado» — y la
conclusión habría sido la contraria de la verdad, porque el patrón que buscaba
mi sonda no existía en el fichero y la rotura nunca se aplicó. El código seguía
correcto, así que los tests seguían verdes.
**Causa:** una sonda por `str.replace` falla **en silencio y devolviendo éxito**:
si el patrón no casa, el fichero queda intacto, el proceso sale con 0 y la suite
pasa. La señal que uno espera («pasa» = «el test no protege esto») es
indistinguible de («pasa» = «no he roto nada»). Es la familia de [PHASE-44.14]
—una revisión que no se ejecuta devuelve lo mismo que una limpia— aplicada al
gesto que precisamente existe para no fiarse.
**Solución:** afirmar la sonda antes de correr nada (`assert patrón in texto`, o
insertar por número de línea comprobando el contenido de esa línea) e imprimir
que se aplicó. Rehecha así, la rotura tumbó el test al instante.
**Regla:** cuando verifiques un test rompiendo el código, **comprueba primero
que la rotura entró**. Una sonda de edición tiene que fallar ruidosamente si no
encuentra su objetivo; si no, el resultado «verde» no distingue «tu test es
inútil» de «tu sonda es inútil», y sólo una de las dos cosas te lleva a
reescribir el test. Corolario: en una tanda de roturas, la que **no** tumba
nada es la que hay que mirar dos veces — no la que sí.

### [PHASE-47.E] Un guardarraíl que sólo hace falta cuando el usuario modela BIEN sus datos no se activa nunca en las pruebas

**Error (cazado por un test que falló):** al abrir el reparto del cargo agregado
de la tarjeta para que alcanzara al recibo aplazado, el test dio **0 cuotas
pagadas** en vez de 1. La causa no estaba en lo que acababa de tocar: con **dos**
pasivos de tipo `LOAN`, `_resolve_target` declara ambiguo el cargo de
amortización y **el préstamo de verdad deja de amortizar**, en silencio.
**Causa:** el segundo `LOAN` sólo existe cuando el usuario registra su recibo
aplazado como lo que el banco le vendió. Mientras tuviera una sola deuda de ese
tipo —o la tuviera archivada, que es el estado actual— el defecto es invisible.
O sea: el fallo aparece **al hacer las cosas bien**, que es el peor momento para
descubrirlo y el que ningún test escrito «con los datos de hoy» reproduce.
**Solución:** los dos pools se hacen disjuntos por la MISMA regla (¿cuelga de una
tarjeta?), y un test afirma que el préstamo avanza exactamente una cuota cuando
los dos cargos caen en el mismo mes.
**Regla:** cuando amplíes qué entra en un reparto, comprueba también qué deja de
ser único al otro lado — un desambiguador que hoy acierta porque sólo hay un
candidato deja de acertar en cuanto haya dos, y esa segunda entidad suele
aparecer precisamente cuando el usuario adopta el modelo que le propones.
Hermana de [PHASE-44.21] «una decisión razonada sin test se revierte sola»: aquí
lo que faltaba no era la razón, era el caso con dos.

### [PHASE-47.E] Un cambio de regla que sólo aplicas en UN módulo deja el mismo bug vivo en el de al lado — y lo destapa el cociente cuyas mitades ya no se miran

**Error:** la fase declaró que el resultado del mes EXCLUYE las compras
aplazadas, y lo cableó en `dashboard/repository.py`. Pero `analytics` calcula la
tasa de ahorro y el runway con sus PROPIAS consultas, que no lo excluían — y su
ingreso lo toma de `get_totals_by_kind`, que sí. O sea que las dos mitades del
mismo cociente pasaron a mirar universos distintos: la tasa estructural podía
salir POR DEBAJO de la bruta, que es imposible (el gasto estructural es un
subconjunto del bruto), y la pantalla pintaba un badge contradiciendo su titular.
**Causa:** al mover una regla de negocio, se cablea donde uno la estaba pensando
—la pantalla que motivó el cambio— y no donde vive el CONCEPTO. «Cuánto he
gastado» se calcula en cuatro sitios, y sólo uno estaba delante.
**Solución:** inventariar TODA agregación de dinero y clasificarla explícitamente
en caja / gasto / saldo antes de tocar nada; luego aplicar la exclusión sólo a
las de caja. El resultado no es uniforme a propósito: `exceptional_by_category`
NO excluye, porque alimenta el desglose. Y un test que ata las dos mitades
(gasto de Análisis == gasto del resumen, y estructural ≥ bruta), que es lo que
faltaba.
**Regla:** cuando cambies qué entra en un cálculo, la unidad de trabajo no es la
consulta que tienes abierta: es el CONCEPTO. Haz el inventario —`grep` de las
funciones de agregación del dominio— y decide una por una, incluidas las que vas
a dejar como están, porque esas también son una decisión. Y busca un invariante
que ate las piezas que deben moverse juntas: aquí, que un cociente cuyas dos
mitades salen de módulos distintos no puede violar una desigualdad aritmética.
Señal de diagnóstico gratis: si dos números que deberían compararse viven en
funciones distintas, escribe el test que los compara — es más barato que la
revisión que no vas a hacer.
**Y otra vez, en la capa de presentación (PHASE-47.H, 2ª entrega).** Al llevar
el signo de una devolución a la pantalla se arreglaron los dos endpoints que
emitían `TopExpenseItem`… y quedó un TERCERO emitiendo lo mismo con otro tipo:
`top_exceptional` de analytics filtra por el **mismo** `_is_expense()`
—importado literalmente del otro módulo— y su tarjeta pintaba el importe crudo,
contradiciendo al desglose de **la misma pantalla**. El inventario que hay que
hacer no es «qué pantallas he tocado» sino **quién consume el predicado**: un
`grep` de `_is_expense` da los tres emisores en una línea, y la pertenencia al
módulo no dice nada — el consumidor que faltaba estaba en otro paquete y con
otro nombre de tipo. Corolario de riesgo: el defecto era invisible con los
datos de hoy por **dos euros** (el corte del top-5 de un mes real estaba en
43,58 € y la devolución de ese mes era de 41,35 €), así que «no se ve en
pantalla» no es prueba de nada — mídelo ejecutando el servicio real contra los
datos, que es lo que convirtió una sospecha en un número.

### [PHASE-47.E] Una revisión que muere a medias devuelve un agregado que se lee como una revisión limpia — mira el recuento de ejecuciones, no el resultado

**Error:** la revisión adversarial de la fase reportó `confirmed: 11` de `raw:
35` y un veredicto por hallazgo. Parecía completa. En realidad **66 de sus 111
agentes murieron por límite de sesión**: el crítico de completitud no llegó a
correr y tres de los cinco frentes se quedaron sin la mayor parte de su
verificación. Los `0` de esos frentes no significaban «no hay nada», significaban
«no se miró».
**Causa:** el agregado (`filter(...).length`) no distingue «cero hallazgos» de
«cero ejecuciones». Ya está escrito en [PHASE-44.14], y aun así la forma en que
llega —un JSON con totales y una lista de veredictos— invita a leerlo como
resultado y no como muestra.
**Solución:** leer el bloque de fallos ANTES que el resultado, y reportar la
cobertura real al usuario en la misma frase que los hallazgos. Los seis defectos
confirmados se arreglaron; lo que no se revisó quedó dicho como no revisado.
**Regla:** de una herramienta de verificación, mira primero cuántas
comprobaciones se ejecutaron y cuántas murieron; sólo después el veredicto. Y
cuando reportes, di la cobertura junto al hallazgo — «seis defectos, con tres
frentes sin verificar del todo» es información; «seis defectos» a secas es una
falsa sensación de fondo tocado.

### [PHASE-47.E] Un `replace(..., 1)` sobre un patrón que aparece dos veces edita la función equivocada — y romper el código no lo caza si la otra no tiene test

**Error:** el arreglo del bloqueador debía excluir el gasto aplazado en DOS
funciones de `analytics`: la base de las tasas de ahorro y la del runway. Apliqué
la edición con un `str.replace(patrón, nuevo, 1)` cuyo patrón —el bloque
`_apply_scope(... window_start ... window_end)` seguido del filtro de
transferencias— **existe en dos funciones**. Se reemplazó la primera del fichero,
que era `monthly_expense_by_category`. Resultado: el runway seguía contando lo
aplazado y, de propina, la CLASIFICACIÓN de categorías recurrentes empezó a
excluirlo, que es lo contrario de lo que debe hacer. El comentario que explica el
runway quedó pegado a una función que no calcula el runway.
**Por qué el gesto de verificar no lo cazó:** rompí la exclusión y un test falló,
así que lo di por probado. Pero el test que falló miraba la OTRA función, la que
sí quedó bien. Para el runway no había ningún test — y un arreglo sin test no
está verificado por mucho que hayas roto algo cerca y visto rojo. La rotura te
dice que ALGO está protegido, no que lo esté lo que tú crees.
**Solución:** afirmar la unicidad antes de editar (`assert t.count(patrón) == 1`)
o editar por número de línea comprobando su contenido; y escribir el test que
faltaba —el del runway— antes de dar el arreglo por bueno.
**Regla:** una edición programática sobre código exige que su ancla sea ÚNICA, y
eso se comprueba contando, no mirando. Y al verificar rompiendo, comprueba que el
test que se cae es el que cubre **la línea que acabas de tocar**: si tu cambio
afecta a N sitios, necesitas N tests que fallen, uno por sitio. Corolario que
duele: fue una revisión adversarial la que encontró esto, no la suite en verde ni
el propio gesto de romper — porque ambos sólo pueden hablar de lo que alguien
decidió mirar.

### [PHASE-47.E] `campo !== null` marca TODAS las filas cuando el servidor aún no manda el campo — y el tipo dice que sí lo manda

**Error:** el asterisco de «gasto aplazado» salía en **todas** las
transacciones, con **cero** aplazamientos declarados en la base. La condición
era `tx.deferred_by_account_id !== null`, y el backend en marcha del usuario era
anterior al campo: llegaba AUSENTE, y `undefined !== null` es cierto. La app le
anunciaba a la cara un aplazamiento que no existía, en cada fila.
**Causa:** el tipo declara `deferred_by_account_id: string | null` —obligatorio—
así que `tsc` no ve nada raro en compararlo con `null`. Pero un tipo describe el
contrato, no lo que el servidor en ejecución está devolviendo: durante un
despliegue a medias, con una respuesta cacheada o con el backend sin recargar,
el campo simplemente no viene. Es la lección de [PHASE-44.16] («ausente y vacío
no son lo mismo») en su versión de API viva en vez de documento persistido.
**Solución:** comprobar por VERDAD (`tx.campo ? … : null`), que cubre `null`,
`undefined` y cadena vacía a la vez; y un test que renderiza una fila con el
campo OMITIDO, no puesto a null — que es el caso que ocurrió.
**Regla:** para decidir si pintas una marca, usa una comprobación por verdad y
no una comparación con `null`. La comparación estricta sólo es correcta si
estás seguro de que el campo SIEMPRE viaja, y de eso no puedes estar seguro
mientras exista una versión del servidor que no lo mandaba. Corolario de test:
un caso de «campo ausente» se escribe **omitiendo la clave**, no poniéndola a
`null` — con `null` el test pasa igual y no prueba nada. Y quien lo destapó fue
una captura de pantalla del usuario, no la suite: las 186 pruebas en verde
convivían con un asterisco en cada fila.

### [PHASE-47.F] Dos correcciones para un mismo hecho dan el número bueno hasta el día que una de las dos se equivoca — y un dato con testigo externo no admite ninguna

**Error:** el saldo de BBVA salía **700,26 € por debajo** del que imprimía el
banco. La app aplicaba DOS correcciones al mismo hecho: anulaba el abono de la
financiación en el saldo (un carve-out en `signed_amount_expr`) **y** borraba el
cargo que lo compensaba (`find_mirror_charge`). Con las dos, el neto salía 0 —
correcto. En julio la segunda se comió una línea que venía del extracto de la
TARJETA importado por error en la cuenta del banco, así que la primera se quedó
sin pareja y anuló un abono real.
**Causa:** la justificación escrita del carve-out estaba **invertida**: decía que
contar el dinero prestado dejaría un «activo fantasma» que inflaría el
patrimonio. Al revés — caja +X contra deuda +X deja el patrimonio IGUAL; caja 0
contra deuda +X lo deja en −X. La app apuntaba la deuda y escondía el dinero, y
recibir un préstamo te empobrecía sobre el papel. El error sobrevivió cuatro
fases porque la segunda corrección lo compensaba.
**Lo que lo destapó:** ejecutar la función REAL contra la BD y compararla con
`anchored_statement_balance`, el saldo que el propio banco imprimió y que
PHASE-39 lleva guardando desde entonces. Nadie lo consultaba **después** de
anclarlo. La entrada previa del backlog, escrita leyendo las filas en vez de
ejecutando el cálculo, afirmaba la diferencia en la dirección CONTRARIA.
**Solución:** una sola verdad — cada línea del extracto aporta su propio signo,
sin carve-out y sin absorción. Cuando el espejo es real, borrar las dos líneas y
dejarlas vivas dan **el mismo número**: lo único que añadía la mecánica era una
forma de equivocarse. Más `scripts/audit_balances_vs_statement.py`, que compara
cada saldo con su testigo y sale con código 1 si alguno diverge.
**Regla:** si un número sale bien por dos correcciones que se compensan, no está
bien: está empatado. Cuenta cuántas veces tocas el mismo hecho y déjalo en una.
Y cuando un dato tenga un **testigo externo** —un saldo que imprime un banco, un
total que declara un tercero— escribe el chequeo que los compara y hazlo fallar
ruidosamente: guardar el testigo y no consultarlo es tener la prueba en el cajón.
Corolario que casi cuesta caro: al retirar una corrección, comprueba qué OTRA
cosa la estaba compensando — aquí, la dirección de la tx origen se reescribía a
«entrada» fuera cual fuera, inofensivo sólo mientras el saldo la anulara después;
sin la anulación, una compra de 500 € subiría el saldo 500 €.

### [PHASE-47.G] Una prueba que se consulta la ÚLTIMA no protege de nada: la conjetura que acierta a decidir nunca llega a contrastarse

**Error:** seis devoluciones (Amazon, Sanareva) entraron como GASTO entre abril
y julio de 2026 — 238,87 € con el signo cambiado, o sea 477,74 € de desvío en el
saldo, el doble de error que si se hubieran perdido. Las seis rompían la cadena
`saldo ± importe` de su propio extracto, que estaba guardada en la misma fila
desde PHASE-39.
**Causa, en dos capas.** La primera: `_parse_amount_signed` sólo llama «entrada»
a un importe con `+` explícito, y un `33,58 €` a secas devuelve «el extracto no
declara dirección», así que decide la categoría — y para un Amazon dice
«compras». Mirando UNA fila es correcto (hay extractos que son magnitudes
puras); mirando el FICHERO no, porque ese mismo fichero escribe los cargos en
negativo. **La convención de signos es una propiedad del lote, no de la línea.**
La segunda, y es la que importa: la comprobación por saldo existía, pero sólo se
aplicaba a las filas que se habían quedado SIN dirección. Una conjetura que
acertaba a decidir —mal— jamás se contrastaba con la prueba.
**Solución:** la cadena de saldos MANDA sobre la conjetura, no la rellena. Si el
salto contradice la dirección asignada, gana el salto (y el preview lo dice).
Sigue exigiendo que el salto sea exactamente el importe, y gobierna sólo la
DIRECCIÓN — la transfer-ness la decide el texto, de la que el saldo no sabe nada.
**Regla:** cuando tengas una señal que DEMUESTRA (una identidad aritmética, un
testigo externo) y varias que DESCRIBEN (un texto, una categoría, una
convención), la que demuestra va PRIMERO y las otras sólo cubren lo que ella no
alcanza. Ponerla de último recurso la deja sin ejercitar justo en los casos en
que las demás se equivocan con seguridad, que son los únicos que importan: una
conjetura que falla en silencio se lee igual que un acierto. Corolario del
método, aprendido en esta misma fase: al verificar rompiendo, una sonda que **no
tumba nada** es información — aquí destapó que el `if` que yo creía guardarraíl
era redundante y que el que protegía de verdad era otro, tres líneas más abajo.

### [PHASE-47.G] Guardar un testigo y no consultarlo es tener la prueba en el cajón

**Error:** `anchored_statement_balance` —el saldo que el propio banco imprimió—
lleva persistido desde PHASE-39. Se escribía al importar y **no lo leía nadie
más**. Con él en la BD, el saldo de BBVA estuvo 700,26 € por debajo del real
durante semanas sin que ninguna pantalla, test o job lo dijera; lo destapó el
usuario porque no se creyó un número.
**Causa:** el dato se capturó para un fin concreto (anclar el `opening_balance`)
y nadie volvió a preguntarse qué MÁS demuestra. Y el mecanismo del anclaje es
justo el que lo esconde: al reanclar, cualquier error anterior se absorbe en el
saldo inicial y la cuenta vuelve a «cuadrar» sola.
**Solución:** `statement_gap` por cuenta en la API, el aviso en la pantalla de
cuentas, `find_statement_seams` para los tramos que faltan (1.211,95 € entre el
30-jun y el 5-jul en los datos reales) y `make audit-balances`. **Fuera de `make
verify` a propósito**: audita datos, no código, y un gate que falla por algo
ajeno al commit se acaba ignorando.
**Regla:** por cada dato que persistas como testigo de una verdad externa,
escribe también QUIÉN lo comprueba y CADA CUÁNTO. Si la respuesta es «nadie,
sólo se escribe», no es un testigo: es una columna. Y desconfía de los
mecanismos que restauran la coherencia recalculando un tapón (un
`opening_balance`, un ajuste, un residuo): dejan el número de hoy correcto y
borran la única señal de que algo iba mal.

### [PHASE-47.H] Apoyarse en una señal que ya ha mentido es aceptable si el peor caso sólo cambia la ETIQUETA — dilo, y ponle el test que lo ata

**Error (de diseño, evitado):** para distinguir una devolución de un ingreso hay
que mirar la categoría, que es exactamente la señal que ha causado nueve
lecciones de esta lista. La tentación era descartarlo por principio.
**Causa del matiz:** las nueve veces anteriores la categoría decidía la
DIRECCIÓN del dinero, y equivocarse ahí invierte un signo: mueve el saldo, el
patrimonio y el cashflow a la vez. Aquí la dirección ya viene probada por la
cadena de saldos del extracto y la categoría sólo responde «¿es una categoría de
compras?». Si se equivoca, un ingreso real cuenta como gasto negativo: el
reparto cambia y **el neto no**.
**Solución:** apoyarse en ella, pero (a) escribir el peor caso en el docstring,
(b) meter el signo en un helper EXPLÍCITO (`expense_amount_expr`) en vez de en
la expresión de importe compartida —que la usan 39 sitios, incluidos los saldos
y los presupuestos, donde firmar habría movido el saldo—, y (c) un test que
afirma que el saldo NO se mueve, que es el guardarraíl del diseño y no una
cobertura más.
**Regla:** al evaluar una señal poco fiable, no preguntes «¿ha fallado antes?»
sino «¿qué se rompe cuando falle esta vez?». Una señal que sólo puede
equivocarse en la etiqueta es utilizable; la misma señal decidiendo un signo, no.
Escribe esa diferencia donde vive el código, porque el que la lea dentro de seis
meses verá «esto usa la categoría» y tendrá razón en sospechar. Corolario de
alcance: cuando el predicado cambie de significado, inventaría sus usos y
clasifícalos —de 26 llamadas, sólo **7 sumaban** y son las únicas que necesitan
el signo; las demás filtran, cuentan o etiquetan—. Firmar donde no toca es tan
error como no firmar donde sí.
**Corolario que costó cinco tests en rojo:** el fichero abría con _«los TRES
helpers son NULL-safe: un row sin flow ni categoría no rompe el WHERE»_, y el
cuarto que añadí nació sin serlo. `(flow == IN) AND (Category.kind == EXPENSE)`
con categoría NULL da **NULL**, no `false`, y ese NULL se propagó al `AND NOT`
de `_is_income()`: toda entrada SIN CATEGORÍA —que es el estado por defecto de
media app recién importada— dejó de contar como ingreso. Síntoma: tasa de ahorro
`None` y titular del mes en −1.500 € en vez de +500. Cuando añadas un miembro a
una familia de helpers, lee el comentario que gobierna la familia y compruebe
que **el tuyo también lo cumple**: un invariante escrito para «los tres» no se
extiende solo al cuarto. Y en SQL, la lógica de tres valores convierte un
descuido de NULL en un filtro que descarta filas en silencio, nunca en un error.

### [PHASE-47] Un dato CIVIL guardado en un tipo que exige zona elige zona por accidente — y el accidente es la máquina que lo escribió

**Error:** «13/02/2026» —la fecha que imprime el banco— se persistía en
`transactions.occurred_at` (`TIMESTAMPTZ`) como `2026-02-12T23:00:00Z`. Medido
en la base real: **469 de 491** filas vivas desplazadas un día, **14 de mes
natural** (una transferencia de 4.267,47 € contando en marzo siendo del 1 de
abril, un cargo de amortización de 232,27 € en mayo siendo del 1 de junio).
**Causa:** `_parse_datetime` devolvía un `datetime` NAIVE, y asyncpg codifica un
naive con `astimezone(utc)` — que sobre un naive asume la zona **del proceso**.
Con el backend en Europe/Madrid, la medianoche civil se convertía en las 23:00Z
del día anterior (22:00 en horario de verano; las dos firmas están en los datos:
354 filas a 22:00 y 194 a 23:00). O sea: **el valor almacenado dependía del
ordenador que hizo el import y de la estación del año.** Una fecha civil no
tiene hora ni zona; guardarla en un tipo que exige instante obliga a elegir una,
y si no la eliges tú la elige el driver.
**Por qué nadie lo vio en cuatro fases:** la pantalla formatea en hora LOCAL, así
que mostraba el día correcto y cuadraba con el extracto. El desajuste sólo asoma
en los BORDES, porque los filtros de rango se construyen en UTC (`T00:00:00Z`):
un movimiento que la app muestra el día 13 vivía a las 23:00Z del 12 y quedaba
fuera de un rango que empieza el 13. Con el mes natural el borde cae el día 1,
que suele tener poco movimiento; lo destapó el ciclo del usuario con D=13, que
puso el borde en medio de datos densos — 3 movimientos en febrero y 6 en marzo.
Y la suite no podía verlo: **todos** sus tests crean transacciones por la API con
cadenas `...T00:00:00Z` explícitas, o sea viviendo ya en el mundo donde la fecha
está bien. Ninguno recorría el camino del importador.
**Solución:** el parser ancla en UTC (anclar, no convertir: convertir asumiría
que venía en local, que es el bug), un `CivilDatetime` compartido en los schemas
de ENTRADA para que ninguna otra ruta reintroduzca un naive, y un script de
datos. Más el test que faltaba: importar `13/02/2026` y afirmar que la fila cae
dentro del día 13 — tz-independiente, así que falla en cualquier máquina que no
esté en UTC.
**Regla:** cuando un dato del dominio sea una fecha CIVIL (el día de un extracto,
un vencimiento, una fecha de operación) y la columna sea `TIMESTAMPTZ`, fija tú
la zona en la frontera de entrada y escríbelo donde el compilador lo vea (un tipo
anotado), no en un comentario. Y desconfía del formateo local: hace que el dato
se lea bien mientras los filtros lo tratan como otro día, así que el bug no se
manifiesta hasta que alguien mira un BORDE. Corolario de test: una suite que
siembra por la API con fechas ya normalizadas no prueba el camino del importador
— para un pipeline de ingesta, el test tiene que entrar por donde entra el dato.
**Corolario de método, y es lo que hizo segura la corrección:** antes de mover
469 filas, busca un TESTIGO que ya tengas. El `import_hash` se calculó con la
fecha civil que el parser leyó del fichero, así que recomputarlo con la fecha
candidata **prueba** que la candidata es la del extracto — 536 de 548 filas se
movieron con esa prueba delante y las 12 restantes (contrapartidas que genera el
propio backend, sin hash) se reportaron aparte. El mismo testigo resolvió un
bloqueante: serializar la fecha SIN el sufijo de zona reproduce byte a byte el
hash que producía el naive, así que el cambio del parser es invisible al dedup y
no hubo que rehashear ni una fila. Verificado contra filas reales antes de
escribir el arreglo, no después.

### [PHASE-47] La octava premisa caducada — y esta vez el detector mira el CABLEADO, no el símbolo

**Error:** La página de Análisis pasaba `range={period === 'cycle' ? 'month' :
period}` al navegador de período, con el comentario «el navegador habla
`DebtTimeRange`, sin `cycle` · rama inalcanzable hasta C3a». Era cierto al
escribirlo y dejó de serlo en C3a, cuando el navegador pasó a declarar
`range: PeriodKey` —CON `cycle`— y a sacar de ahí el chip marcado y la etiqueta
«Ciclo del D mes». Resultado: el preset quedaba activo por dentro (los datos se
pedían con `cycle=true` y el chart pintaba barras de ciclo) mientras el toggle
seguía marcando «Mes».
**Causa:** la misma de [PHASE-43], por octava vez. Pero con una forma que los
detectores anteriores no cubren: aquí no sobraba un símbolo (knip no ve nada, el
componente se usa) ni faltaba un tipo (`'month'` es un `PeriodKey` perfectamente
válido, así que `tsc` calla). Lo que estaba mal era **el valor que un consumidor
decide pasar**, y eso no lo mide ningún eje de los que ya teníamos.
**Solución:** un gate estático que recorre las pantallas y falla si alguna
colapsa `cycle` antes de entregárselo a un selector de período. Verificado
reintroduciendo la línea exacta: falla señalando fichero, número y el texto.
**Regla:** cuando arregles un cableado que ninguna herramienta podía ver, el test
de regresión va sobre **el cableado de todas las pantallas**, no sobre la que
arreglaste — la reintroducción llega en una pantalla que aún no existe, y un test
de las que hoy hay no la vería. Y comprueba que el gate recorre ficheros de
verdad (un `expect(paginas.length).toBeGreaterThan(5)`): un gate que se queda sin
entrada pasa por vacuidad, que es la forma más cara de no tener gate.

### [PHASE-47] Una serie en una unidad DESPLAZADA no se puede indexar por el año natural de su ancla: el primer bucket se cae, y con él dinero real

**Error:** El histórico «en ciclos» (`by-month?year=2026&cycle=true`) devolvía
los **12 ciclos que ABREN en 2026**, y así estaba escrito en el docstring — o
sea, era una decisión, no un descuido. Pero los días 1..D−1 de enero no
pertenecen a ninguno de esos doce: pertenecen al que abrió el día D de
**diciembre del año anterior**. Con D=13 sobre los datos reales eso son **30
movimientos, 69,62 € de entradas y 698,70 € de salidas** que no aparecían en
ninguna barra. La suma del histórico en ciclos daba 25.115,19 € de gasto contra
25.813,89 € del año natural: **698,70 € de diferencia**, exactamente los que
faltaban.
**Causa:** confundir «etiquetar por el ancla» con «filtrar por el ancla». La
etiqueta del bucket sí sale del ancla (el ciclo del 13-dic-2025 se llama
`2025-12`), pero el CONJUNTO de buckets que cubre un año natural no es «los que
abren dentro de él» — es «los que lo tocan», y en los bordes eso incluye uno del
año anterior. Es la misma familia que [AUDIT-2026-08] (una ventana que no
contiene sólo meses realmente observados), pero por el otro extremo: aquí la
ventana deja fuera un bucket que sí tiene datos.
**Por qué la suite lo bendecía:** había un test —`test_el_ciclo_cruza_el_ano_sin_partirse`—
que afirmaba `_sum(en_2026, 'expenses') == 0` para un gasto del 5 de enero. O
sea, el comportamiento roto estaba **escrito como criterio**. El test no estaba
mal por descuido: comprobaba que el año se lee del instante desplazado, que es
correcto; lo que no comprobaba es que ese dinero apareciera en ALGUNA parte de
la vista que el usuario mira.
**Solución:** trece buckets cuando el ciclo está activo, empezando por el que
abre en diciembre del año anterior. Que ese ciclo aparezca también en la vista
del año anterior es deliberado —es un bucket de SOLAPE, no un doble conteo
dentro de una misma vista, y la etiqueta lo dice: «Ciclo del 13 dic 2025»—.
Verificado contra los datos reales: la serie en ciclos y la natural suman
**exactamente lo mismo**, 21.035,58 € y 25.813,89 €.
**Regla:** cuando una serie temporal cambie de unidad (ciclos, semanas fiscales,
trimestres desplazados), escribe primero el test de CONSERVACIÓN —la suma de los
buckets tiene que ser la del período en la unidad vieja— y sólo después los
tests de reparto. El de reparto puede pasar entero con dinero desaparecido; el
de conservación no. Y si un test existente afirma que cierto dinero vale cero en
una vista, pregúntate dónde vale distinto de cero: si la respuesta es «en
ninguna», el test está protegiendo un agujero.

### [PHASE-47] Un ajuste que se ofrece como PRESET compite con lo que redefine — y el usuario acaba con dos vocabularios para la misma pregunta

**Error:** El día en que empieza el mes del usuario (`users.cycle_start_day`) se
expuso como un chip «Mi ciclo» al lado de «Mes». Convivían: el ajuste estaba
puesto y la app seguía enseñando el mes natural hasta que el usuario pulsaba el
chip, en cada pantalla y cada vez. Su veredicto, que vale más que cualquier
especificación: _«sigue siendo raro e incómodo»_.
**Causa:** confundir «el usuario declara un dato» con «el usuario elige una
vista». El día de cobro no es una opción de visualización: es la respuesta a
«¿qué es un mes para ti?», y esa pregunta ya tenía una respuesta por defecto en
el producto. Ofrecer las dos a la vez obliga a mantenerlas sincronizadas para
siempre — y no lo estaban: sólo CINCO endpoints entendían el ciclo y el resto
del backend cortaba por mes natural aunque el ajuste existiera.
**Solución:** el día REDEFINE el mes. El chip desaparece, «Mes» es el mes del
usuario, y en Ajustes hay un check «Modo predeterminado» que dice en voz alta
cuál es el comportamiento por defecto. Una declaración por capa —
`user-month.ts` en el frontend, `user_month.py` en el backend— en vez de un
ternario repetido en seis pantallas y un mes natural derivado a mano en cinco
agregados.
**Regla:** cuando un ajuste REDEFINA un concepto que el producto ya tiene
(qué es un mes, qué es una semana laboral, qué cuenta como gasto), no lo
ofrezcas también como opción paralela: sustituye el concepto y deja el
comportamiento anterior como el default explícito. Dos vocabularios para la
misma pregunta no son flexibilidad, son dos sitios que hay que mantener de
acuerdo y una pregunta que el usuario tiene que volver a responder cada vez.
**Corolario de método, y es lo que hizo el cambio abarcable:** para un
reemplazo así, **borra el valor del TIPO primero** y deja que el compilador
enumere. Quitar `'cycle'` de `PeriodKey` produjo la lista exacta de ~35 puntos;
escribirla a mano habría dejado ramas fuera, y una rama olvidada aquí devuelve
el mes natural **en silencio** —mismo tipo, rango distinto, ningún error—. De
paso, la lista destapó tres bugs que llevaban tiempo ahí y que nadie habría
visto leyendo: el Dashboard afirmaba recibir sus bounds en ciclos sin pedirlos
nunca así, la semilla de «Personalizado» se construía con el mes de calendario,
y la serie diaria de Deuda se habría pintado vacía porque el backend sólo la
calcula con `range=month`. Los cazaron, por ese orden, el compilador, un gate y
un test — ninguno una revisión.

### [PHASE-47] Al reemplazar un concepto, el test que hay que escribir PRIMERO es el de conservación

**Error (evitado, y la razón por la que no hubo sorpresas):** migrar cinco
agregados a «el mes del usuario» significa cambiar la ventana de la proyección,
del runway, de los presupuestos, de la clasificación estructural y del DTI. Con
tests de reparto («este gasto cae en este período») se puede pasar la suite
entera con dinero desaparecido en los bordes.
**Solución:** el primer test del helper compartido no comprueba dónde cae cada
cosa, sino tres propiedades: que los períodos son CONTIGUOS (ni un día huérfano
ni contado dos veces), que `D = 1` degenera **byte a byte** en el mes natural, y
que la aritmética de Python y la de SQL —que existen las dos, porque una acota
y la otra agrupa— dan el mismo período para todos los días de un año.
**Regla:** un cambio que redefine una unidad temporal necesita tests de
PROPIEDAD antes que de caso. «La suma no se mueve», «los períodos son
contiguos» y «el caso degenerado es idéntico al anterior» se escriben en diez
líneas y cubren los bordes que nadie enumera. Y el de degeneración vale doble:
es lo que garantiza que quien no ha configurado nada no note nada — por eso 62
tests de presupuestos, proyección y estructura pasaron sin tocarles una línea.
Corolario: si tu cambio deja DOS implementaciones de la misma regla (aquí, una
en Python para acotar y otra en SQL para agrupar), el test que las ata no es
opcional — cuando divergen, el usuario ve dos cifras del mismo dinero y ninguna
avisa.

### [PHASE-47] Un guardarraíl que comprueba la PRESENCIA de algo no comprueba su EFECTO — y tres veces seguidas el mío se conformó con la presencia

**Error:** En una sola sesión escribí tres verificadores que no verificaban lo
que su nombre decía, y los tres pasaron en verde:

1. Un gate que exigía que una pantalla reanclara al período en curso… y lo
   comprobaba mirando si el fichero **mencionaba** `cycleAnchorContaining`. En
   las dos pantallas de Deuda la llamada estaba, citada y muerta: vivía en un
   manejador que otro manejador pisaba en el mismo evento.
2. Un test de la serie de deuda que sembraba en un bucket **intermedio**,
   cuando el único tramo que el defecto dejaba fuera era el final del ÚLTIMO.
   Sobrevivió intacto a la rotura.
3. El mismo gate, recorriendo sólo `apps/web`: las tres pantallas de móvil con
   el mismo defecto le eran invisibles.
   **Causa:** en los tres casos verifiqué que algo ESTUVIERA (una cadena, un
   bucket, un fichero) en vez de que HICIERA lo que promete. La presencia es fácil
   de comprobar con una regex o un assert genérico, y por eso es la trampa por
   defecto: el verificador se escribe en dos minutos, pasa a la primera y da la
   sensación exacta de estar cubierto.
   **Cómo se destaparon los tres:** rompiendo la línea concreta que cada uno decía
   proteger. Ninguno se cayó releyéndolo — se leen igual de bien estén ciegos o no
   —, y dos de los tres los encontró una revisión adversarial, no la suite.
   **Regla:** al escribir un guardarraíl, pregúntate qué forma tendría el bug si
   volviera y comprueba que tu verificación distingue esa forma de la correcta. En
   concreto: (a) si compruebas que una llamada existe, comprueba también DÓNDE
   está, porque el mismo código en un manejador o en un efecto es código muerto o
   código que corre; (b) si siembras datos para un caso de borde, siémbralos en el
   borde y no cerca; (c) si tu detector recorre ficheros, comprueba que recorre
   TODOS los que pueden tener el defecto — un gate en un paquete no ve el paquete
   de al lado. Y rómpelo siempre: el gesto de romper es el único que separa un
   guardarraíl de un adorno, pero **sólo si la rotura ENTRA** — una sonda que no
   encuentra su objetivo devuelve verde igual que un guardarraíl sano.
   **Corolario, cuarta instancia y la que da el método:** romper la línea que el
   gate protege HOY no basta, porque el defecto no vuelve por donde se fue. Un
   gate de texto hay que atacarlo **escribiendo las variantes plausibles y
   ejecutándolas**. Aquí una revisión adversarial escribió cuatro formas normales
   de reintroducir el mismo defecto —una lista nueva cuyo tipo se INFIERE del hook
   (así que ningún literal de tipo aparece en el fichero), una segunda tabla en la
   misma página, la tabla extraída a un componente que pierde un argumento por el
   camino, y un callback con la variable llamada `row` en vez de `tx`— y el gate
   dio **verde en las cuatro**. La lección práctica: si tu gate selecciona
   ficheros por una cadena, pregúntate qué fichero legítimo NO la contendría; si
   comprueba que una llamada existe, pregúntate qué pasa cuando hay dos sitios y
   sólo uno está bien. Y ojo con la selección: el mismo defecto puede vivir en un
   fichero que tu filtro no mira **porque usa otro tipo** — ahí no hay rotura que
   valga, el gate ni lo abre.

### [PHASE-47] «¿Qué período CONTIENE este día?» y «¿cuál EMPIEZA en este mes?» son dos preguntas, y confundirlas desplaza una serie entera

**Error:** La serie mensual de deuda se acotó con `user_month_bounds(months[0])`,
donde `months` son las anclas de los buckets — que viajan como día 1. Con un
corte en el día 13, el día 1 pertenece al período que abrió el mes ANTERIOR, así
que la ventana quedó desplazada un bucket entero: el ÚLTIMO salía a 0,00 €
siempre y sus movimientos se consultaban y se tiraban, mientras el KPI de la
misma pantalla sí los contaba.
**Causa:** una misma función respondía a dos preguntas que se parecen. Para un
día concreto («¿en qué período cayó esta transacción?») la correcta es
«contiene»; para un ancla `YYYY-MM` («¿qué período representa este bucket?») es
«empieza». Con el mes natural las dos coinciden —el mes que contiene el día 1 es
ese mes— y por eso la confusión es invisible hasta que existe un corte propio.
**Solución:** dos funciones con nombres que se leen distintos
(`user_month_bounds` / `user_month_bounds_for_anchor`) y la diferencia escrita
en el docstring de la segunda, con el fallo concreto que produce mezclarlas.
**Regla:** cuando una feature introduzca un desplazamiento (un mes que no
empieza el 1, una semana que no empieza el lunes), inventaría qué preguntas de
calendario hace tu código y sepáralas por lo que RESPONDEN, no por lo que
devuelven — aquí las dos devuelven `(date, date)` y el compilador no puede
ayudar. La señal de que hay dos preguntas: si con el caso degenerado (día 1)
ambas dan lo mismo, es que llevaban años siendo la misma por accidente.

---

## Ejemplos de referencia (no son lecciones reales)

### [Ejemplo] No usar float para importes monetarios

**Error:** Se usó `float` para almacenar precios.
**Causa:** Inercia — float es el default numérico en Python.
**Solución:** Cambiar a `Decimal(14,2)` en el modelo y `NUMERIC` en PostgreSQL.
**Regla:** SIEMPRE usar `Decimal` para cualquier dato monetario. NUNCA `float`.

### [Ejemplo] Query sin filtro de user_id

**Error:** Un endpoint devolvía transacciones de todos los usuarios.
**Causa:** Se olvidó añadir `.where(Transaction.user_id == user_id)` en el repo.
**Solución:** Añadir filtro y test que verifica aislamiento entre usuarios.
**Regla:** TODA query a tablas de dominio DEBE filtrar por `user_id`.
Añadir test de aislamiento multi-usuario.

### [PHASE-44.24] Una definición vive junto a la fórmula, y el gate se escribe en las DOS direcciones
**Error (evitado por diseño):** el informe pinta 64 métricas, 49 partidas y 8
scores con su valor, su unidad y su banda, y la única pista de qué era cada fila
era la etiqueta. La tentación era escribir las definiciones en la pantalla —es
donde se leen— y ahí está el mecanismo exacto que dejó **tres rótulos mintiendo**
en 44.9: dos fuentes para el mismo dato, y una miente antes que la otra. Una
definición miente **más fácil** que una etiqueta, porque nadie la contrasta con
el número que tiene al lado.
**Solución:** las 113 definiciones viven en el ENGINE, junto a la fórmula, y
viajan por el mismo catálogo que la etiqueta. Cuatro gates: cobertura en las
**dos** direcciones (una métrica sin ficha **y** una ficha huérfana), no
tautológica (que `why` no sea `what` reescrito), y **ningún umbral escrito a
mano** en la prosa — porque las bandas se calibran por sector desde 44.21 y un
corte en texto caduca en silencio.
**Regla:** cuando publiques una explicación de un cálculo, escríbela **donde vive
el cálculo** y hazla viajar; nunca en la pantalla que la pinta. Y el gate de
cobertura tiene que mirar en las dos direcciones: sólo «falta» deja entrar fichas
huérfanas que sobreviven al borrado de su métrica y siguen pareciendo vivas.

### [PHASE-44.24] Una regex de «no escribas el umbral en prosa» se comprueba con el ejemplo del propio documento que la pide
**Error:** el gate que prohíbe escribir cortes a mano en las definiciones buscaba
pistas de texto («por encima de», «al menos») seguidas de un número. El documento
de alcance de la fase traía como ejemplo de lo que hay que decir «holgado del
corte **−2,22**», y esa frase **pasaba el gate entera**: ni la pista estaba en la
lista ni el patrón numérico aceptaba signo.
**Causa:** escribir el detector con los casos que uno imagina en vez de con los
que ya están escritos delante. El texto de prueba estaba a mano y no se usó.
**Solución:** ampliar con el signo (`[−+-]?`) y las tres pistas que faltaban («del
corte», «corte de», «umbral de»), y comprobarlo contra la frase del documento.
En el gate hermano de las plantillas del veredicto (PHASE-44.24.B) se fue más
lejos: tras quitar los `{...}`, una plantilla **no puede contener ningún dígito**
— así se cazan «−2,22», «1,5» y «30 %» sin depender de cómo esté redactada la
frase que los rodea, que es justo lo que le fallaba a la versión por pistas.
**Regla:** cuando escribas un detector de texto, aliméntalo primero con los
ejemplos que ya existen en el repo (documentos de alcance, tests viejos,
comentarios) antes que con los que se te ocurran. Y si puedes sustituir una lista
de pistas por una propiedad estructural del texto —«aquí no puede haber dígitos»—,
hazlo: una propiedad no caduca cuando alguien redacta la frase de otra manera.

### [PHASE-44.24] Un test que verifica el guardarraíl NO puede compartir la razón por la que pasa con otro guardarraíl
**Error:** `sparklineOf` filtra los ejercicios sin número por DOS caminos: valor
ausente y estado (`not_computable` / `not_applicable`). La sonda que rompía el
filtro de ESTADO no mordía. Motivo: hoy el motor siempre empareja los dos —un
`not_applicable` sale con `value: null`—, así que el filtro de valor tapaba al de
estado y el test pasaba por un camino distinto del que decía medir. El mismo
patrón, tres veces más en la misma fase: dos guardas solapadas en `compare()` del
comparador de runs, y un fixture cuyos metrics estaban en orden ascendente, así
que sin el filtro por ejercicio el diccionario se quedaba **igualmente** con el
correcto.
**Solución:** en el primer caso, un `not_applicable` que TRAE número —el caso que
la calibración sectorial de 44.21 hace posible, porque apaga 33 métricas
dejándoles su valor—. En el segundo, dejar UNA sola guarda. En el tercero,
invertir el orden del fixture.
**Regla:** cuando una sonda no muerda, el hallazgo no es «el test es redundante»:
es que **hay otro camino al verde** y no sabes cuál de los dos protege. Busca el
segundo camino y elimínalo (una sola guarda) o rodéalo (un caso que sólo el
guardarraíl bajo prueba pueda salvar). Corolario de diseño: dos guardas
solapadas para la misma condición no son «defensa en profundidad», son un
guardarraíl que no se puede probar.

### [PHASE-44.24] Al mover una regla a una capa compartida, cuenta también las copias que NO existen todavía
**Error (evitado):** `SAFETY` estaba duplicada en `analysis-hero.tsx` y
`tab-verdict.tsx`, y las cinco reglas del perfil Conservador escritas a mano en
el segundo. Al llevar el veredicto a móvil, lo barato era copiarlas: habrían
quedado **cuatro** copias de lo que decide `_safety_profile` en el motor, y el
día que el motor añada una condición las cuatro mienten a la vez sin que nada
avise.
**Regla:** al evaluar si algo debe subir a la capa compartida, no cuentes las
copias que hay: cuenta las que habrá **después de la entrega que estás
haciendo**. Una duplicación que hoy es de dos y mañana de cuatro ya está pagando
su refactor. Y el criterio no es «esto es lógica»: una lista de qué se muestra,
en qué orden y con qué rótulo es tan compartible —y tan divergible— como una
fórmula (corolario de [PHASE-44.13]).

### [PHASE-44.24] Presentar juntos un cambio de la empresa y uno del método es peor que no comparar
**Error (de diseño, resuelto por construcción):** el comparador de dos análisis
podía listar «el Z''-Score pasó de verde a ámbar» con una nota al pie diciendo
«ojo, cambió el motor». Esa nota no funciona: el lector ya ha sacado la
conclusión —la empresa ha empeorado— y es la **contraria** a la verdadera, porque
lo que se movió fue el corte.
**Solución:** `comparable` es una **precondición y no una etiqueta**. Si el motor
o los umbrales difieren, el servidor no emite ni un solo cambio de empresa: las
listas vienen vacías por construcción, y la pantalla dice qué cambió del método.
Y cuando ADEMÁS cambian los ejercicios cubiertos, se dice explícitamente que las
dos causas se mezclan y no se pueden separar — sin esa frase, el usuario lee
«cambió el motor» y descarta un cierre nuevo que sí explica parte.
**Regla:** cuando una pantalla pueda atribuir un efecto a dos causas distintas y
una de ellas invalide la lectura de la otra, no lo resuelvas con un aviso:
**no emitas el dato**. Un aviso compite con el número y pierde. Corolario de
test: lo que hay que atar no es que la etiqueta aparezca, sino que las listas
estén VACÍAS — es la diferencia entre un guardarraíl y un adorno.

### [PHASE-44.24] Leer el `tail` de un log que ya existía es creerse una suite que nunca corrió
**Error:** di por verificada la pasada de copy con «1507 passed in 868.29s». El
comando era `tasklist … ; cd backend && pytest … > /tmp/be.log 2>&1; echo
"EXIT=$?"; tail -25 /tmp/be.log`. El `cd backend` **falló** (el shell ya estaba
ahí), el `&&` cortó, pytest **no se ejecutó** — y el `tail` imprimió el resultado
de una pasada anterior del mismo fichero. El `EXIT=1` estaba a la vista y lo leí
como ruido. Diez minutos después, una pasada dirigida encontró **tres tests
rotos** por esa misma pasada de copy.
**Causa:** dos cosas conocidas combinadas. `cmd | tail` ya está en este fichero
([PHASE-44.15]) por enmascarar el código de salida; lo nuevo es que **un log
reutilizado convierte una no-ejecución en un verde**, que es indistinguible de
un verde real. Y el `&&` no protegía porque lo que falló fue el `cd`, no el
comando cuyo resultado me importaba.
**Regla:** borra el fichero de salida ANTES de lanzar (`rm -f log; cmd > log`) y
haz que el propio comando escriba su código dentro (`echo "EXIT=$?" >> log`), de
modo que un log sin esa línea sea reconocible como «no terminó» en vez de como
«el resultado de antes». Y no uses `cd X && …` para un comando cuyo verde vas a
reportar: si el `cd` falla, la cadena entera se salta en silencio. Hermana de
[PHASE-44.14] «una revisión que no se ejecuta devuelve lo mismo que una limpia».

### [PHASE-44.24] Un `next(...)` sobre una condición que casa dos veces edita la primera, y la primera casi nunca es la tuya
**Error:** al actualizar dos assertions, el script buscó la línea con
`"falta la partida 'cogs'"`. Esa cadena aparece **dos veces** en el fichero: una
en un fixture que la construye a mano (línea 430) y otra en la assertion que yo
quería cambiar (línea 626). El `next()` devolvió la primera y sustituyó tres
líneas en medio de una llamada a función, dejando el fichero **sin compilar** —
que al menos falló ruidosamente.
**Causa:** la misma raíz que [PHASE-47.E] («un `replace(..., 1)` sobre un patrón
que aparece dos veces edita la función equivocada»), en su variante `next()`. La
tuve escrita, la había citado en esta misma sesión, y aun así el ancla no se
contó.
**Regla:** para editar por búsqueda, **cuenta primero** y falla si no hay
exactamente una coincidencia — con `next()` no hay aviso, hay silencio. Cuando
el texto se repita a propósito (un fixture que construye la cadena que otro test
afirma), el ancla tiene que incluir algo del contexto que sólo esté en tu línea.
Y desconfía del caso feliz: aquí salvó el día que el resultado no compilara; con
tres líneas de assertion en un sitio válido, el fichero habría pasado la sintaxis
y el test equivocado se habría relajado sin que nadie lo notara.

### [PHASE-44.24] Un enlace relativo de sólo query SUSTITUYE la query entera — y por eso el papel salía de otro análisis
**Error:** el botón «Dictamen imprimible» era `<a href="?print=1">`. Con la
pantalla en `?run=<id>&tab=veredicto`, ese href resuelve a `?print=1` a secas:
RFC 3986 §5.3 dice que una referencia con componente de consulta reemplaza la
query completa, no la fusiona. Resultado: el dictamen que se imprime es el del
análisis **más reciente**, no el que tienes delante — en un documento que existe
precisamente para archivarse y compartirse.
**Causa:** escribir el href como una constante porque «sólo añade un parámetro».
La intuición de que una query relativa se mezcla con la actual es falsa y no hay
nada en el tipo ni en el linter que lo diga.
**Solución:** componerlo desde `URLSearchParams(searchParams)` — y sacarlo a una
función PURA (`printHrefFor`) porque dentro de la ruta no se puede probar: la
página es un cliente con hooks de `next/navigation` y montarla exige un router
falso. Con la función fuera, el test afirma lo que importa («conserva `?run=`»).
**Regla:** todo enlace que «añade un parámetro» se construye sobre los params
actuales, nunca como literal — y si vive en una pantalla que no se puede
renderizar en un test, extrae la composición a una función pura antes de darla
por buena. Corolario: la prop que lo recibe debe ser OBLIGATORIA; con un valor
por defecto, montar el componente sin pasarla reintroduce el defecto en silencio
y el compilador no dice nada.

### [PHASE-44.24] Un booleano derivado de «lo que cargó ANTES» miente en cuanto añades una segunda fuente
**Error:** `noRunYet = !activeRun && !latestRun.isLoading` decidía el estado
vacío «todavía no se ha ejecutado ningún análisis». Era correcto mientras el run
saliera de una sola query. Al añadir el selector de histórico (`?run=<id>`),
`activeRun` pasa a venir de una SEGUNDA query, y mientras ésa carga —con
`latestRun` resuelto hace rato— el booleano da `true`: la pantalla anuncia que no
hay ningún análisis, y de paso desmonta el bloque donde vive el selector con el
que el usuario acaba de pulsar. Con un id inexistente se queda ahí para siempre.
**Causa:** el predicado nombraba una fuente concreta (`latestRun`) en vez del
concepto («¿está cargando el run que voy a enseñar?»). Al aparecer otra fuente,
la fórmula siguió compilando y siguió pareciendo razonable.
**Regla:** cuando un dato pase a poder venir de más de un sitio, revisa TODOS los
booleanos derivados que nombran una de las fuentes por su nombre — no los que
mencionan el dato. Y sepáralos: «cargando» y «no existe» son estados distintos y
el segundo necesita su propio mensaje y una salida, o el usuario se queda en un
vacío sin explicación. Hermana de [PHASE-47.E] «`campo !== null` marca todas las
filas cuando el servidor aún no manda el campo».

### [PHASE-44.24] Esconder el cromo con CSS de impresión lo deja VIVO en pantalla
**Error:** el modo dictamen (`?print=1`) fuerza la pestaña de Veredicto, y la
barra de pestañas se envolvió en `data-print="hide"`. Pero esa regla sólo actúa
dentro de `@media print`: en pantalla la barra seguía renderizada y clicable, y
pulsarla escribía un `tab` en la URL que `printMode` descarta después. La barra
decía una cosa y la página enseñaba otra.
**Regla:** si un modo de la pantalla **ignora** un control, no lo escondas: no lo
renderices. El CSS de impresión sirve para lo que el papel no necesita (un botón
que no se puede pulsar en papel), no para desactivar lógica. Corolario de test:
esto no lo ve jsdom —no evalúa `@media print`—, así que lo que se puede atar es
que el control no se renderice, no que el CSS lo esconda; declara esa limitación
en vez de fingir cobertura.

### [PHASE-44.24] Si el servidor se molesta en distinguir cuatro motivos, la pantalla no puede colapsarlos en uno
**Error:** `compare_runs` responde 404 con cuatro `detail` distintos («hacen
falta dos análisis», «ese análisis no pertenece a este valor», «es el más
antiguo», «no se puede comparar consigo mismo»). La UI recibía
`notEnoughRuns={comparison.isError}` —un booleano— y pintaba siempre «Hace falta
más de un análisis de este valor», que en tres de los cuatro casos es FALSO. Y
como cualquier fallo entra por la misma puerta, un 500 o la red caída también
salían como «no tienes suficientes análisis».
**Regla:** un booleano en la frontera con la API tira el motivo. Pasa el error (o
el texto ya formateado) y deja que el mensaje del servidor llegue al usuario —
esos `detail` están escritos en español y son user-facing precisamente para eso.
Y el test que lo ata no es «se pinta un aviso», es **«dos motivos distintos se
leen distintos»**: con un solo caso, la versión colapsada pasa igual.

### [PHASE-44.24.H] Un destino por defecto convierte «no sé adónde va» en un enlace que no lleva a ningún sitio
**Error:** `locateMetric(key)` devolvía `{ tab: 'veredicto', sub: null }` para
cualquier clave que no estuviera en el registro, con el razonamiento escrito al
lado: _«las banderas viven en el propio veredicto, que es donde el usuario ya
está; devolver `null` haría que la fila dejara de ser enlazable sin decir por
qué»_. Con eso, las 20 banderas y la señal de stress producían un `href` a la
**misma pestaña**: recargaba la página, cerraba el desglose que se estaba
leyendo y no resaltaba nada. Veintiuna señales que parecían enlaces rotos porque
lo estaban — y fue lo primero que el usuario vio en la prueba manual.
**Causa:** tratar «no tiene sitio» como un caso más del que sí lo tiene. El
fallback existía para que la función nunca devolviera `null`, y ese `null` era
exactamente la información que faltaba: sin destino no debe haber enlace.
Agravante: el comentario justificaba el defecto como decisión, así que leerlo
no lo destapaba.
**Solución:** `null` para lo que no vive en ninguna matriz; la fila se pinta
como texto. Y las derivadas dicen ADÓNDE exactamente (`highlight` con la fila
real, `anchor` para una card), porque «a Evolución» a secas aterrizaba sin
marca.
**Regla:** cuando una función de RESOLUCIÓN (¿dónde está X?) no sepa la
respuesta, que lo diga con `null`, y que el consumidor decida qué hacer con la
ausencia. Un valor por defecto «razonable» ahí es una afirmación falsa con
forma de dato — hermana de [PHASE-44.11] «un default es una afirmación
dormida». Y el test que lo ata no es «toda clave tiene destino» sino **«una
clave sin sitio devuelve null»**: con el fallback, el primero pasaba igual.

### [PHASE-44.24.H] Una card a `pageWide` no es una card: sin ancho de prosa, cada párrafo es una línea de 2.000 px
**Error:** el informe de Inversión heredó `layout.pageWide` (2.400) de PHASE-38
para que las matrices llenaran el monitor, y con él se fueron a 2.400 px las
cards de prosa: el Alcance, el Perfil, los avisos de cabecera de cada pestaña.
En la pantalla del usuario (2.178 px) una viñeta era una sola línea de borde a
borde. El resto de la app lo acotaba **a mano y a números distintos**
(480, 520, 480) en tres componentes de Deuda, así que no había nada que copiar
ni un sitio donde mirar.
**Regla:** el ancho de PÁGINA y el ancho de LÍNEA son dos tokens distintos.
Una página de datos va ancha; un párrafo dentro de ella no debe pasar de ~90
caracteres. `layout.prose` es el segundo, y va en los componentes COMPARTIDOS
de prosa (`InlineNotice`, `DegradedPanel`), no card a card — quince instancias
se arreglaron tocando dos ficheros. Corolario de test: se comprueba el ESTILO
calculado del párrafo, no que el fichero mencione `maxWidth`.

### [PHASE-44.24.H] El mismo defecto que arreglas en web hay que buscarlo en móvil ANTES de que lo encuentre el usuario
**Error:** la revisión adversarial de E/F/G encontró que en web elegir un
análisis del histórico desmontaba la pantalla y pintaba «todavía no se ha
ejecutado ningún análisis». Lo arreglé en web. Móvil tenía **el mismo código**
—`activeRun = selectedRunId ? selectedRun.data : …` con el histórico DENTRO del
bloque que exige `activeRun`— y se quedó igual hasta la auditoría siguiente:
tocar una fila hacía desaparecer hero, histórico y pestañas, y si el run
fallaba, para siempre.
**Regla:** cuando un arreglo sea de CABLEADO (precedencia, qué bloque monta
qué), grepea la misma forma en la otra app antes de cerrar. La paridad de
PANTALLA se mide con listas compartidas; la paridad de DEFECTOS no la mide
nada, y las dos apps se escribieron copiando la misma idea.

### [PHASE-44.24.H] Un MODO de pantalla no es una pestaña forzada: hay que apagar TODOS sus controles, no el primero que se vio
**Error:** el modo dictamen (`?print=1`) fuerza pestaña y sub-pestaña. La
revisión anterior ya había cazado que la barra de pestañas seguía renderizada y
la arregló — y la lección quedó escrita: «si un modo IGNORA un control, no lo
escondas: no lo renderices». En la MISMA pantalla quedaban otros tres controles
igual de vivos: el selector de secciones del veredicto (que además se imprimía),
los enlaces de las señales (que escribían una URL que el modo descartaba) y el
aviso de catálogo no cargado. Se arreglaron uno por uno en dos rondas.
**Causa:** aplicar la regla al control que la disparó en vez de al MODO. «Qué
controles ignora este modo» es una pregunta que se responde una vez y se
enumera; «este control está mal» se responde tantas veces como controles haya.
**Regla:** cuando introduzcas un modo que fuerza estado, **enumera todos los
controles que escriben ese estado** y decide para cada uno: no renderizar,
deshabilitar o dejar. Grepea quién llama al `setParam`/`onChange` de esos
params. Y el test va sobre el MODO («en modo dictamen no existe ningún control
de sección»), no sobre un control concreto.

### [PHASE-44.24.H] «Ya ha cargado» casi nunca es una query: es la pantalla
**Error:** el efecto que abre el diálogo de impresión esperaba a `activeRun` y a
`loadingRun`, que sólo cubre el run, el valor y el run seleccionado. El catálogo
de métricas, las fichas de score y las partidas canónicas son queries
independientes; con el backend en frío llegaban después, y el dictamen se
imprimía con el aviso «el catálogo no se ha podido cargar» y las filas
rotuladas con su clave técnica. En un documento que existe para archivarse.
**Regla:** antes de disparar una acción irreversible al «terminar de cargar»
(imprimir, exportar, capturar, medir), enumera TODAS las queries que alimentan
lo que se va a congelar, no las que tenías a mano en ese componente. Un
`timer` de gracia no sustituye a la condición: sólo hace que el fallo dependa
de la latencia del día.

### [PHASE-44.24.H] Un arreglo responsive que escala el dibujo escala también la letra
**Error:** el dumbbell de stress se recortaba por debajo de 700 px (SVG de 560
con `maxWidth:'100%'` y sin `viewBox`: encoge la caja, no el contenido). Le puse
`viewBox` + `width:100%` y quedó «responsive»… escalando los rótulos de 11 px a
5-6 px. Cambié un recorte por una ilegibilidad, y la solución correcta estaba a
dos ficheros de distancia: la heatmap usa ancho fijo con `overflow-x:auto`.
**Regla:** en un SVG con texto, `viewBox` + ancho fluido escala la tipografía
con el dibujo; sólo sirve cuando no hay texto o cuando el texto es HTML fuera
del SVG. Para un gráfico con rótulos, ancho fijo y scroll. Y antes de inventar
un arreglo responsive, mira cómo lo resuelve el componente hermano de la misma
pantalla.

### [PHASE-44.24.H] Un test que compara un registro consigo mismo es una tautología con forma de gate
**Error:** escribí `expect(locateMetric('fcf_trend')?.highlight).toBe('fcf_cfo')`
con el comentario «si el motor renombra la serie, el enlace aterriza sin marca y
nadie lo vería sin este test». No prueba nada: lee el registro y lo compara con
la constante que el propio registro declara. Si el motor renombra `fcf_cfo`, el
test sigue verde y el enlace sigue roto. Lo mismo con «una bandera no tiene
destino», que miraba dos claves escritas a mano en vez de las 20 reales.
**Solución:** el gate se mudó a donde viven las claves —el backend— y afirma la
relación CRUZADA: `fcf_cfo` está en `HORIZONTAL_ITEMS` del motor, y
`set(FLAG_LABELS) & set(ALL_METRIC_KEYS)` es vacío. En el frontend queda una
comprobación estructural (ninguna clave de pantalla tiene forma de bandera) que
sí puede fallar sola.
**Regla:** un test que sólo toca UN lado de una correspondencia no la ata.
Pregúntate qué otro fichero tiene que estar de acuerdo con éste, y escribe el
test donde puedas leer los dos. Si los dos lados están en repos o lenguajes
distintos, el gate va en el que tiene las claves REALES, no en el que las cita.
