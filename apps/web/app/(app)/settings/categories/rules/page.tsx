'use client';

import Link from 'next/link';
import { useState, type FormEvent } from 'react';

import {
  formatApiError,
  useCategories,
  useCategoryRules,
  useCreateCategoryRule,
  useDeleteCategoryRule,
  useUpdateCategoryRule,
} from '@finanzas/services';
import { toast } from '@finanzas/store';
import type {
  CategoryRule,
  RuleField,
  RuleMatchType,
} from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Select, TextInput } from '@/components/ui/field';

const MATCH_TYPE_LABELS: Record<RuleMatchType, string> = {
  exact: 'Exacto',
  contains: 'Contiene',
  starts_with: 'Empieza por',
  regex: 'Regex',
};

const FIELD_LABELS: Record<RuleField, string> = {
  concept: 'Concepto',
  description: 'Descripción',
  both: 'Ambos',
};

export default function CategoryRulesPage() {
  const rulesQuery = useCategoryRules();
  const categoriesQuery = useCategories();
  const create = useCreateCategoryRule();
  const remove = useDeleteCategoryRule();
  const [pendingDelete, setPendingDelete] = useState<CategoryRule | null>(null);

  const rules = rulesQuery.data ?? [];
  const categories = categoriesQuery.data ?? [];
  const categoriesById = new Map(categories.map((c) => [c.id, c]));

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: spacing.lg }}>
      <Link
        href="/settings/categories"
        style={{
          fontSize: fontSize.sm,
          color: colors.textMuted,
          textDecoration: 'none',
        }}
      >
        ← Categorías
      </Link>

      <header style={{ marginTop: spacing.sm, marginBottom: spacing.lg }}>
        <h1
          style={{
            margin: 0,
            fontSize: fontSize.xl,
            fontWeight: fontWeight.bold,
            color: colors.text,
            letterSpacing: '-0.01em',
          }}
        >
          Reglas de categorización
        </h1>
        <p
          style={{
            margin: `${spacing.xs}px 0 0 0`,
            fontSize: fontSize.sm,
            color: colors.textMuted,
            lineHeight: 1.4,
          }}
        >
          Patrones que el sistema busca al importar transacciones para
          asignar categoría automáticamente. Se evalúan en orden de{' '}
          <strong>prioridad</strong> (menor número = antes). Si dos reglas
          matchean, gana la de menor prioridad.
        </p>
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
          Nueva regla
        </h2>
        <NewRuleForm
          categories={categories}
          submitting={create.isPending}
          onSubmit={(data) =>
            create.mutate(data, {
              onSuccess: () => toast.success('Regla creada.'),
              onError: (err) =>
                toast.error(formatApiError(err, 'Error al crear regla')),
            })
          }
        />
      </Card>

      {rulesQuery.isLoading ? (
        <p style={{ color: colors.textMuted }}>Cargando…</p>
      ) : rules.length === 0 ? (
        <Card style={{ padding: spacing.lg, textAlign: 'center' }}>
          <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
            Aún no tienes reglas. Crea la primera arriba o vuelve a Categorías
            para sembrar las recomendadas.
          </p>
        </Card>
      ) : (
        <Card style={{ padding: 0 }}>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {rules.map((rule, idx) => (
              <li
                key={rule.id}
                style={{
                  borderTop: idx === 0 ? 'none' : `1px solid ${colors.border}`,
                }}
              >
                <RuleRow
                  rule={rule}
                  category={categoriesById.get(rule.category_id) ?? null}
                  onAskDelete={() => setPendingDelete(rule)}
                />
              </li>
            ))}
          </ul>
        </Card>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="¿Eliminar regla?"
        description={
          pendingDelete
            ? `La regla "${pendingDelete.pattern}" dejará de aplicarse en futuras importaciones.`
            : null
        }
        confirmLabel="Eliminar"
        tone="danger"
        loading={remove.isPending}
        onConfirm={() => {
          if (!pendingDelete) return;
          remove.mutate(pendingDelete.id, {
            onSuccess: () => {
              toast.success('Regla eliminada.');
              setPendingDelete(null);
            },
            onError: (err) =>
              toast.error(formatApiError(err, 'Error al eliminar')),
          });
        }}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

interface NewRuleFormProps {
  categories: { id: string; name: string; kind: string }[];
  submitting: boolean;
  onSubmit: (data: {
    pattern: string;
    match_type: RuleMatchType;
    field: RuleField;
    category_id: string;
    priority: number;
  }) => void;
}

function NewRuleForm({ categories, submitting, onSubmit }: NewRuleFormProps) {
  const [pattern, setPattern] = useState('');
  const [matchType, setMatchType] = useState<RuleMatchType>('contains');
  const [field, setField] = useState<RuleField>('both');
  const [categoryId, setCategoryId] = useState('');
  const [priority, setPriority] = useState('100');
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!pattern.trim()) {
      setError('El patrón es obligatorio.');
      return;
    }
    if (!categoryId) {
      setError('Elige una categoría.');
      return;
    }
    const numericPriority = Number.parseInt(priority, 10);
    if (Number.isNaN(numericPriority) || numericPriority < 0) {
      setError('Prioridad inválida.');
      return;
    }
    onSubmit({
      pattern: pattern.trim(),
      match_type: matchType,
      field,
      category_id: categoryId,
      priority: numericPriority,
    });
    setPattern('');
  }

  return (
    <form onSubmit={handleSubmit}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '2fr 1fr 1fr 2fr 100px auto',
          gap: spacing.sm,
          alignItems: 'flex-end',
        }}
      >
        <TextInput
          label="Patrón"
          value={pattern}
          onChange={(e) => setPattern(e.target.value)}
          placeholder="MERCADONA, RESTAURANT, etc."
          maxLength={255}
          required
        />
        <Select
          label="Tipo"
          value={matchType}
          onChange={(e) => setMatchType(e.target.value as RuleMatchType)}
        >
          {Object.entries(MATCH_TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
        <Select
          label="Campo"
          value={field}
          onChange={(e) => setField(e.target.value as RuleField)}
        >
          {Object.entries(FIELD_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
        <Select
          label="Categoría"
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          required
        >
          <option value="">— Elige —</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.kind === 'income' ? 'Ingreso' : 'Gasto'})
            </option>
          ))}
        </Select>
        <TextInput
          label="Prioridad"
          type="number"
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          min={0}
          max={10_000}
        />
        <div style={{ marginBottom: spacing.md }}>
          <Button type="submit" disabled={submitting}>
            {submitting ? '…' : 'Añadir'}
          </Button>
        </div>
      </div>
      {error ? (
        <div
          style={{
            color: colors.danger,
            fontSize: fontSize.sm,
            marginTop: spacing.xs,
          }}
        >
          {error}
        </div>
      ) : null}
    </form>
  );
}

