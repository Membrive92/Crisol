'use client';

import { useEffect, useRef, useState } from 'react';

import { useUserCurrencies } from '@finanzas/services';
import { useCurrencyStore } from '@finanzas/store';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { CheckCircleIcon, ChevronDownIcon, WalletIcon } from '@/components/ui/icons';

// Símbolos para las monedas más comunes. Para el resto se muestra el
// código (USD, MXN, …) — sigue siendo identificable y evita mantener
// una tabla exhaustiva. Esta lista cubre el 99% del MVP (España + viajes
// frecuentes); ampliar es trivial cuando llegue un usuario que lo pida.
const CURRENCY_SYMBOL: Record<string, string> = {
  EUR: '€',
  USD: '$',
  GBP: '£',
  JPY: '¥',
  CHF: 'Fr',
  CNY: '¥',
  CAD: '$',
  AUD: '$',
  MXN: '$',
  BRL: 'R$',
};

function symbolFor(code: string): string {
  return CURRENCY_SYMBOL[code] ?? code;
}

// Monedas siempre visibles en el selector aunque el usuario aún no
// tenga transacciones en ellas. EUR + USD cubren el caso común
// (España + viajes / suscripciones). Si el usuario tiene otras (GBP,
// JPY, …) se añaden dinámicamente al final.
const BASE_CURRENCIES = ['EUR', 'USD'] as const;

/**
 * Selector de moneda global. Vive en el header como dropdown del icono
 * cartera. Lee/escribe `useCurrencyStore` (persistido en localStorage),
 * así que cambiar la moneda se refleja en Dashboard, Análisis y
 * Transacciones a la vez.
 *
 * Sincroniza la moneda activa con las que el usuario tiene en BD: si
 * la activa no está entre las suyas (p. ej. nuevo dispositivo), se
 * cambia a la primera disponible. Esta lógica antes vivía duplicada en
 * cada página.
 */
