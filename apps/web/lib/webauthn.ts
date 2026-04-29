import {
  browserSupportsWebAuthn,
  startAuthentication,
  startRegistration,
} from '@simplewebauthn/browser';

import { passkeysApi } from '@finanzas/services';

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
 * Autentica al usuario por passkey. El email es necesario porque el
 * backend localiza la lista de credenciales del usuario antes de generar
 * el challenge (no usamos discoverable credentials en MVP).
 *
 * Devuelve los tokens. El caller (login page) los pone en el authStore.
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

function isAbort(err: unknown): boolean {
  if (err instanceof Error) {
    return err.name === 'NotAllowedError' || err.name === 'AbortError';
  }
  return false;
}
