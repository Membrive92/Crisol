'use client';

import Link from 'next/link';
import { useState, type FormEvent } from 'react';

import {
  formatApiError,
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useSeedRecommended,
  useUpdateCategory,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type { Category, CategoryKind } from '@crisol/types';
import {
  DEFAULT_CATEGORY_COLOR,
  colors,
  fontSize,
  fontWeight,
  layout,
  radius,
  spacing,
} from '@crisol/ui';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { CategoryAppearanceFields } from '@/components/ui/category-appearance';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Select, TextInput } from '@/components/ui/field';

interface FormState {
  name: string;
  kind: CategoryKind;
  color: string;
  icon: string | null;
  is_transfer: boolean;
}

const EMPTY_FORM: FormState = {
  name: '',
  kind: 'expense',
  color: DEFAULT_CATEGORY_COLOR,
  icon: null,
  is_transfer: false,
};

export default function CategoriesSettingsPage() {
  const list = useCategories();
  const create = useCreateCategory();
  const seed = useSeedRecommended();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [createError, setCreateError] = useState<string | null>(null);

  function handleSeed() {
    seed.mutate(undefined, {
      onSuccess: ({ categories_created, rules_created }) => {
        if (categories_created === 0 && rules_created === 0) {
          toast.info('Ya tienes todas las recomendadas creadas.');
        } else {
          toast.success(
            `Creadas ${categories_created} categorías y ${rules_created} reglas.`,
          );
        }
      },
      onError: (err) =>
        toast.error(formatApiError(err, 'Error al crear recomendadas')),
    });
  }

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    const name = form.name.trim();
    if (!name) {
      setCreateError('El nombre es obligatorio');
      return;
    }
    create.mutate(
      {
        name,
        kind: form.kind,
        color: form.color,
        icon: form.icon,
        is_transfer: form.is_transfer,
      },
      {
        onSuccess: () => setForm(EMPTY_FORM),
        onError: (err) => setCreateError(formatApiError(err, 'No se pudo crear')),
      },
    );
  }

  const items = list.data ?? [];
  // PHASE-23.1: las is_transfer salen del agrupamiento por kind y se
  // muestran en su propia sección "Transferencias", aunque internamente
  // tengan kind=expense o kind=income.
  const expenseItems = items.filter((c) => c.kind === 'expense' && !c.is_transfer);
  const incomeItems = items.filter((c) => c.kind === 'income' && !c.is_transfer);
  const transferItems = items.filter((c) => c.is_transfer);

  return (
    <div style={{ maxWidth: layout.pageWide, margin: '0 auto', padding: spacing.lg }}>
      <Link
        href="/settings"
        style={{
          fontSize: fontSize.sm,
          color: colors.textMuted,
          textDecoration: 'none',
        }}
      >
        ← Ajustes
      </Link>

      <header
        style={{
          marginTop: spacing.sm,
          marginBottom: spacing.lg,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: spacing.md,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ flex: '1 1 360px' }}>
          <h1
            style={{
              margin: 0,
              fontSize: fontSize.xl,
              fontWeight: fontWeight.bold,
              color: colors.text,
              letterSpacing: '-0.01em',
            }}
          >
            Categorías
          </h1>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              fontSize: fontSize.sm,
              color: colors.textMuted,
              lineHeight: 1.4,
            }}
          >
            Las usas para clasificar transacciones, tickets e importaciones del
            módulo Finanzas personales. Al borrar una categoría, las
            transacciones que la usaban quedan sin categoría (no se borran).
          </p>
        </div>
        <div style={{ display: 'inline-flex', gap: spacing.sm, flexWrap: 'wrap' }}>
          <Link href="/settings/categories/rules">
            <Button variant="ghost">Ver reglas</Button>
          </Link>
          <Button
            variant="secondary"
            onClick={handleSeed}
            disabled={seed.isPending}
          >
            {seed.isPending ? 'Creando…' : 'Crear recomendadas'}
          </Button>
        </div>
      </header>

      <Card style={{ padding: spacing.lg, marginBottom: spacing.lg }}>
        <h2
          style={{
            margin: 0,
            marginBottom: spacing.md,
            fontSize: fontSize.lg,
            fontWeight: fontWeight.semibold,
            color: colors.text,
          }}
        >
          Nueva categoría
        </h2>
        <form
          onSubmit={handleCreate}
          style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}
        >
          <div style={{ display: 'flex', gap: spacing.md, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div style={{ flex: '2 1 220px', minWidth: 0 }}>
              <TextInput
                label="Nombre"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                maxLength={64}
                placeholder="Comida, Nómina, Transporte…"
                required
              />
            </div>
            <div style={{ flex: '1 1 160px', minWidth: 0 }}>
              <Select
                label="Tipo"
                value={form.kind}
                onChange={(e) => setForm({ ...form, kind: e.target.value as CategoryKind })}
              >
                <option value="expense">Gasto</option>
                <option value="income">Ingreso</option>
              </Select>
            </div>
          </div>
          <CategoryAppearanceFields
            color={form.color}
            icon={form.icon}
            onColorChange={(hex) => setForm({ ...form, color: hex })}
            onIconChange={(emoji) => setForm({ ...form, icon: emoji })}
          />
          <label
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: spacing.sm,
              fontSize: fontSize.sm,
              color: colors.textMuted,
              cursor: 'pointer',
            }}
          >
            <input
              type="checkbox"
              checked={form.is_transfer}
              onChange={(e) =>
                setForm({ ...form, is_transfer: e.target.checked })
              }
            />
            Es transferencia interna (no cuenta como gasto ni ingreso)
          </label>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Creando…' : 'Crear'}
            </Button>
          </div>
        </form>
        {createError ? (
          <div style={{ color: colors.danger, fontSize: fontSize.sm, marginTop: spacing.xs }}>
            {createError}
          </div>
        ) : null}
      </Card>

      {list.isLoading ? (
        <p style={{ color: colors.textMuted }}>Cargando…</p>
      ) : list.isError ? (
        <p style={{ color: colors.danger }}>
          {formatApiError(list.error, 'Error cargando categorías')}
        </p>
      ) : items.length === 0 ? (
        <Card style={{ padding: spacing.lg, textAlign: 'center' }}>
          <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
            Aún no tienes categorías. Crea la primera arriba.
          </p>
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
          <CategoryGroup title="Gastos" items={expenseItems} />
          <CategoryGroup title="Ingresos" items={incomeItems} />
          <CategoryGroup title="Transferencias" items={transferItems} />
        </div>
      )}
    </div>
  );
}

