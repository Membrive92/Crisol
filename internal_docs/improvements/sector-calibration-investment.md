# Calibración sectorial del motor de análisis — perfiles, rangos y portantes

**Estado**: 📐 especificación de calibración v1 (seed) — lista para implementar
**Mecanismo base**: ya existe (DESIGN v2 Dec.8/D4: `scoring_thresholds` por
sector × norma con `direction`, 4 cortes, `applies`, `model_variant`;
`METRIC_CATALOG` como fuente única de claves). Este documento aporta el
**contenido**: taxonomía sectorial, matriz de aplicabilidad, bandas por
sector, portantes por pregunta y los cambios mínimos de implementación.
**Invariante que NO cambia**: esto son *perfiles* del motor de acciones, no
motores nuevos. El motor bancario completo (NIM, CET1, morosidad, LCR)
exige canónico ampliado → variante futura de la familia de motores, fuera
de alcance aquí.
**Regla anti-tuning (recordatorio de DESIGN §8)**: jamás ajustar una banda
"para que salga verde" una posición propia. Las bandas se calibran con
fuentes, se versionan (`thresholds_version`), y se revisan con runs reales.

---

## 1. Cierres de las tres cuestiones abiertas (pantallazo 2026-08)

| Cuestión | Decisión | Razón |
|---|---|---|
| **Q2 en financieras** | `applies=false`, mismo mecanismo que D2–D5 | FCF y EBITDA carecen de sentido en un banco: el capex/EBITDA no describe su economía |
| **Q3 en financieras** | `applies=false` (discrepo del "yo la dejaría") | Una comprobación de consistencia solo informa si al menos una de las dos medidas es válida. Comparar dos números inválidos diverge por razones estructurales (los vaivenes de WC *son* el negocio bancario) → ámbar permanente → **fatiga de alarmas**. En financieras, la calidad de caja queda en Q1 y Q5 |
| **Portantes** | Formalizados, con **cuarto estado de pregunta: `no_auditado`** (gris) | Un ratio cualquiera no pesa lo mismo que el M-Score. Si falta un portante, la pregunta no presume verde: se declara no auditada con la razón. El verde se gana, no se hereda del silencio |

---

## 2. Taxonomía sectorial interna (Dec.15: propia, derivada de SIC)

12 sectores + `GENERIC` (fallback universal). Mapeo SIC pragmático — rangos
principales; empresa real que caiga raro = punto de parada, no adivinar:

| Sector interno | Rangos SIC (principales) | Flags |
|---|---|---|
| `UTILITIES` | 4900–4991 | |
| `TELECOM` | 4800–4899 | |
| `ENERGY` | 1311, 1381–1389, 2911, 4610–4612, 5171 | cíclico |
| `MATERIALS` | 1000–1499 (minería), 2800–2833, 2840–2899, 3300–3399 | cíclico |
| `INDUSTRIALS` | 1600–1731, 3400–3599, 3600–3699 (eq.), 3700–3799, 8711 | |
| `CONSUMER_STAPLES` | 2000–2199 (alim./tabaco), 2080–2086, 5411, 5122 | |
| `CONSUMER_DISCRETIONARY` | 2200–2799 (textil/edición), 3000s selec., 5200–5999 (retail exc. 5411), 5812, 7000–7999 selec. | WC negativo normal en retail |
| `HEALTHCARE` | 2834–2836 (pharma/bio), 3841–3851, 8000–8099 | goodwill alto normal |
| `TECHNOLOGY` | 3570–3579, 3674, 7370–7379 | SBC alto; caja neta típica |
| `REAL_ESTATE_REIT` | 6500, 6798 | `is_reit=true` → FFO |
| `FINANCIALS` | 6020–6199 (banca), 6200–6299, 6300–6411 (seguros), 6712 | `is_financial=true` → whitelist §5 |
| `GENERIC` | todo lo demás | fallback |

`sic_mapping.py` implementa esta tabla como rangos ordenados; primer match
gana; sin match → `GENERIC` + nota en el run.

---

## 3. Mecánica de resolución y seed (sparse)

1. **Resolución de umbral** para (métrica, security): fila
   `(sector, std, metric_key)` → si no existe, **fallback**
   `(GENERIC, std, metric_key)`. El seed solo materializa **deltas**: el
   set GENERIC completo + las filas sectoriales que difieren (tablas §4) o
   desactivan (`applies=false` + `not_applicable_reason`).
2. **Migración aditiva**: `ALTER TABLE scoring_thresholds ADD COLUMN
   not_applicable_reason TEXT NULL;` — la razón viaja al run y la UI la
   muestra (nunca "N/A" mudo).
