# Dónde estamos — 2026-09-02

Punto de continuación. Reescrito entero en la puesta al día documental del 2
de septiembre. Se lee de arriba abajo; lo que hay que decidir está al final.
Si llegas sin contexto, lee antes [`PROJECT-GUIDE.md`](PROJECT-GUIDE.md).

---

## Lo primero al retomar

**Todo está commiteado y subido**: `main` == `origin/main` (push del
2026-09-02, `ed27daf`), y `main` tiene ya upstream configurado, así que
`git status` avisará si vuelve a haber commits locales sin subir. Antes de ese
push, los cinco commits del 29 y 30 de agosto llevaban diez días sólo en esta
máquina — la segunda vez que pasaba (ya ocurrió con 44.9→44.20). No hay código
ni documentos pendientes.

**Lo que espera tu prueba manual** (verde en la suite, sin recorrer en la app
o recorrido sólo a medias):

| Área | Entregas | Commits | Estado de la prueba |
| --- | --- | --- | --- |
| Finanzas domésticas | [47.I](phases/phase-47.I-declarations-survive-reimport.md) · [47.J](phases/phase-47.J-a-statement-date-is-a-civil-date.md) · [48](phases/phase-48-the-user-defines-the-month.md) · [47.H 2ª](phases/phase-47.H-a-refund-is-not-income.md) · [47.E4](phases/phase-47.E-deferred-receipt.md) | `a6bd7aa` `c49ba05` `9b09c0f` `3784f59` | Sin recorrer |
| Inversión | [44.23](phases/phase-44.23-report-glossary.md) · 44.24 ([A](phases/phase-44.24.A-meaning-layer.md)…[H](phases/phase-44.24.H-ux-audit-fixes.md)) · [44.25](phases/phase-44.25-verdict-argues-its-why.md) · [44.26](phases/phase-44.26-dictamen-reads-top-down.md) | `2af80a4` `89ca390` `5af1f7a` | 44.24: **primera pasada hecha** (salieron 44.24.H y tres arreglos más); segunda pendiente. 44.25/44.26: sin recorrer |

**Lo planificado y sin código**: [44.27](improvements/phase-44.27-data-integrity-and-metric-coverage.md)
(dos auditorías + un bug vivo de datos) y [44.28](improvements/phase-44.28-annual-report-verdict-implementation-plan.md)
(el Veredicto como informe del ejercicio; plan aprobado por ti y pasado por
revisión adversarial — [acta](audits/2026-08-31-plan-44.28-adversarial-review.md)).
Orden: **44.27-E1** (la amortización parcial de MCD, que infla el
apalancamiento) es prerrequisito para leer MCD en 44.28. Y ninguno de los dos
empieza antes de tu prueba manual de 44.24/44.25/44.26 — regla escrita en el
plan de 44.27 §0.

### Verificado hoy contra la BD (2026-09-02, sólo lectura)

- **MCD y PEP tienen run con el motor actual (1.9.0, del 30-ago)** → el
  «Paso 0» del plan de 44.27 (relanzar MCD) está hecho. JNJ está en 1.7.0 y
  NKE en 1.6.0: relánzalos antes de comparar nada con ellos.
- Catálogo: JNJ, MCD, NKE, PEP. Directorio FIRDS sembrado.
- Tu ciclo está configurado en el **día 12**.
- Último extracto importado: **julio** (18-ago). **Agosto sin importar.**
- El abono de 700,26 € del 5-jul (`Recibo anterior jun-26 Otras
  financiaciones`, `TRANSFER_IN`) sigue **sin enlace declarativo** a su pasivo
  (ni par ni amortización). El par del 7-jul («Deuda contraída» / «Operación
  financiada») sí está emparejado.
- Las tablas de respaldo `_bak_civil_dates_20260822` y
  `_bak_civil_paid_at_20260822` siguen ahí.

---

## Cómo probar Finanzas domésticas

1. `.\dev.ps1` — **reinicia**: el backend en marcha puede ser anterior a estos
   cambios, y eso ya costó una sesión entera de diagnóstico.
