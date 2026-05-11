import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { toast, useToastStore } from '@crisol/store';

import { Toaster } from './toaster';

afterEach(() => {
  useToastStore.getState().clear();
});

describe('Toaster + useToastStore', () => {
  it('no renderiza nada cuando la queue está vacía', () => {
    const { container } = render(<Toaster />);
    expect(container.querySelectorAll('[role="status"]')).toHaveLength(0);
  });

  it('muestra los toasts encolados', () => {
    render(<Toaster />);
    act(() => {
      toast.success('Guardado correctamente');
    });
    expect(screen.getByText('Guardado correctamente')).toBeDefined();
  });

  it('renderiza una acción y la dispara al pulsarla', async () => {
    const user = userEvent.setup();
    const onPress = vi.fn();
    render(<Toaster />);
    act(() => {
      toast.show({
        kind: 'info',
        message: 'Movida a papelera.',
        action: { label: 'Deshacer', onPress },
      });
    });
    await user.click(screen.getByRole('button', { name: /deshacer/i }));
    expect(onPress).toHaveBeenCalledOnce();
    // Tras pulsar la acción, el toast se cierra solo (el ToastCard
    // llama dismiss después de invocar action.onPress).
    expect(screen.queryByText('Movida a papelera.')).toBeNull();
  });

  it('cierra el toast al pulsar el botón Cerrar', async () => {
    const user = userEvent.setup();
    render(<Toaster />);
    act(() => {
      toast.success('Algo');
    });
    await user.click(screen.getByRole('button', { name: /cerrar/i }));
    expect(screen.queryByText('Algo')).toBeNull();
  });

  it('auto-dismiss tras dismissAfterMs (con fake timers)', () => {
    vi.useFakeTimers();
    try {
      render(<Toaster />);
      act(() => {
        toast.show({ kind: 'success', message: 'Ok', dismissAfterMs: 500 });
      });
      expect(screen.getByText('Ok')).toBeDefined();
      act(() => {
        vi.advanceTimersByTime(600);
      });
      expect(screen.queryByText('Ok')).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('dismissAfterMs=0 no auto-dismiss (manual sólo)', () => {
    vi.useFakeTimers();
    try {
      render(<Toaster />);
      act(() => {
        toast.show({ kind: 'error', message: 'Boom' }); // error → default 0
      });
      act(() => {
        vi.advanceTimersByTime(60_000);
      });
      expect(screen.getByText('Boom')).toBeDefined();
    } finally {
      vi.useRealTimers();
    }
  });

  it('toast con acción usa default 8s si no se pasa dismissAfterMs', () => {
    const id = toast.show({
      kind: 'info',
      message: 'X',
      action: { label: 'Y', onPress: vi.fn() },
    });
    const stored = useToastStore.getState().toasts.find((t) => t.id === id);
    expect(stored?.dismissAfterMs).toBe(8000);
  });

  it('dedupKey reemplaza el toast existente en su sitio (PHASE-15.1)', () => {
    render(<Toaster />);
    act(() => {
      toast.show({ kind: 'warning', message: 'Comida 80%', dedupKey: 'b:1' });
      toast.show({ kind: 'warning', message: 'Otro', dedupKey: 'other' });
    });
    expect(useToastStore.getState().toasts).toHaveLength(2);
    act(() => {
      toast.show({ kind: 'error', message: 'Comida 105%', dedupKey: 'b:1' });
    });
    const queue = useToastStore.getState().toasts;
    expect(queue).toHaveLength(2); // sin acumular
    expect(queue.find((t) => t.dedupKey === 'b:1')?.message).toBe('Comida 105%');
    expect(queue.find((t) => t.dedupKey === 'b:1')?.kind).toBe('error');
    // El "other" sigue en su posición original.
    expect(queue[1]?.dedupKey).toBe('other');
  });

  it('sin dedupKey los toasts se apilan como antes', () => {
    render(<Toaster />);
    act(() => {
      toast.show({ kind: 'success', message: 'A' });
      toast.show({ kind: 'success', message: 'A' }); // mismo mensaje, sin dedupKey
    });
    expect(useToastStore.getState().toasts).toHaveLength(2);
  });
});
