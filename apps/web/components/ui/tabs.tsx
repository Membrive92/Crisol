'use client';

import { useRef, type CSSProperties, type KeyboardEvent } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

export interface TabItem {
  /** Identificador estable. Es lo que viaja en la URL. */
  key: string;
  label: string;
  /** Contador opcional a la derecha de la etiqueta (nº de banderas, etc.). */
  badge?: number | undefined;
  /**
   * Marca la pestaña como degradada: se puede abrir, pero se avisa ANTES del
   * clic de que su contenido no está disponible para este valor (una financiera
   * no tiene forense; un REIT casi no tiene liquidez). Sin esto el usuario abre
   * y encuentra una pestaña vacía sin entender por qué.
   */
  degraded?: boolean | undefined;
}

export interface TabsProps {
  items: TabItem[];
  value: string;
  onChange: (key: string) => void;
  /** Nombre accesible del conjunto de pestañas. */
  label: string;
  /** Prefijo de los `id` para cablear `aria-controls` con los paneles. */
  idPrefix: string;
}

/**
 * Barra de pestañas de primer nivel, accesible y sin scroll horizontal de página.
 *
 * No toca la URL: recibe `value` y emite `onChange`. Quien la usa decide si eso
 * viaja en un query param (es lo que hace la pantalla de informe) o en estado
 * local. Así el componente es testeable sin router.
 *
 * Teclado: ←/→ mueven el foco y la selección, Inicio/Fin van a los extremos —
 * el patrón de tabs automáticas de WAI-ARIA.
 */
export function Tabs({ items, value, onChange, label, idPrefix }: TabsProps) {
  const listRef = useRef<HTMLDivElement>(null);

  function focusTab(index: number) {
    const target = items[index];
    if (!target) return;
    onChange(target.key);
    const node = listRef.current?.querySelector<HTMLButtonElement>(
      `[data-tab-key="${target.key}"]`,
    );
    node?.focus();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const current = items.findIndex((item) => item.key === value);
    if (current < 0) return;
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      focusTab((current + 1) % items.length);
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      focusTab((current - 1 + items.length) % items.length);
    } else if (event.key === 'Home') {
      event.preventDefault();
      focusTab(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      focusTab(items.length - 1);
    }
  }

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={label}
      onKeyDown={handleKeyDown}
      style={{
        display: 'flex',
        gap: spacing.xs,
        // La barra scrollea DENTRO de sí misma. La página nunca hace scroll
        // horizontal, ni siquiera a 360px con seis pestañas.
        overflowX: 'auto',
        borderBottom: `1px solid ${colors.border}`,
        paddingBottom: 0,
      }}
    >
      {items.map((item) => {
        const selected = item.key === value;
        return (
          <button
            key={item.key}
            type="button"
            role="tab"
            id={`${idPrefix}-tab-${item.key}`}
            data-tab-key={item.key}
            aria-selected={selected}
            aria-controls={`${idPrefix}-panel-${item.key}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.key)}
            style={tabStyle(selected)}
          >
            <span>{item.label}</span>
            {item.badge !== undefined && item.badge > 0 ? (
              <span style={badgeStyle(selected)}>{item.badge}</span>
            ) : null}
            {item.degraded ? (
              <span
                aria-hidden
                title="Sin datos suficientes para este valor"
                style={{ color: colors.textSubtle, fontSize: fontSize.xs }}
              >
                ○
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

function tabStyle(selected: boolean): CSSProperties {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: spacing.xs,
    flexShrink: 0,
    background: 'none',
    border: 'none',
    borderBottom: `2px solid ${selected ? colors.primary : 'transparent'}`,
    color: selected ? colors.text : colors.textMuted,
    fontSize: fontSize.sm,
    fontWeight: selected ? fontWeight.semibold : fontWeight.medium,
    padding: `${spacing.sm}px ${spacing.md}px`,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  };
}

function badgeStyle(selected: boolean): CSSProperties {
  return {
    backgroundColor: selected ? colors.primarySoft : colors.surfaceMuted,
    color: selected ? colors.primary : colors.textMuted,
    borderRadius: radius.sm,
    padding: `0 ${spacing.xs}px`,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
  };
}

export interface TabPanelProps {
  idPrefix: string;
  tabKey: string;
  active: boolean;
  children: React.ReactNode;
}

/** Panel de una pestaña. Sólo se monta el activo: los seis a la vez pintarían
 *  seis matrices de 52 métricas × N años sin que nadie las vea. */
export function TabPanel({ idPrefix, tabKey, active, children }: TabPanelProps) {
  if (!active) return null;
  return (
    <div
      role="tabpanel"
      id={`${idPrefix}-panel-${tabKey}`}
      aria-labelledby={`${idPrefix}-tab-${tabKey}`}
      tabIndex={0}
      style={{ paddingTop: spacing.lg, outline: 'none' }}
    >
      {children}
    </div>
  );
}
