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
}

function options(ctx: TabContext): MetricRowOptions {
  return { index: ctx.index, catalog: ctx.catalog, thresholdsUsed: ctx.run.thresholds_used };
}

/** Las frases de una leyenda derivada, en una sola cadena. Sin frases, nada:
 *  una leyenda vacía ocupa sitio y no dice nada. */
function legendOf(sentences: string[]): string | undefined {
  return sentences.length === 0 ? undefined : sentences.join('\n');
}

function Block({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
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
  const series = run.evolution.horizontal ?? [];

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
        <YearMatrix years={years} rows={seriesRows} firstColumnLabel="Partida" />
      </Block>
      <Block title="Variación anual">
        <YearMatrix years={years} rows={deltaRows} firstColumnLabel="Partida" />
      </Block>
      {/* E3 y E4 son las dos métricas CON BANDA de esta capa, y móvil no pintaba
          ninguna: la pestaña enseñaba series y variaciones, pero ni la
          estabilidad del margen ni el crecimiento sostenible (PHASE-44.20). */}
      {EVOLUTION_METRICS.map((section) => (
        <Block key={section.key} title={section.label} note={section.note}>
          <YearMatrix
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
    <Block
      title={`Los ocho scores (hasta ${verdictYear})`}
      note="Todos book-based: se calculan sólo con las cuentas publicadas, nunca con la cotización. Es lo que hace que reejecutar un análisis antiguo devuelva el mismo resultado."
    >
      <YearMatrix
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
          —en un banco esa caja libre no significa lo mismo—. El payout sobre beneficio, la
          calidad de la caja y la trayectoria sí son válidos.
        </Text>
      ) : null}
      {DIVIDEND_BLOCKS.map((block) => (
        <Block key={block.key} title={block.label} note={block.note}>
          <YearMatrix
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
export function TabValuation({ securityId, catalog }: { securityId: string; catalog: CatalogIndex }) {
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

export function TabVerdict({ ctx }: { ctx: TabContext }) {
  const { run, catalog } = ctx;
  const { verdict } = run;

  return (
    <View style={{ gap: spacing.md }}>
      {verdict.questions.map((question) => {
        // Mismo tri-estado que la web, de la misma función: un verde por
        // ausencia de prueba —y un run viejo que ni siquiera registró qué se
        // evaluó— no se pintan con el color del veredicto.
        const evidence = questionEvidence(question);
        const band = bandColors(evidence === 'evaluated' ? question.verdict : null);
        return (
          <View key={question.key} style={[styles.card, { borderLeftWidth: 3, borderLeftColor: band.fg }]}>
            <Text style={styles.question}>{question.question}</Text>
            <Text style={[styles.bandText, { color: band.fg }]}>
              {evidence === 'evaluated' ? bandLabel(question.verdict) : EVIDENCE_LABEL[evidence]}
            </Text>
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
                />
              </>
            )}
          </View>
        );
      })}
      <FlagList flags={run.flags ?? []} />
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
        Este análisis lo produjo un motor anterior, que no registraba qué señales se evaluaron.
        El veredicto no es auditable: vuelve a ejecutarlo para ver el desglose.
      </Text>
      {groups.map((group) => (
        <Text key={group.name} style={styles.note}>
          <Text style={{ color: group.color, fontWeight: fontWeight.semibold }}>{group.name}: </Text>
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
}: {
  signals: QuestionSignal[];
  catalog: CatalogIndex;
  thresholdsUsed: AnalysisRun['thresholds_used'];
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
        return (
          <View key={signal.key} style={styles.signalRow}>
            <View style={{ flex: 1 }}>
              <Text style={[styles.signalLabel, !signal.counted && styles.muted]}>
                {signal.label}
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
          </View>
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
function FlagList({ flags }: { flags: EngineFlag[] }) {
  const grouped = groupFlags(flags);
  if (grouped.length === 0) return null;
  return (
    <Block title={`Banderas (${grouped.length})`}>
      <View style={{ gap: spacing.sm }}>
        {grouped.map((flag) => {
          const tone =
            flag.severity === 'red'
              ? { fg: colors.danger, bg: colors.dangerSoft }
              : flag.severity === 'amber'
                ? { fg: colors.warning, bg: colors.warningSoft }
                : { fg: colors.textMuted, bg: colors.surfaceMuted };
          return (
            <View key={flag.key} style={{ gap: 2 }}>
              <Text style={[styles.chip, { color: tone.fg, backgroundColor: tone.bg, alignSelf: 'flex-start' }]}>
                {FLAG_SEVERITY_LABEL[flag.severity]}
              </Text>
              {flag.messages.map((message) => (
                <Text key={message} style={styles.flagText}>
                  {message}
                </Text>
              ))}
            </View>
          );
        })}
      </View>
    </Block>
  );
}

const styles = StyleSheet.create({
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
