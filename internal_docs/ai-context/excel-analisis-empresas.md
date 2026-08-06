# Transcripción — «Analisis empresas.xlsx» (metodología del usuario)

> Fuente: `internal_docs/improvements/Analisis empresas.xlsx` (sin versionar en
> git). Este documento es la **transcripción fiel** del cuaderno: 10 pestañas,
> su texto, sus umbrales y el contenido de las 15 imágenes incrustadas (que no
> son decorativas — la pestaña «Valoracion de empresas» está hecha **sólo** de
> imágenes).
>
> **Qué es el cuaderno**: una guía de metodología, no un modelo con datos. No
> tiene ni una fórmula viva sobre cifras de empresa; las únicas fórmulas son dos
> filas de *check* de DuPont (`=(margen×rotación×apalancamiento) − ROE`, que
> deben dar 0). Las celdas de datos están vacías y las series de los 10 gráficos
> apuntan a un libro externo del escritorio del usuario
> (`\Users\membr\Downloads\Ejemplo Modelo de Dupont.xlsx`, hojas `2016-2020`,
> `Modelo Dupont`, `Modelo Dupont Extendido`).
>
> **Para qué sirve aquí**: es el índice de lo que el usuario quiere ver en
> pantalla y en qué orden lo lee. Los umbrales que declara son SUYOS y pueden
> discrepar de los 1.440 sembrados en `scoring_thresholds` — cuando discrepen,
> mandan los del motor y se documenta la diferencia.

---

## Índice de pestañas

| # | Pestaña | Naturaleza |
|---|---------|-----------|
| 1 | Glosario y fórmulas | Definiciones de los 3 estados + FCF/EBITDA/EBIT/CAPEX + tabla de fórmulas |
| 2 | Balance | Estructura del balance por epígrafes + «Vigilar» |
| 3 | Cuenta de resultados | Estructura en 5 bloques + «Vigilar» |
| 4 | Flujo de Caja | Las 3 actividades + «Vigilar» |
| 5 | Deuda | Medición de deuda, FCF puritano vs mantenimiento, working capital + «Vigilar» |
| 6 | Ratios Liquidez | 3 ratios con rango mínimo y óptimo |
| 7 | Ratios de actividad | 4 rotaciones en días (×365) |
| 8 | Ratios de solvencia | 4 ratios con rangos |
| 9 | Ratios de Rentabilidad | 5 ratios + DuPont 3 factores + DuPont extendido 5 factores |
| 10 | Valoracion de empresas | Múltiplos por capitalización y por EV + valoración por múltiplos + DDM Gordon |

---

## 1. Glosario y fórmulas

### Tabla de fórmulas (columnas I:K)

| Estado financiero | Métrica | Fórmula |
|---|---|---|
| Estado de Resultados | Utilidad Bruta (Gross Profit) | Ingresos − Costos de Ventas |
| Estado de Resultados | Utilidad Operativa (Operating Income) | Utilidad Bruta − Gastos Operativos |
| Estado de Resultados | Utilidad Neta (Net Income) | Ingresos − Costos de Ventas − Gastos Operativos − Otros Gastos + Otros Ingresos |
| Balance | Activos Totales | Activos Corrientes + Activos No Corrientes |
| Balance | Pasivos Totales | Pasivos Corrientes + Pasivos No Corrientes |
| Balance | Patrimonio de los Accionistas | Activos Totales − Pasivos Totales |
| Flujo de Efectivo | Operating Cash Flow | Ingresos Operativos − Gastos Operativos − Impuestos Pagados |
| Flujo de Efectivo | Investing Cash Flow | Flujos por Compra/Venta de Activos a Largo Plazo |
| Flujo de Efectivo | Financing Cash Flow | Flujos por Emisión/Reembolso de Deuda y Capital |
| — | Flujo de Efectivo Neto | Operativo + Inversión + Financiación |
| — | EBITDA | Ingresos − Gastos Operativos + Depreciación + Amortización |
| — | EBIT | Ingresos − Gastos Operativos |
| — | CAPEX | Adiciones a Activos Fijos + Mejoras en Activos Existentes |
| — | Free Cash Flow | Flujos de Caja Operativos − CAPEX |

