import type {
  AnalysisRun,
  AnalysisRunListResponse,
  CanonicalItemCatalogResponse,
  CanonicalItemDefinition,
  CorporateAction,
  CorporateActionCreateRequest,
  Dividend,
  DividendCreateRequest,
  FinancialStatement,
  MetricCatalogResponse,
  Valuation,
  IngestionJob,
  IngestRequest,
  Lot,
  LotCreateRequest,
  PortfolioSummary,
  Position,
  PricingRefreshRequest,
  RestatementFlag,
  RunAnalysisRequest,
  Sale,
  SaleCreateRequest,
  Security,
  SecurityResolveRequest,
  SecuritySearchResponse,
} from '@crisol/types';

import { apiClient } from '../client';

/**
 * Endpoints del módulo Inversión (PHASE-44.7). Prefijo `/investment`.
 */
export const investmentApi = {
  // ── Catálogo ────────────────────────────────────────────────────
  async searchSecurities(q: string, limit = 20): Promise<SecuritySearchResponse> {
    const response = await apiClient.get<SecuritySearchResponse>(
      '/investment/securities/search',
      { params: { q, limit } },
    );
    return response.data;
  },

  async resolveSecurity(body: SecurityResolveRequest): Promise<Security> {
    const response = await apiClient.post<Security>('/investment/securities/resolve', body);
    return response.data;
  },

  async getSecurity(securityId: string): Promise<Security> {
    const response = await apiClient.get<Security>(`/investment/securities/${securityId}`);
    return response.data;
  },

  // ── Fundamentales ───────────────────────────────────────────────
  async ingest(securityId: string, body: IngestRequest = {}): Promise<IngestionJob> {
    const response = await apiClient.post<IngestionJob>(
      `/investment/fundamentals/${securityId}/ingest`,
      body,
    );
    return response.data;
  },

  async getIngestionJob(jobId: string): Promise<IngestionJob> {
    const response = await apiClient.get<IngestionJob>(
      `/investment/fundamentals/jobs/${jobId}`,
    );
    return response.data;
  },

  async listStatements(
    securityId: string,
    view: 'latest' | 'all' = 'latest',
  ): Promise<FinancialStatement[]> {
    const response = await apiClient.get<{ items: FinancialStatement[] }>(
      `/investment/fundamentals/${securityId}/statements`,
      { params: { view } },
    );
    return response.data.items;
  },

  async listRestatements(securityId: string): Promise<RestatementFlag[]> {
    const response = await apiClient.get<{ items: RestatementFlag[] }>(
      `/investment/fundamentals/${securityId}/restatements`,
    );
    return response.data.items;
  },

  // ── Análisis ────────────────────────────────────────────────────
  async runAnalysis(securityId: string, body: RunAnalysisRequest = {}): Promise<AnalysisRun> {
    const response = await apiClient.post<AnalysisRun>(
      `/investment/analysis/${securityId}/run`,
      body,
    );
    return response.data;
  },

  async listRuns(securityId: string): Promise<AnalysisRunListResponse> {
    const response = await apiClient.get<AnalysisRunListResponse>(
      `/investment/analysis/${securityId}/runs`,
    );
    return response.data;
  },

  async getRun(runId: string): Promise<AnalysisRun> {
    const response = await apiClient.get<AnalysisRun>(`/investment/analysis/runs/${runId}`);
    return response.data;
  },

  /**
   * El último análisis de un valor, con todo el desglose. Lanza 404 si no hay
   * ninguno — es la señal de "aún no se ha analizado", no un error.
   */
  async getLatestRun(securityId: string): Promise<AnalysisRun> {
    const response = await apiClient.get<AnalysisRun>(
      `/investment/analysis/${securityId}/runs/latest`,
    );
    return response.data;
  },

  /**
   * Múltiplos de valoración contra la cotización viva (PHASE-44.12).
   *
   * `price` simula otra entrada y también cubre los valores que el proveedor no
   * cotiza. Nunca lanza por falta de cotización: responde con `available:false`
   * y el motivo, que es lo que la pantalla enseña.
   */
  async getValuation(securityId: string, price?: string): Promise<Valuation> {
    const response = await apiClient.get<Valuation>(
      `/investment/analysis/${securityId}/valuation`,
      price ? { params: { price } } : undefined,
    );
    return response.data;
  },

  /** El catálogo de las 52 métricas del engine. Estático: se cachea largo. */
  async getMetricCatalog(): Promise<MetricCatalogResponse> {
    const response = await apiClient.get<MetricCatalogResponse>('/investment/analysis/metrics');
    return response.data;
  },

  /** Las 49 partidas canónicas con su etiqueta y su bloque. Estático. */
  async getCanonicalItems(): Promise<CanonicalItemDefinition[]> {
    const response = await apiClient.get<CanonicalItemCatalogResponse>(
      '/investment/fundamentals/items',
    );
    return response.data.items;
  },

  // ── Cartera ─────────────────────────────────────────────────────
  async createLot(body: LotCreateRequest): Promise<Lot> {
    const response = await apiClient.post<Lot>('/investment/portfolio/lots', body);
    return response.data;
  },

  async listLots(securityId?: string): Promise<Lot[]> {
    const params = securityId ? { security_id: securityId } : {};
    const response = await apiClient.get<{ items: Lot[] }>('/investment/portfolio/lots', {
      params,
    });
    return response.data.items;
  },

  async deleteLot(lotId: string): Promise<void> {
    await apiClient.delete(`/investment/portfolio/lots/${lotId}`);
  },

  async createSale(body: SaleCreateRequest): Promise<Sale> {
    const response = await apiClient.post<Sale>('/investment/portfolio/sales', body);
    return response.data;
  },

  async listSales(): Promise<Sale[]> {
    const response = await apiClient.get<{ items: Sale[] }>('/investment/portfolio/sales');
    return response.data.items;
  },

  async deleteSale(saleId: string): Promise<void> {
    await apiClient.delete(`/investment/portfolio/sales/${saleId}`);
  },

  async createDividend(body: DividendCreateRequest): Promise<Dividend> {
    const response = await apiClient.post<Dividend>('/investment/portfolio/dividends', body);
    return response.data;
  },

  async listDividends(): Promise<Dividend[]> {
    const response = await apiClient.get<{ items: Dividend[] }>(
      '/investment/portfolio/dividends',
    );
    return response.data.items;
  },

  async deleteDividend(dividendId: string): Promise<void> {
    await apiClient.delete(`/investment/portfolio/dividends/${dividendId}`);
  },

  async registerCorporateAction(
    body: CorporateActionCreateRequest,
  ): Promise<CorporateAction> {
    const response = await apiClient.post<CorporateAction>(
      '/investment/portfolio/corporate-actions',
      body,
    );
    return response.data;
  },

  async listCorporateActions(): Promise<CorporateAction[]> {
    const response = await apiClient.get<{ items: CorporateAction[] }>(
      '/investment/portfolio/corporate-actions',
    );
    return response.data.items;
  },

  async applyCorporateAction(actionId: string): Promise<CorporateAction> {
    const response = await apiClient.post<CorporateAction>(
      `/investment/portfolio/corporate-actions/${actionId}/apply`,
    );
    return response.data;
  },

  async listPositions(): Promise<Position[]> {
    const response = await apiClient.get<{ items: Position[] }>(
      '/investment/portfolio/positions',
    );
    return response.data.items;
  },

  // ── Precios ─────────────────────────────────────────────────────
  async getPortfolioSummary(): Promise<PortfolioSummary> {
    const response = await apiClient.get<PortfolioSummary>('/investment/portfolio/summary');
    return response.data;
  },

  async refreshPricing(
    body: PricingRefreshRequest = {},
  ): Promise<{ refreshed: number; pricing_enabled: boolean }> {
    const response = await apiClient.post<{ refreshed: number; pricing_enabled: boolean }>(
      '/investment/pricing/refresh',
      body,
    );
    return response.data;
  },
};
