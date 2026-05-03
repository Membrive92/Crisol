export {
  apiClient,
  configureApi,
  setAccessToken,
  setRefreshToken,
  setOnAuthFailure,
} from './api/client';
export { formatApiError } from './api/errors';
export { authApi } from './api/endpoints/auth';
export { passkeysApi, type PasskeyResponse } from './api/endpoints/passkeys';
export { categoriesApi } from './api/endpoints/categories';
export { transactionsApi } from './api/endpoints/transactions';
export { dashboardApi } from './api/endpoints/dashboard';
export { importsApi, type CreateImportPayload } from './api/endpoints/imports';
export { receiptsApi } from './api/endpoints/receipts';
export {
  currencyApi,
  type ConvertQuery,
  type ConvertResponse,
  type RatesResponse,
} from './api/endpoints/currency';

export { queryKeys } from './query/keys';
export {
  useCategories,
  useCategory,
  useCreateCategory,
  useUpdateCategory,
  useDeleteCategory,
} from './query/hooks/useCategories';
export {
  useTransactions,
  useTransaction,
  useCreateTransaction,
  useUpdateTransaction,
  useDeleteTransaction,
} from './query/hooks/useTransactions';
export {
  useDashboardSummary,
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardTopExpenses,
  useUserCurrencies,
} from './query/hooks/useDashboard';
export { useImports, useImport, useCreateImport } from './query/hooks/useImports';
export {
  useReceipts,
  useReceipt,
  useExtractReceipt,
  useConfirmReceipt,
  useRejectReceipt,
  useReceiptImage,
} from './query/hooks/useReceipts';
export {
  useExchangeRates,
  exchangeRatesQueryOptions,
  type ExchangeRatesResult,
} from './query/hooks/useCurrency';
