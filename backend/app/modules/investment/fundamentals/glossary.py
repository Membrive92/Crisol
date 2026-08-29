"""Qué es cada partida de los estados financieros (PHASE-44.23).

Hermano de `analysis/engine/glossary.py`, para las 49 partidas canónicas. Aquí
lo que hay que decir no son fórmulas sino tres cosas que el usuario no puede
adivinar de la etiqueta:

1. **Qué es** la partida en las cuentas de una empresa.
2. **Si la publica la empresa o la deduce la app.** Varias partidas se derivan
   por una identidad contable (§4.4) porque el filing no las etiqueta. «Total
   pasivo» de NIKE es una de ellas — y el propio informe lo avisa arriba: *«el
   cuadre del balance no es verificable: el pasivo total no venía en el filing
   y se dedujo restando el patrimonio del activo»*. Que una fila sea deducida
   cambia cuánto puedes fiarte de ella.
3. **La convención de signo**, que es donde más se confunde uno: en este modelo
   TODAS las partidas se guardan positivas con semántica fija, así que el capex,
   los dividendos pagados y las recompras son números positivos aunque sean
   salidas de caja.

Igual que el glosario de métricas, un test exige que las claves sean
EXACTAMENTE las 49 del catálogo: ni una partida sin definición, ni una
definición huérfana de una partida que se renombró.
"""

from __future__ import annotations

