import { useEffect, useState } from 'react';
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import type { Category, CategoryKind } from '@finanzas/types';
import {
  DEFAULT_CATEGORY_COLOR,
  colors,
  fontSize,
  fontWeight,
  radius,
  spacing,
} from '@finanzas/ui';

import { CategoryAppearanceFields } from './category-appearance-fields';

export interface CategoryFormValues {
  name: string;
  kind: CategoryKind;
  color: string;
  icon: string | null;
}

export interface CategoryFormModalProps {
  visible: boolean;
  /** Si es null se interpreta como modo "crear", si no, modo "editar". */
  initial: Category | null;
  submitting?: boolean;
  onSubmit: (data: CategoryFormValues) => void;
  onCancel: () => void;
}

const KIND_OPTIONS: readonly { value: CategoryKind; label: string }[] = [
  { value: 'expense', label: 'Gasto' },
  { value: 'income', label: 'Ingreso' },
];

export function CategoryFormModal({
  visible,
  initial,
  submitting,
  onSubmit,
  onCancel,
}: CategoryFormModalProps) {
  const [name, setName] = useState('');
  const [kind, setKind] = useState<CategoryKind>('expense');
  const [color, setColor] = useState<string>(DEFAULT_CATEGORY_COLOR);
  const [icon, setIcon] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!visible) return;
    setName(initial?.name ?? '');
    setKind(initial?.kind ?? 'expense');
    setColor(initial?.color ?? DEFAULT_CATEGORY_COLOR);
    setIcon(initial?.icon ?? null);
    setError(null);
  }, [visible, initial]);

  function handleSubmit() {
    setError(null);
    const trimmed = name.trim();
    if (!trimmed) {
      setError('El nombre es obligatorio.');
      return;
    }
    onSubmit({ name: trimmed, kind, color, icon });
  }

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onCancel}
    >
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <View style={styles.header}>
            <Text style={styles.title}>
              {initial ? 'Editar categoría' : 'Nueva categoría'}
            </Text>
            <Pressable onPress={onCancel} accessibilityRole="button">
              <Text style={styles.closeText}>✕</Text>
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={styles.content}>
            <View>
              <Text style={styles.label}>Nombre</Text>
              <TextInput
                style={styles.input}
                value={name}
                onChangeText={setName}
                maxLength={64}
                placeholder="Comida, Nómina, Transporte…"
                placeholderTextColor={colors.textMuted}
              />
            </View>

            <View>
              <Text style={styles.label}>Tipo</Text>
              <View style={styles.segment}>
                {KIND_OPTIONS.map((opt) => {
                  const active = opt.value === kind;
                  return (
                    <Pressable
                      key={opt.value}
                      onPress={() => setKind(opt.value)}
                      style={[
                        styles.segmentButton,
                        active && styles.segmentButtonActive,
                      ]}
                    >
                      <Text
                        style={[
                          styles.segmentText,
                          active && styles.segmentTextActive,
                        ]}
                      >
                        {opt.label}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>

            <CategoryAppearanceFields
              color={color}
              icon={icon}
              onColorChange={setColor}
              onIconChange={setIcon}
            />

            {error ? <Text style={styles.error}>{error}</Text> : null}
          </ScrollView>
          <View style={styles.actions}>
            <Pressable onPress={onCancel} style={styles.actionGhost}>
              <Text style={styles.actionGhostText}>Cancelar</Text>
            </Pressable>
            <Pressable
              onPress={handleSubmit}
              disabled={submitting}
              style={[
                styles.actionPrimary,
                submitting && styles.actionPrimaryDisabled,
              ]}
            >
              <Text style={styles.actionPrimaryText}>
                {submitting ? 'Guardando…' : initial ? 'Guardar' : 'Crear'}
              </Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.background,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    maxHeight: '92%',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  closeText: { fontSize: fontSize.lg, color: colors.textMuted },
  content: { padding: spacing.md, gap: spacing.md, paddingBottom: spacing.lg },
  label: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    fontSize: fontSize.md,
    color: colors.text,
  },
  segment: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  segmentButton: {
    flex: 1,
    paddingVertical: spacing.sm,
    alignItems: 'center',
  },
  segmentButtonActive: { backgroundColor: colors.primarySoft },
  segmentText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    fontWeight: fontWeight.medium,
  },
  segmentTextActive: { color: colors.primary, fontWeight: fontWeight.semibold },
  error: { color: colors.danger, fontSize: fontSize.sm },
  actions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: spacing.sm,
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  actionGhost: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  actionGhostText: { color: colors.textMuted, fontWeight: fontWeight.medium },
  actionPrimary: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
  },
  actionPrimaryDisabled: { opacity: 0.6 },
  actionPrimaryText: {
    color: colors.onPrimary,
    fontWeight: fontWeight.semibold,
  },
});
