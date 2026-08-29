import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

import { describe, expect, it } from 'vitest';

/*
 * PHASE-47.H — gate de cableado del signo de una devolución.
 *
 * El backend RESTA las devoluciones de su categoría desde PHASE-47.H, pero el
 * importe de cada movimiento viaja SIN signo (es el que ordena el ranking).
 * Mientras la lista lo pintaba tal cual, «Suscripciones» de julio enseñaba seis
 * importes que sumaban 187,95 € bajo un total de 184,95 € — dos números
 * plausibles que sólo se contradicen si los miras juntos, y ninguna herramienta
 * mira.
 *
 * El riesgo que vigila esto NO es de tipos: `formatAmount(tx.amount, …)`
 * compila perfectamente y seguirá compilando.
 *
 * **Segunda versión, y por qué.** La primera comprobaba la PRESENCIA de
 * `categoryRowAmount(` en el fichero. Una revisión adversarial ejecutó cuatro
 * formas normales de reintroducir el defecto y el gate dio VERDE en las cuatro:
 * una lista nueva cuyo tipo se infiere del hook (no contiene el literal
 * `TopExpenseItem[]`), una segunda tabla en la misma página (el fichero
 * conserva la llamada de la primera), la tabla extraída a un componente que
 * pierde el kind por el camino, y un callback con la variable llamada `row` en
 * vez de `tx`. Ahora la comprobación es por SITIO DE LLAMADA y la selección de
 * ficheros es mucho más ancha. Ver `lessons.md`: «un guardarraíl que comprueba
 * la PRESENCIA de algo no comprueba su EFECTO».
 *
 * Lee las DOS apps por la misma razón que el gate del período: la mitad de las
 * pantallas vive en móvil.
 */

const RAIZ = join(__dirname, '..', '..', '..');
const DIRS = [
  join(__dirname), // apps/web/app
  join(__dirname, '..', 'components'), // apps/web/components
  join(__dirname, '..', '..', 'mobile', 'app'),
  join(__dirname, '..', '..', 'mobile', 'components'),
];

/**
 * Las señales por las que un fichero entra a vigilancia. Son ANCHAS a
 * propósito: cualquiera de ellas indica que el fichero maneja items de un
 * ranking del cubo de gasto, y basta con una.
 *
 * `useDashboardTopExpenses` está aquí porque el hook ya existe y hoy sólo lo
 * consume móvil: el día que web pinte su «Top gastos», el tipo se infiere del
 * hook y ningún literal de tipo aparece en el fichero.
 */
const SEÑALES = [
  'top_transactions',
  'TopExpenseItem',
  'AnalyticsTxRef',
  'top_exceptional',
  'useDashboardTopExpenses',
];

/**
 * Ficheros que conocen el KIND de la categoría de sus filas y por tanto NO
 * pueden pasar un literal: el drill-down de una categoría de INGRESO pintaría
 * la nómina como «−2.520,68 €» con badge «Devolución».
 *
 * Lo contrario —pasar `'expense'` fijo— sólo es legítimo en una lista que YA
 * viene acotada al cubo de gasto por el propio endpoint. Ésas se enumeran aquí
 * CON su motivo, como las exclusiones de `knip.config.ts`: una excepción sin
 * motivo la borra alguien dentro de seis meses.
 */
const ACOTADAS_AL_CUBO_DE_GASTO: Record<string, string> = {
  'apps/mobile/components/dashboard/top-expenses-list.tsx':
    '/dashboard/top-expenses filtra por _is_expense(): todas sus filas son gasto',
  'apps/web/components/analysis/top-movements-card.tsx':
    'top_exceptional filtra por _is_expense(): todas sus filas son gasto',
};