ITEM_HELP: dict[str, str] = {
    # ── assets_current ──────────────────────────────────────────────
    "cash": (
        "Dinero disponible en caja y bancos más las inversiones a muy corto plazo "
        "convertibles en efectivo de forma inmediata. Es un saldo a la fecha de "
        "cierre, no un flujo del ejercicio. Si el emisor solo publica la línea que "
        "engloba el efectivo restringido, se toma esa."
    ),
    "current_financial_assets": (
        "Inversiones financieras que la empresa espera vender o recuperar dentro del "
        "año (valores negociables, depósitos) y que no son efectivo. Si el filing no "
        "publica el concepto se lee como cero: en XBRL no se etiqueta lo que no se "
        "tiene."
    ),
    "receivables": (
        "Lo que los clientes deben por ventas ya realizadas y todavía no han pagado, "
        "neto de la provisión por insolvencias. Es un saldo a la fecha de cierre: no "
        "dice cuánto se vendió, sino cuánto queda pendiente de cobro."
    ),
    "inventory": (
        "Materias primas, producto en curso y mercancía terminada pendientes de "
        "vender, valorados netos de deterioro. Su ausencia en el filing se lee como "
        "cero: una empresa de servicios sencillamente no tiene existencias."
    ),
    "current_assets": (
        "Total del bloque: el activo que se espera convertir en efectivo dentro del "
        "año. Ya engloba efectivo, inversiones a corto, deudores y existencias, así "
        "que no se suma con ellos. Falta en los balances no clasificados (bancos, "
        "muchas socimis), y entonces la liquidez no se puede calcular."
    ),
    # ── assets_noncurrent ───────────────────────────────────────────
    "ppe_net": (
        "Terrenos, edificios, instalaciones y equipos que la empresa usa para operar, "
        "ya descontada la amortización acumulada: por eso «neto». En socimis y REIT "
        "se toma de la inversión inmobiliaria, que cumple el mismo papel."
    ),
    "goodwill": (
        "Sobreprecio pagado al comprar otras empresas por encima del valor razonable "
        "de lo adquirido. Solo nace de adquisiciones y no se amortiza: se revisa por "
        "deterioro. Su ausencia se lee como cero, porque nadie se olvida de publicar "
        "el fondo de comercio que tiene."
    ),
    "intangibles": (
        "Activos sin soporte físico distintos del fondo de comercio —marcas, "
        "patentes, licencias, software, carteras de clientes—, netos de amortización. "
        "El fondo de comercio queda fuera a propósito: tiene su propia fila. Su "
        "ausencia se lee como cero."
    ),
    "deferred_tax_assets": (
        "Derecho a pagar menos impuestos en el futuro: diferencias temporales, bases "
        "imponibles negativas y créditos fiscales pendientes de aplicar. Se recoge la "
        "cifra neta no corriente que publica el emisor. Su ausencia se lee como cero."
    ),
    "total_assets": (
        "Total de cuanto posee la empresa, corriente y no corriente: es el total del "
        "balance por el lado del activo, así que no se suma con los bloques que lo "
        "componen. Es además el término contra el que se contrasta el cuadre activo = "
        "pasivo + patrimonio."
    ),
    # ── liabilities_current ─────────────────────────────────────────
    "short_term_debt": (
        "Deuda financiera nacida ya a corto plazo: pólizas de crédito, papel "
        "comercial y préstamos a menos de un año. La parte de los préstamos a largo "
        "que vence este ejercicio tiene su propia fila, para no contarla dos veces. "
        "Su ausencia se lee como cero."
    ),
    "ltd_current_portion": (
        "La parte del principal de préstamos y bonos a largo plazo que vence en los "
        "próximos doce meses y que por eso se reclasifica al pasivo corriente. No es "
        "deuda nueva: el resto de esos mismos contratos sigue contado en la deuda a "
        "largo. Su ausencia se lee como cero."
    ),
    "accounts_payable": (
        "Lo que se debe a proveedores por bienes y servicios ya recibidos y aún no "
        "pagados. Es financiación de la propia actividad, no deuda financiera: no "
        "entra en el cálculo de la deuda total ni de la deuda neta."
    ),
    "lease_liabilities_current": (
        "Compromisos de alquiler que las normas IFRS 16 / ASC 842 obligan a reconocer "
        "en el balance, en la parte que vence dentro del año. No es deuda bancaria: "
        "la deuda total la excluye por defecto y hay una variante aparte que sí la "
        "suma. Su ausencia se lee como cero."
    ),
    "current_liabilities": (
        "Total del bloque: todo lo exigible dentro del año, incluidos proveedores, "
        "deuda a corto, la parte corriente de la deuda a largo y los arrendamientos a "
        "corto. Ya los engloba, así que no se suma con ellos. Falta en los balances "
        "no clasificados."
    ),
    # ── liabilities_noncurrent ──────────────────────────────────────
    "long_term_debt": (
        "Préstamos, bonos y demás deuda financiera cuyo vencimiento va más allá del "
        "año; el tramo que vence en los próximos doce meses tiene su propia fila. A "
        "diferencia de otras partidas, si el filing no la publica queda como hueco y "
        "nunca como cero: un cero fabricaría una empresa sin deuda."
    ),
    "lease_liabilities_noncurrent": (
        "Compromisos de alquiler reconocidos en balance (IFRS 16 / ASC 842) que "
        "vencen a más de un año; su ausencia se lee como cero. Cuando el emisor no "
        "separa el tramo corto del largo, la app acumula aquí el importe entero y lo "
        "marca como deducido: es un supuesto, no una identidad contable."
    ),
    "deferred_tax_liabilities": (
        "Impuestos que se acabarán pagando en ejercicios futuros por diferencias "
        "temporales entre el criterio contable y el fiscal. No es deuda financiera y "
        "no entra en la deuda total. Su ausencia se lee como cero."
    ),
    "total_liabilities": (
        "Total de lo que la empresa debe, corriente y no corriente: engloba los "
        "bloques anteriores y no se suma con ellos. Muchos filings no publican esta "
        "línea y entonces la app la deduce como activo − patrimonio; en ese caso el "
        "cuadre del balance se cumple por construcción y queda declarado no "
        "verificable."
    ),
    # ── equity ──────────────────────────────────────────────────────
    "share_premium": (
        "Lo que los accionistas aportaron por encima del valor nominal de las "
        "acciones: dinero puesto por los socios, no beneficio generado por el "
        "negocio. Algunos emisores publican capital y prima en una sola línea, y "
        "entonces aquí figura el conjunto. Su ausencia se lee como cero."
    ),
    "retained_earnings": (
        "Suma de los beneficios que la empresa ha ido reteniendo en lugar de "
        "repartir, arrastrada desde su origen. Puede ser negativa por pérdidas "
        "acumuladas o por repartir más de lo ganado, caso habitual en los REIT y "
        "socimis: ahí el emisor la publica en positivo y la app le invierte el signo."
    ),
    "treasury_stock": (
        "Acciones propias que la empresa ha recomprado y todavía no ha amortizado, "
        "valoradas a lo que costaron. Se guarda en positivo por convención de la app, "
        "pero en el balance RESTA del patrimonio neto. Su ausencia se lee como cero."
    ),
    "equity": (
        "Total del bloque: lo que quedaría para los accionistas una vez pagado todo "
        "el pasivo. Ya engloba prima de emisión, reservas acumuladas y autocartera, "
        "así que no se suma con ellas. Puede salir negativo —recompras por encima de "
        "las reservas— sin que sea un error del dato."
    ),
    # ── income_gross ────────────────────────────────────────────────
    "revenue": (
        "Importe facturado por la actividad ordinaria del ejercicio, antes de restar "
        "ningún coste. Es la primera línea de la cuenta de resultados y el "
        "denominador de todos los márgenes. Si el filing no la publica queda hueca: "
        "nunca se lee como cero."
    ),
    "cogs": (
        "Coste directo de lo vendido —materiales, compras de mercadería, mano de obra "
        "de producción—, sin estructura ni fuerza comercial. Muchas empresas de "
        "servicios no lo separan, y entonces queda hueco: sin él no hay margen bruto "
        "ni días de inventario o de pago."
    ),
    # ── income_operating ────────────────────────────────────────────
    "sga_expense": (
        "Gastos de estructura, comerciales y de administración del ejercicio: sueldos "
        "no productivos, marketing, oficinas. Se guarda en positivo aunque en las "
        "cuentas reste. Si el emisor sólo publica los generales y de administración, "
        "es esa cifra la que entra."
    ),
    "rd_expense": (
        "Gasto en investigación y desarrollo llevado a resultados del ejercicio; lo "
        "que la empresa capitaliza no aparece aquí. Se guarda en positivo aunque "
        "reste. Si el filing no lo publica se lee como cero: quien invierte en I+D lo "
        "etiqueta."
    ),
    "depreciation_amortization": (
        "Cargo del ejercicio por el desgaste del inmovilizado y la amortización de "
        "intangibles. Es un gasto que no supone salida de caja, y por eso vuelve a "
        "sumarse al EBIT para obtener el EBITDA. Se guarda en positivo aunque reste."
    ),
    "impairments": (
        "Pérdidas por deterioro del ejercicio: fondo de comercio o activos cuyo valor "
        "en libros deja de recuperarse. En positivo aunque reste; ausente se lee como "
        "cero. Si el emisor las publica netas con las plusvalías, el neto entra aquí "
        "y aquéllas quedan a cero."
    ),
    "gains_on_sale_of_business": (
        "Resultado obtenido al vender una filial, un negocio o activos productivos. "
        "Es atípico, así que el motor lo resta del EBIT para dejar el resultado "
        "recurrente. Ausente se lee como cero, y queda a cero si el emisor lo publicó "
        "neto con los deterioros."
    ),
    "ebit": (
        "Beneficio de la actividad antes de intereses e impuestos. Si el filing "
        "publica la línea operativa se toma tal cual; cuando falta —hay emisores que "
        "dejaron de etiquetarla— la app la DERIVA como resultado antes de impuestos + "
        "gasto financiero, y sin pretax, como resultado neto + impuestos."
    ),
    # ── income_financial ────────────────────────────────────────────
    "interest_expense": (
        "Coste de la deuda devengado en el ejercicio. Se guarda en positivo aunque "
        "reste. Sólo se lee como cero cuando el filing sitúa en cero la deuda a largo "
        "plazo: con deuda viva y sin dato queda hueco, para no regalar una cobertura "
        "de intereses infinita."
    ),
    # ── income_tax ──────────────────────────────────────────────────
    "pretax_income": (
        "Beneficio del ejercicio antes del impuesto sobre sociedades. Es dato "
        "reportado; en emisores que sólo publican el desglose por jurisdicción se "
        "suman nacional y extranjero para reconstruir el total. De aquí sale el EBIT "
        "cuando éste hay que derivarlo."
    ),
    "taxes": (
        "Gasto por impuesto sobre beneficios devengado en el ejercicio, corriente más "
        "diferido. No es lo que la empresa desembolsó: eso es «Impuestos pagados», en "
        "el estado de flujos, y las dos cifras difieren. Se guarda en positivo aunque "
        "reste."
    ),
    # ── income_result ───────────────────────────────────────────────
    "net_income": (
        "Beneficio que queda tras impuestos: el último renglón de la cuenta de "
        "resultados, el que nutre reservas y dividendos. Se toma del resultado "
        "atribuible a la matriz y, si el emisor no lo publica así, del resultado "
        "consolidado con minoritarios incluidos."
    ),
    # ── income_shares ───────────────────────────────────────────────
    "shares_basic": (
        "Número medio ponderado de acciones en circulación a lo largo del ejercicio, "
        "sin contar dilución potencial. Es la que consume el motor: la caja libre por "
        "acción (R8) y el dividendo por acción se calculan con ella."
    ),
    "shares_diluted": (
        "La misma media ponderada, pero suponiendo ejercidas las opciones, "
        "convertibles y planes de acciones vivos. Sirve para ver cuánta dilución "
        "potencial hay frente a la básica; se ingiere y se muestra, pero ninguna "
        "métrica del catálogo la usa todavía."
    ),
    "shares_outstanding_eop": (
        "Acciones vivas en una fecha concreta, no una media del ejercicio. Suele "
        "venir de la portada del filing, cuya fecha es posterior al cierre. Es la que "
        "da la capitalización en los múltiplos y hace de testigo cuando las acciones "
        "medias llegan en otra escala."
    ),
    "sbc_expense": (
        "Gasto por retribuir a empleados con acciones. No sale caja, pero diluye al "
        "accionista, y por eso el motor lo resta de la caja libre en una de las "
        "pruebas de cobertura del dividendo. En positivo; ausente se lee como cero."
    ),
    # ── cashflow_operating ──────────────────────────────────────────
    "cfo": (
        "La caja que el negocio ordinario ha generado o consumido en el ejercicio, "
        "tras los cobros y pagos del circulante y tras pagar impuestos. Es el TOTAL "
        "del bloque de explotación: la variación de existencias y los impuestos "
        "pagados ya están dentro, no se suman aparte. Lleva su signo real y puede ser "
        "negativo."
    ),
    "wc_change_inventory": (
        "Movimiento del almacén durante el ejercicio, dentro del ajuste de circulante "
        "del flujo de explotación. Se guarda en positivo cuando las existencias "
        "AUMENTAN, que es justo cuando consumen caja. Ya está incluida en el flujo de "
        "explotación: no la sumes aparte."
    ),
    "taxes_paid": (
        "La caja entregada realmente a Hacienda durante el ejercicio, que no tiene "
        "por qué coincidir con el impuesto sobre beneficios de la cuenta de "
        "resultados (devengo frente a pago). Se guarda en positivo aunque sea una "
        "salida. Ya está dentro del flujo de explotación."
    ),
    # ── cashflow_investing ──────────────────────────────────────────
    "capex": (
        "Pagos por adquirir inmovilizado material (instalaciones, equipos, inmuebles) "
        "durante el ejercicio. Se guarda en POSITIVO aunque sea una salida de caja: "
        "la caja libre se calcula restándolo del flujo de explotación. Junta "
        "mantenimiento y crecimiento, que el filing no separa."
    ),
    "acquisitions": (
        "Caja pagada por comprar otras empresas o negocios, neta del efectivo que "
        "venía dentro de lo comprado. Se guarda en positivo aunque sea una salida de "
        "caja. Si el filing no la publica se lee como cero: en XBRL no se etiqueta lo "
        "que no ha ocurrido."
    ),
    "divestitures": (
        "Cobros por vender negocios o activos productivos durante el ejercicio; es "
        "una ENTRADA de caja, al revés que las adquisiciones. Recoge el importe "
        "cobrado, no el beneficio de la venta: esa plusvalía va en la cuenta de "
        "resultados. Ausente en el filing se lee como cero."
    ),
    # ── cashflow_financing ──────────────────────────────────────────
    "dividends_paid": (
        "Caja repartida efectivamente a los accionistas durante el ejercicio, que "
        "puede no coincidir con el dividendo declarado: lo que se registra aquí es el "
        "pago, no el anuncio. Se guarda en positivo aunque sea una salida de caja. "
        "Ausente en el filing se lee como cero."
    ),
    "buybacks": (
        "Caja empleada en recomprar acciones propias durante el ejercicio. Se guarda "
        "en positivo aunque sea una salida de caja. Es el desembolso de ese año, "
        "distinto de la autocartera del balance, que es el saldo de acciones propias "
        "en cartera valorado al coste."
    ),
    "share_issuance": (
        "Caja recibida por emitir acciones nuevas, incluido lo que entra cuando los "
        "empleados ejercitan sus opciones. Es una ENTRADA de caja, al revés que la "
        "recompra. Ausente en el filing se lee como cero."
    ),
    "debt_change": (
        "Diferencia entre lo que la empresa ha tomado prestado y lo que ha amortizado "
        "en el ejercicio. Lleva signo propio, al contrario que el resto del bloque: "
        "positivo = se endeuda neto, negativo = devuelve deuda neta. Si el emisor no "
        "publica la línea neta, la app la arma sumando emisiones y restando "
        "amortizaciones."
    ),
}
"""`item_key` → definición, en el orden de los tres estados."""
