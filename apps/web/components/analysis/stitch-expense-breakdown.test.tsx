import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { CategoryBreakdownItem } from '@crisol/types';

import { StitchExpenseBreakdown, StructureSegmented } from './stitch-expense-breakdown';

// El desglose navega al drill-down de categoría con `useRouter`; en jsdom no
// hay AppRouterContext, así que lo mockeamos a un push no-op (mismo patrón que
// `transaction-list.test.tsx`).
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

function item(
  id: string | null,
  name: string,
  total: string,
  deferred?: string,
): CategoryBreakdownItem {
  return {
    category_id: id,
    category_name: name,
    category_kind: 'expense',
    category_color: null,
    category_icon: null,
    total,
    count: 1,
    // El caso «backend anterior al campo» se escribe OMITIENDO la clave, no
    // poniéndola a null: con null el test pasa igual y no prueba nada.
    ...(deferred === undefined ? {} : { deferred_total: deferred }),
  };
}

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

  it('marca QUÉ categorías están aplazadas, y sólo ésas', () => {
    // El aviso decía cuánto, no dónde. Con nueve categorías en pantalla no hay
    // forma de saber cuál explica la diferencia con el resultado del mes.
    render(
      <StitchExpenseBreakdown
        items={[item('a', 'Supermercado', '208.29', '87.73'), item('b', 'Psicologa', '65.00', '0')]}
        currency="EUR"
        isLoading={false}
        deferredExpenses="87.73"
      />,
    );

    const marcas = screen.getAllByTestId('deferred-category-mark');
    expect(marcas).toHaveLength(1);
    expect(marcas[0]?.getAttribute('title')).toContain('87,73');
  });

  it('no marca nada cuando el backend todavía no manda el dato', () => {
    // `campo !== null` habría marcado TODAS las filas: `undefined !== null`.
    render(
      <StitchExpenseBreakdown
        items={[item('a', 'Supermercado', '208.29')]}
        currency="EUR"
        isLoading={false}
        deferredExpenses="87.73"
      />,
    );

    expect(screen.queryByTestId('deferred-category-mark')).toBeNull();
    // …pero el aviso global sigue, porque el total del periodo SÍ se sabe.
    expect(screen.getByTestId('deferred-notice').textContent).toContain('87,73');
  });

  it('el importe del aviso describe lo que hay EN PANTALLA, no el periodo', () => {
    // Con datos reales de junio el aviso decía «496,67 € aplazados» bajo el
    // filtro Fijo, cuando en pantalla sólo había 245,53 € de ellos: los otros
    // viven en categorías variables que ese filtro no enseña.
    const items = [
      item('sup', 'Supermercado', '208.29', '87.73'),
      item('ropa', 'Ropa', '219.15', '219.15'),
    ];
    const puntual = [
      {
        category_id: 'ropa',
        category_name: 'Ropa',
        color: null,
        icon: null,
        total: '219.15',
        deferred_total: '219.15',
      },
    ];

    const { rerender } = render(
      <StitchExpenseBreakdown
        items={items}
        currency="EUR"
        isLoading={false}
        deferredExpenses="306.88"
        exceptionalByCategory={puntual}
        filter="all"
        onFilterChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId('deferred-notice').textContent).toContain('306,88');

    rerender(
      <StitchExpenseBreakdown
        items={items}
        currency="EUR"
        isLoading={false}
        deferredExpenses="306.88"
        exceptionalByCategory={puntual}
        filter="structural"
        onFilterChange={vi.fn()}
      />,
    );
    // Fijo = todo − puntual: sólo queda Supermercado, con sus 87,73 €.
    expect(screen.getByTestId('deferred-notice').textContent).toContain('87,73');
    expect(screen.getByTestId('deferred-notice').textContent).not.toContain('306,88');

    rerender(
      <StitchExpenseBreakdown
        items={items}
        currency="EUR"
        isLoading={false}
        deferredExpenses="306.88"
        exceptionalByCategory={puntual}
        filter="exceptional"
        onFilterChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId('deferred-notice').textContent).toContain('219,15');
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
