export {
  apiClient,
  configureApi,
  setAccessToken,
  setRefreshToken,
  setOnAuthFailure,
} from './api/client';
export { formatApiError } from './api/errors';
export { authApi } from './api/endpoints/auth';
export { categoriesApi } from './api/endpoints/categories';
export { transactionsApi } from './api/endpoints/transactions';
export { dashboardApi } from './api/endpoints/dashboard';
export { importsApi, type CreateImportPayload } from './api/endpoints/imports';
export { receiptsApi } from './api/endpoints/receipts';

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
} from './query/hooks/useDashboard';
export { useImports, useImport, useCreateImport } from './query/hooks/useImports';
export {
  useReceipts,
  useReceipt,
  useExtractReceipt,
  useConfirmReceipt,
  useRejectReceipt,
} from './query/hooks/useReceipts';
