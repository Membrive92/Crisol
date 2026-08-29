"""Catálogo de banderas del engine (PHASE-44.9).

Una `Flag` sólo existe cuando SALTA, y entonces trae su `message` redactado. Pero
la síntesis usa banderas como **señales** de sus cuatro preguntas, y ahí hace
falta nombrarlas también cuando NO han saltado —«se comprobó y no se encendió» es
información, no silencio—. Sin un nombre estático, esas señales viajaban como la
clave cruda y el usuario leía literalmente

    M-Score · B4_dividend_funded_externally

en la pantalla del veredicto.

Aquí vive ese nombre. Es un mapa `key → etiqueta` puro: ni BD, ni reloj, ni red.
El `message` de la bandera encendida sigue siendo la explicación completa; esto
es sólo cómo se llama.
"""

from __future__ import annotations

from typing import NamedTuple

FLAG_LABELS: dict[str, str] = {
    # ── Cruces evolutivos (capa 1.5) ──────────────────────────────
    "C1_receivables_vs_revenue": "Cobros creciendo por encima de las ventas",
    "C2_income_without_cash": "Beneficio que no se convierte en caja",
    "C3_inventory_vs_cogs": "Inventario creciendo por encima del coste de ventas",
    "C4_underinvestment": "Infrainversión (capex por debajo de la amortización)",
    "C5_goodwill_without_acquisitions": "Fondo de comercio que sube sin compras",
    "C6_dilution": "Dilución sostenida del accionista",
    "C7_shareholder_return_funded_by_debt": "Retorno al accionista financiado con deuda",
    "C8_acquired_growth": "Crecimiento comprado, no orgánico",
    "growth_externally_funded": "Crecimiento por encima de lo autofinanciable",
    # ── Fiscalidad y soporte del dividendo (capa 3) ───────────────
    "Q4_tax_anomaly": "Tipo impositivo anómalo",
    "Q4_tax_persistently_low": "Tipo impositivo persistentemente bajo",
    "B1_debt_competes_with_dividend": "La deuda compite con el dividendo",
    "B2_interest_priority": "Los intereses tienen prioridad sobre el dividendo",
    "B4_dividend_funded_externally": "Dividendo financiado con deuda o emisión",
    # ── Reglas cruzadas sectoriales (PHASE-44.21) ─────────────────
    "RC1_negative_working_capital": "Modelo de circulante negativo (cobra antes de pagar)",
    "RC2_utility_payout_needs_funding_check": "Payout alto en una regulada: mira quién lo financia",
    # ── Calidad del dato (capa 1 y forense) ───────────────────────
    "ebt_divergence": "El resultado antes de impuestos no cuadra con EBIT − intereses",
    "ebt_reconstruction_divergence": "Resultado antes de impuestos reconstruido con divergencia",
    "fcf_divergence": "Las dos formas de medir la caja libre no cuadran",
    "z_score_uncalibrated_for_reit": "Z''-Score sin calibrar para socimis",
}
"""Las claves de bandera que el engine puede emitir, con su nombre legible.

Un test comprueba que el conjunto coincide EXACTAMENTE con las claves que las
seis capas emiten: si alguien añade una bandera sin nombrarla aquí, CI falla en
vez de dejar que la clave cruda llegue a la pantalla."""


def flag_label(key: str) -> str:
    """Nombre legible de una bandera. Cae a la clave si no está catalogada —
    feo pero honesto: mejor la clave que un nombre inventado."""
    return FLAG_LABELS.get(key, key)


class FlagHelp(NamedTuple):
    """Qué es una bandera, por qué importa y dónde comprobarla.

    `NamedTuple` y no `@dataclass` por lo mismo que `ScoreHelp`: el gate de
    contrato enumera todo dataclass definido en `engine/`, así que uno aquí
    movería la huella del motor y exigiría subir `ENGINE_VERSION` por un cambio
    de metadatos.
    """

    what: str
    """Qué mira la regla, en una frase."""
    why: str
    """Por qué le importa a quien vive de los dividendos de esta empresa."""
    reading: str
    """Cuánto pesa y qué NO prueba. Una bandera encendida es una pregunta, no
    un veredicto: casi todas tienen explicaciones legítimas, y decirlo evita
    que se lean como acusaciones."""
    how_to_verify: str
    """Dónde mirar en las cuentas para confirmarla o descartarla. Es lo que
    convierte la bandera en una escuela de lectura forense en vez de en un
    oráculo."""