### Ecuación fundamental

```
Activos Totales = Pasivos Totales + Patrimonio de los Accionistas
Utilidad Neta = Ingresos − Costos de Ventas − Gastos Operativos − Otros Gastos + Otros Ingresos
Flujo Neto = Operativo + Inversión + Financiación
```

### Tipos de CAPEX (distinción que el usuario subraya)

- **CAPEX de crecimiento**: expandir capacidad, nuevos mercados, nuevos
  productos, mejoras significativas. Orientado a ingresos futuros.
- **CAPEX de mantenimiento**: sostener la capacidad actual, reparaciones,
  renovación, actualización de sistemas obsoletos. No genera ingresos
  adicionales.
- **Por qué importa**: evaluar rentabilidad (cuánto va a crecer vs mantener),
  gestión de activos, y proyecciones de caja — el de mantenimiento es
  recurrente y obligatorio, el de crecimiento es opcional.

### Importancia del FCF (según el cuaderno)

Indicador de salud financiera · capacidad de pagar dividendos · capacidad de
reducir deuda · capacidad de reinvertir sin financiación externa · base de la
valoración por DCF.

---

## 2. Balance

Estructura tal cual la ordena el usuario:

```
Activos
  Activos Corrientes
    Existencias - inventarios
    Cuentas a cobrar
    Activos financieros corrientes
    Caja
    Total activos corrientes
  Activos No corrientes
    Propiedades, fábricas, terrenos
    Fondos de Comercio
    Intangibles
    Impuestos diferidos

Pasivos
  Pasivos Corrientes
    Deuda a largo plazo que caduca
    Deuda a corto plazo
    Cuentas por pagar
    Alquileres del año
    Total Pasivos corrientes
  Pasivos No corrientes
    Deuda a largo plazo
    Alquileres a largo plazo
    Impuestos diferidos

Equity (parte de la empresa no hipotecada)
  Primas de emisiones
  Ganancias retenidas (crece mejor)
  Acciones compradas al coste

Total Activos · Total Pasivos · Equity · Resultado
```

**Vigilar:**
- Inventarios y ventas deben ir a la par.
- Deuda es deuda, hay que pagar.
- Ojo a la relación de corrientes (ingresos y gastos), que haya liquidez.
- Fondos de comercio e intangibles.
- Vigilar beneficio no distribuido.

---

## 3. Cuenta de resultados

Cinco bloques, cada uno con su Total:

| Bloque | Partidas |
|---|---|
| **Margen bruto** | Ventas totales · Coste de ventas · Total |
| **Operativa (EBIT)** | Gastos administrativos, ventas, publicidad · Gasto I+D · Depreciaciones y deterioros · Ganancias venta negocios · EBIT · Total |
| **Financiera** | Resumen de gastos financieros · **Límite de pago de intereses sobre EBIT** · Total |
| **Impositiva** | Impuestos de empresas · *(Warning)* Mejorar BPA a costa de pagar menos impuestos · Total |
| **Corporativa** | Acciones básicas (emitidas) · Diluidas (opciones) · *(Warning)* si hay mucha diferencia entre básicas y diluidas · Si diluidas son mucho mayores, cuidado · Total |

**Vigilar:**
- Ventas planas o decrecientes.
- Deflación en ventas.
- Vigilar acciones diluidas.
- Depreciaciones y amortizaciones **son un gasto**.
- Si habla de EBITDA no habla de BPA ni de FCF.
- Presentaciones con beneficios ajustados.

---

## 4. Flujo de Caja

| Bloque | Partidas |
|---|---|
| **Operativa** | Depreciaciones y amortizaciones · Variaciones de inventario · Circulación de dinero · Total |
| **Inversión** | Capex y partidas de crecimiento orgánico · Ventas de partes de empresas / compras de empresas · Total dinero invertido (para ver si nos endeudamos en exceso) · Total |
| **Financieras** | Cambio en deuda · Dividendos · Recompra de acciones · Ampliaciones de capital no liberadas · Movimiento de dinero · Total |

