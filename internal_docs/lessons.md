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
no se "expira" tras commit, queda *stale* tras el flush con `onupdate`.
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
>30s (IA local, exports grandes, jobs síncronos) requiere subir `experimental.proxyTimeout`.
Si una petición "muere" exactamente a los 30s sin trazas en uvicorn, el sospechoso es
casi siempre el dev server.

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
con su motivo escrito — *"Las cards legacy (`BalancesCard`, `DebtHealthCard`) se
mantienen intactas porque siguen siendo válidas en `/dashboard`"*. Era cierto en
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
- `debt/service.resolve_period_end` — su docstring dice *"PHASE-30.8 — Fuente
  ÚNICA de verdad del as-of, compartida entre Capa 1 y Capa 2 para que los tres
  endpoints coincidan"*, y no la llama nadie. Verificado: `compute_debt_health`
  ni siquiera toma período (es snapshot de hoy) y `compute_debt_history` usa
  `months_back/ahead`. **El objetivo de diseño que declara la fase no está
  cableado.**
- `accounts/repository.get_net_savings_movement_for_account` — el doc de PHASE-32
  (HIGH#1) dice *"el ahorro neto de la principal es ahora display-only (`get_net_savings…`)"*.
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
