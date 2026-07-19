'use client';

import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import {
  CalendarIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@/components/ui/icons';

export interface DatePickerProps {
  /** Valor `YYYY-MM-DD` o `null`. */
  value: string | null;
  onChange: (value: string) => void;
  /** Límites inclusivos `YYYY-MM-DD` (deshabilitan días fuera de rango). */
  min?: string | null | undefined;
  max?: string | null | undefined;
  ariaLabel?: string | undefined;
}

const MONTHS_LONG = [
  'Enero',
  'Febrero',
  'Marzo',
  'Abril',
  'Mayo',
  'Junio',
  'Julio',
  'Agosto',
  'Septiembre',
  'Octubre',
  'Noviembre',
  'Diciembre',
] as const;

/** Semana empieza en lunes (L M X J V S D). */
const WEEKDAYS = ['L', 'M', 'X', 'J', 'V', 'S', 'D'] as const;

const DAY_MS = 86_400_000;
/** Ancho fijo del popover del calendario (px). */
const POPOVER_WIDTH = 252;
/** Margen de seguridad al borde del viewport antes de voltear la alineación. */
const VIEWPORT_MARGIN = 8;

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

/** `YYYY-MM-DD` → `DD/MM/YYYY`. */
function formatDisplay(value: string | null): string {
  if (!value) return 'dd/mm/aaaa';
  const [y, m, d] = value.split('-');
  return `${d}/${m}/${y}`;
}

/** Día de HOY como `YYYY-MM-DD` en hora local. Exportado para que otros
 * controles (navegador de período, seeds de rango) usen el mismo tope y no
 * dejen elegir fechas futuras. */
export function todayDayStr(): string {
  const now = new Date();
  return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
}

/**
 * Último día SELECCIONABLE del rango personalizado: fin del último mes con
 * datos (`availableTo`, `YYYY-MM`), nunca posterior a hoy. Sin datos → hoy.
 * Así el calendario no deja elegir días sin datos (p. ej. el mes en curso
 * aún sin importar).
 */
export function dataMaxDayStr(availableTo: string | null | undefined): string {
  const today = todayDayStr();
  if (!availableTo) return today;
  const [y, m] = availableTo.split('-').map(Number);
  const lastDay = new Date(Date.UTC(y ?? 1970, m ?? 1, 0)).getUTCDate();
  const endOfMonth = `${availableTo}-${pad2(lastDay)}`;
  return endOfMonth < today ? endOfMonth : today;
}

/** Primer día SELECCIONABLE: inicio del primer mes con datos (`availableFrom`,
 * `YYYY-MM`). Sin datos → `null` (sin tope inferior). */
export function dataMinDayStr(availableFrom: string | null | undefined): string | null {
  return availableFrom ? `${availableFrom}-01` : null;
}

interface Cell {
  key: string;
  /** `YYYY-MM-DD` */
  dayStr: string;
  day: number;
  currentMonth: boolean;
  disabled: boolean;
  selected: boolean;
  today: boolean;
}

/**
 * PHASE-41 — Date-picker propio (marca copper) que reemplaza al
 * `<input type="date">` nativo, cuyo desplegable no es estilable. Calendario
 * mensual con navegación, selección de un día y límites min/max. Cálculo en
 * UTC (aritmética de días sin DST) — sólo maneja day-strings, sin hora.
 */
export function DatePicker({ value, onChange, min, max, ariaLabel }: DatePickerProps) {
  const [open, setOpen] = useState(false);
  // El popover se ancla a la izq. del disparador por defecto; si abriéndose así
  // se saldría del viewport (picker pegado al borde derecho), se ancla a la
  // derecha. Se decide al ABRIR midiendo la posición del disparador.
  const [alignRight, setAlignRight] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Mes visible: el del valor, o el de hoy si no hay valor.
  const initial = value ?? todayDayStr();
  const [view, setView] = useState<{ year: number; month: number }>(() => ({
    year: Number(initial.slice(0, 4)),
    month: Number(initial.slice(5, 7)),
  }));

  // Al reabrir: re-centrar el mes visible en el valor y decidir la alineación
  // horizontal del popover según el espacio disponible en el viewport.
  useEffect(() => {
    if (!open) return;
    if (value) {
      setView({ year: Number(value.slice(0, 4)), month: Number(value.slice(5, 7)) });
    }
    if (containerRef.current) {
      const { left } = containerRef.current.getBoundingClientRect();
      setAlignRight(left + POPOVER_WIDTH > window.innerWidth - VIEWPORT_MARGIN);
    }
    // Sólo al ABRIR (deps intencionadamente `[open]`).
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onDocMouseDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onDocMouseDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocMouseDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const today = todayDayStr();
  const cells = useMemo<Cell[]>(() => {
    const firstMs = Date.UTC(view.year, view.month - 1, 1);
    const dow = new Date(firstMs).getUTCDay(); // 0=domingo
    const mondayIndex = (dow + 6) % 7;
    const gridStart = firstMs - mondayIndex * DAY_MS;
    const out: Cell[] = [];
    for (let i = 0; i < 42; i++) {
      const d = new Date(gridStart + i * DAY_MS);
      const cy = d.getUTCFullYear();
      const cm = d.getUTCMonth() + 1;
      const cd = d.getUTCDate();
      const dayStr = `${cy}-${pad2(cm)}-${pad2(cd)}`;
      out.push({
        key: dayStr,
        dayStr,
        day: cd,
        currentMonth: cm === view.month && cy === view.year,
        disabled: (min != null && dayStr < min) || (max != null && dayStr > max),
        selected: value != null && dayStr === value,
        today: dayStr === today,
      });
    }
    return out;
  }, [view, min, max, value, today]);

  function stepMonth(direction: 1 | -1) {
    setView((v) => {
      const total = v.year * 12 + (v.month - 1) + direction;
      return { year: Math.floor(total / 12), month: (total % 12) + 1 };
    });
  }

  function pick(cell: Cell) {
    if (cell.disabled) return;
    onChange(cell.dayStr);
    setOpen(false);
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={ariaLabel}
        aria-haspopup="dialog"
        aria-expanded={open}
        style={triggerStyle(open)}
      >
        <span style={{ fontVariantNumeric: 'tabular-nums', color: value ? colors.text : colors.textSubtle }}>
          {formatDisplay(value)}
        </span>
        <CalendarIcon size={15} style={{ color: colors.textMuted, flex: '0 0 auto' }} />
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label="Elegir fecha"
          style={{ ...popoverStyle, ...(alignRight ? { right: 0 } : { left: 0 }) }}
        >
          <div style={headerStyle}>
            <button
              type="button"
              onClick={() => stepMonth(-1)}
              aria-label="Mes anterior"
              style={navBtnStyle}
            >
              <ChevronLeftIcon size={16} />
            </button>
            <span style={{ fontSize: fontSize.sm, fontWeight: fontWeight.semibold, color: colors.text }}>
              {MONTHS_LONG[view.month - 1]} {view.year}
            </span>
            <button
              type="button"
              onClick={() => stepMonth(1)}
              aria-label="Mes siguiente"
              style={navBtnStyle}
            >
              <ChevronRightIcon size={16} />
            </button>
          </div>

          <div style={gridStyle}>
            {WEEKDAYS.map((w) => (
              <span key={w} style={weekdayStyle}>
                {w}
              </span>
            ))}
            {cells.map((cell) => (
              <button
                key={cell.key}
                type="button"
                disabled={cell.disabled}
                onClick={() => pick(cell)}
                aria-pressed={cell.selected}
                aria-current={cell.today ? 'date' : undefined}
                style={dayStyle(cell)}
              >
                {cell.day}
              </button>
            ))}
          </div>

          <div style={footerStyle}>
            <button
              type="button"
              onClick={() => {
                setView({ year: Number(today.slice(0, 4)), month: Number(today.slice(5, 7)) });
              }}
              style={todayBtnStyle}
            >
              Hoy
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

/* ---------- estilos (tokens) ---------- */

function triggerStyle(open: boolean): CSSProperties {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: spacing.sm,
    padding: '5px 10px',
    borderRadius: radius.sm,
    border: `1px solid ${open ? colors.primary : colors.border}`,
    backgroundColor: colors.surface,
    color: colors.text,
    fontSize: fontSize.sm,
    cursor: 'pointer',
    lineHeight: 1.2,
  };
}

const popoverStyle: CSSProperties = {
  position: 'absolute',
  top: 'calc(100% + 6px)',
  zIndex: 200,
  width: POPOVER_WIDTH,
  padding: spacing.sm,
  backgroundColor: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  boxShadow: '0 12px 32px rgba(0, 0, 0, 0.35)',
};

const headerStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: spacing.xs,
};

const navBtnStyle: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 28,
  height: 28,
  borderRadius: radius.sm,
  border: `1px solid ${colors.border}`,
  backgroundColor: colors.surface,
  color: colors.text,
  cursor: 'pointer',
  padding: 0,
};

const gridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(7, 1fr)',
  gap: 2,
};

const weekdayStyle: CSSProperties = {
  display: 'grid',
  placeItems: 'center',
  height: 26,
  fontSize: 11,
  fontWeight: fontWeight.semibold,
  color: colors.textSubtle,
};

function dayStyle(cell: Cell): CSSProperties {
  const base: CSSProperties = {
    display: 'grid',
    placeItems: 'center',
    height: 30,
    borderRadius: radius.sm,
    border: cell.today && !cell.selected ? `1px solid ${colors.primary}` : '1px solid transparent',
    backgroundColor: cell.selected ? colors.primary : 'transparent',
    color: cell.selected
      ? colors.onPrimary
      : cell.disabled
        ? colors.textSubtle
        : cell.currentMonth
          ? colors.text
          : colors.textSubtle,
    fontSize: fontSize.sm,
    fontVariantNumeric: 'tabular-nums',
    fontWeight: cell.selected ? fontWeight.semibold : fontWeight.medium,
    cursor: cell.disabled ? 'not-allowed' : 'pointer',
    opacity: cell.disabled ? 0.4 : 1,
  };
  return base;
}

const footerStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'flex-end',
  marginTop: spacing.xs,
  paddingTop: spacing.xs,
  borderTop: `1px solid ${colors.border}`,
};

const todayBtnStyle: CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: colors.primary,
  fontSize: fontSize.xs,
  fontWeight: fontWeight.semibold,
  cursor: 'pointer',
  padding: `2px ${spacing.xs}px`,
};
