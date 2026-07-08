import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ExceptionalToggle } from './exceptional-toggle';

describe('ExceptionalToggle', () => {
  it('marca "Automático" como activo cuando value es null y lo deshabilita', () => {
    render(<ExceptionalToggle value={null} pending={false} onChange={vi.fn()} />);
    const auto = screen.getByRole('radio', { name: 'Automático' });
    expect(auto.getAttribute('aria-checked')).toBe('true');
    expect((auto as HTMLButtonElement).disabled).toBe(true);
  });

  it('envía null / false / true según la opción pulsada', () => {
    const onChange = vi.fn();
    // value=true → "Puntual" activo; las otras dos son pulsables.
    render(<ExceptionalToggle value={true} pending={false} onChange={onChange} />);
    fireEvent.click(screen.getByRole('radio', { name: 'Automático' }));
    expect(onChange).toHaveBeenCalledWith(null);
    fireEvent.click(screen.getByRole('radio', { name: 'Estructural' }));
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it('pending deshabilita todo el grupo', () => {
    render(<ExceptionalToggle value={null} pending onChange={vi.fn()} />);
    for (const name of ['Automático', 'Estructural', 'Puntual']) {
      expect((screen.getByRole('radio', { name }) as HTMLButtonElement).disabled).toBe(true);
    }
  });
});
