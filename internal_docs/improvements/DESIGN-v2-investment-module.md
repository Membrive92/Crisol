# DESIGN v2 — Módulo de Inversión (Cartera + Análisis Fundamental Forense)

**Estado**: 📐 diseño lógico (v2, co-diseñado y pendiente de veto por número)
**Relación con ARCHITECTURE**: `ARCHITECTURE-investment-module.md` es el
documento hijo (cómo implementar). Este documento define el qué y el
porqué que aquel referencia: el modelo canónico (§4), las derivaciones
(§4.4), el catálogo de métricas por capas (§5) y el registro de
decisiones numeradas Dec.1-18 (§10) que el ARCHITECTURE cita.
**Regla de coherencia**: ninguna afirmación de este documento puede
contradecir el ARCHITECTURE. Si implementando se detecta conflicto,
gana el ARCHITECTURE y se corrige aquí.

---

## 1. Objetivo y encuadre

Módulo green-field **"Inversión"**, desacoplado del resto de Crisol
salvo el Dashboard (§9). Dos tabs sobre un catálogo común:

- **Tab Cartera**: registro de posiciones — lotes, ventas FIFO,
  dividendos cobrados, corporate actions, P&L descompuesto en
  precio/divisa, métricas de broker con quotes EOD/horarias.
  Tracking, no ejecución.
- **Tab Análisis**: análisis fundamental **forense multi-anual** de una
  empresa. Research puro: ejecutable sobre cualquier ticker, esté o no
  en cartera.

**Target del análisis**: riesgo contable + **sostenibilidad del
dividendo**. Es la tesis del usuario (dividenderas por flujos de caja a
largo plazo): la pregunta no es "¿está barata?" sino "¿la contabilidad
es de fiar y el dividendo cabe en la caja que genera?".

**Acoplamiento interno**: las tabs comparten únicamente `Security` (y
la infraestructura de pricing para valorar cartera). El análisis no
depende de tener posición; la posición no depende del análisis.

**Nomenclatura**: el módulo se llama "Inversión" (no "Análisis") para
no colisionar con `/personal-finance/analysis`, que es la pestaña de
flujos de Finanzas Domésticas. Son cosas distintas.

**Exclusiones**: no ejecuta órdenes; no valora precio (DCF/múltiplos =
extensión futura); **sector financiero excluido del scoring forense**
(Beneish/Altman no aplican a bancos/aseguradoras — la UI lo explica,
no se calcula basura); no ingesta 10-Q en MVP (el modelo lo prevé).

---

## 2. Decisiones núcleo de arquitectura (D1-D6)

| # | Decisión | Justificación |
|---|---|---|
| D1 | **Multi-anual desde el núcleo**, no snapshot | Riesgo contable y dividendo son fenómenos de tendencia; medio catálogo (§5) necesita t y t−1, y la trayectoria (T*) necesita 4-5 años |
| D2 | **Modelo canónico-first** + adapters por norma contable (GAAP/IFRS/PGC) | US-GAAP e IFRS difieren en estructura (leases, I+D, orden del CF); modelar US-first obligaría a migrar al llegar Europa |
| D3 | **Ingesta = interfaz común; adapter EDGAR XBRL única implementación MVP** | Dato oficial al regulador, gratis, series nativas, superior a parsear PDF. Cobertura US + ADRs. Europa = adapter futuro (FMP/EODHD, de pago) |
| D4 | **Scoring parametrizado por (sector × norma)** | Los cutoffs de Beneish/Altman están calibrados sobre US-GAAP industrial; aplicarlos tal cual a IFRS o a otros sectores genera falsos positivos sistemáticos. Tabla `scoring_thresholds` con `direction`, bandas y `model_variant` [Dec.8] |
| D5 | **Scores forenses combinados** como output de alto nivel | La evidencia empírica (S&P 500, 2010-2025) muestra que combinar M-Score y Z-Score identifica deterioro mejor que cualquiera aislado (−862 pb/año del quintil peor combinado vs −207/−132 aislados). El módulo presenta la matriz combinada, no scores sueltos |
| D6 | **Stress del dividendo = cobertura determinista + escenarios paramétricos etiquetados como hipótesis** | Proyectar sin supuestos es inventar. La capa 3 mide (determinista); la 3.5 simula con parámetros visibles y etiqueta fija "escenario hipotético" |

---

## 3. Modelo de dominio (lógico)

El DDL completo vive en ARCHITECTURE §2. Aquí las entidades y su papel:

- **`Security`** (global [Dec.11]): identidad del valor. `ticker`,
  `exchange`, `cik`, `sector` interno derivado de SIC [Dec.15],
  `accounting_std`, `is_financial` (excluye forense), `is_reit`
  (activa variante FFO), `security_type`.
- **`FinancialStatement`** (global): un año fiscal según **un filing**
  concreto (`filing_accession`) [Dec.6]. Las 43 partidas canónicas §4,
  todas NULL-ables (hueco ≠ cero), `fiscal_year_end` como fecha real
  [Dec.12], `raw_source_ref` con los conceptos originales sin colapsar
  [Dec.13]. `is_latest_view` marca la versión vigente de cada año.
