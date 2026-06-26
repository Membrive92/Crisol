import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type { Category } from '@crisol/types';

import { CategoryCombobox } from './category-combobox';

function cat(id: string, name: string, kind: 'income' | 'expense'): Category {
  return {
    id,
    user_id: 'u-1',
    name,
    kind,
    is_transfer: false,
    role: 'GENERIC',
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

  it('navegación con teclado: flecha abajo + Enter selecciona', async () => {
    const user = userEvent.setup();
    const { input, onChange } = setup();
    await user.click(input); // abre; activeIndex=0 → "Sin categoría"
    await user.keyboard('{ArrowDown}'); // → primer ingreso (Bizum recibido)
    await user.keyboard('{Enter}');
    expect(onChange).toHaveBeenCalledWith('inc-1');
  });
});