3. **Estructura del seed** (`thresholds/seed.py`):

```python
SECTOR_PROFILES: dict[Sector, SectorProfile] = {
    Sector.UTILITIES: SectorProfile(
        overrides={
            "S4": Bands(lt=4.0, mid=(4.0, 5.5), gt=5.5),
            "S2": Bands(gt=3.5, mid=(2.0, 3.5), lt=2.0),
            ...
        },
        not_applicable={},          # métricas apagadas con razón
    ),
    Sector.FINANCIALS: SectorProfile(
        overrides={...},            # §5 whitelist re-bandeada
        not_applicable={
            "S4": "EBITDA carece de sentido en banca",
            "Q2": "FCF/EBITDA no describen la economía de un banco",
            ...
        },
    ),
}
```

4. Cambio de cualquier banda/perfil ⇒ nuevo `thresholds_version` (hash ya
   diseñado). Cambio de portantes o del estado `no_auditado` ⇒ **bump de
   `ENGINE_VERSION`** (son lógica de motor, no datos).

---

## 4. Bandas por sector — deltas sobre GENERIC (calibración v1, con anclas)

Solo se listan las filas que difieren de GENERIC. Formato
verde · ámbar · rojo según `direction`.

### S4 — Deuda neta / EBITDA (GENERIC: <2 · 2–3,5 · >3,5)

| Sector | Bandas | Ancla |
|---|---|---|
| UTILITIES | <4 · 4–5,5 · >5,5 | Mediana IG del sector 5,1×; >4× "comercialmente normal" en reguladas |
| TELECOM | <2,5 · 2,5–4 · >4 | Mediana IG comm services 2,39×; 4× habitual en cable/telecom |
| REAL_ESTATE_REIT | <6 · 6–8 · >8 | Sector opera 5–7×; media REIT-Office 8,5× — el juicio principal del REIT es D6/FFO, no S4 |
| ENERGY | <1,5 · 1,5–2,5 · >2,5 | Cíclico: el apalancamiento debe ser bajo porque el EBITDA del denominador es el del punto del ciclo que no conoces |
| MATERIALS | <2 · 2–3 · >3 | Cíclico moderado |
| CONSUMER_STAPLES | <2,5 · 2,5–3,5 · >3,5 | Cluster 2–3,5× |
| HEALTHCARE | <2,5 · 2,5–3,5 · >3,5 | Ídem |
| TECHNOLOGY | <1 · 1–2 · >2 | Asset-light rara vez >2×; caja neta típica |
| FINANCIALS | `applies=false` | EBITDA sin sentido en banca |

### S4b — Deuda neta / EBIT (solo donde S4 cambia; desplaza ~+1,5)

UTILITIES <5,5·5,5–7·>7 · TELECOM <4·4–5,5·>5,5 · REIT <7,5·7,5–9,5·>9,5 ·
ENERGY <2·2–3,5·>3,5 · TECHNOLOGY <1,5·1,5–3·>3 · FINANCIALS off.

### S2 — Cobertura de intereses EBIT (GENERIC: >6 · 3–6 · <3)

| Sector | Bandas | Razón |
|---|---|---|
| UTILITIES | >3,5 · 2–3,5 · <2 | Caja regulada y estable soporta cobertura menor |
| TELECOM | >4 · 2,5–4 · <2,5 | Ingresos por suscripción |
| REAL_ESTATE_REIT | >2,5 · 1,8–2,5 · <1,8 | Estructura del sector |
| TECHNOLOGY | >10 · 5–10 · <5 | Sin excusa para cobertura baja |
| FINANCIALS | `applies=false` | El interés es la materia prima del banco, no una carga |

### S6 — Cobertura por caja: mismos deltas relativos que S2. FINANCIALS off.

### S1 / S3 — Apalancamiento y autonomía

- FINANCIALS: **S1 off** (pasivo/activo ~90% ES el negocio). **S3
  re-bandeada como proxy de capital**: >8% · 5–8 · <5 (equity/activos de un
  banco), con nota fija en UI: *"proxy contable; no es capital regulatorio
  (CET1)"*.
- UTILITIES: S1 <0,7 · 0,7–0,8 · >0,8 (estructura regulada más apalancada).

### L1/L2 — Liquidez corriente (GENERIC L1: >1,5 · 1–1,5 · <1)