2. Ajustes → «Modo predeterminado» desmarcado, día 12 → Guardar. La
   previsualización enseña qué cae a cada lado ANTES de guardar.
3. Análisis: el toggle es «Mes / Año / Personalizado», sin chip «Mi ciclo».
   Comprueba que cuadran entre sí la proyección de fin de mes (los días
   restantes cuentan hasta TU corte), los presupuestos, el DTI de Deuda y el
   chart.
4. Transacciones: un chip de mes da tu período (12 → 11), no del 1 al 31.
5. Análisis → una categoría con devoluciones (p. ej. «Suscripciones» en tu
   período de julio): el reembolso sale en verde, marcado «Devolución» y **con
   su signo**, y la columna suma lo mismo que el total de arriba. La misma
   marca aparece en «Top movimientos del periodo».
6. Análisis → junio, «Desglose de gastos»: las categorías con gasto aplazado
   llevan **asterisco** (hover para el importe), y el aviso de arriba cambia
   al pulsar Fijo o Variable porque describe lo que hay en pantalla.
7. Cuentas: el aviso de integridad del extracto (`statement_gap`) debe estar a
   0,00 en BBVA; si no, `make audit-balances` dice dónde.

Lo que verás distinto y es a propósito: el chart de Ingresos vs Gastos son
**12 barras de tu año** (12-ene → 11-ene); un solo aviso en Análisis de móvil
bajo la evolución de patrimonio (única tarjeta en meses naturales); un
reembolso con `+` en Transacciones (entró en la cuenta) y `−` en el desglose
de su categoría (deshace una compra).

## Cómo probar Inversión

Abre MCD (tiene runs de varios motores: sirve para ver que el informe tolera
lo que un run viejo no trae) y PEP (el mockup de 44.28 se compuso desde su
run real).

1. **Las fichas** — la `ⓘ` de cualquier fila abre qué mide, por qué importa y
   cómo se lee. En móvil, tocando la etiqueta.
2. **El Dictamen (44.26)** — la pregunta de aceptación: ¿se entiende de forma
   rápida qué está bien y qué riesgos, **sin abrir nada técnico**? Orden:
   cuatro preguntas → «Qué preocupa» (rojas primero, con distancia al corte y
   enlace) → «Qué está bien (sólo lo comprobado)» → escenario de stress → el
   contrafactual → la matriz plegada «La auditoría del sello».
3. **El porqué (44.25)** — la señal que decidió el sello va marcada
   (decisiva ≠ roja); el contrafactual dice qué haría falta para salir con
   `met` tri-estado, y para un run viejo dice «sin registro en este
   análisis» en vez de inventarlo.
4. **Tendencia y desglose de scores** — columna de tendencia en las matrices;
   en Forense cada score enseña sus variables y cuánto se movieron.
5. **Qué ha cambiado** — Veredicto → tercera sub-pestaña; con motores
   distintos NO debe listar ni un cambio de la empresa, sólo del método. El
   botón de comparar es un toggle.
6. **Dictamen imprimible** — botón del hero → `?print=1` → abre el diálogo
   solo, sin sidebar ni pestañas, conservando el análisis que mirabas.
7. Lo que más interesa: **si alguna frase suena a jerga del motor**. El
   catálogo de razones es largo y sólo se ve con datos reales delante.

---

## Lo siguiente, por orden

1. **Tu prueba manual** (arriba).
2. **Inversión**: 44.27-E1 (bug vivo de la amortización parcial) → 44.28 por
   entregas (plan §6, con el gate de cobertura anclado en claves y las
   familias de redundancia). Relanzar JNJ y NKE con el motor actual.
