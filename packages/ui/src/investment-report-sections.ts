/**
 * Qué métricas entra en cada bloque del informe de Inversión, y con qué nota.
 *
 * Es **contenido**, no presentación: la lista de claves y el porqué del bloque
 * son los mismos en web y en móvil, y lo único que cambia es cómo se pintan. Se
 * comparte por la razón de siempre en este repo —dos copias divergen— y aquí el
 * coste de divergir es concreto: una pantalla enseñando ocho scores forenses y
 * la otra seis, sin que nada avise.
 *
 * Las notas son las de la web, que salieron de contrastar el motor con el
 * cuaderno del usuario. No se resumen para móvil: si un matiz importa para
 * entender el número, importa en las dos pantallas.
 */

export interface ReportSection {
  key: string;
  label: string;
  /** Claves de métrica del catálogo, en orden de lectura. */
  metrics: readonly string[];
  /** Por qué este bloque y qué mirar. Vacío si el bloque no lo necesita. */
  note: string;
}

/** Familias de ratios, en el orden de las hojas 5 a 9 del cuaderno del usuario. */
export const RATIO_FAMILIES: readonly ReportSection[] = [
  {
    key: 'liquidez',
    label: 'Liquidez',
    metrics: ['L1', 'L2', 'L3', 'L4'],
    note: 'El cuaderno pide ratio corriente, prueba ácida y ratio de caja. El muro de vencimientos (L4) lo añade el motor: es el mecanismo real por el que una empresa quiebra —no poder refinanciar— y los otros tres no lo miran.',
  },
  {
    key: 'actividad',
    label: 'Actividad',
    metrics: ['A1', 'A2', 'A3', 'A4', 'A5'],
    note: 'Ninguna tiene banda absoluta, y es deliberado: un plazo de cobro de 45 días es excelente en retail y pésimo en software. Lo que informa aquí es la deriva, no el nivel. Ojo: el motor usa saldos MEDIOS (t y t−1); tu cuaderno usa el saldo de cierre, así que los números no coincidirán exactamente.',
  },
  {
    key: 'solvencia',
    label: 'Solvencia y deuda',
    metrics: ['S1', 'S2', 'S3', 'S4', 'S4b', 'S5', 'S6', 'S7', 'S8'],
    note: 'S2 usa EBIT (devengo, maquillable) y S6 usa caja generada. Si S2 sale verde y S6 rojo, el devengo está mintiendo. Igual con S4 (sobre EBITDA) y S4b (sobre EBIT): en negocios con mucha amortización, el EBITDA infla la capacidad de repago aparente. El ratio de endeudamiento (S7) usa la banda 1-2 de tu cuaderno, calibrada para negocios con activo tangible: en financieras se muestra sin semáforo, porque allí el apalancamiento es el negocio.',
  },
  {
    key: 'rentabilidad',
    label: 'Rentabilidad',
    metrics: ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8', 'R9', 'R9b', 'R10', 'DUPONT_EM'],
    note: 'Margen bruto, margen neto y apalancamiento financiero salen sin banda: los cortes de tu cuaderno (40 %, 10 %, ≤3) son razonables como regla general, pero dependen tanto del sector que el motor prefiere no pintar un semáforo global.',
  },
];

/**
 * Los ocho scores forenses, en el orden en que se leen: primero manipulación,
 * luego quiebra, luego calidad.
 */
/**
 * Una fila del bloque forense, con la lectura que la acompaña si la tiene.
 *
 * `reading` NO es otra métrica: es la MISMA comprobación en otra escala, y la
 * pareja la declara el motor (`SCALE_COMPANIONS`, forensic.py) porque es una
 * propiedad del modelo. Aquí sólo se consume.
 *
 * Se modela como pareja y no como dos entradas de la lista porque, puestas una
 * debajo de otra, las dos lecturas se parecen tanto que invitan a pensar que
 * una es la otra multiplicada — pasó con el X-Score (0,87) y su probabilidad
 * (80,7 %), y no lo son: Φ(0) es 50 %, no 0 %. Con esta forma, devolver la
 * acompañante a la lista de filas deja de ser posible en vez de depender de
 * que alguien recuerde no hacerlo.
 */
