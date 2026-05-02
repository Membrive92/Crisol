import { Stack } from 'expo-router';

export default function PersonalFinanceLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen
        name="transaction/new"
        options={{ headerShown: true, title: 'Nueva transacción' }}
      />
      <Stack.Screen
        name="transaction/[id]"
        options={{ headerShown: true, title: 'Editar transacción' }}
      />
      <Stack.Screen
        name="receipt/new"
        options={{ headerShown: true, title: 'Subir ticket' }}
      />
      <Stack.Screen
        name="receipt/[id]"
        options={{ headerShown: true, title: 'Detalle ticket' }}
      />
    </Stack>
  );
}
