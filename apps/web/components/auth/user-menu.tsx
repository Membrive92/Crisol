'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

import type { User } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, scaleFont, spacing } from '@crisol/ui';

import {
  ChevronDownIcon,
  LogOutIcon,
  SettingsIcon,
} from '@/components/ui/icons';

export interface UserMenuProps {
  user: User | null;
  onLogout: () => void;
}

/**
 * Avatar circular en el extremo derecho del header. Click → dropdown
 * con el email del usuario en cabecera y dos acciones: Ajustes (link a
 * /settings) y Salir (logout). Cierra al hacer click fuera o `Escape`.
 */
export function UserMenu({ user, onLogout }: UserMenuProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open]);

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <UserChipTrigger
        user={user}
        open={open}
        onClick={() => setOpen((v) => !v)}
      />

      {open && (
        <div
          role="menu"
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            right: 0,
            minWidth: 220,
            backgroundColor: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            boxShadow: '0 12px 32px rgba(0, 0, 0, 0.32)',
            zIndex: 60,
            overflow: 'hidden',
          }}
        >
          {user ? (
            <div
              style={{
                padding: `${spacing.sm + 2}px ${spacing.md}px`,
                borderBottom: `1px solid ${colors.border}`,
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
              }}
            >
              <span
                style={{
                  fontSize: fontSize.sm,
                  fontWeight: fontWeight.semibold,
                  color: colors.text,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {user.display_name ?? 'Usuario'}
              </span>
              <span
                style={{
                  fontSize: fontSize.xs,
                  color: colors.textMuted,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {user.email}
              </span>
            </div>
          ) : null}

          <div style={{ padding: spacing.xs }}>
            <MenuItem
              href="/settings"
              label="Ajustes"
              icon={<SettingsIcon size={16} />}
              onClose={() => setOpen(false)}
            />
            <MenuItem
              label="Salir"
              icon={<LogOutIcon size={16} />}
              danger
              onClick={() => {
                setOpen(false);
                onLogout();
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Trigger del UserMenu rediseñado (PHASE-29.3): avatar circular con
 * iniciales sobre gradient copper + nombre del usuario + "Personal"
 * como rol/contexto + chevron. Mismo patrón de glow tonal que el
 * CurrencyPillTrigger para que el header se sienta cohesivo.
 */
function UserChipTrigger({
  user,
  open,
  onClick,
}: {
  user: User | null;
  open: boolean;
  onClick: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const active = open || hovered;
  const displayName = user?.display_name ?? user?.email ?? 'Usuario';
  const initials = initialsFrom(displayName);

  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-haspopup="menu"
      aria-expanded={open}
      aria-label="Menú de usuario"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '3px 10px 3px 3px',
        borderRadius: 999,
        backgroundColor: active ? colors.surfaceMuted : 'transparent',
        border: `1px solid ${active ? colors.border : 'transparent'}`,
        cursor: 'pointer',
        color: colors.text,
        boxShadow: active ? `0 0 0 3px ${colors.primarySoft}` : 'none',
        transition:
          'background-color 140ms ease, border-color 140ms ease, box-shadow 140ms ease',
        maxWidth: 220,
      }}
    >
      <span
        aria-hidden
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 30,
          height: 30,
          borderRadius: '50%',
          background: `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%)`,
          color: colors.onPrimary,
          fontSize: scaleFont(11.5),
          fontWeight: fontWeight.bold,
          letterSpacing: '0.02em',
          flex: '0 0 auto',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,.18)',
        }}
      >
        {initials}
      </span>
      <span
        style={{
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          lineHeight: 1.15,
          textAlign: 'left',
        }}
      >
        <span
          style={{
            fontSize: scaleFont(13),
            fontWeight: fontWeight.semibold,
            color: colors.text,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            maxWidth: 140,
          }}
        >
          {displayName}
        </span>
        <span
          style={{
            fontSize: scaleFont(11),
            color: colors.textMuted,
            fontWeight: fontWeight.medium,
          }}
        >
          Personal
        </span>
      </span>
      <ChevronDownIcon size={12} style={{ color: colors.textSubtle, flex: '0 0 auto' }} />
    </button>
  );
}

/** "JM Membrive" → "JM"; "membrij7@gmail.com" → "ME"; "Juan" → "JU". */
function initialsFrom(name: string): string {
  const cleaned = name.trim();
  if (!cleaned) return '··';
  // Si parece email, usar la parte antes del @.
  const base = cleaned.includes('@') ? cleaned.split('@')[0] ?? cleaned : cleaned;
  const parts = base.split(/[\s._-]+/).filter(Boolean);
  if (parts.length >= 2) {
    const first = parts[0]?.[0] ?? '';
    const second = parts[1]?.[0] ?? '';
    return (first + second).toUpperCase();
  }
  const word = parts[0] ?? base;
  return word.slice(0, 2).toUpperCase();
}

function MenuItem({
  href,
  label,
  icon,
  danger = false,
  onClick,
  onClose,
}: {
  href?: string | undefined;
  label: string;
  icon: React.ReactNode;
  danger?: boolean | undefined;
  onClick?: (() => void) | undefined;
  onClose?: (() => void) | undefined;
}) {
  const [hovered, setHovered] = useState(false);
  const fg = danger ? colors.danger : colors.text;
  const bg = hovered ? colors.surfaceMuted : 'transparent';

  const baseStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: spacing.sm,
    padding: `${spacing.sm}px ${spacing.sm + 4}px`,
    backgroundColor: bg,
    color: fg,
    border: 'none',
    borderRadius: radius.sm,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    cursor: 'pointer',
    width: '100%',
    textAlign: 'left',
    textDecoration: 'none',
    transition: 'background-color 120ms ease',
  };

  if (href) {
    return (
      <Link
        href={href as never}
        role="menuitem"
        onClick={() => onClose?.()}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={baseStyle}
      >
        <span style={{ color: fg, display: 'inline-flex' }}>{icon}</span>
        <span>{label}</span>
      </Link>
    );
  }

  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={baseStyle}
    >
      <span style={{ color: fg, display: 'inline-flex' }}>{icon}</span>
      <span>{label}</span>
    </button>
  );
}
