import { Tabs } from 'expo-router';

import { getModule } from '@crisol/types';
import { colors } from '@crisol/ui';

import { ModuleHeader } from '../../../../components/modules/module-header';

const INVESTMENTS = getModule('investments');

export default function InvestmentsTabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: true,
        tabBarActiveTintColor: colors.primary,
        headerTitle: () => (INVESTMENTS ? <ModuleHeader active={INVESTMENTS} /> : null),
      }}
    >
      <Tabs.Screen name="portfolio" options={{ title: 'Cartera' }} />
      <Tabs.Screen name="analysis" options={{ title: 'Análisis' }} />
    </Tabs>
  );
}
