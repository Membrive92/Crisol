import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type { Category } from '@crisol/types';

import { CategoryCombobox } from './category-combobox';

function cat(
  id: string,
  name: string,
  kind: 'income' | 'expense',
  isTransfer = false,
): Category {
  return {
    id,
    user_id: 'u-1',
    name,
    kind,
    is_transfer: isTransfer,
    role: isTransfer ? 'TRANSFER' : 'GENERIC',
    icon: null,
    color: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  };
}

const categories: Category[] = [
  cat('inc-1', 'Bizum recibido', 'income'),
  cat('inc-2', 'Nómina', 'income'),
  cat('exp-1', 'Comidas fuera', 'expense'),
  cat('exp-2', 'Inglés', 'expense'),
  cat('exp-3', 'Juegos (Ocio)', 'expense'),
  cat('tr-in', 'Transferencia a favor', 'income', true),
  cat('tr-out', 'Transferencias', 'expense', true),
];

function setup(value = '', onChange = vi.fn()) {
  render(
    <CategoryCombobox
      label="Categoría"
      categories={categories}
      value={value}
      onChange={onChange}
    />,
  );
  return { onChange, input: screen.getByRole('combobox') };
}

describe('CategoryCombobox', () => {
  it('al abrir muestra los grupos Ingresos/Gastos y "Sin categoría"', async () => {
    const user = userEvent.setup();
    const { input } = setup();
    await user.click(input);
    expect(screen.getByText('Ingresos')).toBeDefined();
    expect(screen.getByText('Gastos')).toBeDefined();
    expect(screen.getByRole('option', { name: /Sin categoría/ })).toBeDefined();
    expect(screen.getByRole('option', { name: /Comidas fuera/ })).toBeDefined();
  });

  it('la búsqueda filtra y oculta el grupo sin coincidencias', async () => {
    const user = userEvent.setup();
    const { input } = setup();
    await user.click(input);
    await user.type(input, 'comid');
    expect(screen.getByRole('option', { name: /Comidas fuera/ })).toBeDefined();
    expect(screen.queryByText('Nómina')).toBeNull();
    // No hay ingresos que coincidan → el header "Ingresos" desaparece.
    expect(screen.queryByText('Ingresos')).toBeNull();
  });

  it('la búsqueda es tolerante a acentos ("ingles" encuentra "Inglés")', async () => {
    const user = userEvent.setup();
    const { input } = setup();
    await user.click(input);
    await user.type(input, 'ingles');
    expect(screen.getByRole('option', { name: /Inglés/ })).toBeDefined();
  });

  it('seleccionar una opción con click emite su id', async () => {
    const user = userEvent.setup();
    const { input, onChange } = setup();
    await user.click(input);
    await user.click(screen.getByRole('option', { name: /Comidas fuera/ }));
    expect(onChange).toHaveBeenCalledWith('exp-1');
  });

  it('seleccionar "Sin categoría" emite cadena vacía', async () => {
    const user = userEvent.setup();
    const { input, onChange } = setup('exp-1');
    await user.click(input);
    await user.click(screen.getByRole('option', { name: /Sin categoría/ }));
    expect(onChange).toHaveBeenCalledWith('');
  });

  it('las categorías is_transfer van a su propio grupo "Transferencias", no a Ingresos/Gastos', async () => {
    const user = userEvent.setup();
    const { input } = setup();
    await user.click(input);
    const lis = Array.from(document.querySelectorAll('li')).map((li) => li.textContent ?? '');
    const iTransferHeader = lis.indexOf('Transferencias');
    const iIncomeHeader = lis.indexOf('Ingresos');
    const iTransferOpt = lis.findIndex((t) => t.includes('Transferencia a favor'));
    expect(iTransferHeader).toBeGreaterThan(-1);
    // "Transferencia a favor" (income + is_transfer) cae bajo el grupo
    // Transferencias, que va DESPUÉS de Ingresos, no dentro de él.
    expect(iTransferHeader).toBeGreaterThan(iIncomeHeader);
    expect(iTransferOpt).toBeGreaterThan(iTransferHeader);
  });

  it('navegación con teclado: flecha abajo + Enter selecciona', async () => {
    const user = userEvent.setup();
    const { input, onChange } = setup();
    await user.click(input); // abre; activeIndex=0 → "Sin categoría"
    await user.keyboard('{ArrowDown}'); // → primer ingreso (Bizum recibido)
    await user.keyboard('{Enter}');
    expect(onChange).toHaveBeenCalledWith('inc-1');
  });

  it('con hideLabel conserva el nombre accesible (uso inline en imports)', () => {
    // El preview de import lo usa por fila con el concepto del banco como
    // label oculto: no debe verse pero sí seguir nombrando al combobox.
    render(
      <CategoryCombobox
        label="Categoría para NÓMINA EMPRESA SL"
        hideLabel
        categories={categories}
        value=""
        onChange={vi.fn()}
      />,
    );
    expect(
      screen.getByRole('combobox', { name: 'Categoría para NÓMINA EMPRESA SL' }),
    ).toBeDefined();
  });
});