export interface ForensicRow {
  key: string;
  reading?: string;
}

export const FORENSIC_ROWS: readonly ForensicRow[] = [
  { key: 'm_score' },
  { key: 'accruals' },
  { key: 'F7' },
  { key: 'F6' },
  { key: 'z_score' },
  { key: 'FZ', reading: 'FZ_P' },
  { key: 'f_score' },
  { key: 'F5' },
];

/**
 * Todas las claves del bloque, filas y acompañantes.
 *
 * DERIVADA y no escrita a mano: alimenta el registro de ubicaciones y el gate
 * del backend que exige que toda métrica del motor tenga sitio en pantalla, y
 * una segunda lista se quedaría atrás en cuanto la primera cambiara.
 */
export const FORENSIC_KEYS: readonly string[] = FORENSIC_ROWS.flatMap((row) =>
  row.reading ? [row.key, row.reading] : [row.key],
);

/** Bloques del análisis de dividendo. */
export const DIVIDEND_BLOCKS: readonly ReportSection[] = [
  {
    key: 'coverage',
    label: 'Cobertura',
    metrics: ['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D8'],
    note: 'La primaria es el payout sobre caja libre: la caja, no el beneficio, es lo que paga el dividendo. Si el payout ajustado por retribución en acciones es muy superior al normal, el dividendo se está pagando diluyendo.',
  },
  {
    key: 'quality',
    label: 'Calidad de la caja',
    metrics: ['Q1', 'Q2', 'Q3', 'Q5'],
    note: 'Mide si la caja que paga el dividendo es real. La divergencia entre las dos formas de calcular la caja libre es la señal más útil: cuando no cuadran, una de las dos miente.',
  },
  {
    key: 'balance',
    label: 'Soporte del balance',
    metrics: ['B3'],
    note: 'Cuántos años de dividendo hay en caja. Las banderas de este bloque —la deuda compitiendo con el dividendo, los intereses con prioridad, el dividendo financiado fuera— están abajo.',
  },
];

/**
 * Las dos descomposiciones del ROE (PHASE-44.20).
 *
 * No caben en `ReportSection` porque además de métricas llevan una fila de
 * **comprobación** —el producto de los factores menos el ROE, que debe dar
 * cero— y ésa no es una métrica del catálogo: vive en
 * `scores_detail.base_ratios.dupont[]`. Los factores SÍ están en `metrics[]`,
 * así que el índice global sirve y no hace falta ningún índice propio.
 *
 * Estaban escritas a mano en `tab-ratios.tsx`, y por eso móvil no tenía el
 * DuPont: cuatro bloques donde web tenía cinco.
 */
export interface DuPontSection extends ReportSection {
  /** Campo del punto DuPont con el cuadre. No es una `metric_key`. */
  check: 'check_three' | 'check_five';
}

export const DUPONT_SECTIONS: readonly DuPontSection[] = [
  {
    key: 'dupont3',
    label: 'DuPont de tres factores',
    metrics: ['R4', 'A4', 'DUPONT_EM'],
    check: 'check_three',
    note: 'ROE = margen neto × rotación de activos × apalancamiento financiero. Dice QUÉ movió el ROE: uno que sube sólo por el apalancamiento no es mejora del negocio, es deuda.',
  },
  {
    key: 'dupont5',
    label: 'DuPont extendido (cinco factores)',
    metrics: ['DUPONT_OM', 'DUPONT_TAX', 'DUPONT_FIN', 'A4', 'DUPONT_EM'],
    check: 'check_five',
    note: 'Desdobla el margen neto en de dónde sale: cuánto gana el negocio, cuánto se lleva la financiación y cuánto Hacienda. El margen operativo usa el EBIT REPORTADO, no el limpio de deterioros que emplea R3: es lo que hace que la identidad cierre.',
  },
];

/** Las métricas con banda de la capa evolutiva. */
export const EVOLUTION_METRICS: readonly ReportSection[] = [
  {
    key: 'evolucion',
    label: 'Estabilidad y crecimiento',
    metrics: ['E3', 'E4'],
    note: 'La desviación del margen operativo mide predictibilidad, y la predictibilidad ES seguridad: un margen que oscila mucho puede estar en su año bueno justo cuando lo miras. El crecimiento sostenible es el que la empresa puede financiar sin pedir dinero ni emitir acciones.',
  },
];

