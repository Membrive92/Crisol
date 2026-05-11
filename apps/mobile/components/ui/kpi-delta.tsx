import { StyleSheet, Text, View } from 'react-native';

import { colors, fontSize, fontWeight } from '@crisol/ui';

export interface KpiDeltaProps {
  current: number;
  previous: number | null;
  polarity?: 'up=good' | 'up=bad' | undefined;
}

export function KpiDelta({ current, previous, polarity = 'up=good' }: KpiDeltaProps) {
  if (previous === null) return null;

  const diff = current - previous;
  if (diff === 0) {
    return <Text style={styles.muted}>Sin cambio</Text>;
  }

  const percent =
    previous === 0 ? null : ((diff / Math.abs(previous)) * 100).toFixed(1);
  const isUp = diff > 0;
  const isPositive = polarity === 'up=good' ? isUp : !isUp;
  const arrow = isUp ? '↑' : '↓';
  const color = isPositive ? colors.success : colors.danger;
  const sign = isUp ? '+' : '';

  return (
    <View style={styles.row}>
      <Text style={[styles.value, { color }]}>
        {arrow} {percent !== null ? `${sign}${percent}%` : `${sign}—`}
      </Text>
      <Text style={styles.muted}>vs anterior</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  value: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
  },
  muted: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.medium,
    color: colors.textSubtle,
  },
});
