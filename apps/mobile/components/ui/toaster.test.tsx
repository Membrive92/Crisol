// @types/jest expone los globals (describe/it/expect/jest) — sin import.
import { act, fireEvent, render } from '@testing-library/react-native';

import { toast, useToastStore } from '@crisol/store';

import { Toaster } from './toaster';

afterEach(() => {
  useToastStore.getState().clear();
});

describe('Toaster (mobile)', () => {
  it('no renderiza nada cuando la queue está vacía', () => {
    const { queryByText } = render(<Toaster />);
    expect(queryByText(/./)).toBeNull();
  });

  it('muestra los toasts encolados', () => {
    const { getByText } = render(<Toaster />);
    act(() => {
      toast.success('Guardado');
    });
    expect(getByText('Guardado')).toBeTruthy();
  });

  it('llama action.onPress y oculta el toast al pulsar la acción', () => {
    const onPress = jest.fn();
    const { getByText, queryByText } = render(<Toaster />);
    act(() => {
      toast.show({
        kind: 'info',
        message: 'Movida a papelera.',
        action: { label: 'Deshacer', onPress },
      });
    });
    fireEvent.press(getByText('Deshacer'));
    expect(onPress).toHaveBeenCalledTimes(1);
    expect(queryByText('Movida a papelera.')).toBeNull();
  });

  it('cierra el toast al pulsar el botón Cerrar (×)', () => {
    const { getByLabelText, queryByText } = render(<Toaster />);
    act(() => {
      toast.success('Algo');
    });
    fireEvent.press(getByLabelText('Cerrar'));
    expect(queryByText('Algo')).toBeNull();
  });

  it('auto-dismiss tras dismissAfterMs (con fake timers)', () => {
    jest.useFakeTimers();
    try {
      const { getByText, queryByText } = render(<Toaster />);
      act(() => {
        toast.show({ kind: 'success', message: 'Ok', dismissAfterMs: 500 });
      });
      expect(getByText('Ok')).toBeTruthy();
      act(() => {
        jest.advanceTimersByTime(600);
      });
      expect(queryByText('Ok')).toBeNull();
    } finally {
      jest.useRealTimers();
    }
  });
});
