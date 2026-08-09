'use client';

import { useCallback, useMemo } from 'react';
import { useParams, usePathname, useRouter, useSearchParams } from 'next/navigation';

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
import {
  colors,
  DEFAULT_REPORT_TAB,
  fontSize,
  layout,
  radius,
  REPORT_TABS,
  spacing,
} from '@crisol/ui';

import { AnalysisHero } from '@/components/investment/analysis-hero';
import { StaleRunNotice } from '@/components/investment/stale-run-notice';
import { buildCatalogIndex, buildMetricIndex, collectRunMetrics } from '@crisol/ui';
import { TabDividend } from '@/components/investment/tab-dividend';
import { TabEvolution } from '@/components/investment/tab-evolution';
import { TabForensic } from '@/components/investment/tab-forensic';
import { TabRatios } from '@/components/investment/tab-ratios';
import { TabStatements } from '@/components/investment/tab-statements';
import { TabValuation } from '@/components/investment/tab-valuation';
import { TabVerdict } from '@/components/investment/tab-verdict';
import { Card } from '@/components/ui/card';
import { ErrorState } from '@/components/ui/error-state';
import { SkeletonCardList } from '@/components/ui/skeleton';
import { TabPanel, Tabs, type TabItem } from '@/components/ui/tabs';

// La pestaña por defecto y la lista de ids viven en `@crisol/ui` desde
// PHASE-44.8: móvil enseña las mismas seis, en el mismo orden y con las mismas
// claves, así que un enlace significa lo mismo en los dos sitios.
const DEFAULT_TAB = DEFAULT_REPORT_TAB;

/** Sub-sección por defecto de cada pestaña. */
const DEFAULT_SUB: Record<string, string> = {
  estados: 'balance',
  ratios: 'liquidez',
  veredicto: 'dictamen',
};

const TAB_IDS = REPORT_TABS.map((t) => t.key);

