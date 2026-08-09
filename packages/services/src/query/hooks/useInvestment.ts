import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  AnalysisRun,
  CorporateActionCreateRequest,
  DividendCreateRequest,
  IngestionJob,
  LotCreateRequest,
  PricingRefreshRequest,
  RunAnalysisRequest,
  SaleCreateRequest,
  Security,
  SecurityAdoptRequest,
  SecurityResolveRequest,
} from '@crisol/types';

import { investmentApi } from '../../api/endpoints/investment';
import { queryKeys } from '../keys';
import { useDebouncedValue } from './useDebouncedValue';

// ── Catálogo ──────────────────────────────────────────────────────────

/** Caracteres mínimos antes de molestar al servidor. Con uno solo, `a` traía
 *  medio catálogo y ninguna de esas filas era la que el usuario buscaba. */
export const SEARCH_MIN_LENGTH = 2;

/** Espera tras la última tecla. 250 ms es el punto donde el listado ya no
 *  parpadea y todavía no se percibe lentitud al teclear. */
export const SEARCH_DEBOUNCE_MS = 250;

/**
 * Busca valores en el catálogo.
 *
 * El término se retrasa {@link SEARCH_DEBOUNCE_MS} tras la última pulsación:
 * antes de PHASE-44.8 E1 cada tecla lanzaba una petición —teclear `MCDONALDS`
 * eran nueve— y la lista parpadeaba entre respuestas. `placeholderData` mantiene
 * en pantalla los resultados anteriores mientras llega la siguiente tanda.
 */
export function useSecuritySearch(q: string) {
  const query = useDebouncedValue(q.trim(), SEARCH_DEBOUNCE_MS);
  return useQuery({
    queryKey: queryKeys.investment.search(query),
    queryFn: () => investmentApi.searchSecurities(query),
    enabled: query.length >= SEARCH_MIN_LENGTH,
    staleTime: 60_000,
    placeholderData: (previous) => previous,
  });
}

export function useSecurity(securityId: string | null) {
  return useQuery({
    queryKey: queryKeys.investment.security(securityId ?? ''),
    queryFn: () => investmentApi.getSecurity(securityId as string),
    enabled: Boolean(securityId),
    staleTime: 5 * 60_000,
  });
}

export function useResolveSecurity() {
  const qc = useQueryClient();
  return useMutation<Security, Error, SecurityResolveRequest>({
    mutationFn: (body) => investmentApi.resolveSecurity(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.investment.all }),
  });
}

/**
 * Materializa un resultado del buscador (PHASE-44.8 E2).
 *
 * Sustituye a `useResolveSecurity` cuando se elige una fila del desplegable: la
 * `listing_key` lleva la plaza que el índice conoce, mientras que resolver por
 * ticker suelto la pierde y guarda el valor como `UNKNOWN`.
 */
export function useAdoptSecurity() {
  const qc = useQueryClient();
  return useMutation<Security, Error, SecurityAdoptRequest>({
    mutationFn: (body) => investmentApi.adoptSecurity(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.investment.all }),
  });
}

// ── Fundamentales ─────────────────────────────────────────────────────

export function useStatements(securityId: string | null, view: 'latest' | 'all' = 'latest') {
  return useQuery({
    queryKey: queryKeys.investment.statements(securityId ?? '', view),
    queryFn: () => investmentApi.listStatements(securityId as string, view),
    enabled: Boolean(securityId),
    staleTime: 5 * 60_000,
  });
}

export function useRestatements(securityId: string | null) {
  return useQuery({
    queryKey: queryKeys.investment.restatements(securityId ?? ''),
    queryFn: () => investmentApi.listRestatements(securityId as string),
    enabled: Boolean(securityId),
    staleTime: 5 * 60_000,
  });
}

export function useIngest() {
  const qc = useQueryClient();
  return useMutation<IngestionJob, Error, { securityId: string; filings_back?: number }>({
    mutationFn: ({ securityId, filings_back }) =>
      investmentApi.ingest(securityId, filings_back !== undefined ? { filings_back } : {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.investment.all }),
  });
}

/** Polling del job de ingesta: refresca cada 1,5s mientras corre, para al terminar. */
export function useIngestionJob(jobId: string | null) {
  return useQuery({
    queryKey: queryKeys.investment.job(jobId ?? ''),
    queryFn: () => investmentApi.getIngestionJob(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'pending' || status === 'running' ? 1500 : false;
    },
  });
}

// ── Análisis ──────────────────────────────────────────────────────────

export function useRunAnalysis() {
  const qc = useQueryClient();
  return useMutation<AnalysisRun, Error, { securityId: string; body?: RunAnalysisRequest }>({
    mutationFn: ({ securityId, body }) => investmentApi.runAnalysis(securityId, body ?? {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.investment.all }),
  });
}

export function useAnalysisRuns(securityId: string | null) {
  return useQuery({
    queryKey: queryKeys.investment.runs(securityId ?? ''),
    queryFn: () => investmentApi.listRuns(securityId as string),
    enabled: Boolean(securityId),
  });
}

