import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { AnalyticsCategoryAmount, CategoryBreakdownItem } from '@crisol/types';

import {
  deriveStructural,
  StitchExpenseBreakdown,
  StructureSegmented,
} from './stitch-expense-breakdown';

// El desglose navega al drill-down de categoría con `useRouter`; en jsdom no
// hay AppRouterContext, así que lo mockeamos a un push no-op (mismo patrón que
// `transaction-list.test.tsx`).
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

function item(id: string | null, name: string, total: string): CategoryBreakdownItem {
  return {
    category_id: id,
    category_name: name,
    category_kind: 'expense',
    category_color: null,
    category_icon: null,
    total,
    count: 1,
  };
}

function exc(id: string | null, name: string, total: string): AnalyticsCategoryAmount {
  return { category_id: id, category_name: name, color: null, icon: null, total };
}

describe('deriveStructural', () => {
  it('estructural por categoría = total − puntual', () => {
    const all = [item('a', 'Super', '100.00'), item('b', 'Luz', '50.00')];
    const exceptional = [exc('a', 'Super', '30.00')];
    const out = deriveStructural(all, exceptional);
    const byId = Object.fromEntries(out.map((x) => [x.category_id, Number(x.total)]));
    expect(byId['a']).toBeCloseTo(70); // 100 − 30
    expect(byId['b']).toBeCloseTo(50); // sin puntual → todo estructural
  });

  it('descarta categorías cuyo estructural queda ~0', () => {
    const all = [item('c', 'Dentista', '20.00')];
    const exceptional = [exc('c', 'Dentista', '20.00')];
    expect(deriveStructural(all, exceptional)).toEqual([]);
  });

  it('empareja el bucket sin categoría por id nulo', () => {
    const all = [item(null, 'Sin categoría', '40.00')];
    const exceptional = [exc(null, 'Sin categoría', '40.00')];
    expect(deriveStructural(all, exceptional)).toEqual([]);
  });
});

describe('StructureSegmented', () => {
  it('renderiza las tres opciones y marca la activa', () => {
    render(<StructureSegmented value="all" onChange={vi.fn()} />);
    const todo = screen.getByRole('tab', { name: 'Todo' });
    expect(todo.getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tab', { name: 'Fijo' })).toBeTruthy();
    expect(screen.getByRole('tab', { name: 'Variable' })).toBeTruthy();
  });

  it('al pulsar una opción llama onChange con su clave', () => {
    const onChange = vi.fn();
    render(<StructureSegmented value="all" onChange={onChange} />);
    fireEvent.click(screen.getByRole('tab', { name: 'Variable' }));
    expect(onChange).toHaveBeenCalledWith('exceptional');
    fireEvent.click(screen.getByRole('tab', { name: 'Fijo' }));
    expect(onChange).toHaveBeenCalledWith('structural');
  });
});

// ── PHASE-47.E2/E3 · el aviso de gasto aplazado ──────────────────────
//
// Los meses con un recibo financiado, este desglose y el resultado del mes NO
// cuadran a propósito: el gasto se hizo (está aquí) pero el dinero no salió
// (no está allí). Si nadie lo dice, quien intente cuadrarlos concluirá que la
// app está mal — y tendrá razón en desconfiar, porque nada se lo explicaba.

describe('StitchExpenseBreakdown · aviso de aplazado', () => {
  const items = [item('a', 'Supermercado', '700.26')];

  it('lo explica cuando parte del gasto está aplazado', () => {
    render(
      <StitchExpenseBreakdown
        items={items}
        currency="EUR"
        isLoading={false}
        deferredExpenses="700.26"
      />,
    );

    const notice = screen.getByTestId('deferred-notice');
    expect(notice.textContent).toContain('700,26');
    expect(notice.textContent).toContain('no salieron de tu cuenta');
  });

  it('no pinta nada el resto de los meses', () => {
    // Que es casi siempre: un aviso permanente se convierte en ruido y deja de
    // leerse justo el mes que importa.
    render(
      <StitchExpenseBreakdown
        items={items}
        currency="EUR"
        isLoading={false}
        deferredExpenses="0"
      />,
    );

    expect(screen.queryByTestId('deferred-notice')).toBeNull();
  });
});
