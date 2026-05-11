'use client';

import { useEffect, type ReactNode } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { Button } from './button';

export type ConfirmDialogTone = 'danger' | 'primary';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: ConfirmDialogTone;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Eliminar',
  cancelLabel = 'Cancelar',
  tone = 'danger',
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && !loading) onCancel();
    }
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
    };
  }, [open, loading, onCancel]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: spacing.lg,
        zIndex: 100,
      }}
      onClick={() => {
        if (!loading) onCancel();
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          backgroundColor: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: radius.md,
          padding: spacing.lg,
          width: '100%',
          maxWidth: 420,
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.18)',
        }}
      >
        <h3
          id="confirm-dialog-title"
          style={{
            margin: 0,
            fontSize: fontSize.lg,
            fontWeight: fontWeight.semibold,
            color: colors.text,
          }}
        >
          {title}
        </h3>
        {description ? (
          <div
            style={{
              margin: `${spacing.sm}px 0 0`,
              fontSize: fontSize.sm,
              color: colors.textMuted,
              lineHeight: 1.5,
            }}
          >
            {description}
          </div>
        ) : null}
        <div
          style={{
            display: 'flex',
            gap: spacing.sm,
            justifyContent: 'flex-end',
            marginTop: spacing.md,
          }}
        >
          <Button type="button" variant="ghost" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant={tone === 'danger' ? 'danger' : 'primary'}
            onClick={onConfirm}
            disabled={loading}
            autoFocus
          >
            {loading ? 'Procesando…' : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
