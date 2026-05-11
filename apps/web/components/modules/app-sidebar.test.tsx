import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { getModule } from '@crisol/types';

import { AppSidebar } from './app-sidebar';

const personalFinance = getModule('personal-finance')!;

describe('AppSidebar', () => {
  it('expone data-mobile-open=false por defecto', () => {
    const { container } = render(<AppSidebar active={personalFinance} />);
    const aside = container.querySelector('[data-app-sidebar]');
    expect(aside).not.toBeNull();
    expect(aside?.getAttribute('data-mobile-open')).toBe('false');
  });

  it('refleja mobileOpen=true en data-mobile-open', () => {
    const { container } = render(<AppSidebar active={personalFinance} mobileOpen />);
    const aside = container.querySelector('[data-app-sidebar]');
    expect(aside?.getAttribute('data-mobile-open')).toBe('true');
  });

  it('llama onCloseMobile al pulsar el botón "Cerrar menú"', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <AppSidebar active={personalFinance} mobileOpen onCloseMobile={onClose} />,
    );
    // El botón tiene `display: none` inline (la media query global del
    // layout lo eleva a `inline-flex` en mobile, pero jsdom no aplica
    // media queries). Como el botón está oculto, los queries por
    // role/name lo descartan; usamos getByLabelText que sí lo
    // localiza vía aria-label directamente.
    await user.click(screen.getByLabelText(/cerrar menú/i));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
