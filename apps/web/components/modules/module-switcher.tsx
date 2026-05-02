'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import { MODULES, type AppModule } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

interface ModuleSwitcherProps {
  active: AppModule;
}

export function ModuleSwitcher({ active }: ModuleSwitcherProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState(false);
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

  function selectModule(m: AppModule) {
    setOpen(false);
    if (!m.enabled || m.id === active.id) return;
    const target = m.sections[0]?.path ?? m.basePath;
    router.push(target as never);
  }

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        aria-haspopup="listbox"
        aria-expanded={open}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: spacing.sm,
          padding: `${spacing.xs + 2}px ${spacing.sm + 4}px`,
          backgroundColor:
            open || hovered ? colors.surfaceMuted : colors.surface,
          color: colors.text,
          border: `1px solid ${open ? colors.borderStrong : colors.border}`,
          borderRadius: radius.md,
          cursor: 'pointer',
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          lineHeight: 1.2,
          transition: 'background-color 120ms ease, border-color 120ms ease',
        }}
      >
        <span
          aria-hidden
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            backgroundColor: colors.primary,
            flex: '0 0 auto',
          }}
        />
        <span style={{ color: colors.text }}>{active.label}</span>
        <Chevron open={open} />
      </button>
      {open && (
        <ul
          role="listbox"
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: 0,
            minWidth: 260,
            margin: 0,
            padding: spacing.xs,
            listStyle: 'none',
            backgroundColor: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            boxShadow: '0 12px 32px rgba(0, 0, 0, 0.32)',
            zIndex: 20,
          }}
        >
          {MODULES.map((m) => (
            <li key={m.id}>
              <ModuleOption
                module={m}
                active={m.id === active.id}
                onSelect={() => selectModule(m)}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ModuleOption({
  module,
  active,
  onSelect,
}: {
  module: AppModule;
  active: boolean;
  onSelect: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const disabled = !module.enabled;
  return (
    <button
      type="button"
      role="option"
      aria-selected={active}
      onClick={onSelect}
      disabled={disabled}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        width: '100%',
        textAlign: 'left',
        padding: `${spacing.sm}px ${spacing.sm + 4}px`,
        backgroundColor:
          active
            ? colors.surfaceMuted
            : hovered && !disabled
              ? colors.surfaceMuted
              : 'transparent',
        color: disabled ? colors.textSubtle : colors.text,
        border: 'none',
        borderRadius: radius.sm,
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontSize: fontSize.sm,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: spacing.sm,
        transition: 'background-color 120ms ease',
      }}
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: spacing.sm,
          fontWeight: active ? fontWeight.semibold : fontWeight.medium,
        }}
      >
        <span
          aria-hidden
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            backgroundColor: active
              ? colors.primary
              : disabled
                ? colors.textSubtle
                : colors.borderStrong,
          }}
        />
        {module.label}
      </span>
      {disabled ? (
        <span
          style={{
            fontSize: fontSize.xs,
            color: colors.textSubtle,
            fontWeight: fontWeight.medium,
          }}
        >
          Próximamente
        </span>
      ) : active ? (
        <span style={{ fontSize: fontSize.xs, color: colors.primary }}>Activo</span>
      ) : null}
    </button>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden
      width="12"
      height="12"
      viewBox="0 0 12 12"
      style={{
        color: colors.textMuted,
        transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
        transition: 'transform 150ms ease',
        flex: '0 0 auto',
      }}
    >
      <path
        d="M3 4.5l3 3 3-3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
