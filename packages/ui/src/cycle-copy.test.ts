import { describe, expect, it } from 'vitest';

import { dayRangeLabel, shortMonthEs } from './civil-dates';
import {
  CYCLE_PRESET_LABEL,
  NATURAL_MONTH_NOTICE,
  cycleLabel,
  cycleRangeLabel,
} from './cycle-copy';
import { formatMonthLabel } from './format';

describe('CYCLE_PRESET_LABEL', () => {
  it('es el mismo chip en las dos apps', () => {
    expect(CYCLE_PRESET_LABEL).toBe('Mi ciclo');
  });
});

describe('cycleLabel', () => {
  it('nombra el ciclo por su día de cobro (dos cifras)', () => {
    // El caso motivador: el usuario cobra el 14. Ver "Ciclo del 14 ago" es lo
    // que le dice de un vistazo que está mirando SU mes y no el del calendario.
    expect(cycleLabel(14, '2026-08')).toBe('Ciclo del 14 ago 2026');
  });

  it('no pinta el día con cero delante (una cifra)', () => {
    expect(cycleLabel(1, '2026-09')).toBe('Ciclo del 1 sep 2026');
    expect(cycleLabel(5, '2026-01')).toBe('Ciclo del 5 ene 2026');
  });

  it('usa el mes del ANCLA, que es el que abre el ciclo', () => {
    // Un ciclo con ancla 2026-12 abre en diciembre aunque acabe en enero.
    expect(cycleLabel(14, '2026-12')).toBe('Ciclo del 14 dic 2026');
  });

  it('con un ancla ilegible dice menos en vez de inventarse una fecha', () => {
    // Nunca "Ciclo del 14 NaN NaN": un hueco se pregunta, una frase se cree
    // (PHASE-44.16).
    expect(cycleLabel(14, 'no-es-un-mes')).toBe(CYCLE_PRESET_LABEL);
    expect(cycleLabel(14, '2026-13')).toBe(CYCLE_PRESET_LABEL);
    expect(cycleLabel(14, '2026-00')).toBe(CYCLE_PRESET_LABEL);
    expect(cycleLabel(14, '2026-8')).toBe(CYCLE_PRESET_LABEL);
  });

  it('con un día ilegible dice menos en vez de inventarse una fecha', () => {
    expect(cycleLabel(Number.NaN, '2026-08')).toBe(CYCLE_PRESET_LABEL);
    expect(cycleLabel(14.5, '2026-08')).toBe(CYCLE_PRESET_LABEL);
    expect(cycleLabel(0, '2026-08')).toBe(CYCLE_PRESET_LABEL);
  });
});

describe('cycleRangeLabel', () => {
  it('dice el año UNA vez cuando el ciclo no cruza de año', () => {
    expect(cycleRangeLabel('2026-08-14', '2026-09-13')).toBe('14 ago – 13 sep 2026');
  });

  it('dice los DOS años cuando el ciclo cruza diciembre', () => {
    // Aquí el año no es decoración: sin él, "14 dic – 13 ene" no dice de qué
    // ciclo se está hablando.
    expect(cycleRangeLabel('2026-12-14', '2027-01-13')).toBe('14 dic 2026 – 13 ene 2027');
  });

  it('no pinta ceros delante en los días', () => {
    // D=1 degenera en el mes natural: el rango tiene que leerse como tal.
    expect(cycleRangeLabel('2026-09-01', '2026-09-30')).toBe('1 sep – 30 sep 2026');
    expect(cycleRangeLabel('2027-01-28', '2027-02-27')).toBe('28 ene – 27 feb 2027');
  });

  it('separa con guion de rango tipográfico, no con el menos del teclado', () => {
    const label = cycleRangeLabel('2026-08-14', '2026-09-13');
    expect(label).toContain('–');
    expect(label).not.toContain('-');
  });

  it('con un día ilegible devuelve las fechas en crudo', () => {
    // Son fechas: enseñarlas tal cual no inventa nada.
    expect(cycleRangeLabel('ayer', '2026-09-13')).toBe('ayer – 2026-09-13');
    expect(cycleRangeLabel('2026-08-14', '2026-09-32')).toBe('2026-08-14 – 2026-09-32');
  });
});

