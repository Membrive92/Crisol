import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  bandColors,
  bandLabel,
  buildStatementRows,
  collectQualityFlags,
  colors,
  DIVIDEND_BLOCKS,
  effectiveThreshold,
  FORENSIC_KEYS,
  formatMetricValue,
  formatPercentDelta,
  formatThreshold,
  FLAG_SEVERITY_LABEL,
  fontSize,
  fontWeight,
  groupFlags,
  DUPONT_SECTIONS,
  dupontCheckRow,
  EVIDENCE_LABEL,
  EVOLUTION_METRICS,
  evidenceBreakdown,
  locateMetric,
  metricGapLegend,
  metricRow,
  QUALITY_LABEL,
  questionEvidence,
  radius,
  type StatementViewMode,
  RATIO_FAMILIES,
  spacing,
  TRAJECTORY_SECTION,
  VALUATION_COMPANIONS,
  VALUATION_ORDER,
  type CatalogIndex,
  type MatrixRow,
  type MetricIndex,
  type MetricRowOptions,
  type ScoreHelpIndex,
  scoreBreakdownRows,
  coreItemCoverage,
  REPORT_LEGEND,
  REPORT_SCOPE,
  SAFETY,
  safetyRules,
  type SafetyChecklist,
} from '@crisol/ui';
import type {
  AnalysisRun,
  CanonicalItemDefinition,
  EngineFlag,
  FinancialStatement,
  QuestionSignal,
  QuestionVerdict,
  Security,
  StatementKind,
} from '@crisol/types';

import { useValuation } from '@crisol/services';

import { YearMatrix } from './year-matrix';

/**
 * El cuerpo de las siete pestañas del informe en móvil (PHASE-44.8).
 *
 * **Qué se comparte y qué no.** Las filas se construyen con `metricRow` de
 * `@crisol/ui` —el mismo constructor que usa la web—, así que el valor, el
 * formato por unidad, la banda, el corte aplicado y la razón de un no-calculable
 * son literalmente el mismo cálculo. Lo único propio de este fichero es el
 * renderizado en primitivas RN. Es la línea que evita el estado del que venimos:
 * la web pasó a seis pestañas con formato por unidad en PHASE-44.9 mientras el
 * móvil seguía pintando el veredicto con las señales EN CRUDO
 * (`B4_dividend_funded_externally` en pantalla) y los márgenes como `0,42`.
 */

export interface TabContext {
  run: AnalysisRun;
  index: MetricIndex;
  catalog: CatalogIndex;
  security: Security | undefined;
  /**
   * Fichas del engine: qué es cada score y cómo se llama cada una de sus
   * variables (PHASE-44.24.A). Opcional: el catálogo llega por su propia query
   * y hasta que carga la tarjeta pinta la clave cruda diciéndolo.
   */
  help?: ScoreHelpIndex | undefined;
  /**
   * La fila a la que se ha llegado desde una señal del veredicto
   * (PHASE-44.24). En web viaja en la URL; aquí, en el estado de la pantalla.
   */
  highlightKey?: string | null | undefined;
  /**
   * Ir a una pestaña resaltando una fila. Lo llama la lista de señales del
   * veredicto: tocar «Deuda neta / EBITDA» debe llevar a Ratios con esa fila
   * marcada, como en web — antes tocarla no hacía nada.
   */
  goTo?: ((tab: string, highlight: string | null) => void) | undefined;
}

function options(ctx: TabContext): MetricRowOptions {
  return { index: ctx.index, catalog: ctx.catalog, thresholdsUsed: ctx.run.thresholds_used };
}

/** Las frases de una leyenda derivada, en una sola cadena. Sin frases, nada:
 *  una leyenda vacía ocupa sitio y no dice nada. */
function legendOf(sentences: string[]): string | undefined {
  return sentences.length === 0 ? undefined : sentences.join('\n');
}

function Block({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{title}</Text>
      {note ? <Text style={styles.note}>{note}</Text> : null}
      {children}
    </View>
  );
}

function Degraded({ title, reason }: { title: string; reason: string }) {
  return (
    <View style={[styles.card, styles.degraded]}>
      <Text style={styles.cardTitle}>{title}</Text>
      <Text style={styles.note}>{reason}</Text>
    </View>
  );
}

// ── Estados financieros ───────────────────────────────────────────────

const STATEMENT_KINDS: { key: StatementKind; label: string }[] = [
  { key: 'balance', label: 'Balance' },
  { key: 'income', label: 'Resultados' },
  { key: 'cashflow', label: 'Flujos' },
];

/** Los tres modos de lectura de la web, con etiquetas cortas para móvil. Las
 *  CLAVES son las mismas (`StatementViewMode` de `@crisol/ui`): la que decide
 *  qué se calcula es compartida, aquí sólo cambia cómo se llama el botón. */
const STATEMENT_VIEWS: { key: StatementViewMode; label: string }[] = [
  { key: 'amount', label: 'Importe' },
  { key: 'weight', label: '% común' },
  { key: 'delta', label: 'Variación' },
];

/** Qué significa cada modo, porque un «% común» sin contexto no dice sobre qué
 *  se calcula el porcentaje — y la respuesta (ventas para el P&L, activo total
 *  para el balance) es justo lo que hace útil la lectura. */
const VIEW_NOTE: Record<StatementViewMode, string> = {
  amount: '',
  weight:
    'Cada partida como porcentaje de su base: ventas en la cuenta de resultados, activo total en el balance. No cubre el flujo de caja ni cuatro partidas del P&L; ésas salen con «—».',
  delta: 'Variación respecto al ejercicio anterior. El primer año no tiene con qué compararse.',
};

