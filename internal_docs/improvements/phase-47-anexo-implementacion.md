# PHASE-47 — Anexo de implementación (contratos exactos)

**Propósito**: reducir la probabilidad de fallo de implementación cerrando
los puntos donde el plan + respuestas dejan margen de improvisación.
**Regla de lectura**: ante conflicto, este anexo manda sobre el plan;
las respuestas (`phase-47-respuestas.md`) mandan sobre ambos en las
decisiones D1–D14. Nada de este anexo reabre una decisión.

---

## A. Contrato del id determinista y del `accept` (D1)

```python
def inbox_item_id(kind: str, transaction_ids: Sequence[UUID]) -> str:
    canonical = kind + "|" + ",".join(sorted(str(t) for t in transaction_ids))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

- `kind` es el enum del detector (`QUOTA_MATCH`, `FINANCING_BIRTH`,
  `CYCLE_CLOSE`, `POSSIBLE_SETTLEMENT`, `CYCLE_GAP`, `UNCLASSIFIED`).
  16 hex bastan (volumen ~decenas; colisión irrelevante, y si ocurriera el
  accept la detecta por payload).
- **Flujo de `accept/resolve`** (idéntico para ambos):
  1. Recalcular la clasificación SOLO del set de transacciones del id
     (no toda la bandeja) con el mismo motor.
  2. Si el item resultante tiene el mismo id **y** el mismo
     `proposal_hash` (sha256 del payload de propuesta serializado
     canónicamente) → ejecutar.
  3. Id no derivable ya (tx resuelta entre medias) → `404 {"detail":
     "el item ya no existe — la bandeja cambió"}`.
  4. Id derivable pero propuesta distinta → `409 {"detail": "la
     propuesta cambió, recarga la bandeja", "current": <item nuevo>}`.
- **Idempotencia**: segundo `accept` del mismo id tras éxito → `404`
  (la tx ya está resuelta; el recálculo del paso 1 lo produce solo).
- Prohibido cachear items entre peticiones en servidor: el estado ES la
  BD; la bandeja se deriva siempre.

## B. Máquina de estados del item y LÍMITES del undo

Estados (derivados, no persistidos salvo lo indicado):

```
DERIVED ──accept/resolve──► ACTED(manual)     [rastro: filas existentes]
DERIVED ──auto (solo caso A con prueba)──► ACTED(auto_applied=TRUE)
DERIVED ──dismiss──► DISMISSED               [tabla debt_inbox_dismissals]
ACTED ──undo──► DERIVED (reaparece en la siguiente lectura)
DISMISSED ──undismiss──► DERIVED
```

**Límite duro del undo — solo acciones de tipo VÍNCULO**: des-marcar cuota
(+ des-enlazar tx), des-vincular transferencia/amortización, revertir
`counts_as_expense`. **El undo NO cubre acciones de tipo ASISTENTE**: si
un item B/B' lanzó el asistente "nueva financiación" y este creó pasivo +
cuadro + vínculos, la reversión es la del propio asistente/flujos de plan
existentes (borrar plan), no un botón de la bandeja. Motivo: un undo que
borra cuentas y cuadros en un click es una pistola cargada; el de
vínculos es inocuo. La UI del item tipo-asistente no muestra "Deshacer":
muestra "Gestionar plan →".

`auto_applied` es `BOOLEAN NULL`: **NULL = acción pre-47 (origen
desconocido)** — la sección "Resuelto automáticamente" pinta SOLO
`TRUE` post-47. No reinterpretar el pasado.

## C. Detector #1 (nuevo — cuota por importe+fecha), spec exacta

Entrada: cargo OUT no resuelto. Candidatas: cuotas `PENDING` de planes
vivos cuyo pasivo esté atribuido a la cuenta del cargo
(`settlement_account_id` == tx.account_id, o `category_id` como señal
secundaria proponente).

```
match si |tx.amount − cuota.payment| ≤ DEBT_QUOTA_MATCH_TOLERANCE_EUR (1.00)
      y  |tx.date − cuota.due_date| ≤ DEBT_QUOTA_DATE_WINDOW_DAYS (7)
```

- **0 candidatas** → sigue la cascada.
- **1 candidata** → item `QUOTA_MATCH` con propuesta (cuota concreta,
  sugerencia de gasto del motor PHASE-45 adjunta con su motivo).
- **≥2 candidatas** (dos planes con cuota igual en ventana) → item con
  lista de candidatas ordenada por |Δfecha|; **jamás elegir en silencio**.
- La constante es NUEVA (H1: no existe tolerancia heredable). Ambas van a
  config con estos defaults y se calibran en la parada 2 contra
  mayo/junio.
- El texto del concepto puede AÑADIR confianza a la propuesta
  (anotación "el concepto menciona amortización"), nunca filtrar
  candidatas (D3).

## D. Detector #2 (generalización de `find_financing_matches`), spec exacta

Entrada: abono IN no resuelto. Señal estructural única de decisión:

```
candidatos = pasivos con cuadro cuyo capital_total == tx.amount (±0,01)
             y fecha de alta del plan dentro de ±FINANCING_BIRTH_WINDOW_DAYS (10)
             del abono   [si el plan aún no existe: candidato "crear plan"]
```

- Corroboración (sube confianza, NO decide): existe OUT espejo de igual
  importe en ±3 días en la misma cuenta.
- **0 candidatos y sin espejo** → sigue cascada (no es financiación).
- **0 candidatos pero par espejo neto-cero presente** → item
  `FINANCING_BIRTH` con propuesta "crear plan" (asistente), importe
  precargado.
- **1 candidato plan existente** → item con propuesta "vincular a {plan}".
- **≥2** → item con candidatos (el silencio de PHASE-46 ante ambigüedad
  se sustituye por esto — es el único cambio de comportamiento).
- `find_mirror_charge` del import NO se toca; conjuntos disjuntos
  garantizados porque la bandeja solo consume no-resueltas (D11).

## E. Invariante del ciclo — fórmula exacta

```
ciclo(t) = [fecha_cargo_anterior, fecha_cargo_actual)     # semiabierto
compras_netas(ciclo) = Σ OUT(tarjeta, ciclo) − Σ IN_reembolso(tarjeta, ciclo)
invariante: |compras_netas − (cargo_ciclo + Σ financiado_del_ciclo)|
            ≤ DEBT_CYCLE_TOLERANCE_EUR
```

- `IN_reembolso` = abonos en la cuenta tarjeta no clasificados como
  financiación (una devolución de compra reduce el recibo). Sin
  clasificar por texto: cualquier IN de la tarjeta que no sea pata de
  financiación cuenta como reembolso.
- Fechas en fecha-valor local del extracto (las que trae el import), sin
  conversión TZ — los extractos españoles vienen en fecha local.
- Primer ciclo de una tarjeta (sin cargo anterior): el invariante no
  aplica; el cargo va a bandeja como `UNCLASSIFIED` con la sugerencia del
  motor 45.
- El resultado del invariante se persiste NO — se deriva; el detalle de la
  tarjeta lo calcula on-read.

## F. Guardarraíl del import (D9) — dos señales concretas, en orden

1. **Huella de cabecera por cuenta**: al confirmar cada import se guarda
   (en `import_batches`, columna aditiva `header_fingerprint`) el hash de
   la lista ordenada de columnas del fichero. En el preview, si la huella
   del fichero coincide con la huella histórica de OTRA cuenta y no con
   la elegida → aviso bloqueable "este formato coincide con los imports
   de {otra cuenta}".
2. **Solape de dedup-hash cruzado**: calcular los dedup de las filas del
   preview y comprobarlos contra transacciones existentes de OTRAS
   cuentas. Solape > `IMPORT_CROSS_OVERLAP_PCT` (20%) → aviso "N filas
   ya existen en {cuenta}: ¿fichero en la cuenta equivocada?".
- Ambas son avisos **bloqueables** (confirmar exige tick explícito), no
  prohibiciones — el usuario puede tener razón.
- **Parada (a) del D9**: si con los CSV reales de BBVA ninguna señal
  discrimina banco↔tarjeta, preguntar antes de añadir heurísticas.

## G. Checklist mecánico de 47.0 (ejecutar en este orden)

1. `git mv` de los 6 ficheros + `git mv` de los schemas de deuda a
   `debt/schemas.py` (identificarlos: los usados SOLO por los 6).
2. Shim temporal en `accounts/schemas.py`:
   `from ..debt.schemas import DebtHealthKpis  # DEPRECATED: retirar en 47.C`
   (solo si quedan importadores internos; si no, nada).
3. Actualizar imports (`ruff --fix` + búsqueda manual de strings de
   módulo en tests).
4. **Verificación de no-cambio**:
   - `alembic upgrade head` sin migraciones nuevas (0 diffs de esquema).
   - Golden pre/post: serializar respuesta de `debt-health`,
     `get_balances` y `category-summary` con el seed de tests → diff
     vacío byte a byte.
   - `pytest` completo verde SIN tocar ningún assert.
   - `grep -rn "from ..accounts.*debt\|amortization\|installments"
     backend/` → solo el shim.
5. Commit propio: `refactor(debt): consolidate domain (no behavior
   change) — Refs: PHASE-47.A, H2`.
6. URLs: **cero cambios** (D6). El router de los endpoints movidos sigue
   registrado donde estaba.

## H. Esquema del item y tabla de errores

```python
class DebtInboxItem(BaseModel):
    id: str                    # §A
    kind: InboxKind
    transaction_ids: list[UUID]
    occurred_at: datetime      # la más antigua del set
    amount: Decimal
    proposal: Proposal | None  # None solo en UNCLASSIFIED
    proposal_hash: str
    reason: str                # frase de negocio, español
    confidence: Literal["arithmetic","structural","suggested"]
    candidates: list[Candidate] = []   # cuando hay ambigüedad
    suggested_counts_as_expense: bool | None
    suggestion_reason: str | None      # motor PHASE-45, literal
```

Orden de la respuesta: `occurred_at ASC, id ASC` (estable). Sin
paginación en v1 (volumen ~decenas; si un mes supera 50 items, eso es un
bug de detectores, no un caso de paginar).

| Código | Cuándo |
|---|---|
| 404 | id no derivable (tx ya resuelta / nunca existió) |
| 409 | id derivable con propuesta distinta (payload `current` incluido) |
| 422 | `resolve` con variante no ofrecida en `candidates` |

## I. Migraciones (DDL exacto, 4 aditivas)

```sql
-- 1
CREATE TABLE debt_inbox_dismissals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  item_id VARCHAR(16) NOT NULL,
  transaction_ids UUID[] NOT NULL,
  kind VARCHAR(24) NOT NULL,
  reason TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (user_id, item_id)
);
-- 2  (rastro auto vs manual; NULL = pre-47 desconocido, §B)
ALTER TABLE transactions ADD COLUMN amortization_auto_applied BOOLEAN NULL;
-- 3  (atribución D4)
ALTER TABLE accounts ADD COLUMN settlement_account_id UUID NULL
  REFERENCES accounts(id) ON DELETE SET NULL;
-- 4  (guardarraíl F)
ALTER TABLE import_batches ADD COLUMN header_fingerprint VARCHAR(64) NULL;
```

`downgrade` de las cuatro = drop simple. Ninguna toca datos existentes.

## J. Property test de no-silencio — universo en SQL, no en el clasificador

```sql
-- Universo (independiente de la cascada):
SELECT t.id FROM transactions t
JOIN accounts a ON a.id = t.account_id
WHERE t.user_id = :u AND t.occurred_at BETWEEN :from AND :to
  AND (
    a.kind IN ('LIABILITY','CREDIT_CARD')                      -- toca deuda
    OR a.id IN (SELECT settlement_account_id FROM accounts
                WHERE settlement_account_id IS NOT NULL)        -- cuenta de cargo
  )
  AND t.resolution IS NULL          -- el criterio de "no resuelta" vigente
```

Assert: cada id del universo ∈ (items de bandeja ∪ acciones con rastro del
periodo ∪ dismissals). El universo se construye con esta query en el test,
**no** llamando al clasificador (D3).

## K. Fixtures y goldens

| Fichero | Contenido | Origen |
|---|---|---|
| `fixtures/debt/cycle_green.json` | Mes mayo/junio real anonimizado: compras + cargo que cierra | **Parada 2 — lo aporta el usuario (D5)** |
| `fixtures/debt/cycle_gap_july.json` | Julio real: cargos + par 700,26 + 0 compras en tarjeta | Ídem |
| `fixtures/debt/synthetic_two_cards.json` | 2 tarjetas, cuotas iguales en ventana → ambigüedad #1 | Sintético |
| `fixtures/debt/financing_ambiguous.json` | Abono que casa con 2 planes → candidatos #2 | Sintético |
| Golden 47.0 | debt-health/get_balances/category-summary serializados | Seed de tests |

Las dos fixtures reales NO se inventan: 47.B queda en parada hasta
recibirlas. Construirlas con datos sintéticos "parecidos" invalida el
caso de regresión — es exactamente el error de H4.

## L. Riesgos residuales conocidos (con su parada)

| Riesgo | Mitigación/parada |
|---|---|
| Los CSV de BBVA no traen señal discriminante para F | Parada F — preguntar |
| `settlement_account_id` ambiguo con 4 cargos/6 pasivos hasta que el usuario declare | El flujo (c) de D4: la bandeja pide la atribución, no se adivina |
| Cuotas ajustadas a mano (PHASE-24.1 permite editar) rompen el match por importe | La tolerancia ±1 € y la ventana ±7d absorben lo normal; si un plan editado queda sistemáticamente fuera → item con candidatas, que es el comportamiento correcto |
| El shim de schemas se eterniza | Entrada en backlog con caducidad 47.C, verificada en el checklist de retirada |
| Recalibrar tolerancias "para que la bandeja quede bonita" | Regla anti-tuning: las constantes solo cambian en la parada 2 con los datos de mayo/junio delante, documentado en el phase doc |
