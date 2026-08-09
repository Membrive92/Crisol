import { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import {
  formatApiError,
  useCanonicalItems,
  useIngest,
  useLatestAnalysisRun,
  useMetricCatalog,
  useRunAnalysis,
  useSecurity,
  useStatements,
} from '@crisol/services';
import type { StatementKind } from '@crisol/types';
import {
  bandColors,
  buildCatalogIndex,
  buildMetricIndex,
  collectRunMetrics,
  colors,
  DEFAULT_REPORT_TAB,
  fontSize,
  fontWeight,
  radius,
  REPORT_TABS,
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

  const security = useSecurity(securityId);
  const statements = useStatements(securityId, 'all');
  const latestRun = useLatestAnalysisRun(securityId);
  const metricCatalog = useMetricCatalog();
  const canonicalItems = useCanonicalItems();
  const ingest = useIngest();
  const run = useRunAnalysis();

  // El run mostrado es el persistido; si se acaba de reejecutar, el más reciente
  // es el de la mutación (la query aún no ha refrescado). Mismo criterio que web.
  const activeRun = run.data ?? latestRun.data;

  const catalogIndex = useMemo(
    () => buildCatalogIndex(metricCatalog.data?.items),
    [metricCatalog.data],
  );

  const metricIndex = useMemo(() => {
    if (!activeRun) return null;
    return buildMetricIndex(collectRunMetrics(activeRun), activeRun.years_covered);
  }, [activeRun]);

  const hasStatements = (statements.data?.length ?? 0) > 0;

  const ctx: TabContext | null =
    activeRun && metricIndex
      ? { run: activeRun, index: metricIndex, catalog: catalogIndex, security: security.data }
      : null;

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <SecuritySearch
        onSelect={(id) => {
          setSecurityId(id);
          setTab(DEFAULT_REPORT_TAB);
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
      {run.isError ? <Text style={styles.error}>{formatApiError(run.error, 'No se pudo ejecutar el análisis.')}</Text> : null}

      {securityId && hasStatements ? (
        <Pressable
          onPress={() => void run.mutateAsync({ securityId })}
          disabled={run.isPending}
          style={styles.primaryBtn}
        >
          <Text style={styles.primaryBtnText}>
            {run.isPending ? 'Analizando…' : activeRun ? 'Volver a analizar' : 'Ejecutar análisis'}
          </Text>
        </Pressable>
      ) : null}

      {ctx && securityId ? (
        <>
          <Hero ctx={ctx} />
          <TabBar value={tab} onChange={setTab} />
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
  );
}

/**
 * Cabecera persistente: el dictamen y la confianza no desaparecen al cambiar de
 * pestaña. Es lo que impide leer un ratio suelto sin recordar de qué valor es ni
 * con cuánta evidencia se ha juzgado.
 */
function Hero({ ctx }: { ctx: TabContext }) {
  const { run, security } = ctx;
  const profile = run.verdict.safety_profile;
  const tone = bandColors(
    profile.label === 'conservative' ? 'healthy' : profile.label === 'watch' ? 'caution' : 'stressed',
  );
  const completeness = Math.round(Number(run.data_completeness.value) * 100);

  return (
    <View style={styles.hero}>
      <Text style={styles.heroTicker}>
        {security?.ticker ?? '—'}
        {security?.name ? ` · ${security.name}` : ''}
      </Text>
      <Text style={[styles.heroVerdict, { color: tone.fg, backgroundColor: tone.bg }]}>
        {profile.label === 'conservative'
          ? 'Conservador'
          : profile.label === 'watch'
            ? 'Vigilar'
            : 'Evitar'}
      </Text>
      <Text style={styles.heroMeta}>
        Confianza {completeness}% · ejercicios {run.years_covered.join(', ')} · motor{' '}
        {run.engine_version}
      </Text>
    </View>
  );
}

function TabBar({ value, onChange }: { value: string; onChange: (key: string) => void }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.tabBar}>
      {REPORT_TABS.map((item) => (
        <Pressable
          key={item.key}
          onPress={() => onChange(item.key)}
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
  return <TabVerdict ctx={ctx} />;
}

const styles = StyleSheet.create({
  container: { padding: spacing.md, gap: spacing.md },
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
