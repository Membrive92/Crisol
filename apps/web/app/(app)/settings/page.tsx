'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { passkeysApi, type PasskeyResponse } from '@crisol/services';
import { colors, fontSize, fontWeight, formatDate, radius, spacing } from '@crisol/ui';

import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { PasskeyAbortError, registerPasskey, supportsPasskeys } from '@/lib/webauthn';

interface ConfirmDeleteState {
  id: string;
  label: string;
}

export default function SettingsPage() {
  const [items, setItems] = useState<PasskeyResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [registering, setRegistering] = useState(false);
  const [supported, setSupported] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<ConfirmDeleteState | null>(null);

  useEffect(() => {
    setSupported(supportsPasskeys());
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const list = await passkeysApi.list();
        if (!cancelled) setItems(list);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Error cargando passkeys');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleRegister() {
    setError(null);
    setRegistering(true);
    try {
      const created = await registerPasskey('Este dispositivo');
      setItems((prev) => [created, ...prev]);
    } catch (err) {
      if (err instanceof PasskeyAbortError) return;
      setError(err instanceof Error ? err.message : 'No se pudo registrar');
    } finally {
      setRegistering(false);
    }
  }

  async function handleRename(id: string, label: string) {
    setError(null);
    try {
      const updated = await passkeysApi.relabel(id, label.trim());
      setItems((prev) => prev.map((p) => (p.id === id ? updated : p)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo renombrar');
    } finally {
      setRenamingId(null);
    }
  }

  async function handleDelete(id: string) {
    setError(null);
    try {
      await passkeysApi.remove(id);
      setItems((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo eliminar');
    } finally {
      setPendingDelete(null);
    }
  }

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: spacing.lg }}>
      <header style={{ marginBottom: spacing.lg }}>
        <h1
          style={{
            margin: 0,
            fontSize: fontSize.xl,
            fontWeight: fontWeight.bold,
            color: colors.text,
            letterSpacing: '-0.01em',
          }}
        >
          Ajustes
        </h1>
        <p
          style={{
            margin: `${spacing.xs}px 0 0 0`,
            fontSize: fontSize.sm,
            color: colors.textMuted,
          }}
        >
          Gestiona tu cuenta y la configuración de los módulos.
        </p>
      </header>

      <section style={{ marginBottom: spacing.lg }}>
        <h2
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
          Finanzas personales
        </h2>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.sm,
          }}
        >
          <Link
            href="/settings/accounts"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: colors.surface,
              border: `1px solid ${colors.border}`,
              borderRadius: radius.md,
              padding: spacing.md,
              color: colors.text,
              textDecoration: 'none',
            }}
          >
            <div>
              <div
                style={{
                  fontSize: fontSize.md,
                  fontWeight: fontWeight.semibold,
                  color: colors.text,
                }}
              >
                Cuentas
              </div>
              <div
                style={{
                  marginTop: spacing.xs,
                  fontSize: fontSize.sm,
                  color: colors.textMuted,
                  lineHeight: 1.4,
                }}
              >
                Define dónde vive tu dinero (banco, ahorro, crypto, efectivo).
                Cada transacción se imputa a una cuenta.
              </div>
            </div>
            <span
              style={{
                fontSize: fontSize.lg,
                color: colors.textMuted,
                marginLeft: spacing.md,
              }}
              aria-hidden
            >
              →
            </span>
          </Link>
          <Link
            href="/settings/categories"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: colors.surface,
              border: `1px solid ${colors.border}`,
              borderRadius: radius.md,
              padding: spacing.md,
              color: colors.text,
              textDecoration: 'none',
            }}
          >
            <div>
              <div
                style={{
                  fontSize: fontSize.md,
                  fontWeight: fontWeight.semibold,
                  color: colors.text,
                }}
              >
                Categorías
              </div>
              <div
                style={{
                  marginTop: spacing.xs,
                  fontSize: fontSize.sm,
                  color: colors.textMuted,
                  lineHeight: 1.4,
                }}
              >
                Crea, edita y borra las categorías que clasifican transacciones,
                tickets e importaciones.
              </div>
            </div>
            <span
              style={{
                fontSize: fontSize.lg,
                color: colors.textMuted,
                marginLeft: spacing.md,
              }}
              aria-hidden
            >
              →
            </span>
          </Link>
        </div>
      </section>

      <section
        style={{
          backgroundColor: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: radius.md,
          padding: spacing.lg,
        }}
      >
        <header
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: spacing.md,
            marginBottom: spacing.md,
          }}
        >
          <div>
            <h2
              style={{
                margin: 0,
                fontSize: fontSize.lg,
                fontWeight: fontWeight.semibold,
                color: colors.text,
              }}
            >
              Passkeys
            </h2>
            <p
              style={{
                margin: `${spacing.xs}px 0 0 0`,
                fontSize: fontSize.sm,
                color: colors.textMuted,
                lineHeight: 1.4,
              }}
            >
              Cada passkey es un dispositivo (Touch ID, Windows Hello, llave
              física…) capaz de iniciar sesión sin contraseña.
            </p>
          </div>
          {supported ? (
            <button
              type="button"
              onClick={handleRegister}
              disabled={registering}
              style={{
                padding: `${spacing.xs}px ${spacing.md}px`,
                backgroundColor: colors.primary,
                color: colors.onPrimary,
                border: 'none',
                borderRadius: radius.sm,
                fontSize: fontSize.sm,
                fontWeight: fontWeight.semibold,
                cursor: registering ? 'not-allowed' : 'pointer',
                opacity: registering ? 0.7 : 1,
                whiteSpace: 'nowrap',
              }}
            >
              {registering ? 'Esperando dispositivo…' : '+ Añadir passkey'}
            </button>
          ) : (
            <span
              style={{
                fontSize: fontSize.xs,
                color: colors.textSubtle,
                textAlign: 'right',
                maxWidth: 220,
              }}
            >
              Tu navegador no soporta WebAuthn.
            </span>
          )}
        </header>

        {error ? (
          <div
            role="alert"
            style={{
              padding: spacing.sm,
              marginBottom: spacing.md,
              border: `1px solid ${colors.danger}`,
              borderRadius: radius.sm,
              background:
                'color-mix(in srgb, var(--color-danger) 10%, transparent)',
              color: colors.danger,
              fontSize: fontSize.sm,
            }}
          >
            {error}
          </div>
        ) : null}

        {loading ? (
          <p style={{ color: colors.textMuted, fontSize: fontSize.sm }}>
            Cargando…
          </p>
        ) : items.length === 0 ? (
          <div
            style={{
              padding: spacing.lg,
              textAlign: 'center',
              color: colors.textMuted,
              fontSize: fontSize.sm,
              backgroundColor: colors.surfaceMuted,
              borderRadius: radius.sm,
            }}
          >
            Aún no tienes passkeys registradas.
          </div>
        ) : (
          <ul
            style={{
              listStyle: 'none',
              padding: 0,
              margin: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: spacing.sm,
            }}
          >
            {items.map((p) => (
              <PasskeyRow
                key={p.id}
                passkey={p}
                isRenaming={renamingId === p.id}
                onStartRename={() => setRenamingId(p.id)}
                onCancelRename={() => setRenamingId(null)}
                onCommitRename={(label) => handleRename(p.id, label)}
                onAskDelete={() =>
                  setPendingDelete({ id: p.id, label: p.label ?? 'Passkey' })
                }
              />
            ))}
          </ul>
        )}
      </section>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="¿Eliminar passkey?"
        description={
          pendingDelete ? (
            <>
              <strong>{pendingDelete.label}</strong> dejará de poder usarse para
              iniciar sesión. Si tienes otras passkeys o tu password sigues
              entrando con normalidad.
            </>
          ) : null
        }
        confirmLabel="Eliminar"
        cancelLabel="Cancelar"
        tone="danger"
        onConfirm={() => {
          if (pendingDelete) void handleDelete(pendingDelete.id);
        }}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

