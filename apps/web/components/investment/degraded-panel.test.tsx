import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { layout } from '@crisol/ui';

import { DegradedPanel, InlineNotice } from './degraded-panel';

/**
 * El ancho de línea de la prosa (PHASE-44.24, auditoría UX).
 *
 * `InlineNotice` encabeza CADA pestaña del informe y `DegradedPanel` sustituye
 * a las secciones que no aplican. Sin límite, en un monitor de 2.400 px sus
 * frases corrían de borde a borde. Se comprueba el ESTILO calculado, no que
 * el fichero mencione `maxWidth`: un gate de presencia daría verde con el
 * límite puesto en el elemento equivocado.
 */
describe('la prosa del informe está acotada', () => {
  it('InlineNotice no pasa de layout.prose', () => {
    render(<InlineNotice>Un aviso largo</InlineNotice>);
    expect(screen.getByText('Un aviso largo').style.maxWidth).toBe(`${layout.prose}px`);
  });

  it('DegradedPanel acota el motivo y la consecuencia', () => {
    render(<DegradedPanel title="T" reason="El motivo" consequence="La consecuencia" />);
    expect(screen.getByText('El motivo').style.maxWidth).toBe(`${layout.prose}px`);
    expect(screen.getByText('La consecuencia').style.maxWidth).toBe(`${layout.prose}px`);
  });
});
