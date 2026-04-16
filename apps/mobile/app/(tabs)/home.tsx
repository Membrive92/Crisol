import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

import { authApi } from '@finanzas/services';
import { useAuthStore } from '@finanzas/store';

export default function HomeScreen() {
  const { user, refreshToken, logout: clearAuth } = useAuthStore();

  async function handleLogout() {
    try {
      if (refreshToken) {
        await authApi.logout(refreshToken);
      }
    } finally {
      clearAuth();
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Bienvenido, {user?.display_name ?? 'usuario'}</Text>
      <Text style={styles.subtitle}>{user?.email}</Text>
      <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
        <Text style={styles.logoutText}>Cerrar sesión</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  title: { fontSize: 24, fontWeight: '600', marginBottom: 8 },
  subtitle: { fontSize: 14, color: '#666', marginBottom: 32 },
  logoutButton: {
    backgroundColor: '#d32f2f',
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 32,
  },
  logoutText: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
