'use client';

import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { useTheme } from '@/lib/theme-provider';

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const next = theme === 'dark' ? 'claro' : 'oscuro';

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={`Cambiar a tema ${next}`}
      title={`Cambiar a tema ${next}`}
      style={{
        padding: `${spacing.xs}px ${spacing.sm}px`,
        backgroundColor: 'transparent',
        color: colors.text,
        border: `1px solid ${colors.border}`,
        borderRadius: 6,
        cursor: 'pointer',
        fontSize: fontSize.sm,
        fontWeight: fontWeight.medium,
      }}
    >
      {theme === 'dark' ? '☀️ Claro' : '🌙 Oscuro'}
    </button>
  );
}