interface RuleRowProps {
  rule: CategoryRule;
  category: { id: string; name: string; kind: string } | null;
  onAskDelete: () => void;
}

function RuleRow({ rule, category, onAskDelete }: RuleRowProps) {
  const update = useUpdateCategoryRule(rule.id);

  function toggle() {
    update.mutate(
      { enabled: !rule.enabled },
      {
        onError: (err) =>
          toast.error(formatApiError(err, 'Error al actualizar')),
      },
    );
  }

  return (
    <div
      style={{
        padding: `${spacing.sm}px ${spacing.md}px`,
        display: 'flex',
        alignItems: 'center',
        gap: spacing.sm,
        opacity: rule.enabled ? 1 : 0.5,
      }}
    >
      <div
        style={{
          width: 50,
          textAlign: 'center',
          fontSize: fontSize.xs,
          color: colors.textMuted,
          fontVariantNumeric: 'tabular-nums',
        }}
        title={`Prioridad ${rule.priority}`}
      >
        #{rule.priority}
      </div>
      <code
        style={{
          flex: 1,
          fontSize: fontSize.sm,
          color: colors.text,
          fontWeight: fontWeight.medium,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
        title={rule.pattern}
      >
        {rule.pattern}
      </code>
      <Badge>{MATCH_TYPE_LABELS[rule.match_type]}</Badge>
      <Badge>{FIELD_LABELS[rule.field]}</Badge>
      <span
        style={{
          fontSize: fontSize.sm,
          color: colors.text,
          width: 180,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        → {category?.name ?? '(categoría borrada)'}
      </span>
      <Button
        type="button"
        variant="ghost"
        onClick={toggle}
        disabled={update.isPending}
      >
        {rule.enabled ? 'Desactivar' : 'Activar'}
      </Button>
      <Button type="button" variant="ghost" onClick={onAskDelete}>
        Eliminar
      </Button>
    </div>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        padding: `2px ${spacing.xs}px`,
        borderRadius: radius.sm,
        backgroundColor: colors.surfaceMuted,
        color: colors.textMuted,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.medium,
      }}
    >
      {children}
    </span>
  );
}
