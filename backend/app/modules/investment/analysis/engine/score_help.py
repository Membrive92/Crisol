"""Qué es cada score forense y cada una de sus variables (PHASE-44.24.A).

Hermano de `glossary.py`, para lo que aquel no cubre: los **componentes** de los
cuatro scores que publican desglose. El catálogo de métricas explica qué es el
M-Score; esto explica qué es `DSRI`, que es lo que el usuario lee de verdad
cuando despliega la tarjeta.

**El defecto que cierra.** `score-breakdown-card.tsx` imprimía la clave cruda:
en pantalla salía `DSRI`, `TATA`, `P4_cfo_supera_beneficio`. Es exactamente lo
que pasaba con las señales del veredicto antes de PHASE-44.9
(`B4_dividend_funded_externally` a la cara del usuario) y se arregla igual: la
etiqueta sale de un catálogo del engine, no de un diccionario escrito en la
pantalla.

**Por qué `NamedTuple` y no `@dataclass`.** El gate de contrato
(`test_investment_engine_contract._engine_shape`) enumera TODO dataclass definido
en cualquier módulo de `engine/`, así que un `@dataclass` aquí movería la huella
del motor y exigiría subir `ENGINE_VERSION` por un cambio de metadatos — que no
es un cambio de fórmula. `NamedTuple` no es dataclass y queda fuera. Por el mismo
motivo este módulo no declara ningún alias `Literal`.

**Y por qué las claves son claves del diccionario.** `_emitted_flag_keys()`
escanea `engine/*.py` buscando `key="..."`: escribir `ScoreComponentHelp(key=...)`
haría que las 27 variables se contaran como banderas emitidas sin nombre y CI
fallaría con un mensaje que no se parece en nada a la causa.

**Qué NO va en estos textos**: números de corte. Las bandas se calibran por
sector desde PHASE-44.21 y viajan en el propio run; un umbral en prosa caduca en
silencio y acaba contradiciendo al semáforo que tiene al lado.

Este módulo es **hoja**: no importa nada del engine, así que puede consumirlo
cualquier capa sin crear un ciclo.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple


class ScoreComponentHelp(NamedTuple):
    """Una variable de un score, con el nombre que se pinta y qué significa."""

    label: str
    """Nombre legible. Conserva la sigla del modelo entre paréntesis porque es
    como aparece en la literatura y en el cuaderno del usuario: quien quiera
    contrastarlo fuera necesita la sigla, y quien no, la frase."""
    what: str
    """Qué compara esa variable, en una frase, con la dirección de lectura."""


class ScoreHelp(NamedTuple):
    """La ficha de un score: qué mide, por qué importa y cómo se lee."""

    what: str
    why: str
    reading: str
    components: Mapping[str, ScoreComponentHelp] = {}
    """Las variables que el motor publica en `ScoreBreakdown`. Vacío en los
    cuatro scores que no tienen desglose por diseño (`accruals`, `F5`, `F6`,
    `FZ`): son un ratio único, no un agregado."""


_M_SCORE_COMPONENTS: Mapping[str, ScoreComponentHelp] = {
    "DSRI": ScoreComponentHelp(
        "Índice de cobros (DSRI)",
        "Compara lo pendiente de cobrar por cada euro vendido con lo del ejercicio "
        "anterior. Por encima de la unidad significa que se está cobrando más "
        "despacio, o que hay ventas apuntadas que todavía no ha pagado nadie.",
    ),
    "GMI": ScoreComponentHelp(
        "Índice de margen bruto (GMI)",
        "El margen bruto del ejercicio ANTERIOR dividido por el de éste, así que "
        "sube cuando el margen se deteriora. Un margen que cae presiona a la "
        "dirección, y la presión es lo que precede a la contabilidad creativa.",
    ),
    "AQI": ScoreComponentHelp(
        "Índice de calidad del activo (AQI)",
        "Qué parte del activo no es ni circulante ni inmovilizado material, "
        "comparada con la del año anterior. Ese resto es donde se acumula lo que "
        "se ha capitalizado en vez de llevarlo a gasto.",
    ),
    "SGI": ScoreComponentHelp(
        "Índice de crecimiento de ventas (SGI)",
        "Ventas de este ejercicio sobre las del anterior. No es malo por sí "
        "mismo: entra en el modelo porque una empresa que crece deprisa tiene más "
        "incentivo y más margen para estirar sus cifras.",
    ),
    "DEPI": ScoreComponentHelp(
        "Índice de amortización (DEPI)",
        "La tasa a la que se amortizaba el año pasado dividida por la de éste, así "
        "que sube cuando la empresa amortiza más despacio — una forma silenciosa "
        "de subir el beneficio sin vender más.",
    ),
    "SGAI": ScoreComponentHelp(
        "Índice de gastos de estructura (SGAI)",
        "Gastos comerciales y de administración por euro vendido, este ejercicio "
        "contra el anterior. Que suban desproporcionadamente indica pérdida de "
        "eficiencia; en el modelo resta, porque el manipulador típico los contiene.",
    ),
    "LVGI": ScoreComponentHelp(
        "Índice de apalancamiento (LVGI)",
        "Pasivo corriente más deuda a largo sobre activo total, este ejercicio "
        "contra el anterior. Más deuda aprieta los covenants, y un covenant "
        "apretado es un motivo concreto para maquillar.",
    ),
    "TATA": ScoreComponentHelp(
        "Devengo total sobre activo (TATA)",
        "Resultado neto menos flujo de explotación, dividido entre el activo "
        "total: el beneficio que no ha llegado en forma de dinero. Es la variable "
        "que más pesa del modelo, y la que hay que mirar primero.",
    ),
}

_Z_SCORE_COMPONENTS: Mapping[str, ScoreComponentHelp] = {
    "X1": ScoreComponentHelp(
        "Fondo de maniobra sobre activo (X1)",
        "Activo corriente menos pasivo corriente, sobre el activo total: el "
        "colchón de circulante con el que la empresa aguanta un mal trimestre.",
    ),
    "X2": ScoreComponentHelp(
        "Reservas acumuladas sobre activo (X2)",
        "Beneficios retenidos a lo largo de toda la vida de la empresa sobre el "
        "activo total. Mide autofinanciación y madurez: una empresa joven o que "
        "ha repartido todo puntúa bajo aunque hoy vaya bien.",
    ),
    "X3": ScoreComponentHelp(
        "Rentabilidad operativa del activo (X3)",
        "Resultado de explotación sobre activo total. Usa el EBIT REPORTADO y no "
        "el limpio de deterioros que emplean otras métricas del informe: el "
        "modelo se calibró sobre el contable y cambiarlo movería la escala.",
    ),
    "X4": ScoreComponentHelp(
        "Patrimonio sobre pasivo (X4)",
        "Cuánto patrimonio neto hay por cada euro de pasivo — el colchón contable "
        "antes de que las pérdidas se coman a los acreedores. En la variante de "
        "1995 va con valor CONTABLE, no bursátil, y por eso el análisis no "
        "depende de la cotización.",
    ),
}

_F_SCORE_COMPONENTS: Mapping[str, ScoreComponentHelp] = {
    "P1_roa_positivo": ScoreComponentHelp(
        "Gana dinero",
        "El resultado neto del ejercicio es positivo. El más básico de los nueve, "
        "y el que más empresas suspenden en el peor momento del ciclo.",
    ),
    "P2_cfo_positivo": ScoreComponentHelp(
        "Genera caja de explotación",
        "El flujo de explotación es positivo: el negocio ingresa más dinero del "
        "que gasta en hacerlo funcionar, con independencia del beneficio contable.",
    ),
    "P3_roa_mejora": ScoreComponentHelp(
        "Mejora su rentabilidad",
        "La rentabilidad sobre el activo es mayor que la del ejercicio anterior. "
        "Mide dirección, no nivel: una empresa mediocre que mejora lo pasa.",
    ),
    "P4_cfo_supera_beneficio": ScoreComponentHelp(
        "La caja supera al beneficio",
        "El flujo de explotación es mayor que el resultado neto. Es el test de "
        "calidad del beneficio: si se suspende, el beneficio va por delante del "
        "dinero y hay que mirar por qué.",
    ),
    "P5_menos_apalancamiento": ScoreComponentHelp(
        "Reduce deuda a largo",
        "La deuda a largo plazo pesa menos sobre el activo que el año pasado. "
        "Menos deuda es menos competencia por la misma caja que paga el dividendo.",
    ),
    "P6_mejor_liquidez": ScoreComponentHelp(
        "Mejora su liquidez",
        "El ratio corriente —lo que puede convertir en dinero a un año frente a "
        "lo que debe pagar en ese plazo— es mejor que el del ejercicio anterior.",
    ),
    "P7_sin_emision": ScoreComponentHelp(
        "No ha emitido acciones",
        "No ha habido emisión de capital en el ejercicio. Emitir para financiarse "
        "diluye al accionista que ya estaba, y suele ser señal de que la caja "
        "propia no llegaba.",
    ),
    "P8_mejor_margen_bruto": ScoreComponentHelp(
        "Mejora el margen bruto",
        "El margen bruto es mayor que el del año anterior: señal de poder de "
        "precios o de mejora de costes, según qué lado se haya movido.",
    ),
    "P9_mejor_rotacion": ScoreComponentHelp(
        "Mejora la rotación del activo",
        "Vende más por cada euro de activo que el año pasado — está exprimiendo "
        "mejor lo que ya tiene, sin necesidad de invertir más.",
    ),
}

_C_SCORE_COMPONENTS: Mapping[str, ScoreComponentHelp] = {
    "C1_beneficio_por_delante_de_caja": ScoreComponentHelp(
        "El beneficio va por delante de la caja",
        "El resultado neto supera al flujo de explotación. Encendido no prueba "
        "nada por sí solo —hay motivos legítimos— pero es el punto de partida de "
        "casi todos los casos de cocina contable.",
    ),
    "C2_dias_de_cobro_suben": ScoreComponentHelp(
        "Suben los días de cobro",
        "Se tarda más en cobrar a los clientes que el ejercicio anterior. Puede "
        "ser una política comercial nueva o ventas que nadie va a pagar.",
    ),
    "C3_dias_de_inventario_suben": ScoreComponentHelp(
        "Suben los días de inventario",
        "La mercancía pasa más tiempo en el almacén. En un sector sin inventario "
        "material esta comprobación no se plantea y sale del cómputo, con su "
        "motivo, en vez de bloquear el score entero.",
    ),
    "C4_otros_activos_corrientes_suben": ScoreComponentHelp(
        "Sube el cajón de «otros activos corrientes»",
        "Crece la parte del circulante que no es caja, ni cobros, ni inventario, "
        "medida sobre ventas. Es el sitio donde acaba lo que no encaja en ninguna "
        "otra línea, y por eso conviene mirarlo cuando crece.",
    ),
    "C5_amortiza_mas_despacio": ScoreComponentHelp(
        "Amortiza más despacio",
        "La tasa de amortización ha bajado respecto al año anterior. Alargar la "
        "vida útil de los activos sube el beneficio sin que cambie el negocio.",
    ),
    "C6_activo_crece_mas_del_10": ScoreComponentHelp(
        "El activo crece deprisa",
        "El activo total crece por encima del listón que fija el modelo. El "
        "crecimiento rápido, sobre todo por compras, es donde más fácil resulta "
        "esconder un ajuste.",
    ),
}


SCORE_HELP: Mapping[str, ScoreHelp] = {
    "m_score": ScoreHelp(
        what=(
            "Combina ocho comparaciones entre el ejercicio y el anterior —cobros, "
            "margen, calidad del activo, ventas, amortización, gastos de "
            "estructura, apalancamiento y devengo— en un único indicador de si las "
            "cuentas parecen manipuladas."
        ),
        why=(
            "Es la primera pregunta antes que cualquier otra: si las cifras no son "
            "de fiar, el dividendo que aparenten sostener tampoco lo es."
        ),
        reading=(
            "Menos es mejor. Lo informativo no es el agregado sino QUÉ variable lo "
            "dispara, así que las ocho se publican al lado. No aplica a entidades "
            "financieras: el modelo se calibró sobre empresas industriales."
        ),
        components=_M_SCORE_COMPONENTS,
    ),
    "z_score": ScoreHelp(
        what=(
            "Pondera cuatro proporciones del balance —colchón de circulante, "
            "reservas acumuladas, rentabilidad operativa y patrimonio frente a "
            "pasivo— en un indicador de distancia a la insolvencia."
        ),
        why=(
            "Una empresa que se acerca a la insolvencia recorta el dividendo antes "
            "de dejar de pagar a sus acreedores: es el aviso que llega primero."
        ),
        reading=(
            "Más es mejor. Es la variante de balance de 1995, que no usa "
            "capitalización bursátil, y por eso el mismo análisis reejecutado "
            "mañana da el mismo número. No aplica a entidades financieras."
        ),
        components=_Z_SCORE_COMPONENTS,
    ),
    "f_score": ScoreHelp(
        what=(
            "Cuenta cuántos de nueve tests binarios de fortaleza financiera supera "
            "la empresa: rentabilidad, generación de caja, deuda, liquidez, "
            "dilución, márgenes y rotación."
        ),
        why=(
            "Mide la salud del negocio por acumulación de pruebas pequeñas en vez "
            "de por un ratio único, así que un dato raro no lo mueve entero."
        ),
        reading=(
            "Más tests superados es mejor. Si falta cualquiera de los nueve el "
            "score sale sin calcular en vez de sobre un total distinto: siete de "
            "siete y siete de nueve no significan lo mismo y comparten banda."
        ),
        components=_F_SCORE_COMPONENTS,
    ),
    "accruals": ScoreHelp(
        what=(
            "La diferencia entre el resultado neto y el flujo de explotación, "
            "dividida entre el activo total medio del ejercicio: qué parte del "
            "beneficio no ha llegado en forma de dinero."
        ),
        why=(
            "Un beneficio que no se convierte en caja no puede pagar un dividendo "
            "de forma sostenida, por muy bien que se lea en la cuenta de "
            "resultados."
        ),
        reading=(
            "Se bandea sobre el VALOR ABSOLUTO, así que menos es mejor en los dos "
            "sentidos: que la caja vaya muy por delante del beneficio también es "
            "una anomalía que conviene explicarse. El signo original queda en el "
            "desglose."
        ),
    ),
    "F5": ScoreHelp(
        what=(
            "Cuánto pesa el fondo de comercio sobre el activo total, es decir qué "
            "parte de lo que la empresa dice tener es el sobreprecio pagado en "
            "compras pasadas."
        ),
        why=(
            "El fondo de comercio no genera caja y se puede deteriorar de golpe: "
            "un saneamiento grande se lleva por delante el beneficio del año y, "
            "con él, la coartada del dividendo."
        ),
        reading=(
            "Menos es mejor, pero depende mucho del modelo de negocio: un "
            "comprador serial sano puede vivir permanentemente en ámbar, y ahí lo "
            "que informa es la deriva y no el nivel."
        ),
    ),
    "F6": ScoreHelp(
        what=(
            "Compara cuánto se ha movido el circulante operativo con cuánto se han "
            "movido las ventas, en tanto por uno. Es la descomposición visible del "
            "devengo: dice en qué ejercicio mirar."
        ),
        why=(
            "Cuando el circulante crece mucho más deprisa que el negocio, el "
            "beneficio se está acumulando en cobros o en almacén en vez de en el "
            "banco."
        ),
        reading=(
            "Menos es mejor. Necesita dos ejercicios comparables con ventas y "
            "circulante en ambos; sin ellos sale sin calcular y dice cuál falta."
        ),
    ),
    "FZ": ScoreHelp(
        what=(
            "Un segundo modelo de riesgo de quiebra, independiente del anterior, "
            "construido sobre rentabilidad, apalancamiento y liquidez del balance."
        ),
        why=(
            "Vale como contraste: cuando los dos modelos de insolvencia coinciden, "
            "la señal es fuerte; cuando discrepan, la discrepancia es el hallazgo."
        ),
        reading=(
            "Menos es mejor, y la escala es NEGATIVA: un valor positivo ya está en "
            "zona mala. Junto al valor va la misma comprobación traducida a "
            "probabilidad, que es la lectura que no hay que interpretar. No aplica "
            "a entidades financieras."
        ),
    ),
    "FZ_P": ScoreHelp(
        what=(
            "El X-Score traducido a la probabilidad de insolvencia que el modelo le "
            "asigna. Mismo cálculo y mismos cortes, en la escala en la que la cifra "
            "se entiende sin compararla con nada."
        ),
        why=(
            "Una puntuación en escala negativa no dice por sí sola si es alta o "
            "baja, y esta comprobación es de las que deciden el sello: leerla en "
            "probabilidad es lo que permite discutirla."
        ),
        reading=(
            "Menos es mejor. Es el X-Score visto de otra forma, así que su color "
            "coincide con el suyo por construcción. Ojo: una empresa con patrimonio "
            "neto negativo por recompras dispara este modelo sin tener tensión de "
            "caja."
        ),
    ),
    "F7": ScoreHelp(
        what=(
            "Cuenta cuántas de seis señales binarias de «cocina» contable están "
            "encendidas: beneficio por delante de la caja, cobros, inventario, "
            "otros activos corrientes, ritmo de amortización y crecimiento del "
            "activo."
        ),
        why=(
            "Es el contraste por conteo del modelo de manipulación: cuando ambos "
            "apuntan, la evidencia es fuerte; cuando divergen, el desglose dice "
            "por qué."
        ),
        reading=(
            "Menos señales encendidas es mejor. Las comprobaciones que no se "
            "plantean en el sector salen del cómputo con su motivo en vez de "
            "bloquear el score, y si quedan demasiado pocas aplicables no se "
            "publica número: un conteo sobre un total distinto no comparte banda."
        ),
        components=_C_SCORE_COMPONENTS,
    ),
}
"""Ficha por score forense, con sus componentes cuando los publica.

Un test de contrato exige que las claves sean EXACTAMENTE las ocho de
`forensic.METRIC_KEYS`, y que los componentes de cada score coincidan con los que
el motor emite de verdad — comprobado con un escaneo estático de las cuatro
funciones que los construyen, no ejecutando el engine: ejecutarlo sólo destaparía
lo que la fixture del test da la casualidad de ejercitar."""


def score_help(key: str) -> ScoreHelp | None:
    """La ficha de un score, o `None` si no está catalogado."""
    return SCORE_HELP.get(key)


def component_label(score_key: str, component_key: str) -> str:
    """Nombre legible de una variable de un score.

    Cae a la clave cruda si no está catalogada — feo, pero honesto: antes que
    inventar un nombre, se enseña el que el motor usa. El gate de contrato hace
    que ese camino no pueda ocurrir con un componente real.
    """
    help_entry = SCORE_HELP.get(score_key)
    if help_entry is None:
        return component_key
    component = help_entry.components.get(component_key)
    return component.label if component is not None else component_key
