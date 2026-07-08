'use client';

import { colors, fontSize, fontWeight, radius } from '@crisol/ui';

export interface ExceptionalToggleProps {
  /** `null` = automático (heurística), `false` = estructural, `true` = puntual. */
  value: boolean | null;
  pending: boolean;
  onChange: (next: boolean | null) => void;
}

const OPTIONS: { key: string; label: string; val: boolean | null; hint: string }[] = [
  { key: 'auto', label: 'Automático', val: null, hint: 'Decide la heurística' },
  { key: 'structural', label: 'Estructural', val: false, hint: 'Gasto recurrente' },
  { key: 'exceptional', label: 'Puntual', val: true, hint: 'Gasto one-off' },
];

/**
 * Control tri-estado de la clasificación estructural/puntual del gasto
 * (PHASE-37.3): Automático (`null`) · Estructural (`false`) · Puntual (`true`).
 * El estado activo se deshabilita para no reenviar el mismo valor; `pending`
 * bloquea todo el grupo durante la mutación.
 */
export function ExceptionalToggle({ value, pending, onChange }: ExceptionalToggleProps) {
  return (
    <div
      role="radiogroup"
      aria-label="Clasificación del gasto"
      style={{
        display: 'inline-flex',
        gap: 4,
        padding: 3,
        borderRadius: radius.md,
        backgroundColor: colors.surfaceMuted,
        border: `1px solid ${colors.border}`,
        opacity: pending ? 0.6 : 1,
      }}
    >
      {OPTIONS.map((opt) => {
        const active = value === opt.val;
        return (
          <button
            key={opt.key}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={pending || active}
            onClick={() => onChange(opt.val)}
            title={opt.hint}
            style={{
              padding: '6px 14px',
              borderRadius: radius.sm,
              border: 'none',
              cursor: pending || active ? 'default' : 'pointer',
              fontSize: fontSize.sm,
              fontWeight: active ? fontWeight.semibold : fontWeight.medium,
              backgroundColor: active ? colors.surface : 'transparent',
              color: active ? colors.text : colors.textMuted,
              boxShadow: active ? '0 1px 2px rgba(0,0,0,0.18)' : 'none',
              transition: 'background-color 120ms ease, color 120ms ease',
            }}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
