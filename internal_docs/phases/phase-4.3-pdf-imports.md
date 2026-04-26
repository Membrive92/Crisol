# PHASE-4.3 — PDF imports

**Estado**: ✅ completada
**Rama**: `feat/phase-4.3-pdf-imports`
**PR**: —
**Fecha de merge**: 2026-04-26

## Objetivo

Aceptar extractos bancarios en PDF (con texto extraíble) en el mismo
pipeline de importación que CSV/XLSX, sin tocar el modelo de datos ni
los endpoints.

## Qué se implementó

- **`backend/app/modules/imports/parser.py`**:
  - Nuevo formato `pdf` en `detect_format` (extensión `.pdf` o
    `application/pdf`).
  - `parse_pdf(payload)` con `pdfplumber.extract_tables()`. La primera
    tabla del PDF marca la cabecera; tablas en páginas sucesivas se
    concatenan y la cabecera repetida se descarta.
  - Helper `_pdf_clean` para normalizar celdas (colapsa saltos de
    línea internos y espacios múltiples).
  - PDFs sin tablas (por ejemplo, escaneados sin OCR) se rechazan con
    `ParseError("No se detectaron tablas en el PDF (¿escaneado?)")`,
    el job termina como `failed` con el mensaje en `error_log`.
- **Dependencias backend**:
  - Nueva: `pdfplumber>=0.11.0` (runtime).
  - Nueva dev: `reportlab>=4.0.0` para generar PDFs en tests.
- **Wizard frontend**:
  - `apps/web/components/imports/upload-step.tsx` añade `.pdf` a
    `ACCEPTED_EXTENSIONS` y al texto del input.
  - `mapping-step.tsx` aclara que los CSV detectan cabeceras y que
    XLSX/PDF requieren teclear el nombre.
- **Tests**:
  - 6 nuevos en `tests/test_imports_parser.py` (detección por
    extensión y mime, tabla básica, multipágina con header repetido,
    PDF sin tablas, bytes no-PDF).
  - 2 nuevos en `tests/test_imports.py` (PDF válido completa el job;
    `.txt` rechazado mantiene el comportamiento anterior). El test
    previo de PDF inválido pasa a llamarse
    `test_import_invalid_pdf_marks_failed` para reflejar el cambio
    de semántica (antes fallaba por "formato no soportado", ahora
    por "PDF inválido").

## Flujo técnico

```
   POST /imports (file=.pdf)         (sin cambios en API)
        │
        ▼
   detect_format → "pdf"
        │
        ▼
   parse_pdf
   ├─ pdfplumber.open(BytesIO)
   ├─ for page in pages:
   │     tables += page.extract_tables()
   ├─ if not tables → ParseError
   ├─ headers ← primera fila de la primera tabla
   └─ filas ← concat de todas las tablas, descartando cabeceras
       repetidas y filas vacías
        │
        ▼
   pipeline 4.1 (mapping → validación → SHA-256 → dedup → persist)
```

## Archivos clave

- `backend/app/modules/imports/parser.py` — `detect_format`,
  `parse_pdf`, `_pdf_clean`.
- `backend/pyproject.toml` — `pdfplumber` (runtime), `reportlab` (dev).
- `backend/tests/test_imports_parser.py` — 6 tests nuevos del parser.
- `backend/tests/test_imports.py` — 2 tests HTTP nuevos.
- `apps/web/components/imports/upload-step.tsx` — `.pdf` aceptado.
- `apps/web/components/imports/mapping-step.tsx` — copy aclarado.

## Endpoints añadidos

Ninguno. `POST /imports`, `GET /imports`, `GET /imports/{id}` siguen
exactamente igual que en 4.1.

## Decisiones tomadas

- **`pdfplumber` antes que `pdfminer.six` o `pypdf`**. `extract_tables`
  hace el trabajo pesado y la heurística por defecto cubre el caso
  "tabla con líneas visibles", que es como salen los extractos PDF
  bancarios. Otras libs requerirían escribir nuestra propia detección.
- **Sin almacenar el PDF original**, igual que con CSV/XLSX. El
  usuario re-sube si quiere reprocesar.
- **Header global desde la primera tabla**. Algunos PDFs traen tablas
  distintas por página; la estrategia simple cubre el 80–90% de
  extractos. Si hace falta más sofisticación se añade en una iteración
  siguiente sin tocar el contrato.
- **Sin OCR ni fallback a visión en esta fase**. Queda explícito como
  follow-up tras PHASE-5.1 cuando el módulo `ai/` esté maduro.

## Verificación

- [x] `pytest tests/` — 69/69 (8 nuevos).
- [x] `ruff check app/` verde.
- [x] `mypy app/` verde (49 archivos).
- [x] `pnpm lint` + `typecheck` + `test` verdes.
- [ ] Smoke manual con un PDF real bancario — pendiente del usuario.

## Limitaciones conocidas

- PDFs escaneados (sin texto) — **ya cubierto** vía fallback de visión
  (follow-up post 5.1, branch `feat/pdf-vision-fallback`): el service
  detecta `NoTablesInPdfError`, renderiza páginas con `pypdfium2` y
  llama a `ai.service.extract_bank_statement_page`. Limitado a las
  primeras 5 páginas para no saturar Ollama.
- Si las celdas tienen contenido en varias líneas (caso raro), se
  colapsan a un único string separado por espacios.
- La heurística de tablas de `pdfplumber` requiere bordes visibles.
  PDFs con tablas "lógicas" sin líneas (estilo plain text alineado por
  espacios) podrían no detectarse — caería en "No se detectaron
  tablas".
- No se intenta reconciliar tablas con número de columnas distinto
  entre páginas: se usa el header de la primera y se truncan las
  filas si las páginas siguientes traen más columnas.

## Próxima fase

PHASE-5.1 — Receipts backend (Ollama + qwen2.5-vl, MinIO, módulo
`receipts/`).