**Vigilar:** variaciones extrañas en flujos operativos · inventarios · deuda ·
acciones emitidas, compradas y recompradas · ampliaciones liberadas ·
adquisiciones.

---

## 5. Deuda

| Concepto | Contenido |
|---|---|
| Divisa | En qué divisa se recibe y se paga la deuda |
| Deuda / fondos propios | Relación deuda-fondos propios. Vigilar intangibles y fondos de comercio |
| Deuda según pago de intereses | Que los intereses no se coman el beneficio. **EBIT como rango: no más del 20%** (revisar por sector) |
| Calendario de deuda | Vigilar pagos de intereses en el vencimiento |
| Medir deuda | **Deuda Neta / EBITDA** — favorece a empresas con amortización y depreciación; *el más usado*. **Deuda Neta / EBIT** — penaliza a intensivas en capital; *más restrictivo* |
| Cálculo de deuda neta | Deuda a largo plazo + deuda de largo en pasivos corrientes − efectivo o equivalentes. Mirar inventarios (¿se deprecia el producto?) y pasivos no corrientes (intereses a pagar) |
| FCF | «Dinero que nos queda, liquidez». **FCF = EBITDA − intereses − Capex − Impuestos** |
| FCF puritano | No separa CAPEX total del de mantenimiento. Da errores cuando la empresa crece o deja morir un negocio |
| FCF de mantenimiento | Se calcula el CAPEX de mantenimiento y es el que se resta. **Recomendado** |
| Fondo de maniobra | Mirar cuándo hay variaciones: cuando la empresa crece baja, cuando decrece sube |
| Working capital | Inventarios + receivable − payable. **No añadir efectivo** |
| Pago a directivas | Mirar la cantidad; si está muy escondido, es grande |

**Vigilar:**
- No más del **20 % del EBIT** en intereses de deuda.
- Deuda **no más de 3,5 × EBIT**.

Imagen incrustada: `Relación Deuda/EBIT = Deuda Total / EBIT`.

---

## 6. Ratios de Liquidez

> «Miden solvencia de la empresa»

| Ratio | Fórmula | Rango |
|---|---|---|
| **Ratio entre corrientes** (current ratio) | Activos corrientes / Pasivos corrientes | Mínimo 1 · **ideal 1,5–2**. Si < 1, prestar atención y buscar por qué |
| **Test ácido** (quick ratio) | (Activos corrientes − Inventarios) / Pasivos corrientes | Mínimo **0,8** · óptimo **1,5** |
| **Ratio de efectivo** (cash ratio) | Efectivo / Pasivos corrientes | Mínimo **0,2** · óptimo **0,3** |

---

## 7. Ratios de actividad

> «Eficiencia de la gestión al producir productos y servicios. Se mide en días
> o en número de veces.»

| Ratio | Fórmula | Criterio |
|---|---|---|
| **Ratio de activos** (cuánto tardan los activos en convertirse en venta) | (Activos totales / Ventas) × 365 | Cuanto más bajo, mejor |
| **Rotación de inventario** | (Inventario / Coste de ventas) × 365 | Cuanto más bajo, mejor |
| **Rotación cuentas por cobrar** (DSO) | (Cuentas por cobrar / Ventas) × 365 | Cuanto más bajo, mejor |
| **Rotación cuentas por pagar** (DPO) | (Cuentas por pagar / Coste de ventas) × 365 | Cuanto más bajo, mejor |

> Nota: el criterio «cuanto más bajo mejor» aplicado a DPO es discutible (pagar
> tarde financia el circulante), pero se transcribe tal cual lo escribe el
> cuaderno.

---

## 8. Ratios de solvencia

> «Mide la calidad y cantidad de deuda»