- **`RestatementFlag`** (global): divergencia >1% en partidas clave
  entre dos filings del mismo año [Dec.6]. La reexpresión es en sí una
  señal forense.
- **`ScoringThresholds`** (global): umbral por (sector × norma ×
  métrica) con `direction`, 4 cortes de banda y `model_variant`
  [Dec.8]. IFRS/PGC nacen `uncalibrated`.
- **`AnalysisRun`** (scoped): resultado inmutable de una ejecución.
  `engine_version` + `thresholds_version` + scores de primer nivel en
  columnas para consulta en serie; desglose en JSONB [Dec.7].
- **Cartera** (scoped): `inv_lots`, `inv_sales`,
  `inv_sale_allocations` (FIFO **global por security**, pool único
  criterio AEAT, `account_id` opcional informativo [Dec.10]),
  `inv_dividends_received`, `inv_corporate_actions` +
  `inv_lot_adjustments` (aplicación auditada y reversible [Dec.9]).
  La posición NO es tabla: se deriva de lotes − allocations.
- **`PriceQuote`** (global): una quote viva por security, refresh
  on-access con TTL, staleness visible. Finnhub MVP.

---

## 4. Modelo canónico de partidas

43 partidas. Convención de signos: **todas positivas con semántica
fija** (capex positivo = inversión; dividends_paid positivo = pago). La
normalización de signos y escalas XBRL ocurre en ingesta, una sola vez.

### 4.1. Balance (23)

| Grupo | Partidas |
|---|---|
| Activo corriente | `cash`, `current_financial_assets`, `receivables`, `inventory`, `current_assets` |
| Activo no corriente | `ppe_net`, `goodwill`, `intangibles`, `deferred_tax_assets`, `total_assets` |
| Pasivo corriente | `short_term_debt`, `ltd_current_portion`, `accounts_payable`, `lease_liabilities_current`, `current_liabilities` |
| Pasivo no corriente | `long_term_debt`, `lease_liabilities_noncurrent`, `deferred_tax_liabilities`, `total_liabilities` |
| Patrimonio | `share_premium`, `retained_earnings`, `treasury_stock`, `equity` |

### 4.2. Cuenta de resultados (12)

`revenue`, `cogs`, `sga_expense`, `rd_expense`,
`depreciation_amortization`, `impairments`,
`gains_on_sale_of_business`, `ebit`, `interest_expense`, `taxes`,
`net_income` + acciones: `shares_basic`, `shares_diluted`,
`shares_outstanding_eop`, `sbc_expense`.

`impairments` y `gains_on_sale_of_business` van **separados** para
poder construir un EBIT limpio [Dec.5]: un deterioro de goodwill o una
plusvalía por venta de negocio distorsionan el EBIT del año y todas
las métricas que cuelgan de él.

### 4.3. Flujo de caja (10)

`cfo`, `wc_change_inventory`, `capex`, `acquisitions`, `divestitures`,
`dividends_paid`, `buybacks`, `share_issuance`, `debt_change`,
`taxes_paid`.

### 4.4. Derivaciones (reglas explícitas — `derivations.py`)

| Derivada | Fórmula | Notas |
|---|---|---|
| `total_debt` | short_term_debt + ltd_current_portion + long_term_debt | **Sin leases** por defecto; variante `total_debt_incl_leases` (+ lease_liabilities_*) para comparabilidad IFRS16/ASC842. Ambas expuestas |
| `net_debt` | total_debt − cash − current_financial_assets | |
| `ebitda` | ebit + depreciation_amortization | |
| `ebit_clean` | ebit + impairments − gains_on_sale_of_business | [Dec.5] Base de márgenes y coberturas "limpias"; el EBIT reportado se muestra al lado |
| `ebt` | net_income + taxes | [Dec.2] Con flag si diverge >2% de (ebit − interest_expense): señala partidas no modeladas (resultado financiero no-interés, asociadas) |
| `effective_tax_rate` | taxes / ebt | Guard: ebt ≤ 0 → `not_computable` |
| `nopat` | ebit_clean × (1 − effective_tax_rate) | |
| `invested_capital` | equity + total_debt − cash | |
| `wc_total` | current_assets − current_liabilities | [Dec.1] Para Altman X1 |
| `wc_operating` | (receivables + inventory) − accounts_payable | [Dec.1] Para eficiencia y F6: el WC total mete deuda financiera corriente y ensucia la señal operativa |
| `fcf_cfo` | cfo − capex | **Primaria** (D2, Q*, stress) |
| `fcf_ebitda` | ebitda − capex − Δwc_operating − taxes_paid | **Contraste**: reconstruye la caja desde el devengo. Divergencia vs fcf_cfo >15% sostenida 2 años → `Flag("fcf_divergence", amber)` — señal de accruals o de partidas de CFO no modeladas |
| `maintenance_capex` | min(capex, depreciation_amortization) | [Dec.4] SIEMPRE `status=estimated`; proxy honesto, nunca cuenta como hueco de datos |
| `ffo` | net_income + depreciation_amortization + impairments − gains_on_sale_of_business | Solo `is_reit`. Sustituye a FCF en la capa 3 (D6). AFFO fuera de alcance |
| `dividend_per_share` | dividends_paid / shares_basic | |

