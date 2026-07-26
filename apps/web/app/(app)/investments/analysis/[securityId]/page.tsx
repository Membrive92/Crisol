'use client';

import { useParams } from 'next/navigation';

import {
  formatApiError,
  useIngest,
  useRunAnalysis,
  useSecurity,
  useStatements,
} from '@crisol/services';
import { colors, fontSize, fontWeight, formatAmount, layout, radius, spacing } from '@crisol/ui';

import { AnalysisReport } from '@/components/investment/analysis-report';
import { Card } from '@/components/ui/card';

function Badge({ children }: { children: string }) {
  return (
    <span
      style={{
        backgroundColor: colors.primarySoft,
        color: colors.primary,
        borderRadius: radius.sm,
        padding: `2px ${spacing.sm}px`,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
      }}
    >
      {children}
    </span>
  );
}

export default function SecurityAnalysisPage() {
  const { securityId } = useParams<{ securityId: string }>();
  const security = useSecurity(securityId);
  const statements = useStatements(securityId, 'latest');
  const ingest = useIngest();
  const run = useRunAnalysis();

  const hasStatements = (statements.data?.length ?? 0) > 0;
  const sec = security.data;

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
      {sec ? (
        <div style={{ display: 'flex', alignItems: 'baseline', gap: spacing.md, flexWrap: 'wrap' }}>
          <h1 style={{ margin: 0, fontSize: fontSize.xl, fontWeight: fontWeight.bold, color: colors.text }}>
            {sec.ticker}
          </h1>
          <span style={{ color: colors.textMuted, fontSize: fontSize.md }}>{sec.name}</span>
          <Badge>{sec.sector.replace(/_/g, ' ')}</Badge>
          {sec.is_reit ? <Badge>REIT</Badge> : null}
          {sec.is_financial ? <Badge>Financiera</Badge> : null}
        </div>
      ) : (
        <p style={{ color: colors.textMuted }}>Cargando valor…</p>
      )}

      {sec && !hasStatements ? (
        <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.md, alignItems: 'flex-start' }}>
          <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
            Aún no hay estados financieros ingeridos para {sec.ticker}. Descárgalos de EDGAR para
            poder analizarlos.
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
              Este valor no tiene CIK (no es un emisor US); el análisis no está disponible todavía.
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

      {hasStatements && !run.data ? (
        <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.md, alignItems: 'flex-start' }}>
          <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
            {statements.data?.length} ejercicios ingeridos (
            {statements.data?.map((s) => s.fiscal_year).join(', ')}). Último ingreso:{' '}
            {formatAmount(statements.data?.at(-1)?.revenue ?? '0', sec?.currency ?? 'USD')}.
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

      {run.data ? <AnalysisReport run={run.data} /> : null}
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
