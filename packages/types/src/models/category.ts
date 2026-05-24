export type CategoryKind = 'income' | 'expense';

export interface Category {
  id: string;
  user_id: string;
  name: string;
  icon: string | null;
  color: string | null;
  kind: CategoryKind;
  /**
   * PHASE-23.1: si `true`, las txs con esta categoría son transferencias
   * internas y quedan fuera del cashflow agregado (dashboard,
   * presupuestos), pero SIGUEN contribuyendo al saldo de la cuenta con
   * el signo dictado por `kind`. Separa "es transferencia" del "signo
   * en balance" — corrige el bug de PHASE-23 que rompía saldos.
   */
  is_transfer: boolean;
  created_at: string;
  updated_at: string;
}
