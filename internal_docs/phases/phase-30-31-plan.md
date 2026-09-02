# Crisol — Plan de fases PHASE-30 y PHASE-31

Estos cuatro documentos describen dos fases relacionadas pero
independientes del proyecto Crisol. Se entregan juntos porque comparten
contexto y conviene leerlos en orden.

## Orden de ejecución recomendado

```
                    PHASE-31                            PHASE-30
                    ────────                            ────────
              Saneamiento de cuentas              Rediseño módulo deuda
              (urgente, bloqueante)               (estructural, valor producto)
                       │                                   │
                       ▼                                   ▼
              ┌──────────────┐                  ┌───────────────────┐
              │ 31.1 Seed     │                  │ 30.1 categories   │
              │   transferencias                 │   .role enum     │
              │   bidireccional                  │                  │
              │ 31.2 Bulk fix │                  │ 30.2 /debt/      │
              │ 31.3 else_=0  │     primero ───▶│   category-summary
              │ 31.4 No valued│                  │ 30.3 /debt UI    │
              │ 31.5 _infer_  │                  │ 30.4 Capa 2      │
              │   transfer    │                  │   condensada    │
              └──────────────┘                  └───────────────────┘
```

PHASE-31 va antes porque:

1. **Resuelve un bug bloqueante**: hay usuarios con saldos
   incorrectos en producción (transferencias entrantes mal
   categorizadas). PHASE-30 no puede entregar valor encima de un
   modelo de cuentas roto.
2. **Limpia el modelo que PHASE-30 va a evolucionar**: 30.1
   introduce el enum `categories.role` que sustituye al flag
   `is_transfer`. La migración es más limpia si la categorización
   actual está saneada por 31.1.
3. **Los KPIs de la Capa 1 de PHASE-30 dependen del flujo de
   transferencias correctamente signado**. Si 31 no está, la
   tasa de esfuerzo del usuario reportado sale con valores
   incorrectos.

## Documentos del paquete (ya colocados en el repo)

| Archivo | Tipo | Ubicación |
|---|---|---|
| `phase-31-account-integrity.md` | Phase doc | [`internal_docs/phases/phase-31-account-integrity.md`](./phase-31-account-integrity.md) |
| `phase-30-debt-module-redesign.md` | Phase doc | [`internal_docs/phases/phase-30-debt-module-redesign.md`](./phase-30-debt-module-redesign.md) |
| `0003-debt-module-two-layer-architecture.md` | ADR | [`internal_docs/decisions/0003-debt-module-two-layer-architecture.md`](../decisions/0003-debt-module-two-layer-architecture.md) |
| `wireframe.md` | Wireframe / design exploration | [`internal_docs/design-explorations/debt-redesign-30/wireframe.md`](../design-explorations/debt-redesign-30/wireframe.md) |

## Resumen ejecutivo de cada fase

### PHASE-31 — Saneamiento de cuentas e integridad de saldos

**Problema**: cuatro causas distintas producen saldos incorrectos en
la app.

| Sub-fase | Qué resuelve |
|---|---|
| 31.1 | Transferencias entrantes categorizadas como gasto (causa principal del -21.000 € observado). |
| 31.2 | UI para identificar y corregir en bloque las transacciones afectadas. |
| 31.3 | `else_=Transaction.amount` cambia a `else_=0` — las tx sin categoría no contaminan el saldo. |
| 31.4 | Cuentas brokerage/crypto dejan de sumar al patrimonio neto agregado (hasta que exista módulo inversión real). |
| 31.5 | Heurística `_infer_transfer_kind` ampliada y robustecida con señal de categoría preexistente. |

**Coste estimado**: 1 sprint corto.
**Migraciones**: 1 (Alembic, idempotente, con backfill).
**Cambios breaking**: ninguno en API. Cambios en cómputo de saldos
visibles para el usuario al desplegar — conviene changelog explícito.

### PHASE-30 — Rediseño módulo deuda en dos capas

