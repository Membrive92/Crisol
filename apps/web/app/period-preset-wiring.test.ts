import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

/*
 * Gate de cableado del período del usuario.
 *
 * Nació para cazar una pantalla que degradaba el preset a mes natural antes de
 * dárselo al selector. Ese literal ya no existe —`cycle` salió de `PeriodKey`—
 * así que aquel caso habría quedado verde para siempre **sin comprobar nada**.
 * El riesgo se ha mudado, no desaparecido, y cada caso de aquí cubre una forma
 * concreta en que el mes del usuario deja de llegar a una pantalla **sin que
 * nada falle**: mismo tipo, rango distinto, ningún error.
 *
 * Los cinco defectos que cubre OCURRIERON. Ninguno lo vio el compilador, la
 * suite ni una revisión por lectura: dos los cazó este gate y los otros tres
 * una revisión adversarial.
 */

/*
 * Las DOS apps. El gate vive en el paquete web por dónde corre, pero lee
 * ficheros: limitarlo a `apps/web` dejaba la mitad de las pantallas sin vigilar
 * y así se coló la semilla de «Personalizado» en las dos pantallas de móvil —
 * el mismo defecto que este gate acababa de cazar en web.
 */
const APP_DIRS = [join(__dirname), join(__dirname, '..', '..', 'mobile', 'app')];

function tsxFilesUnder(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === '.next') continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...tsxFilesUnder(full));
    else if (entry.endsWith('.tsx') && !entry.endsWith('.test.tsx')) out.push(full);
  }
  return out;
}

/** Pantallas que dejan al usuario navegar por períodos. */
function pantallasConSelectorDePeriodo(paginas: string[]): string[] {
  return paginas.filter((f) => {
    const src = readFileSync(f, 'utf8');
    return (
      src.includes('<PeriodNavigator') ||
      src.includes('<StitchPeriodToggle') ||
      src.includes('<PeriodToggle')
    );
  });
}

/**
 * ¿Hay una llamada de reanclaje DENTRO de un `useEffect`?
 *
 * Se recorre línea a línea, no con una regex sobre el fichero entero, porque
 * lo que importa es DÓNDE está la llamada y no si está. En un manejador la
 * pisa el `onAnchorChange` que el navegador dispara justo después —dos
 * `setState` planas en el mismo evento, gana la segunda— y en un efecto no.
 *
 * La versión anterior de este helper se conformaba con que el fichero
 * MENCIONARA la función, y así dio por buenas las dos pantallas de Deuda,
 * donde el reanclaje estaba presente, citado y muerto.
 */
