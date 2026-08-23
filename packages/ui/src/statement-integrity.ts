/**
 * PHASE-47.G — qué decirle al usuario cuando la app y su banco no coinciden.
 *
 * Capa PURA (sin React) para que web y móvil digan lo MISMO. La lección de
 * [PHASE-44.13] es exactamente ésta: compartir el cálculo no basta si cada app
 * se guarda su propia lista de qué mostrar.
 *
 * Dos avisos distintos, y conviene no mezclarlos:
 *
 * - **La diferencia** (`statement_gap`): el saldo de la app ya no coincide con
 *   el que imprimió el banco. Como el ancla se fija al importar, en ese momento
 *   la diferencia era 0 — así que si ahora no lo es, algo la movió DESPUÉS.
 * - **El hueco** (`statement_seams`): faltan movimientos por importar. Éste no
 *   descuadra nada visible, porque al anclar se absorbe en el saldo inicial;
 *   por eso hay que decirlo en voz alta o no se entera nadie.
 */

import { formatAmount, formatCivilDate } from './format';

export interface StatementSeamLike {
  after: string;
  before: string;
  amount: string;
}

export interface StatementIntegrityInput {
  /** `null`/ausente = la cuenta nunca se ancló a un extracto. */
  statementGap?: string | null | undefined;
  seams?: StatementSeamLike[] | undefined;
  currency: string;
}

export interface StatementIntegrityNotice {
  kind: 'gap' | 'seam';
  message: string;
}

/** Por debajo de un céntimo no hay nada que avisar: es ruido de redondeo. */
const TOLERANCE = 0.01;

/**
 * Las frases que hay que enseñar, o `[]` si la cuenta cuadra.
 *
 * Se comprueba por VERDAD y no contra `null`: un backend anterior a esta fase
 * no manda el campo, y `undefined !== null` habría marcado TODAS las cuentas
 * (es el asterisco que salía en cada fila en [PHASE-47.E]).
 */
export function statementIntegrityNotices({
  statementGap,
  seams,
  currency,
}: StatementIntegrityInput): StatementIntegrityNotice[] {
  const notices: StatementIntegrityNotice[] = [];

  if (statementGap) {
    const value = Number(statementGap);
    if (Number.isFinite(value) && Math.abs(value) >= TOLERANCE) {
      const direccion = value > 0 ? 'por encima' : 'por debajo';
      notices.push({
        kind: 'gap',
        message:
          `La app calcula ${formatAmount(String(Math.abs(value)), currency)} ${direccion} ` +
          'de lo que dijo tu último extracto. Algo movió el saldo después de importarlo.',
      });
    }
  }

  for (const seam of seams ?? []) {
    notices.push({
      kind: 'seam',
      message:
        `Faltan movimientos entre el ${formatCivilDate(seam.after)} y el ${formatCivilDate(seam.before)}: ` +
        `${formatAmount(String(Math.abs(Number(seam.amount))), currency)} que tu banco movió y ` +
        'la app no tiene. Importa el extracto de esos días.',
    });
  }

  return notices;
}
