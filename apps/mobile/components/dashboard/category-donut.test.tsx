// @types/jest expone los globals (describe/it/expect) — sin import.
import { render } from '@testing-library/react-native';

// `react-native-gifted-charts` arrastra un paquete ESM que el
// `transformIgnorePatterns` de la app no transforma, y `expo-router` exige un
// contenedor de navegación. Ninguno interviene en lo que se comprueba aquí
// (mismo patrón que `analysis.test.tsx`).
jest.mock('react-native-gifted-charts', () => ({
  BarChart: () => null,
  LineChart: () => null,
  PieChart: () => null,
}));

jest.mock('expo-router', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
}));

import { CategoryDonut } from './category-donut';

/*
 * PHASE-47.E4 — el aviso de lo aplazado, en móvil.
 *
 * Vivía en la pantalla de Análisis y citaba el total del periodo. El filtro
 * estructural/puntual es estado de ESTE componente, así que desde fuera no
 * había forma de saber qué se está mostrando: bajo «Fijo» el aviso hablaba de
 * un conjunto que no estaba en pantalla. Ahora vive aquí y se deriva de las
 * filas visibles.
 *
 * El donut de `react-native-gifted-charts` no pinta nada útil en jsdom, pero
 * los textos sí se renderizan, que es lo que se comprueba.
 */

function fila(id: string, name: string, total: string, deferred?: string) {
  return {
    category_id: id,
    category_name: name,
    category_kind: 'expense' as const,
    category_color: null,
    category_icon: null,
    total,
    count: 1,
    // El caso «backend anterior al campo» se escribe OMITIENDO la clave.
    ...(deferred === undefined ? {} : { deferred_total: deferred }),
  };
}

const NOOP = jest.fn();

describe('CategoryDonut · aviso de aplazado', () => {
  it('lo explica cuando hay gasto aplazado en pantalla', () => {
    const { getByTestId } = render(
      <CategoryDonut
        data={[fila('a', 'Supermercado', '208.29', '87.73')]}
        currency="EUR"
        isLoading={false}
        kind="expense"
        onKindChange={NOOP}
      />,
    );
    expect(getByTestId('deferred-notice').props.children).toContain('87,73');
  });

  it('no lo pinta sobre el donut de INGRESOS', () => {
    // Sería un pie de foto que no describe lo que hay encima.
    //
    // La fila NO declara `deferred_total` a propósito: así el aviso caería al
    // total del periodo y SÍ se pintaría si la guarda desapareciera. Con una
    // fila a '0' el test pasaba por el cero, no por la guarda — verificado
    // rompiéndola: seguía verde.
    const { queryByTestId } = render(
      <CategoryDonut
        data={[fila('a', 'Nómina', '2520.68')]}
        currency="EUR"
        isLoading={false}
        kind="income"
        onKindChange={NOOP}
        deferredExpenses="87.73"
      />,
    );
    expect(queryByTestId('deferred-notice')).toBeNull();
  });

  it('marca la categoría aplazada con un asterisco Y con su importe', () => {
    // En táctil no hay hover: si la marca no trae su explicación en texto, no
    // hay forma de abrirla (lección PHASE-44.15).
    const { getByText, queryByText } = render(
      <CategoryDonut
        data={[fila('a', 'Supermercado', '208.29', '87.73'), fila('b', 'Psicologa', '65.00', '0')]}
        currency="EUR"
        isLoading={false}
        kind="expense"
        onKindChange={NOOP}
      />,
    );
    expect(getByText('Supermercado *')).toBeTruthy();
    expect(queryByText('Psicologa *')).toBeNull();
  });

  it('cae al total del periodo cuando el backend no manda el dato por categoría', () => {
    const { getByTestId } = render(
      <CategoryDonut
        data={[fila('a', 'Supermercado', '208.29')]}
        currency="EUR"
        isLoading={false}
        kind="expense"
        onKindChange={NOOP}
        deferredExpenses="87.73"
      />,
    );
    expect(getByTestId('deferred-notice').props.children).toContain('87,73');
  });
});
