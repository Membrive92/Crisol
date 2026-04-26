import { AxiosError } from 'axios';

/**
 * Convierte un error de la capa HTTP en un mensaje legible para el usuario.
 *
 * Distingue:
 * - Sin respuesta del servidor (red caída, CORS, server abajo).
 * - 5xx: mensaje genérico, no exponer detalles.
 * - 4xx con `detail` string: lo usa tal cual (los mensajes del backend están
 *   en español y son user-facing, p. ej. "El email ya está registrado").
 * - 422 Pydantic: extrae la primera entrada `msg` del array.
 * - Cualquier otro caso: cae al `fallback`.
 */
export function formatApiError(error: unknown, fallback: string): string {
  if (!(error instanceof AxiosError)) return fallback;

  if (error.response === undefined || error.response === null) {
    return 'No se pudo contactar con el servidor. Revisa tu conexión.';
  }

  const status = error.response.status;
  if (status >= 500) {
    return 'Error del servidor. Inténtalo en unos minutos.';
  }

  const data = error.response.data as unknown;
  const detail = (data as { detail?: unknown } | null)?.detail;

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown };
    if (typeof first.msg === 'string' && first.msg.trim()) {
      return `Datos inválidos: ${first.msg}`;
    }
  }

  return fallback;
}
