'use client';

import { useState } from 'react';

import type { Budget, Category } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@crisol/ui';

import { Button } from '@/components/ui/button';

export interface BudgetRowProps {
  budget: Budget;
  categories: Category[];
  onSave: (id: string, amount: string) => Promise<void> | void;
  onDelete: (id: string) => void;
  /** True mientras se persiste cualquier mutation sobre este row. */
  busy?: boolean;
  /** Mostrar bordertop si NO es el primer row. */
  withTopBorder?: boolean;
}

/**
 * Fila editable de un presupuesto activo. Modo lectura por defecto;
 * "Editar" pasa a modo edición con input + Guardar/Cancelar. Tras
 * guardar (o cancelar), vuelve a lectura. Validación local idéntica
 * a `BudgetForm`: amount > 0.
 */
export function BudgetRow({
  budget: b,
  categories,
  onSave,
  onDelete,
  busy = false,
  withTopBorder = false,
}: BudgetRowProps) {
  const cat = categories.find((c) => c.id === b.category_id);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string>(b.amount);
  const [error, setError] = useState<string | null>(null);

  function handleStart() {
    setDraft(b.amount);
    setError(null);
    setEditing(true);
  }

  function handleCancel() {
    setEditing(false);
    setError(null);
  }

  async function handleSave() {
    const trimmed = draft.trim().replace(',', '.');
    if (!trimmed || Number.isNaN(Number(trimmed)) || Number(trimmed) <= 0) {
      setError('El importe debe ser un número positivo.');
      return;
    }
    setError(null);
    await onSave(b.id, trimmed);
    setEditing(false);
  }

  return (
    <li
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: spacing.sm,
        padding: spacing.md,
        borderTop: withTopBorder ? `1px solid ${colors.border}` : 'none',
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <span
          style={{
            fontSize: fontSize.sm,
            fontWeight: fontWeight.semibold,
            color: colors.text,
            display: 'block',
          }}
        >
          {cat?.name ?? 'Global'}
        </span>
        {editing ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: spacing.xs,
              marginTop: spacing.xs,
              flexWrap: 'wrap',
            }}
          >
            <input
              autoFocus
              type="text"
              inputMode="decimal"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              style={{
                width: 120,
                padding: `${spacing.xs}px ${spacing.sm}px`,
                fontSize: fontSize.sm,
                color: colors.text,
                backgroundColor: colors.surface,
                border: `1px solid ${colors.border}`,
                borderRadius: radius.sm,
              }}
            />
            <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
              {b.currency} / mes
            </span>
            {error ? (
              <span
                style={{
                  fontSize: fontSize.xs,
                  color: colors.danger,
                  width: '100%',
                }}
              >
                {error}
              </span>
            ) : null}
          </div>
        ) : (
          <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
            {formatAmount(b.amount, b.currency)} / mes · vigente desde{' '}
            {b.effective_from}
          </span>
        )}
      </div>

      <div style={{ display: 'inline-flex', gap: spacing.xs }}>
        {editing ? (
          <>
            <Button
              onClick={handleSave}
              disabled={busy}
              style={{ padding: `4px ${spacing.sm + 2}px` }}
            >
              {busy ? 'Guardando…' : 'Guardar'}
            </Button>
            <Button
              variant="ghost"
              onClick={handleCancel}
              disabled={busy}
              style={{ padding: `4px ${spacing.sm}px` }}
            >
              Cancelar
            </Button>
          </>
        ) : (
          <>
            <Button
              variant="ghost"
              onClick={handleStart}
              disabled={busy}
              style={{ padding: `4px ${spacing.sm}px` }}
            >
              Editar
            </Button>
            <Button
              variant="ghost"
              onClick={() => onDelete(b.id)}
              disabled={busy}
              style={{
                padding: `4px ${spacing.sm}px`,
                color: colors.danger,
                borderColor: colors.border,
              }}
            >
              {busy ? 'Cerrando…' : 'Cerrar'}
            </Button>
          </>
        )}
      </div>
    </li>
  );
}
