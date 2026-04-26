'use client';

import { useParams, useRouter } from 'next/navigation';

import { useImport } from '@finanzas/services';
import { colors, fontSize, spacing } from '@finanzas/ui';

import { ResultStep } from '@/components/imports/result-step';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export default function ImportDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id;

  const { data, isLoading, isError, error } = useImport(id);

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: spacing.lg }}>
      <header style={{ marginBottom: spacing.lg }}>
        <Button variant="ghost" onClick={() => router.push('/imports')}>
          ← Volver
        </Button>
        <h1
          style={{
            fontSize: fontSize.xl,
            color: colors.text,
            marginTop: spacing.sm,
            marginBottom: 0,
          }}
        >
          Detalle de importación
        </h1>
      </header>

      <Card style={{ padding: spacing.lg }}>
        {isLoading ? (
          <p>Cargando…</p>
        ) : isError ? (
          <p style={{ color: colors.danger }}>
            Error: {error instanceof Error ? error.message : 'desconocido'}
          </p>
        ) : data ? (
          <ResultStep job={data} onRestart={() => router.push('/imports/new')} />
        ) : (
          <p style={{ color: colors.textMuted }}>Job no encontrado.</p>
        )}
      </Card>
    </div>
  );
}