/**
 * Trayectoria del dividendo. Mezcla dos escalares y una serie que NO son
 * métricas (`streak_no_cut`, `momentum_slowdown`, `dps_series`) con dos que sí.
 *
 * T2 y T3 quedan fuera de `DIVIDEND_BLOCKS` a propósito: el motor las emite una
 * sola vez, para el último ejercicio, así que en una matriz por año saldrían con
 * N−1 huecos indistinguibles de un «no calculable».
 */
export const TRAJECTORY_SECTION: ReportSection = {
  key: 'trayectoria',
  label: 'Trayectoria',
  metrics: ['T2', 'T3'],
  note: 'La racha sin recorte es una COTA INFERIOR: sólo cuenta lo que hay en la serie ingerida, no el histórico completo de la empresa.',
};

/** Múltiplos de valoración (PHASE-44.12) y sus dos acompañantes. */
export const VALUATION_ORDER: readonly string[] = ['V1', 'V2', 'V3', 'V4', 'V5'];
export const VALUATION_COMPANIONS: readonly string[] = ['V6', 'V7'];

/**
 * TODA clave de métrica que alguna pestaña puede llegar a pintar.
 *
 * Existe para que un test pueda afirmar que el catálogo del motor y la pantalla
 * no divergen. La divergencia que motiva esto: la capa compartida cubría 57 de
 * las 64, y las otras 7 estaban escritas a mano en tres ficheros de web — así
 * que móvil, que renderiza estrictamente desde aquí, no las pintaba nunca
 * (PHASE-44.20).
 */
/** La clave de sub-sección de la pestaña DuPont, que no es una familia. */
export const RATIOS_SUB_DUPONT = 'dupont';

/** Dónde se pinta un bloque de métricas: pestaña y, si la tiene, sub-sección. */
export interface SectionPlacement {
  metrics: readonly string[];
  tab: string;
  sub: string | null;
}

/**
 * El registro ÚNICO de dónde vive cada métrica (PHASE-44.24.C.4).
 *
 * De aquí se derivan las dos cosas que antes se enumeraban por separado: qué
 * claves puede pintar la pantalla (`allScreenMetricKeys`) y en qué pestaña está
 * cada una (`locateMetric`). Con dos enumeraciones, quitar una métrica de una
 * lista la quitaría también del dominio del test que la comprueba, y el test
 * seguiría verde sin haber preguntado por ella — el defecto exacto que una
 * revisión adversarial encontró en el plan de esta fase.
 *
 * El orden importa: la primera coincidencia gana. `R4`, `A4` y `DUPONT_EM`
 * están a la vez en una familia de ratios y en las descomposiciones DuPont, y
 * el destino correcto es la familia, que es donde está su serie completa.
 */
/**
 * El `id` de la card de escenarios de stress en el veredicto.
 *
 * Declarado aquí y no en la card, porque quien lo consume es el registro de
 * destinos: la señal «Escenario de stress» no es una fila, es esa card.
 */
export const STRESS_ANCHOR = 'stress-scenarios';

/**
 * El ancla de la card «Por qué este veredicto» (PHASE-44.25).
 *
 * Vive aquí y no en la página que la compone porque la usan el hero (para
 * enlazar) y la card (para recibir el salto): dos literales sueltos divergen en
 * cuanto alguien renombra uno.
 */
export const WHY_ANCHOR = 'por-que-este-veredicto';

export const SECTION_PLACEMENT: readonly SectionPlacement[] = [
  ...RATIO_FAMILIES.map((family) => ({ metrics: family.metrics, tab: 'ratios', sub: family.key })),
  ...EVOLUTION_METRICS.map((section) => ({
    metrics: section.metrics,
    tab: 'evolucion',
    sub: null,
  })),
  { metrics: FORENSIC_KEYS, tab: 'forense', sub: null },
  ...DIVIDEND_BLOCKS.map((block) => ({
    metrics: block.metrics,
    tab: 'dividendo',
    sub: block.key,
  })),
  { metrics: TRAJECTORY_SECTION.metrics, tab: 'dividendo', sub: TRAJECTORY_SECTION.key },
  ...DUPONT_SECTIONS.map((section) => ({
    metrics: section.metrics,
    tab: 'ratios',
    sub: RATIOS_SUB_DUPONT,
  })),
  { metrics: VALUATION_ORDER, tab: 'valoracion', sub: null },
  { metrics: VALUATION_COMPANIONS, tab: 'valoracion', sub: null },
];

