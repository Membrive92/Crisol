/**
 * DTOs de request del módulo Inversión (PHASE-44.7).
 */

import type { CorpActionType } from '../models/investment';

export interface SecurityResolveRequest {
  ticker: string;
  /**
   * Opcional y NO vinculante (PHASE-44.8 E1): el servidor decide la plaza y
   * normaliza lo que llegue. El cliente mandaba `'US'` —un país, no un
   * mercado— y eso duplicaba filas contra la restricción única
   * `(ticker, exchange)`. Omitirlo es lo correcto salvo que se sepa la plaza
   * de verdad.
   */
  exchange?: string;
}

export interface IngestRequest {
  filings_back?: number;
}

export interface StressParamsRequest {
  revenue_drops?: string[];
  rate_shocks_bps?: number[];
  pct_variable_debt?: string;
}

export interface RunAnalysisRequest {
  stress_params?: StressParamsRequest;
}

export interface LotCreateRequest {
  security_id: string;
  account_id?: string | null;
  trade_date: string;
  quantity: string;
  price: string;
  fx_rate_at_trade?: string;
  fees?: string;
}

export interface SaleCreateRequest {
  security_id: string;
  trade_date: string;
  quantity: string;
  price: string;
  fx_rate_at_trade?: string;
  fees?: string;
}

export interface DividendCreateRequest {
  security_id: string;
  pay_date: string;
  ex_date?: string | null;
  gross_amount: string;
  withholding_tax?: string;
  net_amount?: string | null;
  currency: string;
  fx_rate?: string;
}

export interface CorporateActionCreateRequest {
  security_id: string;
  action_type: CorpActionType;
  action_date: string;
  ratio?: string | null;
  notes?: string | null;
}

export interface PricingRefreshRequest {
  security_ids?: string[];
}
