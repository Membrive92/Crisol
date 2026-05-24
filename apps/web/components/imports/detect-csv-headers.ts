/**
 * Lee la primera línea de un CSV y devuelve los headers detectados.
 *
 * Heurística: prueba `,`, `;` y `\t`, elige el delimitador que da más
 * columnas. Soporta cabeceras entrecomilladas. Devuelve `null` si no se
 * pudo extraer nada útil. No es un parser completo — solo se usa para
 * sugerir nombres de columna en el wizard de mapeo.
 */
export async function detectCsvHeaders(file: File): Promise<string[] | null> {
  if (!isCsvFile(file)) return null;

  const text = await readFirstLine(file);
  if (!text) return null;

  const delimiters = [',', ';', '\t'] as const;
  let best: string[] = [];
  for (const delimiter of delimiters) {
    const parsed = splitCsvLine(text, delimiter);
    if (parsed.length > best.length) {
      best = parsed;
    }
  }

  return best.length > 1 ? best : null;
}

function isCsvFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith('.csv') || name.endsWith('.tsv');
}

const HEADER_PREVIEW_BYTES = 8192;

async function readFirstLine(file: File): Promise<string> {
  const sample = await readBlobAsText(file);
  const truncated = sample.slice(0, HEADER_PREVIEW_BYTES);
  const newlineIndex = truncated.search(/\r?\n/);
  return newlineIndex === -1 ? truncated : truncated.slice(0, newlineIndex);
}

/**
 * Lee un blob como texto con soporte de tildes españolas. Intenta UTF-8
 * primero; si detecta el carácter de reemplazo Unicode `�` (señal de
 * mojibake) reintenta con `windows-1252` — los extractos de bancos
 * españoles antiguos suelen venir en esa codificación. Espeja la
 * estrategia del backend (`parse_csv` prueba utf-8-sig → latin-1).
 */
function readBlobAsText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== 'string') {
        resolve('');
        return;
      }
      if (!result.includes('�')) {
        resolve(result);
        return;
      }
      const fallback = new FileReader();
      fallback.onload = () => {
        const r = fallback.result;
        resolve(typeof r === 'string' ? r : '');
      };
      fallback.onerror = () =>
        reject(fallback.error ?? new Error('No se pudo leer el fichero'));
      fallback.readAsText(blob, 'windows-1252');
    };
    reader.onerror = () => reject(reader.error ?? new Error('No se pudo leer el fichero'));
    reader.readAsText(blob, 'utf-8');
  });
}

function splitCsvLine(line: string, delimiter: string): string[] {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === delimiter && !inQuotes) {
      result.push(current.trim());
      current = '';
      continue;
    }
    current += char;
  }
  result.push(current.trim());
  return result.filter((value) => value.length > 0);
}
