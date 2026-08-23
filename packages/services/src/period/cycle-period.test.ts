import { describe, expect, it } from 'vitest';

import { boundsForAnchor } from './calendar-period';
import {
  MAX_CYCLE_START_DAY,
  MIN_CYCLE_START_DAY,
  canStepCycleNext,
  canStepCyclePrev,
  clampCycleAnchor,
  cycleAnchorContaining,
  cycleBoundsForAnchor,
  cycleDaysForAnchor,
  isValidCycleStartDay,
  stepCycleAnchor,
} from './cycle-period';

/**
 * ¿Cae el instante ISO `iso` dentro de los bounds? Réplica EXACTA del criterio
 * del backend, que es cerrado en ambos extremos (`>= date_from AND
 * <= date_to`). La comparación es de cadenas a propósito: todos los ISO son
 * UTC con milisegundos, así que el orden lexicográfico es el cronológico —
 * y así el test no puede "arreglar" con `Date` un borde que el SQL no arregla.
 */
function inCycle(iso: string, bounds: { dateFrom: string; dateTo: string }): boolean {
  return iso >= bounds.dateFrom && iso <= bounds.dateTo;
}

describe('el caso motivador: la nómina se fecha el 14, no el 15', () => {
  it('la nómina del 14 entra en el ciclo del 14 (y NO en el del mes anterior)', () => {
    const nomina = '2026-08-14T10:00:00.000Z';

    expect(inCycle(nomina, cycleBoundsForAnchor(14, '2026-08'))).toBe(true);
    expect(inCycle(nomina, cycleBoundsForAnchor(14, '2026-07'))).toBe(false);
    expect(cycleAnchorContaining('2026-08-14', 14)).toBe('2026-08');
  });

  it('documenta por qué existe la feature: un corte 15→15 la dejaría fuera', () => {
    // Con D=15 la misma nómina cae en el ciclo ANTERIOR (el que abre en julio),
    // que es el "ingresos 0" que el usuario reportó al filtrar 15→15 a mano.
    const nomina = '2026-08-14T10:00:00.000Z';

    expect(inCycle(nomina, cycleBoundsForAnchor(15, '2026-08'))).toBe(false);
    expect(inCycle(nomina, cycleBoundsForAnchor(15, '2026-07'))).toBe(true);
  });
});

describe('cycleDaysForAnchor', () => {
  it('abre el día D y cierra el día D−1 del mes siguiente', () => {
    expect(cycleDaysForAnchor(14, '2026-08')).toEqual({
      fromDay: '2026-08-14',
      toDay: '2026-09-13',
    });
  });

  it('D=28 en febrero: 28-ene → 27-feb, sin clamp de fin de mes', () => {
    expect(cycleDaysForAnchor(28, '2026-01')).toEqual({
      fromDay: '2026-01-28',
      toDay: '2026-02-27',
    });
    // Y el ciclo que ABRE en febrero cierra el 27 de marzo (febrero corto no
    // desplaza nada: el día D existe en todos los meses porque D ≤ 28).
    expect(cycleDaysForAnchor(28, '2026-02')).toEqual({
      fromDay: '2026-02-28',
      toDay: '2026-03-27',
    });
  });

  it('cruza el año: el ciclo del 14 dic 2026 cierra el 13 ene 2027', () => {
    expect(cycleDaysForAnchor(14, '2026-12')).toEqual({
      fromDay: '2026-12-14',
      toDay: '2027-01-13',
    });
  });

  it('D=1 cierra el último día del PROPIO mes (no el día 0 del siguiente)', () => {
    expect(cycleDaysForAnchor(1, '2026-02')).toEqual({
      fromDay: '2026-02-01',
      toDay: '2026-02-28',
    });
    expect(cycleDaysForAnchor(1, '2024-02').toDay).toBe('2024-02-29'); // bisiesto
    expect(cycleDaysForAnchor(1, '2026-12')).toEqual({
      fromDay: '2026-12-01',
      toDay: '2026-12-31',
    });
  });
});

