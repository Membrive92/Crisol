import { describe, expect, it } from 'vitest';

import { detectCsvHeaders } from './detect-csv-headers';

function makeFile(content: string, name = 'movs.csv', type = 'text/csv'): File {
  return new File([content], name, { type });
}

describe('detectCsvHeaders', () => {
  it('extrae cabeceras separadas por coma', async () => {
    const file = makeFile('amount,date,description\n10,2026-01-01,café');
    expect(await detectCsvHeaders(file)).toEqual(['amount', 'date', 'description']);
  });

  it('detecta el delimitador con más columnas (punto y coma)', async () => {
    const file = makeFile('importe;fecha;concepto\n10;2026-01-01;café');
    expect(await detectCsvHeaders(file)).toEqual(['importe', 'fecha', 'concepto']);
  });

  it('soporta cabeceras entrecomilladas con coma dentro', async () => {
    const file = makeFile('"col, a","col b"\n1,2');
    expect(await detectCsvHeaders(file)).toEqual(['col, a', 'col b']);
  });

  it('devuelve null para ficheros que no son CSV', async () => {
    const file = makeFile('binarystuff', 'movs.xlsx', 'application/octet-stream');
    expect(await detectCsvHeaders(file)).toBeNull();
  });

  it('devuelve null cuando solo hay una columna detectable', async () => {
    const file = makeFile('singleheader\nvalor');
    expect(await detectCsvHeaders(file)).toBeNull();
  });

  it('cae a windows-1252 cuando UTF-8 produce mojibake (tildes españolas)', async () => {
    // "concepto,café\n1,2" codificado en Windows-1252.
    // El byte 0xE9 representa "é" en Win-1252, pero es inválido como
    // byte solitario en UTF-8 → el primer FileReader devuelve U+FFFD,
    // el helper detecta el reemplazo y reintenta con windows-1252.
    const bytes = new Uint8Array([
      0x63, 0x6f, 0x6e, 0x63, 0x65, 0x70, 0x74, 0x6f, // concepto
      0x2c, // ,
      0x63, 0x61, 0x66, 0xe9, // café (é = 0xE9 en Win-1252)
      0x0a, // \n
      0x31, 0x2c, 0x32, // 1,2
    ]);
    const file = new File([bytes], 'movs.csv', { type: 'text/csv' });
    expect(await detectCsvHeaders(file)).toEqual(['concepto', 'café']);
  });
});
