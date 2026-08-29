'use client';

import Link from 'next/link';

import {
  colors,
  DIVIDEND,
  fontSize,
  fontWeight,
  questionEvidence,
  radius,
  SAFETY,
  spacing,
  layout,
} from '@crisol/ui';
import type { AnalysisRun, Security } from '@crisol/types';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

import { BandDot } from './band-chip';

// PHASE-44.24.E — `SAFETY` y `DIVIDEND` viven en `@crisol/ui`: estaban
// duplicadas aquí y en `tab-verdict.tsx`, y móvil las necesita idénticas.

export interface AnalysisHeroProps {
  security: Security | undefined;
  run: AnalysisRun | undefined;
  onRerun: () => void;
  rerunning: boolean;
  /**
   * A dónde lleva «Dictamen imprimible».
   *
   * Lo compone la PÁGINA, que es la única pieza que lee la URL: un
   * `href="?print=1"` escrito aquí es una referencia relativa que sustituye la
   * query ENTERA (RFC 3986 §5.3), así que perdía el `?run=` y se imprimía el
   * análisis más reciente en vez del que estabas mirando — en un documento que
   * existe para archivarse.
   *
   * OBLIGATORIA a propósito: con un valor por defecto, montar el hero sin
   * pasarla reintroduce el defecto en silencio. Así lo caza el compilador.
   */
  printHref: string;
  /**
   * A dónde lleva «Cómo leer este informe», con la vuelta dentro.
   *
   * Obligatoria por el mismo motivo que `printHref`: un literal aquí perdería
   * de dónde se viene, y la guía era un callejón sin salida.
   */
  guideHref: string;
  /**
   * Por qué falló el último re-análisis, si falló.
   *
   * Vivía sólo en la tarjeta de «aún no se ha analizado», que por definición no
   * está en pantalla cuando ya hay informe — que es justo cuando se pulsa
   * «Volver a analizar».
   */
  rerunError?: string | undefined;
}

/**
 * El titular del informe: identidad, perfil, las cuatro preguntas de un vistazo
 * y la confianza. Vive por encima de la barra de pestañas y no cambia al navegar
 * — el veredicto se ve siempre, y además tiene su pestaña propia con el porqué.
 */
export function AnalysisHero({
  security,
  run,
  onRerun,
  rerunning,
  printHref,
  guideHref,
  rerunError,
}: AnalysisHeroProps) {
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
                // Cuatro preguntas, cuatro columnas como MÁXIMO: con
                // `auto-fit` a secas, en un monitor de 2.400 px cada pregunta
                // se llevaba ~575 px y quedaban 300 de aire entre punto y
                // texto. `minmax(…, 320px)` acota cada columna y el grid deja
                // de crecer con la pantalla.
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 220px), 320px))',
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

          {/* El titular lo compone el SERVIDOR (PHASE-44.24.B): determinista y
              con goldens, para que la primera frase que se lee del informe y la
              del dictamen impreso no puedan discrepar. */}
          {run.report?.headline ? (
            <p
              style={{
                margin: 0,
                maxWidth: layout.prose,
                color: colors.text,
                fontSize: fontSize.sm,
                lineHeight: 1.5,
              }}
            >
              {run.report.headline}
            </p>
          ) : null}

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
            {/* La guía del vocabulario (PHASE-44.24.E). Vive en su propia ruta y
                no en un tooltip: son seis bloques y se consulta, no se ojea. */}
            <Link
              data-print="hide"
              href={guideHref as never}
              style={{ color: colors.primary, textDecoration: 'none' }}
            >
              · Cómo leer este informe
            </Link>
            {/* Las dos acciones van JUNTAS: sueltas, «Volver a analizar» se
                quedaba a la derecha y «Dictamen imprimible» caía solo a la
                línea siguiente, a la izquierda. */}
            <span
              data-print="hide"
              style={{ display: 'flex', gap: spacing.sm, marginLeft: 'auto', flexWrap: 'wrap' }}
            >
              <Button
                variant="ghost"
                onClick={onRerun}
                disabled={rerunning}
                style={{ fontSize: fontSize.xs, padding: `${spacing.xs}px ${spacing.md}px` }}
              >
                {rerunning ? 'Analizando…' : 'Volver a analizar'}
              </Button>
              {/* El dictamen imprimible (PHASE-44.24.G): fuerza el veredicto y
                  esconde la navegación. Se abre en una pestaña propia para no
                  perder dónde estabas. Es un enlace y no un botón porque abre
                  una URL; se viste como el `ghost` para no parecer otra cosa. */}
              <a
                href={printHref}
                target="_blank"
                rel="noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  border: `1px solid ${colors.border}`,
                  borderRadius: radius.md,
                  color: colors.text,
                  fontSize: fontSize.xs,
                  fontWeight: fontWeight.semibold,
                  padding: `${spacing.xs}px ${spacing.md}px`,
                  textDecoration: 'none',
                }}
              >
                Dictamen imprimible
              </a>
            </span>
          </div>

          {rerunError ? (
            <p
              data-print="hide"
              style={{ margin: 0, color: colors.danger, fontSize: fontSize.sm, lineHeight: 1.5 }}
            >
              {rerunError}
            </p>
          ) : null}
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
