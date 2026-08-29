'use client';

import Link from 'next/link';

import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useParams, usePathname, useRouter, useSearchParams } from 'next/navigation';

import {
  formatApiError,
  useCanonicalItems,
  useHelpCatalog,
  useIngest,
  useAnalysisRun,
  useAnalysisRuns,
  useLatestAnalysisRun,
  useRunComparison,
  useMetricCatalog,
  useRunAnalysis,
  useSecurity,
  useStatements,
} from '@crisol/services';
import {
  colors,
  DEFAULT_REPORT_TAB,
  fontSize,
  fontWeight,
  layout,
  radius,
  REPORT_SCOPE,
  REPORT_TABS,
  spacing,
} from '@crisol/ui';

import { AnalysisHero } from '@/components/investment/analysis-hero';
import type { AnalysisRun } from '@crisol/types';

import { InlineNotice } from '@/components/investment/degraded-panel';
import { RunComparison } from '@/components/investment/run-comparison';
import { RunPicker } from '@/components/investment/run-picker';
import { StaleRunNotice } from '@/components/investment/stale-run-notice';
import { guideHrefFor, printHrefFor, reportHrefFor, signalHrefFor } from '@/lib/report-links';
import {
  buildCatalogIndex,
  buildMetricIndex,
  buildScoreHelpIndex,
  collectRunMetrics,
} from '@crisol/ui';
import { TabDividend } from '@/components/investment/tab-dividend';
import { TabEvolution } from '@/components/investment/tab-evolution';
import { TabForensic } from '@/components/investment/tab-forensic';
import { TabRatios } from '@/components/investment/tab-ratios';
import { TabStatements } from '@/components/investment/tab-statements';
import { TabValuation } from '@/components/investment/tab-valuation';
import { TabVerdict } from '@/components/investment/tab-verdict';
import { Button } from '@/components/ui/button';
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
  const helpCatalog = useHelpCatalog();
  const ingest = useIngest();
  const run = useRunAnalysis();
  const runs = useAnalysisRuns(securityId);

  /**
   * Modo dictamen imprimible (PHASE-44.24.G).
   *
   * Fuerza la pestaña de Veredicto y esconde la navegación: lo que se imprime
   * es el dictamen con su alcance y sus versiones, no el informe navegable.
   */
  const printMode = searchParams.get('print') === '1';

  const rawTab = searchParams.get('tab') ?? DEFAULT_TAB;
  const requestedTab = (TAB_IDS as readonly string[]).includes(rawTab) ? rawTab : DEFAULT_TAB;
  // En modo impresión manda el veredicto, venga lo que venga en la URL:
  // imprimir la pestaña de Estados no es un dictamen.
  const tab = printMode ? 'veredicto' : requestedTab;
  const sub = printMode ? 'dictamen' : (searchParams.get('sub') ?? DEFAULT_SUB[tab] ?? '');
  const view = searchParams.get('view') ?? 'amount';
  const highlightKey = searchParams.get('metric') ?? undefined;
  /** El análisis seleccionado en el histórico, y contra cuál se compara. */
  const selectedRunId = searchParams.get('run');
  const compareBaseId = searchParams.get('compare');

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

  // `metric: null` NO es decorativo: `setParam` parte de los params actuales y
  // conserva por diseño lo que no se toca, así que sin borrarlo el resaltado
  // sobreviviría al cambio de pestaña y reaparecería en cada visita — lo
  // contrario de lo que un resaltado significa (PHASE-44.24.C.4).
  const handleTabChange = useCallback(
    (key: string) => setParam({ tab: key, sub: DEFAULT_SUB[key] ?? null, metric: null }),
    [setParam],
  );

  const handleSubChange = useCallback(
    (key: string) => setParam({ sub: key, metric: null }),
    [setParam],
  );

  /**
   * Reejecuta y borra la selección del histórico.
   *
   * Sin el borrado, el análisis recién hecho quedaría detrás del que el usuario
   * tenía seleccionado y parecería que el botón no ha hecho nada.
   */
  const rerun = useCallback(async () => {
    try {
      await run.mutateAsync({ securityId });
    } catch {
      // El error ya vive en `run.error` y se pinta en el hero. Sin este
      // `catch`, `void rerun()` deja el rechazo suelto y acaba en
      // `unhandledrejection`.
      return;
    }
    setParam({ run: null, compare: null });
  }, [run, securityId, setParam]);

  /**
   * El enlace al dictamen imprimible, CONSERVANDO el análisis seleccionado.
   *
   * Se compone aquí porque ésta es la única pieza que lee la URL, igual que
   * `hrefForSignal`.
   */
  const printHref = useMemo(
    () => printHrefFor(pathname, searchParams.toString()),
    [pathname, searchParams],
  );
  const guideHref = useMemo(
    () => guideHrefFor(pathname, searchParams.toString()),
    [pathname, searchParams],
  );
  const reportHref = useMemo(
    () => reportHrefFor(pathname, searchParams.toString()),
    [pathname, searchParams],
  );

  /**
   * A dónde lleva una señal del veredicto.
   *
   * Se compone AQUÍ porque ésta es la única pieza que lee la URL: un hook de
   * `next/navigation` dentro de `SignalTable` haría que `useRouter` lanzara en
   * los tests, que la montan sin router.
   */
  const hrefForSignal = useCallback(
    (signal: { key: string }) =>
      signalHrefFor(pathname, searchParams.toString(), { tab, sub }, signal.key),
    [pathname, searchParams, sub, tab],
  );

  const selectedRun = useAnalysisRun(selectedRunId);
  const comparison = useRunComparison(
    securityId,
    compareBaseId,
    selectedRunId,
    tab === 'veredicto' && sub === 'historia',
  );

  /**
   * El run mostrado.
   *
   * La precedencia NO es `run.data ?? selectedRun.data ?? latestRun.data`:
   * `useMutation.data` persiste mientras la página esté montada, así que con
   * ese orden el selector no podría enseñar nunca un run viejo después de
   * reejecutar. Que «un rerun recién hecho gane» se consigue BORRANDO la
   * selección en el handler del rerun, no con el orden.
   */
  const activeRun = selectedRunId ? selectedRun.data : (run.data ?? latestRun.data);

  const catalogIndex = useMemo(
    () => buildCatalogIndex(metricCatalog.data?.items),
    [metricCatalog.data],
  );

  // Las fichas de score son estáticas y viven en su propia key: si no han
  // cargado, la tarjeta cae a la clave cruda del motor y lo dice, en vez de
  // dejar el hueco en blanco (PHASE-44.24.A).
  const scoreHelp = useMemo(() => buildScoreHelpIndex(helpCatalog.data), [helpCatalog.data]);

  const metricIndex = useMemo(() => {
    if (!activeRun) return null;
    // La recolección vive en `@crisol/ui` (PHASE-44.8): olvidar un bloque no
    // falla, sólo deja sus filas como huecos indistinguibles de «no calculable».
    return buildMetricIndex(collectRunMetrics(activeRun), activeRun.years_covered);
  }, [activeRun]);

  const hasStatements = (statements.data?.length ?? 0) > 0;
  const sec = security.data;

  // Con `?run=` en la URL, `activeRun` está vacío mientras esa query carga, y
  // `latestRun` ya resolvió hace rato. Sin estos dos estados, elegir un
  // análisis del histórico pintaba «todavía no se ha ejecutado ningún
  // análisis» —falso— y desmontaba el propio selector con el que se acababa de
  // pulsar (PHASE-44.24.F, revisión adversarial).
  const selectedPending = Boolean(selectedRunId) && selectedRun.isLoading;
  const selectedMissing = Boolean(selectedRunId) && selectedRun.isError;

  const loadingRun = latestRun.isLoading || security.isLoading || selectedPending;
  // 404 en `runs/latest` no es un error: es «todavía no se ha analizado». Pero
  // un 404 del run SELECCIONADO es otra cosa —ese id no existe o no es tuyo— y
  // tiene su propio aviso, con salida.
  const noRunYet = !activeRun && !latestRun.isLoading && !selectedPending && !selectedMissing;

  // En modo dictamen, el diálogo de impresión se abre solo cuando el informe
  // está en pantalla — una vez. Sin esto la pestaña nueva se quedaba quieta y
  // el usuario no sabía qué hacer con ella.
  // «Cargado» es el INFORME, no sólo el run: catálogo de métricas, fichas y
  // partidas son queries aparte. Con sólo el run, un backend en frío imprimía
  // el aviso «el catálogo no se ha podido cargar» y las filas con su clave
  // técnica — en un documento que existe para archivarse.
  const reportSettled =
    !metricCatalog.isLoading &&
    !helpCatalog.isLoading &&
    !canonicalItems.isLoading &&
    !statements.isLoading;
  const printedOnce = useRef(false);
  useEffect(() => {
    if (!printMode || printedOnce.current || !activeRun || loadingRun || !reportSettled) return;
    printedOnce.current = true;
    const timer = window.setTimeout(() => window.print(), 400);
    return () => window.clearTimeout(timer);
  }, [printMode, activeRun, loadingRun, reportSettled]);

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
        onRerun={() => void rerun()}
        rerunning={run.isPending}
        printHref={printHref}
        guideHref={guideHref}
        {...(run.isError
          ? { rerunError: formatApiError(run.error, 'No se pudo ejecutar el análisis.') }
          : {})}
      />

      {/* Un id de análisis que no existe, o que es de otro usuario. Sin esto la
          pantalla se quedaba en un estado vacío permanente sin decir por qué ni
          ofrecer salida. */}
      {selectedMissing ? (
        <InlineNotice>
          El análisis que pide la dirección no existe o no es tuyo.{' '}
          <button
            type="button"
            onClick={() => setParam({ run: null, compare: null })}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              color: colors.primary,
              cursor: 'pointer',
              fontSize: 'inherit',
              textDecoration: 'underline',
            }}
          >
            Volver al último
          </button>
          .
        </InlineNotice>
      ) : null}

      <StaleRunNotice
        runVersion={activeRun?.engine_version}
        engineVersion={metricCatalog.data?.engine_version}
        onRerun={() => void rerun()}
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
          <Button
            variant="primary"
            onClick={() => void ingest.mutateAsync({ securityId, filings_back: 5 })}
            disabled={ingest.isPending || !sec.analysis_available}
          >
            {ingest.isPending ? 'Descargando 10-K…' : 'Descargar 10-K (EDGAR)'}
          </Button>
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
          <Button variant="primary" onClick={() => void rerun()} disabled={run.isPending}>
            {run.isPending ? 'Analizando…' : 'Ejecutar análisis'}
          </Button>
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
          {printMode ? (
            <>
              <PrintToolbar reportHref={reportHref} />
              <PrintHeader run={activeRun} ticker={sec?.ticker ?? '—'} name={sec?.name ?? ''} />
            </>
          ) : null}

          {/* En modo dictamen la navegación NO se renderiza. Esconderla sólo
              con `@media print` la dejaba viva en pantalla: se veían pestañas
              que al pulsarlas escribían un `tab` en la URL que `printMode`
              descarta, así que la barra decía una cosa y la página enseñaba
              otra. */}
          {printMode ? null : (
            <Tabs
              items={tabs}
              value={tab}
              onChange={handleTabChange}
              label="Secciones del informe"
              idPrefix="analysis"
            />
          )}

          {!catalogIndex.ready ? (
            <p
              data-print="hide"
              style={{ margin: 0, color: colors.textSubtle, fontSize: fontSize.xs }}
            >
              El catálogo de métricas no se ha podido cargar: las filas salen con su clave técnica y
              sin unidad.
            </p>
          ) : null}

          <TabPanel idPrefix="analysis" tabKey="estados" active={tab === 'estados'}>
            <TabStatements
              run={activeRun}
              statements={statements.data}
              items={canonicalItems.data}
              currency={sec?.currency ?? 'USD'}
              sub={sub}
              onSubChange={handleSubChange}
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
              onSubChange={handleSubChange}
              highlightKey={highlightKey}
            />
          </TabPanel>

          <TabPanel idPrefix="analysis" tabKey="evolucion" active={tab === 'evolucion'}>
            <TabEvolution
              run={activeRun}
              index={metricIndex}
              catalog={catalogIndex}
              highlightKey={highlightKey}
            />
          </TabPanel>

          <TabPanel idPrefix="analysis" tabKey="forense" active={tab === 'forense'}>
            <TabForensic
              run={activeRun}
              index={metricIndex}
              catalog={catalogIndex}
              security={sec}
              help={scoreHelp}
              highlightKey={highlightKey}
            />
          </TabPanel>

          <TabPanel idPrefix="analysis" tabKey="dividendo" active={tab === 'dividendo'}>
            <TabDividend
              run={activeRun}
              index={metricIndex}
              catalog={catalogIndex}
              security={sec}
              highlightKey={highlightKey}
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
              help={scoreHelp}
              // En el dictamen las señales se pintan como texto: `tab` está
              // forzado, así que un enlace cambiaría la URL sin mover nada.
              hrefFor={printMode ? undefined : hrefForSignal}
              sub={sub}
              onSubChange={handleSubChange}
              printMode={printMode}
              history={
                <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
                  <RunPicker
                    runs={runs.data?.items ?? []}
                    selectedId={selectedRunId}
                    compareId={compareBaseId}
                    onSelect={(id) => setParam({ run: id })}
                    onCompare={(id) => setParam({ compare: id })}
                  />
                  <RunComparison
                    diff={comparison.data}
                    loading={comparison.isLoading}
                    reason={
                      comparison.isError
                        ? formatApiError(
                            comparison.error,
                            'Hace falta más de un análisis de este valor. Vuelve a analizarlo cuando publique un ejercicio nuevo y aquí saldrá qué se ha movido.',
                          )
                        : null
                    }
                  />
                </div>
              }
            />
          </TabPanel>
        </>
      ) : null}
    </div>
  );
}
/**
 * La barra del modo dictamen (PHASE-44.24.G).
 *
 * «Dictamen imprimible» abría una pestaña con el informe sin pestañas y NO
 * pasaba nada más: el usuario esperaba el diálogo de impresión y veía la misma
 * página con una cabecera distinta. Ahora se dice qué es esto y hay un botón;
 * y el diálogo se abre solo cuando el informe ha terminado de cargar (el
 * `useEffect` de la página), una sola vez.
 */