export function TabStatements({
  ctx,
  statements,
  items,
  kind,
  onKindChange,
  view,
  onViewChange,
}: {
  ctx: TabContext;
  statements: FinancialStatement[] | undefined;
  items: CanonicalItemDefinition[] | undefined;
  kind: StatementKind;
  onKindChange: (kind: StatementKind) => void;
  view: StatementViewMode;
  onViewChange: (view: StatementViewMode) => void;
}) {
  if (!statements || statements.length === 0 || !items) {
    return (
      <Degraded
        title="Sin estados financieros"
        reason="No hay ejercicios ingeridos para este valor, o el catálogo de partidas no se ha podido cargar."
      />
    );
  }

  const years = statements.map((s) => s.fiscal_year);
  const verdictYear = ctx.run.years_covered[ctx.run.years_covered.length - 1];
  const rows = buildStatementRows({ kind, items, statements, view, run: ctx.run });
  const qualityFlags = collectQualityFlags(statements);

  return (
    <View style={{ gap: spacing.md }}>
      <Segmented
        value={kind}
        options={STATEMENT_KINDS}
        onChange={(next) => onKindChange(next as StatementKind)}
      />
      <Segmented
        value={view}
        options={STATEMENT_VIEWS}
        onChange={(next) => onViewChange(next as StatementViewMode)}
      />
      <Block
        title={STATEMENT_KINDS.find((k) => k.key === kind)?.label ?? ''}
        {...(VIEW_NOTE[view] ? { note: VIEW_NOTE[view] } : {})}
      >
        <YearMatrix
          marksLegend={REPORT_LEGEND}
          highlightKey={ctx.highlightKey}
          years={years}
          rows={rows}
          verdictYear={verdictYear}
          firstColumnLabel="Partida"
          legend={
            view === 'amount'
              ? '— hueco: el filing no publica el concepto, NO es un cero · · cero imputado · † derivada de otras partidas · ≈ proxy estimado · • ejercicio que alimenta el dictamen.'
              : '— la partida no entra en este modo de lectura · • ejercicio que alimenta el dictamen.'
          }
        />
      </Block>
      {qualityFlags.length > 0 ? (
        <Block title="Calidad del dato">
          <View style={{ gap: spacing.xs }}>
            {qualityFlags.map((flag) => (
              <Text key={flag.key} style={styles.flagText}>
                {flag.years.join(', ')} — {QUALITY_LABEL[flag.key] ?? flag.key}
              </Text>
            ))}
          </View>
        </Block>
      ) : null}
    </View>
  );
}

/** Selector compacto de sub-sección. RN no tiene `Segmented`, y el de web es
 *  HTML: aquí es la versión mínima que hace falta. */