| Ratio | Fórmula | Rango |
|---|---|---|
| **Ratio de deuda** | Pasivos totales / Activos totales | **50–70 %** |
| *(variante anotada al lado)* | Deuda total / Activos totales | **40–60 %** |
| **Ratio de endeudamiento** | Pasivo total / Patrimonio neto | Óptimo **1–2** (según sector) |
| **Calidad de la deuda** | Deuda a corto / Deuda total | Óptimo **20–40 %** (80 % máximo) |
| **Cobertura de intereses** | EBIT / Pago de intereses | Óptimo **> 5** |

Anotación lateral (columna J), con la definición precisa que usa:

- Deuda: pasivos totales / activos totales
- Endeudamiento: pasivos totales / patrimonio neto
- Calidad de deuda: deuda en pasivos corrientes (la de corto) / deuda total
  (toda la deuda en pasivos)
- Pago de intereses: **beneficios antes de impuestos / gastos por intereses**

---

## 9. Ratios de Rentabilidad

> «Capacidad de rentabilizar sus recursos»

| Ratio | Fórmula | Rango |
|---|---|---|
| **Margen bruto** | (Ventas − Coste de ventas) / Ventas | Óptimo **40 %** (cuanto más alto mejor) |
| **Margen neto** | Beneficio neto / Ventas | Óptimo **10 %** (cuanto más alto mejor) |
| **ROA** | Beneficio neto / Total activos | Cuanto más alto mejor |
| **ROE** | Beneficio neto / Patrimonio neto | Cuanto más alto mejor · óptimo **12 %** (si es financiero, debe ser más) |
| **Apalancamiento financiero** | Total activos / Patrimonio neto | **No supere 3** |

Además: **«Mayor que 1 en ventas / total activos»** (rotación de activos > 1).

### Modelo DuPont (3 factores)

> «Herramienta para identificar si la empresa usa sus recursos eficientemente,
> creada a partir del ROE.» Sirve para: averiguar cómo se generan ganancias o
> pérdidas · detectar problemas de eficiencia y rentabilidad · demostrar el
> impacto de las decisiones · comparar empresas fácilmente.

```
ROE = ROA × Apalancamiento financiero
ROE = Margen neto × Rotación de activos × Apalancamiento financiero

Beneficio neto   Beneficio neto     Ventas        Total activos
────────────── = ────────────── × ───────────── × ──────────────
Patrimonio neto      Ventas       Total activos  Patrimonio neto
```

Filas de la tabla (una columna por año, 2016–2020 en el ejemplo):
ROE · Margen neto · Rotación de activos · Apalancamiento financiero ·
**Check** = `(Margen × Rotación × Apalancamiento) − ROE` → **debe dar 0**
(formato condicional: se resalta cuando ≠ 0).

### Modelo DuPont extendido (5 factores)

Filas: ROE · **Margen operativo (EBIT / Ventas)** · **Efecto fiscal (Beneficio
neto / Beneficio antes de impuestos)** · **Coste financiero (Beneficio antes de
impuestos / EBIT)** · Rotación de activos · Apalancamiento financiero ·
**Check** = `(Margen op. × Efecto fiscal × Coste financiero × Rotación ×
Apalancamiento) − ROE` → **debe dar 0**.

---

## 10. Valoracion de empresas

Pestaña compuesta enteramente por imágenes de un curso. Contenido íntegro:

### ¿Qué son los ratios de valoración?

- Ratio de valoración = **Dato de precio / Dato financiero**
- Infinidad de ratios de valoración.
- **Un solo ratio no debe ser indicativo del valor de la empresa.**
- Comparar entre empresas del mismo sector, la empresa con años anteriores, o
  la empresa con el sector.
- Diferenciar entre **capitalización** y **valor de la empresa**.

### Múltiplos por capitalización

`Capitalización bursátil = Precio por acción × Nº de acciones`

