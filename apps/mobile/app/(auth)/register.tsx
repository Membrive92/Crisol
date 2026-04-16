import { useState } from 'react';
import { Alert, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { Link } from 'expo-router';

import { authApi } from '@finanzas/services';
import { useAuthStore } from '@finanzas/store';

export default function RegisterScreen() {
  const { setTokens, setUser } = useAuthStore();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleRegister() {
    setLoading(true);
    try {
      const tokens = await authApi.register({
        email,
        password,
        display_name: displayName,
      });
      setTokens(tokens.access_token, tokens.refresh_token);
      const user = await authApi.getMe();
      setUser(user);
    } catch {
      Alert.alert('Error', 'No se pudo registrar. ¿El email ya está en uso?');
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Crear cuenta</Text>
      <TextInput
        style={styles.input}
        placeholder="Nombre"
        value={displayName}
        onChangeText={setDisplayName}
      />
      <TextInput
        style={styles.input}
        placeholder="Email"
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
      />
      <TextInput
        style={styles.input}
        placeholder="Contraseña (mín. 8 caracteres)"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />
      <TouchableOpacity style={styles.button} onPress={handleRegister} disabled={loading}>
        <Text style={styles.buttonText}>{loading ? 'Registrando...' : 'Registrarse'}</Text>
      </TouchableOpacity>
      <Link href="/(auth)/login" style={styles.link}>
        ¿Ya tienes cuenta? Inicia sesión
      </Link>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24 },
  title: { fontSize: 24, fontWeight: '600', textAlign: 'center', marginBottom: 24 },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 14,
    fontSize: 16,
    marginBottom: 12,
  },
  button: {
    backgroundColor: '#1976d2',
    borderRadius: 8,
    padding: 14,
    alignItems: 'center',
    marginTop: 4,
  },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  link: { marginTop: 16, textAlign: 'center', color: '#1976d2', fontSize: 14 },
});
