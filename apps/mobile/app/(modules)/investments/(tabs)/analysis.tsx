import { useEffect, useMemo, useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  formatApiError,
  useCanonicalItems,
  useIngest,
  useAnalysisRun,
  useAnalysisRuns,
  useLatestAnalysisRun,
  useRunComparison,
  useHelpCatalog,
  useMetricCatalog,
  useRunAnalysis,
  useSecurity,
  useStatements,
} from '@crisol/services';
import type { AnalysisRunSummary, RunDiff, StatementKind } from '@crisol/types';
import {
  bandColors,
  buildCatalogIndex,
  buildScoreHelpIndex,
  buildMetricIndex,
  collectRunMetrics,
  colors,
  DEFAULT_REPORT_TAB,
  diffRows,
  DIVIDEND,
  fontSize,
  fontWeight,
  isRunOutdated,
  questionEvidence,
  radius,
  REPORT_GUIDE,
  REPORT_TABS,
  SAFETY,
  spacing,
  type StatementViewMode,
} from '@crisol/ui';

import {
  TabDividend,
  TabEvolution,
  TabForensic,
  TabRatios,
  TabStatements,
  TabValuation,
  TabVerdict,
  type TabContext,
} from '@/components/investment/report-tabs';
import { SecuritySearch } from '@/components/investment/security-search';

/**
 * Informe de análisis en móvil — paridad con web (PHASE-44.8).
 *
 * Antes esta pantalla era un `TextInput` de ticker y una lista de preguntas con
 * **las señales en crudo**: el usuario leía `B4_dividend_funded_externally` y un
 * margen del 42 % como `0,42`. La web lo arregló en PHASE-44.9 y el móvil se
 * quedó atrás, que es la forma en que dos pantallas de la misma app acaban
 * contando cosas distintas.
 *
 * Ahora consume la MISMA capa pura (`@crisol/ui`): las mismas siete pestañas, las
 * mismas métricas por bloque, el mismo formato por unidad, la misma banda y el
 * mismo corte. Lo único propio son las primitivas de React Native.
 *
 * La pestaña vive en estado local y no en la URL: Expo Router no tiene aquí el
 * query param de la web, y forzarlo obligaría a una ruta por pestaña. La CLAVE
 * sí es la misma (`veredicto`, `estados`…), así que el día que haya enlaces
 * profundos no hay que renombrar nada.
 */