| Múltiplo | Fórmula | Lectura | Cuándo NO / cuándo sí |
|---|---|---|---|
| **PER** | Precio por acción / BPA = Capitalización / Beneficio neto | Años de beneficios necesarios para recuperar la inversión | **No adecuado** para empresas con pérdidas, en crecimiento y cíclicas |
| **P/S** (Precio/Ventas) | Precio por acción / Ventas por acción = Capitalización / Ventas totales | Años de ventas necesarios para recuperar la inversión | Empresas de Internet, farmacéuticas, periodos de maduración largos |
| **P/BV** (Precio/Valor contable) | Precio por acción / Patrimonio neto por acción = Capitalización / Patrimonio neto | Cuánto vale la empresa si se declara en quiebra | Empresas financieras, inmobiliarias, intensivas en capital |
| **P/FCF** | Precio por acción / FCF por acción = Capitalización / Flujo de caja libre | Años de flujo de caja necesarios para recuperar la inversión | **Ratio más objetivo** |

### Método por valor de empresa (EV)

- El valor de empresa (*Enterprise Value*) incluye su capitalización, su deuda y
  su efectivo.
- Ratio de valoración = **EV / Dato financiero**
- **EV = Capitalización bursátil + Deuda bruta − Caja**

| Múltiplo | Fórmula | Lectura |
|---|---|---|
| **EV/EBITDA** | EV / EBITDA | El multiplicador del valor de la compañía sobre los recursos que genera. **Adecuado para empresas cíclicas. Se evita el «maquillaje»** |

### Valoración por múltiplos (el ejemplo que trae el cuaderno)

Comparativa de múltiplos (Donaldson vs Evoqua vs Sector):

| | DONALDSON | EVOQUA | SECTOR |
|---|---|---|---|
| PER | 31,45 | 51,68 | 38,49 |
| Precio/Ventas | 2,97 | 2,43 | 2,16 |
| Precio/Flujo de caja libre | 32,96 | 45,67 | 32,91 |
| Precio/Valor contable | 7,09 | 6,76 | 3,19 |

Y el cálculo del precio objetivo aplicando el múltiplo del comparable y del
sector a la magnitud **por acción** de la empresa analizada:

| Magnitud (por acción) | DONALDSON | Múltiplo | EVOQUA | Valoración (Evoqua) | SECTOR | Valoración (Sector) |
|---|---|---|---|---|---|---|
| Beneficio | 2 | PER | 51,68 | 103,36 $ | 38,49 | 76,98 $ |
| Ventas | 20,12 | P/Ventas | 2,43 | 48,89 $ | 2,16 | 43,46 $ |
| Flujo de caja libre | 2,04 | P/FCF | 45,67 | 93,16 $ | 32,91 | 67,13 $ |
| Valor contable | 7,74 | P/VC | 6,76 | 52,32 $ | 3,19 | 24,69 $ |
| | | | **Media** | **74,43 $** | **Media** | **53,06 $** |

Notas manuscritas en la hoja: «Más baja = más barata» · «Medir todos y valorar»
· «Comparar ratios de empresa por sector» · «Comparar múltiplo de una empresa
con la magnitud de otra, esto da la valoración de la empresa».

### Modelo de descuento por dividendos (Gordon)

- El valor de la empresa es la suma de los dividendos futuros.

```
        D₀ × (1 + g)
P  =  ───────────────
           r − g

P  = Precio objetivo
D₀ = Dividendo actual
g  = Crecimiento esperado de los dividendos
r  = Rentabilidad exigida = Rf + Beta × (Rm − Rf) = Rf + Beta × Prima de riesgo
```

---

## Dependencias que este cuaderno impone

Lo que la pestaña 10 pide **no se puede calcular sólo con la SEC**: PER, P/S,
P/BV, P/FCF, EV/EBITDA y el DDM de Gordon necesitan **precio de mercado** (y el
DDM, además, beta y prima de riesgo). El módulo tiene `PriceAdapter` (Finnhub),
apagado sin API key. La comparativa «vs sector» necesita además una fuente de
múltiplos sectoriales que hoy **no existe** en el proyecto.