**Problema**: el módulo `/debt` actual exige onboarding (TIN, plazo,
fecha de inicio) para aportar valor. La mayoría de usuarios no
rellenan esos campos y ven el módulo vacío.

**Solución**: dividir en dos capas coexistentes:

- **Capa 1 (default, sin onboarding)**: análisis sobre flujo de
  categorías marcadas como deuda. Tasa de esfuerzo (bandas Banco
  España 30/35% sobre netos), pagos a deuda, composición,
  evolución. Funciona desde el primer extracto importado.
- **Capa 2 (opt-in, avanzado)**: lo que ya existe (liability
  accounts, cuadro francés condensado, wizard, saldo pendiente),
  conservado intacto pero presentado como detalle por contrato.

| Sub-fase | Qué entrega |
|---|---|
| 30.1 | Enum `categories.role` (`GENERIC`/`TRANSFER`/`DEBT_PAYMENT`/`DEBT_INTEREST`) + migración + seed update. |
| 30.2 | Endpoint `/debt/category-summary` + recalibración bandas a Banco España + fix `time_to_payoff`. |
| 30.3 | Rediseño visual de `/debt` con Capa 1 hero. |
| 30.4 | Capa 2: cuadro francés condensado anual/mensual + vinculación contrato-categoría. |
| 30.5 | Mobile parity (aplazable). |

**Coste estimado**: 2-3 sprints.
**Migraciones**: 2 (categories.role + accounts.category_id).
**Cambios breaking**: ninguno en API existente. Endpoints nuevos.

## Decisiones de producto cerradas (referencia rápida)

Estas decisiones se tomaron en la conversación previa y están
reflejadas en los docs:

| Cuestión | Decisión |
|---|---|
| Job to be done del módulo deuda | Reflejar gasto en categorías marcadas como deuda y analizar sobre eso (Capa 1). Las liability accounts conviven como detalle por contrato (Capa 2). |
| Posición de `/debt` en la nav | Top-level (sidebar). Se mueven páginas relevantes bajo `/debt/`. |
| Mercado objetivo | España first. Bandas Banco España, terminología español banco (TIN/TAE, "Tasa de esfuerzo"). |
| Cuadro de amortización | Condensado por defecto (resumen anual). Detalle mensual expandible. |
| Tasa de esfuerzo: estricta vs ampliada | Ambas, con toggle. |
| KPI "coste de la deuda" | Renombrado a "Pagos a deuda" (suma todo el flujo). Expandible muestra intereses+comisiones vs capital amortizado. |
| Patrimonio neto cuando hay categoría debt sin liability | UI explícita avisando que se subestima, CTA para vincular contrato. No se infiere automáticamente. |
| Operación financiada (PHASE-24) | Feature secundaria, visible solo en detalle de tx — no se promueve en `/debt`. |
| Brokerage / crypto en patrimonio neto | Excluidas hasta que exista módulo inversión real (PHASE-31.4). |
| Heurística de signo en transferencias | Ampliada y con fallback a `None` cuando ambigua, no a EXPENSE arbitrario (PHASE-31.5). |

## Hotfix antes del despliegue completo

PHASE-31.1 incluye un script SQL como anexo que el usuario reportante
puede ejecutar **hoy mismo** sobre su BD local para corregir los
saldos sin esperar al despliegue de la fase entera. Ver sección
"Hotfix antes de la migración" en `phase-31-account-integrity.md`.

Recomendación operativa:

1. Hacer `pg_dump` por seguridad.
2. Ejecutar el `SELECT` del hotfix para confirmar que los registros
   coinciden con lo esperado (~21.000 € de impacto).
3. Si encaja, ejecutar el `UPDATE`.
4. Verificar saldo en la UI.
5. Posteriormente, cuando PHASE-31.1 se despliegue formalmente, la
   migración Alembic será idempotente: detectará que las tx ya están
   bien y no hará nada sobre ellas.