describe('los meses cortos son nuestros, no los de Intl', () => {
  // Esta decisión sin test se revierte sola (PHASE-44.21): alguien verá una
  // tabla de meses escrita a mano y pensará que `Intl` la ahorra. No la ahorra:
  // `Intl.DateTimeFormat('es-ES', { month: 'short' })` devuelve "sept" en el
  // Node de este repo, y en Hermes puede devolver la forma con punto o inglés.
  // Web y móvil tienen que pintar la MISMA cadena.
  it('septiembre es "sep", no "sept"', () => {
    expect(cycleLabel(14, '2026-09')).toBe('Ciclo del 14 sep 2026');
  });

  it('los doce meses son tres letras minúsculas y sin punto', () => {
    for (let month = 1; month <= 12; month += 1) {
      const anchor = `2026-${String(month).padStart(2, '0')}`;
      const label = cycleLabel(1, anchor);
      const name = label.replace('Ciclo del 1 ', '').replace(' 2026', '');
      expect(name).toMatch(/^[a-záéíóú]{3}$/);
    }
  });
});

describe('NATURAL_MONTH_NOTICE', () => {
  it('no está vacío', () => {
    expect(NATURAL_MONTH_NOTICE.trim().length).toBeGreaterThan(0);
  });

  it('nombra las DOS cosas que el lector necesita distinguir', () => {
    // Qué corte usa esa tarjeta (el mes del calendario) y cuál NO (el suyo).
    // Si el texto deja de decir una de las dos, el aviso no avisa de nada.
    expect(NATURAL_MONTH_NOTICE).toContain('día 1');
    expect(NATURAL_MONTH_NOTICE).toContain('día de cobro');
  });
});

/*
 * Regresión de la revisión adversarial de C0: el subtítulo del ciclo y el
 * caption del rango libre de los charts responden LA MISMA pregunta y llegaron
 * a estar escritos por separado, produciendo la misma cadena, en la misma
 * pantalla de Análisis. Este test los ata: si alguien cambia una redacción y no
 * la otra, cae aquí en vez de descubrirse mirando las dos líneas juntas.
 */
describe('el rango del ciclo y el del rango libre son la misma función', () => {
  it('las dos producen la MISMA cadena, afirmada literalmente', () => {
    // Ojo con el test que parecería obvio aquí:
    // `expect(cycleRangeLabel(a,b)).toBe(dayRangeLabel(a,b))` no puede fallar
    // nunca, porque la primera DELEGA en la segunda — pasaría igual de verde si
    // el formato entero estuviera mal. Así que lo que se fija es la cadena, por
    // las dos vías: si alguien toca el guion, el orden o el año, caen las dos.
    expect(dayRangeLabel('2026-08-14', '2026-09-13')).toBe('14 ago – 13 sep 2026');
    expect(cycleRangeLabel('2026-08-14', '2026-09-13')).toBe('14 ago – 13 sep 2026');
    expect(dayRangeLabel('2026-12-14', '2027-01-13')).toBe('14 dic 2026 – 13 ene 2027');
    expect(cycleRangeLabel('2026-12-14', '2027-01-13')).toBe('14 dic 2026 – 13 ene 2027');
  });

  it('el nombre del mes es el mismo que pinta formatMonthLabel', () => {
    // Septiembre era el único mes que discrepaba —`Intl` daba «Sept» y la
    // tabla del ciclo «sep»— y discrepaba porque nadie había comparado las dos
    // grafías, que conviven en la pantalla de móvil.
    expect(formatMonthLabel('2026-09')).toBe('Sep 2026');
    expect(cycleLabel(14, '2026-09')).toBe('Ciclo del 14 sep 2026');
    for (let month = 1; month <= 12; month += 1) {
      const mm = String(month).padStart(2, '0');
      const fromCatalog = shortMonthEs(month);
      expect(formatMonthLabel(`2026-${mm}`).toLowerCase()).toBe(`${fromCatalog} 2026`);
    }
  });
});
