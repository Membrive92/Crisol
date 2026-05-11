import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Stack } from 'expo-router';

import {
  formatApiError,
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useSeedRecommended,
  useUpdateCategory,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type { Category } from '@crisol/types';
import {
  DEFAULT_CATEGORY_COLOR,
  colors,
  fontSize,
  fontWeight,
  radius,
  spacing,
} from '@crisol/ui';

import {
  CategoryFormModal,
  type CategoryFormValues,
} from '../../../components/categories/category-form-modal';
import { ConfirmDialog } from '../../../components/ui/confirm-dialog';

/**
 * Pantalla de gestión de categorías para mobile. Lista agrupada por
 * `kind` (gastos / ingresos), FAB para crear y modal compartido para
 * crear y editar (incluye color + emoji).
 *
 * Las categorías "fijas" (las que el seed inicial puebla) no son
 * inmutables — el usuario puede renombrarlas, recolorearlas o
 * borrarlas igual que las creadas a mano.
 */
export default function CategoriesScreen() {
  const list = useCategories();
  const createMutation = useCreateCategory();
  const seedMutation = useSeedRecommended();
  const deleteMutation = useDeleteCategory();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Category | null>(null);

  const items = list.data ?? [];
  const expenseItems = items.filter((c) => c.kind === 'expense');
  const incomeItems = items.filter((c) => c.kind === 'income');

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(category: Category) {
    setEditing(category);
    setFormOpen(true);
  }

  function handleCreate(values: CategoryFormValues) {
    createMutation.mutate(values, {
      onSuccess: () => {
        toast.success('Categoría creada.');
        setFormOpen(false);
      },
      onError: (err) =>
        toast.error(formatApiError(err, 'No se pudo crear la categoría.')),
    });
  }

  function handleSeed() {
    seedMutation.mutate(undefined, {
      onSuccess: ({ categories_created, rules_created }) => {
        if (categories_created === 0 && rules_created === 0) {
          toast.info('Ya tienes todas las recomendadas.');
        } else {
          toast.success(
            `Creadas ${categories_created} categorías y ${rules_created} reglas.`,
          );
        }
      },
      onError: (err) =>
        toast.error(formatApiError(err, 'Error al crear recomendadas.')),
    });
  }

  function confirmDelete() {
    if (!pendingDelete) return;
    const target = pendingDelete;
    setPendingDelete(null);
    deleteMutation.mutate(target.id, {
      onSuccess: () => toast.success('Categoría eliminada.'),
      onError: (err) =>
        toast.error(formatApiError(err, 'No se pudo eliminar.')),
    });
  }

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: 'Categorías' }} />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.intro}>
          Las usas para clasificar transacciones, tickets e importaciones. Al
          borrar una categoría, las transacciones que la usaban quedan sin
          categoría — no se borran.
        </Text>

        <Pressable
          onPress={handleSeed}
          disabled={seedMutation.isPending}
          style={({ pressed }) => [
            styles.secondaryButton,
            (pressed || seedMutation.isPending) && { opacity: 0.7 },
          ]}
        >
          <Text style={styles.secondaryText}>
            {seedMutation.isPending ? 'Creando…' : 'Crear recomendadas'}
          </Text>
        </Pressable>

        {list.isLoading ? (
          <Text style={styles.placeholder}>Cargando…</Text>
        ) : list.isError ? (
          <Text style={styles.error}>
            {formatApiError(list.error, 'Error cargando categorías.')}
          </Text>
        ) : items.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyText}>
              Aún no tienes categorías. Toca "+" para crear la primera.
            </Text>
          </View>
        ) : (
          <>
            <CategoryGroup
              title="Gastos"
              items={expenseItems}
              onEdit={openEdit}
              onDelete={setPendingDelete}
            />
            <CategoryGroup
              title="Ingresos"
              items={incomeItems}
              onEdit={openEdit}
              onDelete={setPendingDelete}
            />
          </>
        )}
      </ScrollView>

      <Pressable
        onPress={openCreate}
        style={({ pressed }) => [styles.fab, pressed && { opacity: 0.85 }]}
        accessibilityLabel="Nueva categoría"
      >
        <Text style={styles.fabText}>+</Text>
      </Pressable>

      {editing ? (
        <EditCategoryModal
          visible={formOpen}
          category={editing}
          onClose={() => setFormOpen(false)}
        />
      ) : (
        <CategoryFormModal
          visible={formOpen}
          initial={null}
          submitting={createMutation.isPending}
          onSubmit={handleCreate}
          onCancel={() => setFormOpen(false)}
        />
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="¿Eliminar categoría?"
        description={
          pendingDelete
            ? `"${pendingDelete.name}" dejará de estar disponible. Las transacciones que la usaban quedarán sin categoría.`
            : undefined
        }
        confirmLabel="Eliminar"
        cancelLabel="Atrás"
        tone="danger"
        loading={deleteMutation.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </View>
  );
}

interface EditCategoryModalProps {
  visible: boolean;
  category: Category;
  onClose: () => void;
}

/**
 * Subcomponente que envuelve `useUpdateCategory(id)` — el hook necesita
 * el id en su construcción, así que aislamos el ciclo de vida en una
 * unidad re-montable cuando cambia la categoría editada.
 */
function EditCategoryModal({
  visible,
  category,
  onClose,
}: EditCategoryModalProps) {
  const update = useUpdateCategory(category.id);

  function handleSubmit(values: CategoryFormValues) {
    update.mutate(values, {
      onSuccess: () => {
        toast.success('Categoría actualizada.');
        onClose();
      },
      onError: (err) =>
        toast.error(formatApiError(err, 'No se pudo guardar.')),
    });
  }

  return (
    <CategoryFormModal
      visible={visible}
      initial={category}
      submitting={update.isPending}
      onSubmit={handleSubmit}
      onCancel={onClose}
    />
  );
}

interface CategoryGroupProps {
  title: string;
  items: Category[];
  onEdit: (c: Category) => void;
  onDelete: (c: Category) => void;
}

function CategoryGroup({ title, items, onEdit, onDelete }: CategoryGroupProps) {
  if (items.length === 0) {
    return (
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>{title}</Text>
        <View style={styles.emptyCard}>
          <Text style={styles.emptyText}>Ninguna en esta sección.</Text>
        </View>
      </View>
    );
  }
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>
        {title} · {items.length}
      </Text>
      <View style={styles.list}>
        {items.map((cat, idx) => (
          <View
            key={cat.id}
            style={[styles.row, idx === 0 && { borderTopWidth: 0 }]}
          >
            <CategorySwatch color={cat.color} icon={cat.icon} />
            <Text style={styles.rowName} numberOfLines={1}>
              {cat.name}
            </Text>
            <Pressable onPress={() => onEdit(cat)} style={styles.rowAction}>
              <Text style={styles.rowActionText}>Editar</Text>
            </Pressable>
            <Pressable
              onPress={() => onDelete(cat)}
              style={styles.rowAction}
            >
              <Text style={[styles.rowActionText, { color: colors.danger }]}>
                Borrar
              </Text>
            </Pressable>
          </View>
        ))}
      </View>
    </View>
  );
}

