/**
 * DTOs del módulo budgets (PHASE-12.2).
 */

export interface BudgetCreateRequest {
  /** `null` o ausente = budget global del mes. */
  category_id?: string | null;
  /** Decimal como string (ej. `"300.00"`). */
  amount: string;
  /** ISO 4217. */
  currency: string;
  /** ISO date `YYYY-MM-DD`. */
  effective_from: string;
  /** PHASE-16: opt-in cross-currency. Default `false` en backend. */
  convert_other_currencies?: boolean;
}

export interface BudgetUpdateRequest {
  amount?: string;
  currency?: string;
  convert_other_currencies?: boolean;
}
