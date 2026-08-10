# Dónde estamos — 2026-08-10

Punto de continuación tras las sesiones del 7 al 10 de agosto. Se lee de
arriba abajo; lo que hay que decidir está al final.

---

## Lo primero al retomar

**La decisión abierta, y es de diseño, no de código.** Al cerrar la sesión del 10
dijiste: *«seguimos teniendo el mismo problema de fondo, el manejo del módulo es
demasiado complicado»*, y vas a estudiar una solución por tu cuenta. Lo que se
midió ese día, para que la conversación arranque con datos:

- **6 cuentas de pasivo y 5 cuadros de amortización (177 cuotas)** para lo que en
  la vida real son un préstamo, una tarjeta y tres compras a plazos.
- **45 de 479 movimientos** (uno de cada diez) no son ni gasto ni ingreso: para
  leer un mes hay que saber por qué está cada uno.
- **Diez operaciones distintas** para gestos que en la cabeza del usuario son
  uno: enlazar, deshacer, convertir en transferencia, convertir en operación
  financiada, es una amortización, deshacerla, recategorizar en bloque,
  reconciliar deuda, reasignar cuenta y cuadrar saldo.
- Las **seis correcciones** que hicieron falta ese día para dejar julio bien
  **no se podían hacer desde la interfaz**.

Las tres direcciones que quedaron sobre la mesa (sin decidir): el **cuadre del
extracto como portero del import**, que la **deuda nazca del extracto** en vez
del formulario, y **un solo gesto** «¿qué es este movimiento?» en la transacción.
Pregunta de fondo anterior a todas: si el saldo de la deuda necesita las **dos
verdades** (cuadro vs. movimientos) del MUX de PHASE-36.

**Todo lo anterior está commiteado y en `origin/main`**, incluidas PHASE-45 y
PHASE-46, a petición tuya y **sin prueba manual completa**.

- **PHASE-46 — la deuda que nace no es un ingreso.** Julio tenía 700,26 € de
  ingreso que nadie cobró (el 100 % del ingreso del mes) y otros 700,26 € de
  gasto que doblaba compras ya contadas. Ver
  [`phases/phase-46-financing-is-not-income.md`](phases/phase-46-financing-is-not-income.md).
- **PHASE-45 — «Es una amortización».** Un `ADEUDO MENSUAL DE TARJETA` sacaba el
  dinero de BBVA y **no tocaba el módulo de deuda**: no existía ningún gesto para
  decir «esto paga esta deuda». Panel nuevo en el detalle de transacción (web y
  móvil) que lo enlaza. **Hay migración**: `alembic upgrade head`.
- **PHASE-44.17** — «lo que no se pudo medir, se dice». Motor **1.4.0** y **1.5.0**.
- **PHASE-44.21** — calibración sectorial. Motor **1.6.0**.
- **PHASE-44.22** — los tres charts del informe (web).

---

## Estado de los datos tras la sesión del 10 (finanzas domésticas)

Julio quedó cuadrado, pero hizo falta cirugía. Lo que hay que saber:

| | |
|---|---|
| Ingresos julio 2026 | 2.529,68 € |
| Gastos julio 2026 | 1.952,31 € (BBVA 1.343,17 + tarjeta 609,14) |
| Saldo BBVA | 1.778,19 € — idéntico al extracto del 30-07 |
| Saldo Tarjeta BBVA credito | 926,48 € |
| Transacciones sin clasificar | 0 en toda la app |

**Origen del lío:** `julio criedito.pdf` (extracto de la TARJETA) se importó
eligiendo la cuenta **BBVA**. Sin un solo error: 19 filas OK. La señal que lo
delató fue comparar meses — mayo 7 compras en la tarjeta, junio 7, **julio 0**.

**Queda un clic pendiente**: en Transacciones hay una propuesta para atar
`06/07 · Operación financiada · 700,26 €` con la deuda
`Compra finaciada recibo junio`. Ya no cuenta como ingreso; lo que falta es que
la deuda tenga registrado el movimiento que la originó.

**Y un descuadre de 1,50 €**: `Reembolso maxima netflix` lleva seis meses
entrando como ingreso en `Bonus tarjeta de credito` y el de julio entró como
gasto en `Suscripciones`.

Los tres scripts de `backend/scripts/` que se usaron llevan `--dry-run`:
`undo_card_statement_into_bank.py`, `move_import_to_account.py` y
`classify_from_statement_balance.py`. El segundo sirve para cualquier futuro
fichero que se cuele en la cuenta equivocada.

---

## PHASE-45 — qué probar (finanzas domésticas)

En **Transacciones → una salida de dinero sin emparejar** aparece un bloque nuevo
**«¿Es una amortización?»**. Los cuatro cargos de julio son el caso real:

| Fecha | Importe | Concepto |
|---|---|---|
| 08-jul | 406,33 € | Adeudo mensual de tarjeta |
| 08-jul | 384,38 € | Adeudo mensual de tarjeta |
| 15-jul | 164,94 € | Adeudo mensual de tarjeta |
| 15-jul | 143,99 € | Adeudo mensual de tarjeta |