FLAG_HELP: dict[str, FlagHelp] = {
    # ── Cruces evolutivos (capa 1.5) ──────────────────────────────
    "C1_receivables_vs_revenue": FlagHelp(
        what=(
            "Compara cuánto crecen los saldos pendientes de cobro con cuánto crecen las "
            "ventas, y salta cuando los cobros van muy por delante durante dos "
            "ejercicios seguidos."
        ),
        why=(
            "Una venta que no se cobra no paga dividendos. Si el patrón se sostiene, el "
            "beneficio del año está financiando a los clientes en vez de llegar a caja."
        ),
        reading=(
            "Encendida no significa fraude: puede ser un cambio de política comercial, "
            "un cliente grande nuevo o estacionalidad. Lo que dice es que el crecimiento "
            "de este año todavía no es dinero."
        ),
        how_to_verify=(
            "Mira la evolución de deudores comerciales en el balance junto a las ventas, "
            "y el plazo medio de cobro de la pestaña Actividad. Si el plazo sube y la "
            "empresa no lo explica en sus notas, la pregunta sigue abierta."
        ),
    ),
    "C2_income_without_cash": FlagHelp(
        what=(
            "Salta cuando el resultado neto sube y el flujo de explotación no acompaña, "
            "durante dos ejercicios consecutivos."
        ),
        why=(
            "El dividendo se paga con caja, no con beneficio. Dos años de divergencia "
            "significan que lo que sostiene la cuenta de resultados no está entrando "
            "por el banco."
        ),
        reading=(
            "Es la señal más general de calidad del beneficio y la puerta de entrada a "
            "casi todos los casos de contabilidad forzada. Un año suelto no la enciende "
            "a propósito: la divergencia puntual es normal."
        ),
        how_to_verify=(
            "Compara el resultado neto con el flujo de explotación en el estado de "
            "flujos de los últimos ejercicios, y mira qué línea de ajustes explica la "
            "diferencia: circulante, deterioros o provisiones."
        ),
    ),
    "C3_inventory_vs_cogs": FlagHelp(
        what=(
            "Compara el crecimiento del inventario con el del coste de ventas y salta "
            "cuando la mercancía crece mucho más deprisa que lo que se vende."
        ),
        why=(
            "El inventario que no rota acaba en rebaja o en deterioro, y las dos cosas "
            "se comen el margen del ejercicio siguiente — el mismo del que saldría el "
            "dividendo."
        ),
        reading=(
            "En sectores sin inventario material la regla no se plantea y sale declarada "
            "como tal, no como hueco. Puede haber acumulación deliberada antes de un "
            "lanzamiento o por problemas de suministro."
        ),
        how_to_verify=(
            "Mira existencias en el balance frente al coste de ventas, y los días de "
            "inventario de la pestaña Actividad. Un salto conviene contrastarlo con lo "
            "que la empresa cuente sobre su cadena de suministro."
        ),
    ),
    "C4_underinvestment": FlagHelp(
        what=(
            "Salta cuando la inversión en activos se queda por debajo de la amortización "
            "durante tres ejercicios seguidos."
        ),
        why=(
            "Invertir menos de lo que se desgasta libera caja hoy y la resta mañana: es "
            "una forma de sostener un dividendo consumiendo la capacidad productiva."
        ),
        reading=(
            "Es informativa y no puntúa en el veredicto. Puede ser el final de un ciclo "
            "inversor, un negocio que se vuelve menos intensivo en activos, o "
            "exactamente lo que parece."
        ),
        how_to_verify=(
            "Compara el capex del estado de flujos con la amortización de la cuenta de "
            "resultados en la serie, y mira si el inmovilizado neto del balance está "
            "encogiendo año tras año."
        ),
    ),
    "C5_goodwill_without_acquisitions": FlagHelp(
        what=(
            "Salta cuando el fondo de comercio sube de un ejercicio al siguiente sin que "
            "el estado de flujos registre compras de empresas."
        ),
        why=(
            "El fondo de comercio no genera caja y su deterioro se lleva el beneficio de "
            "un año entero. Que aparezca sin una compra que lo justifique merece "
            "explicación."
        ),
        reading=(
            "La causa más frecuente y perfectamente legítima es el tipo de cambio: un "
            "fondo de comercio en otra divisa se revaloriza al consolidar. También puede "
            "ser una compra pagada con acciones."
        ),
        how_to_verify=(
            "Busca en las notas el movimiento del fondo de comercio del ejercicio: suele "
            "desglosar altas, deterioros y diferencias de conversión. Si el aumento no "
            "está en ninguna de las tres, pregunta."
        ),
    ),
    "C6_dilution": FlagHelp(
        what=(
            "Salta cuando el número de acciones crece de forma sostenida y la empresa no "
            "ha recomprado nada en esos ejercicios."
        ),
        why=(
            "Cada acción nueva reparte el mismo dividendo entre más manos. Un dividendo "
            "por acción estable con más acciones en circulación cuesta cada año más "
            "dinero."
        ),
        reading=(
            "Sube a atención cuando el crecimiento es fuerte. Puede venir de retribución "
            "en acciones a empleados, de compras pagadas con capital o de una ampliación "
            "para financiarse — y las tres se leen distinto."
        ),
        how_to_verify=(
            "Mira las acciones medias en circulación de la serie y contrástalo con el "
            "gasto por retribución en acciones y con las emisiones de capital del estado "
            "de flujos."
        ),
    ),
    "C7_shareholder_return_funded_by_debt": FlagHelp(
        what=(
            "Salta cuando lo devuelto al accionista —dividendo más recompras— supera a "
            "la caja libre del ejercicio y, a la vez, la deuda aumenta."
        ),
        why=(
            "Es la definición literal de un dividendo que no se gana: el dinero que sale "
            "hacia el accionista está entrando por el lado de los acreedores."
        ),
        reading=(
            "Grave cuando se sostiene dos ejercicios seguidos; en uno suelto puede ser un "
            "año inversor o un dividendo extraordinario ya anunciado. Es de las señales "
            "que más pesan sobre el perfil de seguridad."
        ),
        how_to_verify=(
            "En el estado de flujos, suma dividendos y recompras y compáralo con el flujo "
            "de explotación menos el capex; después mira si la variación de deuda del "
            "mismo ejercicio es positiva."
        ),
    ),
    "C8_acquired_growth": FlagHelp(
        what=(
            "Compara el dinero gastado en comprar empresas durante el periodo con el "
            "aumento de ventas conseguido, y salta cuando buena parte del crecimiento "
            "viene acompañado de compras."
        ),
        why=(
            "El crecimiento comprado no se repite solo: para mantener el ritmo hay que "
            "seguir comprando, y eso compite por la misma caja que paga el dividendo."
        ),
        reading=(
            "Informativa: no puntúa en el veredicto y no dice que las compras sean malas. "
            "Dice que el crecimiento que ves no es orgánico y no debe extrapolarse."
        ),
        how_to_verify=(
            "Suma las adquisiciones del estado de flujos en los ejercicios de la serie y "
            "compáralo con el aumento de ventas entre el primero y el último. Si la "
            "empresa publica crecimiento orgánico, contrasta ahí."
        ),
    ),
    "growth_externally_funded": FlagHelp(
        what=(
            "Compara el ritmo al que crecen las ventas con el que la empresa podría "
            "financiar sólo con los beneficios que retiene, y salta cuando el primero "
            "supera al segundo de forma sostenida."
        ),
        why=(
            "Crecer por encima de lo autofinanciable exige dinero de fuera, y ese dinero "
            "llega diluyendo al accionista o endeudando a la empresa. Las dos cosas "
            "erosionan el dividendo por acción."
        ),
        reading=(
            "Se lee junto a la dilución y al retorno financiado con deuda: son las tres "
            "caras del mismo hecho. Por sí sola no dice de dónde salió el dinero, sólo "
            "que no salió del negocio."
        ),
        how_to_verify=(
            "Mira las emisiones de capital y la variación de deuda del estado de flujos "
            "en los mismos ejercicios: ahí está la respuesta de quién puso el dinero."
        ),
    ),
    # ── Fiscalidad y soporte del dividendo (capa 3) ───────────────
    "Q4_tax_anomaly": FlagHelp(
        what=(
            "Salta cuando el tipo impositivo efectivo de un ejercicio cae muy por debajo "
            "de la mediana de la propia serie de la empresa."
        ),
        why=(
            "Un beneficio inflado por una ventaja fiscal puntual no se repite, y un "
            "dividendo dimensionado sobre él tampoco se sostiene."
        ),
        reading=(
            "Se juzga contra la propia historia de la empresa, no contra un tipo teórico: "
            "lo que informa es la caída, no el nivel. Créditos fiscales activados o la "
            "resolución de un litigio la encienden de forma legítima."
        ),
        how_to_verify=(
            "Busca la conciliación del gasto por impuesto en las notas: desglosa qué "
            "parte es corriente, qué parte diferida y qué partidas extraordinarias han "
            "movido el tipo ese año."
        ),
    ),
    "Q4_tax_persistently_low": FlagHelp(
        what=(
            "Salta cuando el tipo impositivo efectivo se mantiene muy bajo durante dos "
            "ejercicios consecutivos."
        ),
        why=(
            "Un tipo bajo sostenido suele apoyarse en estructuras que pueden cambiar con "
            "una reforma fiscal, y entonces el beneficio disponible para repartir cae de "
            "golpe."
        ),
        reading=(
            "Distinta de la anomalía puntual: aquí no hay sorpresa sino dependencia. En "
            "muchos casos es perfectamente legal y conocida, pero es un riesgo "
            "regulatorio que conviene tener presente."
        ),
        how_to_verify=(
            "Mira la conciliación fiscal de varios ejercicios seguidos y localiza la "
            "partida recurrente que rebaja el tipo; suele nombrar la jurisdicción o el "
            "régimen del que depende."
        ),
    ),
    "B1_debt_competes_with_dividend": FlagHelp(
        what=(
            "Cruza el apalancamiento sobre EBITDA con el peso del dividendo en la caja "
            "libre, y salta cuando los dos están tensos a la vez."
        ),
        why=(
            "Amortizar deuda y repartir dividendo compiten por el mismo dinero. Cuando "
            "ambos aprietan, algo cede, y lo que cede casi siempre es el dividendo."
        ),
        reading=(
            "Ninguna de las dos mitades por separado enciende la bandera: es la "
            "coincidencia lo que informa. No aplica a entidades financieras, donde la "
            "deuda es la materia prima del negocio."
        ),
        how_to_verify=(
            "Mira la deuda neta y el EBITDA del último ejercicio en la pestaña Solvencia, "
            "y el reparto sobre caja libre en Dividendo. Después busca el calendario de "
            "vencimientos en las notas."
        ),
    ),
    "B2_interest_priority": FlagHelp(
        what=(
            "Cruza la cobertura de intereses con el peso del dividendo sobre el "
            "beneficio, y salta cuando la cobertura es débil y el reparto es alto."
        ),
        why=(
            "Los intereses se cobran antes que tú y no son negociables. Con poca "
            "holgura, un mal año se lleva por delante el dividendo mucho antes que el "
            "pago a los acreedores."
        ),
        reading=(
            "Mide prelación, no solvencia: la empresa puede estar perfectamente sana y "
            "aun así dejarte en la cola. No aplica a entidades financieras, donde el "
            "interés no es una carga sino el negocio."
        ),
        how_to_verify=(
            "Compara el resultado de explotación con el gasto financiero de la cuenta de "
            "resultados, y mira si la deuda es a tipo fijo o variable en las notas: con "
            "tipo variable la holgura se estrecha sola."
        ),
    ),
    "B4_dividend_funded_externally": FlagHelp(
        what=(
            "Salta cuando el dividendo pagado supera a la caja libre del ejercicio y, a "
            "la vez, entra dinero por deuda nueva o por emisión de acciones."
        ),
        why=(
            "Es la señal individual que mejor anticipa un recorte de dividendo: la "
            "empresa está pagando con dinero prestado algo que debería salir del "
            "negocio."
        ),
        reading=(
            "Es una de las condiciones que por sí sola descarta el perfil más "
            "conservador. Si no se puede comprobar, tampoco se concede ese perfil: el "
            "verde se gana, no se hereda de un dato que falta."
        ),
        how_to_verify=(
            "En el estado de flujos, compara los dividendos pagados con el flujo de "
            "explotación menos el capex, y mira en la sección de financiación si ese "
            "mismo año entró deuda o capital."
        ),
    ),
    # ── Reglas cruzadas sectoriales (PHASE-44.21) ─────────────────
    "RC1_negative_working_capital": FlagHelp(
        what=(
            "Reconoce el modelo de negocio que cobra a sus clientes antes de pagar a sus "
            "proveedores, y que por eso funciona con circulante negativo."
        ),
        why=(
            "Sin esta lectura, un negocio sano de este tipo sale en rojo permanente de "
            "liquidez — y un rojo que siempre está encendido se aprende a ignorar, "
            "incluido el que sí importa."
        ),
        reading=(
            "No es una alarma: es contexto que explica por qué los ratios de liquidez de "
            "esta empresa se leen distinto. Los proveedores financian la operación, y eso "
            "es una ventaja mientras las ventas no caigan."
        ),
        how_to_verify=(
            "Compara el plazo de cobro a clientes con el de pago a proveedores en la "
            "pestaña Actividad: si el segundo es bastante mayor, el modelo está "
            "confirmado."
        ),
    ),
    "RC2_utility_payout_needs_funding_check": FlagHelp(
        what=(
            "En una empresa regulada, señala que el reparto alto sobre la caja libre es "
            "su modelo normal y que la pregunta que decide es otra: quién financia el "
            "exceso."
        ),
        why=(
            "En estos negocios el reparto alto convive con inversión constante, así que "
            "el nivel por sí solo no distingue una eléctrica sana de una que se está "
            "endeudando para pagarte."
        ),
        reading=(
            "Es una redirección, no una alarma: manda mirar el retorno financiado con "
            "deuda y el dividendo financiado desde fuera, que son las dos que no se "
            "relajan por sector."
        ),
        how_to_verify=(
            "Mira la variación de deuda y las emisiones de capital del estado de flujos "
            "en los ejercicios de reparto alto. Si la deuda crece al ritmo del "
            "dividendo, ya tienes la respuesta."
        ),
    ),
    # ── Calidad del dato (capa 1 y forense) ───────────────────────
    "ebt_divergence": FlagHelp(
        what=(
            "Comprueba que el resultado antes de impuestos publicado cuadra con el "
            "resultado neto más los impuestos, y avisa cuando no cuadra."
        ),
        why=(
            "Si el cuadre falla, por debajo hay partidas que el modelo del informe no "
            "recoge, y todo lo que se calcule con esas cifras arrastra el hueco."
        ),
        reading=(
            "Habla de la CALIDAD DEL DATO ingerido, no de la salud de la empresa. Suele "
            "venir de intereses minoritarios, de resultados de actividades "
            "interrumpidas o de participadas."
        ),
        how_to_verify=(
            "Abre la cuenta de resultados del ejercicio en la pestaña Estados y recorre "
            "las líneas entre el resultado antes de impuestos y el neto: la que falte es "
            "la que el modelo no está viendo."
        ),
    ),
    "ebt_reconstruction_divergence": FlagHelp(
        what=(
            "Cuando el resultado antes de impuestos hay que reconstruirlo, comprueba que "
            "el valor reconstruido cuadra con el resultado de explotación menos los "
            "intereses, y avisa si se separan."
        ),
        why=(
            "Un dato deducido que además no cuadra con su comprobación es el punto donde "
            "conviene desconfiar del resto de la cadena que lo usa."
        ),
        reading=(
            "Igual que la anterior: es calidad del dato. La diferencia suele ser "
            "resultado financiero distinto de intereses, o resultados por venta de "
            "activos."
        ),
        how_to_verify=(
            "Busca en la cuenta de resultados las partidas financieras que no son gasto "
            "por intereses, y comprueba si su importe explica la diferencia que la "
            "bandera reporta."
        ),
    ),
    "fcf_divergence": FlagHelp(
        what=(
            "Calcula la caja libre por dos caminos —desde el flujo de explotación y "
            "reconstruida desde el resultado de explotación— y avisa cuando ambos se "
            "separan de forma sostenida."
        ),
        why=(
            "La caja libre es lo que paga el dividendo. Si dos formas razonables de "
            "medirla no coinciden durante varios ejercicios, una de las dos está "
            "contando otra cosa."
        ),
        reading=(
            "Es la señal más útil del bloque de calidad de la caja. La causa habitual "
            "son grandes movimientos de circulante o partidas no monetarias que "
            "distorsionan uno de los dos caminos."
        ),
        how_to_verify=(
            "En el estado de flujos, mira la línea de variación de circulante y los "
            "ajustes por partidas no monetarias: suelen explicar la mayor parte de la "
            "diferencia."
        ),
    ),
    "z_score_uncalibrated_for_reit": FlagHelp(
        what=(
            "Avisa de que el modelo de insolvencia se está aplicando a una sociedad "
            "inmobiliaria cotizada, para la que no fue calibrado."
        ),
        why=(
            "Estas sociedades trabajan con un apalancamiento alto por diseño, así que el "
            "modelo las castiga por hacer exactamente aquello para lo que existen."
        ),
        reading=(
            "El número se enseña como orientación, no como veredicto. Para juzgar su "
            "solidez pesan más la cobertura de intereses, el vencimiento de la deuda y "
            "el valor de los activos."
        ),
        how_to_verify=(
            "Mira el calendario de vencimientos y el porcentaje de deuda a tipo fijo en "
            "las notas, y la valoración de los inmuebles: ahí está el riesgo real de "
            "este tipo de sociedad."
        ),
    ),
}
"""Ficha de cada bandera del catálogo.

Un test de contrato exige que las claves sean EXACTAMENTE las de `FLAG_LABELS`:
una bandera nombrada pero sin explicar deja al usuario con un titular y sin
saber qué hacer con él, que es medio camino."""


def flag_help(key: str) -> FlagHelp | None:
    """La ficha de una bandera, o `None` si no está catalogada."""
    return FLAG_HELP.get(key)
