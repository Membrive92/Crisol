import { describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { TrashedBanner } from './trashed-banner';

describe('TrashedBanner', () => {
  it('no renderiza nada cuando lastDeletedId es null', () => {
    render(
      <TrashedBanner lastDeletedId={null} onUndo={vi.fn()} isRestoring={false} />,
    );
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('muestra mensaje + acciones cuando hay un ID', () => {
    render(
      <TrashedBanner
        lastDeletedId="tx-1"
        onUndo={vi.fn()}
        isRestoring={false}
      />,
    );
    expect(screen.getByText(/movida a papelera/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /deshacer/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /ver papelera/i })).toBeDefined();
  });

  it('llama onUndo al pulsar Deshacer y oculta el banner', async () => {
    const user = userEvent.setup();
    const onUndo = vi.fn();
    render(
      <TrashedBanner lastDeletedId="tx-1" onUndo={onUndo} isRestoring={false} />,
    );
    await user.click(screen.getByRole('button', { name: /deshacer/i }));
    expect(onUndo).toHaveBeenCalledOnce();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('auto-dismiss tras dismissAfterMs', () => {
    vi.useFakeTimers();
    try {
      render(
        <TrashedBanner
          lastDeletedId="tx-1"
          onUndo={vi.fn()}
          isRestoring={false}
          dismissAfterMs={1000}
        />,
      );
      expect(screen.getByRole('status')).toBeDefined();
      act(() => {
        vi.advanceTimersByTime(1100);
      });
      expect(screen.queryByRole('status')).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });
});
