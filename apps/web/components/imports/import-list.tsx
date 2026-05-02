'use client';

import Link from 'next/link';

import type { ImportJob } from '@finanzas/types';
import { colors, fontSize, fontWeight, formatDate, radius, spacing } from '@finanzas/ui';

import { StatusBadge } from './status-badge';

export interface ImportListProps {
  items: ImportJob[];
}

export function ImportList({ items }: ImportListProps) {
  if (items.length === 0) {
    return (
      <div
        style={{
          padding: spacing.xl,
          textAlign: 'center',
          color: colors.textMuted,
          backgroundColor: colors.surfaceMuted,
          borderRadius: radius.md,
        }}
      >
        Aún no has importado ningún fichero.
      </div>
    );
  }

  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {items.map((job) => (
        <li
          key={job.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: spacing.md,
            padding: spacing.md,
            borderBottom: `1px solid ${colors.border}`,
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: fontSize.md,
                fontWeight: fontWeight.medium,
                color: colors.text,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {job.filename}
            </div>
            <div style={{ fontSize: fontSize.sm, color: colors.textMuted }}>
              {formatDate(job.created_at)} · {job.rows_ok} importadas · {job.rows_skipped}{' '}
              duplicadas · {job.rows_failed} con error
            </div>
          </div>
          <StatusBadge status={job.status} />
          <Link
            href={{ pathname: `/personal-finance/imports/${job.id}` }}
            style={{
              fontSize: fontSize.sm,
              fontWeight: fontWeight.medium,
              color: colors.primary,
              textDecoration: 'none',
            }}
          >
            Ver detalle →
          </Link>
        </li>
      ))}
    </ul>
  );
}
