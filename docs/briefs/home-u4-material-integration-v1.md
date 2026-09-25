# U4 — Integración material de Home

Fecha de apertura y aprobación: 2026-09-09. Estado: **videoteca empotrada autorizada;
U4.2a/b aprobadas; U4.2c/d integradas y aceptadas el 2026-09-12; U4.3 integrada con
la opción B de dos carteleras el 2026-09-13. U4.4 implementada y U4.6a verificada;
resta regresión U4.6b; U4.5 absorbida**.
Modo: Operate con exploración material. Superficie:
Home web de escritorio.

## Trabajo y resultado

Quien recorre su videoteca debe percibir cartelera, estantería y ficha breve como partes
de una misma máquina de archivo audiovisual. La interacción y los datos actuales se
conservan. El éxito visual es que ningún control, display, placa o lomo parezca colocado
encima de un fondo o asset independiente.

## Dirección inicial e historial

Una consola gráfica semiilustrada reemplaza la mezcla actual entre pared fotográfica,
carcasa raster hiperrealista y paneles CSS. Formas controladas, metal pintado oscuro,
serigrafía, biseles y sombras internas construyen la profundidad. Cyan, magenta y dorado
se comportan como reflejo o señal funcional, no como iluminación ambiental competitiva.

El fondo actual no conserva ningún rasgo: deja de ser una pared reconocible y pasa a ser
un campo nocturno abstracto, de contraste bajo, derivado de los materiales del aparato.
La escena memorable es un mueble que emerge de ese campo y continúa fuera del encuadre
hacia la derecha.

El owner eligió la **opción B — Espina de control**. El marco de cartelera y el poste
izquierdo pertenecen a una misma columna estructural; de ella nacen el carril de
selección, el travesaño y la videoteca. También pidió reincorporar el detalle lateral que
la comparación mostraba: ventilaciones y las leyendas `ARCHIVO / PELÍCULAS / MEMORIA` y
`REBOBINAR / EXPLORAR / CONSERVAR`. Son identidad serigrafiada, no acciones ni promesas.

## Composición e interacción iniciales

- La franja inferior de la cartelera no tiene que convertirse obligatoriamente en un
  panel monolítico. Acciones, miniatura, datos, señal y estado sí comparten retícula,
  basamento, profundidad e iluminación. La señal funciona como pantalla empotrada.
- La continuidad fuera de cuadro a la derecha se conserva. El poste izquierdo visible
  pertenecía a la B inicial; en la nueva comparación puede sustituirse por otro soporte.
  No admite corte magenta terminal, vacío negro ni una textura repetida para fingir ancho.
- Placas y VHS comparten la luz del hueco. Las placas quedan físicamente ancladas al
  travesaño y los lomos apoyados sobre la base; selección y foco siguen diferenciados.
- La consola inferior ocupa los huecos existentes de la carcasa. El contenido queda
  detrás de un bisel y una máscara comunes, sin un rectángulo cyan flotante. Acciones,
  imágenes, ficha, créditos y estado continúan siendo contenido semántico vivo.

## Alcance y límites

U4 trabaja primero en 1280×720, 1440×900 y 1920×1080. La arquitectura debe permitir una
adaptación futura, pero esta entrega sólo exige en móvil un smoke de reflow y ausencia de
overflow horizontal. La experiencia vertical prioritaria pertenece al futuro cliente
nativo Kotlin.

No se modifican APIs, datos, reglas de selección, navegación, permisos, contenido factual
ni tipografía global. No se agregan decoración, pantallas o controles sin función. No se
rasterizan textos ni controles principales.

## Secuencia

1. U4.1: tres north stars de escritorio con la dirección fija y distinta topología.
2. U4.2: escenario abstracto y carcasa continua.
3. U4.3: integración material de la cartelera.
4. U4.4: unificación de mueble, placas y VHS.
5. U4.5: consola inferior empotrada.
6. U4.6: gate visual desktop y smoke responsive.

U4.1 quedó cerrada con la elección B. La nueva exploración U4.2 muestra la composición
completa para validar sus encuentros. Su implementación sigue centrada en escenario y
carcasa; la integración de los componentes de cartelera se completa en U4.3.

## Reapertura U4.2

El owner conservó la dirección B pero rechazó su primera traducción: la columna se percibía
pegada y la carcasa rasterizada seguía compitiendo con el contenido. La columna deja de
tratarse como una «espina» autónoma y pasa a ser el costado técnico del bastidor completo.
Cartelera, rótulo, navegación y videoteca nacen sin separación de ese mismo borde.

La primera revisión eliminó los dos grandes assets y ensayó carcasa y fondo CSS. El owner
rechazó también ese resultado: se perdieron espesor y acabado, permanecieron elementos
superpuestos y la estructura no llegó a expresar la opción B.

La segunda revisión compara tres composiciones completas: B reconstruida con el lateral
unido al marco, carcasa horizontal sin columna y videoteca empotrada en una superficie
común. El soporte de las ventilaciones puede cambiar. CSS exclusivo deja de ser una
condición; se evalúan assets coherentes con el fondo, biseles segmentados y un material
compartido entre piezas. La inspección y los prompts quedan en
`docs/design/u4-2-options-v2/`. No hay nueva base aprobada.

## Enfoque actual — videoteca empotrada

El owner volvió a adjuntar la referencia empotrada y pidió planificar una continuidad
real entre el background y los bordes. La B inicial queda como historia, no como
topología obligatoria. El frente completo usa un solo material; cartelera, estante y
consola se alojan en aberturas con profundidad hacia adentro. No se conserva una
carcasa exterior independiente ni se intenta disimular su rectángulo con un fondo parecido.

El plan propuesto vive en `docs/design/u4-2-inset-library-plan.md`: material/kit U4.2a,
encuentro representativo U4.2b y base continua U4.2c, antes de completar U4.3–U4.6.
La referencia está preservada como `docs/design/u4-2-options-v2/owner-reference-inset-library.png`.
El grado de desgaste se revisará en una muestra sin cambiar la dirección elegida.
El owner autorizó arrancar tras revisar si hacía falta cambiar la base tecnológica.
Se conserva Python/FastAPI + HTML/CSS/JS modular; no se agrega un framework. U4.2a vive
en `docs/design/u4-2a-material-kit-v1/`, fuera de la Home de producción. El owner aprobó
el acabado el 2026-09-10; la entrega técnica es CSS + fuentes RGB con recortes declarados,
no exports alpha. U4.2b se probó con renderer real y fixture aislada en
`docs/design/u4-2b-integrated-junction-v1/`. El owner aprobó el encuentro y pidió más
escala: playlist Winamp con seis filas visibles, sin scroll interno en escritorio.
U4.2c aplica la base a Home sin cambiar JS, APIs ni datos. Evidencia de la aplicación
real con catálogo desechable en `docs/design/u4-2c-evidence/`. U4.2 espera aceptación
visual de la integración en ese corte; posteriormente d.3 consolidó la consola y
el owner aceptó el conjunto el 2026-09-12. En ese corte U4.3–U4.6 seguían abiertas.
La evolución U5–U9/MW1 está en `docs/design/home-evolution-backlog-2026-09-12.md`;
Actualización 2026-09-13: U6.1 cerró con B; U4.3 integra dos carteleras y una consola
común. U4.5 queda absorbida. U4.4 completa apoyos, placas y luz; U4.6a verifica
escritorio/reflow/foco/contraste. Restan regresión histórica U4.6b y compatibilidad U5.
Evidencia en `docs/design/u4-4-visual-gate/README.md`.
