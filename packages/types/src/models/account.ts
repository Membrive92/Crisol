/**
 * Tipos del dominio de cuentas (PHASE-19.1, PHASE-22).
 *
 * Mantén el enum sincronizado con `backend/.../accounts/models.py`.
 */

export type AccountType =
  | 'bank'
  | 'savings'
  | 'brokerage'
  | 'crypto'
  | 'cash'
  | 'credit_card'
  | 'loan'
  | 'mortgage';

export type AccountNature = 'asset' | 'liability';

/** Tipos `asset` (dinero disponible). */
export const ASSET_ACCOUNT_TYPES: readonly AccountType[] = [
  'bank',
  'savings',
  'brokerage',
  'crypto',
  'cash',
] as const;

/** Tipos `liability` (deuda). PHASE-22. */
export const LIABILITY_ACCOUNT_TYPES: readonly AccountType[] = [
  'credit_card',
  'loan',
  'mortgage',
] as const;

/** Cualquier tipo que el form expone al usuario. */
export const SELECTABLE_ACCOUNT_TYPES: readonly AccountType[] = [
  ...ASSET_ACCOUNT_TYPES,
  ...LIABILITY_ACCOUNT_TYPES,
] as const;

/** Tipos a los que aplica el cuadro francés (apr/term/start_date).
 * PHASE-24.2: tarjetas financiadas también lo aceptan. */
export const AMORTIZABLE_ACCOUNT_TYPES: readonly AccountType[] = [
  'loan',
  'mortgage',
  'credit_card',
] as const;

export interface Account {
  id: string;
  user_id: string;
  name: string;
  type: AccountType;
  nature: AccountNature;
  currency: string;
  color: string | null;
  icon: string | null;
  /** Decimal serializado como string. */
  opening_balance: string;
  /** YYYY-MM-DD o null. */
  opening_balance_date: string | null;
  /** TIN anual decimal (0.0350 = 3.50% TIN). Sólo tipos amortizables. */
  apr: string | null;
  /** PHASE-24.2 — TAE anual decimal. Informativa, no afecta cálculo. */
  tae: string | null;
  /** Plazo total en meses. Sólo tipos amortizables. */
  term_months: number | null;
  /** YYYY-MM-DD. Inicio del préstamo. Sólo tipos amortizables. */
  start_date: string | null;
  /** PHASE-24.3 — Total contractualizado por el banco. */
  total_to_pay?: string | null;
  /** PHASE-24.3 — Primera cuota especial sólo de intereses. */
  interest_only_first_payment?: string | null;
  display_order: number;
  is_archived: boolean;
  /** PHASE-32 — Cuenta principal del usuario: pre-seleccionada en los
   * formularios (transacción, import, ticket). Única por usuario. */
  is_default: boolean;
  /** PHASE-40 — ¿Cuenta como DEUDA? `false` en tarjetas de crédito que se
   * pagan íntegras cada mes (revolving): salen del módulo de deuda (deuda viva,
   * DTI, composición, movimientos) pero siguen en el patrimonio neto. Sólo
   * significativo en liabilities. */
  counts_as_debt: boolean;
  /** PHASE-30.4 — Categoría de pagos vinculada (chip en Capa 2 de
   * /debt). NULL = sin vincular. Sólo significativo en liabilities. */
  category_id?: string | null;
  /** PHASE-35 — Tarjeta padre cuando esta cuenta es una COMPRA A PLAZOS
   * dentro de una tarjeta de crédito. NULL = cuenta normal. La vista de
   * deuda agrupa las hijas bajo el padre; los selectores de transacción
   * las ocultan. */
  parent_account_id?: string | null;
  /** PHASE-47.A — Cuenta de ACTIVO desde la que se cobra este pasivo (el
   * cargo del banco). Sólo significativo en liabilities; NULL = sin declarar.
   *
   * Existe porque el cargo de cierre de una tarjeta vive en la cuenta del
   * banco, no en la tarjeta, así que sin este dato no se puede saber qué
   * cargo cierra qué ciclo: no hay invariante de conservación ni detección
   * automática. La app propone un candidato a partir de los enlaces que ya
   * hiciste (PHASE-45), pero lo adjudicas tú (ADR-0011). */
  settlement_account_id?: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * PHASE-47.A — Propuesta del servidor sobre desde qué cuenta de activo se cobra
 * un pasivo, derivada de los enlaces que el usuario YA hizo (PHASE-45).
 *
 * No se persiste ni se aplica sola: se ofrece precargada en el formulario con
 * su motivo escrito y el usuario adjudica (ADR-0011). Sin evidencia,
 * `account_id` es `null` y no se propone nada — decir «probablemente BBVA»
 * sin haber contado nada sería adivinar.
 */
export interface SettlementCandidate {
  account_id: string | null;
  account_name: string | null;
  /** Frase en español con la evidencia contada, o `null` si no la hay. */
  reason: string | null;
  /** Cargos que apuntan a la cuenta propuesta. */
  matches: number;
  /** Cargos con origen identificable examinados en total. */
  total: number;
}
