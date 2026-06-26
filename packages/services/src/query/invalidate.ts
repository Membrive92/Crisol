import type { QueryClient } from '@tanstack/react-query';

import { queryKeys } from './keys';

/**
 * Invalida de forma consistente TODAS las caches que dependen del
 * conjunto de transacciones del usuario.
 *
 * Cualquier mutación que cree, edite, borre o restaure transacciones
 * (incluidos commit de import y confirm de receipt, que persisten tx)
 * mueve potencialmente:
 * - el listado / papelera / detalle / periodos disponibles (`transactions.all`),
 * - los KPIs y gráficas del dashboard (`dashboard.all`),
 * - el estado de los presupuestos por categoría (`budgets.all`),
 * - los saldos y la lista de cuentas (`accounts.all`, engloba `balances`),
 * - la salud y el resumen de deuda — Capa 1 + Capa 2 (`debt.all`).
 *
 * Se invalida por prefijo de grupo, así que engloba cualquier
 * invalidación específica (p. ej. `accounts.balances()`) que algún
 * `onSuccess` mantuviera por separado.
 *
 * AUDIT-2026-06: centraliza el "blast radius" de las mutaciones de tx
 * que estaba disperso e incompleto entre hooks (saldos/deuda stale tras
 * crear/editar tx, commit import y confirm receipt).
 *
 * @param queryClient - cliente de TanStack Query del contexto.
 */
export function invalidateTransactionSideEffects(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all });
  void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
  void queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all });
  void queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
  void queryClient.invalidateQueries({ queryKey: queryKeys.debt.all });
}