function reanclaEnUnEfecto(src: string): boolean {
  const REANCLAJE = /(userMonthAnchorContaining|cycleAnchorContaining)\s*\(/;
  let dentro = false;
  for (const linea of src.split(/\r?\n/)) {
    if (/useEffect\s*\(/.test(linea)) dentro = true;
    else if (dentro && /^\s{0,4}\}, \[/.test(linea)) dentro = false;
    if (dentro && REANCLAJE.test(linea)) return true;
  }
  return false;
}

describe('el mes del usuario se deriva de un solo sitio', () => {
  const paginas = APP_DIRS.flatMap(tsxFilesUnder);
  const conSelector = pantallasConSelectorDePeriodo(paginas);

  it('encuentra pantallas que analizar (si no, el gate pasaría por vacuidad)', () => {
    // Sin esto, mover las páginas de sitio dejaría el gate recorriendo cero
    // ficheros y en verde — que es exactamente cómo murió su versión anterior.
    expect(paginas.length).toBeGreaterThan(5);
    expect(conSelector.length).toBeGreaterThan(0);
  });

  it('ninguna calcula los bounds de su período a mano', () => {
    const culpables: string[] = [];
    for (const fichero of conSelector) {
      const src = readFileSync(fichero, 'utf8');
      // `boundsForAnchor` es la aritmética de CALENDARIO. Una pantalla que la
      // llame directamente se salta la pregunta «¿este usuario tiene su propio
      // día de corte?» y le enseña el mes natural sin decírselo.
      for (const [i, linea] of src.split(/\r?\n/).entries()) {
        if (/\bboundsForAnchor\s*\(/.test(linea)) {
          culpables.push(`${fichero}:${i + 1}`);
        }
      }
    }
    expect(
      culpables,
      `Una pantalla con selector de período calcula sus bounds con la aritmética ` +
        `de calendario, así que para quien declaró que su mes empieza el día 12 ` +
        `enseña el mes NATURAL sin avisar. Usa \`boundsForUserPeriod\`. ` +
        culpables.join(' · '),
    ).toEqual([]);
  });

  it('las que siembran el ancla con el calendario reanclan al período en curso', () => {
    /*
     * El ancla se siembra en `useState` —síncrono— mientras el día llega de
     * `useMe()`, que no lo es. Para quien corta el día 12, del 1 al 11 el mes
     * de calendario apunta al período que ABRIRÁ el 12: todos los KPIs a cero
     * bajo un titular que dice ser el actual, un tercio de los días del mes.
     */
    const sinReanclaje = conSelector.filter((f) => {
      const src = readFileSync(f, 'utf8');
      // Sólo aplica a las que MANTIENEN el ancla en estado propio; las que la
      // derivan en cada render ya están bien por construcción.
      const anclaEnEstado = /useState[^;]*anchor/i.test(src) || /setAnchorMonth/.test(src);
      if (!anclaEnEstado) return false;
      if (!/cycleStartDay/.test(src)) return false;
      return !reanclaEnUnEfecto(src);
    });
    expect(
      sinReanclaje,
      `Estas pantallas guardan el ancla en estado y conocen el día de corte del ` +
        `usuario, pero no reanclan al período EN CURSO desde un efecto. En un ` +
        `manejador no vale: el navegador lo pisa en el mismo evento. ` +
        sinReanclaje.join(' · '),
    ).toEqual([]);
  });

  it('la que AFIRMA recibir bounds en ciclos los pide en ciclos', () => {
    /*
     * `boundsAlreadyInCycles` es una afirmación del consumidor: «los límites
     * que le paso al navegador ya vienen bucketizados». El Dashboard la hacía
     * sin mandar nunca `cycle` en su query, así que recibía meses naturales y
     * acotaba las flechas con la unidad equivocada. Las dos mitades compilan,
     * tipan y no lanzan; sólo son incoherentes entre sí.
     */
    const mienten = conSelector.filter((f) => {
      const src = readFileSync(f, 'utf8');
      // Sólo cuenta si AFIRMA que sí: la prop sin valor (JSX la hace `true`) o
      // `={true}`. Pasarla a `false` es la declaración contraria y es correcta
      // — la pantalla de Deuda lo hace, porque su endpoint no tiene parámetro
      // de ciclo. La primera versión de este caso no distinguía las dos y la
      // señalaba; un gate ruidoso se acaba ignorando.
      const afirmaQueSi = /boundsAlreadyInCycles(?!\s*=)|boundsAlreadyInCycles=\{true\}/.test(src);
      if (!afirmaQueSi) return false;
      return !/cycle:\s*true/.test(src);
    });
    expect(
      mienten,
      `Estas pantallas le dicen al navegador que sus límites vienen en ciclos ` +
        `pero nunca los piden así. ` +
        mienten.join(' · '),
    ).toEqual([]);
  });

  it('la semilla del rango libre sale del período que se estaba viendo', () => {
    /*
     * Al pulsar «Personalizado», los date-pickers se siembran con el período
     * que el usuario tenía delante. Construirlo a mano —`${anchor}-01` y
     * `Date.UTC` para el último día— siembra el mes de CALENDARIO, así que a
     * quien corta el día 14 le desplaza el rango 13 días sin haber tocado
     * nada. Ocurrió en cinco pantallas; el arreglo llegó a dos y este gate no
     * podía ver las otras tres porque sólo miraba `apps/web` y sólo buscaba
     * `boundsForAnchor(`.
     */
    const aMano = conSelector.filter((f) => {
      const src = readFileSync(f, 'utf8');
      const lineas = src.split(/\r?\n/);
      const inicio = lineas.findIndex((l) => /function seedCustom\w*\(/.test(l));
      if (inicio === -1) return false;
      // El cuerpo, hasta el cierre de la función al nivel del componente.
      const fin = lineas.findIndex((l, i) => i > inicio && /^ {2}\}/.test(l));
      const bloque = lineas.slice(inicio, fin === -1 ? undefined : fin).join('\n');
      return !bloque.includes('boundsForUserPeriod');
    });
    expect(
      aMano,
      `Estas pantallas siembran el rango libre construyendo fechas a mano, así ` +
        `que a quien tiene día de corte le desplazan el rango al pulsar ` +
        `«Personalizado». Usa \`boundsForUserPeriod\`. ` +
        aMano.join(' · '),
    ).toEqual([]);
  });

  it('las que navegan por período sí lo derivan del helper compartido', () => {
    const sinHelper = conSelector.filter((f) => {
      const src = readFileSync(f, 'utf8');
      const calculaBounds = /\bdateFrom\b/.test(src) && /useMemo/.test(src);
      return calculaBounds && !src.includes('boundsForUserPeriod');
    });
    expect(
      sinHelper,
      `Estas pantallas calculan un rango de fechas sin pasar por ` +
        `\`boundsForUserPeriod\`, así que el mes del usuario no llega hasta ellas. ` +
        sinHelper.join(' · '),
    ).toEqual([]);
  });
});
