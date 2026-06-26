'use client';

import { useEffect, useId, useMemo, useRef, useState } from 'react';

import type { Category } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

export interface CategoryComboboxProps {
  label: string;
  categories: Category[];
  /** `category_id` seleccionado; `''` = sin categoría. */
  value: string;
  onChange: (categoryId: string) => void;
  disabled?: boolean;
  error?: string | undefined;
}

interface Option {
  id: string; // '' para "sin categoría"
  name: string;
  kind: 'income' | 'expense' | 'none';
  icon: string | null;
}

const NONE_OPTION: Option = {
  id: '',
  name: 'Sin categoría',
  kind: 'none',
  icon: null,
};

// Diacríticos (propiedad Unicode `\p{Diacritic}` + flag `u`): ASCII puro
// en el source, sin caracteres combinantes literales.
const COMBINING_MARKS = /\p{Diacritic}/gu;

/** Quita acentos y baja a minúsculas para una búsqueda tolerante. */
function fold(s: string): string {
  return s.normalize('NFD').replace(COMBINING_MARKS, '').toLowerCase().trim();
}

/**
 * Selector de categoría con búsqueda inline y agrupación por
 * Ingresos / Gastos. Reemplaza al `<select>` nativo, que con ~30
 * categorías era tedioso de recorrer al categorizar un movimiento.
 *
 * Accesibilidad: patrón combobox (input `role="combobox"` +
 * `listbox`), navegación con flechas/Enter/Escape y
 * `aria-activedescendant`. Cierra al hacer click fuera.
 */
export function CategoryCombobox({
  label,
  categories,
  value,
  onChange,
  disabled,
  error,
}: CategoryComboboxProps) {
  const baseId = useId();
  const listId = `${baseId}-list`;
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);

  const selected = useMemo(
    () => categories.find((c) => c.id === value) ?? null,
    [categories, value],
  );
  const selectedLabel = value === '' ? '' : (selected?.name ?? '');

  // Lista filtrada y partida por kind. La lista PLANA (`flat`) sostiene
  // el índice del resaltado por teclado; el render la reagrupa.
  const { income, expense, none, flat } = useMemo(() => {
    const q = fold(query);
    const matches = (o: Option) => q === '' || fold(o.name).includes(q);
    const cats: Option[] = categories.map((c) => ({
      id: c.id,
      name: c.name,
      kind: c.kind === 'income' ? 'income' : 'expense',
      icon: c.icon ?? null,
    }));
    const noneList = matches(NONE_OPTION) ? [NONE_OPTION] : [];
    const incomeList = cats.filter((o) => o.kind === 'income' && matches(o));
    const expenseList = cats.filter((o) => o.kind === 'expense' && matches(o));
    return {
      none: noneList,
      income: incomeList,
      expense: expenseList,
      flat: [...noneList, ...incomeList, ...expenseList],
    };
  }, [categories, query]);

  // Mantener el resaltado dentro de rango cuando el filtro cambia.
  useEffect(() => {
    setActiveIndex((i) => (flat.length === 0 ? 0 : Math.min(i, flat.length - 1)));
  }, [flat.length]);

  // Cerrar al hacer click fuera.
  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        close();
      }
    }
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [open]);

  // Auto-scroll de la opción resaltada al navegar con teclado.
  useEffect(() => {
    if (!open) return;
    const el = document.getElementById(`${baseId}-opt-${activeIndex}`);
    // optional-chaining en el método: jsdom (tests) no implementa
    // scrollIntoView; es UX no crítica, así que no debe romper.
    el?.scrollIntoView?.({ block: 'nearest' });
  }, [open, activeIndex, baseId]);

  function openMenu() {
    if (disabled) return;
    setOpen(true);
    // Posicionar el resaltado en la selección actual si está visible.
    const idx = flat.findIndex((o) => o.id === value);
    setActiveIndex(idx >= 0 ? idx : 0);
  }

  function close() {
    setOpen(false);
    setQuery('');
  }

  function choose(option: Option) {
    onChange(option.id);
    close();
    inputRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (disabled) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!open) {
        openMenu();
        return;
      }
      setActiveIndex((i) => Math.min(i + 1, Math.max(flat.length - 1, 0)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (!open) {
        openMenu();
        return;
      }
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      if (open && flat[activeIndex]) {
        e.preventDefault();
        choose(flat[activeIndex]);
      }
    } else if (e.key === 'Escape') {
      if (open) {
        e.preventDefault();
        close();
      }
    } else if (e.key === 'Tab') {
      if (open) close();
    }
  }

  const activeOptionId = open && flat[activeIndex] ? `${baseId}-opt-${activeIndex}` : undefined;

  // Índice global de cada opción dentro de `flat` (id estable para
  // aria-activedescendant + auto-scroll).
  let runningIndex = 0;

  return (
    <div ref={containerRef} style={{ marginBottom: spacing.md, position: 'relative' }}>
      <label htmlFor={baseId} style={labelStyle}>
        {label}
      </label>
      <input
        ref={inputRef}
        id={baseId}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={activeOptionId}
        autoComplete="off"
        disabled={disabled}
        placeholder={selectedLabel || '— Sin categoría —'}
        value={open ? query : selectedLabel}
        onChange={(e) => {
          setQuery(e.target.value);
          if (!open) setOpen(true);
          setActiveIndex(0);
        }}
        onFocus={openMenu}
        onClick={openMenu}
        onKeyDown={handleKeyDown}
        style={{
          ...controlStyle,
          ...(error ? { borderColor: colors.danger } : {}),
          cursor: disabled ? 'not-allowed' : 'text',
        }}
      />
      {open ? (
        <ul
          id={listId}
          role="listbox"
          aria-label={label}
          style={{
            position: 'absolute',
            zIndex: 20,
            top: '100%',
            left: 0,
            right: 0,
            marginTop: 4,
            maxHeight: 280,
            overflowY: 'auto',
            listStyle: 'none',
            padding: spacing.xs,
            margin: 0,
            backgroundColor: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.sm,
            boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
          }}
        >
          {flat.length === 0 ? (
            <li
              style={{
                padding: `${spacing.sm}px ${spacing.sm}px`,
                color: colors.textMuted,
                fontSize: fontSize.sm,
              }}
            >
              Sin resultados
            </li>
          ) : null}
          {none.map((o) => {
            const idx = runningIndex++;
            return (
              <Row
                key="none"
                option={o}
                id={`${baseId}-opt-${idx}`}
                active={idx === activeIndex}
                selected={o.id === value}
                onPick={() => choose(o)}
                onHover={() => setActiveIndex(idx)}
              />
            );
          })}
          {income.length > 0 ? <GroupHeader label="Ingresos" /> : null}
          {income.map((o) => {
            const idx = runningIndex++;
            return (
              <Row
                key={o.id}
                option={o}
                id={`${baseId}-opt-${idx}`}
                active={idx === activeIndex}
                selected={o.id === value}
                onPick={() => choose(o)}
                onHover={() => setActiveIndex(idx)}
              />
            );
          })}
          {expense.length > 0 ? <GroupHeader label="Gastos" /> : null}
          {expense.map((o) => {
            const idx = runningIndex++;
            return (
              <Row
                key={o.id}
                option={o}
                id={`${baseId}-opt-${idx}`}
                active={idx === activeIndex}
                selected={o.id === value}
                onPick={() => choose(o)}
                onHover={() => setActiveIndex(idx)}
              />
            );
          })}
        </ul>
      ) : null}
      {error ? <div style={errorStyle}>{error}</div> : null}
    </div>
  );
}

