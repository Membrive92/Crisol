"""Qué es cada métrica: qué mide, por qué importa y cómo se lee (PHASE-44.24.A).

El informe pinta 64 métricas con su valor, su unidad y su banda. Hasta PHASE-44.23
la única pista de qué eran era la etiqueta; desde entonces hay una definición por
fila. Lo que faltaba —y añade esta fase— es **por qué le importa a quien vive de
los dividendos de esa empresa**, y separar la lectura para poder pintarla aparte
en vez de enterrada al final del párrafo.

Tres campos y no uno:

- `what` — qué mide y cómo se calcula. Es lo que la «i» enseña primero y lo que
  `MetricDefinition.help` devuelve, así que las pantallas que sólo leen `help`
  siguen funcionando.
- `why` — por qué importa, con el sesgo de la tesis del usuario: seguridad del
  reparto, caja disponible, riesgo de recorte. Un gate mide que no sea una
  paráfrasis del anterior, porque al redactar sesenta porqués seguidos la salida
  natural es reescribir el qué.
- `reading` — hacia dónde se lee y con qué matices (si usa medias de dos
  ejercicios, si no aplica a financieras, si el primer año sale degradado).

**Por qué vive en el engine y no en la interfaz.** La lección de PHASE-44.9: tres
rótulos escritos a mano en la pantalla acabaron mintiendo sobre su propio número
(F5, F6 y D8). Una definición miente igual de fácil y es más difícil de detectar,
porque nadie la contrasta con la fórmula. Aquí está al lado del código que
calcula, y el contrato exige que las claves sean EXACTAMENTE las del catálogo.

**Por qué `NamedTuple` y no `@dataclass`.** El gate de la huella enumera todo
dataclass definido en cualquier módulo de `engine/`: uno aquí movería la huella
del motor y exigiría subir `ENGINE_VERSION` por un cambio de metadatos, que no
es un cambio de fórmula. Comprobado empíricamente antes de elegir la forma.

**Qué NO va en estos textos.** Números de corte. Las bandas se calibran por
sector desde PHASE-44.21 y viajan en el propio run; un umbral escrito en prosa
caduca en silencio y contradice al semáforo que tiene al lado.
"""

from __future__ import annotations

from typing import NamedTuple


class MetricHelp(NamedTuple):
    """La ficha de una métrica, en sus tres preguntas."""

    what: str
    why: str
    reading: str


