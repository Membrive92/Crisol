'use client';

import { useEffect, useState } from 'react';

import { passkeysApi } from '@crisol/services';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { PasskeyAbortError, registerPasskey, supportsPasskeys } from '@/lib/webauthn';

const DISMISS_KEY = 'finanzas_passkey_prompt_dismissed';

interface State {
  visible: boolean;
  loading: boolean;
  error: string | null;
}

/**
 * Banner discreto que aparece tras el login si el usuario:
 *  - usa un navegador con WebAuthn
 *  - aún no tiene passkeys
 *  - no ha descartado el prompt antes (localStorage)
 *
 * Activarla es un click → diálogo nativo del SO → registrada. Si el
 * usuario la descarta, no volvemos a preguntar.
 */
export function PasskeyPrompt() {
  const [state, setState] = useState<State>({
    visible: false,
    loading: false,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    async function check() {
      if (!supportsPasskeys()) return;
      try {
        if (window.localStorage.getItem(DISMISS_KEY) === '1') return;
      } catch {
        // localStorage bloqueado — seguimos comprobando.
      }
      try {
        const list = await passkeysApi.list();
        if (cancelled) return;
        if (list.length === 0) {
          setState((prev) => ({ ...prev, visible: true }));
        }
      } catch {
        // Backend no disponible o sesión caducada — silencio.
      }
    }
    void check();
    return () => {
      cancelled = true;
    };
  }, []);

  function dismiss(): void {
    try {
      window.localStorage.setItem(DISMISS_KEY, '1');
    } catch {
      // no-op
    }
    setState({ visible: false, loading: false, error: null });
  }

  async function handleActivate(): Promise<void> {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      await registerPasskey('Este dispositivo');
      // Tras registrar, dismiss permanente (ya tiene una passkey).
      try {
        window.localStorage.setItem(DISMISS_KEY, '1');
      } catch {
        // no-op
      }
      setState({ visible: false, loading: false, error: null });
    } catch (err) {
      if (err instanceof PasskeyAbortError) {
        setState((prev) => ({ ...prev, loading: false, error: null }));
        return;
      }
      const message = err instanceof Error ? err.message : 'No se pudo registrar';
      setState((prev) => ({ ...prev, loading: false, error: message }));
    }
  }

  if (!state.visible) return null;

  return (
    <div
      role="dialog"
      aria-label="Activar acceso rápido con passkey"
      style={{
        margin: spacing.md,
        padding: spacing.md,
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        display: 'flex',
        gap: spacing.md,
        alignItems: 'flex-start',
      }}
    >
      <div
        aria-hidden="true"
        style={{
          fontSize: 24,
          flexShrink: 0,
        }}
      >
        🔑
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: fontSize.md,
            fontWeight: fontWeight.semibold,
            color: colors.text,
            marginBottom: 2,
          }}
        >
          Activa el acceso rápido
        </div>
        <p
          style={{
            margin: 0,
            fontSize: fontSize.sm,
            color: colors.textMuted,
            lineHeight: 1.4,
          }}
        >
          Usa Touch ID, Windows Hello o tu PIN para entrar sin escribir
          contraseña. Tu huella nunca sale del dispositivo.
        </p>
        {state.error ? (
          <div
            style={{
              marginTop: spacing.sm,
              fontSize: fontSize.sm,
              color: colors.danger,
            }}
          >
            {state.error}
          </div>
        ) : null}
        <div
          style={{
            display: 'flex',
            gap: spacing.sm,
            marginTop: spacing.sm,
          }}
        >
          <button
            type="button"
            onClick={handleActivate}
            disabled={state.loading}
            style={{
              padding: `${spacing.xs}px ${spacing.md}px`,
              backgroundColor: colors.primary,
              color: colors.onPrimary,
              border: 'none',
              borderRadius: radius.sm,
              fontSize: fontSize.sm,
              fontWeight: fontWeight.semibold,
              cursor: state.loading ? 'not-allowed' : 'pointer',
              opacity: state.loading ? 0.7 : 1,
            }}
          >
            {state.loading ? 'Esperando dispositivo…' : 'Activar'}
          </button>
          <button
            type="button"
            onClick={dismiss}
            disabled={state.loading}
            style={{
              padding: `${spacing.xs}px ${spacing.md}px`,
              backgroundColor: 'transparent',
              color: colors.textMuted,
              border: 'none',
              borderRadius: radius.sm,
              fontSize: fontSize.sm,
              cursor: 'pointer',
            }}
          >
            Ahora no
          </button>
        </div>
      </div>
    </div>
  );
}