export function CurrencyMenu() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const currency = useCurrencyStore((s) => s.currency);
  const setCurrency = useCurrencyStore((s) => s.setCurrency);
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const setConvertAll = useCurrencyStore((s) => s.setConvertAll);
  const currenciesQuery = useUserCurrencies();
  const userCurrencies = currenciesQuery.data;

  // Sync de seguridad: si la moneda persistida queda fuera tanto de
  // BASE como de las del usuario (p. ej. localStorage viejo con un
  // código que ya no usa nadie), la corregimos a la primera del
  // usuario. NO actuamos si la moneda activa está en BASE — el usuario
  // puede haber seleccionado USD sin tener aún datos en USD y respeta-
  // mos esa elección. Sólo dependemos de `userCurrencies`: reaccionar
  // a `currency` aquí provocaría loop con el setter.
  useEffect(() => {
    if (!userCurrencies || userCurrencies.length === 0) return;
    const active = useCurrencyStore.getState().currency;
    const inBase = (BASE_CURRENCIES as readonly string[]).includes(active);
    if (inBase) return;
    if (!userCurrencies.includes(active)) {
      setCurrency(userCurrencies[0] ?? 'EUR');
    }
  }, [userCurrencies, setCurrency]);

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

  // Lista a mostrar: BASE (EUR+USD) + las que el usuario ya tenga en
  // datos + la activa si fuera distinta. Sin duplicados, conservando
  // el orden de aparición (BASE primero).
  const merged = [
    ...BASE_CURRENCIES,
    ...(userCurrencies ?? []),
    currency,
  ];
  const options = Array.from(new Set(merged));

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Moneda activa: ${currency}. Cambiar.`}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          height: 36,
          padding: `0 ${spacing.sm}px`,
          backgroundColor: open ? colors.surfaceMuted : 'transparent',
          color: open ? colors.text : colors.textMuted,
          border: 'none',
          borderRadius: 8,
          cursor: 'pointer',
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          transition: 'background-color 120ms ease, color 120ms ease',
        }}
      >
        <WalletIcon size={18} />
        <span>{currency}</span>
        <ChevronDownIcon size={12} style={{ color: colors.textSubtle }} />
      </button>

      {open && (
        <div
          role="menu"
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            right: 0,
            minWidth: 200,
            backgroundColor: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            boxShadow: '0 12px 32px rgba(0, 0, 0, 0.32)',
            zIndex: 60,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              padding: `${spacing.sm}px ${spacing.md}px`,
              borderBottom: `1px solid ${colors.border}`,
              fontSize: 11,
              fontWeight: fontWeight.semibold,
              color: colors.textSubtle,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Moneda
          </div>
          <div style={{ padding: spacing.xs }}>
            {options.map((code) => (
              <CurrencyItem
                key={code}
                code={code}
                active={code === currency}
                onSelect={() => {
                  setCurrency(code);
                  setOpen(false);
                }}
              />
            ))}
          </div>

          {/* Toggle de conversión cross-currency. ON (default) suma
              todas las monedas convertidas a la activa; OFF mantiene
              el filtrado pre-PHASE-8.2. */}
          <div
            style={{
              borderTop: `1px solid ${colors.border}`,
              padding: `${spacing.sm}px ${spacing.md}px`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: spacing.sm,
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span
                style={{
                  fontSize: fontSize.sm,
                  fontWeight: fontWeight.medium,
                  color: colors.text,
                }}
              >
                Convertir todas las monedas
              </span>
              <span
                style={{
                  fontSize: fontSize.xs,
                  color: colors.textSubtle,
                  marginTop: 2,
                }}
              >
                Suma cross-currency a {currency}.
              </span>
            </div>
            <Toggle
              checked={convertAll}
              onChange={setConvertAll}
              ariaLabel="Convertir todas las monedas"
            />
          </div>
        </div>
      )}
    </div>
  );
}

function Toggle({
  checked,
  onChange,
  ariaLabel,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      onClick={() => onChange(!checked)}
      style={{
        width: 36,
        height: 20,
        borderRadius: 999,
        border: `1px solid ${checked ? colors.primary : colors.border}`,
        backgroundColor: checked ? colors.primary : colors.surfaceMuted,
        position: 'relative',
        cursor: 'pointer',
        padding: 0,
        flex: '0 0 auto',
        transition: 'background-color 120ms ease, border-color 120ms ease',
      }}
    >
      <span
        aria-hidden
        style={{
          position: 'absolute',
          top: 1,
          left: checked ? 17 : 1,
          width: 16,
          height: 16,
          borderRadius: '50%',
          backgroundColor: checked ? colors.onPrimary : colors.text,
          transition: 'left 120ms ease',
        }}
      />
    </button>
  );
}

function CurrencyItem({
  code,
  active,
  onSelect,
}: {
  code: string;
  active: boolean;
  onSelect: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const bg = active ? colors.primarySoft : hovered ? colors.surfaceMuted : 'transparent';
  const fg = active ? colors.primary : colors.text;

  return (
    <button
      type="button"
      role="menuitemradio"
      aria-checked={active}
      onClick={onSelect}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.sm,
        padding: `${spacing.sm}px ${spacing.sm + 4}px`,
        backgroundColor: bg,
        color: fg,
        border: 'none',
        borderRadius: radius.sm,
        fontSize: fontSize.sm,
        fontWeight: active ? fontWeight.semibold : fontWeight.medium,
        cursor: 'pointer',
        width: '100%',
        textAlign: 'left',
        transition: 'background-color 120ms ease, color 120ms ease',
      }}
    >
      {/* Glyph circular con el símbolo de la moneda — equivalente a
          un "logo" sin tener que mantener SVGs por cada divisa. */}
      <span
        aria-hidden
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 28,
          height: 28,
          borderRadius: '50%',
          backgroundColor: active ? colors.primary : colors.surfaceMuted,
          color: active ? colors.onPrimary : colors.text,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.bold,
          flex: '0 0 auto',
        }}
      >
        {symbolFor(code)}
      </span>
      <span style={{ flex: 1 }}>{code}</span>
      {active ? <CheckCircleIcon size={14} /> : null}
    </button>
  );
}
