export type { User } from './models/user';
export type { AppModule, ModuleId, ModuleSection } from './models/module';
export {
  MODULES,
  DEFAULT_MODULE_ID,
  PERSONAL_FINANCE_BASE,
  getModule,
  findModuleByPath,
} from './registry/modules';
export type { Category, CategoryKind } from './models/category';
export type { BudgetAlert, Transaction, TransactionSource } from './models/transaction';
export type {
  DashboardSummary,
  CategoryBreakdownItem,
  MonthlyBucket,
  TopExpenseItem,
} from './models/dashboard';
export type {
  ImportColumnMappings,
  ImportErrorEntry,
  ImportJob,
  ImportJobStatus,
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
  Subscription,
  SubscriptionStatus,
  SubscriptionScanResponse,
} from './models/subscription';

export type {
  LoginRequest,
  RegisterRequest,
  RefreshRequest,
  TokenResponse,
} from './dto/auth.dto';

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
  DashboardSummaryQuery,
  DashboardByCategoryQuery,
  DashboardByMonthQuery,
  DashboardTopExpensesQuery,
} from './dto/dashboard.dto';

export type { ImportListQuery, ImportListResponse } from './dto/import.dto';

export type {
  ReceiptConfirmRequest,
  ReceiptExtractResponse,
  ReceiptListQuery,
  ReceiptListResponse,
} from './dto/receipt.dto';

export type { BudgetCreateRequest, BudgetUpdateRequest } from './dto/budget.dto';