| Sector | Bandas L1 | Nota |
|---|---|---|
| CONSUMER_STAPLES / _DISCRETIONARY | >1,2 · 0,8–1,2 · <0,8 | + **regla cruzada RC-1** (§6): CCC<0 degrada el rojo a info |
| UTILITIES / TELECOM | >1 · 0,7–1 · <0,7 | Estructuralmente bajas; su riesgo real es refinanciación → L4 pesa más |
| FINANCIALS | `applies=false` | La liquidez bancaria es LCR/NSFR, fuera del canónico |

### L4 — Muro de vencimientos: GENERIC universal. FINANCIALS off (misma razón).

### R6 — ROA (GENERIC: >5% · 2–5 · <2)

| Sector | Bandas |
|---|---|
| **FINANCIALS** | **>1,2% · 0,7–1,2 · <0,7** — la banda bancaria: un banco con ROA 1% es un buen banco. Junto a R5 y S3, el núcleo del veredicto en financieras |
| UTILITIES | >3,5 · 1,5–3,5 · <1,5 |

### R9 / R9b — ROIC / CROIC

UTILITIES: R9 >7·5–7·<5, R9b >5·3–5·<3 (retorno regulado ≈ permitido).
FINANCIALS: ambos off (el capital invertido no modela un balance bancario).

### R10 — GP/Activos, Novy-Marx (GENERIC: >0,33 · 0,18–0,33 · <0,18)

- Asset-heavy (UTILITIES, ENERGY, MATERIALS, TELECOM, REIT):
  >0,15 · 0,08–0,15 · <0,08.
- TECHNOLOGY / HEALTHCARE: >0,45 · 0,30–0,45 · <0,30.
- FINANCIALS: off (no existe cogs).
- *El 0,33 GENERIC es el umbral del paper original sobre mercado amplio US;
  los deltas son calibración propia marcada como v1.*

### A2 (días inventario) y C3 — `applies=false` con razón "sin inventario
material" en: UTILITIES, TELECOM, TECHNOLOGY(software), REIT, FINANCIALS.

### D — Cobertura del dividendo (GENERIC D2: <60 · 60–85 · >85)

| Sector | Delta | Nota |
|---|---|---|
| UTILITIES | D2 <75 · 75–95 · >95 | Payout alto es su modelo; **la banda alta NO relaja C7/B4**: dividendo por encima del FCF financiado con deuda sigue siendo rojo — la utility que lo hace crónicamente es exactamente el caso que C7 existe para cazar |
| CONSUMER_STAPLES | D2 <70 · 70–90 · >90 | |
| REAL_ESTATE_REIT | D6 <80 · 80–95 · >95 | FFO payout alto es estructural |
| FINANCIALS | D2/D3/D4/D5 off → **D1 es LA métrica**: <50 · 50–70 · >70 | El dividendo bancario se juzga sobre beneficio (y supervisor) |

### F5 — Goodwill (GENERIC: <30% · 30–50 · >50)

HEALTHCARE / TECHNOLOGY (serial acquirers estructurales): <40 · 40–60 · >60.

### Forense

- M-Score, Z'', F-Score, Sloan, F7: FINANCIALS `applies=false` (ya vigente).
- REIT: **Sloan off** — razón: "la D&A domina los accruals; juzgar por FFO";
  Z'' se mantiene con `model_variant='uncalibrated'` (ya vigente).
- **F7 (Montier) con denominador variable**: los checks no aplicables al
  sector (2/3 en sin-inventario) salen del cómputo; bandas sobre los
  aplicables; mínimo 4 checks aplicables para computar, si no →
  `not_computable`.
- Piotroski: sin deltas — es Δ-interanual por construcción, sector-agnóstico.
- Márgenes R1–R4: sin bandas absolutas por diseño (deriva) — ya eran
  sector-agnósticos. E3 (estabilidad) sin deltas: la predictibilidad se
  exige igual a todos.

---

## 5. FINANCIALS — whitelist completa (la tabla que el pantallazo empezó)

| Métrica | Estado | Razón corta |
|---|---|---|
| R5 ROE, **R6 ROA (banda bancaria)**, S3 (proxy capital) | ✅ re-bandeadas | El núcleo del juicio bancario book-based |
| D1, D7, T1–T4 | ✅ | Payout sobre beneficio + trayectoria |
| Q1 (CFO/NI), Q5 (extraordinarios), Q4 (anomalía fiscal) | ✅ | Calidad del beneficio que sí es medible |
| C2 (NI vs CFO), C6 (dilución), E1/E2 (evolución/common-size) | ✅ | |
| Q2, Q3, S4/S4b, S2/S6, L1–L4, R9/R9b/R10, A1–A5, C1/C3, D2–D5, B1–B3, M/Z/F/Sloan/F7, ST1–ST3 | ❌ `applies=false` | Cada una con su `not_applicable_reason` sembrada (EBITDA/FCF/WC/cobertura sin sentido bancario; modelos no calibrados para financieras) |
| B4 | ✅ adaptada | dividendo > beneficio ∧ (deuda↑ ∨ emisión↑) → rojo |