Abre uno, elige la deuda y **antes de confirmar** el panel te dice qué va a
pasar: cuántas cuotas marca (o que crea la contrapartida), cuánto capital
amortiza de verdad y a cuánto se queda la deuda. Después eliges si cuenta como
gasto, con la sugerencia razonada al lado.

Lo que conviene comprobar con los ojos:

1. **Con la tarjeta** (sin cuadro): sugiere **«No, es neutro»** porque tiene
   compras registradas — y lo dice contando cuántas. La deuda baja por el importe
   entero.
2. **Con el préstamo** (con cuadro): sugiere **«Sí, es gasto»**, marca cuota(s) y
   la deuda baja por el **capital**, no por lo pagado. Si el número que ves es el
   del pago, hay un bug.
3. **Un pago pequeño contra el préstamo** sale con aviso: «no llega a completar
   la cuota más antigua, la deuda no bajará». Es correcto, no un fallo.
4. **Deshacer** devuelve la deuda a su valor anterior. La contrapartida creada
   aparece en la papelera.
5. Cruza el resultado con **/debt** y con el saldo de la cuenta: tienen que
   coincidir (salen del mismo cálculo, pero es lo que ningún test puede mirar).

---

## Qué cambia de verdad en pantalla (inversión)

Lo que sigue se ve **reejecutando un análisis**; los runs guardados son de
motores anteriores y saldrán con el aviso de run caducado (que es correcto).

1. **Los motivos de los huecos dejan de mandar a ingerir historia.** En
   McDonald's, el M-Score decía «sin ejercicio 2020» —el primer año de la
   serie— cuando lo que falta en 2022-2025 es el coste de ventas. Ahora manda el
   ejercicio más reciente, y si los motivos difieren se declara.
2. **La leyenda del bloque forense sale del run**, no de una frase escrita a
   mano que era falsa para McDonald's en los cinco ejercicios. Sin huecos, no se
   pinta nada.
3. **No tener deuda a doce meses ya no es un hueco**: es el mejor resultado
   posible del muro de vencimientos. Verde si el cero lo publica la empresa, sin
   banda si lo supone la ingesta — el verde se gana.
4. **«No se ha encendido» sólo se dice cuando se ha comprobado.** Una regla que
   abortaba por falta de un dato producía la misma ausencia que una limpia; ahora
   dice «no se ha podido comprobar: falta el coste de ventas».
5. **Los contadores separan lo limpio de lo que no se pudo.** Donde MCD decía «7
   sin poder evaluar» había 2 huecos reales y 5 banderas comprobadas y limpias.
6. **Las cuatro preguntas pueden salir «No auditada»** (gris) con la lista de lo
   que falta: sin un portante, el veredicto no se sostiene aunque el resto esté
   verde.
7. **Los umbrales dependen del sector.** Latente con tu catálogo actual —JNJ es
   healthcare y MCD consumo discrecional, ninguna es banco ni eléctrica—, pero
   MCD sí toca banda: su perfil relaja el ratio corriente (0,8/1,2) y JNJ gana el
   corte de fondo de comercio de healthcare (0,40/0,60).

---

## Estado de verificación

**Todo verde**, con el intérprete del proyecto (`.venv`, el mismo que CI):

- Backend: la suite completa · `ruff` · `black` · `mypy` · migración
  `upgrade`/`downgrade` reversible, cabeza única (`g3c95b7d2e8f41`), `alembic
  check` sin drift. Los recuentos exactos salen de la verificación de abajo; las
  cifras de cada fase están en su phase doc, que sí es una foto fechada.
- Frontend: `typecheck` · `lint` · `knip` · los tests de web, móvil, services, ui
  y store.
- `python scripts/check_docs.py` sin podredumbre.
- Los **gates nuevos probados rompiéndolos**: la huella del motor con dominios
  `Literal` (añadir un valor a `Band` la tumba), la cobertura de evaluaciones de
  bandera (quitar la de C3 la tumba) y la regla del motivo más reciente.

**Lo que NO se ha verificado**: tu prueba manual, y el CI de GitHub Actions (`gh`
sigue sin estar instalado en esta máquina).

---

## Lo siguiente, por orden

### 1. Probar (es el paso que bloquea el commit)

```bash
docker compose up -d
cd backend && .venv/Scripts/python.exe -m alembic upgrade head
cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8002
pnpm dev:web
```

El backend va en **8002**, no en 8000.

**Reejecutar MCD y JNJ** es la prueba principal, y de paso cierra la de 44.16:
abre `/investments` → el valor → Análisis → «Volver a ejecutar».

En McDonald's, después de reejecutar:

- En **Forense**, la leyenda de la matriz debe nombrar los ejercicios REALES sin
  dato y su motivo — y si no hay huecos, no debe aparecer.
- La fila del M-Score no puede decir «sin ejercicio 2020»: el motivo que manda es
  el del último ejercicio.
