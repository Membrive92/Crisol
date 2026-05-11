'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

import type { User } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import {
  ChevronDownIcon,
  LogOutIcon,
  SettingsIcon,
  UserIcon,
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
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Menú de usuario"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          padding: 2,
          paddingRight: 8,
          backgroundColor: open ? colors.surfaceMuted : 'transparent',
          border: `1px solid ${open ? colors.borderStrong : colors.border}`,
          borderRadius: 9999,
          cursor: 'pointer',
          color: colors.textMuted,
          transition: 'background-color 120ms ease, border-color 120ms ease',
        }}
      >
        <span
          aria-hidden
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 28,
            height: 28,
            borderRadius: '50%',
            backgroundColor: colors.surfaceMuted,
            color: colors.text,
          }}
        >
          <UserIcon size={16} />
        </span>
        <ChevronDownIcon size={14} style={{ color: colors.textSubtle }} />
      </button>

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
