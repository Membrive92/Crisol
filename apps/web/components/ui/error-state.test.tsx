import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ErrorState } from './error-state';

describe('ErrorState', () => {
  it('renderiza el rol alert con el título por defecto', () => {
    render(<ErrorState />);
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toContain('No se pudieron cargar los datos');
  });

  it('usa el título y la descripción personalizados', () => {
    render(<ErrorState title="Ups" description="Algo falló" />);
    expect(screen.getByText('Ups')).toBeDefined();
    expect(screen.getByText('Algo falló')).toBeDefined();
  });

  it('dispara onRetry al pulsar Reintentar', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);
    await user.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('no pinta botón cuando no hay onRetry', () => {
    render(<ErrorState />);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('deshabilita el botón mientras reintenta', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} retrying />);
    const button = screen.getByRole('button', { name: 'Reintentando…' });
    await user.click(button);
    expect(onRetry).not.toHaveBeenCalled();
  });
});