**Pregunta 4 ("¿aguanta un golpe?") en FINANCIALS: `no_auditado`
permanente** con razón fija: *"La resiliencia bancaria es capital
regulatorio (CET1, LCR) — fuera del canónico 10-K. Requiere el motor
bancario (variante futura)."* Fingir auditarla con Z'' sería calcular
basura con semáforo.

**Pregunta 1 en FINANCIALS**: portantes [Q1, C2]; si computa, el verde sale
con badge fijo *"cobertura forense limitada en financieras"* — verde
ganado, pero honesto sobre su alcance.

---

## 6. Reglas cruzadas nuevas (mecánica, no bandas)

| Clave | Regla |
|---|---|
| **RC-1** | Si A5 (CCC) < 0 → un rojo de L1/L2 se degrada a **info** con texto "modelo de working capital negativo (cobra antes de pagar): fortaleza estructural, no riesgo de liquidez". El caso Inditex/supermercados |
| **RC-2** | En UTILITIES con D2 en ámbar/rojo, el informe enlaza explícitamente C7/B4: la pregunta correcta no es "¿payout alto?" sino "¿quién financia el exceso?" |

---

## 7. Portantes por pregunta (borrador v1 — lógica de motor, ENGINE_VERSION)

| Pregunta | Portantes GENERIC | FINANCIALS | REIT |
|---|---|---|---|
| 1 ¿Contabilidad fiable? | M-Score, Sloan | Q1, C2 (+badge cobertura limitada) | M-Score, Q1 (Sloan off) |
| 2 ¿Genera caja real? | Q1, tendencia FCF (E1) | Q1 | Q1, tendencia FFO |
| 3 ¿El dividendo cabe? | D2, B4 | D1, B4 | D6, B4 |
| 4 ¿Aguanta un golpe? | Z'', S2 (+stress) | — → `no_auditado` permanente | Z''(uncal.), S2(REIT) |

**Regla del cuarto estado**: cualquier portante `not_computable` →
pregunta = `no_auditado` (gris, con la lista de qué falta). Verde exige
todos los portantes computados Y en verde. Las métricas no-portantes
modulan (ámbar por acumulación) pero no otorgan el verde por sí solas.

---

## 8. Implementación (cambios mínimos, en orden)

1. Migración: `not_applicable_reason` en `scoring_thresholds` (aditiva).
2. `sic_mapping.py`: tabla §2 (rangos ordenados, fallback GENERIC, nota en
   run si fallback).
3. `thresholds/seed.py`: `SECTOR_PROFILES` (§3) generando GENERIC completo
   + deltas §4/§5. `thresholds_version` recalculado.
4. Engine: resolución con fallback GENERIC; `applies=false` → resultado
   `not_applicable` portando la razón (distinto de `not_computable`: uno es
   "no tiene sentido aquí", otro es "faltan datos" — la UI los distingue).
5. `synthesis.py`: portantes §7 + estado `no_auditado` + badge financieras
   + reglas RC-1/RC-2. **Bump ENGINE_VERSION**.
6. UI: razón visible en cada `not_applicable`; gris de `no_auditado` con su
   lista; badges.

### Tests (goldens nuevos, uno por perfil crítico)

| Fixture sintético | Verifica |
|---|---|
| Utility apalancada 4,8× | S4 ámbar (no rojo); D2 88% ámbar; RC-2 enlaza C7 |
| Retail WC negativo (CCC −20d, L1 0,85) | RC-1: L1 info, no rojo |
| Banco (ROA 1,0%, equity/TA 7%, payout 55%) | Whitelist: S4/Q2/Q3 `not_applicable` con razón; R6 verde en banda bancaria; P4 `no_auditado`; P1 verde con badge |
| REIT | D6 en uso; Sloan `not_applicable`; F7 denominador variable |
| Falta un portante (sin CFO) | P1/P2 → `no_auditado`, jamás verde |
| Resolución | Métrica sin fila sectorial → banda GENERIC; con fila → sectorial |

## 9. Fuera de alcance

Motor bancario completo (NIM/CET1/NPL/LCR → canónico ampliado, familia de
motores) · split banca/seguros dentro de FINANCIALS (un perfil v1) ·
calibración IFRS (sigue `uncalibrated` hasta adapter EU) · recalibración
con runs reales (posterior, con la regla anti-tuning delante).