describe('cycleBoundsForAnchor — intervalo CERRADO en ambos extremos', () => {
  it('emite [D 00:00:00Z, D−1 del mes siguiente 23:59:59Z]', () => {
    const { dateFrom, dateTo } = cycleBoundsForAnchor(14, '2026-08');
    expect(dateFrom).toBe('2026-08-14T00:00:00.000Z');
    expect(dateTo).toBe('2026-09-13T23:59:59.000Z');
  });

  it('el día D a las 00:00:00Z cuenta SOLO en el ciclo que ABRE', () => {
    const apertura = '2026-08-14T00:00:00.000Z';
    expect(inCycle(apertura, cycleBoundsForAnchor(14, '2026-08'))).toBe(true);
    expect(inCycle(apertura, cycleBoundsForAnchor(14, '2026-07'))).toBe(false);
  });

  it('el día D−1 a las 23:59:59Z cuenta SOLO en el ciclo saliente', () => {
    const cierre = '2026-08-13T23:59:59.000Z';
    expect(inCycle(cierre, cycleBoundsForAnchor(14, '2026-07'))).toBe(true);
    expect(inCycle(cierre, cycleBoundsForAnchor(14, '2026-08'))).toBe(false);
  });

  it('dos ciclos consecutivos NO se solapan: el borde no se cuenta dos veces', () => {
    // Si `toDay` fuese el día D del mes siguiente (y no D−1), el 14-sep caería
    // en los DOS ciclos y el importe de ese día se contaría por duplicado.
    const saliente = cycleBoundsForAnchor(14, '2026-08');
    const entrante = cycleBoundsForAnchor(14, '2026-09');
    expect(saliente.dateTo < entrante.dateFrom).toBe(true);
    expect(inCycle(entrante.dateFrom, saliente)).toBe(false);
  });

  it('usa UTC (no hora local): el día D a las 00:00Z no se va al ciclo anterior', () => {
    // Heredado de `debt-period.test.ts`: con `new Date('YYYY-MM-DD')` en
    // Europe/Madrid la frontera se desplazaba 1-2 h y el día D podía caer fuera.
    expect(cycleBoundsForAnchor(14, '2026-08').dateFrom.startsWith('2026-08-14')).toBe(true);
    expect(cycleBoundsForAnchor(1, '2026-01').dateFrom.startsWith('2026-01-01')).toBe(true);
  });
});

describe('D = 1 degenera EXACTAMENTE en el mes natural', () => {
  it('es idéntico byte a byte a boundsForAnchor(month) — febrero', () => {
    const ciclo = cycleBoundsForAnchor(1, '2026-02');
    const natural = boundsForAnchor('month', '2026-02');
    expect(ciclo.dateFrom).toBe(natural.dateFrom);
    expect(ciclo.dateTo).toBe(natural.dateTo);
  });

  it('es idéntico byte a byte en meses de 30, 31 y 29 días', () => {
    for (const anchor of ['2026-04', '2026-07', '2024-02', '2026-12']) {
      const ciclo = cycleBoundsForAnchor(1, anchor);
      const natural = boundsForAnchor('month', anchor);
      expect(ciclo).toEqual(natural);
    }
  });
});

describe('cycleAnchorContaining', () => {
  it('a los DOS lados de D: el día D abre ciclo, el D−1 pertenece al anterior', () => {
    expect(cycleAnchorContaining('2026-08-14', 14)).toBe('2026-08');
    expect(cycleAnchorContaining('2026-08-13', 14)).toBe('2026-07');
  });

  it('el último día del mes siempre cae en el ciclo que abre ese mes (D ≤ 28)', () => {
    expect(cycleAnchorContaining('2026-08-31', 28)).toBe('2026-08');
    expect(cycleAnchorContaining('2026-02-28', 28)).toBe('2026-02');
    expect(cycleAnchorContaining('2026-02-27', 28)).toBe('2026-01');
  });

  it('cruza el año hacia atrás', () => {
    expect(cycleAnchorContaining('2026-01-05', 14)).toBe('2025-12');
    expect(cycleAnchorContaining('2026-01-14', 14)).toBe('2026-01');
  });

  it('con D=1 el ancla es siempre el propio mes', () => {
    expect(cycleAnchorContaining('2026-08-01', 1)).toBe('2026-08');
    expect(cycleAnchorContaining('2026-08-31', 1)).toBe('2026-08');
  });
});