### 4.5. Convenciones de cálculo (`conventions.py`)

- `DAY_COUNT = 365`.
- **Denominadores de balance en medias**: `avg(t, t−1)`. Primer año de
  la serie sin t−1 → se usa el saldo final y la métrica sale con
  `status="approximation"` [Dec.3]. Nunca se omite en silencio.
- Decimal en todo; redondeo solo en presentación.
- Hueco (`None`) en cualquier input → `MetricResult(status=
  "not_computable", reason=...)`. Jamás 0 implícito, jamás excepción.
- **Ausencia vs cero (política de imputación — vive en la ingesta,
  no en el engine)**: en XBRL las empresas omiten conceptos que valen
  cero (sin deuda a corto → no etiquetan el concepto). Regla: existe
  una **lista blanca de partidas imputables a 0 cuando ausentes**
  (componentes omitibles-si-inmateriales: deudas parciales, leases,
  inventario, goodwill/intangibles, rd/sbc, impairments, plusvalías,
  buybacks/emisiones, dividendos, adquisiciones...), definida en el
  adapter (ARCHITECTURE §3.3). Las partidas núcleo (revenue, cfo,
  totales de balance, capex, D&A, taxes_paid...) **nunca** se imputan.
  `interest_expense` es condicional: 0 solo si toda la deuda es
  0/imputada. Toda imputación se marca con proveniencia
  `imputed_zero` (cuarto valor junto a sourced/derived/estimated), se
  registra en `raw_source_ref.mapping`, **no cuenta como `sourced` en
  la completitud**, y se revierte a `None` si rompe un cuadre de
  validación (la identidad contable manda sobre la lista).
- Guards explícitos: equity ≤ 0, revenue ≤ 0, ebt ≤ 0, denominador 0.

---

## 5. Catálogo de métricas

Claves estables (se citan en docstrings, thresholds y UI). Umbrales:
**defaults seed para US-GAAP genérico**, calibrables por sector×norma
[Dec.8/D4] — la banda es (verde | ámbar | rojo) según `direction`.

### Capa 1 — Base (27 métricas: 16 plantilla + 4 adiciones v2 [+] + 7 ampliación v2.1 [++])

*Nota de coherencia: el ARCHITECTURE (fase de engine, 40.2/44.2) dice
"las 20 métricas base"; con la ampliación v2.1 léase **27**. Es el
único ajuste textual que requiere aquel documento. La descomposición
DuPont NO cuenta: es salida explicativa, no métrica (ver R5).*

**Liquidez (L)**

| Clave | Métrica | Fórmula | Banda default |
|---|---|---|---|
| L1 | Ratio corriente | current_assets / current_liabilities | >1,5 · 1,0-1,5 · <1,0 |
| L2 | Prueba ácida | (current_assets − inventory) / current_liabilities | >1,0 · 0,7-1,0 · <0,7 |
| L3 | Ratio de caja | (cash + current_financial_assets) / current_liabilities | >0,3 · 0,15-0,3 · <0,15 |
| L4 [++] | **Muro de vencimientos** | (cash + current_financial_assets + fcf_cfo) / (short_term_debt + ltd_current_portion) | >1,5 · 1,0-1,5 · <1,0. La deuda que vence en 12 meses contra la liquidez + caja libre del año: el mecanismo por el que las empresas quiebran de verdad (no pueden refinanciar), y L1-L3 no lo miran |

**Actividad (A)** — todas con medias [Dec.3]

| Clave | Métrica | Fórmula | Banda |
|---|---|---|---|
| A1 | Días de cobro (DSO) | receivables_avg / revenue × 365 | Sin banda absoluta: se evalúa su **deriva** (C1) |
| A2 | Días de inventario (DIO) | inventory_avg / cogs × 365 | Ídem (C3) |
| A3 | Días de pago (DPO) | accounts_payable_avg / cogs × 365 | Ídem |
| A4 | Rotación de activos | revenue / total_assets_avg | Ídem (Piotroski P9 usa su Δ) |
| A5 [+] | Ciclo de conversión de caja | A1 + A2 − A3 | Deriva >15 días vs mediana 3a → ámbar |

**Solvencia (S)**

| Clave | Métrica | Fórmula | Banda |
|---|---|---|---|
| S1 | Apalancamiento | total_liabilities / total_assets | <0,6 · 0,6-0,75 · >0,75 |
| S2 | Cobertura de intereses | ebit_clean / interest_expense | >6 · 3-6 · <3 |
| S3 | Autonomía financiera | equity / total_assets | >0,35 · 0,2-0,35 · <0,2 |
| S4 [+] | Deuda neta / EBITDA | net_debt / ebitda | <2 · 2-3,5 · >3,5 |
| S4b [+] | Deuda neta / EBIT | net_debt / ebit_clean | <3 · 3-5 · >5. Complementa S4: en negocios con D&A alto (mucho capex), EBITDA infla la capacidad aparente |
| S5 [++] | **Años de repago** | net_debt / fcf_cfo | <4 · 4-8 · >8. Cuántos años de caja libre real tardaría en devolver la deuda neta. net_debt<0 → verde "caja neta"; fcf≤0 con deuda>0 → `not_computable` con razón (que en la práctica es la peor señal) |
| S6 [++] | **Cobertura de intereses por caja** | (cfo + interest_expense + taxes_paid) / interest_expense | >8 · 4-8 · <4. S2 usa EBIT (devengo, maquillable); esta usa caja generada. Si S2 verde y S6 rojo, el devengo está mintiendo |