function CategoryGroup({ title, items }: { title: string; items: Category[] }) {
  if (items.length === 0) {
    return (
      <section>
        <h3
          style={{
            margin: 0,
            marginBottom: spacing.sm,
            fontSize: fontSize.sm,
            fontWeight: fontWeight.semibold,
            color: colors.textMuted,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {title}
        </h3>
        <Card style={{ padding: spacing.md }}>
          <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
            Ninguna en esta sección.
          </p>
        </Card>
      </section>
    );
  }
  return (
    <section>
      <h3
        style={{
          margin: 0,
          marginBottom: spacing.sm,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: colors.textMuted,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        {title} · {items.length}
      </h3>
      <Card style={{ padding: 0 }}>
        <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
          {items.map((cat, idx) => (
            <li
              key={cat.id}
              style={{
                borderTop: idx === 0 ? 'none' : `1px solid ${colors.border}`,
              }}
            >
              <CategoryRow category={cat} />
            </li>
          ))}
        </ul>
      </Card>
    </section>
  );
}

function CategoryRow({ category }: { category: Category }) {
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [draftName, setDraftName] = useState(category.name);
  const [draftKind, setDraftKind] = useState<CategoryKind>(category.kind);
  const [draftColor, setDraftColor] = useState<string>(
    category.color ?? DEFAULT_CATEGORY_COLOR,
  );
  const [draftIcon, setDraftIcon] = useState<string | null>(category.icon);
  const [draftIsTransfer, setDraftIsTransfer] = useState<boolean>(
    category.is_transfer,
  );
  const [rowError, setRowError] = useState<string | null>(null);

  const update = useUpdateCategory(category.id);
  const remove = useDeleteCategory();

  function startEdit() {
    setRowError(null);
    setDraftName(category.name);
    setDraftKind(category.kind);
    setDraftColor(category.color ?? DEFAULT_CATEGORY_COLOR);
    setDraftIcon(category.icon);
    setDraftIsTransfer(category.is_transfer);
    setEditing(true);
  }

  function saveEdit() {
    setRowError(null);
    const name = draftName.trim();
    if (!name) {
      setRowError('El nombre es obligatorio');
      return;
    }
    update.mutate(
      {
        name,
        kind: draftKind,
        color: draftColor,
        icon: draftIcon,
        is_transfer: draftIsTransfer,
      },
      {
        onSuccess: () => setEditing(false),
        onError: (err) => setRowError(formatApiError(err, 'No se pudo guardar')),
      },
    );
  }

  function handleDelete() {
    setRowError(null);
    remove.mutate(category.id, {
      onSuccess: () => setConfirming(false),
      onError: (err) => setRowError(formatApiError(err, 'No se pudo eliminar')),
    });
  }

  if (editing) {
    return (
      <div
        style={{
          padding: spacing.md,
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.md,
        }}
      >
        <div style={{ display: 'flex', gap: spacing.sm, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: '2 1 200px', minWidth: 0 }}>
            <TextInput
              label="Nombre"
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              maxLength={64}
            />
          </div>
          <div style={{ flex: '1 1 140px', minWidth: 0 }}>
            <Select
              label="Tipo"
              value={draftKind}
              onChange={(e) => setDraftKind(e.target.value as CategoryKind)}
            >
              <option value="expense">Gasto</option>
              <option value="income">Ingreso</option>
            </Select>
          </div>
        </div>
        <CategoryAppearanceFields
          color={draftColor}
          icon={draftIcon}
          onColorChange={setDraftColor}
          onIconChange={setDraftIcon}
        />
        <label
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: spacing.sm,
            fontSize: fontSize.sm,
            color: colors.textMuted,
            cursor: 'pointer',
          }}
        >
          <input
            type="checkbox"
            checked={draftIsTransfer}
            onChange={(e) => setDraftIsTransfer(e.target.checked)}
          />
          Es transferencia interna (no cuenta como gasto ni ingreso)
        </label>
        <div style={{ display: 'flex', gap: spacing.xs, justifyContent: 'flex-end' }}>
          <Button type="button" variant="ghost" onClick={() => setEditing(false)}>
            Cancelar
          </Button>
          <Button type="button" onClick={saveEdit} disabled={update.isPending}>
            {update.isPending ? 'Guardando…' : 'Guardar'}
          </Button>
        </div>
        {rowError ? (
          <div style={{ color: colors.danger, fontSize: fontSize.sm }}>{rowError}</div>
        ) : null}
      </div>
    );
  }

  return (
    <div
      style={{
        padding: `${spacing.sm}px ${spacing.md}px`,
        display: 'flex',
        alignItems: 'center',
        gap: spacing.md,
      }}
    >
      <CategorySwatch color={category.color} icon={category.icon} />
      <span
        style={{
          flex: 1,
          fontSize: fontSize.md,
          color: colors.text,
          fontWeight: fontWeight.medium,
        }}
      >
        {category.name}
      </span>
      <KindBadge kind={category.kind} isTransfer={category.is_transfer} />
      <div style={{ display: 'flex', gap: spacing.xs }}>
        <Button type="button" variant="ghost" onClick={startEdit}>
          Editar
        </Button>
        <Button type="button" variant="ghost" onClick={() => setConfirming(true)}>
          Eliminar
        </Button>
      </div>
      {rowError ? (
        <div style={{ flex: '1 0 100%', color: colors.danger, fontSize: fontSize.sm }}>
          {rowError}
        </div>
      ) : null}
      <ConfirmDialog
        open={confirming}
        title="¿Eliminar categoría?"
        description={
          <>
            <strong>{category.name}</strong> dejará de estar disponible. Las
            transacciones que la usaban quedarán sin categoría — no se borran.
          </>
        }
        confirmLabel="Eliminar"
        tone="danger"
        loading={remove.isPending}
        onConfirm={handleDelete}
        onCancel={() => setConfirming(false)}
      />
    </div>
  );
}

function CategorySwatch({ color, icon }: { color: string | null; icon: string | null }) {
  const bg = color ?? DEFAULT_CATEGORY_COLOR;
  return (
    <span
      aria-hidden="true"
      style={{
        width: 32,
        height: 32,
        borderRadius: '50%',
        backgroundColor: bg,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      {icon ? <span style={{ fontSize: fontSize.md, lineHeight: 1 }}>{icon}</span> : null}
    </span>
  );
}

function KindBadge({
  kind,
  isTransfer,
}: {
  kind: CategoryKind;
  isTransfer: boolean;
}) {
  const baseLabel = kind === 'income' ? 'Ingreso' : 'Gasto';
  const baseFg = kind === 'income' ? colors.income : colors.expense;
  const label = isTransfer ? `${baseLabel} · Transfer` : baseLabel;
  const fg = isTransfer ? colors.textMuted : baseFg;
  return (
    <span
      style={{
        padding: `${spacing.xs / 2}px ${spacing.sm}px`,
        borderRadius: radius.sm,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        backgroundColor: 'transparent',
        color: fg,
        border: `1px solid ${fg}`,
      }}
    >
      {label}
    </span>
  );
}
