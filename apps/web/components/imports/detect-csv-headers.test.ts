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
});
