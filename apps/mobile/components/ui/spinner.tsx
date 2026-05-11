import { ActivityIndicator } from 'react-native';

import { colors } from '@crisol/ui';

export interface SpinnerProps {
  size?: 'small' | 'large' | number;
  color?: string;
}

/**
 * Wrapper sobre `ActivityIndicator` con color del tema por defecto.
 * Mantiene la misma API conceptual que el spinner web (`size` + `color`).
 */
export function Spinner({ size = 'small', color }: SpinnerProps) {
  return <ActivityIndicator size={size} color={color ?? colors.primary} />;
}