describe('stepCycleAnchor', () => {
  it('±1 mes de ancla, cruzando año', () => {
    expect(stepCycleAnchor('2026-08', 1)).toBe('2026-09');
    expect(stepCycleAnchor('2026-01', -1)).toBe('2025-12');
    expect(stepCycleAnchor('2026-12', 1)).toBe('2027-01');
  });
});

describe('clampCycleAnchor', () => {
  // `availableFrom`/`availableTo` llegan del backend como MESES NATURALES con
  // datos. Con D > 1, el primer ciclo navegable es el que ABRE en el mes
  // ANTERIOR a `availableFrom`: su tramo final (días 1..D−1) pisa el primer mes
  // con datos.
  const FROM = '2026-03';
  const TO = '2026-08';

  it('sin límites devuelve el ancla tal cual', () => {
    expect(clampCycleAnchor('2026-05', null, null, 14)).toBe('2026-05');
  });

  it('DENTRO del rango no toca el ancla (el otro lado del umbral)', () => {
    expect(clampCycleAnchor('2026-05', FROM, TO, 14)).toBe('2026-05');
    // Y justo EN los dos bordes tampoco.
    expect(clampCycleAnchor('2026-02', FROM, TO, 14)).toBe('2026-02');
    expect(clampCycleAnchor('2026-08', FROM, TO, 14)).toBe('2026-08');
  });

  it('con D>1 el suelo es el mes ANTERIOR a availableFrom, no availableFrom', () => {
    expect(clampCycleAnchor('2025-11', FROM, TO, 14)).toBe('2026-02');
    // La prueba de que el −1 mes es real: 2026-02 es navegable y 2026-01 no.
    expect(clampCycleAnchor('2026-01', FROM, TO, 14)).toBe('2026-02');
  });

  it('con D=1 el suelo es availableFrom mismo (no se retrocede un mes)', () => {
    expect(clampCycleAnchor('2026-01', FROM, TO, 1)).toBe('2026-03');
    expect(clampCycleAnchor('2026-02', FROM, TO, 1)).toBe('2026-03');
  });

  it('el techo es el ciclo que abre en availableTo, con cualquier D', () => {
    expect(clampCycleAnchor('2026-12', FROM, TO, 14)).toBe('2026-08');
    expect(clampCycleAnchor('2026-12', FROM, TO, 1)).toBe('2026-08');
    expect(clampCycleAnchor('2026-12', FROM, TO, 28)).toBe('2026-08');
  });

  it('con límites cruzados manda availableFrom (mismo orden que clampAnchor)', () => {
    expect(clampCycleAnchor('2026-05', '2026-09', '2026-04', 14)).toBe('2026-08');
  });
});

describe('canStepCyclePrev / canStepCycleNext', () => {
  it('sin datos (límites null) ambas deshabilitadas', () => {
    expect(canStepCyclePrev('2026-05', null, 14)).toBe(false);
    expect(canStepCycleNext('2026-05', null, 14)).toBe(false);
  });

  it('prev habilitado mientras quede un ciclo anterior con datos', () => {
    expect(canStepCyclePrev('2026-05', '2026-03', 14)).toBe(true);
    expect(canStepCyclePrev('2026-03', '2026-03', 14)).toBe(true); // aún queda 2026-02
    expect(canStepCyclePrev('2026-02', '2026-03', 14)).toBe(false); // ya en el primero
  });

  it('con D=1 el primer ciclo es availableFrom: no hay mes extra hacia atrás', () => {
    expect(canStepCyclePrev('2026-03', '2026-03', 1)).toBe(false);
    expect(canStepCyclePrev('2026-04', '2026-03', 1)).toBe(true);
  });

  it('next habilitado mientras quede un ciclo posterior con datos', () => {
    expect(canStepCycleNext('2026-07', '2026-08', 14)).toBe(true);
    expect(canStepCycleNext('2026-08', '2026-08', 14)).toBe(false); // ya en el último
  });
});

