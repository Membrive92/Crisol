'use client';

import { Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

import { colors, fontSize, fontWeight, layout, radius, REPORT_GUIDE, spacing } from '@crisol/ui';

import { Card, CardTitle } from '@/components/ui/card';
import { guideBackHref } from '@/lib/report-links';

/**
 * «Cómo leer este informe» (PHASE-44.24.E).
 *
 * Sin contenido propio: renderiza `REPORT_GUIDE` de `@crisol/ui`, que a su vez
 * importa las etiquetas de donde se PINTAN (`bandLabel`, `EVIDENCE_LABEL`, el
 * registro de marcas). Escribir aquí los estados a mano sería la forma exacta
 * en que caducó la leyenda del forense: una guía que describe un vocabulario
 * que la pantalla ya no usa, sin que nada avise.
 */
/**
 * «← Volver al informe», leyendo `?back=` de la URL.
 *
 * Va en su propio componente y bajo `<Suspense>`: `useSearchParams` en una
 * página que Next prerenderiza exige un límite de suspensión, y esta ruta es
 * estática. CI hace `next build`; un aviso ahí se convierte en un fallo.
 */
function BackToReport() {
  const searchParams = useSearchParams();
  // La vuelta al informe del que se viene. Sin ella, esta página era un
  // callejón: «Análisis» en la barra lleva al buscador vacío.
  const back = guideBackHref(searchParams.get('back'));
  if (!back) return null;
  return (
    <Link
      href={back as never}
      style={{
        display: 'inline-block',
        marginBottom: spacing.sm,
        color: colors.primary,
        fontSize: fontSize.sm,
        textDecoration: 'none',
      }}
    >
      ← Volver al informe
    </Link>
  );
}

export default function AnalysisGuidePage() {
  return (
    <div
      style={{
        maxWidth: layout.pageNarrow,
        margin: '0 auto',
        padding: spacing.lg,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.lg,
      }}
    >
      <div>
        <Suspense fallback={null}>
          <BackToReport />
        </Suspense>
        <h1
          style={{
            margin: 0,
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: colors.text,
          }}
        >
          Cómo leer este informe
        </h1>
        <p style={{ color: colors.textMuted, fontSize: fontSize.sm, marginTop: spacing.xs }}>
          El informe demuestra lo que afirma: cada color sale de comparar un número con un corte
          publicado, y cada hueco dice por qué está vacío. Esto es el vocabulario.
        </p>
      </div>

      {REPORT_GUIDE.map((section) => (
        <Card key={section.key}>
          <CardTitle size="sm">{section.title}</CardTitle>
          <p
            style={{
              margin: `${spacing.sm}px 0 0`,
              color: colors.textMuted,
              fontSize: fontSize.sm,
              lineHeight: 1.6,
            }}
          >
            {section.intro}
          </p>
          <dl
            style={{
              margin: `${spacing.md}px 0 0`,
              display: 'grid',
              gridTemplateColumns: 'minmax(min(40%, 160px), auto) 1fr',
              columnGap: spacing.lg,
              rowGap: spacing.sm,
            }}
          >
            {section.entries.map((entry) => (
              <div key={entry.term} style={{ display: 'contents' }}>
                <dt
                  style={{
                    color: colors.text,
                    fontSize: fontSize.sm,
                    fontWeight: fontWeight.semibold,
                  }}
                >
                  <span
                    style={{
                      display: 'inline-block',
                      minWidth: 24,
                      textAlign: 'center',
                      backgroundColor: colors.surface,
                      borderRadius: radius.sm,
                      padding: `0 ${spacing.xs}px`,
                    }}
                  >
                    {entry.term}
                  </span>
                </dt>
                <dd
                  style={{
                    margin: 0,
                    color: colors.textMuted,
                    fontSize: fontSize.sm,
                    lineHeight: 1.6,
                  }}
                >
                  {entry.meaning}
                </dd>
              </div>
            ))}
          </dl>
        </Card>
      ))}
    </div>
  );
}