export default function AnalysisScreen() {
  const [securityId, setSecurityId] = useState<string | null>(null);
  const [tab, setTab] = useState<string>(DEFAULT_REPORT_TAB);
  const [statementKind, setStatementKind] = useState<StatementKind>('balance');
  const [statementView, setStatementView] = useState<StatementViewMode>('amount');
  // La guía del vocabulario (PHASE-44.24.E). En móvil es una hoja modal y no
  // una ruta: se consulta sin perder la pestaña en la que estabas.
  const [guideOpen, setGuideOpen] = useState(false);
  // El análisis del histórico que se está mirando (PHASE-44.24.F). `null` = el
  // último.
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  // La fila a la que se ha llegado desde una señal del veredicto. Web la lleva
  // en la URL (`?metric=`); aquí vive en estado y se borra al cambiar de
  // pestaña a mano, por el mismo motivo: un resaltado que sobrevive a la
  // navegación reaparece en cada visita.
  const [highlightKey, setHighlightKey] = useState<string | null>(null);
  const page = useRef<ScrollView>(null);

  const security = useSecurity(securityId);
  const statements = useStatements(securityId, 'all');
  const latestRun = useLatestAnalysisRun(securityId);
  const metricCatalog = useMetricCatalog();
  const helpCatalog = useHelpCatalog();
  const canonicalItems = useCanonicalItems();
  const ingest = useIngest();
  const run = useRunAnalysis();

  const runs = useAnalysisRuns(securityId);
  const selectedRun = useAnalysisRun(selectedRunId);
  // Sólo se pide si HAY con qué comparar: con menos de dos análisis el servidor
  // responde 404 por diseño, y pedirlo igualmente sería una petición garantizada
  // a fallar en cada valor que se abre.
  const comparison = useRunComparison(
    securityId,
    null,
    selectedRunId,
    (runs.data?.items.length ?? 0) >= 2,
  );

  /**
   * El run mostrado. Mismo criterio que web (PHASE-44.24.F): la selección del
   * histórico manda, y un rerun la BORRA — con la precedencia al revés,
   * `useMutation.data` persiste mientras la pantalla esté montada y el selector
   * no podría enseñar nunca un análisis viejo tras reejecutar.
   */
  const activeRun = selectedRunId ? selectedRun.data : (run.data ?? latestRun.data);

  const catalogIndex = useMemo(
    () => buildCatalogIndex(metricCatalog.data?.items),
    [metricCatalog.data],
  );

  // Las fichas del engine (PHASE-44.24.A). Si no han cargado, la tarjeta cae a
  // la clave cruda del motor y lo dice, en vez de dejar el hueco en blanco.
  const scoreHelp = useMemo(() => buildScoreHelpIndex(helpCatalog.data), [helpCatalog.data]);

  const metricIndex = useMemo(() => {
    if (!activeRun) return null;
    return buildMetricIndex(collectRunMetrics(activeRun), activeRun.years_covered);
  }, [activeRun]);

  const hasStatements = (statements.data?.length ?? 0) > 0;

  const ctx: TabContext | null =
    activeRun && metricIndex
      ? {
          run: activeRun,
          index: metricIndex,
          catalog: catalogIndex,
          security: security.data,
          help: scoreHelp,
          highlightKey,
          goTo: (target, highlight) => {
            setTab(target);
            setHighlightKey(highlight);
            // La página es un solo ScrollView vertical y conserva el offset al
            // cambiar de pestaña: desde la tercera pregunta del veredicto se
            // aterrizaba a ~1.500 px de scroll, sin la barra de pestañas y sin
            // la fila resaltada a la vista. Arriba, con la barra visible.
            page.current?.scrollTo({ y: 0, animated: true });
          },
        }
      : null;

  // El run seleccionado en el histórico mientras carga, o si no existe. Sin
  // estos dos estados, elegir un análisis viejo desmontaba la pantalla ENTERA
  // —hero, histórico y pestañas— hasta que llegaba, y si no llegaba, para
  // siempre (el mismo defecto que se corrigió en web).
  const selectedPending = Boolean(selectedRunId) && selectedRun.isLoading;
  const selectedMissing = Boolean(selectedRunId) && selectedRun.isError;
  // «Hay análisis» no depende del seleccionado: mientras uno viejo carga (o
  // no existe) el botón decía «Ejecutar análisis» como si no hubiera ninguno.
  const hasAnyRun = Boolean(latestRun.data ?? run.data);

  /**
   * Reejecuta y BORRA la selección del histórico. El comentario de `activeRun`
   * lo prometía y el botón no lo hacía: con un run viejo seleccionado, el
   * análisis recién ejecutado quedaba escondido detrás y el banner seguía
   * diciendo «no es el último». El `catch` evita el rechazo suelto.
   */
  const rerun = async (id: string) => {
    try {
      await run.mutateAsync({ securityId: id });
    } catch {
      return;
    }
    setSelectedRunId(null);
  };

  return (
    <>
      <GuideSheet open={guideOpen} onClose={() => setGuideOpen(false)} />
      <ScrollView ref={page} contentContainerStyle={styles.container}>
        <SecuritySearch
          onSelect={(id) => {
            setSecurityId(id);
            setTab(DEFAULT_REPORT_TAB);
            setSelectedRunId(null);
            // `useMutation.data` NO se limpia al cambiar de valor: sin esto, el
            // análisis que acabas de lanzar sobre MCD se presenta como el
            // informe de la empresa que acabas de elegir. Preexistente a esta
            // fase; el selector de runs lo habría heredado (PHASE-44.24.F).
            run.reset();
          }}
        />

        {securityId && !hasStatements && !statements.isLoading ? (
          <Pressable
            onPress={() => void ingest.mutateAsync({ securityId, filings_back: 5 })}
            disabled={ingest.isPending}
            style={styles.primaryBtn}
          >
            <Text style={styles.primaryBtnText}>
              {ingest.isPending ? 'Descargando 10-K…' : 'Descargar 10-K (EDGAR)'}
            </Text>
          </Pressable>
        ) : null}

        {ingest.data?.status === 'failed' ? (
          <Text style={styles.error}>{ingest.data.error}</Text>
        ) : null}
        {run.isError ? (
          <Text style={styles.error}>
            {formatApiError(run.error, 'No se pudo ejecutar el análisis.')}
          </Text>
        ) : null}

        {securityId && hasStatements ? (
          <Pressable
            onPress={() => void rerun(securityId)}
            disabled={run.isPending}
            style={styles.primaryBtn}
          >
            <Text style={styles.primaryBtnText}>
              {run.isPending
                ? 'Analizando…'
                : hasAnyRun
                  ? 'Volver a analizar'
                  : 'Ejecutar análisis'}
            </Text>
          </Pressable>
        ) : null}

        {securityId && (ctx || selectedPending || selectedMissing) ? (
          <>
            {ctx ? (
              <Hero ctx={ctx} onGuide={() => setGuideOpen(true)} />
            ) : (
              <View style={styles.hero}>
                <Text style={styles.heroMeta}>
                  {selectedMissing
                    ? 'Ese análisis no existe o no es tuyo.'
                    : 'Cargando ese análisis…'}
                </Text>
              </View>
            )}
            <RunHistory
              runs={runs.data?.items ?? []}
              selectedId={selectedRunId}
              onSelect={setSelectedRunId}
              diff={comparison.data}
              reason={
                comparison.isError
                  ? formatApiError(comparison.error, 'No se ha podido comparar.')
                  : null
              }
              pending={selectedPending}
              missing={selectedMissing}
            />
          </>
        ) : null}

        {ctx && securityId ? (
          <>
            <TabBar
              value={tab}
              onChange={(key) => {
                setTab(key);
                setHighlightKey(null);
                page.current?.scrollTo({ y: 0, animated: false });
              }}
            />
            <TabBody
              tab={tab}
              ctx={ctx}
              securityId={securityId}
              statements={statements.data}
              items={canonicalItems.data}
              statementKind={statementKind}
              onStatementKindChange={setStatementKind}
              statementView={statementView}
              onStatementViewChange={setStatementView}
            />
          </>
        ) : null}
      </ScrollView>
    </>
  );
}

