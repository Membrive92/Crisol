import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

/**
 * El CABLEADO de la pantalla de informe (PHASE-44.24.F/G).
 *
 * Cuatro de los defectos que encontró la revisión adversarial no viven en un
 * componente sino en la ruta que los conecta: un booleano derivado mal, un
 * `href` relativo que pierde la query, una barra de pestañas que se renderiza
 * cuando no debería, y un error que se pinta en un bloque que no está montado.
 *
 * Ninguno lo puede ver un test de componente —la página es un cliente con
 * hooks de `next/navigation`, y montarla exigiría un router falso— ni `tsc`,
 * porque todo son valores válidos de tipos válidos. Lo que sí se puede
 * comprobar es el TEXTO de la ruta, con el precedente de
 * `apps/web/app/period-preset-wiring.test.ts`.
 *
 * Un gate de texto es débil por naturaleza: comprueba que la pieza está, no que
 * funcione. Por eso cada caso de abajo busca la forma CONCRETA que tenía el
 * defecto, no una mención genérica.
 */

const PAGINA = join(__dirname, '(app)', 'investments', 'analysis', '[securityId]', 'page.tsx');
const HERO = join(__dirname, '..', 'components', 'investment', 'analysis-hero.tsx');

function leer(ruta: string): string {
  return readFileSync(ruta, 'utf-8');
}

/**
 * El fichero SIN comentarios.
 *
 * Un escáner de texto que no distingue código de prosa reporta como defecto la
 * frase que EXPLICA el arreglo — pasó con este mismo gate a la primera.
 */
function codigo(ruta: string): string {
  return leer(ruta)
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');
}

describe('cableado de la pantalla de informe', () => {
  it('los ficheros existen y tienen tamaño: el gate no pasa por vacuidad', () => {
    // Un gate que se queda sin entrada da verde. Es la forma más cara de no
    // tener gate.
    expect(leer(PAGINA).length).toBeGreaterThan(5000);
    expect(leer(HERO).length).toBeGreaterThan(2000);
  });

  it('el estado vacío NO se declara mientras el run seleccionado carga', () => {
    // El defecto: con `?run=` en la URL, `activeRun` está vacío mientras esa
    // query resuelve y `latestRun` ya resolvió, así que `noRunYet` salía true
    // y la pantalla decía «todavía no se ha ejecutado ningún análisis» — falso
    // — y desmontaba el propio selector con el que acababas de pulsar.
    const fuente = leer(PAGINA);
    const linea = fuente.split('\n').find((l) => l.includes('const noRunYet'));
    expect(linea, 'no se encuentra `noRunYet`').toBeTruthy();
    expect(linea).toContain('selectedPending');
    expect(linea).toContain('selectedMissing');
  });

  it('un run seleccionado que no existe se DICE, con salida', () => {
    const fuente = leer(PAGINA);
    expect(fuente).toContain('selectedMissing ?');
    // La salida: volver al último borrando la selección.
    expect(fuente).toMatch(/setParam\(\{\s*run:\s*null/);
  });

  it('el enlace del dictamen imprimible CONSERVA la query', () => {
    // El defecto: `href="?print=1"` es una referencia relativa que sustituye la
    // query ENTERA (RFC 3986 §5.3), así que perdía `?run=` y se imprimía el
    // análisis más reciente en vez del que estabas mirando.
    // Ningún href a una query literal: ni el de impresión ni otro que venga
    // después. La prop, además, es obligatoria, así que `tsc` caza la omisión.
    expect(codigo(HERO), 'el hero no debe escribir un href de query a mano').not.toMatch(
      /href="\?/,
    );
    expect(codigo(HERO)).toContain('href={printHref');

    // La composición vive en `printHrefFor`, pura y con tests de EFECTO que sí
    // comprueban que conserva `?run=` (lib/report-links.test.ts). Aquí sólo se
    // ata que la página la USE: un gate de texto no puede comprobar el efecto,
    // y la versión anterior de este caso daba verde con un `delete('run')`
    // metido en medio.
    const pagina = codigo(PAGINA);
    expect(pagina).toContain('printHrefFor(pathname, searchParams.toString())');
    expect(pagina, 'la página no debe recomponer la query a mano').not.toMatch(
      /printHref = useMemo\(\(\) => \{/,
    );
  });

  it('en modo dictamen la barra de pestañas NO se renderiza', () => {
    // El defecto: estaba envuelta en `data-print="hide"`, que sólo la esconde
    // dentro de `@media print`. En pantalla seguía viva y pulsarla escribía un
    // `tab` en la URL que `printMode` descarta.
    const fuente = leer(PAGINA);
    expect(fuente).toMatch(/printMode \? null : \(\s*<Tabs/);
  });

  it('el error de un re-análisis llega al hero, no sólo al estado vacío', () => {
    // El defecto: `run.isError` se pintaba dentro del bloque
    // `hasStatements && noRunYet`, que por definición no está en pantalla
    // cuando ya hay informe — que es justo cuando se pulsa «Volver a analizar».
    // Que se PINTE lo ata `analysis-hero.test.tsx`, que renderiza el hero y
    // busca el texto. Un gate de presencia daba verde con el render vaciado,
    // porque `rerunError` aparece igualmente en la declaración de la prop y en
    // su JSDoc. Aquí sólo se comprueba el CABLEADO: que la página lo pase.
    expect(codigo(PAGINA)).toContain('rerunError:');
  });

  it('el re-análisis captura su propio rechazo', () => {
    // `void rerun()` con un `await mutateAsync` dentro deja el rechazo suelto y
    // acaba en `unhandledrejection`.
    const fuente = leer(PAGINA);
    const inicio = fuente.indexOf('const rerun = useCallback');
    expect(inicio).toBeGreaterThan(-1);
    expect(fuente.slice(inicio, inicio + 600)).toMatch(/try\s*\{/);
  });

  it('el motivo de que no haya comparación viaja como TEXTO, no como booleano', () => {
    // El servidor distingue cuatro causas de 404 con su motivo escrito;
    // colapsarlas en un booleano le daba al usuario una explicación que en tres
    // de los cuatro casos es falsa.
    const fuente = leer(PAGINA);
    expect(fuente).not.toContain('notEnoughRuns');
    expect(fuente).toContain('formatApiError(');
  });
});