export default function SecurityAnalysisPage() {
  const { securityId } = useParams<{ securityId: string }>();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const security = useSecurity(securityId);
  const statements = useStatements(securityId, 'latest');
  const latestRun = useLatestAnalysisRun(securityId);
  const metricCatalog = useMetricCatalog();
  const canonicalItems = useCanonicalItems();
  const ingest = useIngest();
  const run = useRunAnalysis();

  const rawTab = searchParams.get('tab') ?? DEFAULT_TAB;
  const tab = (TAB_IDS as readonly string[]).includes(rawTab) ? rawTab : DEFAULT_TAB;
  const sub = searchParams.get('sub') ?? DEFAULT_SUB[tab] ?? '';
  const view = searchParams.get('view') ?? 'amount';

  /**
   * La pestaña viaja en la URL como query param, no como segmento de ruta: así
   * recargar (F5) conserva dónde estabas, la URL se puede compartir, y cambiar
   * de pestaña no desmonta la página ni tira la caché del análisis.
   */
  const setParam = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(patch)) {
        if (value === null) next.delete(key);
        else next.set(key, value);
      }
      router.replace(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  const handleTabChange = useCallback(
    (key: string) => setParam({ tab: key, sub: DEFAULT_SUB[key] ?? null }),
    [setParam],
  );

  // El run mostrado es el persistido; si se acaba de reejecutar, el más reciente
  // es el de la mutación (la query aún no ha refrescado).
  const activeRun = run.data ?? latestRun.data;

  const catalogIndex = useMemo(
    () => buildCatalogIndex(metricCatalog.data?.items),
    [metricCatalog.data],
  );

  const metricIndex = useMemo(() => {
    if (!activeRun) return null;
    // La recolección vive en `@crisol/ui` (PHASE-44.8): olvidar un bloque no
    // falla, sólo deja sus filas como huecos indistinguibles de «no calculable».
    return buildMetricIndex(collectRunMetrics(activeRun), activeRun.years_covered);
  }, [activeRun]);

  const hasStatements = (statements.data?.length ?? 0) > 0;
  const sec = security.data;
  const loadingRun = latestRun.isLoading || security.isLoading;
  // 404 en `runs/latest` no es un error: es «todavía no se ha analizado».
  const noRunYet = !activeRun && !latestRun.isLoading;

  const tabs: TabItem[] = useMemo(() => {
    const flagCount = activeRun?.flags.length ?? 0;
    return [
      { key: 'estados', label: 'Estados' },
      { key: 'ratios', label: 'Ratios' },
      { key: 'evolucion', label: 'Evolución', badge: activeRun?.evolution.flags?.length },
      {
        key: 'forense',
        label: 'Forense',
        degraded: sec?.is_financial === true,
      },
      {
        key: 'dividendo',
        label: 'Dividendo',
        degraded: activeRun?.dividend_verdict === 'not_applicable',
      },
      { key: 'valoracion', label: 'Valoración' },
      { key: 'veredicto', label: 'Veredicto', badge: flagCount },
    ];
  }, [activeRun, sec]);

  return (
    <div
      style={{
        maxWidth: layout.pageWide,
        margin: '0 auto',
        padding: spacing.lg,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.lg,
      }}
    >
      <AnalysisHero
        security={sec}
        run={activeRun}
        onRerun={() => void run.mutateAsync({ securityId })}
        rerunning={run.isPending}
      />

      <StaleRunNotice
        runVersion={activeRun?.engine_version}
        engineVersion={metricCatalog.data?.engine_version}
        onRerun={() => void run.mutateAsync({ securityId })}
        rerunning={run.isPending}
      />

      {security.isError ? (
        <ErrorState
          title="No se pudo cargar el valor"
          onRetry={() => void security.refetch()}
          retrying={security.isFetching}
        />
      ) : null}

      {sec && !hasStatements ? (
        <Card
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.md,
            alignItems: 'flex-start',
          }}
        >
          <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
            Aún no hay estados financieros para {sec.ticker}. Descárgalos de EDGAR para poder
            analizarlos.
          </p>
          <button
            type="button"
            onClick={() => void ingest.mutateAsync({ securityId, filings_back: 5 })}
            disabled={ingest.isPending || !sec.analysis_available}
            style={primaryButton(ingest.isPending)}
          >
            {ingest.isPending ? 'Descargando 10-K…' : 'Descargar 10-K (EDGAR)'}
          </button>
          {!sec.analysis_available ? (
            <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
              {sec.analysis_reason ??
                'Este valor no se puede analizar: el motor necesita cuentas presentadas ante la SEC.'}
            </span>
          ) : null}
          {ingest.data?.status === 'failed' ? (
            <span style={{ color: colors.danger, fontSize: fontSize.sm }}>{ingest.data.error}</span>
          ) : null}
          {ingest.isError ? (
            <span style={{ color: colors.danger, fontSize: fontSize.sm }}>
              {formatApiError(ingest.error, 'No se pudo ingerir.')}
            </span>
          ) : null}
        </Card>
      ) : null}

      {hasStatements && noRunYet ? (
        <Card
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.md,
            alignItems: 'flex-start',
          }}
        >
          <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
            {statements.data?.length} ejercicios listos (
            {statements.data?.map((s) => s.fiscal_year).join(', ')}). Todavía no se ha ejecutado
            ningún análisis sobre ellos.
          </p>
          <button
            type="button"
            onClick={() => void run.mutateAsync({ securityId })}
            disabled={run.isPending}
            style={primaryButton(run.isPending)}
          >
            {run.isPending ? 'Analizando…' : 'Ejecutar análisis'}
          </button>
          {run.isError ? (
            <span style={{ color: colors.danger, fontSize: fontSize.sm }}>
              {formatApiError(run.error, 'No se pudo ejecutar el análisis.')}
            </span>
          ) : null}
        </Card>
      ) : null}

      {loadingRun && !activeRun ? <SkeletonCardList rows={3} /> : null}

      {activeRun && metricIndex ? (
        <>
          <Tabs
            items={tabs}
            value={tab}
            onChange={handleTabChange}
            label="Secciones del informe"
            idPrefix="analysis"
          />

          {!catalogIndex.ready ? (
            <p style={{ margin: 0, color: colors.textSubtle, fontSize: fontSize.xs }}>
              El catálogo de métricas no se ha podido cargar: las filas salen con su clave
              técnica y sin unidad.
            </p>
          ) : null}

          <TabPanel idPrefix="analysis" tabKey="estados" active={tab === 'estados'}>
            <TabStatements
              run={activeRun}
              statements={statements.data}
              items={canonicalItems.data}
              currency={sec?.currency ?? 'USD'}
              sub={sub}
              onSubChange={(key) => setParam({ sub: key })}
              view={view === 'weight' || view === 'delta' ? view : 'amount'}
              onViewChange={(next) => setParam({ view: next })}
            />
          </TabPanel>

          <TabPanel idPrefix="analysis" tabKey="ratios" active={tab === 'ratios'}>
            <TabRatios
              run={activeRun}
              index={metricIndex}
              catalog={catalogIndex}
              sub={sub}
              onSubChange={(key) => setParam({ sub: key })}
            />
          </TabPanel>

          <TabPanel idPrefix="analysis" tabKey="evolucion" active={tab === 'evolucion'}>
            <TabEvolution run={activeRun} index={metricIndex} catalog={catalogIndex} />
          </TabPanel>

          <TabPanel idPrefix="analysis" tabKey="forense" active={tab === 'forense'}>
            <TabForensic
              run={activeRun}
              index={metricIndex}
              catalog={catalogIndex}
              security={sec}
            />
          </TabPanel>

          <TabPanel idPrefix="analysis" tabKey="dividendo" active={tab === 'dividendo'}>
            <TabDividend
              run={activeRun}
              index={metricIndex}
              catalog={catalogIndex}
              security={sec}
            />
          </TabPanel>

          <TabPanel idPrefix="analysis" tabKey="valoracion" active={tab === 'valoracion'}>
            <TabValuation securityId={securityId} security={sec} catalog={catalogIndex} />
          </TabPanel>

          <TabPanel idPrefix="analysis" tabKey="veredicto" active={tab === 'veredicto'}>
            <TabVerdict
              run={activeRun}
              catalog={catalogIndex}
              statements={statements.data}
              items={canonicalItems.data}
              sub={sub}
              onSubChange={(key) => setParam({ sub: key })}
            />
          </TabPanel>
        </>
      ) : null}
    </div>
  );
}

function primaryButton(disabled: boolean): React.CSSProperties {
  return {
    backgroundColor: colors.primary,
    color: colors.onPrimary,
    border: 'none',
    borderRadius: radius.md,
    padding: `${spacing.sm}px ${spacing.lg}px`,
    fontSize: fontSize.sm,
    fontWeight: 600,
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.6 : 1,
  };
}
