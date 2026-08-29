import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import {
  MARK,
  MATRIX_LEGEND,
  REPORT_LEGEND,
  TEXT_LEGEND,
  provenanceMarkOf,
} from './investment-marks';

/**
 * El registro único de marcas (PHASE-44.24.E).
 *
 * Un test «la leyenda contiene todas las marcas» se cumple **por
 * construcción** (`MATRIX_LEGEND = Object.values(MARK)`) y no prueba nada: es
 * la forma tautológica que ya ha dado verde tres veces en este proyecto. Lo que
 * hay que impedir es que alguien vuelva a escribir un glifo A MANO en el fichero
 * que emite las celdas, que es como se llegó a tener el mismo `·` con dos
 * títulos distintos.
 */

const EMISORES = [
  new URL('./investment-metric-rows.ts', import.meta.url),
  new URL('./investment-statement-rows.ts', import.meta.url),
  // Las dos cabeceras de matriz, que pintan el `•` del ejercicio del dictamen.
  // Están en otro paquete a propósito: el mismo defecto puede vivir en un
  // fichero que el filtro no mira, y ahí no hay rotura que valga.
  new URL('../../../apps/web/components/investment/year-matrix.tsx', import.meta.url),
  new URL('../../../apps/mobile/components/investment/year-matrix.tsx', import.meta.url),
];

const GLIFOS = new Set<string>(Object.values(MARK).map((entry) => entry.glyph));

describe('registro de marcas', () => {
  it('ningún emisor de celdas escribe un glifo a mano', () => {
    // CUALQUIER literal de un solo glifo, venga como venga. Anclarlo a
    // `push|return|mark:` deja fuera las formas normales de reintroducirlo —un
    // ternario, una interpolación, una constante local— y una sonda lo
    // demostró: `provenance === 'derived' ? '†' : …` pasaba el filtro entero.
    const patron = /'([^\w\s'])'/g;
    const culpables: string[] = [];
    for (const url of EMISORES) {
      const fuente = readFileSync(url, 'utf-8');
      for (const match of fuente.matchAll(patron)) {
        const glifo = match[1] as string;
        if (!GLIFOS.has(glifo)) continue; // otro carácter: no es una marca
        culpables.push(`${url.pathname.split('/').pop()}: ${match[0]}`);
      }
    }
    expect(culpables, 'un glifo escrito a mano fuera de MARK').toEqual([]);
  });

  it('el escáner mira ficheros de verdad y no una lista vacía', () => {
    // Un gate que se queda sin entrada pasa por vacuidad, que es la forma más
    // cara de no tener gate.
    expect(EMISORES).toHaveLength(4);
    for (const url of EMISORES) expect(readFileSync(url, 'utf-8').length).toBeGreaterThan(1000);
  });

  it('el escáner CAZA un glifo suelto cuando lo hay', () => {
    // La sonda del propio detector: si no distingue, el test de arriba sólo
    // demuestra que hoy no hay ninguno, no que se detectaría.
    const patron = /(?:push|return|mark:)\s*\(?\s*'([^\w\s'])'/g;
    const falso = "  marks.push('†');\n  return '≈';\n";
    const hallados = [...falso.matchAll(patron)].map((m) => m[1]);
    expect(hallados).toEqual(['†', '≈']);
  });

  it('los estados de texto NO están entre las marcas', () => {
    // Un `—` es lo que se pinta EN LUGAR del número; un `†` acompaña a uno que
    // existe. Colapsarlos haría creer que un hueco es una anotación.
    for (const texto of TEXT_LEGEND) expect(GLIFOS.has(texto.glyph)).toBe(false);
  });

  it('la leyenda del informe lleva los dos grupos, en orden', () => {
    expect(REPORT_LEGEND).toHaveLength(TEXT_LEGEND.length + MATRIX_LEGEND.length);
    expect(REPORT_LEGEND[0]).toBe(TEXT_LEGEND[0]);
    expect(REPORT_LEGEND[REPORT_LEGEND.length - 1]).toBe(MATRIX_LEGEND[MATRIX_LEGEND.length - 1]);
  });

  it('ninguna entrada repite glifo ni deja el título vacío', () => {
    const glifos = REPORT_LEGEND.map((e) => e.glyph);
    expect(new Set(glifos).size).toBe(glifos.length);
    for (const entrada of REPORT_LEGEND) expect(entrada.title.length).toBeGreaterThan(20);
  });

  it('una procedencia normal (`sourced`) no lleva marca', () => {
    // Marcar lo normal es ruido: la marca existe para señalar la excepción.
    expect(provenanceMarkOf('sourced')).toBeUndefined();
    expect(provenanceMarkOf(null)).toBeUndefined();
    expect(provenanceMarkOf('derived')).toBe(MARK.derived);
  });
});
