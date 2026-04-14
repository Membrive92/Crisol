# Lecciones aprendidas — Finanzas App

> Este archivo se actualiza CADA VEZ que se corrige un error que podría haberse
> prevenido. Leer al inicio de cada fase y añadir entradas durante la misma.

---

## Formato de una lección

```markdown
### [PHASE-X.Y] Título breve del error
**Error:** qué se hizo mal.
**Causa:** por qué ocurrió.
**Solución:** cómo se corrigió.
**Regla:** qué hacer siempre para evitarlo en el futuro.
```

---

## Lecciones

*Aún vacío. Las entradas se añaden durante el desarrollo.*

---

## Ejemplos de referencia (no son lecciones reales)

### [Ejemplo] No usar float para importes monetarios
**Error:** Se usó `float` para almacenar precios.
**Causa:** Inercia — float es el default numérico en Python.
**Solución:** Cambiar a `Decimal(14,2)` en el modelo y `NUMERIC` en PostgreSQL.
**Regla:** SIEMPRE usar `Decimal` para cualquier dato monetario. NUNCA `float`.

### [Ejemplo] Query sin filtro de user_id
**Error:** Un endpoint devolvía transacciones de todos los usuarios.
**Causa:** Se olvidó añadir `.where(Transaction.user_id == user_id)` en el repo.
**Solución:** Añadir filtro y test que verifica aislamiento entre usuarios.
**Regla:** TODA query a tablas de dominio DEBE filtrar por `user_id`.
Añadir test de aislamiento multi-usuario.
