import {
  browserSupportsWebAuthn,
  startAuthentication,
  startRegistration,
} from '@simplewebauthn/browser';

import { passkeysApi } from '@crisol/services';

/**
 * Detecta si el navegador soporta WebAuthn. Útil para esconder los botones
 * de passkey en navegadores muy viejos. Llamar después de mount (no SSR).
 */
export function supportsPasskeys(): boolean {
  if (typeof window === 'undefined') return false;
  return browserSupportsWebAuthn();
}

export class PasskeyAbortError extends Error {
  constructor(message = 'Operación cancelada') {
    super(message);
    this.name = 'PasskeyAbortError';
  }
}

/**
 * Registra una nueva passkey para el usuario logueado.
 *
 * Pide al backend las options, llama a `navigator.credentials.create`
 * via SimpleWebAuthn y envía la attestation de vuelta. Devuelve la
 * passkey persistida.
 *
 * Si el usuario cancela el diálogo del SO (Touch ID/Hello), lanza
 * `PasskeyAbortError` para que el caller pueda diferenciarlo de un
 * error real.
 */
export async function registerPasskey(label?: string) {
  const options = (await passkeysApi.registrationOptions()) as Parameters<
    typeof startRegistration
  >[0]['optionsJSON'];

  let credential;
  try {
    credential = await startRegistration({ optionsJSON: options });
  } catch (err) {
    if (isAbort(err)) throw new PasskeyAbortError();
    throw err;
  }

  return passkeysApi.registrationVerify({
    credential,
    label: label ?? null,
  });
}

/**
 * Autentica al usuario por passkey en modo email-driven (botón explícito).
 * El backend filtra por las credenciales del email; al verificar valida
 * además que el credential_id corresponda al usuario.
 */
export async function authenticateWithPasskey(email: string) {
  const options = (await passkeysApi.authenticationOptions(email)) as Parameters<
    typeof startAuthentication
  >[0]['optionsJSON'];

  let credential;
  try {
    credential = await startAuthentication({ optionsJSON: options });
  } catch (err) {
    if (isAbort(err)) throw new PasskeyAbortError();
    throw err;
  }

  return passkeysApi.authenticationVerify({ email, credential });
}

/**
 * Inicia un flujo Conditional UI: pide options sin email y deja la promesa
 * de `startAuthentication` viva en background. El navegador mostrará
 * passkeys disponibles en el autocompletado del input email (que debe
 * llevar `autoComplete="email webauthn"`); cuando el usuario elija una,
 * esta función resuelve con los tokens.
 *
 * Devuelve `null` si el navegador no soporta autofill condicional o si el
 * usuario cancela.
 */
export async function startConditionalAuthentication(): Promise<
  { access_token: string; refresh_token: string; token_type: string } | null
> {
  if (typeof window === 'undefined') return null;
  const supportsConditional =
    typeof PublicKeyCredential !== 'undefined' &&
    'isConditionalMediationAvailable' in PublicKeyCredential &&
    (await (
      PublicKeyCredential as unknown as {
        isConditionalMediationAvailable: () => Promise<boolean>;
      }
    ).isConditionalMediationAvailable());
  if (!supportsConditional) return null;

  const options = (await passkeysApi.authenticationOptions()) as Parameters<
    typeof startAuthentication
  >[0]['optionsJSON'];

  let credential;
  try {
    credential = await startAuthentication({
      optionsJSON: options,
      useBrowserAutofill: true,
    });
  } catch (err) {
    if (isAbort(err)) return null;
    throw err;
  }

  return passkeysApi.authenticationVerify({ credential });
}

function isAbort(err: unknown): boolean {
  if (err instanceof Error) {
    return err.name === 'NotAllowedError' || err.name === 'AbortError';
  }
  return false;
}
