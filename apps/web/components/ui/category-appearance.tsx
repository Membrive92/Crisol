'use client';

import {
  CATEGORY_COLOR_PALETTE,
  CATEGORY_EMOJI_PRESETS,
  colors,
  fontSize,
  fontWeight,
  radius,
  spacing,
} from '@finanzas/ui';

export interface CategoryAppearanceFieldsProps {
  color: string | null;
  icon: string | null;
  onColorChange: (hex: string) => void;
  onIconChange: (emoji: string | null) => void;
}

/**
 * Pickers de color (paleta curada) y emoji (set sugerido) para
 * personalizar una categoría. Diseñado para vivir dentro de un form
 * — no incluye padding ni card propia.
 */
export function CategoryAppearanceFields({
  color,
  icon,
  onColorChange,
  onIconChange,
}: CategoryAppearanceFieldsProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <div>
        <span style={labelStyle}>Color</span>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: spacing.xs,
            marginTop: spacing.xs,
          }}
          role="radiogroup"
          aria-label="Color de la categoría"
        >
          {CATEGORY_COLOR_PALETTE.map((preset) => {
            const selected = preset.hex.toLowerCase() === color?.toLowerCase();
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => onColorChange(preset.hex)}
                title={preset.label}
                aria-label={preset.label}
                aria-checked={selected}
                role="radio"
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  backgroundColor: preset.hex,
                  border: selected
                    ? `2px solid ${colors.text}`
                    : `1px solid ${colors.border}`,
                  boxShadow: selected ? `0 0 0 2px ${colors.surface}` : 'none',
                  cursor: 'pointer',
                  padding: 0,
                }}
              />
            );
          })}
        </div>
      </div>

      <div>
        <span style={labelStyle}>Icono</span>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: spacing.xs,
            marginTop: spacing.xs,
          }}
          role="radiogroup"
          aria-label="Icono de la categoría"
        >
          <button
            type="button"
            onClick={() => onIconChange(null)}
            aria-checked={!icon}
            role="radio"
            style={emojiButtonStyle(!icon)}
            title="Sin icono"
          >
            <span style={{ color: colors.textMuted, fontSize: fontSize.xs }}>—</span>
          </button>
          {CATEGORY_EMOJI_PRESETS.map((emoji) => {
            const selected = emoji === icon;
            return (
              <button
                key={emoji}
                type="button"
                onClick={() => onIconChange(emoji)}
                aria-checked={selected}
                role="radio"
                style={emojiButtonStyle(selected)}
                title={emoji}
              >
                <span style={{ fontSize: fontSize.lg, lineHeight: 1 }}>{emoji}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const labelStyle = {
  display: 'block',
  fontSize: fontSize.sm,
  fontWeight: fontWeight.medium,
  color: colors.text,
} as const;

function emojiButtonStyle(selected: boolean) {
  return {
    width: 36,
    height: 36,
    borderRadius: radius.sm,
    backgroundColor: selected ? colors.primarySoft : colors.surface,
    border: `1px solid ${selected ? colors.primary : colors.border}`,
    cursor: 'pointer',
    padding: 0,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  } as const;
}
