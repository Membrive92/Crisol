import { describe, expect, it } from 'vitest';

import { statementIntegrityNotices } from './statement-integrity';

describe('statementIntegrityNotices', () => {
  it('calla cuando la cuenta cuadra', () => {
    expect(statementIntegrityNotices({ statementGap: '0.00', seams: [], currency: 'EUR' })).toEqual(
      [],
    );
  });

  it('calla cuando el servidor no manda el campo', () => {
    // El caso que importa: un backend anterior a 47.G omite `statement_gap`.
    // Comparando con `null` en vez de por verdad, TODAS las cuentas saldrían
    // marcadas — es el asterisco que apareció en cada fila en PHASE-47.E. El
    // test omite la clave a propósito; ponerla a `null` no probaría nada.
    expect(statementIntegrityNotices({ currency: 'EUR' })).toEqual([]);
  });

  it('avisa cuando la app va por debajo del extracto', () => {
    const [notice] = statementIntegrityNotices({ statementGap: '-700.26', currency: 'EUR' });
    expect(notice?.kind).toBe('gap');
    expect(notice?.message).toContain('por debajo');
    // El importe se enseña en positivo: el signo ya lo dice la frase.
    expect(notice?.message).not.toContain('-700');
  });

  it('ignora un descuadre menor de un céntimo', () => {
    expect(statementIntegrityNotices({ statementGap: '0.004', currency: 'EUR' })).toEqual([]);
  });

  it('dice entre qué fechas falta extracto y cuánto', () => {
    const [notice] = statementIntegrityNotices({
      seams: [{ after: '2026-06-29T00:00:00Z', before: '2026-07-05T00:00:00Z', amount: '-1211.95' }],
      currency: 'EUR',
    });
    expect(notice?.kind).toBe('seam');
    expect(notice?.message).toContain('Importa el extracto');
    expect(notice?.message).toContain('1211,95');
    // En positivo, igual que arriba: el sentido lo dice la frase, no un menos.
    expect(notice?.message).not.toContain('-1211');
  });
});