**Rentabilidad (R)** — medias en denominadores de balance

| Clave | Métrica | Fórmula | Banda |
|---|---|---|---|
| R1 | Margen bruto | (revenue − cogs) / revenue | Deriva, no absoluto (Piotroski P8) |
| R2 | Margen EBITDA | ebitda / revenue | Deriva |
| R3 | Margen EBIT | ebit_clean / revenue | Deriva; se muestra también con EBIT reportado |
| R4 | Margen neto | net_income / revenue | Deriva |
| R5 | ROE | net_income / equity_avg | >12% · 8-12 · <8; guard equity≤0 |
| R6 | ROA | net_income / total_assets_avg | >5% · 2-5 · <2 |
| R9 [+] | ROIC | nopat / invested_capital_avg | >10% · 6-10 · <6. La métrica de creación de valor; separa negocio de apalancamiento (vs ROE) |
| R7 [++] | **Margen FCF** | fcf_cfo / revenue | >8% · 3-8 · <3. Cuánta venta acaba siendo caja libre; su estabilidad en la serie es proxy de foso |
| R8 [++] | FCF por acción | fcf_cfo / shares_basic | Sin banda: serie. La contrapartida por-acción de la dilución (C6): FCF total puede crecer mientras el FCF/acción cae |
| R9b [++] | **CROIC** | fcf_cfo / invested_capital_avg | >8% · 4-8 · <4. El ROIC medido en caja: si R9 verde y R9b rojo, el retorno es contable, no monetario |
| R10 [++] | **Rentabilidad bruta s/ activos** (Novy-Marx) | (revenue − cogs) / total_assets_avg | >0,33 · 0,18-0,33 · <0,18. El factor de calidad con mejor respaldo empírico académico: margen bruto por unidad de activo, difícil de manipular (arriba de la cascada contable) |

**Descomposición DuPont de R5** (explicativa — **no es métrica del
catálogo**: sin `metric_key` ni banda; viaja en `scores_detail` del
run): `ROE = R4 × A4 × (total_assets_avg / equity_avg)` — el informe
muestra qué componente movió el ROE cada año (margen, rotación o
apalancamiento). Un ROE que sube solo por el multiplicador no es
mejora del negocio: es deuda.

### Capa 1.5 — Evolutiva (los movimientos de la empresa)

- **E1 Horizontal**: YoY y CAGR de revenue, ebit_clean, net_income,
  cfo, fcf_cfo, dividends_paid, shares_basic. Base 100 = primer año.
- **E2 Vertical (common-size)**: balance sobre total_assets; P&L sobre
  revenue. Años en columnas — es la vista que revela cambios de mezcla.
- **E3 [++] Estabilidad de márgenes**: σ (desviación típica) del margen
  EBIT limpio (R3) en la serie. Banda: <2 pp · 2-5 · >5. La
  predictibilidad ES seguridad: un margen errático convierte cualquier
  cobertura de dividendo en una lotería.
- **E4 [++] Tasa de crecimiento sostenible**: `g = R5 × (1 − D1)` — lo
  que puede crecer autofinanciándose. Si `CAGR_revenue − g > 10 pp`
  sostenido → ámbar "crecimiento dependiente de financiación externa"
  (cruzar con C6 dilución y C7 deuda: alguien lo está pagando).
- **Reglas de coherencia (C)** — cruces que delatan divergencias:

| Clave | Regla | Umbral default → flag |
|---|---|---|
| C1 | Crecimiento de receivables vs revenue | Δreceivables − Δrevenue >15 pp sostenido 2a → ámbar (cobro forzado / channel stuffing). Alimenta DSRI |
| C2 | NI vs CFO | NI crece y CFO plano/cae 2a → ámbar (beneficio sin caja). Cruce con Sloan |
| C3 | Inventory vs cogs | Δinventory − Δcogs >20 pp → ámbar (inventario hinchado) |
| C4 | Capex vs D&A | capex/D&A <0,8 sostenido 3a → info (descapitalización; cruzar con Dec.4) |
| C5 | Goodwill | Δgoodwill >0 sin `acquisitions` en CF → ámbar (¿de dónde salió?) |
| C6 | Dilución | Δshares_basic >2%/año sostenido sin buybacks → info; >5% → ámbar |
| C7 [++] | Retorno financiado con deuda | (dividends_paid + buybacks) > fcf_cfo ∧ debt_change > 0 → ámbar; 2a sostenidos → rojo. El patrón terminal de las dividenderas rotas: se sostiene el dividendo pidiendo prestado |
| C8 [++] | Crecimiento comprado (proxy) | Σacquisitions de la serie / Δrevenue acumulado > 0,5 → info. Proxy honesto (el 10-K no separa orgánico): si media del crecimiento vino de compras, el CAGR no es repetible sin seguir comprando |

### Capa 2 — Forense

**No se calcula si `is_financial`** — `not_computable` con razón
explícita en cada score, nunca omitido.