function PrintToolbar({ reportHref }: { reportHref: string }) {
  return (
    <div
      data-print="hide"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.md,
        flexWrap: 'wrap',
        padding: `${spacing.sm}px ${spacing.md}px`,
        borderRadius: radius.sm,
        backgroundColor: colors.surfaceMuted,
        color: colors.textMuted,
        fontSize: fontSize.sm,
      }}
    >
      <span>
        Vista de impresión: sólo el veredicto, con las versiones del motor en la cabecera.
      </span>
      <Button variant="primary" onClick={() => window.print()} style={{ marginLeft: 'auto' }}>
        Imprimir
      </Button>
      {/* No `window.close()`: sólo cierra pestañas abiertas por script, y el
          enlace del hero lleva `noreferrer` (sin opener). En Firefox el botón
          quedaba mudo; con la URL pegada a mano, en todos. Un enlace de vuelta
          funciona siempre. */}
      <Link
        href={reportHref as never}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          border: `1px solid ${colors.border}`,
          borderRadius: radius.md,
          color: colors.text,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          padding: `${spacing.sm}px ${spacing.md}px`,
          textDecoration: 'none',
        }}
      >
        Volver al informe
      </Link>
    </div>
  );
}

/**
 * La cabecera del dictamen impreso (PHASE-44.24.G).
 *
 * Un papel sin las tres versiones y la fecha no es auditable: el mismo valor
 * analizado con otra calibración da otros colores, y sin eso escrito nadie
 * puede reproducir lo que tiene delante.
 */
function PrintHeader({ run, ticker, name }: { run: AnalysisRun; ticker: string; name: string }) {
  return (
    <div
      data-print="block"
      style={{
        borderBottom: `2px solid ${colors.border}`,
        paddingBottom: spacing.sm,
        marginBottom: spacing.md,
      }}
    >
      <h1 style={{ margin: 0, fontSize: fontSize.lg, color: colors.text }}>
        Dictamen · {ticker} {name ? `· ${name}` : ''}
      </h1>
      <p style={{ margin: `${spacing.xs}px 0 0`, color: colors.textMuted, fontSize: fontSize.xs }}>
        Análisis {run.id} · {new Date(run.run_date).toLocaleDateString('es-ES')} · motor{' '}
        {run.engine_version} · umbrales {run.thresholds_version} · ejercicios{' '}
        {run.years_covered.join(', ')}
      </p>
      <p style={{ margin: `${spacing.xs}px 0 0`, color: colors.textMuted, fontSize: fontSize.xs }}>
        {REPORT_SCOPE.map((entry) => entry.term).join(' · ')} quedan FUERA de este dictamen.
      </p>
    </div>
  );
}