/** Dónde vive una señal del veredicto, para enlazarla. */
export interface MetricPlacement {
  tab: string;
  sub: string | null;
  /**
   * La fila que hay que resaltar al llegar, cuando NO es la propia clave.
   *
   * Una señal derivada («tendencia de la caja libre») no es una fila de
   * ninguna matriz: la fila que la explica es la serie de la que sale.
   */
  highlight?: string;
  /**
   * Un ancla dentro de la pestaña, para las señales que no son una fila sino
   * una CARD (los escenarios de stress). Se llega con `#ancla`, sin recargar.
   */
  anchor?: string;
}

/**
 * Las señales que la síntesis COMPONE y que no son métricas del catálogo.
 *
 * El gate del backend no las ve —no están en `ALL_METRIC_KEYS`— así que si se
 * quedaran sin sitio nadie lo diría, y el enlace del veredicto llevaría a
 * ninguna parte. Cada una dice ADÓNDE exactamente: la primera versión mandaba
 * `fcf_trend` a Evolución «a secas», y el usuario aterrizaba arriba de la
 * pestaña sin ninguna fila marcada.
 */
const DERIVED_PLACEMENT: Readonly<Record<string, MetricPlacement>> = {
  fcf_trend: { tab: 'evolucion', sub: null, highlight: 'fcf_cfo' },
  stress: { tab: 'veredicto', sub: 'dictamen', anchor: STRESS_ANCHOR },
};

/**
 * En qué pestaña vive una señal, o `null` si no vive en ninguna.
 *
 * Las banderas no son métricas ni filas: su sitio es la lista de banderas del
 * propio veredicto, donde el usuario ya está. La versión anterior las mandaba
 * «al veredicto» y eso producía un enlace a la MISMA pestaña que recargaba la
 * página, cerraba el desglose que se estaba leyendo y no resaltaba nada —
 * veintiuna señales que parecían enlaces y no llevaban a ningún sitio. Sin
 * destino no hay enlace: la fila se pinta como texto.
 */
export function locateMetric(key: string): MetricPlacement | null {
  const derived = DERIVED_PLACEMENT[key];
  if (derived) return derived;
  const placement = SECTION_PLACEMENT.find((section) => section.metrics.includes(key));
  if (placement) return { tab: placement.tab, sub: placement.sub };
  return null;
}

export function allScreenMetricKeys(): ReadonlySet<string> {
  const keys = new Set<string>();
  SECTION_PLACEMENT.forEach((section) => section.metrics.forEach((k) => keys.add(k)));
  return keys;
}

/**
 * Las pestañas del informe, en su orden.
 *
 * Las claves son las que YA viajan en la URL de la web (`?tab=veredicto`), no
 * unas nuevas: inventar un segundo vocabulario para móvil es exactamente el
 * fallo que compartir este fichero evita, y además rompería los enlaces
 * guardados.
 */
export const REPORT_TABS: readonly { key: string; label: string }[] = [
  { key: 'estados', label: 'Estados' },
  { key: 'ratios', label: 'Ratios' },
  { key: 'evolucion', label: 'Evolución' },
  { key: 'forense', label: 'Forense' },
  { key: 'dividendo', label: 'Dividendo' },
  // Valoración va DESPUÉS del dividendo y ANTES del veredicto, y separada del
  // forense a propósito: «¿es seguro?» y «¿está cara?» son preguntas distintas
  // (PHASE-44.12). Son SIETE pestañas; contarlas mal es lo que dejó esta
  // inalcanzable durante un rato al centralizar la lista.
  { key: 'valoracion', label: 'Valoración' },
  { key: 'veredicto', label: 'Veredicto' },
];

/** Pestaña de aterrizaje: el veredicto es lo que se viene a ver; la evidencia
 *  se consulta desde ahí. */
export const DEFAULT_REPORT_TAB = 'veredicto';