function CategorySwatch({
  color,
  icon,
}: {
  color: string | null;
  icon: string | null;
}) {
  return (
    <View
      style={[
        styles.swatch,
        { backgroundColor: color ?? DEFAULT_CATEGORY_COLOR },
      ]}
    >
      {icon ? <Text style={styles.swatchIcon}>{icon}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl + 60 },
  intro: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    marginBottom: spacing.md,
    lineHeight: 18,
  },
  secondaryButton: {
    alignSelf: 'flex-start',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.md,
  },
  secondaryText: { color: colors.text, fontWeight: fontWeight.medium },
  placeholder: { color: colors.textMuted, paddingVertical: spacing.md },
  error: { color: colors.danger, paddingVertical: spacing.md },
  emptyCard: {
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderStyle: 'dashed',
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.lg,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    textAlign: 'center',
  },
  section: { marginTop: spacing.md },
  sectionTitle: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: spacing.sm,
  },
  list: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  rowName: {
    flex: 1,
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  rowAction: {
    paddingHorizontal: spacing.xs,
    paddingVertical: spacing.xs,
  },
  rowActionText: {
    color: colors.primary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
  },
  swatch: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  swatchIcon: { fontSize: fontSize.md },
  fab: {
    position: 'absolute',
    right: spacing.lg,
    bottom: spacing.lg,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 6,
  },
  fabText: { color: colors.onPrimary, fontSize: 28, lineHeight: 32 },
});