function ficherosBajo(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === '.next') continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...ficherosBajo(full));
    else if (/\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

function ruta(f: string): string {
  return relative(RAIZ, f).split(sep).join('/');
}

/** Ficheros que manejan items de un ranking del cubo de gasto. */
function ficherosVigilados(): string[] {
  return DIRS.flatMap(ficherosBajo).filter((f) => {
    const src = readFileSync(f, 'utf8');
    return SEÑALES.some((s) => src.includes(s));
  });
}

/**
 * Todo `formatAmount(<x>)` cuyo argumento sea un importe de fila SIN firmar.
 *
 * Cubre las dos formas: directa (`formatAmount(row.amount)`, con CUALQUIER
 * nombre de variable — la versión anterior enumeraba `tx|item|movimiento` y
 * `row` se le escapaba) e indirecta (`const importe = tx.amount` y luego
 * `formatAmount(importe)`, que es justo el idioma que tenía la tarjeta de
 * «Top movimientos»).
 */
function importesCrudosQueSePintan(src: string): string[] {
  const crudos: string[] = [];

  const directo = /formatAmount\(\s*([A-Za-z_$][\w$]*)\.(amount|converted_amount)\b/g;
  for (const m of src.matchAll(directo)) crudos.push(`${m[1]}.${m[2]}`);

  // Variables que reciben un importe de fila sin pasar por el helper.
  const sinFirmar = new Set<string>();
  const asignacion =
    /(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*([^;\n]*\.(?:amount|converted_amount)\b[^;\n]*)/g;
  for (const m of src.matchAll(asignacion)) {
    const [, nombre, rhs] = m;
    if (nombre && rhs && !rhs.includes('categoryRowAmount(')) sinFirmar.add(nombre);
  }
  for (const nombre of sinFirmar) {
    if (new RegExp(`formatAmount\\(\\s*${nombre}\\b`).test(src)) crudos.push(nombre);
  }

  return crudos;
}

describe('el signo de una devolución llega a todas las listas del ranking', () => {
  it('hay ficheros que vigilar, y están los que sabemos', () => {
    // Un gate que se queda sin entrada pasa por vacuidad, que es la forma más
    // cara de no tener gate. Además de contar, se exigen por nombre las
    // pantallas conocidas: así, mover una lista a otro sitio obliga a pasar
    // por aquí en vez de perder cobertura en silencio.
    const rutas = ficherosVigilados().map(ruta);
    expect(rutas.length).toBeGreaterThanOrEqual(5);
    for (const conocida of [
      'apps/web/app/(app)/personal-finance/analysis/category/[id]/page.tsx',
      'apps/mobile/app/(modules)/personal-finance/analysis/category/[id].tsx',
      'apps/mobile/components/dashboard/top-expenses-list.tsx',
      'apps/web/components/analysis/top-movements-card.tsx',
    ]) {
      expect(rutas, `${conocida} salió de la vigilancia`).toContain(conocida);
    }
  });

  it('ningún sitio de llamada pinta el importe de una fila sin firmar', () => {
    const culpables = ficherosVigilados()
      .map((f) => ({ f: ruta(f), crudos: importesCrudosQueSePintan(readFileSync(f, 'utf8')) }))
      .filter((x) => x.crudos.length > 0);
    expect(culpables).toEqual([]);
  });

  it('sólo pasa un kind literal quien tiene derecho, y con su motivo escrito', () => {
    for (const f of ficherosVigilados()) {
      const src = readFileSync(f, 'utf8');
      const literal = /categoryRowAmount\([^)]*,\s*'(expense|income)'\s*\)/.test(src);
      if (!literal) continue;
      expect(
        ACOTADAS_AL_CUBO_DE_GASTO[ruta(f)],
        `${ruta(f)} fija el kind a mano sin estar declarado como lista acotada al cubo de gasto`,
      ).toBeTruthy();
    }
  });

  it('quien conoce el kind de su categoría se lo pasa', () => {
    // La comprobación NO se condiciona a que el `.map` viva en el mismo
    // fichero: extraer la tabla a un componente con props `{ items }` pierde el
    // kind por el camino y la versión anterior del gate se saltaba la rama.
    for (const f of ficherosVigilados()) {
      const src = readFileSync(f, 'utf8');
      if (!src.includes('categoryRowAmount(')) continue;
      if (ACOTADAS_AL_CUBO_DE_GASTO[ruta(f)]) continue;
      expect(src, `${ruta(f)} firma sin decir de qué categoría`).toMatch(
        /categoryRowAmount\([^)]*category_kind/s,
      );
    }
  });
});
