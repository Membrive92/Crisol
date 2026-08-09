# Dónde estamos — 2026-08-09

Punto de continuación tras las sesiones del 7, el 8 y el 9 de agosto. Se lee de
arriba abajo; lo que hay que decidir está al final.

---

## Lo primero al retomar

**Hay trabajo terminado y SIN COMMITEAR: tres fases más.** Está verde en todas
las verificaciones automáticas, pero **falta tu prueba manual** — y la convención
del proyecto es no commitear hasta que la des por buena.

- **PHASE-44.17** — «lo que no se pudo medir, se dice». Las tres piezas
  contrastadas del plan (el motivo del ejercicio equivocado, la leyenda falsa del
  forense, el «denominador cero» de L4) **y** lo que estaba bloqueado: las reglas
  de bandera publican si se pudieron evaluar. Motor **1.4.0** y **1.5.0**.
- **PHASE-44.21** — calibración sectorial. Doce perfiles, la whitelist financiera
  con motivo por métrica, dos reglas cruzadas y las cuatro preguntas declarando
  sus portantes. Motor **1.6.0**. **Hay migración**: `alembic upgrade head`.
- **PHASE-44.22** — los tres charts del informe (web): heatmap de variaciones,
  deriva de la estructura de márgenes y dumbbell de stress. Sin backend.
- **Deuda mecánica saldada**: knip entra en CI (y `scripts/` en ruff/black/mypy),
  el sector se refresca al re-resolver, la tabla de cartera gana test, el alta
  móvil usa el date-picker nativo, el combobox arrastra la opción activa a la
  vista y en móvil el motivo por celda por fin se lee.

**Y sigue pendiente todo lo anterior de subir**: `origin/main` está en `d98c96f`
y el `main` local va muy por delante (PHASE-44.9 a 44.20 commiteadas y nunca
empujadas).

---

## Qué cambia de verdad en pantalla

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
