import { Tabs } from 'expo-router';

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: true,
        tabBarActiveTintColor: '#1976d2',
      }}
    >
      <Tabs.Screen
        name="home"
        options={{
          title: 'Inicio',
        }}
      />
    </Tabs>
  );
}
