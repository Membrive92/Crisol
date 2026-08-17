# PHASE-47.G — El extracto manda, y la app desconfía sola

**Estado**: 🚧 pendiente prueba manual
**Rama**: `main` (push directo)
**Fecha**: 2026-08-17

## Objetivo

Cerrar la familia de bugs «la dirección del dinero se decidió con algo que
describe el movimiento en vez de con algo que lo demuestra», que lleva
[PHASE-28, 32, 34, 37, 38, 46, 47.F] — nueve entradas en `lessons.md` con la
misma raíz.

## El bug que lo destapó

Seis movimientos que el banco ABONÓ entraron como gasto. Cada uno con su prueba
en la cadena de saldos del propio extracto:

| fecha | importe | salto del saldo |
|---|---|---|
| 06-abr | 19,98 | 6.398,18 → 6.418,16 |
| 06-may | 42,99 | 3.976,30 → 4.019,29 |
| 25-jun | 41,35 | 2.204,88 → 2.246,23 |
| 06-jul | 33,58 | 730,96 → 764,54 |
| 15-jul | 21,97 | 3.046,25 → 3.068,22 |
| 20-jul | 79,00 | 2.417,00 → 2.496,00 |

Son devoluciones (Amazon, Sanareva). **238,87 €** con el signo cambiado, o sea
**477,74 €** de desvío — el doble de error que si se hubieran perdido.

**La causa.** `_parse_amount_signed` sólo devuelve «entrada» con un `+`
explícito; un `33,58 €` a secas devuelve *«el extracto no declara dirección»* y
la decisión cae al texto y luego al kind de la categoría, que para un Amazon
dice «compras». Mirando UNA fila es correcto —hay extractos que son magnitudes
puras, como el de la tarjeta—. Mirando el FICHERO deja de serlo: si ese banco
escribe los cargos en negativo, un positivo desnudo es un abono.

## Qué se implementó

### 1. La convención de signos es del FICHERO, no de la fila

`_file_declares_signs(rows, mappings)`: si alguna línea del lote trae un cargo
en negativo, un positivo desnudo pasa a valer `+1`. Si no hay ni un negativo, el
fichero son magnitudes y todo sigue como estaba.

### 2. La cadena de saldos MANDA sobre la conjetura

`resolve_flows_from_balance_chain` dejaba en paz cualquier fila que ya tuviera
dirección: sólo rellenaba huecos. Por eso una conjetura que *acertaba a decidir*
—mal— nunca llegaba a contrastarse. Ahora, cuando el salto del saldo contradice
la dirección asignada, gana el salto, y el preview lo dice
(«N movimientos entraban con la dirección al revés»).

Gobierna **sólo la dirección**: si la cadena confirma el sentido, no se toca la
transfer-ness, que la decide el texto y de la que el saldo no sabe nada.

Sigue exigiendo que el salto sea EXACTAMENTE el importe: si entre dos saldos hay
un movimiento que no vemos, no se toca nada.

### 3. La app compara con el banco, sin que nadie se lo pida

- `AccountBalance.statement_gap` — lo que la app calcula menos lo que dijo el
  extracto. El testigo (`anchored_statement_balance`) llevaba desde PHASE-39 en
  la BD y **sólo se escribía**; con eso, un desvío de 700,26 € vivió semanas.
- `find_statement_seams` — dónde falta extracto. Si el saldo anterior implícito
  de una fila no aparece en ninguna otra, entre medias hay movimientos que no
  tenemos, y se dice entre qué fechas y por cuánto. En los datos del usuario:
  **1.211,95 € entre el 30-jun y el 5-jul de 2026**.
- `statementIntegrityNotices` en `@crisol/ui` (capa PURA, compartible con móvil)
  y el aviso pintado en la pantalla de cuentas.
- `make audit-balances` para el informe completo por consola.

**Por qué el audit NO entra en `make verify`**: audita datos, no código. Un
extracto sin importar bloquearía un commit que no tiene nada que ver, y un gate
que falla por algo ajeno se acaba ignorando.

## Archivos clave

- `backend/app/modules/personal_finance/imports/service.py` — `_file_declares_signs`, `resolve_flows_from_balance_chain`
- `backend/app/modules/personal_finance/accounts/repository.py` — `find_statement_seams`
- `backend/app/modules/personal_finance/accounts/service.py` — `statement_gap` por cuenta
- `packages/ui/src/statement-integrity.ts` — las frases, compartidas
- `backend/scripts/audit_balances_vs_statement.py`, `backend/scripts/classify_from_statement_balance.py` (`--fix-contradictions`)

## Migraciones

Ninguna.

## Verificación

- [x] BE tests · mypy · ruff · black · FE typecheck · lint · knip
- [x] Cada test nuevo verificado **rompiendo la línea concreta** que protege, con
      la sonda afirmando que la rotura entró.
- [x] Un caso lo destapó el método: la sonda sobre `if index == 0` **no tumbó
      nada** — era código redundante, y el guardarraíl real era el `if not
      earlier`. Se simplificó y se verificó el de verdad.
- [ ] Prueba manual del usuario

## Datos del usuario corregidos

Las seis filas se corrigieron con `classify_from_statement_balance
--fix-contradictions --apply` (cada una firmada por la aritmética del banco, no
por criterio) y se re-ancló. BBVA cuadra al céntimo: 1.778,19 €.

Tras ello la cadena de BBVA sólo se rompe en dos sitios, y los dos son
legítimos: el 1 de enero (principio de la historia) y el 5 de julio, donde
empieza el extracto de julio — que es el hueco que el detector reporta.

## Limitaciones conocidas

- El detector de huecos sólo ve cuentas con columna Saldo en su extracto. Un
  banco que no la publique no tiene testigo, y ahí la app no puede desconfiar.
- `find_statement_seams` carga todas las filas con saldo del usuario en cada
  petición de `/accounts/balances` (~370 en los datos reales) y resuelve en
  Python. A esta escala no se nota; con años de historia habría que acotarlo por
  cuenta o materializarlo.
- Sin paridad móvil: la capa de frases es compartida, pero la pantalla de
  cuentas de móvil todavía no las pinta.