export function useAnalysisRun(runId: string | null) {
  return useQuery({
    queryKey: queryKeys.investment.run(runId ?? ''),
    queryFn: () => investmentApi.getRun(runId as string),
    enabled: Boolean(runId),
    staleTime: 5 * 60_000,
  });
}

/**
 * El último análisis persistido de un valor (PHASE-44.9).
 *
 * Es lo que abre la pantalla de informe. Antes el informe vivía en la respuesta
 * de la mutación `useRunAnalysis` y desaparecía al recargar la página.
 *
 * Un 404 aquí NO es un fallo: significa «este valor todavía no se ha
 * analizado». Por eso no se reintenta — reintentar un 404 sólo retrasa el
 * momento en que la pantalla puede ofrecer el botón de analizar.
 */
export function useLatestAnalysisRun(securityId: string | null) {
  return useQuery({
    queryKey: queryKeys.investment.latestRun(securityId ?? ''),
    queryFn: () => investmentApi.getLatestRun(securityId as string),
    enabled: Boolean(securityId),
    staleTime: 5 * 60_000,
    retry: false,
  });
}

/**
 * Múltiplos de valoración contra la cotización viva (PHASE-44.12).
 *
 * `staleTime` corto y no compartido con el análisis: el veredicto forense sale
 * de cuentas cerradas y aguanta minutos, pero esto depende del precio. `price`
 * entra en la query key, así que simular otra entrada es una consulta distinta
 * y no reutiliza la anterior.
 *
 * No reintenta: cuando no hay cotización el backend responde 200 con el motivo,
 * así que un fallo aquí es de red y reintentar sólo retrasa el mensaje.
 */
export function useValuation(securityId: string | null, price?: string) {
  return useQuery({
    queryKey: queryKeys.investment.valuation(securityId ?? '', price),
    queryFn: () => investmentApi.getValuation(securityId as string, price),
    enabled: Boolean(securityId),
    staleTime: 60_000,
    retry: false,
  });
}

/**
 * El catálogo de métricas del engine: etiqueta, familia, unidad y cortes.
 *
 * Es la definición del motor, no datos del usuario: no cambia hasta que cambia
 * `engine_version`. De ahí el `staleTime` de una hora y la key fuera de
 * `investment.all` — una mutación del módulo no debe volver a pedirlo.
 */
export function useMetricCatalog() {
  return useQuery({
    queryKey: queryKeys.investment.metricCatalog(),
    queryFn: () => investmentApi.getMetricCatalog(),
    staleTime: 60 * 60_000,
  });
}

/** Las 49 partidas canónicas con su etiqueta en español y su bloque. Estático. */
export function useCanonicalItems() {
  return useQuery({
    queryKey: queryKeys.investment.canonicalItems(),
    queryFn: () => investmentApi.getCanonicalItems(),
    staleTime: 60 * 60_000,
  });
}

// ── Cartera ───────────────────────────────────────────────────────────

export function useLots(securityId?: string) {
  return useQuery({
    queryKey: queryKeys.investment.lots(securityId),
    queryFn: () => investmentApi.listLots(securityId),
  });
}

export function usePositions() {
  return useQuery({
    queryKey: queryKeys.investment.positions(),
    queryFn: () => investmentApi.listPositions(),
  });
}

export function useCorporateActions() {
  return useQuery({
    queryKey: queryKeys.investment.corporateActions(),
    queryFn: () => investmentApi.listCorporateActions(),
  });
}

function useInvestmentMutation<TData, TVars>(
  mutationFn: (vars: TVars) => Promise<TData>,
) {
  const qc = useQueryClient();
  return useMutation<TData, Error, TVars>({
    mutationFn,
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.investment.all }),
  });
}

export function useCreateLot() {
  return useInvestmentMutation((body: LotCreateRequest) => investmentApi.createLot(body));
}

export function useDeleteLot() {
  return useInvestmentMutation((lotId: string) => investmentApi.deleteLot(lotId));
}

export function useCreateSale() {
  return useInvestmentMutation((body: SaleCreateRequest) => investmentApi.createSale(body));
}

export function useDeleteSale() {
  return useInvestmentMutation((saleId: string) => investmentApi.deleteSale(saleId));
}

export function useCreateDividend() {
  return useInvestmentMutation((body: DividendCreateRequest) =>
    investmentApi.createDividend(body),
  );
}

export function useRegisterCorporateAction() {
  return useInvestmentMutation((body: CorporateActionCreateRequest) =>
    investmentApi.registerCorporateAction(body),
  );
}

export function useApplyCorporateAction() {
  return useInvestmentMutation((actionId: string) =>
    investmentApi.applyCorporateAction(actionId),
  );
}

// ── Precios ───────────────────────────────────────────────────────────

export function usePortfolioSummary() {
  return useQuery({
    queryKey: queryKeys.investment.summary(),
    queryFn: () => investmentApi.getPortfolioSummary(),
    staleTime: 60_000,
  });
}

export function useRefreshPricing() {
  return useInvestmentMutation((body: PricingRefreshRequest = {}) =>
    investmentApi.refreshPricing(body),
  );
}
