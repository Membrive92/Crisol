import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { Stack } from 'expo-router';

import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';

import { CycleSettings } from '../../../components/settings/cycle-settings';

/**
 * C2 (decisión D4 del plan) — Ajustes en móvil. Hoy sólo «tu mes».
 *
 * Móvil no tenía pantalla de Ajustes: los enlaces a Categorías, Cuentas y
 * Presupuestos cuelgan de la cabecera de Análisis. Ésta es la primera, y nace
 * con el ajuste que la necesita: el día en que empieza el mes del usuario es un
 * dato de PERFIL (vive en el servidor), así que tiene que poder configurarse
 * desde el dispositivo con el que el usuario mira sus cuentas, no sólo desde la
 * web.
 *
 * La pantalla es una cáscara a propósito, igual que su gemela web
 * (`apps/web/app/(app)/settings/cycle/page.tsx`): todo el comportamiento vive en
 * `components/settings/`, que es donde puede probarse sin arrastrar el router.
 */
export default function SettingsScreen() {
  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: 'Ajustes' }} />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.heading}>Tu mes</Text>
        <Text style={styles.intro}>
          Decide en qué día empieza tu mes. Es un ajuste de presentación: cambia
          por dónde se cortan los períodos, no tus datos.
        </Text>
        <CycleSettings />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  heading: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  intro: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    lineHeight: 18,
    marginBottom: spacing.md,
  },
});
