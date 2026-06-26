'use client';

import Link from 'next/link';

import type { ImportJob } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { Button } from '../ui/button';
import { StatusBadge } from './status-badge';

export interface ResultStepProps {
  job: ImportJob;
  onRestart: () => void;
}

export function ResultStep({ job, onRestart }: ResultStepProps) {
  const isSuccess = job.status === 'completed';
  // P5 (transfers-ux): el backend mezcla en `error_log` fallos reales y
  // avisos de revisión (flag `review`). Los separamos: "A revisar" son
  // filas que SÍ se importaron pero conviene mirar (no son errores).
  const errors = job.error_log.filter((e) => e.review !== true);
  const reviews = job.error_log.filter((e) => e.review === true);
  const visibleErrors = errors.slice(0, 10);
  const remainingErrors = Math.max(0, errors.length - visibleErrors.length);
  const visibleReviews = reviews.slice(0, 10);
  const remainingReviews = Math.max(0, reviews.length - visibleReviews.length);

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
          gridTemplateColumns: 'repeat(auto-fit, minmax(90px, 1fr))',
          gap: spacing.sm,
          marginBottom: spacing.lg,
        }}
      >
        <Stat label="Total" value={job.rows_total} />
        <Stat label="Importadas" value={job.rows_ok} tone="success" />
        <Stat label="Duplicadas" value={job.rows_skipped} tone="muted" />
        <Stat label="Con error" value={job.rows_failed} tone="danger" />
        {reviews.length > 0 ? (
          <Stat label="A revisar" value={reviews.length} tone="warning" />
        ) : null}
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

      {visibleReviews.length > 0 ? (
        <div style={{ marginBottom: spacing.lg }}>
          <h3
            style={{
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              margin: `0 0 ${spacing.xs}px 0`,
            }}
          >
            A revisar
          </h3>
          <p
            style={{
              margin: `0 0 ${spacing.sm}px 0`,
              fontSize: fontSize.xs,
              color: colors.textMuted,
            }}
          >
            Estas filas SÍ se importaron, pero conviene que las revises (por
            ejemplo, transferencias cuya dirección no pudimos determinar).
          </p>
          <ul
            style={{
              listStyle: 'none',
              padding: 0,
              margin: 0,
              border: `1px solid ${colors.warning}`,
              borderRadius: radius.sm,
              backgroundColor: colors.warningSoft,
            }}
          >
            {visibleReviews.map((entry) => (
              <li
                key={`r-${entry.row}-${entry.error}`}
                style={{
                  padding: spacing.sm,
                  borderBottom: `1px solid ${colors.warning}`,
                  fontSize: fontSize.sm,
                  color: colors.text,
                }}
              >
                <strong>Fila {entry.row}:</strong> {entry.error}
              </li>
            ))}
          </ul>
          {remainingReviews > 0 ? (
            <div
              style={{
                marginTop: spacing.xs,
                fontSize: fontSize.xs,
                color: colors.textMuted,
              }}
            >
              … y {remainingReviews} fila{remainingReviews === 1 ? '' : 's'} más a
              revisar.
            </div>
          ) : null}
          <div style={{ marginTop: spacing.sm }}>
            <Link href="/personal-finance/transfers">
              <Button variant="secondary">Revisar transferencias</Button>
            </Link>
          </div>
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
  tone?: 'success' | 'danger' | 'muted' | 'warning';
}

function Stat({ label, value, tone }: StatProps) {
  const valueColor =
    tone === 'success'
      ? colors.success
      : tone === 'danger'
        ? colors.danger
        : tone === 'warning'
          ? colors.warning
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
