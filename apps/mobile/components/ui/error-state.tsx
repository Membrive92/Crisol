import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

export interface ErrorStateProps {
  /** Título corto del error. Default genérico. */
  title?: string;
  /** Mensaje explicativo. Default genérico accionable. */
  description?: string;
  /** Handler de reintento (típicamente `query.refetch`). */
  onRetry?: (() => void) | undefined;
  /** Etiqueta del botón. Default "Reintentar". */
  retryLabel?: string;
  /** Reintento en curso (deshabilita el botón). */
  retrying?: boolean;
}

/**
 * Estado de error reutilizable para ramas `isError` (paridad con el
 * `ErrorState` web). Antes de AUDIT-2026-05 las pantallas móviles
 * mostraban "No hay datos" cuando en realidad la red había fallado.
 */
export function ErrorState({
  title = 'No se pudieron cargar los datos',
  description = 'Ha ocurrido un problema al contactar con el servidor. Comprueba tu conexión e inténtalo de nuevo.',
  onRetry,
  retryLabel = 'Reintentar',
  retrying = false,
}: ErrorStateProps) {
  return (
    <View style={styles.card} accessibilityRole="alert">
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.description}>{description}</Text>
      {onRetry ? (
        <Pressable
          onPress={onRetry}
          disabled={retrying}
          accessibilityRole="button"
          accessibilityLabel={retryLabel}
          style={({ pressed }) => [
            styles.button,
            pressed && styles.pressed,
            retrying && styles.disabled,
          ]}
        >
          <Text style={styles.buttonText}>
            {retrying ? 'Reintentando…' : retryLabel}
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.dangerSoft,
    borderColor: colors.danger,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.lg,
    alignItems: 'center',
    gap: spacing.sm,
  },
  title: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    textAlign: 'center',
  },
  description: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 20,
  },
  button: {
    marginTop: spacing.xs,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  buttonText: {
    color: colors.text,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
  pressed: {
    opacity: 0.7,
  },
  disabled: {
    opacity: 0.5,
  },
});
