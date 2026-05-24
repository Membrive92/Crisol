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
export { accountsApi, type AccountListQuery } from './api/endpoints/accounts';
export { transfersApi } from './api/endpoints/transfers';
export { categoriesApi } from './api/endpoints/categories';
export { transactionsApi } from './api/endpoints/transactions';
export { dashboardApi } from './api/endpoints/dashboard';
export { budgetsApi } from './api/endpoints/budgets';
export {
  fixedExpensesApi,
  type AutopostResponse,
  type FixedExpenseListQuery,
  type FixedExpenseUpdatePayload,
} from './api/endpoints/fixed-expenses';
export {
  importsApi,
  type CreateImportPayload,
  type PreviewImportPayload,
} from './api/endpoints/imports';
export {
  bankMappingsApi,
  type BankMappingUpsertPayload,
} from './api/endpoints/bank-mappings';
export { categoryRulesApi } from './api/endpoints/category-rules';
export { receiptsApi } from './api/endpoints/receipts';
export {
  currencyApi,
  type ConvertQuery,
  type ConvertResponse,
  type RatesResponse,
} from './api/endpoints/currency';

export { queryKeys } from './query/keys';
export {
  useAccount,
  useAccountBalances,
  useAccounts,
  useAmortizationSchedule,
  useCreateAccount,
  useDebtHealth,
  useDebtHistory,
  useDeleteAccount,
  usePayInstallment,
  useRegenerateAmortization,
  useUnpayInstallment,
  useUpdateAccount,
  useUpdateInstallment,
} from './query/hooks/useAccounts';
export {
  useConvertToDebt,
  useConvertToTransfer,
  useLinkTransfer,
  useMarkTransfer,
  useMatchTransfers,
  useTransferCandidates,
  useTransfers,
  useTransferSuspects,
  useUnlinkTransfer,
} from './query/hooks/useTransfers';
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
  useTransactionAvailablePeriods,
  useCreateTransaction,
  useUpdateTransaction,
  useDeleteTransaction,
  useBulkDeleteTransactions,
  useTrashedTransactions,
  useRestoreTransaction,
  usePurgeTransaction,
  useBulkRestoreTrash,
  useBulkPurgeTrash,
} from './query/hooks/useTransactions';
export {
  useCategoryAvailablePeriods,
  useCategoryDetail,
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
  useDashboardTopExpenses,
  useUserCurrencies,
} from './query/hooks/useDashboard';
export {
  useImports,
  useImport,
  useCreateImport,
  usePreviewImport,
  useCommitImport,
  useAiSuggestImport,
  type CommitImportPayload,
} from './query/hooks/useImports';
export {
  useBankMappings,
  useUpsertBankMapping,
  useDeleteBankMapping,
} from './query/hooks/useBankMappings';
export {
  useCategoryRules,
  useCreateCategoryRule,
  useUpdateCategoryRule,
  useDeleteCategoryRule,
  useSeedRecommended,
} from './query/hooks/useCategoryRules';
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
export {
  useBudgets,
  useBudget,
  useBudgetStatus,
  useCreateBudget,
  useUpdateBudget,
  useDeleteBudget,
} from './query/hooks/useBudgets';
export {
  useFixedExpenses,
  useFixedExpense,
  useScanFixedExpenses,
  useAutopostFixedExpenses,
  useUpdateFixedExpense,
  useConfirmFixedExpense,
  useDismissFixedExpense,
  useDeleteFixedExpense,
  usePauseFixedExpense,
  useResumeFixedExpense,
  useCancelFixedExpense,
} from './query/hooks/useFixedExpenses';