**M-Score de Beneish (8 variables)** — probabilidad de manipulación
contable. Todas las variables son ratios t/t−1:

```
DSRI = (receivables/revenue)_t ÷ (receivables/revenue)_t−1
GMI  = margen_bruto_t−1 ÷ margen_bruto_t
AQI  = [1 − (current_assets + ppe_net)/total_assets]_t ÷ ídem_t−1
SGI  = revenue_t ÷ revenue_t−1
DEPI = tasa_dep_t−1 ÷ tasa_dep_t,  tasa_dep = D&A/(D&A + ppe_net)
SGAI = (sga_expense/revenue)_t ÷ ídem_t−1
LVGI = [(current_liabilities + long_term_debt)/total_assets]_t ÷ ídem_t−1
TATA = (net_income − cfo) / total_assets

M = −4,84 + 0,920·DSRI + 0,528·GMI + 0,404·AQI + 0,892·SGI
    + 0,115·DEPI − 0,172·SGAI + 4,679·TATA − 0,327·LVGI
```

Banda: **M < −2,22 verde · −2,22 a −1,78 ámbar · M > −1,78 rojo**.
Se reporta M y las 8 variables (la variable que dispara importa más
que el agregado).

**Z-Score de Altman** — riesgo de insolvencia. **MVP: variante Z''
(1995, book-based)** — determinista, sin dependencia de precio:

```
Z'' = 6,56·X1 + 3,26·X2 + 6,72·X3 + 1,05·X4
X1 = wc_total/total_assets    X2 = retained_earnings/total_assets
X3 = ebit/total_assets        X4 = equity/total_liabilities
```

Banda: **>2,60 verde · 1,10-2,60 ámbar · <1,10 rojo**. La Z clásica
(con capitalización de mercado vía pricing) queda como `model_variant`
futura — mezclar un precio staleness-tolerant en un score determinista
del engine rompería la reproducibilidad de los runs [decisión a vetar
si prefieres Z clásica desde MVP]. REITs: Z'' se calcula con
`model_variant='uncalibrated'` y nota ámbar (el modelo no está
calibrado para ellos).

**F-Score de Piotroski (9 tests binarios)** — calidad/fortaleza:

| # | Test (1 punto si...) |
|---|---|
| P1 | ROA > 0 |
| P2 | CFO > 0 |
| P3 | ΔROA > 0 |
| P4 | CFO > net_income (accrual check) |
| P5 | Δ(long_term_debt/total_assets) < 0 |
| P6 | ΔL1 (ratio corriente) > 0 |
| P7 | share_issuance ≈ 0 (sin emisión) |
| P8 | Δmargen bruto > 0 |
| P9 | Δrotación de activos (A4) > 0 |

Banda: **7-9 verde · 4-6 ámbar · 0-3 rojo**.

**Accruals de Sloan**: `(net_income − cfo) / total_assets_avg`.
Banda absoluta: **|x| <5% verde · 5-10% ámbar · >10% rojo**. Positivo
alto = beneficio por delante de la caja.

**F5 — Riesgo de goodwill**: goodwill/total_assets. Banda: <30% ·
30-50% · >50% (calibrable por sector — un serial acquirer sano puede
vivir en ámbar). Cruce con C5 y con `impairments` históricos.

**F6 — Anomalía de working capital**: |Δwc_operating| vs Δrevenue
>15 pp en el año → ámbar. Es la descomposición visible de TATA: dónde
se está acumulando el devengo.

**FZ [++] — X-Score de Zmijewski** (probit de quiebra, book-based):

```
X = −4,336 − 4,513·(net_income/total_assets)
    + 5,679·(total_liabilities/total_assets)
    + 0,004·(current_assets/current_liabilities)
P(distress) = Φ(X)   [normal estándar; solo en presentación]
```

Banda sobre P: **<15% verde · 15-40% ámbar · >40% rojo** (seed,
calibrable). Razón de incluir un segundo modelo de quiebra: Z''
pondera eficiencia del activo; Zmijewski pondera pasivo y
rentabilidad — triangulan. Z'' verde + FZ rojo = el balance aguanta
pero la cuenta de resultados no lo sostiene. Misma exclusión de
financieras.

**F7 [++] — C-Score de Montier** (6 checks binarios de "cocina",
1 punto cada uno — reutiliza señales ya computadas):

| # | Check |
|---|---|
| 1 | net_income > cfo (beneficio por delante de la caja) |
| 2 | ΔDSO (A1) > 0 |
| 3 | ΔDIO (A2) > 0 |
| 4 | Δ[(current_assets − cash − current_financial_assets − receivables − inventory)/revenue] > 0 — "otros activos corrientes" creciendo sobre ventas |
| 5 | DEPI < 1 (la tasa de depreciación cae) |
| 6 | Δtotal_assets > 10% interanual |

Banda: **0-1 verde · 2-3 ámbar · ≥4 rojo**. Complementa a Beneish:
conteo binario robusto vs regresión — cuando ambos disparan, la
evidencia es fuerte; cuando divergen, el desglose dice por qué.

### Capa 3 — Dividendo (el target)

`is_reit=True` → D1/D2/D3/D8 usan **FFO** en lugar de NI/FCF (D6).

