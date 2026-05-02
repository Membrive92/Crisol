import { Tabs } from 'expo-router';

import { getModule } from '@finanzas/types';
import { colors } from '@finanzas/ui';

import { ModuleHeader } from '../../../../components/modules/module-header';

const PERSONAL_FINANCE = getModule('personal-finance');

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: true,
        tabBarActiveTintColor: colors.primary,
        headerTitle: () =>
          PERSONAL_FINANCE ? <ModuleHeader active={PERSONAL_FINANCE} /> : null,
      }}
    >
      <Tabs.Screen
        name="home"
        options={{
          title: 'Dashboard',
        }}
      />
      <Tabs.Screen
        name="transactions"
        options={{
          title: 'Transacciones',
        }}
      />
      <Tabs.Screen
        name="receipts"
        options={{
          title: 'Tickets',
        }}
      />
    </Tabs>
  );
}