function GroupHeader({ label }: { label: string }) {
  return (
    <li
      role="presentation"
      style={{
        padding: `${spacing.xs}px ${spacing.sm}px`,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        color: colors.textMuted,
      }}
    >
      {label}
    </li>
  );
}

function Row({
  option,
  id,
  active,
  selected,
  onPick,
  onHover,
}: {
  option: Option;
  id: string;
  active: boolean;
  selected: boolean;
  onPick: () => void;
  onHover: () => void;
}) {
  return (
    <li
      id={id}
      role="option"
      aria-selected={selected}
      // onMouseDown (no onClick): el blur del input al hacer click cerraría
      // el menú antes de que onClick dispare. mousedown gana al blur.
      onMouseDown={(e) => {
        e.preventDefault();
        onPick();
      }}
      onMouseEnter={onHover}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.xs,
        padding: `${spacing.sm}px ${spacing.sm}px`,
        borderRadius: radius.sm,
        cursor: 'pointer',
        fontSize: fontSize.sm,
        color: colors.text,
        backgroundColor: active ? colors.primarySoft : 'transparent',
        fontWeight: selected ? fontWeight.semibold : fontWeight.regular,
      }}
    >
      {option.icon ? (
        <span aria-hidden style={{ flex: '0 0 auto' }}>
          {option.icon}
        </span>
      ) : null}
      <span style={{ flex: 1, minWidth: 0 }}>{option.name}</span>
      {selected ? (
        <span aria-hidden style={{ color: colors.primary, flex: '0 0 auto' }}>
          ✓
        </span>
      ) : null}
    </li>
  );
}

const labelStyle = {
  display: 'block',
  marginBottom: spacing.xs,
  fontSize: fontSize.sm,
  fontWeight: fontWeight.medium,
  color: colors.text,
} as const;

const controlStyle = {
  width: '100%',
  padding: `${spacing.sm}px ${spacing.sm}px`,
  borderRadius: radius.sm,
  border: `1px solid ${colors.border}`,
  fontSize: fontSize.md,
  backgroundColor: colors.surface,
  color: colors.text,
  boxSizing: 'border-box' as const,
} as const;

const errorStyle = {
  marginTop: spacing.xs,
  fontSize: fontSize.xs,
  color: colors.danger,
} as const;
