'use client';

import { useRef, useState, type CSSProperties } from 'react';
import { createPortal } from 'react-dom';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { InfoIcon } from '@/components/ui/icons';

export interface InfoTooltipProps {
  /** Texto explicativo que se muestra al pasar el ratón (o al enfocar). */
  text: string;
  /** Etiqueta accesible del botón (por defecto "Más información"). */
  label?: string;
  /** Tamaño del icono en px. */
  size?: number;
}

const TOOLTIP_WIDTH = 240;
const VIEWPORT_MARGIN = 8;
/** Hueco entre el icono y el tooltip. */
const GAP = 6;

/**
 * Icono "i" con tooltip estilado que aparece en hover o focus. Pensado para
 * explicar un KPI junto a su etiqueta.
 *
 * El tooltip se renderiza en un PORTAL a `document.body` con `position: fixed`:
 * los strips de KPI usan `overflow: hidden` (para recortar sus esquinas), lo que
 * recortaría un tooltip posicionado dentro. El portal lo saca de ahí. La
 * posición se calcula desde el rect del disparador y se ancla a la derecha si no
 * cabría por la izquierda (KPIs pegados al borde). Accesible: disparador
 * `<button>` + texto en `role="tooltip"`.
 */
export function InfoTooltip({ text, label = 'Más información', size = 13 }: InfoTooltipProps) {
  const ref = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  function show(): void {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const overflowsRight = r.left + TOOLTIP_WIDTH > window.innerWidth - VIEWPORT_MARGIN;
    const left = overflowsRight
      ? Math.max(VIEWPORT_MARGIN, r.right - TOOLTIP_WIDTH)
      : r.left;
    setPos({ top: r.bottom + GAP, left });
  }

  function hide(): void {
    setPos(null);
  }

  return (
    <span
      style={{ display: 'inline-flex', alignItems: 'center' }}
      onMouseEnter={show}
      onMouseLeave={hide}
    >
      <button
        ref={ref}
        type="button"
        aria-label={label}
        onFocus={show}
        onBlur={hide}
        style={triggerStyle}
      >
        <InfoIcon size={size} />
      </button>
      {pos
        ? createPortal(
            <span role="tooltip" style={{ ...tooltipStyle, top: pos.top, left: pos.left }}>
              {text}
            </span>,
            document.body,
          )
        : null}
    </span>
  );
}

const triggerStyle: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 0,
  border: 'none',
  background: 'transparent',
  color: colors.textSubtle,
  cursor: 'help',
  lineHeight: 0,
};

const tooltipStyle: CSSProperties = {
  position: 'fixed',
  zIndex: 1000,
  width: TOOLTIP_WIDTH,
  padding: `${spacing.xs}px ${spacing.sm}px`,
  backgroundColor: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.sm,
  boxShadow: '0 8px 24px rgba(0, 0, 0, 0.32)',
  color: colors.text,
  fontSize: fontSize.xs,
  fontWeight: fontWeight.medium,
  // El label del KPI va en mayúsculas; el tooltip debe leerse normal.
  letterSpacing: 'normal',
  textTransform: 'none',
  whiteSpace: 'normal',
  lineHeight: 1.45,
  textAlign: 'left',
  pointerEvents: 'none',
};