**Cobertura (D)**

| Clave | Métrica | Fórmula | Banda |
|---|---|---|---|
| D1 | Payout sobre beneficio | dividends_paid / net_income | <60% · 60-80 · >80 |
| D2 | **Payout sobre FCF** (primaria) | dividends_paid / fcf_cfo | <60% · 60-85 · >85 |
| D3 | Cobertura FCF | fcf_cfo / dividends_paid | >1,6 · 1,15-1,6 · <1,15 |
| D4 | Payout FCF ajustado por SBC | dividends_paid / (fcf_cfo − sbc_expense) | Como D2. La SBC es coste real que el CFO esconde; si D4 ≫ D2 el dividendo se paga diluyendo |
| D5 | Retorno total sobre FCF | (dividends_paid + buybacks) / fcf_cfo | <90% · 90-110 · >110. >100% sostenido = se devuelve más de lo que se genera (deuda o caja) |
| D6 | Payout REIT | dividends_paid / ffo | <75% · 75-90 · >90 |
| D7 | DPS y su serie | dividend_per_share por año | Alimenta T* |
| D8 | Margen de seguridad | (fcf_cfo − dividends_paid) / revenue | >5% · 2-5 · <2. Colchón en términos de ventas |

**Calidad de la caja (Q)**

| Clave | Métrica | Fórmula | Banda |
|---|---|---|---|
| Q1 | Conversión CFO/NI | cfo / net_income | >1,0 · 0,8-1,0 · <0,8 sostenido |
| Q2 | Conversión FCF/EBITDA | fcf_cfo / ebitda | >50% · 30-50 · <30 |
| Q3 | Divergencia FCF dual | |fcf_cfo − fcf_ebitda| / fcf_cfo | <15% verde · 15-20 ámbar · >20 rojo (2a sostenidos → flag) |
| Q4 [++] | Anomalía fiscal | ETR del año vs mediana de la serie | Caída >10 pp, o ETR <10% sostenida 2a → ámbar "beneficio apoyado en partidas fiscales". Los créditos fiscales inflan NI sin tocar la caja operativa y no se repiten |
| Q5 [++] | Peso de extraordinarios | |gains_on_sale_of_business − impairments| / |ebt| | >20% → ámbar. Si el beneficio depende de vender negocios o de no deteriorar, el beneficio "normal" es otro |

**Soporte del balance (B)** — ¿la deuda deja sitio al dividendo?

| Clave | Métrica | Fórmula/cruce | Banda |
|---|---|---|---|
| B1 | Capacidad | S4 (deuda neta/EBITDA) evaluada contra el dividendo | S4 rojo + D2 ámbar → el dividendo compite con la deuda |
| B2 | Prioridad de intereses | S2 <3 con D2 >60% | → rojo compuesto: los intereses cobran antes que tú |
| B3 | Años de dividendo en caja | (cash + current_financial_assets) / dividends_paid | >2a · 1-2 · <1 |
| B4 [++] | Fuente del dividendo | dividends_paid > fcf_cfo ∧ (debt_change > 0 ∨ share_issuance > 0) | → rojo "dividendo financiado con deuda/emisión", con la evidencia cuantificada (cuánto vino de cada fuente). Es C7 aplicado específicamente al dividendo: la señal individual más predictiva de un recorte futuro |

**Trayectoria (T)** — sobre la serie disponible (4-5 filings ≈ 5-6
años con comparativos):

| Clave | Métrica | Definición | Nota de honestidad |
|---|---|---|---|
| T1 | Racha sin recorte | Años consecutivos con DPS_t ≥ DPS_t−1 | **Cota inferior**: la serie es la ingerida, no la histórica completa. La UI lo dice ("≥ N años en los datos disponibles") |
| T2 | CAGR del dividendo | CAGR de DPS en la serie | <0 → rojo directo |
| T3 | Estabilidad del payout | Desviación estándar de D2 en la serie | σ >20 pp → ámbar (payout errático = política no creíble) |
| T4 | Momentum | Δ%DPS últimos 2a vs CAGR serie | Desaceleración >50% → info (posible techo) |

### Capa 3.5 — Stress (paramétrico, etiqueta fija "escenario hipotético")

| Clave | Escenario | Mecánica | Parámetros |
|---|---|---|---|
| ST1 | Shock de ingresos | revenue × (1−x); el EBIT cae por apalancamiento operativo estimado con el margen de contribución proxy (Δebit/Δrevenue histórico, mediana de la serie); FCF y D2/D3 recalculados | x ∈ {10%, 20%, 30%} default, editable |
| ST2 | Shock de tipos | interest_expense recalculado: sobre `pct_variable_debt` de total_debt se aplica +y pb. **Aproximación agregada** por defecto; perfil de vencimientos manual opcional [Dec.14] | y ∈ {100, 200, 300} pb; pct_variable default 30%, editable |
| ST3 | Breakeven del dividendo | Máxima caída de FCF que mantiene D3 ≥ 1,0 | Derivado, sin parámetros |