function Segmented({
  value,
  options,
  onChange,
}: {
  value: string;
  options: { key: string; label: string }[];
  onChange: (key: string) => void;
}) {
  return (
    <View style={styles.segmented}>
      {options.map((option) => (
        <Pressable
          key={option.key}
          onPress={() => onChange(option.key)}
          style={[styles.segment, option.key === value && styles.segmentActive]}
        >
          <Text style={[styles.segmentText, option.key === value && styles.segmentTextActive]}>
            {option.label}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

// ── Ratios ────────────────────────────────────────────────────────────

export function TabRatios({ ctx }: { ctx: TabContext }) {
  const years = ctx.run.years_covered;
  const verdictYear = years[years.length - 1];
  const opts = options(ctx);
  // El DuPont llegó a móvil en PHASE-44.20: hasta entonces esta pestaña tenía
  // CUATRO bloques donde web tenía cinco, y el test de paridad no podía verlo
  // porque comparaba contra la lista compartida, que es justo donde faltaba.
  const dupont = ctx.run.scores_detail.base_ratios.dupont ?? [];
  return (
    <View style={{ gap: spacing.md }}>
      {RATIO_FAMILIES.map((family) => (
        <Block key={family.key} title={family.label} note={family.note}>
          <YearMatrix
            marksLegend={REPORT_LEGEND}
            highlightKey={ctx.highlightKey}
            years={years}
            rows={family.metrics.map((key) => metricRow(key, opts))}
            verdictYear={verdictYear}
            firstColumnLabel="Métrica"
            legend="— no calculable (el motivo, bajo la etiqueta) · * calculada con un input degradado · una celda gris es un valor SIN banda: el motor no tiene corte que aplicar, no significa que esté sano."
          />
        </Block>
      ))}
      {DUPONT_SECTIONS.map((section) => (
        <Block key={section.key} title={section.label} note={section.note}>
          {dupont.length === 0 ? (
            // Nunca en blanco: un hueco silencioso se lee como «no aplica», y lo
            // que pasa es que este análisis no trae la descomposición (regla 6).
            <Text style={styles.note}>
              Este análisis no trae la descomposición del ROE. Vuelve a ejecutarlo para obtenerla.
            </Text>
          ) : (
            <YearMatrix
              marksLegend={REPORT_LEGEND}
              highlightKey={ctx.highlightKey}
              years={dupont.map((point) => point.fiscal_year)}
              rows={[
                ...section.metrics.map((key) => metricRow(key, opts)),
                dupontCheckRow(section.check, dupont, (point) => point[section.check]),
              ]}
              firstColumnLabel="Factor"
            />
          )}
        </Block>
      ))}
    </View>
  );
}

// ── Evolución ─────────────────────────────────────────────────────────

export function TabEvolution({ ctx }: { ctx: TabContext }) {
  const { run } = ctx;
  const years = run.years_covered;
  // Mismo criterio que web: `horizontal` AUSENTE (motor 1.0.0) no es una
  // serie vacía, es una sección que ese motor no producía.
  if (run.evolution.horizontal === undefined) {
    return (
      <Degraded
        title="Este análisis no tiene serie de evolución"
        reason={`Lo calculó el motor ${run.engine_version}, que no emitía las variaciones año a año. No es un hueco en las cuentas de la empresa. Vuelve a analizar el valor para verla con el motor actual.`}
      />
    );
  }
  const series = run.evolution.horizontal;

  if (series.length === 0) {
    return (
      <Degraded
        title="Sin serie evolutiva"
        reason="Este análisis no trae el análisis horizontal. Vuelve a ejecutarlo para obtenerlo."
      />
    );
  }

  const seriesRows: MatrixRow[] = series.map((serie) => ({
    key: serie.key,
    label: serie.label,
    hint: serie.cagr
      ? `compuesto ${formatPercentDelta(serie.cagr)} anual`
      : (serie.cagr_reason ?? 'sin crecimiento compuesto calculable'),
    cells: years.map((year) => {
      const point = serie.points.find((p) => p.fiscal_year === year);
      return point ? { text: formatMetricValue(point.value, undefined) } : { text: '—' };
    }),
  }));

  const deltaRows: MatrixRow[] = series.map((serie) => ({
    key: `${serie.key}-yoy`,
    label: serie.label,
    cells: years.map((year) => {
      const point = serie.points.find((p) => p.fiscal_year === year);
      return { text: formatPercentDelta(point?.yoy ?? null) };
    }),
  }));

  return (
    <View style={{ gap: spacing.md }}>
      <Block title="Serie" note="Lo que el cuaderno pide mirar «año contra año», ya calculado.">
        <YearMatrix
          marksLegend={REPORT_LEGEND}
          highlightKey={ctx.highlightKey}
          years={years}
          rows={seriesRows}
          firstColumnLabel="Partida"
        />
      </Block>
      <Block title="Variación anual">
        <YearMatrix
          marksLegend={REPORT_LEGEND}
          highlightKey={ctx.highlightKey}
          years={years}
          rows={deltaRows}
          firstColumnLabel="Partida"
        />
      </Block>
      {/* E3 y E4 son las dos métricas CON BANDA de esta capa, y móvil no pintaba
          ninguna: la pestaña enseñaba series y variaciones, pero ni la
          estabilidad del margen ni el crecimiento sostenible (PHASE-44.20). */}
      {EVOLUTION_METRICS.map((section) => (
        <Block key={section.key} title={section.label} note={section.note}>
          <YearMatrix
            marksLegend={REPORT_LEGEND}
            highlightKey={ctx.highlightKey}
            years={years}
            rows={section.metrics.map((key) => metricRow(key, options(ctx)))}
            firstColumnLabel="Métrica"
          />
        </Block>
      ))}
      <FlagList flags={run.evolution.flags ?? []} />
    </View>
  );
}

// ── Forense ───────────────────────────────────────────────────────────

export function TabForensic({ ctx }: { ctx: TabContext }) {
  const years = ctx.run.years_covered;
  const verdictYear = years[years.length - 1];

  if (ctx.security?.is_financial) {
    return (
      <Degraded
        title="Los modelos forenses no aplican a una financiera"
        reason="Beneish, Altman, Piotroski y compañía se calibraron sobre empresas no financieras. En un banco el apalancamiento ES el negocio, así que estos cortes darían alarmas constantes sin significado. Consecuencia: sin ningún score en verde, el perfil de seguridad no puede llegar a «Conservador»."
      />
    );
  }

  return (
    <View style={{ gap: spacing.md }}>
      <Block
        title={`El desglose en ${verdictYear}`}
        note="Un score es un agregado: lo que dice el modelo está en sus variables. Al lado de cada una, cuánto se ha movido desde el ejercicio anterior — un nivel suelto no significa nada."
      >
        <View style={{ gap: spacing.md }}>
          {FORENSIC_KEYS.map((key) => (
            <ScoreCard key={key} metricKey={key} ctx={ctx} year={verdictYear} />
          ))}
        </View>
      </Block>

      <Block
        title={`Los ocho scores (hasta ${verdictYear})`}
        note="Todos book-based: se calculan sólo con las cuentas publicadas, nunca con la cotización. Es lo que hace que reejecutar un análisis antiguo devuelva el mismo resultado."
      >
        <YearMatrix
          marksLegend={REPORT_LEGEND}
          highlightKey={ctx.highlightKey}
          years={years}
          rows={FORENSIC_KEYS.map((key) => metricRow(key, options(ctx)))}
          verdictYear={verdictYear}
          firstColumnLabel="Score"
          // Derivada del run, igual que en web (PHASE-44.17): qué scores faltan y
          // por qué. La leyenda que había en web estaba escrita a mano y era falsa
          // en McDonald's; una copia a mano aquí lo habría sido en otro sitio.
          legend={legendOf(metricGapLegend(FORENSIC_KEYS, options(ctx)))}
        />
      </Block>
    </View>
  );
}

/**
 * Las cuatro claves forenses que NUNCA emiten desglose, por diseño.
 *
 * Misma lista que en web, y por el mismo motivo: distinguir «no tiene desglose»
 * de «este año no se pudo calcular».
 */
const NO_BREAKDOWN_BY_DESIGN = new Set(['accruals', 'F5', 'F6', 'FZ']);

/**
 * El desglose de un score forense en RN (PHASE-44.24.D).
 *
 * Móvil no tenía NINGUNO: los ocho scores salían como un número por año y las
 * 27 variables que los componen no se veían por ningún sitio. Las filas las
 * arma `scoreBreakdownRows` de `@crisol/ui`, la misma función que usa web, así
 * que la delta y el orden no pueden discrepar entre las dos apps.
 */
function ScoreCard({
  metricKey,
  ctx,
  year,
}: {
  metricKey: string;
  ctx: TabContext;
  year: number | undefined;
}) {
  const [open, setOpen] = useState(false);
  const ficha = ctx.help?.score(metricKey);
  const base = ctx.catalog.definition(metricKey);
  const definition = effectiveThreshold(metricKey, ctx.run.thresholds_used, base);
  const metric = year === undefined ? undefined : ctx.index.get(metricKey, year);
  const notComputable = !metric || metric.status === 'not_computable';
  const view = scoreBreakdownRows(
    metricKey,
    ctx.run.scores_detail.forensic.breakdowns,
    year,
    ctx.index,
    definition?.unit,
    ctx.help,
  );

  return (
    <View style={styles.scoreCard}>
      <View style={styles.scoreHead}>
        <Pressable
          disabled={!ficha}
          accessibilityRole={ficha ? 'button' : undefined}
          accessibilityLabel={ficha ? `Qué es «${base?.label ?? metricKey}»` : undefined}
          onPress={() => setOpen((v) => !v)}
          style={{ flex: 1 }}
        >
          <Text style={styles.scoreLabel}>
            {base?.label ?? metricKey}
            {metricKey === 'z_score' && ctx.run.z_variant ? ` ${ctx.run.z_variant}` : ''}
            {ficha ? ' ⓘ' : ''}
          </Text>
        </Pressable>
        <Text style={[styles.scoreValue, { color: bandColors(metric?.band ?? null).fg }]}>
          {notComputable ? '—' : formatMetricValue(metric.value, definition?.unit)}
        </Text>
      </View>

      {formatThreshold(definition) ? (
        <Text style={styles.scoreThreshold}>{formatThreshold(definition)}</Text>
      ) : null}

      {/* Los tres campos separados, igual que en web: «qué mide» se lee
          siempre, «cómo se lee» es lo que se vuelve a consultar. */}
      {open && ficha ? (
        <View style={{ gap: 4, marginTop: 4 }}>
          <Text style={styles.scoreHelp}>{ficha.what}</Text>
          <Text style={styles.scoreHelp}>Por qué importa: {ficha.why}</Text>
          <Text style={styles.scoreHelp}>Cómo se lee: {ficha.reading}</Text>
        </View>
      ) : null}

      {notComputable ? (
        <Text style={styles.scoreNote}>{metric?.reason ?? 'no se calculó en este ejercicio'}</Text>
      ) : null}

      {view.rows.map((row) => (
        <View key={row.key} style={styles.scoreRow}>
          <Text style={styles.scoreRowLabel} numberOfLines={2}>
            {row.kind === 'check' ? (row.passed ? '✓ ' : '✕ ') : ''}
            {row.label}
          </Text>
          <Text style={styles.scoreRowValue}>
            {row.kind === 'check' ? '' : row.value}
            {/* `null` es «no se puede comparar», no «no ha cambiado»: no se
                pinta nada, porque un «=» ahí afirmaría una comparación que no
                se ha hecho. */}
            {row.delta === null ? '' : ` ${row.delta}`}
          </Text>
        </View>
      ))}

      {view.rows.length === 0 && !notComputable ? (
        <Text style={styles.scoreNote}>
          {NO_BREAKDOWN_BY_DESIGN.has(metricKey)
            ? 'Este score no tiene desglose por diseño: es un ratio único, no un agregado de componentes.'
            : 'Sin desglose para este ejercicio.'}
        </Text>
      ) : null}
    </View>
  );
}

// ── Dividendo ─────────────────────────────────────────────────────────

export function TabDividend({ ctx }: { ctx: TabContext }) {
  const { run, security } = ctx;
  const years = run.years_covered;
  const verdictYear = years[years.length - 1];

  // Misma regla que la web (PHASE-44.19): `not_applicable` colapsa «financiera»
  // y «no reparte», y ocultar la pestaña con esa etiqueta escondía ocho métricas
  // ya calculadas. La pregunta se resuelve contra el RUN, no contra la fila viva.
  const paysDividend = (run.dividend_analysis.dps_series ?? []).some(
    (point) => point.dps !== null && Number(point.dps) > 0,
  );
  const quality = DIVIDEND_BLOCKS.find((block) => block.key === 'quality');

  if (!paysDividend) {
    return (
      <View style={{ gap: spacing.md }}>
        <Degraded
          title="Sin dividendo que juzgar"
          reason="Esta empresa no registra dividendos pagados en la serie. La calidad de la caja sí se calcula y va debajo: mide si el beneficio se convierte en caja, y eso no depende de que se reparta."
        />
        {quality ? (
          <Block title={quality.label} note={quality.note}>
            <YearMatrix
              marksLegend={REPORT_LEGEND}
              highlightKey={ctx.highlightKey}
              years={years}
              rows={quality.metrics.map((key) => metricRow(key, options(ctx)))}
              verdictYear={verdictYear}
              firstColumnLabel="Métrica"
            />
          </Block>
        ) : null}
        <FlagList flags={run.dividend_analysis.flags ?? []} />
      </View>
    );
  }

  return (
    <View style={{ gap: spacing.md }}>
      {security?.is_financial ? (
        <Text style={styles.note}>
          Es una financiera: las ratios que dividen por caja libre salen sin calcular a propósito
          —en un banco esa caja libre no significa lo mismo—. El payout sobre beneficio, la calidad
          de la caja y la trayectoria sí son válidos.
        </Text>
      ) : null}
      {DIVIDEND_BLOCKS.map((block) => (
        <Block key={block.key} title={block.label} note={block.note}>
          <YearMatrix
            marksLegend={REPORT_LEGEND}
            highlightKey={ctx.highlightKey}
            years={years}
            rows={block.metrics.map((key) => metricRow(key, options(ctx)))}
            verdictYear={verdictYear}
            firstColumnLabel="Métrica"
          />
        </Block>
      ))}
      {/* La Trayectoria no existía en móvil: faltaban el CAGR del dividendo, la
          estabilidad del payout, la racha sin recorte y —lo más elemental— el
          dividendo por acción año a año (PHASE-44.20). */}
      <Block title={TRAJECTORY_SECTION.label} note={TRAJECTORY_SECTION.note}>
        <Text style={styles.note}>
          {run.dividend_analysis.trajectory.streak_no_cut} años seguidos sin recortar
          {run.dividend_analysis.trajectory.momentum_slowdown
            ? ' · el crecimiento se está frenando'
            : ''}
        </Text>
        <YearMatrix
          marksLegend={REPORT_LEGEND}
          highlightKey={ctx.highlightKey}
          years={years}
          rows={[
            {
              key: 'dps',
              label: 'Dividendo por acción',
              hint: 'lo que se pagó por acción cada ejercicio',
              cells: years.map((year) => {
                const point = (run.dividend_analysis.dps_series ?? []).find(
                  (p) => p.fiscal_year === year,
                );
                return { text: formatMetricValue(point?.dps ?? null, 'currency_per_share') };
              }),
            },
            ...TRAJECTORY_SECTION.metrics.map((key) => metricRow(key, options(ctx))),
          ]}
          verdictYear={verdictYear}
          firstColumnLabel="Métrica"
        />
      </Block>
      <FlagList flags={run.dividend_analysis.flags ?? []} />
    </View>
  );
}

// ── Valoración ────────────────────────────────────────────────────────

/**
 * Los múltiplos contra la cotización (PHASE-44.12).
 *
 * Separada del veredicto forense a propósito: «¿es seguro?» sale de cuentas
 * cerradas y es reproducible; «¿está cara?» depende del precio de hoy. Y sin
 * semáforos, porque sin comparables de sector un color sería una opinión
 * disfrazada de dato.
 */
export function TabValuation({
  securityId,
  catalog,
}: {
  securityId: string;
  catalog: CatalogIndex;
}) {
  const query = useValuation(securityId);
  const data = query.data;

  if (query.isLoading) return <Degraded title="Cargando múltiplos…" reason="" />;
  if (!data || !data.available) {
    return (
      <Degraded
        title="Sin múltiplos"
        reason={data?.reason ?? 'No hay cotización con la que cruzar el último ejercicio.'}
      />
    );
  }

  const byKey = new Map(data.metrics.map((m) => [m.key, m]));
  const rows = [...VALUATION_ORDER, ...VALUATION_COMPANIONS]
    .map((key) => ({ key, metric: byKey.get(key), definition: catalog.definition(key) }))
    .filter((row) => row.metric !== undefined);

  return (
    <View style={{ gap: spacing.md }}>
      <Block
        title={`Múltiplos · ejercicio ${data.fiscal_year ?? '—'}`}
        note="Cruzan el precio del momento con el último ejercicio cerrado. No llevan banda: sin comparables de sector, un semáforo sería una opinión, no un dato."
      >
        <View style={{ gap: spacing.xs }}>
          {rows.map(({ key, metric, definition }) => (
            <View key={key} style={styles.signalRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.signalLabel}>{definition?.label ?? key}</Text>
                {definition?.note ? <Text style={styles.signalHint}>{definition.note}</Text> : null}
              </View>
              <Text style={[styles.signalValue, metric?.value === null && styles.muted]}>
                {metric?.value == null
                  ? 'no computable'
                  : formatMetricValue(metric.value, definition?.unit) +
                    (definition?.unit === 'currency_per_share' && data.statement_currency
                      ? ` ${data.statement_currency}`
                      : '')}
              </Text>
            </View>
          ))}
        </View>
      </Block>

      {/* Doble staleness: la fecha de la cotización Y la distancia a las cuentas
          con que se compara. Un PER con precio de hoy sobre un beneficio de hace
          catorce meses no es falso, pero tiene que decirlo. */}
      <Block title="Frescura del dato">
        <Text style={styles.note}>
          Cotización {data.quote_stale ? 'ANTIGUA' : 'al día'}
          {data.quote_as_of ? ` (${data.quote_as_of.slice(0, 10)})` : ''} · proveedor{' '}
          {data.provider_status === 'live'
            ? 'respondió'
            : data.provider_status === 'cached'
              ? 'no consultado (precio en caché)'
              : 'no disponible'}
          {data.days_since_fiscal_year_end != null
            ? ` · ${data.days_since_fiscal_year_end} días desde el cierre del ejercicio`
            : ''}
          {data.price_is_override ? ' · precio introducido a mano' : ''}
        </Text>
      </Block>
    </View>
  );
}

// ── Veredicto ─────────────────────────────────────────────────────────

export function TabVerdict({
  ctx,
  statements,
  items,
}: {
  ctx: TabContext;
  /** Para la sección de confianza. Van como props y NO en `TabContext`: sólo
   *  esta pestaña los necesita, y meterlos en el contexto obligaría a las siete
   *  a cargarlos. */
  statements?: FinancialStatement[] | undefined;
  items?: CanonicalItemDefinition[] | undefined;
}) {
  const { run, catalog } = ctx;
  const { verdict } = run;
  const profile = verdict.safety_profile;
  const safety = SAFETY[profile.label];
  // Las mismas reglas que web, del mismo view-model: si el motor añade una
  // condición, las dos pantallas la ganan a la vez (PHASE-44.24.E).
  const checklist = safetyRules(profile);
  // Las frases las compone el SERVIDOR (PHASE-44.24.B): deterministas y con
  // goldens, para que el dictamen de las dos apps no pueda discrepar.
  const sentenceOf = (key: string) => run.report?.questions?.find((q) => q.key === key)?.sentence;

  return (
    <View style={{ gap: spacing.md }}>
      <View style={styles.card}>
        <View style={styles.profileHead}>
          <Text style={styles.cardTitle}>Perfil de seguridad</Text>
          <Text style={[styles.profileBadge, { color: safety.fg, backgroundColor: safety.bg }]}>
            {safety.label}
          </Text>
        </View>
        <Text style={styles.note}>
          El perfil no es una nota media: sale de reglas booleanas sobre los scores forenses. Estas
          son, con lo que ha pasado en este análisis.
        </Text>
        <RuleChecklist block={checklist.avoid} />
        <RuleChecklist block={checklist.conservative} />
        {checklist.blocking.length > 0 ? (
          <Text style={styles.blocking}>
            {checklist.blockingLabel}
            {checklist.blocking.join('; ')}.
          </Text>
        ) : null}
      </View>

      {run.report?.next_checks?.length ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Qué miraría a continuación</Text>
          {run.report.next_checks.map((check) => (
            <Text key={check.key} style={styles.note}>
              {'· '}
              {check.text}
            </Text>
          ))}
        </View>
      ) : null}

      {verdict.questions.map((question) => {
        // Mismo tri-estado que la web, de la misma función: un verde por
        // ausencia de prueba —y un run viejo que ni siquiera registró qué se
        // evaluó— no se pintan con el color del veredicto.
        const evidence = questionEvidence(question);
        const band = bandColors(evidence === 'evaluated' ? question.verdict : null);
        return (
          <View
            key={question.key}
            style={[styles.card, { borderLeftWidth: 3, borderLeftColor: band.fg }]}
          >
            <Text style={styles.question}>{question.question}</Text>
            <Text style={[styles.bandText, { color: band.fg }]}>
              {evidence === 'evaluated' ? bandLabel(question.verdict) : EVIDENCE_LABEL[evidence]}
            </Text>
            {sentenceOf(question.key) ? (
              <Text style={styles.sentence}>{sentenceOf(question.key)}</Text>
            ) : null}
            {evidence === 'not-recorded' ? (
              <LegacySignals question={question} catalog={catalog} />
            ) : (
              <>
                {/* Mismo desglose que en web: «comprobado y limpio» es evidencia
                    positiva, y meterlo en el mismo cubo que un hueco hacía que
                    la pantalla se contradijera con su propio veredicto. */}
                <Text style={styles.evidence}>{evidenceBreakdown(question)}</Text>
                {/* El cuarto estado (PHASE-44.21): sin un portante, el veredicto
                    no se sostiene. Se dice qué falta, no sólo que falta. */}
                {evidence === 'not-audited'
                  ? (question.unaudited_reasons ?? []).map((reason) => (
                      <Text key={reason} style={styles.evidence}>
                        · {reason}
                      </Text>
                    ))
                  : null}
                {(question.notes ?? []).map((note) => (
                  <Text key={note} style={styles.evidence}>
                    {note}
                  </Text>
                ))}
                <SignalList
                  signals={question.signals ?? []}
                  catalog={catalog}
                  thresholdsUsed={run.thresholds_used}
                  goTo={ctx.goTo}
                />
              </>
            )}
          </View>
        );
      })}
      <FlagList flags={run.flags ?? []} help={ctx.help} />

      <StressCard run={run} />

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Alcance: lo que este informe NO cubre</Text>
        {/* El texto vive en `@crisol/ui`: lo pintan también web y el dictamen
            imprimible, y una copia por sitio es cómo divergen. */}
        {REPORT_SCOPE.map((entry) => (
          <Text key={entry.term} style={styles.note}>
            <Text style={styles.scopeTerm}>{entry.term}.</Text> {entry.meaning}
          </Text>
        ))}
      </View>

      <ConfidenceSection run={run} statements={statements} items={items} />

      <Text style={styles.footer}>
        Motor {run.engine_version} {'·'} umbrales {run.thresholds_version} {'·'} ejercicios{' '}
        {run.years_covered.join(', ')} {'·'} análisis del{' '}
        {new Date(run.run_date).toLocaleDateString('es-ES')}
      </Text>
    </View>
  );
}

/** Una de las dos listas de reglas del perfil, con su marca por condición. */
function RuleChecklist({
  block,
}: {
  block: SafetyChecklist['avoid'] | SafetyChecklist['conservative'];
}) {
  return (
    <View style={{ gap: 2, marginTop: spacing.xs }}>
      <Text style={styles.ruleTitle}>{block.title}</Text>
      {block.rules.map((rule) => {
        // En la lista de «Evitar», cumplir una regla es la MALA noticia: el
        // color no puede salir de `met` a secas.
        const malo = block.metIsBad ? rule.met : !rule.met;
        return (
          <Text
            key={rule.text}
            style={[styles.rule, { color: malo ? colors.danger : colors.textMuted }]}
          >
            {rule.met ? '✓' : '✕'} {rule.text}
          </Text>
        );
      })}
    </View>
  );
}

/**
 * Los escenarios de stress, en RN (PHASE-44.24.E).
 *
 * Sin el dumbbell, que sigue siendo sólo web (backlog 44.22): aquí van las
 * frases del motor, `breakeven_fcf_drop` y el motivo cuando no se pudo calcular
 * — que es justo lo que móvil no enseñaba, así que un escenario en rojo era
 * invisible en el teléfono.
 */
function StressCard({ run }: { run: AnalysisRun }) {
  const stress = run.verdict.stress;
  const scenarios = stress?.scenarios ?? [];
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Escenarios de stress</Text>
      <Text style={styles.note}>
        La cobertura se mide sobre caja libre (flujo de explotación − inversión), no sobre el FFO.
        En una socimi puede no coincidir con la cobertura de la pestaña Dividendo.
      </Text>
      {stress?.not_computable_reason ? (
        <Text style={styles.note}>Faltan escenarios: {stress.not_computable_reason}.</Text>
      ) : null}
      {scenarios.length === 0 ? (
        <Text style={styles.note}>No se ha podido calcular ningún escenario para este valor.</Text>
      ) : (
        scenarios.map((scenario) => (
          <View key={scenario.key} style={{ gap: 2, marginTop: spacing.xs }}>
            <Text style={styles.stressLabel}>
              [{scenario.label}] {scenario.parameter}
            </Text>
            <Text style={styles.note}>{scenario.sentence}</Text>
          </View>
        ))
      )}
      {stress?.breakeven_fcf_drop ? (
        <Text style={styles.note}>
          Margen de caída de la caja libre antes de dejar de cubrir el dividendo:{' '}
          {(Number(stress.breakeven_fcf_drop) * 100).toLocaleString('es-ES', {
            maximumFractionDigits: 0,
          })}{' '}
          %.
        </Text>
      ) : null}
    </View>
  );
}

/**
 * De qué se compone la confianza.
 *
 * Móvil enseñaba el porcentaje sin decir de dónde salía, que es un número sin
 * forma de auditarlo.
 */
function ConfidenceSection({
  run,
  statements,
  items,
}: {
  run: AnalysisRun;
  statements?: FinancialStatement[] | undefined;
  items?: CanonicalItemDefinition[] | undefined;
}) {
  const dc = run.data_completeness;
  const pct = (value: string) => Math.round(Number(value) * 100);
  // El mismo view-model que web (PHASE-44.24.E): qué partidas núcleo publicó
  // el filing en cada ejercicio, y si los ejercicios en pantalla son los que
  // el análisis juzgó.
  const coverage = coreItemCoverage(statements, items, run.years_covered);

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Cómo se calcula la confianza</Text>
      <Text style={styles.note}>
        {pct(dc.value)} % = completitud {pct(dc.completeness_core)} % × frescura{' '}
        {Number(dc.staleness_factor).toLocaleString('es-ES', {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1,
        })}
        .
      </Text>
      <Text style={styles.note}>
        {'· '}Completitud: fracción de las 10 partidas núcleo publicadas por el filing en cada
        ejercicio. Una partida imputada a cero no cuenta como publicada
        {dc.imputed_core_count > 0 ? ` — aquí hay ${dc.imputed_core_count} imputadas.` : '.'}
      </Text>
      <Text style={styles.note}>
        {'· '}Frescura: 1,0 si el último cierre tiene menos de 9 meses; 0,7 hasta 18 meses; 0,4 a
        partir de ahí.
        {dc.days_stale !== null
          ? ` El último cierre (${dc.latest_fiscal_year_end ?? '—'}) tiene ${dc.days_stale} días.`
          : ''}
      </Text>
      <Text style={styles.note}>
        Para datos anuales, una confianza alta con un cierre de hace meses es normal: el último 10-K
        es lo más reciente que existe.
      </Text>
      {coverage.mismatch ? (
        <Text style={styles.blocking}>
          Ojo: los estados en pantalla cubren {coverage.years.join(', ')} y el análisis juzgó{' '}
          {run.years_covered.join(', ')}. Vuelve a ejecutar el análisis para que coincidan.
        </Text>
      ) : null}

      {coverage.rows.length > 0 ? (
        <View style={{ gap: 2, marginTop: spacing.xs }}>
          <Text style={styles.ruleTitle}>
            Partidas núcleo por ejercicio ({coverage.years.join(' · ')})
          </Text>
          <Text style={styles.note}>
            Sale de los estados ingeridos, no del análisis. Un hueco aquí puede ser estructural: un
            balance no clasificado no publica activo ni pasivo corriente, y una empresa que no
            reparte no «omite» el dividendo — vale cero.
          </Text>
          {coverage.rows.map((row) => (
            <View key={row.key} style={styles.coverageRow}>
              <Text style={styles.coverageLabel} numberOfLines={1}>
                {row.label}
              </Text>
              <Text style={styles.coverageMarks}>
                {row.present.map((yes) => (yes ? '✓' : '—')).join(' ')}
              </Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

/**
 * Lo único que un run anterior a PHASE-44.9 sabe decir de una pregunta.
 *
 * Sin `signals[]` no hay desglose, pero `red_signals`/`amber_signals` sí están.
 * Se traducen con el catálogo para no enseñar la clave cruda, y se dice que el
 * veredicto no es auditable: sin saber cuántas señales se evaluaron, un verde
 * puede ser salud o ausencia de prueba y no hay forma de distinguirlo.
 */
function LegacySignals({
  question,
  catalog,
}: {
  question: QuestionVerdict;
  catalog: CatalogIndex;
}) {
  const label = (key: string) => catalog.definition(key)?.label ?? key;
  const groups = [
    { keys: question.red_signals, color: colors.danger, name: 'En rojo' },
    { keys: question.amber_signals, color: colors.warning, name: 'En ámbar' },
  ].filter((group) => group.keys.length > 0);

  return (
    <View style={{ gap: spacing.xs, marginTop: spacing.xs }}>
      <Text style={styles.note}>
        Este análisis lo produjo un motor anterior, que no registraba qué señales se evaluaron. El
        veredicto no es auditable: vuelve a ejecutarlo para ver el desglose.
      </Text>
      {groups.map((group) => (
        <Text key={group.name} style={styles.note}>
          <Text style={{ color: group.color, fontWeight: fontWeight.semibold }}>
            {group.name}:{' '}
          </Text>
          {group.keys.map(label).join(' · ')}
        </Text>
      ))}
    </View>
  );
}

/**
 * Las señales de una pregunta, con su valor, su banda y su corte.
 *
 * Enseña TODAS, incluidas las que no puntuaron y por qué: saber qué se comprobó
 * y salió bien es la otra mitad del porqué. Hasta esta fase el móvil concatenaba
 * `red_signals` y `amber_signals`, que son las CLAVES CRUDAS del motor — el
 * usuario leía `B4_dividend_funded_externally` en pantalla.
 */
function SignalList({
  signals,
  catalog,
  thresholdsUsed,
  goTo,
}: {
  signals: QuestionSignal[];
  catalog: CatalogIndex;
  thresholdsUsed: AnalysisRun['thresholds_used'];
  goTo?: ((tab: string, highlight: string | null) => void) | undefined;
}) {
  if (signals.length === 0) {
    // Lista VACÍA, no ausente: el motor sí publicó el desglose y esta pregunta
    // no tuvo ninguna señal candidata. El caso «motor anterior» lo atiende
    // `LegacySignals`, porque allí la clave ni siquiera existe.
    return <Text style={styles.note}>Esta pregunta no evaluó ninguna señal.</Text>;
  }
  return (
    <View style={{ gap: spacing.xs, marginTop: spacing.xs }}>
      {signals.map((signal) => {
        const definition = effectiveThreshold(
          signal.key,
          thresholdsUsed,
          catalog.definition(signal.key),
        );
        const threshold = formatThreshold(definition);
        const band = bandColors(signal.band);
        // Mismo registro que web: una señal con fila en otra pestaña se toca y
        // lleva allí; una bandera o un ancla, no (aquí no hay scroll a una
        // card). Sin destino, texto plano — no un toque que no hace nada.
        const target = goTo ? locateMetric(signal.key) : null;
        const navegable = Boolean(target && !target.anchor);
        return (
          <Pressable
            key={signal.key}
            style={styles.signalRow}
            disabled={!navegable}
            accessibilityRole={navegable ? 'button' : undefined}
            accessibilityHint={navegable ? 'Ir a la fila que la explica' : undefined}
            onPress={() =>
              target && goTo ? goTo(target.tab, target.highlight ?? signal.key) : undefined
            }
          >
            <View style={{ flex: 1 }}>
              <Text style={[styles.signalLabel, !signal.counted && styles.muted]}>
                {signal.label}
                {navegable ? ' ›' : ''}
              </Text>
              {threshold ? <Text style={styles.signalHint}>{threshold}</Text> : null}
              {!signal.counted ? (
                <Text style={styles.signalHint}>no puntúa · {signal.reason}</Text>
              ) : null}
            </View>
            <Text style={[styles.signalValue, !signal.counted && styles.muted]}>
              {signal.kind === 'metric' ? formatMetricValue(signal.value, definition?.unit) : '—'}
            </Text>
            <Text style={[styles.chip, { color: band.fg, backgroundColor: band.bg }]}>
              {bandLabel(signal.band)}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/**
 * Las banderas del motor, ya AGRUPADAS por clave (`groupFlags` compartido).
 *
 * Sin agrupar, una empresa que diluye siete años seguidos produce siete líneas
 * idénticas: el motor las emite por ejercicio y la síntesis las concatena. En
 * una pantalla de móvil eso es la diferencia entre leerlo y no leerlo.
 */
function FlagList({ flags, help }: { flags: EngineFlag[]; help?: ScoreHelpIndex | undefined }) {
  const grouped = groupFlags(flags);
  if (grouped.length === 0) return null;
  return (
    <Block title={`Banderas (${grouped.length})`}>
      <View style={{ gap: spacing.sm }}>
        {grouped.map((flag) => (
          <FlagCard key={flag.key} flag={flag} ficha={help?.flag(flag.key)} />
        ))}
      </View>
    </Block>
  );
}

/**
 * Una bandera con su ficha (PHASE-44.24.A), que móvil no enseñaba.
 *
 * Web despliega qué es, por qué importa, cómo se lee y DÓNDE comprobarlo en las
 * cuentas; aquí sólo salía el chip y el mensaje. Se abre tocando, que es el
 * único afordance sin ratón.
 */
function FlagCard({
  flag,
  ficha,
}: {
  flag: ReturnType<typeof groupFlags>[number];
  ficha: ReturnType<ScoreHelpIndex['flag']>;
}) {
  const [open, setOpen] = useState(false);
  const tone =
    flag.severity === 'red'
      ? { fg: colors.danger, bg: colors.dangerSoft }
      : flag.severity === 'amber'
        ? { fg: colors.warning, bg: colors.warningSoft }
        : { fg: colors.textMuted, bg: colors.surfaceMuted };
  return (
    <Pressable
      style={{ gap: 2 }}
      disabled={!ficha}
      accessibilityRole={ficha ? 'button' : undefined}
      accessibilityLabel={ficha ? `Qué significa esta bandera` : undefined}
      onPress={() => setOpen((v) => !v)}
    >
      <Text
        style={[styles.chip, { color: tone.fg, backgroundColor: tone.bg, alignSelf: 'flex-start' }]}
      >
        {FLAG_SEVERITY_LABEL[flag.severity]}
        {ficha ? ' ⓘ' : ''}
      </Text>
      {flag.messages.map((message) => (
        <Text key={message} style={styles.flagText}>
          {message}
        </Text>
      ))}
      {open && ficha ? (
        <View style={{ gap: 4, marginTop: 4 }}>
          <Text style={styles.scoreHelp}>{ficha.what}</Text>
          <Text style={styles.scoreHelp}>Por qué importa: {ficha.why}</Text>
          <Text style={styles.scoreHelp}>Cómo se lee: {ficha.reading}</Text>
          <Text style={styles.scoreHelp}>Dónde comprobarlo: {ficha.how_to_verify}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  profileHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  profileBadge: {
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold,
    overflow: 'hidden',
  },
  ruleTitle: {
    color: colors.textSubtle,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    marginTop: 2,
  },
  rule: { fontSize: fontSize.xs, lineHeight: 17 },
  blocking: { color: colors.warning, fontSize: fontSize.xs, lineHeight: 17, marginTop: spacing.xs },
  sentence: { color: colors.text, fontSize: fontSize.sm, lineHeight: 20, marginTop: 2 },
  scopeTerm: { color: colors.text, fontWeight: fontWeight.semibold },
  stressLabel: { color: colors.textSubtle, fontSize: fontSize.xs },
  footer: { color: colors.textSubtle, fontSize: 10, lineHeight: 15 },
  coverageRow: { flexDirection: 'row', alignItems: 'baseline', gap: spacing.sm },
  coverageLabel: { flex: 1, color: colors.textMuted, fontSize: fontSize.xs },
  coverageMarks: { color: colors.text, fontSize: fontSize.xs, letterSpacing: 2 },
  scoreCard: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.sm,
    gap: 2,
  },
  scoreHead: { flexDirection: 'row', alignItems: 'baseline', gap: spacing.sm },
  scoreLabel: { color: colors.text, fontSize: fontSize.sm, fontWeight: fontWeight.semibold },
  scoreValue: { fontSize: fontSize.md, fontWeight: fontWeight.bold },
  scoreThreshold: { color: colors.textSubtle, fontSize: fontSize.xs },
  scoreHelp: { color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 18, marginTop: 4 },
  scoreNote: { color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 18 },
  scoreRow: { flexDirection: 'row', alignItems: 'baseline', gap: spacing.sm },
  scoreRowLabel: { flex: 1, color: colors.textMuted, fontSize: fontSize.xs },
  scoreRowValue: { color: colors.text, fontSize: fontSize.xs, fontWeight: fontWeight.semibold },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    gap: spacing.sm,
  },
  degraded: { borderStyle: 'dashed' },
  cardTitle: { color: colors.text, fontSize: fontSize.sm, fontWeight: fontWeight.semibold },
  note: { color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 18 },
  question: { color: colors.text, fontSize: fontSize.sm, fontWeight: fontWeight.semibold },
  bandText: { fontSize: fontSize.xs, fontWeight: fontWeight.bold },
  evidence: { color: colors.textMuted, fontSize: fontSize.xs },
  signalRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.xs,
  },
  signalLabel: { color: colors.text, fontSize: fontSize.xs },
  signalHint: { color: colors.textSubtle, fontSize: 10, marginTop: 1 },
  signalValue: { color: colors.text, fontSize: fontSize.xs, minWidth: 62, textAlign: 'right' },
  muted: { color: colors.textMuted },
  chip: {
    fontSize: 10,
    fontWeight: fontWeight.semibold,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    overflow: 'hidden',
  },
  flagText: { color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 18 },
  segmented: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    padding: 2,
  },
  segment: { flex: 1, paddingVertical: spacing.xs, borderRadius: radius.sm, alignItems: 'center' },
  segmentActive: { backgroundColor: colors.surface },
  segmentText: { color: colors.textMuted, fontSize: fontSize.xs },
  segmentTextActive: { color: colors.text, fontWeight: fontWeight.semibold },
});
