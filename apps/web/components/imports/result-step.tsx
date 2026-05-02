'use client';

import Link from 'next/link';

import type { ImportJob } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { Button } from '../ui/button';
import { StatusBadge } from './status-badge';

export interface ResultStepProps {
  job: ImportJob;
  onRestart: () => void;
}

export function ResultStep({ job, onRestart }: ResultStepProps) {
  const isSuccess = job.status === 'completed';
  const visibleErrors = job.error_log.slice(0, 10);
  const remainingErrors = Math.max(0, job.error_log.length - visibleErrors.length);

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing.sm,
          marginBottom: spacing.md,
        }}
      >
        <StatusBadge status={job.status} />
        <span style={{ fontSize: fontSize.sm, color: colors.textMuted }}>
          {job.filename}
        </span>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: spacing.sm,
          marginBottom: spacing.lg,
        }}
      >
        <Stat label="Total" value={job.rows_total} />
        <Stat label="Importadas" value={job.rows_ok} tone="success" />
        <Stat label="Duplicadas" value={job.rows_skipped} tone="muted" />
        <Stat label="Con error" value={job.rows_failed} tone="danger" />
      </div>

      {visibleErrors.length > 0 ? (
        <div style={{ marginBottom: spacing.lg }}>
          <h3
            style={{
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              margin: `0 0 ${spacing.sm}px 0`,
            }}
          >
            Errores
          </h3>
          <ul
            style={{
              listStyle: 'none',
              padding: 0,
              margin: 0,
              border: `1px solid ${colors.border}`,
              borderRadius: radius.sm,
            }}
          >
            {visibleErrors.map((entry) => (
              <li
                key={`${entry.row}-${entry.error}`}
                style={{
                  padding: spacing.sm,
                  borderBottom: `1px solid ${colors.border}`,
                  fontSize: fontSize.sm,
                  color: colors.text,
                }}
              >
                <strong>Fila {entry.row}:</strong> {entry.error}
              </li>
            ))}
          </ul>
          {remainingErrors > 0 ? (
            <div
              style={{
                marginTop: spacing.xs,
                fontSize: fontSize.xs,
                color: colors.textMuted,
              }}
            >
              … y {remainingErrors} error{remainingErrors === 1 ? '' : 'es'} más.
            </div>
          ) : null}
        </div>
      ) : null}

      <div style={{ display: 'flex', gap: spacing.sm }}>
        {isSuccess ? (
          <Link href="/personal-finance/transactions">
            <Button>Ver transacciones</Button>
          </Link>
        ) : null}
        <Button variant="secondary" onClick={onRestart}>
          Importar otro fichero
        </Button>
        <Link href="/personal-finance/imports">
          <Button variant="ghost">Volver al listado</Button>
        </Link>
      </div>
    </div>
  );
}

interface StatProps {
  label: string;
  value: number;
  tone?: 'success' | 'danger' | 'muted';
}

function Stat({ label, value, tone }: StatProps) {
  const valueColor =
    tone === 'success'
      ? colors.success
      : tone === 'danger'
        ? colors.danger
        : tone === 'muted'
          ? colors.textMuted
          : colors.text;

  return (
    <div
      style={{
        padding: spacing.sm,
        backgroundColor: colors.surfaceMuted,
        borderRadius: radius.sm,
        textAlign: 'center',
      }}
    >
      <div
        style={{
          fontSize: fontSize.xl,
          fontWeight: fontWeight.semibold,
          color: valueColor,
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: fontSize.xs, color: colors.textMuted }}>{label}</div>
    </div>
  );
}