METRIC_HELP: dict[str, MetricHelp] = {
    # ── liquidez ──────────────────────────────────────────────────────
    "L1": MetricHelp(
        what=(
            "Activo corriente entre pasivo corriente, con saldos de cierre: si lo que la "
            "empresa puede convertir en dinero en menos de un año cubre lo que tiene que "
            "pagar en ese mismo plazo."
        ),
        why=(
            "El dividendo se paga con dinero, no con beneficio. Una compañía apretada por "
            "los vencimientos próximos acaba eligiendo entre pagar a proveedores y "
            "repartir, y el reparto es lo que se recorta."
        ),
        reading=(
            "Más alto, más holgura. Sin balance clasificado —bancos, algunas socimis— no "
            "hay número, y en banca se apaga la vara. Con ciclo de caja negativo, cobrar "
            "antes de pagar, pierde el rojo con su motivo."
        ),
    ),
    "L2": MetricHelp(
        what=(
            "El ratio corriente descontando las existencias, lo más difícil de convertir "
            "en dinero deprisa: activo corriente menos existencias, entre pasivo "
            "corriente y con saldos de cierre. Un filing que no las publica las lee como "
            "cero, así que ahí coincide con el ratio corriente."
        ),
        why=(
            "Si la holgura a corto plazo se sostiene sobre un almacén lleno, atender los "
            "pagos obliga a vender con descuento, y ese margen sacrificado es el mismo "
            "del que sale el reparto del año siguiente."
        ),
        reading=(
            "Más alto, más capacidad de pagar el corto plazo sin vaciar el almacén. Su "
            "vara se deriva de la del ratio corriente y se apaga en banca; con circulante "
            "negativo pierde el rojo, igual que él."
        ),
    ),
    "L3": MetricHelp(
        what=(
            "Sólo el dinero ya disponible frente a lo que vence a corto: efectivo y "
            "equivalentes más activos financieros corrientes, entre pasivo corriente. "
            "Deja fuera las existencias y lo pendiente de cobrar."
        ),
        why=(
            "Es la versión del corto plazo que no depende de que nadie pague a tiempo. "
            "Cuando el cobro se retrasa, la caja que quedaba comprometida para el "
            "trimestre es exactamente la que financia el próximo pago al accionista."
        ),
        reading=(
            "Más alto, más colchón inmediato. Al dejar fuera el cobro pendiente, quien "
            "cobra deprisa sale bajo sin tener problema. En banca se le apaga la vara, y "
            "el alivio por circulante negativo no la alcanza."
        ),
    ),
    "L4": MetricHelp(
        what=(
            "Lo que vence en doce meses contra los medios de afrontarlo sin refinanciar: "
            "efectivo, activos financieros corrientes y la caja libre del año —flujo de "
            "explotación menos capex— entre deuda a corto más la parte corriente de la "
            "deuda a largo."
        ),
        why=(
            "Las empresas no quiebran por un ratio malo, quiebran por no poder renovar un "
            "vencimiento. Y mucho antes de llegar ahí, el consejo suspende el reparto "
            "para guardar la caja: ésta es la métrica que anticipa ese recorte."
        ),
        reading=(
            "Más alto mejor. Un cero publicado —no debe nada a corto— es el mejor "
            "resultado y sale verde, salvo en banca, donde la vara se apaga; si el filing "
            "calla uno de los dos conceptos, sale sin banda."
        ),
    ),
    # ── actividad ─────────────────────────────────────────────────────
    "A1": MetricHelp(
        what=(
            "Cuánto tarda de media en cobrar a sus clientes: deudores comerciales entre "
            "ventas, por 365 días. El saldo de deudores entra como media de dos "
            "ejercicios (t y t−1), no como el saldo de cierre."
        ),
        why=(
            "Una venta apuntada no es dinero hasta que llega: mientras el cliente no "
            "paga, el reparto se sostiene con caja de otro sitio o con banco, y un "
            "alargamiento sostenido es una fuga silenciosa."
        ),
        reading=(
            "Menos días, antes entra el dinero; sin banda absoluta, informa su deriva. "
            "Sin ejercicio anterior en la serie se usa el saldo de cierre y sale marcado "
            "como aproximación. En un banco no aplica."
        ),
    ),
    "A2": MetricHelp(
        what=(
            "Cuántos días de media pasa la mercancía en almacén: existencias entre COSTE "
            "DE VENTAS —no ventas—, por 365, con las existencias en media de dos "
            "ejercicios (t y t−1)."
        ),
        why=(
            "Cada día de almacén es caja inmovilizada en producto aún sin vender: dinero "
            "que no está disponible para repartir y que, si la mercancía se queda, acaba "
            "saliendo por el desagüe del deterioro."
        ),
        reading=(
            "Menos días, menos dinero parado; sin banda absoluta, se lee por su deriva. "
            "Sin coste de ventas desglosado —habitual en servicios— no se calcula, y en "
            "un banco o sin inventario el motor la apaga."
        ),
    ),
    "A3": MetricHelp(
        what=(
            "Cuántos días de media tarda en pagar a sus proveedores: acreedores "
            "comerciales entre coste de ventas, por 365, con el saldo en media de dos "
            "ejercicios. Mismo denominador que los días de inventario y distinto "
            "numerador."
        ),
        why=(
            "Retrasar al proveedor es financiación gratis que sostiene el reparto sin "
            "pedir banco; pero un estirón repentino suele ser tensión de tesorería "
            "disfrazada de mejora, y ese dinero no es suyo."
        ),
        reading=(
            "Más días, más tiempo financiándose con el proveedor, y no siempre es mejor. "
            "Sin banda absoluta: se lee por su deriva y dentro del ciclo. Sin ejercicio "
            "anterior sale aproximado; en banca no aplica."
        ),
    ),
    "A4": MetricHelp(
        what=(
            "Cuántos euros de ventas obtiene por cada euro de activo: ventas entre activo "
            "total MEDIO de dos ejercicios. Habla de intensidad de uso del activo, no de "
            "rentabilidad; es además el factor de rotación de las dos identidades DuPont."
        ),
        why=(
            "Un negocio que exprime poco lo que tiene necesita invertir más para crecer, "
            "y esa inversión sale de la misma caja que paga el dividendo: si cae de forma "
            "sostenida, el reparto compite con el capex."
        ),
        reading=(
            "Más alto, más ventas por activo empleado, pero el nivel normal depende del "
            "negocio: sin banda absoluta, se lee por su evolución. Sin ejercicio anterior "
            "sale aproximado; en un banco no aplica."
        ),
    ),
    "A5": MetricHelp(
        what=(
            "Los días que el dinero pasa fuera de caja entre pagar al proveedor y cobrar "
            "al cliente: días de cobro más días de inventario menos días de pago (A1 + A2 "
            "− A3), con los tres componentes recalculados."
        ),
        why=(
            "Es el circulante que hay que financiar todos los días antes de repartir "
            "nada: cuando se alarga, la caja del ejercicio se queda en almacén y en "
            "clientes aunque el beneficio no se mueva."
        ),
        reading=(
            "Sin banda propia; en banca no aplica. Negativo: cobra antes de pagar, y el "
            "motor retira el rojo —sólo el rojo— del ratio corriente y la prueba ácida. "
            "Un componente aproximado marca el ciclo entero."
        ),
    ),
    # ── solvencia y deuda ─────────────────────────────────────────────
    "S1": MetricHelp(
        what=(
            "Qué parte del activo está financiada con dinero ajeno: pasivo total entre "
            "activo total, ambos a cierre del ejercicio. No es el «apalancamiento "
            "financiero» del análisis DuPont (activo entre patrimonio), que en este "
            "informe es DUPONT_EM."
        ),
        why=(
            "El acreedor cobra antes que el accionista. Cuanto más del balance pertenezca "
            "al banco y al bonista, menos margen queda para sostener el reparto el año "
            "que el negocio afloje."
        ),
        reading=(
            "Cuanto más bajo, menos dependencia de terceros. Si el pasivo total no venía "
            "en el filing, se deriva restando patrimonio al activo y deja de probar algo "
            "distinto de S3. En financieras, sin semáforo."
        ),
    ),
    "S2": MetricHelp(
        what=(
            "Cuántas veces el beneficio operativo cubre la factura de intereses: EBIT "
            "limpio entre gasto financiero. El limpio suma los deterioros y resta las "
            "plusvalías por venta de negocios, para que un suceso de una vez no "
            "distorsione el año."
        ),
        why=(
            "El cupón se paga antes que el reparto y no se negocia. Un colchón estrecho "
            "aquí es el aviso más temprano de que el dividendo pasa a depender de que "
            "nada se mueva: ni los tipos, ni el negocio."
        ),
        reading=(
            "Más alto, mejor. Si el filing no publica resultado operativo, el EBIT se "
            "deriva del resultado antes de impuestos más intereses. En financieras no se "
            "bandea."
        ),
    ),
    "S3": MetricHelp(
        what=(
            "Qué parte del activo está financiada con recursos propios: patrimonio neto "
            "entre activo total, ambos a cierre del ejercicio. Es S1 mirado desde el otro "
            "lado, aunque no siempre suman uno exacto: el patrimonio puede dejar fuera a "
            "los minoritarios."
        ),
        why=(
            "Es el colchón que absorbe un mal ejercicio sin tocar el reparto: cuanto más "
            "grueso, menos probable que un tropiezo obligue a elegir entre atender al "
            "banco y pagar al accionista."
        ),
        reading=(
            "Más alto, mejor. Si el pasivo total se derivó restando patrimonio al activo, "
            "ésta y S1 suman uno exacto y dejan de probar cosas distintas. En banca es un "
            "proxy del capital."
        ),
    ),
    "S4": MetricHelp(
        what=(
            "Cuántas veces el EBITDA anual cabe en la deuda neta: deuda a corto, porción "
            "corriente y deuda a largo —sin arrendamientos— menos caja e inversiones "
            "financieras corrientes, todo dividido entre el EBITDA."
        ),
        why=(
            "Es la vara con la que el acreedor decide si refinancia y a qué precio. "
            "Cuando se tensa, el ajuste empieza por el dividendo, que es el único pago "
            "que la empresa puede recortar sin incumplir un contrato."
        ),
        reading=(
            "Más bajo, mejor, pero un negativo no es una nota alta: puede ser caja neta o "
            "un EBITDA en pérdidas. Ese EBITDA parte del EBIT REPORTADO, no del limpio "
            "que usan S2 y S4b. Sin semáforo en financieras."
        ),
    ),
    "S4b": MetricHelp(
        what=(
            "La misma deuda neta que S4, pero dividida entre el EBIT limpio: ya después "
            "de amortizaciones, con los deterioros sumados y las plusvalías por venta de "
            "negocios restadas."
        ),
        why=(
            "El desgaste del inmovilizado hay que reponerlo, y esa caja no está "
            "disponible para repartir. Medir la deuda contra un beneficio que ya lo "
            "descuenta dice mejor cuánto aguanta de verdad el dividendo."
        ),
        reading=(
            "Más bajo, mejor, con la misma trampa que S4: en negativo puede ser caja neta "
            "o un EBIT en pérdidas. Existe porque el EBITDA infla el repago cuando hay "
            "mucha amortización. Sin banda en financieras."
        ),
    ),
    "S5": MetricHelp(
        what=(
            "Años de caja libre que costaría devolver la deuda neta: la deuda neta "
            "dividida entre el flujo de explotación menos la inversión en inmovilizado."
        ),
        why=(
            "Mide la deuda en la misma moneda con la que se paga el dividendo, que es "
            "caja. Si devolver lo debido se come muchos años de esa caja, el reparto "
            "compite con el vencimiento y suele perder."
        ),
        reading=(
            "Más bajo, mejor. Con más liquidez que deuda devuelve cero años. Si la caja "
            "libre no es positiva no se calcula, y esa ausencia es en sí la señal. Sin "
            "semáforo en financieras."
        ),
    ),
    "S6": MetricHelp(
        what=(
            "Cuántas veces la caja generada cubre los intereses: flujo de explotación más "
            "gasto financiero más impuestos pagados, todo dividido entre el gasto "
            "financiero."
        ),
        why=(
            "Es el mismo examen que S2 con dinero contado en lugar de devengo, y para "
            "quien vive del reparto pesa más: el bonista cobra de la caja, y lo que sobra "
            "después es lo único repartible."
        ),
        reading=(
            "Más alto, mejor. Si S2 sale bien y ésta no, el beneficio contable no se está "
            "convirtiendo en caja. Su ajuste por sector se deriva del de S2. Sin semáforo "
            "en financieras."
        ),
    ),
    "S7": MetricHelp(
        what=(
            "Cuántos euros de pasivo hay por cada euro de recursos propios: pasivo total "
            "entre patrimonio neto. Se evalúa como banda con dos extremos, no como un "
            "«cuanto menos, mejor»."
        ),
        why=(
            "Dice quién manda de verdad en el balance. Con el pasivo dominando, cualquier "
            "renegociación llega con condiciones, y la primera que se acepta suele ser "
            "limitar o suspender el reparto."
        ),
        reading=(
            "Quedarse por debajo del rango no es rojo: sólo puede indicar capital ocioso. "
            "Con patrimonio negativo no se calcula, y en financieras el número sale sin "
            "semáforo."
        ),
    ),
    "S8": MetricHelp(
        what=(
            "Qué parte de la deuda financiera vence en menos de doce meses: deuda a corto "
            "plazo más la porción corriente de la deuda a largo, entre la deuda total, "
            "sin contar arrendamientos."
        ),
        why=(
            "Un vencimiento próximo hay que refinanciarlo sí o sí, y si el mercado se "
            "cierra el dinero sale de donde se pueda. El reparto es lo primero que se "
            "sacrifica para tapar ese agujero."
        ),
        reading=(
            "Cuanto más baja, menos depende de refinanciar; complementa a L4. Sin deuda "
            "no se calcula, y un cero puede salir de que el filing no publique deuda a "
            "corto y la ingesta la suponga. En banca sí aplica."
        ),
    ),
    # ── rentabilidad ──────────────────────────────────────────────────
    "R1": MetricHelp(
        what=(
            "Qué parte de cada euro vendido queda tras pagar lo que cuesta producir lo "
            "vendido: ventas menos coste de ventas, entre ventas."
        ),
        why=(
            "Es el primer colchón de la cuenta de resultados: de ahí salen los gastos de "
            "estructura, los intereses, los impuestos y, el último de la fila, el reparto "
            "al accionista. Cuando se estrecha, el dividendo es lo que peor lo aguanta."
        ),
        reading=(
            "Más alto mejor, sin banda absoluta: se lee contra su serie y su sector. Sin "
            "coste de ventas desglosado —común en servicios— no se calcula: un hueco "
            "nunca es un cero."
        ),
    ),
    "R2": MetricHelp(
        what=(
            "Qué parte de la venta sobrevive antes de amortizaciones, intereses e "
            "impuestos: EBIT más amortizaciones y depreciaciones, entre ventas."
        ),
        why=(
            "Es la vara con la que el motor mide la deuda: la deuda neta se divide entre "
            "esta magnitud, así que marca cuánto aire hay antes de que el acreedor pase "
            "por delante del accionista. Y no es dinero: por el camino faltan aún el "
            "capex y el circulante."
        ),
        reading=(
            "Sin banda absoluta, se lee como serie. Usa el EBIT tal cual se ingiere, no "
            "el limpio que emplea el margen EBIT; y si el filing no lo publica, viene "
            "reconstruido desde el resultado antes de impuestos."
        ),
    ),
    "R3": MetricHelp(
        what=(
            "Qué parte de la venta queda como resultado de explotación: EBIT limpio entre "
            "ventas. Limpio quiere decir con los deterioros sumados y las plusvalías por "
            "venta de negocios restadas, para que un suceso de una vez no distorsione el "
            "año."
        ),
        why=(
            "Es la rentabilidad del negocio en sí, sin financiación ni fiscalidad de por "
            "medio. Su constancia a lo largo de los años es lo que hace previsible un "
            "dividendo: sobre un margen errático, cualquier cobertura es una lotería."
        ),
        reading=(
            "Sin banda absoluta; se juzga su deriva y su dispersión. El margen operativo "
            "del DuPont usa el EBIT REPORTADO: los dos se separan en los años con "
            "deterioros o plusvalías, y coinciden en el resto."
        ),
    ),
    "R4": MetricHelp(
        what=(
            "Qué parte de cada euro vendido acaba siendo beneficio final, ya descontados "
            "intereses, impuestos y extraordinarios: resultado neto entre ventas."
        ),
        why=(
            "El dividendo se declara contra el beneficio y el payout se mide con ese "
            "mismo numerador, así que este margen fija cuánto hay que repartir sobre el "
            "papel — otra cosa es que exista el dinero, y eso lo dice el margen de caja "
            "libre."
        ),
        reading=(
            "Sin banda absoluta: se lee contra su serie y contra el margen EBIT, del que "
            "se aparta por intereses e impuestos y por los deterioros y plusvalías que "
            "aquél depura. Es el primer factor del DuPont."
        ),
    ),
    "R5": MetricHelp(
        what=(
            "Cuánto beneficio obtiene la empresa por cada euro puesto por los "
            "accionistas: resultado neto entre el patrimonio MEDIO de este ejercicio y el "
            "anterior, no el de cierre."
        ),
        why=(
            "De aquí sale el crecimiento que la empresa puede pagarse sola —el motor lo "
            "calcula como esta cifra por la parte que no reparte—, así que cuando flojea "
            "hay que elegir entre subir el dividendo y seguir creciendo."
        ),
        reading=(
            "Más alto, mejor. Con patrimonio medio negativo no se calcula: el cociente "
            "saldría positivo justo cuando la empresa pierde dinero. Sin ejercicio "
            "anterior sale como aproximación."
        ),
    ),
    "R6": MetricHelp(
        what=(
            "Cuánto beneficio genera por cada euro de activo, lo financie quien lo "
            "financie: resultado neto entre el activo total MEDIO de este ejercicio y el "
            "anterior."
        ),
        why=(
            "Es la rentabilidad del negocio sin el maquillaje del apalancamiento, y por "
            "eso dice mejor que el ROE si el reparto se sostiene en lo que la empresa "
            "produce o en lo que debe."
        ),
        reading=(
            "Más alto mejor. No mejora por endeudarse: la deuda financia activo, que está "
            "en el denominador. Media de dos ejercicios; sin el anterior sale como "
            "aproximación. En banca lleva banda propia."
        ),
    ),
    "R7": MetricHelp(
        what=(
            "Cuánta de la venta acaba convertida en caja libre: flujo de explotación "
            "menos inversión en inmovilizado, entre ventas."
        ),
        why=(
            "El dividendo se paga con dinero, no con beneficio, así que esta es la cifra "
            "que dice cuánto queda de verdad disponible por cada euro facturado. Alimenta "
            "la pregunta de si la empresa genera caja."
        ),
        reading=(
            "Más alto, mejor. Mide caja y no devengo, así que puede separarse del margen "
            "neto; su estabilidad en la serie se lee como indicio de foso. No aplica a "
            "financieras."
        ),
    ),
    "R8": MetricHelp(
        what=(
            "La caja libre repartida entre las acciones: flujo de explotación menos "
            "inversión en inmovilizado, entre las acciones medias básicas del ejercicio."
        ),
        why=(
            "El dividendo se paga por acción y sale de ese dinero, no del beneficio "
            "contable: mientras cubra el reparto queda margen; si lleva años bajando, la "
            "subida anual se está financiando con otra cosa."
        ),
        reading=(
            "No lleva semáforo, se lee como serie: es la contrapartida de la dilución, "
            "porque la caja total puede crecer mientras la caja por acción cae."
        ),
    ),
    "R9": MetricHelp(
        what=(
            "Rentabilidad del capital que el negocio emplea de verdad, al margen de cómo "
            "se financie: resultado de explotación limpio menos impuestos al tipo "
            "efectivo del año, entre el capital invertido MEDIO de este ejercicio y el "
            "anterior (patrimonio más deuda total menos caja)."
        ),
        why=(
            "Dice si la empresa gana más de lo que le cuesta financiarse, que es lo que "
            "permite subir el reparto sin apretar el balance; cuando el retorno es flojo, "
            "el dividendo acaba saliendo de deuda o de recortar inversión."
        ),
        reading=(
            "Más alto, mejor. El capital invertido entra en media de dos ejercicios y el "
            "primero de la serie sale como aproximación; con pérdidas antes de impuestos "
            "no se calcula y en una financiera, sin banda."
        ),
    ),
    "R9b": MetricHelp(
        what=(
            "El mismo denominador del ROIC —capital invertido medio de este ejercicio y "
            "el anterior— pero con la caja arriba: flujo de explotación menos inversión "
            "en inmovilizado. La diferencia está sólo en el numerador, dinero frente a "
            "resultado operativo tras impuestos."
        ),
        why=(
            "Un reparto se paga con efectivo, no con devengo: esto dice cuánto dinero "
            "contante deja al año el capital empleado, que es la bolsa de la que tiene "
            "que salir el dividendo sin recurrir al banco."
        ),
        reading=(
            "Más alto, mejor, y se lee junto al ROIC: si aquél sale alto y éste bajo, el "
            "retorno es contable. En una financiera va sin banda; el primer ejercicio, "
            "como aproximación."
        ),
    ),
    "R10": MetricHelp(
        what=(
            "Cuánto margen bruto produce cada euro de activo: ventas menos coste de "
            "ventas, entre el activo total MEDIO de este ejercicio y el anterior. Se "
            "apoya en el beneficio de más arriba de la cascada contable, el más difícil "
            "de maquillar, en vez del resultado neto del ROA."
        ),
        why=(
            "Un reparto se sostiene durante años sólo si el negocio rinde de verdad sobre "
            "lo que posee: quien saca poco de su activo tiene poco colchón cuando el "
            "ciclo se gira, y acaba eligiendo entre invertir o pagar el dividendo."
        ),
        reading=(
            "Más alto, mejor. El activo va en media de dos ejercicios y el primero de la "
            "serie sale como aproximación; en un banco no se bandea, porque no hay coste "
            "de ventas del que sacar beneficio bruto."
        ),
    ),
    "DUPONT_EM": MetricHelp(
        what=(
            "Cuánto activo sostiene cada euro de fondos propios: activo total medio entre "
            "patrimonio medio, ambos promediados con el ejercicio anterior. Es el factor "
            "que convierte la rentabilidad del activo en la del patrimonio; no es el "
            "ratio de endeudamiento de solvencia, que compara pasivo con activo."
        ),
        why=(
            "Un ROE que sube sólo por este factor no es mejora del negocio, es deuda — y "
            "la deuda cobra antes que el accionista, así que es lo primero que compite "
            "con el reparto cuando suben los tipos o hay que refinanciar."
        ),
        reading=(
            "Sin banda: el nivel sano depende del sector. Con patrimonio medio negativo "
            "no se calcula, y el primer ejercicio de la serie sale como aproximación."
        ),
    ),
    "DUPONT_OM": MetricHelp(
        what=(
            "Qué parte de cada euro vendido queda como resultado operativo, el primer "
            "factor de la identidad: EBIT entre ventas. Usa el EBIT REPORTADO, no el "
            "limpio de deterioros y plusvalías del margen EBIT, porque sólo así se "
            "cancela contra el coste financiero y el ROE reconstruido cierra."
        ),
        why=(
            "Es el tramo que dice cuánto gana el negocio por sí mismo, antes de intereses "
            "e impuestos; si se erosiona, el dividendo pasa a depender de que la "
            "financiación y la fiscalidad no se muevan en contra."
        ),
        reading=(
            "Cuanto más alto, más deja la venta antes de financiación e impuestos. Sin "
            "banda: lleva el EBIT reportado, así que un deterioro de una vez lo aparta "
            "del margen EBIT limpio sin que el negocio cambie."
        ),
    ),
    "DUPONT_TAX": MetricHelp(
        what=(
            "Qué fracción del beneficio sobrevive a Hacienda: resultado neto entre "
            "resultado antes de impuestos, el publicado y, si falta, neto más impuestos. "
            "Es el último tramo de la cascada, del resultado antes de impuestos al neto."
        ),
        why=(
            "Una mejora sostenida aquí puede ser eficiencia fiscal real o el aviso del "
            "cuaderno: ganar más por acción pagando menos a Hacienda no mejora el "
            "negocio, y un reparto que descansa en eso caduca con el primer cambio "
            "normativo."
        ),
        reading=(
            "Sin banda: subir no es bueno ni malo por sí solo. Con resultado antes de "
            "impuestos negativo se sigue calculando —para no romper la descomposición de "
            "un año en pérdidas— y cuesta de leer."
        ),
    ),
    "DUPONT_FIN": MetricHelp(
        what=(
            "Qué parte del resultado operativo sobrevive a los gastos financieros y demás "
            "partidas no operativas: resultado antes de impuestos entre EBIT, el mismo "
            "EBIT reportado del margen operativo para que ambos se cancelen."
        ),
        why=(
            "Los intereses cobran antes que los accionistas: cuando este factor se "
            "estrecha año tras año, el margen que quedaba para mantener —y subir— el "
            "dividendo se lo está comiendo la deuda."
        ),
        reading=(
            "Cuanto más alto, menos pesan los intereses. Sin banda: es una pieza de la "
            "identidad, así que con magnitudes negativas se calcula igual y deja de "
            "leerse como una fracción."
        ),
    ),
    # ── evolución ─────────────────────────────────────────────────────
    "E3": MetricHelp(
        what=(
            "Cuánto oscila el margen operativo limpio —EBIT más deterioros menos "
            "plusvalías por venta de negocio, sobre ventas— a lo largo de la serie: su "
            "desviación típica poblacional, que divide entre los años con margen "
            "calculable y no entre uno menos, en puntos porcentuales."
        ),
        why=(
            "Quien vive del reparto no cobra del margen medio, cobra del que traiga el "
            "año siguiente. Un negocio que salta de un ejercicio a otro puede cubrir hoy "
            "el dividendo y no cubrirlo mañana sin que nada haya cambiado, y obliga a "
            "juzgarlo por su peor año, no por el último."
        ),
        reading=(
            "Menos es mejor. Describe la serie entera, así que se repite idéntica en cada "
            "ejercicio: no busques tendencia en ella. Exige tres ejercicios con margen "
            "calculable; con menos, no sale."
        ),
    ),
    "E4": MetricHelp(
        what=(
            "A qué ritmo puede crecer la empresa sin pedir dinero fuera: ROE multiplicado "
            "por la parte del beneficio que no reparte, o sea por uno menos el payout. El "
            "ROE va sobre patrimonio MEDIO del ejercicio y el anterior, y el payout es "
            "dividendos pagados entre resultado neto."
        ),
        why=(
            "Es lo que el beneficio retenido —la parte que no te llega— compra en negocio "
            "futuro. Si las ventas corren muy por encima de este ritmo, la diferencia la "
            "pagan deuda o acciones nuevas, y ambas compiten con el reparto: los "
            "intereses cobran antes que el accionista y cada acción nueva parte la misma "
            "tarta."
        ),
        reading=(
            "No tiene banda: se lee contra el crecimiento real de las ventas, no contra "
            "un valor bueno. Con pérdidas o patrimonio medio no positivo no sale, y todo "
            "año sin su anterior en la serie es aproximado."
        ),
    ),
    # ── forense ───────────────────────────────────────────────────────
    "m_score": MetricHelp(
        what=(
            "Modelo de Beneish para detectar maquillaje contable: suma ponderada de ocho "
            "variables. Siete comparan un ratio del ejercicio con el del anterior —cobros "
            "sobre ventas, margen bruto, calidad del activo, ventas, amortización, gastos "
            "de estructura y apalancamiento— y la octava es el devengo del año, la que "
            "más pesa."
        ),
        why=(
            "Antes de comprobar si el dividendo está cubierto hay que poder fiarse de las "
            "cifras con las que se calcula esa cobertura: un beneficio inflado sostiene "
            "un reparto que sólo existe sobre el papel."
        ),
        reading=(
            "Cuanto más bajo, mejor. Exige el ejercicio anterior y las ocho variables: si "
            "falta una no se publica nada. Mira qué variable lo dispara, no sólo el "
            "agregado; en financieras no se calcula."
        ),
    ),
    "z_score": MetricHelp(
        what=(
            "Z'' de Altman en su variante de balance de 1995: cuatro proporciones con su "
            "peso —fondo de maniobra total, reservas acumuladas y EBIT, los tres sobre el "
            "activo, y patrimonio entre pasivo total—. No entra ningún dato de mercado, "
            "así que el análisis reejecutado mañana da lo mismo."
        ),
        why=(
            "Una empresa que se acerca a la insolvencia recorta el reparto antes que "
            "ninguna otra cosa: los acreedores cobran primero y el accionista es el "
            "amortiguador."
        ),
        reading=(
            "Más alto, mejor. Usa el EBIT reportado y no el limpio, porque el modelo se "
            "calibró así. No se calcula en financieras, y en socimis se publica avisado: "
            "su balance de inmuebles lo sesga."
        ),
    ),
    "f_score": MetricHelp(
        what=(
            "Nueve pruebas de sí o no sobre la fortaleza financiera. Cuatro miran el "
            "nivel del año: resultado positivo, flujo de explotación positivo, caja por "
            "delante del beneficio y no haber emitido acciones. Las otras cinco miran la "
            "mejora frente al ejercicio anterior en rentabilidad, deuda, liquidez, margen "
            "y rotación."
        ),
        why=(
            "Es una lectura por acumulación de pruebas pequeñas en vez de por un ratio "
            "único, así que un dato raro no la mueve entera; y la dilución cuenta, porque "
            "emitir acciones reparte el mismo dividendo entre más manos."
        ),
        reading=(
            "Más pruebas superadas, mejor, sobre nueve puntos. Necesita el ejercicio "
            "anterior, y si una de las nueve no se puede evaluar no se publica número. La "
            "de dilución sólo la pasa quien no emitió nada."
        ),
    ),
    "accruals": MetricHelp(
        what=(
            "Resultado neto menos flujo de explotación, dividido entre el activo total "
            "MEDIO de los dos ejercicios: la parte del beneficio que no ha llegado en "
            "forma de dinero. Se publica en valor absoluto, y el signo no viaja con el "
            "número: este score no tiene desglose."
        ),
        why=(
            "Un reparto se paga con dinero, no con beneficio contable. Cuando los dos "
            "llevan años separándose, la caja disponible para el dividendo es menor de lo "
            "que sugiere la cuenta de resultados."
        ),
        reading=(
            "Más cerca de cero, mejor en los dos sentidos: que la caja vaya por delante "
            "también es anómalo. Sin año anterior sale marcado como aproximación. No se "
            "calcula en financieras y en socimis va sin banda."
        ),
    ),
    "F5": MetricHelp(
        what=(
            "Qué parte del activo total es fondo de comercio: el sobreprecio pagado en "
            "compras de otras empresas, que no genera caja por sí mismo y puede "
            "deteriorarse de golpe si la adquisición no rinde lo prometido."
        ),
        why=(
            "Un saneamiento no mueve un euro de caja, pero borra el beneficio del "
            "ejercicio y con él la coartada contable del reparto y el margen frente a los "
            "compromisos pactados con la banca."
        ),
        reading=(
            "Cuanto más bajo, menos expuesto, pero no hay vara única: la banda se calibra "
            "por sector porque un comprador en serie sano vive alto, y ahí informa la "
            "deriva más que el nivel."
        ),
    ),
    "F6": MetricHelp(
        what=(
            "Crecimiento del circulante operativo —clientes más existencias menos "
            "proveedores— en valor absoluto, menos el crecimiento de las ventas, en tanto "
            "por uno. Es la descomposición visible del devengo: dice dónde se acumula y "
            "en qué ejercicio mirar."
        ),
        why=(
            "El circulante que engorda más deprisa que el negocio es dinero atrapado en "
            "el almacén o en manos de los clientes, y ese dinero no está en la cuenta el "
            "día que toca pagar."
        ),
        reading=(
            "Cuanto más bajo, mejor; necesita el ejercicio anterior. El circulante entra "
            "en valor absoluto y las ventas con su signo, así que un año de caída de "
            "ventas también empuja la cifra hacia arriba."
        ),
    ),
    "FZ": MetricHelp(
        what=(
            "Probit de quiebra de Zmijewski, con sólo tres ratios de balance: resultado "
            "sobre activo, pasivo total sobre activo y liquidez corriente. No usa "
            "reservas ni fondo de maniobra, y el motor publica la puntuación exacta, no "
            "la probabilidad que se deriva de ella."
        ),
        why=(
            "Es la segunda opinión sobre la solvencia y con menos ingredientes, así que "
            "sobrevive donde el otro modelo no llega a calcularse. Cuando ambos coinciden "
            "la señal es fuerte; cuando discrepan, la discrepancia es el hallazgo."
        ),
        reading=(
            "Cuanto más bajo, mejor; no se calcula en financieras. Si el informe anual no "
            "publica el pasivo total, la ingesta lo deduce restando patrimonio al activo "
            "y el término de deuda hereda esa deducción."
        ),
    ),
    "F7": MetricHelp(
        what=(
            "Recuento de cuántas de seis señales de cocina contable se encienden: "
            "beneficio por delante de la caja, más días de cobro, más días de inventario, "
            "otros activos corrientes al alza sobre ventas, amortización más lenta y un "
            "activo que crece con fuerza."
        ),
        why=(
            "Cuenta señales en vez de ponderarlas, así que un dato raro no lo dispara ni "
            "lo apaga; y cada una encendida apunta a un sitio concreto por donde el "
            "dinero se queda por el camino en lugar de llegar al bolsillo del accionista."
        ),
        reading=(
            "Cuantas menos, mejor; exige el ejercicio anterior. Los checks que no aplican "
            "al sector —el inventario en una eléctrica— salen del recuento: mira sobre "
            "cuántos va, y si quedan muy pocos no hay número."
        ),
    ),
    # ── dividendo ─────────────────────────────────────────────────────
    "D1": MetricHelp(
        what=(
            "Qué parte del beneficio contable se va en dividendo: dividendos pagados "
            "entre resultado neto, o entre FFO si es una socimi. Mide contra el "
            "beneficio, no contra la caja, que es lo que hace D2."
        ),
        why=(
            "Un reparto que se come casi todo lo que la empresa gana deja sin margen al "
            "primer año malo: es la señal más antigua de que el próximo recorte sólo "
            "depende de que algo se tuerza."
        ),
        reading=(
            "Más bajo, más holgura. Con pérdidas sale negativo —y con banda sana, que "
            "aquí no significa nada bueno— en vez de no calculable. Es la única del "
            "bloque que sí se calcula en una financiera."
        ),
    ),
    "D2": MetricHelp(
        what=(
            "Dividendos pagados entre la caja libre del año —flujo de explotación menos "
            "inversión en inmovilizado—, o entre FFO en una socimi. Es la primaria de la "
            "familia: el dividendo se paga con caja."
        ),
        why=(
            "El dinero que sale por la puerta tiene que haber entrado antes; cuando el "
            "reparto se acerca a todo lo que genera el negocio, un ejercicio flojo obliga "
            "a elegir entre recortarlo o endeudarse para mantenerlo."
        ),
        reading=(
            "Más bajo, más holgura, y sólo con caja libre positiva: si es negativa el "
            "cociente sale negativo y la banda lo da por sano. En una financiera no se "
            "calcula: su negocio es mover dinero."
        ),
    ),
    "D3": MetricHelp(
        what=(
            "Cuántas veces cubre la caja libre al dividendo del año: caja libre entre "
            "dividendos pagados, en veces (FFO en una socimi). Es la misma relación de D2 "
            "leída al revés."
        ),
        why=(
            "Dicho en veces se entiende cuánto puede caer la generación de dinero antes "
            "de que el reparto deje de pagarse solo, que es la pregunta que importa a "
            "quien vive de ese cobro."
        ),
        reading=(
            "Aquí más alto es mejor. Si la empresa no reparte, el divisor es cero y sale "
            "no calculable, no cero. En una financiera no se calcula."
        ),
    ),
    "D4": MetricHelp(
        what=(
            "Dividendos pagados entre la caja libre una vez restada la retribución en "
            "acciones. El flujo de explotación no descuenta ese coste, así que este "
            "payout lo devuelve al denominador."
        ),
        why=(
            "Pagar a la plantilla con acciones no gasta caja pero reparte la empresa: si "
            "el dividendo sólo cuadra ignorándolo, el accionista lo cobra a cambio de "
            "quedarse cada año con un trozo más pequeño."
        ),
        reading=(
            "Más bajo mejor; lo informativo es la distancia con D2. Usa la caja libre "
            "también en una socimi y en una financiera no se calcula; con caja libre "
            "negativa sale negativo y con banda sana."
        ),
    ),
    "D5": MetricHelp(
        what=(
            "Cuánta caja libre se devuelve al accionista contando también la recompra: "
            "dividendos pagados más recompra de acciones, entre la caja libre del año."
        ),
        why=(
            "Dividendo y recompra compiten por el mismo dinero, así que un reparto que "
            "parece cómodo mirando sólo el dividendo puede estar ya al límite en cuanto "
            "se suma lo que la empresa gasta en retirar acciones."
        ),
        reading=(
            "Más bajo mejor; usa la caja libre también en una socimi y en una financiera "
            "no se calcula. Con caja libre negativa sale negativo y con banda sana, "
            "aunque todo lo repartido venga de fuera."
        ),
    ),
    "D6": MetricHelp(
        what=(
            "Qué parte del FFO reparte una socimi: dividendos pagados entre FFO, o sea "
            "resultado neto más amortizaciones y deterioros, menos plusvalías por venta "
            "de negocio."
        ),
        why=(
            "En un inmueble la amortización es un apunte que no refleja desgaste real, "
            "así que el payout contable exagera el esfuerzo; ésta es la cobertura que de "
            "verdad describe si la socimi puede seguir pagando."
        ),
        reading=(
            "Más bajo, más holgura. Fuera de una socimi sale no calculable. Dentro "
            "coincide con D1 —que también pasa a medirse sobre FFO—: entre las dos filas "
            "cambia la banda, no el número."
        ),
    ),
    "D8": MetricHelp(
        what=(
            "Cuánta caja libre sobra tras pagar el dividendo, medida contra el tamaño del "
            "negocio: caja libre menos dividendos pagados, entre las ventas del año (FFO "
            "menos dividendos en una socimi)."
        ),
        why=(
            "Es lo que queda para amortizar deuda, invertir o aguantar un mal ejercicio "
            "sin tocar el reparto: el colchón que separa un dividendo cómodo de otro que "
            "ya depende de que todo salga bien."
        ),
        reading=(
            "Más alto, más colchón. El denominador son las ventas, no el precio de la "
            "acción: no es una rentabilidad. En una financiera no se calcula."
        ),
    ),
    "Q1": MetricHelp(
        what=(
            "Calidad de la caja: cuánto del beneficio declarado llega en forma de dinero. "
            "Es el flujo de explotación entre el resultado neto —siempre el neto, también "
            "en una socimi—, así que enfrenta lo devengado con lo cobrado."
        ),
        why=(
            "El reparto se paga con dinero contante, no con apuntes contables. Si lo "
            "declarado no se convierte en cobros, la empresa está distribuyendo contra "
            "algo que todavía no ha entrado por la puerta y acabará tirando de deuda."
        ),
        reading=(
            "Más alto mejor y sin tope por arriba, así que una socimi sale verde de "
            "oficio: la amortización del inmueble hunde el resultado neto sin tocar la "
            "caja y aquí no se sustituye por FFO."
        ),
    ),
    "Q2": MetricHelp(
        what=(
            "Calidad de la caja: qué parte del resultado operativo bruto sobrevive como "
            "caja libre. Es caja libre —flujo de explotación menos inversión— entre "
            "EBITDA, y ese EBITDA se arma con el EBIT tal y como se reporta más las "
            "amortizaciones."
        ),
        why=(
            "Enseña lo que se queda por el camino entre operar y tener dinero disponible: "
            "impuestos, circulante y, sobre todo, la inversión que hay que hacer sí o sí. "
            "Del resto es de donde sale el pago a los accionistas."
        ),
        reading=(
            "Más alto mejor, con una trampa: un ejercicio con deterioro grande baja el "
            "EBIT reportado y con él el denominador, así que la conversión sale mejor de "
            "lo que es. No aplica a financieras."
        ),
    ),
    "Q3": MetricHelp(
        what=(
            "Calidad de la caja: si las dos formas de medirla cuadran. Compara la caja "
            "libre del estado de flujos con la reconstruida desde el devengo —EBITDA "
            "menos inversión, menos variación del circulante operativo y menos impuestos "
            "pagados—, en proporción a la primera."
        ),
        why=(
            "Cuando un mismo ejercicio arroja dos cifras distintas de dinero disponible, "
            "una de las dos está contando otra cosa. Antes de fiarse del colchón que "
            "cubre el reparto conviene comprobar que ese colchón aparece medido por los "
            "dos caminos."
        ),
        reading=(
            "Más bajo mejor. Va en valor absoluto: no dice cuál de las dos medidas falla "
            "ni en qué sentido. Exige el ejercicio anterior, así que el primero de la "
            "serie no sale. No aplica a financieras."
        ),
    ),
    "Q5": MetricHelp(
        what=(
            "Calidad del beneficio: cuánto del resultado antes de impuestos lo explican "
            "sucesos de una vez. Es la diferencia entre plusvalías por venta de negocio y "
            "deterioros, en valor absoluto, sobre ese resultado —el publicado y, si "
            "falta, resultado neto más impuestos—, también en absoluto."
        ),
        why=(
            "Un dividendo que se apoya en la venta de un negocio, o en el año en que no "
            "tocó apuntar ninguna pérdida de valor, no se apoya en nada el ejercicio "
            "siguiente. Sirve para separar el reparto repetible del que sólo se pudo "
            "pagar una vez."
        ),
        reading=(
            "Más bajo mejor. Plusvalías y deterioros se restan ANTES del valor absoluto, "
            "así que un año con las dos partidas grandes a la vez sale limpio sin serlo: "
            "se cancelan entre sí."
        ),
    ),
    "B3": MetricHelp(
        what=(
            "Soporte del balance: cuántos años de dividendo cubriría el dinero que ya "
            "está en el balance sin generar un euro más. Es efectivo y equivalentes más "
            "activos financieros corrientes al cierre del ejercicio, entre los dividendos "
            "pagados de ese año."
        ),
        why=(
            "Es el margen para aguantar un mal ejercicio sin tocar el reparto: mientras "
            "quede colchón, un tropiezo del negocio no obliga a recortar de inmediato. "
            "Compra tiempo, que en una tesis de rentas es justo lo que hace falta."
        ),
        reading=(
            "Más alto mejor, pero es un colchón, no una previsión: ese dinero responde "
            "también de vencimientos de deuda y del propio negocio. No aplica a "
            "financieras."
        ),
    ),
    "T2": MetricHelp(
        what=(
            "Trayectoria: a qué ritmo compuesto anual ha crecido el dividendo por acción, "
            "calculado como dividendos pagados entre acciones medias básicas. Toma el "
            "primer y el último ejercicio con dato y anualiza el salto entre ellos."
        ),
        why=(
            "Un reparto que crece por encima de la inflación conserva el poder "
            "adquisitivo de quien vive de él; uno plano lo va perdiendo cada año sin que "
            "nadie anuncie nada. Y el crecimiento suele apagarse antes de que llegue el "
            "recorte."
        ),
        reading=(
            "Más alto mejor, e ignora el camino intermedio: dos extremos parecidos tapan "
            "un recorte por medio. Si algún extremo no es positivo no sale, y sólo mide "
            "la historia ingerida, no toda la de la empresa."
        ),
    ),
    "T3": MetricHelp(
        what=(
            "Trayectoria: cómo de errático ha sido el reparto, no su nivel. Es la "
            "desviación típica poblacional del payout sobre caja libre (D2) —sobre FFO si "
            "es una socimi— de los ejercicios en que ese payout se pudo calcular, "
            "expresada en puntos porcentuales."
        ),
        why=(
            "Una política de dividendo creíble se nota en que la proporción repartida "
            "apenas se mueve. Cuando salta de un año a otro, detrás no hay política sino "
            "lo que fuera sobrando, y eso puede dejar de sobrar sin previo aviso."
        ),
        reading=(
            "Más bajo mejor, y mide dispersión: un payout alto pero constante puntúa "
            "bien. Necesita al menos tres ejercicios con payout calculable, así que en "
            "una financiera no llega a salir."
        ),
    ),
    # ── valoración por múltiplos ──────────────────────────────────────
    "V1": MetricHelp(
        what=(
            "Cuánto paga el mercado por cada euro de beneficio: la capitalización —precio "
            "actual por las acciones en circulación al cierre— entre el resultado neto "
            "del último ejercicio cerrado."
        ),
        why=(
            "El dividendo se reparte con cargo al resultado, así que este múltiplo dice "
            "cuántos años de beneficio actual cuesta comprar esa renta. Pagar caro no "
            "rompe el reparto, pero reduce lo que se cobra por cada euro invertido."
        ),
        reading=(
            "Cuanto más bajo, menos se paga por ese beneficio. Con resultado nulo o "
            "negativo se deja en blanco, porque el cociente saldría positivo y se leería "
            "como barato; sin banda de referencia."
        ),
    ),
    "V2": MetricHelp(
        what=(
            "Cuánto paga el mercado por cada euro facturado: la capitalización (precio "
            "por acciones al cierre) entre las ventas del último ejercicio."
        ),
        why=(
            "Es el múltiplo que menos se descoloca cuando un deterioro o una plusvalía "
            "deforman el resultado de un año: sirve de contraste al PER justo cuando el "
            "beneficio del que sale el dividendo deja de ser representativo."
        ),
        reading=(
            "Cuanto más bajo, menos se paga por esas ventas. En una financiera «ventas» "
            "es margen por intereses y comisiones, así que no compara con una industrial; "
            "tampoco lleva banda."
        ),
    ),
    "V3": MetricHelp(
        what=(
            "Cuánto paga el mercado por cada euro de patrimonio contable: la "
            "capitalización entre el patrimonio neto al cierre del último ejercicio."
        ),
        why=(
            "En un negocio cuyo reparto se apoya en el balance —una utility, un REIT— "
            "dice si estás comprando esos activos con prima o con descuento; en uno que "
            "gana dinero sin apenas activos, informa poco."
        ),
        reading=(
            "Más bajo, más barato. Usa el saldo de patrimonio al cierre y no la media de "
            "dos ejercicios que emplean los ratios de rentabilidad. Con patrimonio nulo o "
            "negativo se deja en blanco, y no lleva banda."
        ),
    ),
    "V4": MetricHelp(
        what=(
            "Cuánto paga el mercado por cada euro de caja libre, entendida aquí como "
            "flujo de explotación menos inversión en inmovilizado: la capitalización "
            "entre esa caja libre."
        ),
        why=(
            "El dividendo se cobra en dinero, no en resultado contable, así que éste es "
            "el múltiplo que dice más directamente a qué precio estás comprando el flujo "
            "del que sale tu ingreso."
        ),
        reading=(
            "Más bajo, más barata la caja que genera el negocio. Con caja libre nula o "
            "negativa se deja en blanco; sin banda."
        ),
    ),
    "V5": MetricHelp(
        what=(
            "Precio de la empresa entera —capitalización más deuda neta: deuda financiera "
            "sin arrendamientos, menos caja y activos financieros corrientes— entre el "
            "EBITDA, que es el EBIT más amortizaciones; si el filing no reporta el EBIT, "
            "se deduce del resultado antes de impuestos más el gasto financiero."
        ),
        why=(
            "Neutraliza cómo está financiado el negocio, de forma que uno muy endeudado y "
            "otro que no lo está se pueden comparar — y el apalancamiento es justo lo que "
            "decide si el reparto aguanta un año malo."
        ),
        reading=(
            "Más bajo, más barata; sin banda. Queda en blanco por los dos extremos: si el "
            "EBITDA no es positivo y si la caja neta supera a la capitalización, porque "
            "ahí el múltiplo saldría negativo."
        ),
    ),
    "V6": MetricHelp(
        what=(
            "Cuánto patrimonio contable respalda cada acción según libros, no según el "
            "mercado: patrimonio neto al cierre entre las acciones en circulación a esa "
            "misma fecha."
        ),
        why=(
            "Puesto al lado de la cotización es lo que convierte un precio en un "
            "múltiplo. Y por sí solo dice cuánto respaldo contable queda detrás de cada "
            "acción: cuando ahí no queda nada, el reparto se sostiene sólo con la caja "
            "del año."
        ),
        reading=(
            "Se emite aunque salga negativo, a diferencia de los múltiplos: ahí el signo "
            "informa. Sin banda; comparado con la cotización da el precio/valor contable."
        ),
    ),
    "V7": MetricHelp(
        what=(
            "Caja libre por cada euro de capitalización, en porcentaje: el flujo de "
            "explotación menos la inversión en inmovilizado, dividido entre la "
            "capitalización."
        ),
        why=(
            "Es la comparación directa con lo que se cobra: si el dinero que el negocio "
            "deja libre por cada euro invertido no llega al dividendo que reparte, ese "
            "reparto se está financiando con otra cosa."
        ),
        reading=(
            "Más alta, mejor; sin banda. Cuando ambos existen es el inverso exacto del "
            "precio/caja libre; lo que cambia es el dominio: aquí no se exige caja "
            "positiva, y con caja negativa aquel se deja en blanco."
        ),
    ),
}
"""Las 64 fichas, agrupadas por familia y en el orden del informe.

Cuatro gates de contrato las vigilan: cobertura en las dos direcciones (falta
una / sobra una), longitud y no-tautología POR CAMPO, ningún umbral escrito a
mano, y que `why` no sea una paráfrasis de `what`."""


def metric_help(key: str) -> MetricHelp | None:
    """La ficha de una métrica, o `None` si no está catalogada."""
    return METRIC_HELP.get(key)
