import { useState } from 'react';
import { FlatList, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { MODULES, type AppModule } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

interface ModuleHeaderProps {
  active: AppModule;
}

export function ModuleHeader({ active }: ModuleHeaderProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  function handleSelect(m: AppModule) {
    setOpen(false);
    if (!m.enabled || m.id === active.id) return;
    const target = m.sections[0]?.path ?? m.basePath;
    router.replace(target as never);
  }

  return (
    <>
      <Pressable
        style={styles.trigger}
        onPress={() => setOpen(true)}
        accessibilityRole="button"
        accessibilityLabel="Cambiar módulo"
      >
        <Text style={styles.title}>{active.label}</Text>
        <Text style={styles.caret}>▾</Text>
      </Pressable>
      <Modal
        visible={open}
        transparent
        animationType="fade"
        onRequestClose={() => setOpen(false)}
      >
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.sheetTitle}>Módulos</Text>
            <FlatList
              data={MODULES as readonly AppModule[]}
              keyExtractor={(m) => m.id}
              ItemSeparatorComponent={() => <View style={styles.separator} />}
              renderItem={({ item }) => {
                const isActive = item.id === active.id;
                const disabled = !item.enabled;
                return (
                  <Pressable
                    style={[styles.row, isActive && styles.rowActive]}
                    onPress={() => handleSelect(item)}
                    disabled={disabled}
                  >
                    <Text
                      style={[
                        styles.rowLabel,
                        disabled && styles.rowLabelDisabled,
                        isActive && styles.rowLabelActive,
                      ]}
                    >
                      {item.label}
                    </Text>
                    {disabled && <Text style={styles.rowHint}>Próximamente</Text>}
                  </Pressable>
                );
              }}
            />
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  trigger: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  title: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold as '600',
    color: colors.text,
  },
  caret: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
  },
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    padding: spacing.md,
    paddingBottom: spacing.xl,
  },
  sheetTitle: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    fontWeight: fontWeight.medium as '500',
    marginBottom: spacing.sm,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  separator: { height: 1, backgroundColor: colors.border },
  row: {
    paddingVertical: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  rowActive: {
    backgroundColor: colors.background,
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
  },
  rowLabel: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: fontWeight.medium as '500',
  },
  rowLabelActive: {
    color: colors.primary,
    fontWeight: fontWeight.semibold as '600',
  },
  rowLabelDisabled: { color: colors.textMuted },
  rowHint: { fontSize: fontSize.xs, color: colors.textMuted },
});
