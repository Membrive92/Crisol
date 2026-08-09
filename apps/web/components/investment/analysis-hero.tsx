'use client';

import { colors, fontSize, fontWeight, questionEvidence, radius, spacing } from '@crisol/ui';
import type { AnalysisRun, DividendVerdict, SafetyLabel, Security } from '@crisol/types';

import { Card } from '@/components/ui/card';

import { BandDot } from './band-chip';

const SAFETY: Record<SafetyLabel, { label: string; fg: string; bg: string }> = {
  conservative: { label: 'Conservador', fg: colors.success, bg: colors.successSoft },
  watch: { label: 'Vigilar', fg: colors.warning, bg: colors.warningSoft },
  avoid: { label: 'Evitar', fg: colors.danger, bg: colors.dangerSoft },
};

const DIVIDEND: Record<DividendVerdict, string> = {
  healthy: 'Dividendo sano',
  caution: 'Dividendo a vigilar',
  stressed: 'Dividendo en riesgo',
  not_applicable: 'Sin dividendo relevante',
};

export interface AnalysisHeroProps {
  security: Security | undefined;
  run: AnalysisRun | undefined;
  onRerun: () => void;
  rerunning: boolean;
}

/**
 * El titular del informe: identidad, perfil, las cuatro preguntas de un vistazo
 * y la confianza. Vive por encima de la barra de pestañas y no cambia al navegar
 * — el veredicto se ve siempre, y además tiene su pestaña propia con el porqué.
 */
export function AnalysisHero({ security, run, onRerun, rerunning }: AnalysisHeroProps) {
  const safety = run ? SAFETY[run.verdict.safety_profile.label] : null;

  return (
    <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: spacing.md, flexWrap: 'wrap' }}>
        <h1
          style={{
            margin: 0,
            fontSize: fontSize.xl,
            fontWeight: fontWeight.bold,
            color: colors.text,
          }}
        >
          {security?.ticker ?? '—'}
        </h1>
        <span style={{ color: colors.textMuted, fontSize: fontSize.md }}>
          {security?.name ?? ''}
        </span>
        {security ? <Badge>{security.sector.replace(/_/g, ' ')}</Badge> : null}
        {security?.is_reit ? <Badge>Socimi</Badge> : null}
        {security?.is_financial ? <Badge>Financiera</Badge> : null}
      </div>

      {run && safety ? (
        <>
          <div
            style={{
              display: 'flex',
              gap: spacing.lg,
              flexWrap: 'wrap',
              alignItems: 'center',
            }}
          >
            <span
              style={{
                color: safety.fg,
                backgroundColor: safety.bg,
                borderRadius: radius.sm,
                padding: `${spacing.xs}px ${spacing.md}px`,
                fontSize: fontSize.md,
                fontWeight: fontWeight.bold,
              }}
            >
              {safety.label}
            </span>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 220px), 1fr))',
                gap: `${spacing.xs}px ${spacing.lg}px`,
                flex: 1,
                minWidth: 220,
              }}
            >
              {run.verdict.questions.map((question) => {
                // Sin ninguna señal evaluada, un verde es ausencia de prueba y
                // no salud: se pinta gris y se dice. Un run viejo, que no
                // registraba el desglose, tampoco puede presumir de verde.
                const evidence = questionEvidence(question);
                const noEvidence = evidence !== 'evaluated';
                return (
                  <span
                    key={question.key}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: spacing.sm,
                      color: colors.textMuted,
                      fontSize: fontSize.sm,
                    }}
                  >
                    <BandDot
                      band={noEvidence ? null : question.verdict}
                      title={
                        evidence === 'no-evidence'
                          ? 'sin evidencia evaluable'
                          : evidence === 'not-recorded'
                            ? 'análisis de un motor anterior: no registró qué señales se evaluaron'
                            : undefined
                      }
                    />
                    {question.question}
                  </span>
                );
              })}
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: spacing.md,
              flexWrap: 'wrap',
              paddingTop: spacing.sm,
              borderTop: `1px solid ${colors.border}`,
              color: colors.textMuted,
              fontSize: fontSize.xs,
            }}
          >
            <span>{DIVIDEND[run.verdict.dividend_verdict]}</span>
            <span>
              · Confianza{' '}
              <strong style={{ color: colors.text }}>
                {Math.round(Number(run.data_completeness.value) * 100)} %
              </strong>
            </span>
            <span>· Ejercicios {run.years_covered.join(', ')}</span>
            <span>· Análisis del {new Date(run.run_date).toLocaleDateString('es-ES')}</span>
            <button
              type="button"
              onClick={onRerun}
              disabled={rerunning}
              style={{
                marginLeft: 'auto',
                background: 'none',
                border: `1px solid ${colors.border}`,
                borderRadius: radius.sm,
                color: colors.textMuted,
                fontSize: fontSize.xs,
                padding: `${spacing.xs}px ${spacing.md}px`,
                cursor: rerunning ? 'default' : 'pointer',
                opacity: rerunning ? 0.6 : 1,
              }}
            >
              {rerunning ? 'Analizando…' : 'Volver a analizar'}
            </button>
          </div>
        </>
      ) : null}
    </Card>
  );
}

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
