'use client';

import Link from 'next/link';
import type { Route } from 'next';

import type { ModuleDashboardSummary, ModuleVerdict } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@crisol/ui';

import { Card } from '@/components/ui/card';

export interface ModuleCardProps {
  /** Nombre del módulo (p. ej. "Finanzas Domésticas"). */
  label: string;
  /** Emoji identificativo del módulo. */
  emoji: string;
  summary: ModuleDashboardSummary | undefined;
  isLoading: boolean;
}

const VERDICT_LABEL: Record<ModuleVerdict, string> = {
  healthy: 'saludable',
  caution: 'atención',
  stressed: 'en tensión',
  neutral: '—',
};

const VERDICT_COLOR: Record<ModuleVerdict, string> = {
  healthy: colors.success,
  caution: colors.warning,
  stressed: colors.danger,
  neutral: colors.textMuted,
};

/**
 * PHASE-43.4 (ADR-0006) — tarjeta de un módulo en el dashboard:
 * `veredicto + un número + un link`. NO es un mini-módulo — el detalle vive
 * en `summary.link`. Formato canónico:
 * `💳 Deuda  −19.500 €  esfuerzo 10,3 % · saludable  →`.
 */
export function ModuleCard({ label, emoji, summary, isLoading }: ModuleCardProps) {
  const verdict = summary?.verdict ?? 'neutral';
  const value =
    summary != null
      ? formatAmount(summary.headline_value, summary.currency)
      : isLoading
        ? '…'
        : '—';
  const href = (summary?.link ?? '#') as Route;

  return (
    <Card compact style={{ padding: 0 }}>
      <Link
        href={href}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing.md,
          padding: spacing.md,
          textDecoration: 'none',
          color: 'inherit',
        }}
      >
        <span
          aria-hidden
          style={{
            width: 40,
            height: 40,
            borderRadius: radius.md,
            backgroundColor: colors.surfaceMuted,
            border: `1px solid ${colors.border}`,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 20,
            flex: '0 0 auto',
          }}
        >
          {emoji}
        </span>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: fontSize.sm, fontWeight: fontWeight.semibold, color: colors.text }}>
            {label}
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: spacing.sm,
              flexWrap: 'wrap',
              marginTop: 2,
            }}
          >
            {summary?.secondary.map((s) => (
              <span key={s.label} style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
                {s.label} {s.value}
              </span>
            ))}
            {verdict !== 'neutral' ? (
              <span
                style={{
                  fontSize: fontSize.xs,
                  fontWeight: fontWeight.semibold,
                  color: VERDICT_COLOR[verdict],
                }}
              >
                · {VERDICT_LABEL[verdict]}
              </span>
            ) : null}
          </div>
        </div>

        <span
          style={{
            fontSize: fontSize.lg,
            fontWeight: fontWeight.semibold,
            color: colors.text,
            fontVariantNumeric: 'tabular-nums',
            whiteSpace: 'nowrap',
          }}
        >
          {value}
        </span>
        <span aria-hidden style={{ color: colors.textMuted, fontSize: fontSize.lg }}>
          →
        </span>
      </Link>
    </Card>
  );
}
