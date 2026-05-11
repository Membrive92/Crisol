import { Tabs } from 'expo-router';

import { getModule } from '@crisol/types';
import { colors } from '@crisol/ui';

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
        name="analysis"
        options={{
          title: 'Análisis',
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