/**
 * Cabecera persistente: el dictamen y la confianza no desaparecen al cambiar de
 * pestaña. Es lo que impide leer un ratio suelto sin recordar de qué valor es ni
 * con cuánta evidencia se ha juzgado.
 */
function Hero({ ctx, onGuide }: { ctx: TabContext; onGuide: () => void }) {
  const { run, security } = ctx;
  const safety = SAFETY[run.verdict.safety_profile.label];
  const completeness = Math.round(Number(run.data_completeness.value) * 100);
  // El motor que produjo ESTE run frente al del catálogo cargado. Un informe
  // de 1.0.0 tiene huecos que no son de la empresa (PHASE-44.16).
  const stale = isRunOutdated(run.engine_version, ctx.help?.engineVersion);

  return (
    <View style={styles.hero}>
      <Text style={styles.heroTicker}>
        {security?.ticker ?? '—'}
        {security?.name ? ` · ${security.name}` : ''}
      </Text>
      <Text style={[styles.heroVerdict, { color: safety.fg, backgroundColor: safety.bg }]}>
        {safety.label}
      </Text>

      {/* Las cuatro preguntas de un vistazo, con el MISMO tri-estado que web:
          un verde sin evidencia evaluada se pinta gris, porque es ausencia de
          prueba y no salud (PHASE-44.9). */}
      <View style={styles.heroQuestions}>
        {run.verdict.questions.map((question) => {
          const evidence = questionEvidence(question);
          const band = bandColors(evidence === 'evaluated' ? question.verdict : null);
          return (
            <View key={question.key} style={styles.heroQuestion}>
              <View style={[styles.heroDot, { backgroundColor: band.fg }]} />
              <Text style={styles.heroQuestionText} numberOfLines={1}>
                {question.question}
              </Text>
            </View>
          );
        })}
      </View>

      {/* El titular lo compone el SERVIDOR (PHASE-44.24.B): determinista y con
          goldens, para que la primera frase del informe sea la misma en las dos
          apps y en el dictamen impreso. */}
      {run.report?.headline ? <Text style={styles.heroHeadline}>{run.report.headline}</Text> : null}

      <Text style={styles.heroMeta}>
        {DIVIDEND[run.verdict.dividend_verdict]} · confianza {completeness} % · ejercicios{' '}
        {run.years_covered.join(', ')}
      </Text>
      <Text style={styles.heroMeta}>
        Motor {run.engine_version} · umbrales {run.thresholds_version} · análisis del{' '}
        {new Date(run.run_date).toLocaleDateString('es-ES')}
      </Text>

      {stale ? (
        <Text style={styles.heroStale}>
          Este análisis lo produjo un motor anterior ({run.engine_version}); el actual es{' '}
          {ctx.help?.engineVersion}. Vuelve a analizarlo para ver las métricas que entonces no se
          calculaban.
        </Text>
      ) : null}

      <Pressable onPress={onGuide} accessibilityRole="button">
        <Text style={styles.heroGuide}>Cómo leer este informe</Text>
      </Pressable>
    </View>
  );
}

