# 📄 ESPECIFICACIÓN TÉCNICA: MÉTRICAS FINANCIERAS MCDONALD'S (MCD)
## Framework de Análisis para App de Contabilidad - Sector QSR
### Versión 1.0 | Fuente Primaria: SEC EDGAR

---

## 1. FUENTES EDGAR REQUERIDAS

| Formulario | Frecuencia | Secciones Clave | Datos Extraíbles |
|------------|------------|-----------------|----------------|
| **10-K** | Anual | Item 6 (Selected Financial Data), Item 7 (MD&A), Item 8 (Financial Statements) | Métricas anuales completas, estrategia, riesgos |
| **10-Q** | Trimestral | Part I, Item 2 (Management's Discussion), Financial Statements | Métricas trimestrales, actualizaciones operativas |
| **8-K** | Eventos | Item 2.02 (Results), Item 7.01 (Regulation FD) | Earnings releases, guidance updates |
| **DEF 14A** | Anual (proxy) | Executive Compensation, Equity Compensation Plans | Dividend policy, buyback programs |
| **S-3/S-4** | Eventos | Shelf registrations, M&A | Cambios estructurales |

**URL Pattern EDGAR**: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000063908`

---

## 2. MÉTRICAS CONTABLES ESTÁNDAR

### 2.1 Rentabilidad (Income Statement)

| Métrica | Fórmula | Ubicación EDGAR | XPath/Pattern |
|---------|---------|-----------------|---------------|
| **Margen Bruto** | `(Revenue - COGS) / Revenue` | 10-K/10-Q: Consolidated Statements of Income | `//GrossProfit div //Revenues` |
| **Margen Operativo** | `Operating Income / Revenue` | 10-K Item 8 | `//OperatingIncomeLoss div //Revenues` |
| **Margen Neto** | `Net Income / Revenue` | 10-K Item 8 | `//NetIncomeLoss div //Revenues` |
| **ROE** | `Net Income / Average Shareholders' Equity` | Balance Sheet + Income Statement | `//NetIncomeLoss div ((//EquityCurrentYear + //EquityPriorYear) div 2)` |
| **ROIC** | `NOPAT / (Debt + Equity - Cash)` | Requiere cálculo: EBIT × (1 - Tax Rate) | `//OperatingIncomeLoss * (1 - (//IncomeTaxExpenseBenefit div //IncomeLossBeforeTax)) div (//LongTermDebt + //StockholdersEquity - //CashAndCashEquivalents)` |
| **ROA** | `Net Income / Average Total Assets` | Balance Sheet | `//NetIncomeLoss div ((//AssetsCurrentYear + //AssetsPriorYear) div 2)` |

> **Nota EDGAR**: MCD tiene **equity negativo** desde 2016. El campo `StockholdersEquity` aparecerá como valor negativo. Tu app debe manejar este caso y priorizar ROIC sobre ROE.

### 2.2 Liquidez (Balance Sheet)

| Métrica | Fórmula | Ubicación EDGAR | Tags XBRL |
|---------|---------|-----------------|-----------|
| **Current Ratio** | `Current Assets / Current Liabilities` | 10-K Item 8 - Consolidated Balance Sheets | `//AssetsCurrent div //LiabilitiesCurrent` |
| **Quick Ratio** | `(Current Assets - Inventory) / Current Liabilities` | Balance Sheet | `(//AssetsCurrent - //InventoryNet) div //LiabilitiesCurrent` |
| **Cash Ratio** | `Cash / Current Liabilities` | Balance Sheet | `//CashAndCashEquivalentsAtCarryingValue div //LiabilitiesCurrent` |
| **Working Capital** | `Current Assets - Current Liabilities` | Balance Sheet | `//AssetsCurrent - //LiabilitiesCurrent` |

### 2.3 Solvencia (Balance Sheet + Notes)

| Métrica | Fórmula | Ubicación EDGAR | Notas |
|---------|---------|-----------------|-------|
| **Net Debt / EBITDA** | `(Total Debt - Cash) / EBITDA` | Nota 9 (Debt) + Income Statement | EBITDA no está en EDGAR directamente; calcular: `Operating Income + Depreciation` |
| **Interest Coverage** | `EBIT / Interest Expense` | Income Statement | `//OperatingIncomeLoss div //InterestExpense` |
| **Debt/Assets** | `Total Debt / Total Assets` | Balance Sheet | `//Liabilities div //Assets` |
| **Fixed Charge Coverage** | `(EBIT + Lease Expense) / (Interest + Lease Expense)` | Nota 15 (Leases) | Requiere extracción de obligaciones de arrendamiento |

> **Tag EDGAR específico para deuda**: `//LongTermDebtNoncurrent` + `//LongTermDebtCurrent`

### 2.4 Eficiencia

| Métrica | Fórmula | Ubicación EDGAR | Observación |
|---------|---------|-----------------|-------------|
| **Asset Turnover** | `Revenue / Average Total Assets` | Income + Balance | `//Revenues div ((//Assets[CY] + //Assets[PY]) div 2)` |
| **Inventory Turnover** | `COGS / Average Inventory` | MCD: Inventory es mínimo | `//CostOfRevenue div ((//InventoryNet[CY] + //InventoryNet[PY]) div 2)` |
| **CCC** | `DIO + DSO - DPO` | Requiere cálculo manual | MCD típicamente negativo (-40 a -60 días) |

---

## 3. MÉTRICAS ESPECÍFICAS SECTOR QSR

### 3.1 Métricas Operativas (MD&A - Item 7)

| Métrica | Fórmula | Ubicación EDGAR | Patrón de Búsqueda |
|---------|---------|-----------------|------------------|
| **Same-Store Sales Growth (SSSG)** | `(Sales Current Year - Sales Prior Year) / Sales Prior Year` (locales >13 meses) | 10-K Item 7, 10-Q Item 2 | Buscar: "comparable sales", "global comparable sales", "comp sales" |
| **Traffic Growth** | `% change in guest counts` | MD&A - "Guest counts" | Texto libre: "guest counts increased/decreased X%" |
| **Average Ticket** | `Total Sales / Number of Transactions` | No está explícito en EDGAR | Calcular: SSSG - Traffic Growth |
| **Sales per Restaurant** | `Systemwide Sales / Number of Restaurants` | Item 7 | "Systemwide sales" / "Number of restaurants" |

> **Keywords EDGAR para scraping**: `comparable sales`, `systemwide sales`, `guest counts`, `average check`

### 3.2 Métricas de Franquicias (Item 7 + Segment Reporting)

| Métrica | Cálculo | Ubicación EDGAR | Notas |
|---------|---------|-----------------|-------|
| **Franchise Mix** | `Franchise Revenue / Total Revenue` | Nota 16 (Segment Reporting) | MCD reporta: U.S., International Operated Markets, International Developmental Licensed Markets |
| **Royalty Rate** | `Franchise Revenue / Franchise Sales` | No explícito | Tasa estándar MCD: ~4-5% de ventas franquiciadas |
| **Refranchising Rate** | `% de restaurantes propios vendidos` | MD&A - "refranchising" | MCD target: >95% franquiciado |

### 3.3 Métricas de Red (Item 1 + Item 7)

| Métrica | Fuente | Patrón EDGAR |
|---------|--------|--------------|
| **Net Restaurant Growth** | 10-K Item 1 (Business) | "restaurants at year-end" vs año anterior |
| **Total Restaurants** | 10-K Item 1 | Tabla: "Number of restaurants" |
| **Digital Sales Mix** | MD&A | "digital sales", "app-based sales", "kiosk sales" |
| **Delivery Penetration** | MD&A | "delivery sales", "McDelivery", "Uber Eats", "DoorDash" |

---

## 4. MÉTRICAS DE PROPIEDAD INMOBILIARIA

MCD es ~$40B en real estate (REIT-like characteristics):

| Métrica | Cálculo | Ubicación EDGAR | Notas |
|---------|---------|-----------------|-------|
| **Real Estate Value** | Valoración propiedades | Nota 1 (Summary of Significant Accounting Policies) | Propiedades en `PropertyPlantAndEquipmentNet` |
| **Rent Yield** | `Rental Income / Property Value` | Nota 16 (Revenue breakdown) | "Rental income" separado de "Sales by company-operated restaurants" |
| **Occupancy Rate** | Locales operativos / Total propiedades | Calcular: Total restaurants menos cierres / Total | ~99% típico |

**Tags XBRL relevantes**:
- `//PropertyPlantAndEquipmentNet`
- `//OperatingLeaseLiability`
- `//FinanceLeaseLiability`

---

## 5. MÉTRICAS DE DIVIDENDO (Dividend Analysis)

### 5.1 Datos de Dividendo (Item 5 + Def 14A + 8-K)

| Métrica | Fórmula | Ubicación EDGAR | Frecuencia |
|---------|---------|-----------------|------------|
| **Dividend Yield** | `Annual Dividend / Stock Price` | 8-K Item 8.01 (dividend declarations) | Trimestral |
| **Payout Ratio (Earnings)** | `Dividends / Net Income` | Income Statement + Cash Flow | Anual |
| **Payout Ratio (FCF)** | `Dividends / Free Cash Flow` | Cash Flow Statement | Anual |
| **Dividend Growth Rate** | `CAGR(Dividend)` | Histórico 8-Ks | Anual |

### 5.2 Fuentes EDGAR para Dividendos

| Formulario | Sección | Contenido |
|------------|---------|-----------|
| **8-K** | Item 8.01 - Other Events | Declaración de dividendo trimestral |
| **10-K** | Item 5 - Market for Registrant's Common Equity | Histórico de dividendos, política de dividendos |
| **DEF 14A** | Executive Compensation | Dividend equivalents, dividend policy |
| **Cash Flow Statement** | Financing Activities | `PaymentsOfDividends` (tag XBRL) |

### 5.3 Tags XBRL para Dividendos

| Tag | Descripción |
|-----|-------------|
| `//DividendsPaid` | Dividendos pagados (Cash Flow) |
| `//DividendPerShare` | Dividendo por acción declarado |
| `//CommonStockDividendsPerShareDeclared` | DPS declarado |
| `//DividendPolicy` | Texto descriptivo de política |

---


| Categoría | Métricas Universales |
|-----------|---------------------|
| **Rentabilidad** | Margen bruto, operativo, neto; ROE, ROA, ROIC |
| **Liquidez** | Current ratio, quick ratio, cash ratio |
| **Solvencia** | Debt/EBITDA, interest coverage, net debt/equity |
| **Eficiencia** | Asset turnover, working capital management |
| **Capital Allocation** | Shareholder yield, payout ratios, buybacks |
| **Dividendo** | Yield, payout ratio, cobertura, CAGR |
| **Valoración** | P/E, EV/EBITDA, P/FCF |
| **Resiliencia** | Beta, downside capture, drawdown |


Métrica Específica	Fórmula	Aplica a
Same-Store Sales Growth (SSSG)	Growth tiendas >13 meses	Todos restaurantes
Traffic vs Ticket	Descomposición SSSG	Todos restaurantes
AUV (Average Unit Volume)	Sales/unidad	Todos restaurantes
Restaurant-Level EBITDA	Margen a nivel tienda	Franquiciadores
Digital/Delivery Mix	% ventas digitales	QSR moderno
Franchise Mix	% ingresos franquicia	Franquiciadores
Royalty Rate	% ventas franquiciado	Franquiciadores
Food Cost %	COGS alimentos/Revenue	Restaurantes propios


Métrica	Por qué es específica MCD
Franchisee Rent Coverage	MCD es el mayor propietario inmobiliario privado del mundo (~$40B). Pocos tienen este modelo "REIT-híbrido"
Real Estate Yield	MCD genera ~$7B en rentas anuales de propiedades
Refranchising Strategy	MCD vendió miles de restaurantes propios a franquiciados (95% franquiciado)
Digital Mix >30%	Líder en transformación digital QSR
MyMcDonald's Rewards	Programa fidelidad específico
48 años Dividend Aristocrat	Historial específico de consistencia