interface PasskeyRowProps {
  passkey: PasskeyResponse;
  isRenaming: boolean;
  onStartRename: () => void;
  onCancelRename: () => void;
  onCommitRename: (label: string) => void;
  onAskDelete: () => void;
}

function PasskeyRow({
  passkey,
  isRenaming,
  onStartRename,
  onCancelRename,
  onCommitRename,
  onAskDelete,
}: PasskeyRowProps) {
  const [draft, setDraft] = useState(passkey.label ?? '');

  useEffect(() => {
    if (isRenaming) setDraft(passkey.label ?? '');
  }, [isRenaming, passkey.label]);

  const subtitle = `Creada ${formatDate(passkey.created_at)}${
    passkey.last_used_at ? ` · Usada ${formatDate(passkey.last_used_at)}` : ''
  }${passkey.transports ? ` · ${passkey.transports}` : ''}`;

  return (
    <li
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.md,
        padding: spacing.md,
        backgroundColor: colors.surfaceMuted,
        borderRadius: radius.sm,
        border: `1px solid ${colors.border}`,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          fontSize: 22,
          flexShrink: 0,
        }}
      >
        🔑
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        {isRenaming ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (draft.trim()) onCommitRename(draft);
            }}
            style={{ display: 'flex', gap: spacing.sm }}
          >
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoFocus
              maxLength={100}
              style={{
                flex: 1,
                padding: `${spacing.xs}px ${spacing.sm}px`,
                border: `1px solid ${colors.border}`,
                borderRadius: radius.sm,
                fontSize: fontSize.sm,
                backgroundColor: colors.surface,
                color: colors.text,
              }}
            />
            <button
              type="submit"
              style={{
                padding: `${spacing.xs}px ${spacing.sm}px`,
                backgroundColor: colors.primary,
                color: colors.onPrimary,
                border: 'none',
                borderRadius: radius.sm,
                fontSize: fontSize.sm,
                cursor: 'pointer',
              }}
            >
              Guardar
            </button>
            <button
              type="button"
              onClick={onCancelRename}
              style={{
                padding: `${spacing.xs}px ${spacing.sm}px`,
                backgroundColor: 'transparent',
                color: colors.textMuted,
                border: 'none',
                borderRadius: radius.sm,
                fontSize: fontSize.sm,
                cursor: 'pointer',
              }}
            >
              Cancelar
            </button>
          </form>
        ) : (
          <>
            <div
              style={{
                fontSize: fontSize.md,
                fontWeight: fontWeight.medium,
                color: colors.text,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {passkey.label ?? '(sin nombre)'}
            </div>
            <div style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
              {subtitle}
            </div>
          </>
        )}
      </div>
      {!isRenaming ? (
        <div style={{ display: 'flex', gap: spacing.xs }}>
          <button
            type="button"
            onClick={onStartRename}
            style={{
              padding: `${spacing.xs}px ${spacing.sm}px`,
              backgroundColor: 'transparent',
              color: colors.primary,
              border: `1px solid ${colors.border}`,
              borderRadius: radius.sm,
              fontSize: fontSize.xs,
              fontWeight: fontWeight.medium,
              cursor: 'pointer',
            }}
          >
            Renombrar
          </button>
          <button
            type="button"
            onClick={onAskDelete}
            style={{
              padding: `${spacing.xs}px ${spacing.sm}px`,
              backgroundColor: 'transparent',
              color: colors.danger,
              border: `1px solid ${colors.border}`,
              borderRadius: radius.sm,
              fontSize: fontSize.xs,
              fontWeight: fontWeight.medium,
              cursor: 'pointer',
            }}
          >
            Eliminar
          </button>
        </div>
      ) : null}
    </li>
  );
}