3. **Finanzas**: importar agosto · el clic «Es una financiación» para el
   abono del 5-jul · borrar las dos tablas `_bak_*` cuando des 47.J por bueno
   · **47.B (la bandeja)** sigue bloqueada por la **parada 2**, que es
   indelegable: un mes verde (mayo o junio con el extracto de la tarjeta
   donde toca) y calibrar `DEBT_QUOTA_MATCH_TOLERANCE_EUR`,
   `DEBT_QUOTA_DATE_WINDOW_DAYS` y `DEBT_CYCLE_TOLERANCE_EUR` con esos datos
   delante. Después, la liquidación anticipada
   ([plan](improvements/phase-48-debt-early-settlement.md)) — ojo con la
   numeración, ver decisiones.
4. **Orden obligatorio si se tocan datos**: arreglar → re-anclar → y sólo
   entonces reimportar.

---

## Decisiones abiertas

| # | Decisión | Recomendación |
| --- | --- | --- |
| 1 | **El plan de liquidación anticipada se llama PHASE-48** y PHASE-48 ya es «el mes lo define el usuario» (entregada). Dos cosas con el mismo número | Renumerarlo (PHASE-49) al abrirlo; el fichero lleva un aviso desde hoy |
| 2 | **¿Se adopta algún umbral del cuaderno?** ([divergencias](investment-threshold-divergences.md)) | Revisarlo con la calibración sectorial delante; hoy manda el motor |
| 3 | **Los cortes de C2 y C6** (inversión) | Esperar a tener más empresas: con cuatro no se distingue «el corte es bueno» de «no hay casos» |
| 4 | **Las dos verdades del saldo de deuda** (MUX cuadro-vs-movimientos de PHASE-36) | No se responde aquí; el plan de liquidación anticipada propone nombrarlas (`outstanding_principal` vs `pending_total`) |

---

## Deuda declarada

Vive en [`backlog.md`](backlog.md) — ése es el sitio durable; este fichero se
reescribe entero cada sesión. Lo punzante ahora mismo:

- **Inversión**: el 44.27-E1 es un bug de DATOS vivo (D&A parcial en MCD
  contamina cinco métricas); los runs de JNJ/NKE son de motores viejos.
- **Deuda**: dos residuos de la reorg (helpers de fecha a `core/dates.py`,
  re-exportar `converted_amount_expr`); F.2 subestima el solape con filas
  idénticas repetidas (deliberado).
- **Datos**: el enlace del abono de 700,26 €; agosto sin importar; las tablas
  `_bak_*`.

---

## Comprobado y cerrado (para no repetirlo)

- **Nunca dos `pytest` a la vez**: `crisol_test` es una sola base compartida,
  y eso incluye los que lance un subagente.
- **No encadenes con `&&` un comando cuya salida pase por `| tail`**: el
  código de salida es el de `tail`. Borra el log antes de lanzar.
- **jest-dom no está en el proyecto.** Los tests web usan `toBeTruthy()`.
- **`exactOptionalPropertyTypes` sigue mordiendo**: `prop?: T | undefined`.
- **El padre de una migración sale de `alembic heads`**, nunca del último
  fichero por orden alfabético.
- **`prettier --write <fichero>`**, nunca `pnpm format`.
- **El backend de desarrollo va en el puerto de `apps/web/.env.local`**
  (`BACKEND_ORIGIN`), hoy 8002 — `dev.ps1` lo deriva de ahí.
- **Una revisión adversarial se lee empezando por cuántos agentes murieron**:
  un resultado vacío o pequeño es indistinguible de una revisión limpia.
- **`git log origin/main..HEAD` antes de dar algo por subido**: `main` ya
  tiene upstream (desde el 2026-09-02), pero la costumbre de comprobarlo es
  lo que destapó los dos lotes de commits que se quedaron sin subir.

---

## Verificación completa

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q > /tmp/be.log 2>&1; echo "EXIT=$?" >> /tmp/be.log
cd backend && .venv/Scripts/python.exe -m mypy app/ scripts/
cd backend && .venv/Scripts/python.exe -m ruff check app tests scripts alembic
cd backend && .venv/Scripts/python.exe -m black --check app tests scripts alembic
cd backend && .venv/Scripts/python.exe -m alembic check
pnpm typecheck && pnpm lint && pnpm test && pnpm knip
python scripts/check_docs.py
```