Output: cobertura resultante por escenario + la frase generada ("con
ingresos −20% y tipos +200 pb, la cobertura FCF baja de 1,8× a 1,1×").

### Capa 4 — Síntesis

**Cuatro preguntas** (el veredicto que la UI muestra primero):

1. **¿La contabilidad es de fiar?** ← M-Score + F7 (Montier) + accruals + Q3/Q4/Q5 + C1/C2/C3 + restatements
2. **¿Genera caja de verdad?** ← Q1/Q2 + F-Score + R7/R9b/R10 + E3 + tendencia FCF (E1)
3. **¿El dividendo cabe en la caja?** ← D2/D3/D4/D5 (o D6) + B1/B2/B3/B4
4. **¿Aguanta un golpe?** ← ST1-ST3 + Z'' + FZ (Zmijewski) + L4 + S2/S4/S5/S6

**Matriz de seguridad** (materializa D5 — los scores combinados como
output de alto nivel): el informe abre con un perfil de tres estados
por reglas explícitas:

- **Conservador**: M verde ∧ Z'' verde ∧ FZ verde ∧ F-Score ≥7 ∧
  accruals verde.
- **Evitar**: (M rojo ∧ accruals rojo) ∨ Z'' rojo ∨ FZ rojo ∨ B4 rojo.
- **Vigilar**: todo lo demás — con las flags concretas que lo impiden
  ser Conservador listadas al lado.

Sin estados intermedios difusos: el usuario ve el perfil y las razones
exactas que lo producen, y puede abrir cada una.

Cada pregunta → semáforo agregado por reglas explícitas (no media
ponderada opaca): **rojo si cualquiera de sus métricas núcleo está
roja; ámbar si ≥2 ámbar; verde en el resto**. Las métricas núcleo por
pregunta se listan en thresholds (revisables).

**`dividend_verdict`** ∈ {healthy, caution, stressed, not_applicable}:
mapea de las preguntas 3-4 (not_applicable si no paga dividendo o
`is_financial`).

**Confianza** = `completeness_core × staleness_factor`:
- `completeness_core`: fracción de partidas núcleo (revenue, ebit,
  net_income, cfo, capex, dividends_paid, total_assets, equity,
  current_assets, current_liabilities) con `status=sourced` en los
  años usados. Las partidas `imputed_zero` NO computan como sourced:
  el panel de completitud las lista aparte ("N partidas imputadas a
  cero").
- `staleness_factor`: 1,0 si el último fiscal_year_end <9 meses de la
  fecha de análisis; 0,7 si 9-18m; 0,4 si >18m [Dec.16]. La UI muestra
  SIEMPRE la fecha del último dato ("análisis sobre FY2025, cerrado
  hace 7 meses").

**Matriz de banderas**: toda flag (C*, F5, F6, fcf_divergence,
restatement, aproximaciones Dec.3/Dec.4) se lista con severidad,
evidencia (serie que la dispara) y capa de origen. Nada se agrega sin
poder abrirse.

---

## 6. Flujo end-to-end (Tab Análisis)

```
Ticker → resolver Security (EDGAR/CIK; symbol search si no-US)
  → ¿statements? no → ingesta (job, 4-5 filings 10-K, cache local)
  → normalización → canónico + validación de cuadres + restatements
  → run: series (is_latest_view) → capa 1 → 1.5 → 2 → 3 → 3.5 → 4
  → AnalysisRun persistido (engine_version + thresholds_version)
  → informe: veredicto 4 preguntas → scores → dividendo → stress
    → evolución common-size → statements (canónico ⇄ raw) → historial
```

Determinismo: mismo set de statements + mismos thresholds + misma
versión de engine ⇒ mismo run, byte a byte. Es lo que permite comparar
runs en el tiempo y detectar que "cambió la empresa" vs "cambió el
motor".

---

## 7. Fuentes y precios

| Fuente | Papel | Coste | Límite |
|---|---|---|---|
| **EDGAR XBRL** (edgartools) | Fundamentales MVP | Gratis | Solo US + ADRs; identidad SEC obligatoria; ~10 req/s → descargas serializadas [Dec.18]; cache local de crudos como evidencia [Dec.18] |
| **Finnhub** | Quotes cartera (~~+ symbol search~~) | Free tier 60 req/min | Real-time limitado; suficiente para EOD/1h staleness-tolerant. **PHASE-44.8 / ADR-0008**: el symbol search se retira — su `/search` no devuelve la bolsa (sólo `description`, `displaySymbol`, `symbol`, `type`), así que no puede alimentar un buscador multi-mercado |
| FMP / EODHD | Fundamentales EU (futuro) | De pago | Adapter futuro tras D2/D3 |
| PDF + LLM | Fallback manual | — | Frágil; fuera de MVP |

Google Finance descartado (API descontinuada 2012, sin acceso
programático). Sector financiero excluido del forense; REITs con FFO.

---

## 8. Validación pendiente y riesgos abiertos

**Acción del usuario (bloquea fase 40.4 del ARCHITECTURE, nada más)**:
ejecutar `validate_edgar.py` en su máquina contra 3 empresas reales
(una industrial tipo MMM, una utility, un REIT) y devolver el cruzado
→ fija el `concept_map` XBRL→canónico con datos, no con candidatos.

| Riesgo | Estado |
|---|---|
| Mapeos XBRL ambiguos por empresa (extensiones custom) | Mitigado por raw_source_ref + punto de parada en 40.4 |
| Umbrales seed genéricos ≠ tu cartera real | Calibración post-MVP con runs reales; nunca "ajustar para que salga verde" |
| IFRS/PGC sin calibrar | `model_variant='uncalibrated'` visible hasta tener adapter EU |
| T1 (racha) como cota inferior | Aceptado y comunicado en UI |
| Sopa de scores (38+ métricas) | Mitigado por diseño: cada métrica mapea a exactamente una de las 4 preguntas y la síntesis agrega por reglas explícitas. Ninguna métrica "suelta" en el informe |

**Excluido deliberadamente de la ampliación** (para que no se
reabra sin motivo): EVA/ROIC−WACC (exige datos de mercado y beta —
rompe el determinismo del engine; extensión cuando pricing entre en
los runs), O-Score de Ohlson (su variable de tamaño exige deflactor
del PNB — dependencia externa fea; Zmijewski cubre el hueco),
crecimiento orgánico real por segmentos (el 10-K estructurado no lo
trae; C8 es el proxy honesto), ley de Benford sobre las cifras
(ruido con 5 filings).
| Z'' book vs Z con mercado | Decisión tomada (Z'' MVP); vetable |

---

## 9. Relación con el Dashboard (contrato PHASE-43)

El módulo implementa el contrato de agregación acordado en PHASE-43.4:

```
GET /investment/dashboard-summary
→ { verdict, headline_value: valor de mercado de la cartera (EUR),
    headline_label: "Inversión",
    secondary: [{P&L no realizado}, {yield on cost}], link: "/investment" }
```

- La card en el dashboard es **veredicto + número + link** — regla
  dura de PHASE-43, no un mini-módulo.
- El **valor de mercado de la cartera entra al patrimonio neto
  consolidado** del dashboard, cerrando la exclusión provisional de
  las cuentas brokerage (PHASE-31.4 "opción A"): con el módulo vivo,
  el agregador ya tiene una fuente de verdad valorada y con staleness
  explícito. Posición sin quote → excluida del total con badge (misma
  política anti-dato-ficticio).
- Separación balance/resultados respetada: el dashboard muestra el
  **stock** (valor, P&L latente); los **flujos** (dividendos cobrados,
  ventas del periodo) viven dentro del módulo.

---

## 10. Registro de decisiones (Dec.1-18)

Reconstruidas para casar con las citas del ARCHITECTURE. **Pendientes
de tu veto por número** — las citadas por el ARCHITECTURE (3, 6-13,
15, 18) están además fijadas por el código que aquel especifica.

| # | Decisión |
|---|---|
| 1 | **WC dual**: `wc_total` (Altman) y `wc_operating` (eficiencia/F6) — el total mete deuda financiera corriente y ensucia la señal operativa |
| 2 | **EBT = NI + taxes** con flag si diverge >2% de (EBIT − intereses): delata partidas no modeladas |
| 3 | **Primer año sin t−1**: media → saldo final + `status="approximation"`. Nunca silencioso |
| 4 | **maintenance_capex = min(capex, D&A)**: siempre `estimated`, proxy honesto, jamás cuenta como hueco de datos |
| 5 | **Impairments y gains_on_sale separados** → `ebit_clean` además del reportado |
| 6 | **Versionado por filing** (`filing_accession`) + `RestatementFlag` con divergencias >1%: la reexpresión es señal forense |
| 7 | **AnalysisRun** inmutable con `engine_version` + `thresholds_version` + scores de primer nivel en columnas (consultables en serie) |
| 8 | **ScoringThresholds** por (sector × norma × métrica): `direction`, 4 cortes, `model_variant`. Seed US-GAAP; IFRS/PGC `uncalibrated` |
| 9 | **CorporateAction desde el día uno** con aplicación auditada (`lot_adjustments`) y reversible: un split no auditado corrompe FIFO silenciosamente |
| 10 | **FIFO global por security** (pool único, criterio AEAT — coherente con el módulo Bitcoin) + `account_id` opcional informativo |
| 11 | **Tablas globales sin user_id** (securities, statements, thresholds, quotes) — ADR de excepción al multi-tenant: los datos de mercado son objetivos |
| 12 | **`fiscal_year_end` como DATE** (no solo año): los fiscales partidos (jun, sep) rompen la comparación por año natural y el staleness |
| 13 | **Fidelidad**: canónico ampliado + `raw_source_ref` con los conceptos originales sin colapsar — auditar el mapeo siempre posible |
| 14 | **Stress de tipos**: aproximación agregada (pct deuda variable paramétrico) por defecto; perfil de vencimientos manual opcional |
| 15 | **Taxonomía sectorial propia desde SIC** (no GICS, que es licenciado): el sector solo gobierna umbrales y aplicabilidad de modelos |
| 16 | **Staleness visible + confianza degradada**: >9 meses desde el último cierre penaliza la confianza y se muestra siempre |
| 17 | **Retribución de directivos fuera del canónico** (vive en DEF 14A, no en 10-K financials): extensión futura, no partida |
| 18 | **Cache local de filings crudos** (evidencia re-derivable) + **tests de propiedad** en normalización (cuadre balance <1%, márgenes acotados) + descargas serializadas por rate limit SEC |
