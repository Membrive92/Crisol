import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { TabPanel, Tabs } from './tabs';

const ITEMS = [
  { key: 'estados', label: 'Estados' },
  { key: 'ratios', label: 'Ratios' },
  { key: 'veredicto', label: 'Veredicto', badge: 3 },
];

describe('Tabs', () => {
  it('expone un tablist con nombre accesible y una sola pestaña seleccionada', () => {
    render(
      <Tabs items={ITEMS} value="ratios" onChange={vi.fn()} label="Informe" idPrefix="t" />,
    );
    expect(screen.getByRole('tablist', { name: 'Informe' })).toBeTruthy();
    expect(screen.getByRole('tab', { name: /Ratios/ }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tab', { name: /Estados/ }).getAttribute('aria-selected')).toBe(
      'false',
    );
  });

  it('se navega entera con el teclado, sin ratón', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <Tabs items={ITEMS} value="estados" onChange={onChange} label="Informe" idPrefix="t" />,
    );

    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole('tab', { name: /Estados/ }));

    await user.keyboard('{ArrowRight}');
    expect(onChange).toHaveBeenCalledWith('ratios');

    await user.keyboard('{End}');
    expect(onChange).toHaveBeenCalledWith('veredicto');

    await user.keyboard('{Home}');
    expect(onChange).toHaveBeenCalledWith('estados');
  });

  it('sólo la pestaña activa entra en el orden de tabulación', () => {
    render(
      <Tabs items={ITEMS} value="ratios" onChange={vi.fn()} label="Informe" idPrefix="t" />,
    );
    expect(screen.getByRole('tab', { name: /Ratios/ }).getAttribute('tabindex')).toBe('0');
    expect(screen.getByRole('tab', { name: /Estados/ }).getAttribute('tabindex')).toBe('-1');
  });

  it('pinta el contador de una pestaña', () => {
    render(
      <Tabs items={ITEMS} value="estados" onChange={vi.fn()} label="Informe" idPrefix="t" />,
    );
    expect(screen.getByText('3')).toBeTruthy();
  });

  it('sólo monta el panel activo: seis matrices a la vez no las ve nadie', () => {
    render(
      <>
        <TabPanel idPrefix="t" tabKey="estados" active={false}>
          <p>contenido de estados</p>
        </TabPanel>
        <TabPanel idPrefix="t" tabKey="ratios" active>
          <p>contenido de ratios</p>
        </TabPanel>
      </>,
    );
    expect(screen.queryByText('contenido de estados')).toBeNull();
    expect(screen.getByText('contenido de ratios')).toBeTruthy();
  });

  it('cablea el panel con su pestaña por aria', () => {
    render(
      <>
        <Tabs items={ITEMS} value="ratios" onChange={vi.fn()} label="Informe" idPrefix="t" />
        <TabPanel idPrefix="t" tabKey="ratios" active>
          <p>contenido</p>
        </TabPanel>
      </>,
    );
    const tab = screen.getByRole('tab', { name: /Ratios/ });
    const panel = screen.getByRole('tabpanel');
    expect(tab.getAttribute('aria-controls')).toBe(panel.id);
    expect(panel.getAttribute('aria-labelledby')).toBe(tab.id);
  });
});
