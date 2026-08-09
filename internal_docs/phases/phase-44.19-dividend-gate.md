# PHASE-44.19 — Las métricas que un gate escondía

**Estado**: ✅ código completo y verde · ⏳ pendiente prueba manual del usuario
**Fecha**: 2026-08-09
**Plan**: [`improvements/phase-44.17-metric-honesty-and-parity.md`](../improvements/phase-44.17-metric-honesty-and-parity.md) §5

## Objetivo

Recuperar ocho métricas que el motor ya calculaba —con valor y con banda— y que
la pestaña Dividendo escondía detrás de una sola etiqueta.

---

## 1. Una etiqueta para dos situaciones

`synthesis.py:520` devuelve `not_applicable` en dos casos distintos:

```python
if series.security.is_financial:
    return "not_applicable"          # ← un banco que SÍ reparte
...
if dividends is None or dividends == 0:
    return "not_applicable"          # ← no reparte
```

Y `tab-dividend.tsx` ocultaba la pestaña entera con esa etiqueta. Se perdían
**D1, D8, T2, T3** y —lo que menos sentido tenía— **Q1, Q2, Q3 y Q5**, la calidad
de la caja, que mide si el beneficio se convierte en caja y **no depende del
dividendo en absoluto**.

## 2. Qué se enseña ahora en cada caso

**No reparte**: la cobertura y la trayectoria no tienen nada que juzgar y se
declaran así, pero **la calidad de la caja se muestra**. Es el caso que más se
va a dar: cualquier tecnológica que no reparta.

**Financiera que reparte**: la pestaña ya no desaparece. El payout sobre
beneficio, la calidad de la caja y la trayectoria son válidos; las ratios sobre
caja libre se marcan sin calcular, con su motivo.

La pregunta «¿reparte?» se resuelve **contra el run** (`dps_series`) y no contra
la fila viva de `securities`: el run es la foto, y es lo que el usuario está
mirando. Es la misma regla que 44.16.

## 3. Lo que había que arreglar ANTES de dejar de ocultar

El motor **no tenía ninguna guarda** para financieras en la capa de dividendo:
calculaba D2–D5 y D8 dividiendo por caja libre, con banda y color. Mientras la
pestaña estaba oculta daba igual; al destaparla habrían salido **verdes falsos**,
que es peor que no enseñarlas.

Ahora se marcan `not_computable` con motivo, **copiando el patrón que D6 ya usaba
con las socimis** — listadas siempre, nunca omitidas (regla dura de
ARCHITECTURE §4.2).

Dos precisiones que salieron de leer el código y **corrigen el plan**:

- **D8 también divide por caja libre** (`(caja libre − dividendos) / ventas`),
  pese a que su nombre —«margen de seguridad»— no lo sugiere. El plan la daba
  por válida para un banco. No lo es.
- **D1 sí es válida**: divide por *beneficio*, no por caja. Es contable y
  significa lo mismo en un banco que en una fábrica. Si se hubiera eximido
  también, la pestaña habría quedado vacía y no habríamos arreglado nada.

## Archivos clave

- `engine/dividend.py` — `NOT_APPLICABLE_TO_FINANCIALS_CASH` + el envoltorio
  `cash_based()` sobre D2, D3, D4, D5 y D8
- `apps/web/components/investment/tab-dividend.tsx` — fuera el gate; los tres casos

## Verificación

- Backend: `ruff` · `black` · `mypy` (219 ficheros) · suite completa.
- Frontend: `typecheck` · `lint` · 3 tests nuevos de la pestaña.
- **Los detectores, probados rompiéndolos**: con el gate viejo reintroducido caen
  2 de los 3 tests web; el test del engine afirma además que D1 **sigue**
  calculándose en un banco, para que «arreglarlo» apagándolo todo no cuele.

## Efecto sobre los datos del usuario

**Ninguno visible hoy, y conviene decirlo claro**: el catálogo tiene dos valores
(JNJ y MCD), ninguno es financiera y los dos reparten. Así que esta fase es
**enteramente latente** y no se puede comprobar a ojo con lo que hay. Se activa
al analizar un banco —Santander es alcanzable desde PHASE-44.15— o una empresa
que no reparta.

## Limitaciones conocidas

- **Q2 y Q3 también se apoyan en caja libre** (conversión FCF/EBITDA y
  divergencia FCF dual) y NO se han eximido para financieras. Es una decisión
  deliberadamente conservadora: la calidad de la caja es justo lo que esta fase
  viene a rescatar, y apagarla en el mismo commit habría sido quitar con una mano
  lo que se da con la otra. Merece una decisión de dominio aparte.
- El motor **no cambia de versión**. La huella de salida no se mueve (mismas
  claves, mismos campos) y no hay ninguna financiera analizada, así que ningún
  run existente cambia de significado. Si se analizara un banco con un run
  anterior a esta fase, sus D2–D5/D8 serían números sin sentido y nada lo
  declararía — el aviso de run caducado de 44.16 sólo salta con cambio de
  versión. Es aceptable porque el caso no existe todavía, pero es una premisa que
  caduca: **si se añade una financiera antes de tocar la versión, hay que
  reejecutar su análisis**.

## Próxima fase

PHASE-44.17, que necesita rediseño: su crítica adversarial encontró ocho
problemas de severidad alta (ver §3.1.b del plan).
