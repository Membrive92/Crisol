/**
 * El reparto fijo/variable del desglose, y cómo se parte lo APLAZADO con él.
 *
 * Los tres primeros casos vienen de `apps/web` tal cual: la función vivía
 * duplicada en las dos apps y sus tests sólo cubrían la copia de web.
 */

import { describe, expect, it } from 'vitest';

import {
  deriveStructural,
  toBreakdownRow,
  type BreakdownRow,
  type ExceptionalRow,
} from './breakdown-structure';

function fila(
  id: string | null,
  name: string,
  total: string,
  deferred?: string | null,
): BreakdownRow {
  return {
    category_id: id,
    category_name: name,
    category_kind: 'expense',
    category_color: null,
    category_icon: null,
    total,
    count: 1,
    ...(deferred === undefined ? {} : { deferred_total: deferred }),
  };
}

function puntual(
  id: string | null,
  name: string | null,
  total: string,
  deferred?: string | null,
): ExceptionalRow {
  return {
    category_id: id,
    category_name: name,
    color: null,
    icon: null,
    total,
    ...(deferred === undefined ? {} : { deferred_total: deferred }),
  };
}

describe('deriveStructural', () => {
  it('estructural por categoría = total − puntual', () => {
    const out = deriveStructural(
      [fila('a', 'Super', '100.00'), fila('b', 'Luz', '50.00')],
      [puntual('a', 'Super', '30.00')],
    );
    const byId = Object.fromEntries(out.map((x) => [x.category_id, Number(x.total)]));
    expect(byId['a']).toBeCloseTo(70); // 100 − 30
    expect(byId['b']).toBeCloseTo(50); // sin puntual → todo estructural
  });

  it('descarta categorías cuyo estructural queda ~0', () => {
    expect(
      deriveStructural([fila('c', 'Dentista', '20.00')], [puntual('c', 'Dentista', '20.00')]),
    ).toEqual([]);
  });

  it('empareja el bucket sin categoría por id nulo', () => {
    expect(
      deriveStructural(
        [fila(null, 'Sin categoría', '40.00')],
        [puntual(null, 'Sin categoría', '40.00')],
      ),
    ).toEqual([]);
  });

  it('parte lo aplazado por la misma resta que el total', () => {
    // Los datos reales de junio: «Ropa» es 219,15 € enteros, todos aplazados y
    // todos puntuales → en la vista de Fijo no queda nada de ella.
    // «Supermercado» tiene 208,29 € de los que 87,73 € están aplazados, y nada
    // puntual → en Fijo se queda con los dos números intactos.
    const out = deriveStructural(
      [fila('sup', 'Supermercado', '208.29', '87.73'), fila('ropa', 'Ropa', '219.15', '219.15')],
      [puntual('ropa', 'Ropa', '219.15', '219.15')],
    );
    expect(out).toHaveLength(1);
    expect(out[0]?.category_id).toBe('sup');
    expect(out[0]?.deferred_total).toBe('87.73');
  });

  it('resta lo aplazado puntual de lo aplazado total', () => {
    // Una categoría mixta: 100 € de los que 60 aplazados; de ellos 25 son
    // puntuales y 35 fijos.
    const out = deriveStructural(
      [fila('mix', 'Mixta', '100.00', '60.00')],
      [puntual('mix', 'Mixta', '40.00', '25.00')],
    );
    expect(out[0]?.total).toBe('60.00');
    expect(out[0]?.deferred_total).toBe('35.00');
  });

  it('propaga la AUSENCIA del dato, no un cero', () => {
    // Un backend anterior a `deferred_total`. Convertirlo en '0.00' aquí haría
    // que el aviso afirmara «no hay nada aplazado» en vez de callar.
    const out = deriveStructural([fila('a', 'Super', '100.00')], [puntual('a', 'Super', '30.00')]);
    expect(out[0]?.deferred_total).toBeUndefined();
  });

  it('nunca devuelve un aplazado negativo', () => {
    // Guarda de aritmética: si el reparto llegara descuadrado, un negativo se
    // restaría del aviso y lo dejaría por debajo de lo que hay en pantalla.
    const out = deriveStructural(
      [fila('a', 'Super', '100.00', '10.00')],
      [puntual('a', 'Super', '30.00', '25.00')],
    );
    expect(Number(out[0]?.deferred_total)).toBe(0);
  });
});

describe('toBreakdownRow', () => {
  it('conserva lo aplazado de la fila puntual', () => {
    // Sin esto, la vista de Variable pierde el dato y su aviso desaparece.
    expect(toBreakdownRow(puntual('a', 'Ropa', '219.15', '219.15')).deferred_total).toBe('219.15');
  });

  it('nombra el bucket sin categoría', () => {
    expect(toBreakdownRow(puntual(null, null, '10.00')).category_name).toBe('Sin categoría');
  });
});
