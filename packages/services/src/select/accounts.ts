import type { Account } from '@crisol/types';

/**
 * Cuenta a pre-seleccionar por defecto en formularios (transacción, import,
 * ticket) y como destino del reassign. Prioridad:
 *   1. la cuenta principal (`is_default`), si está activa
 *   2. la primera cuenta de ACTIVO (`nature === 'asset'`) activa — nunca un
 *      pasivo (tarjeta/préstamo), para no contabilizar un gasto como aumento
 *      de deuda por accidente
 *   3. la primera cuenta activa (fallback)
 *
 * Devuelve `undefined` si no hay cuentas activas. Acepta la lista completa o
 * ya filtrada (vuelve a excluir archivadas de forma idempotente).
 *
 * AUDIT MEDIUM#9 / LOW#14 — antes los forms caían a `accounts[0]`, que podía
 * ser un pasivo; y el destino del reassign caía a `''`, dejando el botón
 * deshabilitado cuando el usuario no tenía cuenta principal.
 */
export function pickPreferredAccount(accounts: readonly Account[]): Account | undefined {
  const active = accounts.filter((a) => !a.is_archived);
  return active.find((a) => a.is_default) ?? active.find((a) => a.nature === 'asset') ?? active[0];
}

/** Id de `pickPreferredAccount`, o `''` si no hay cuentas activas. */
export function pickPreferredAccountId(accounts: readonly Account[]): string {
  return pickPreferredAccount(accounts)?.id ?? '';
}
