import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

import { describe, expect, it } from 'vitest';

import { layout } from '@crisol/ui';

/*
 * Gate del ancho de página (PHASE-38 · PHASE-44.24).
 *
 * El defecto que cubre OCURRIÓ, y en dos formas distintas: dos listas fijaban
 * `maxWidth: 1200` a mano —se quedaron fuera de la estandarización de
 * PHASE-38.3— y cinco pantallas usaban `pageNarrow` como contenedor de PÁGINA,
 * así que en un monitor grande eran una columna de 720 px flotando en el centro
 * mientras el resto de la app ocupaba el ancho completo. El cuadro de
 * amortización llegaba a estrangular una tabla de siete columnas.
 *
 * Ninguna de las dos formas la ve el compilador (`1200` y `layout.pageNarrow`
 * son `maxWidth` perfectamente válidos) ni el linter ni un test de render: el
 * resultado es una pantalla que funciona y se ve mal, y sólo se nota
 * comparándola con otra.
 *
 * La regla: la PÁGINA usa el ancho global; lo que no deba ensancharse se acota
 * DENTRO con `pageNarrow` (formularios) o `prose` (texto).
 */

const APP_DIR = __dirname;

/**
 * Fuera del shell de la app: `(auth)` y `onboarding` son pantallas de
 * bienvenida sin sidebar ni header, con su propia tarjeta centrada. Ahí un
 * ancho de página no significa lo mismo, así que no se les aplica la regla.
 */
const FUERA_DEL_SHELL = ['(auth)', 'onboarding'];

function paginasDeApp(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === '.next') continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...paginasDeApp(full));
    else if (entry === 'page.tsx') out.push(full);
  }
  return out;
}

function dentroDelShell(file: string): boolean {
  const partes = relative(APP_DIR, file).split(sep);
  return !partes.some((p) => FUERA_DEL_SHELL.includes(p));
}

/**
 * El ancho que declara el contenedor de página, o `null` si no declara ninguno.
 *
 * Es el PRIMER `maxWidth` del fichero porque el contenedor de página abre el
 * `return` del componente; lo que venga después ya es contenido acotándose a sí
 * mismo, que es exactamente lo que la regla permite. Un `null` es una página
 * sin contenedor: los tres redirects (`/`, `/home`, `/investments`) no pintan
 * nada.
 */
function anchoDePagina(file: string): string | null {
  const m = /maxWidth:\s*([^,\n]+)/.exec(readFileSync(file, 'utf8'));
  return m ? (m[1] as string).trim() : null;
}

describe('ancho de página', () => {
  const paginas = paginasDeApp(APP_DIR).filter(dentroDelShell);

  it('el gate mira las páginas de verdad', () => {
    // Un gate que se queda sin entrada pasa por vacuidad, que es la forma más
    // cara de no tener gate.
    expect(paginas.length).toBeGreaterThan(20);
    expect(paginas.filter((f) => anchoDePagina(f) !== null).length).toBeGreaterThan(20);
  });

  it('toda página usa el ancho GLOBAL, ninguna el suyo', () => {
    const desviadas = paginas
      .map((f) => ({ file: relative(APP_DIR, f), ancho: anchoDePagina(f) }))
      .filter(({ ancho }) => ancho !== null && ancho !== 'layout.pageWide');

    expect(
      desviadas,
      'El contenedor de página va a `layout.pageWide`. Si el contenido no debe ' +
        'ensancharse, acótalo DENTRO con `layout.pageNarrow` (formularios) o ' +
        '`layout.prose` (texto) — no estrechando la página entera.',
    ).toEqual([]);
  });

  it('los dos anchos que se acotan dentro son distintos del de página', () => {
    // Si alguien igualara los tres tokens, la regla de arriba pasaría a ser
    // decorativa: todo valdría y nada se acotaría.
    expect(layout.pageNarrow).toBeLessThan(layout.pageWide);
    expect(layout.prose).toBeLessThan(layout.pageWide);
  });
});
