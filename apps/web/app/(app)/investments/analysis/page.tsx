'use client';

import type { Route } from 'next';
import { useRouter } from 'next/navigation';

import { colors, fontSize, fontWeight, layout, spacing } from '@crisol/ui';

import { SecuritySearch } from '@/components/investment/security-search';

export default function InvestmentsAnalysisPage() {
  const router = useRouter();
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
        <h1 style={{ margin: 0, fontSize: fontSize.xxl, fontWeight: fontWeight.bold, color: colors.text }}>
          Análisis fundamental
        </h1>
        <p style={{ color: colors.textMuted, fontSize: fontSize.sm, marginTop: spacing.xs }}>
          Busca una empresa cotizada en EE.UU. y analiza sus 10-K de la SEC: forense contable,
          solvencia, calidad de caja y seguridad del dividendo.
        </p>
      </div>
      <SecuritySearch onSelect={(id) => router.push(`/investments/analysis/${id}` as Route)} />
    </div>
  );
}
