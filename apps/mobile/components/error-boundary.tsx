import { Component, type ErrorInfo, type ReactNode } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';

import { colors, spacing } from '@crisol/ui';

import { ErrorState } from './ui/error-state';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/**
 * Boundary de render de la app móvil. React Native no tiene un
 * equivalente a `app/error.tsx` de Next, así que envolvemos el
 * navigator en este class-component: captura cualquier excepción de
 * render y muestra un `ErrorState` con "Reintentar" en vez de
 * tumbar la app a la pantalla roja (AUDIT-2026-05).
 *
 * `reset` re-monta el subárbol; si el fallo era transitorio (datos
 * corruptos en un render puntual) la app se recupera sin reinicio.
 */
export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  override state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[mobile] unhandled render error:', error, info.componentStack);
  }

  reset = (): void => {
    this.setState({ hasError: false });
  };

  override render(): ReactNode {
    if (this.state.hasError) {
      return (
        <ScrollView
          contentContainerStyle={styles.container}
          style={{ backgroundColor: colors.background }}
        >
          <View style={styles.inner}>
            <ErrorState
              title="Algo ha ido mal"
              description="No hemos podido mostrar esta pantalla. Puedes reintentar; si el problema persiste, reinicia la app."
              onRetry={this.reset}
            />
          </View>
        </ScrollView>
      );
    }
    return this.props.children;
  }
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: spacing.lg,
  },
  inner: {
    width: '100%',
  },
});
