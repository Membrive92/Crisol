export type { User } from './models/user';
export type { AppModule, ModuleId, ModuleSection } from './models/module';
export {
  MODULES,
  DEFAULT_MODULE_ID,
  PERSONAL_FINANCE_BASE,
  getModule,
  findModuleByPath,
} from './registry/modules';
export type {
  Account,
  AccountNature,
  AccountType,
} from './models/account';
export {
  AMORTIZABLE_ACCOUNT_TYPES,
  ASSET_ACCOUNT_TYPES,
  LIABILITY_ACCOUNT_TYPES,
  SELECTABLE_ACCOUNT_TYPES,
} from './models/account';
export type {
  AccountBalance,
  AccountBalancesResponse,
} from './models/account-balance';
export type {
  PositionAsOf,
  PositionHistoryResponse,
  PositionPoint,
} from './models/position';
export type {
  AnalyticsCategoryAmount,
  AnalyticsTxRef,
  CategoryStructureExplain,
  CommittedItem,
  ExpenseStructureResponse,
  MonthOutlookResponse,
  StructureReason,
} from './models/analytics';
export type {
  AmortizationRow,
  AmortizationSchedule,
  DailyDebtPoint,
  DebtCategorySummary,
  DebtHealthKpis,
  DebtHistoryPoint,
  DebtHistoryPointKind,
  DebtHistoryResponse,
  DebtTimeRange,
  DebtTypeBreakdown,
  DebtTypeBucket,
  DtiStatus,
  EffortStatus,
  InstallmentBulkPayRequest,
  InstallmentBulkPayResponse,
  InstallmentPayRequest,
  InstallmentUpdateRequest,
  MonthlyDebtPoint,
  RecurringQuotaRef,
} from './models/debt';
export type {
  MisclassifiedTransfer,
  ReclassifyBulkResponse,
  TransferPair,
} from './models/transfer';
export type {
  Category,
  CategoryKind,
  CategoryRole,
  ExpenseNature,
} from './models/category';
export type {
  CategoryRule,
  CategoryRuleCreateRequest,
  CategoryRuleUpdateRequest,
  RuleField,
  RuleMatchType,
  SeedResult,
} from './models/category-rule';
export type {
  BudgetAlert,
  Transaction,
  TransactionFlow,
  TransactionSource,
} from './models/transaction';
export type {
  CategoryBreakdownItem,
  CategoryDetail,
  CategoryMonthlyBucket,
  DashboardSummary,
  ModuleDashboardSummary,
  ModuleSummaryItem,
  ModuleVerdict,
  MonthlyBucket,
  TopExpenseItem,
} from './models/dashboard';
export type {
  BankCategoryMapping,
  ImportColumnMappings,
  ImportErrorEntry,
  ImportJob,
  ImportJobStatus,
  ImportPreviewBankConceptGroup,
  ImportPreviewResponse,
  ImportPreviewRow,
  ImportSource,
  ImportSuggestionSource,
} from './models/import';
export type {
  Receipt,
  ReceiptExtraction,
  ReceiptLineItem,
  ReceiptStatus,
} from './models/receipt';
export type { Toast, ToastAction, ToastInput, ToastKind } from './models/toast';
export type {
  Budget,
  BudgetStatus,
  BudgetStatusItem,
  BudgetStatusResponse,
} from './models/budget';
export type {
  FixedExpense,
  FixedExpenseStatus,
  FixedExpenseScanResponse,
} from './models/fixed-expense';

export type {
  LoginRequest,
  RegisterRequest,
  RefreshRequest,
  TokenResponse,
} from './dto/auth.dto';

export type {
  AccountCreateRequest,
  AccountUpdateRequest,
} from './dto/account.dto';

export type {
  NewLiabilityForDebt,
  TransferFromSourceDebtRequest,
  TransferFromSourceRequest,
  TransferLinkRequest,
} from './dto/transfer.dto';

export type {
  CategoryCreateRequest,
  CategoryUpdateRequest,
} from './dto/category.dto';

export type {
  TransactionCreateRequest,
  TransactionUpdateRequest,
  TransactionListQuery,
  TransactionListResponse,
} from './dto/transaction.dto';

export type {
  DashboardByCategoryQuery,
  DashboardByMonthQuery,
  DashboardCategoryDetailQuery,
  DashboardSummaryQuery,
  DashboardTopExpensesQuery,
} from './dto/dashboard.dto';

export type { ExpenseStructureQuery, MonthOutlookQuery } from './dto/analytics.dto';

export type { ImportListQuery, ImportListResponse } from './dto/import.dto';

export type {
  ReceiptConfirmRequest,
  ReceiptExtractResponse,
  ReceiptListQuery,
  ReceiptListResponse,
} from './dto/receipt.dto';

export type { BudgetCreateRequest, BudgetUpdateRequest } from './dto/budget.dto';
