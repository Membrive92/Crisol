'use client';

import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';

import { useTheme, type ThemePreference } from '@/lib/theme-provider';

const LABELS: Record<ThemePreference, { icon: string; text: string; next: string }> = {
  light: { icon: '☀️', text: 'Claro', next: 'oscuro' },
  dark: { icon: '🌙', text: 'Oscuro', next: 'sistema' },
  system: { icon: '🖥️', text: 'Sistema', next: 'claro' },
};

export function ThemeToggle() {
  const { preference, cyclePreference } = useTheme();
  const current = LABELS[preference];

  return (
    <button
      type="button"
      onClick={cyclePreference}
      aria-label={`Tema actual: ${current.text}. Click para cambiar a ${current.next}.`}
      title={`Tema: ${current.text} (click → ${current.next})`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: `${spacing.xs}px ${spacing.sm}px`,
        backgroundColor: 'transparent',
        color: colors.text,
        border: `1px solid ${colors.border}`,
        borderRadius: 6,
        cursor: 'pointer',
        fontSize: fontSize.sm,
        fontWeight: fontWeight.medium,
        lineHeight: 1,
      }}
    >
      <span aria-hidden="true">{current.icon}</span>
      <span>{current.text}</span>
    </button>
  );
}