describe('isValidCycleStartDay', () => {
  it('acepta los enteros de 1 a 28', () => {
    expect(isValidCycleStartDay(MIN_CYCLE_START_DAY)).toBe(true);
    expect(isValidCycleStartDay(MAX_CYCLE_START_DAY)).toBe(true);
    expect(isValidCycleStartDay(14)).toBe(true);
  });

  it('rechaza 0, 29 y 31 (29-31 no se ofrecen: clamp de febrero)', () => {
    expect(isValidCycleStartDay(0)).toBe(false);
    expect(isValidCycleStartDay(29)).toBe(false);
    expect(isValidCycleStartDay(31)).toBe(false);
    expect(isValidCycleStartDay(-14)).toBe(false);
  });

  it('rechaza no-enteros, cadenas y AUSENCIA (guarda por verdad, no por !== null)', () => {
    expect(isValidCycleStartDay(14.5)).toBe(false);
    expect(isValidCycleStartDay('14')).toBe(false);
    expect(isValidCycleStartDay(null)).toBe(false);
    // El caso que ocurre de verdad con un backend anterior a la columna: el
    // campo llega AUSENTE. Se escribe con la clave omitida, no con `null`
    // (lección [PHASE-47.E]: con `null` el test pasa igual y no prueba nada).
    const user: { cycle_start_day?: number | null } = {};
    expect(isValidCycleStartDay(user.cycle_start_day)).toBe(false);
    expect(isValidCycleStartDay(Number.NaN)).toBe(false);
  });
});

/*
 * Regresiones de la revisión adversarial de C0. Cada una nació de un defecto
 * real encontrado leyendo el código recién escrito, no de imaginar escenarios.
 */
describe('cycleAnchorContaining acepta un ISO datetime, que es lo que trae una transacción', () => {
  it('un occurred_at completo cae en el MISMO ciclo que su day-string', () => {
    // La pregunta que C4 tiene que responder es «¿a qué ciclo pertenece esta
    // transacción?», y una transacción trae un ISO. Con la parte horaria
    // colándose en el parseo, `Number('14T10:00...')` daba NaN y `NaN >= 14`
    // es false: la respuesta era el ciclo ANTERIOR — el caso motivador
    // resuelto al revés, y en silencio.
    expect(cycleAnchorContaining('2026-08-14T10:00:00.000Z', 14)).toBe('2026-08');
    expect(cycleAnchorContaining('2026-08-14', 14)).toBe('2026-08');
    // Y el día de antes sigue perteneciendo al ciclo anterior por las dos vías.
    expect(cycleAnchorContaining('2026-08-13T23:59:59.000Z', 14)).toBe('2026-07');
    expect(cycleAnchorContaining('2026-08-13', 14)).toBe('2026-07');
  });

  it('con algo que no es una fecha LANZA, en vez de inventar un ancla', () => {
    // Devolver '0NaN-NaN' dejaba correr el error hasta una pantalla que
    // pintaría un período inexistente. Esta función decide en qué período cae
    // el dinero: mejor ruidosa aquí que plausible más abajo.
    expect(() => cycleAnchorContaining('basura', 14)).toThrow();
    expect(() => cycleAnchorContaining('', 14)).toThrow();
    expect(() => cycleAnchorContaining('2026-08', 14)).toThrow();
  });
});

describe('el huso del dispositivo no puede mover el corte del ciclo', () => {
  it('los bounds son los mismos que en UTC aunque el proceso corra en Europe/Madrid', () => {
    // Este fichero corre con TZ=Europe/Madrid fijado en vitest.config.ts. Con
    // el huso en UTC (que es donde corre CI) este test pasa aunque alguien
    // cambie `Date.UTC(...)` por `new Date(...)`, porque en UTC las dos dan lo
    // mismo: el gate sólo existe con un huso ≠ UTC. Verificado por mutación —
    // sustituir Date.UTC por el constructor local tumba 9 tests de este
    // fichero, y en CI pasaban los 52.
    expect(process.env.TZ).toBe('Europe/Madrid');
    expect(cycleBoundsForAnchor(14, '2026-08')).toEqual({
      dateFrom: '2026-08-14T00:00:00.000Z',
      dateTo: '2026-09-13T23:59:59.000Z',
    });
    // El primer día del ciclo, a medianoche UTC, es del ciclo que abre. En
    // Madrid ese instante son las 02:00 del día 14: si algún cálculo se hiciera
    // en local, este día se iría al ciclo anterior.
    expect(inCycle('2026-08-14T00:00:00.000Z', cycleBoundsForAnchor(14, '2026-08'))).toBe(true);
    expect(inCycle('2026-08-14T00:00:00.000Z', cycleBoundsForAnchor(14, '2026-07'))).toBe(false);
  });
});