function TabBar({ value, onChange }: { value: string; onChange: (key: string) => void }) {
  const scroller = useRef<ScrollView>(null);
  const offsets = useRef<Record<string, number>>({});

  // La pestaña activa, a la vista. La de aterrizaje es Veredicto, la SÉPTIMA:
  // sin esto quedaba fuera de pantalla y todos los chips visibles salían en
  // gris, sin nada que dijera que había más a la derecha.
  useEffect(() => {
    const x = offsets.current[value];
    if (x === undefined) return;
    scroller.current?.scrollTo({ x: Math.max(0, x - spacing.lg), animated: true });
  }, [value]);

  return (
    <ScrollView
      ref={scroller}
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.tabBar}
    >
      {REPORT_TABS.map((item) => (
        <Pressable
          key={item.key}
          onPress={() => onChange(item.key)}
          onLayout={(event) => {
            offsets.current[item.key] = event.nativeEvent.layout.x;
            // El primer layout llega DESPUÉS del primer efecto: si es la
            // activa, se desplaza ahora.
            if (item.key === value) {
              scroller.current?.scrollTo({
                x: Math.max(0, event.nativeEvent.layout.x - spacing.lg),
                animated: false,
              });
            }
          }}
          accessibilityRole="tab"
          accessibilityState={{ selected: item.key === value }}
          style={[styles.tab, item.key === value && styles.tabActive]}
        >
          <Text style={[styles.tabText, item.key === value && styles.tabTextActive]}>
            {item.label}
          </Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

function TabBody({
  tab,
  ctx,
  securityId,
  statements,
  items,
  statementKind,
  onStatementKindChange,
  statementView,
  onStatementViewChange,
}: {
  tab: string;
  ctx: TabContext;
  securityId: string;
  statements: Parameters<typeof TabStatements>[0]['statements'];
  items: Parameters<typeof TabStatements>[0]['items'];
  statementKind: StatementKind;
  onStatementKindChange: (kind: StatementKind) => void;
  statementView: StatementViewMode;
  onStatementViewChange: (view: StatementViewMode) => void;
}) {
  if (tab === 'estados') {
    return (
      <TabStatements
        ctx={ctx}
        statements={statements}
        items={items}
        kind={statementKind}
        onKindChange={onStatementKindChange}
        view={statementView}
        onViewChange={onStatementViewChange}
      />
    );
  }
  if (tab === 'ratios') return <TabRatios ctx={ctx} />;
  if (tab === 'evolucion') return <TabEvolution ctx={ctx} />;
  if (tab === 'forense') return <TabForensic ctx={ctx} />;
  if (tab === 'dividendo') return <TabDividend ctx={ctx} />;
  if (tab === 'valoracion') {
    return <TabValuation securityId={securityId} catalog={ctx.catalog} />;
  }
  return <TabVerdict ctx={ctx} statements={statements} items={items} />;
}

const styles = StyleSheet.create({
  container: { padding: spacing.md, gap: spacing.md },
  heroQuestions: { gap: 2, marginTop: spacing.xs },
  heroQuestion: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  heroDot: { width: 8, height: 8, borderRadius: 4 },
  heroQuestionText: { flex: 1, color: colors.textMuted, fontSize: fontSize.xs },
  heroHeadline: {
    color: colors.text,
    fontSize: fontSize.sm,
    lineHeight: 20,
    marginTop: spacing.xs,
  },
  heroStale: {
    color: colors.warning,
    fontSize: fontSize.xs,
    lineHeight: 17,
    marginTop: spacing.xs,
  },
  heroGuide: { color: colors.primary, fontSize: fontSize.xs, marginTop: spacing.xs },
  history: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  historyToggle: { color: colors.primary, fontSize: fontSize.xs },
  historyRun: { color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 18 },
  historyRunActive: { color: colors.text, fontWeight: fontWeight.semibold },
  historyNote: { color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 17 },
  historyWarn: { color: colors.warning, fontSize: fontSize.xs, lineHeight: 17 },
  historyRow: { fontSize: fontSize.xs, lineHeight: 17 },
  historyBanner: {
    marginTop: spacing.xs,
    padding: spacing.sm,
    borderRadius: radius.sm,
    backgroundColor: colors.warningSoft,
    gap: 4,
  },
  historyBannerText: { color: colors.text, fontSize: fontSize.xs, lineHeight: 17 },
  sheet: { flex: 1, backgroundColor: colors.background },
  sheetHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  sheetTitle: { color: colors.text, fontSize: fontSize.md, fontWeight: fontWeight.bold },
  sheetClose: { color: colors.primary, fontSize: fontSize.sm },
  sheetBody: { padding: spacing.md, gap: spacing.lg },
  sheetSection: { gap: spacing.xs },
  sheetSectionTitle: { color: colors.text, fontSize: fontSize.sm, fontWeight: fontWeight.semibold },
  sheetIntro: { color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 18 },
  sheetEntry: { flexDirection: 'row', gap: spacing.sm, marginTop: 2 },
  sheetTerm: {
    width: 92,
    color: colors.text,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
  },
  sheetMeaning: { flex: 1, color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 18 },
  primaryBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryBtnText: {
    color: colors.onPrimary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
  error: { color: colors.danger, fontSize: fontSize.sm },
  hero: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    gap: spacing.xs,
  },
  heroTicker: { color: colors.text, fontSize: fontSize.md, fontWeight: fontWeight.semibold },
  heroVerdict: {
    alignSelf: 'flex-start',
    fontSize: fontSize.xs,
    fontWeight: fontWeight.bold,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    overflow: 'hidden',
  },
  heroMeta: { color: colors.textMuted, fontSize: fontSize.xs },
  tabBar: { gap: spacing.xs, paddingVertical: 2 },
  tab: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceMuted,
  },
  tabActive: { backgroundColor: colors.primary },
  tabText: { color: colors.textMuted, fontSize: fontSize.xs },
  tabTextActive: { color: colors.onPrimary, fontWeight: fontWeight.semibold },
});

/**
 * «Cómo leer este informe», en una hoja modal (PHASE-44.24.E).
 *
 * Sin contenido propio: renderiza `REPORT_GUIDE` de `@crisol/ui`, el mismo que
 * pinta la página de web. Escribir los estados a mano aquí sería la forma
 * exacta en que caducó la leyenda del forense.
 */
function GuideSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Modal visible={open} animationType="slide" onRequestClose={onClose} transparent={false}>
      {/* Bajo el área segura: a pantalla completa, el título y el botón
          «Cerrar» quedaban debajo del notch y la barra de estado. */}
      <SafeAreaView style={styles.sheet} edges={['top', 'bottom']}>
        <View style={styles.sheetHead}>
          <Text style={styles.sheetTitle}>Cómo leer este informe</Text>
          <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Cerrar">
            <Text style={styles.sheetClose}>Cerrar</Text>
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={styles.sheetBody}>
          {REPORT_GUIDE.map((section) => (
            <View key={section.key} style={styles.sheetSection}>
              <Text style={styles.sheetSectionTitle}>{section.title}</Text>
              <Text style={styles.sheetIntro}>{section.intro}</Text>
              {section.entries.map((entry) => (
                <View key={entry.term} style={styles.sheetEntry}>
                  <Text style={styles.sheetTerm}>{entry.term}</Text>
                  <Text style={styles.sheetMeaning}>{entry.meaning}</Text>
                </View>
              ))}
            </View>
          ))}
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

/**
 * El histórico de análisis y qué ha cambiado (PHASE-44.24.F).
 *
 * Las filas las arma `diffRows` de `@crisol/ui` —la misma función que usa web—,
 * así que las dos apps ordenan igual: lo que ha empeorado primero.
 */
function RunHistory({
  runs,
  selectedId,
  onSelect,
  diff,
  reason,
  pending,
  missing,
}: {
  runs: AnalysisRunSummary[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  diff: RunDiff | undefined;
  /** Por qué no hay comparación, en lenguaje del usuario. `null` si la hay. */
  reason: string | null;
  /** El análisis seleccionado aún está cargando. */
  pending: boolean;
  /** El análisis seleccionado no existe o no es tuyo. */
  missing: boolean;
}) {
  // Abierto por defecto si hay una selección: al desmontarse y volver, el
  // panel se plegaba y el usuario tenía que reabrirlo para saber dónde estaba.
  const [open, setOpen] = useState(Boolean(selectedId));
  if (runs.length < 2) return null;
  const view = diffRows(diff);
  const viewing = selectedId ? runs.find((r) => r.id === selectedId) : undefined;
  // Sólo cuando el seleccionado EXISTE y ha cargado: con `missing`, este
  // banner y el de «no existe» salían a la vez, cada uno con su «Volver».
  const viewingOld = Boolean(viewing) && viewing?.id !== runs[0]?.id && !missing && !pending;

  return (
    <View style={styles.history}>
      <Pressable onPress={() => setOpen((v) => !v)} accessibilityRole="button">
        <Text style={styles.historyToggle}>
          {open ? 'Ocultar' : 'Ver'} qué ha cambiado desde el análisis anterior
        </Text>
      </Pressable>

      {/* Tocar una fila cambia TODO el informe de arriba: sin este aviso, la
          única señal era una negrita dentro de un panel plegado. */}
      {viewingOld && viewing ? (
        <View style={styles.historyBanner}>
          <Text style={styles.historyBannerText}>
            Estás viendo el análisis del {new Date(viewing.run_date).toLocaleDateString('es-ES')},
            no el último.
          </Text>
          <Pressable onPress={() => onSelect(null)} accessibilityRole="button">
            <Text style={styles.historyToggle}>Volver al último</Text>
          </Pressable>
        </View>
      ) : null}
      {pending ? <Text style={styles.historyNote}>Cargando ese análisis…</Text> : null}
      {missing ? (
        <View style={styles.historyBanner}>
          <Text style={styles.historyWarn}>Ese análisis no existe o no es tuyo.</Text>
          <Pressable onPress={() => onSelect(null)} accessibilityRole="button">
            <Text style={styles.historyToggle}>Volver al último</Text>
          </Pressable>
        </View>
      ) : null}

      {open ? (
        <View style={{ gap: spacing.xs, marginTop: spacing.xs }}>
          {runs.map((item) => {
            const activo = item.id === (selectedId ?? runs[0]?.id);
            return (
              <Pressable
                key={item.id}
                onPress={() => onSelect(item.id === runs[0]?.id ? null : item.id)}
                accessibilityRole="button"
              >
                <Text style={[styles.historyRun, activo ? styles.historyRunActive : null]}>
                  {new Date(item.run_date).toLocaleDateString('es-ES')} ·{' '}
                  {item.years_covered.join(', ')} · motor {item.engine_version}
                </Text>
              </Pressable>
            );
          })}

          {/* El MOTIVO del servidor, no una frase fija: «hacen falta dos»,
              «es el más antiguo» y «no es tuyo» son cosas distintas, y un 500
              o la red caída no son ninguna de ellas. */}
          {reason ? <Text style={styles.historyWarn}>{reason}</Text> : null}

          {view.caveat ? <Text style={styles.historyWarn}>{view.caveat}</Text> : null}

          {view.methodChanges.length > 0 ? (
            <Text style={styles.historyNote}>
              Cambió el método: {view.methodChanges.join('; ')}.
            </Text>
          ) : null}

          {view.restatements.map((frase) => (
            <Text key={frase} style={styles.historyNote}>
              {frase}
            </Text>
          ))}

          {view.unchanged ? (
            <Text style={styles.historyNote}>
              Nada se ha movido: mismo perfil, mismas bandas, mismas banderas.
            </Text>
          ) : null}

          {view.rows.map((row) => (
            <Text
              key={row.key}
              style={[
                styles.historyRow,
                {
                  color:
                    row.direction === 'worse'
                      ? colors.danger
                      : row.direction === 'better'
                        ? colors.success
                        : colors.textMuted,
                },
              ]}
            >
              {row.label}: {row.before ?? '—'} → {row.after ?? '—'}
            </Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}
