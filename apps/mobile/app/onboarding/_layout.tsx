import { Stack } from 'expo-router';

/**
 * Layout standalone para el flujo de onboarding bloqueante (PHASE-19.1).
 * Sin tabs ni headers — el usuario debe declarar al menos una cuenta
 * antes de poder navegar al resto de la app. El guard del root layout
 * empuja aquí cuando hay sesión y la lista de cuentas es vacía.
 */
export default function OnboardingLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