- En **Veredicto**, alguna de las cuatro preguntas puede salir **«No auditada»**
  con la lista de lo que falta. Es lo esperado, no un fallo: antes salía verde.
- El desglose de cada pregunta debe decir «N comprobadas y limpias» además de las
  evaluadas.
- En **Ratios**, si la empresa no tiene deuda a doce meses, el muro de
  vencimientos sale `n/a` con su explicación en vez de un guión.

**Contraste que lo prueba**: el aviso de run caducado desaparece al reejecutar, y
el veredicto de alguna pregunta cambia. Si nada cambia, algo no se ha aplicado.

**Los tres charts nuevos, mirándolos** (pestaña Evolución y Veredicto → Dictamen).
Es el paso que no puedo dar yo: están tipados y con tests, pero nadie los ha
visto renderizados. Lo que hay que buscar es colisión de etiquetas, desbordes, y
que el nombre al final de cada línea de la deriva no se salga del lienzo.

**Precios de 44.11 contra tu bróker** — sigue pendiente y no es delegable.

### 2. Commit

Cuando des el visto bueno. Mensaje en inglés, `— Refs: PHASE-44.17` y
`PHASE-44.21` (son separables en dos commits).

### 3. Refrescar el directorio, cuando toque

```bash
cd backend && .venv/Scripts/python.exe -m scripts.seed_listing_directory
```

Manual, trimestral o a demanda. **Sin cron** (local-first).

---

## Decisiones abiertas

Las dos que quedaban del plan de calibración están **cerradas** por el documento
que añadiste (Q2 y Q3 en financieras: las dos `applies=false`; y los portantes en
vez de una proporción). Quedan:

| # | Decisión | Recomendación |
|---|---|---|
| 1 | **¿Se adopta algún umbral del cuaderno?** Ver [`investment-threshold-divergences.md`](investment-threshold-divergences.md). Ahora hay una capa sectorial donde encajarlos | Revisarlo con la calibración v1 delante, no antes |
| 2 | **¿ETFs en el directorio?** Ya decidido que no ahora | — |
| 3 | **Los cortes de C2 y C6.** Medidos contra tu BD el 2026-08-09 y anotados en el backlog: C2 tiene su primer caso concreto (JNJ 2023 y 2025, beneficio +90% con caja plana) y C6 está **dormida** porque tus dos empresas recompran | Esperar a tener más empresas; con dos no se distingue «el corte es bueno» de «no hay casos» |

---

## Deuda declarada

**Vive en [`backlog.md`](backlog.md), sección «Módulo Inversión»** — ése es el
sitio durable. Este fichero se reescribe entero cada sesión.

Lo más punzante, para no tener que abrirlo:

- **El delta de S7 para intangibles queda CERRADO sin cambio**: JNJ sale 1,44-1,52,
  verde dentro de la banda del cuaderno los cinco ejercicios, así que la
  advertencia que lo pedía no muerde en nada de tu catálogo.
- **La calibración sectorial es v1 y casi toda latente**: no hay ninguna
  financiera ni ninguna eléctrica en tu catálogo, así que la parte más trabajada
  (la whitelist bancaria) no se ve hasta que analices una. Los goldens son
  sintéticos por eso.
- **Suiza es frontera documentada**: SIX no reporta a FIRDS.
- **Sin charts en el informe**, ni en web ni en móvil.
- El **alta `ext:` exige red** (resolución del símbolo + cotización real).

---

## Comprobado y cerrado (para no repetirlo)

- **La huella del motor no veía los `Literal`.** Comparaba nombres de campo de
  dataclass, así que un estado nuevo en `MetricStatus` no la movía. Ya los
  incluye.
- **Nunca dos `pytest` a la vez**: `crisol_test` es una sola base compartida, y
  eso incluye los que lance un subagente.
- **jest-dom no está en el proyecto.** Los tests web usan `toBeTruthy()`.
- **`exactOptionalPropertyTypes` sigue mordiendo**: una prop opcional que vaya a
  recibir `undefined` explícito se declara `prop?: T | undefined`.
- **El índice de emisores no hace red.** En los tests está VACÍO por defecto.
- **Las fechas históricas de Frankfurter tardan 13-17 s.** No es un fallo de red.
- **FIRDS reporta en MICs de SEGMENTO**, no operativos.

---

## Verificación completa

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q    # ~13 min
cd backend && .venv/Scripts/python.exe -m mypy app/
cd backend && .venv/Scripts/python.exe -m ruff check app tests scripts
cd backend && .venv/Scripts/python.exe -m black --check app tests scripts
pnpm typecheck && pnpm lint && pnpm test && pnpm knip
python scripts/check_docs.py
```

Nunca dos `pytest` a la vez. Y no encadenes con `&&` un comando cuya salida pase
por `| tail`: el código de salida es el de `tail`, así que el `&&` deja de
proteger y puedes acabar con dos suites a la vez sin enterarte.
