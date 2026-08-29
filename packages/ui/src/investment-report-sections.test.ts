import { describe, expect, it } from 'vitest';

import {
  allScreenMetricKeys,
  locateMetric,
  STRESS_ANCHOR,
  RATIO_FAMILIES,
  RATIOS_SUB_DUPONT,
  REPORT_TABS,
  SECTION_PLACEMENT,
  DIVIDEND_BLOCKS,
} from './investment-report-sections';

/**
 * El registro de dónde vive cada métrica (PHASE-44.24.C.4).
 *
 * Con `allScreenMetricKeys` y `locateMetric` derivados del MISMO registro,
 * «toda clave resuelve» es cierto por construcción y no es un gate: quitar una
 * métrica la quita del dominio del test y de la tabla a la vez, y el verde no
 * significa nada. Lo que sí puede fallar —y es lo que se prueba aquí— es que el
 * destino no exista, que la precedencia esté mal, o que una señal que no es
 * métrica se quede sin sitio.
 */
describe('locateMetric', () => {
  it('toda pestaña de destino existe de verdad', () => {
    const tabs = new Set(REPORT_TABS.map((t) => t.key));
    const desconocidas = [...allScreenMetricKeys()]
      // Toda métrica de pantalla TIENE destino: un `null` aquí sería una
      // fila que existe y no se puede enlazar desde el veredicto.
      .map((key) => locateMetric(key)?.tab ?? '(sin destino)')
      .filter((tab) => !tabs.has(tab));
    expect([...new Set(desconocidas)]).toEqual([]);
  });

  it('toda sub-sección de destino es la clave de una sección real', () => {
    const subs = new Set<string>([
      ...RATIO_FAMILIES.map((f) => f.key),
      ...DIVIDEND_BLOCKS.map((b) => b.key),
      'trayectoria',
      RATIOS_SUB_DUPONT,
    ]);
    const huerfanas = [...allScreenMetricKeys()]
      .map((key) => locateMetric(key)?.sub ?? null)
      .filter((sub): sub is string => sub !== null && !subs.has(sub));
    expect([...new Set(huerfanas)]).toEqual([]);
  });

  it('una métrica que está en dos bloques va a su FAMILIA, no al DuPont', () => {
    // R4, A4 y DUPONT_EM están en las dos: la familia es donde está su serie
    // completa, y el DuPont sólo su papel como factor.
    expect(locateMetric('R4')).toEqual({ tab: 'ratios', sub: 'rentabilidad' });
    expect(locateMetric('A4')).toEqual({ tab: 'ratios', sub: 'actividad' });
  });

  it('los factores exclusivos del DuPont sí van al DuPont', () => {
    expect(locateMetric('DUPONT_OM')).toEqual({ tab: 'ratios', sub: RATIOS_SUB_DUPONT });
  });

  it('las señales DERIVADAS tienen sitio, aunque el gate del backend no las vea', () => {
    // No están en `ALL_METRIC_KEYS`, así que si se quedaran sin destino nadie
    // lo diría y el enlace del veredicto llevaría a ninguna parte.
    // Y dicen ADÓNDE exactamente: la primera versión mandaba `fcf_trend` a
    // Evolución «a secas» y el usuario aterrizaba sin ninguna fila marcada.
    expect(locateMetric('fcf_trend')).toEqual({
      tab: 'evolucion',
      sub: null,
      highlight: 'fcf_cfo',
    });
    expect(locateMetric('stress')).toMatchObject({ tab: 'veredicto', anchor: STRESS_ANCHOR });
  });

  it('ninguna clave de PANTALLA tiene forma de bandera', () => {
    // Las banderas del motor se escriben `<LETRA><n>_<snake>` (`C3_inventory_vs_cogs`,
    // `B4_dividend_funded_externally`). Si una entrara en un bloque de pantalla
    // por error, volvería a enlazarse a ninguna parte — y el test de abajo,
    // que mira dos claves concretas, no lo vería. El gate que ata claves REALES
    // vive en el backend (`test_investment_report_links.py`).
    const conFormaDeBandera = [...allScreenMetricKeys()].filter((key) =>
      /^[A-Z]{1,2}\d+_[a-z]/.test(key),
    );
    expect(conFormaDeBandera).toEqual([]);
  });

  it('una bandera NO tiene destino: no es una fila de ninguna matriz', () => {
    // Antes caía «al veredicto», que es donde el usuario ya está: eso producía
    // un enlace a la misma pestaña que recargaba la página, cerraba el
    // desglose y no resaltaba nada. Sin destino, sin enlace.
    expect(locateMetric('B4_dividend_funded_externally')).toBeNull();
    expect(locateMetric('C3_inventory_vs_cogs')).toBeNull();
    expect(locateMetric('clave_que_no_existe')).toBeNull();
  });

  it('el registro no está vacío ni se ha quedado sin bloques', () => {
    // Un registro vacío haría que todos los tests de arriba pasaran por
    // vacuidad: no habría ninguna clave que comprobar.
    expect(SECTION_PLACEMENT.length).toBeGreaterThan(8);
    expect(allScreenMetricKeys().size).toBeGreaterThan(50);
  });
});
