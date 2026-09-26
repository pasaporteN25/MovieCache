---
name: Movie Inbox
description: Un videoclub nocturno para operar, explorar y recordar una biblioteca audiovisual personal.
colors:
  playhead-pink: "#ff3ea5"
  playhead-pink-deep: "#d92a91"
  crt-cyan: "#22d8e5"
  rental-sticker-gold: "#ffbe55"
  tape-violet: "#785cff"
  cassette-black: "#080a18"
  night-shelf: "#11152a"
  case-blue: "#191d38"
  screen-white: "#f5f3ff"
  ink-on-signal: "#080a18"
  dusty-lavender: "#a7aac7"
  action-violet: "#c247ff"
  soft-signal-line: "rgba(139, 124, 255, 0.34)"
  projection-panel: "rgba(17, 21, 42, 0.9)"
  control-background: "#0c1025"
  control-border: "#6f78b5"
  quiet-control: "#222745"
  text-pink: "#ff79bf"
  text-cyan-soft: "#9bf8ff"
  text-gold-soft: "#ffe0a2"
  text-danger-soft: "#ffacb8"
  poster-red-mid: "#76256f"
  poster-teal-mid: "#14627f"
  poster-gold-mid: "#a13779"
  poster-violet-mid: "#34306f"
  poster-deep: "#0a0c1d"
  chip-tint-red: "#ffb8dc"
  chip-tint-teal: "#a8faff"
  chip-tint-gold: "#fff4d7"
  chip-tint-violet: "#dedaff"
  danger: "#ff667a"
  danger-border: "#b9564c"
  danger-ink: "#8e2f28"
typography:
  home-plaque:
    fontFamily: '"Oswald", "Arial Narrow", "Trebuchet MS", sans-serif'
    fontWeight: 400
    fontSize: "20px"
    lineHeight: 1.15
    letterSpacing: "0.12em"
  home-plaque-mobile:
    fontSize: "18px"
  home-signage:
    fontFamily: '"Barlow Condensed", "Arial Narrow", "Trebuchet MS", sans-serif'
    fontWeight: 600
  home-data:
    fontFamily: '"IBM Plex Mono", "Courier New", monospace'
    fontWeight: 400
  display:
    fontFamily: '"Arial Narrow", "Trebuchet MS", sans-serif'
    fontSize: "clamp(28px, 4vw, 46px)"
    fontWeight: 900
    lineHeight: 0.95
    letterSpacing: "0.055em"
  feature:
    fontFamily: '"Arial Narrow", "Trebuchet MS", sans-serif'
    fontSize: "clamp(30px, 5vw, 68px)"
    fontWeight: 900
    lineHeight: 0.88
    letterSpacing: "0.02em"
  title:
    fontFamily: '"Arial Narrow", "Trebuchet MS", sans-serif'
    fontSize: "24px"
    fontWeight: 900
    lineHeight: 1.12
    letterSpacing: "0.035em"
  stat:
    fontSize: "22px"
  body:
    fontFamily: '"Space Grotesk", "Trebuchet MS", Verdana, ui-sans-serif, system-ui, sans-serif'
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0"
  compact:
    fontSize: "15px"
  control:
    fontSize: "14px"
  small:
    fontSize: "13px"
  meta:
    fontSize: "12px"
  caption:
    fontSize: "11px"
  label:
    fontFamily: '"Courier New", monospace'
    fontSize: "10px"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "0.12em"
rounded:
  none: "0"
  control: "3px"
  result: "8px"
  case: "4px 10px 10px 4px"
  pill: "999px"
spacing:
  control-y: "8px"
  control-x: "10px"
  compact: "14px"
  base: "18px"
  section: "22px"
  page-x: "28px"
  page-y: "56px"
  grid-max: "30px"
components:
  button-primary:
    backgroundColor: "{colors.playhead-pink}"
    textColor: "{colors.ink-on-signal}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
    height: "38px"
  button-quiet:
    backgroundColor: "{colors.quiet-control}"
    textColor: "{colors.screen-white}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
    height: "38px"
  input-search:
    backgroundColor: "{colors.control-background}"
    textColor: "{colors.screen-white}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
    height: "38px"
  navigation-active:
    backgroundColor: "{colors.case-blue}"
    textColor: "{colors.crt-cyan}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "6px 10px"
    height: "32px"
  status-chip:
    backgroundColor: "{colors.case-blue}"
    textColor: "{colors.screen-white}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "3px 7px"
  dvd-case:
    backgroundColor: "{colors.cassette-black}"
    textColor: "{colors.screen-white}"
    typography: "{typography.title}"
    rounded: "{rounded.case}"
    padding: "7px 7px 7px 13px"
    width: "100%"
---

# Design System: Movie Inbox

## Overview

**Creative North Star: "El videoclub después de medianoche"**

Movie Inbox es nocturna, cinéfila, táctil y técnica. La interfaz debe sentirse como un archivo personal abierto después de la última función: precisa para mantener una biblioteca grande, pero atravesada por el placer material de explorar cajas, portadas, fichas y recuerdos.

La experiencia combina controles técnicos sobrios con portadas táctiles y expresivas. Las superficies operativas permanecen planas, legibles y previsibles; la profundidad y el movimiento se reservan para objetos del videoclub y momentos de descubrimiento. Movie Inbox no debe parecer un dashboard SaaS genérico, una copia de Netflix ni una interfaz minimalista pálida y excesivamente redondeada.

**Key Characteristics:**
- Nocturna y de alto contraste, sin caer en una paleta de un solo color.
- Operativa en controles y navegación; cinematográfica en portadas, spotlight y ficha.
- Inspirada en cajas de video, etiquetas de alquiler, señal CRT y archivo físico.
- Densa pero organizada, con complejidad revelada sólo cuando la tarea la necesita.
- Personal antes que algorítmica: la biblioteca propia conserva la autoridad visual.

## Colors

La paleta combina una base azul-negra de archivo con señales magenta, cyan, violeta y dorada que cumplen funciones distintas.

### Primary
- **Playhead Pink:** acción principal, reproducción, énfasis editorial y bordes de alta atención.
- **Playhead Pink Deep:** estado hover o presión del acento principal.

### Secondary
- **CRT Cyan:** foco, navegación activa, enlaces y confirmaciones de disponibilidad.
- **Tape Violet:** estructura secundaria, separadores y superficies de archivo.
- **Rental Sticker Gold:** selección aleatoria, puntuación, advertencias suaves y etiquetas físicas.

### Neutral
- **Cassette Black:** fondo más profundo, lomos y marcos materiales.
- **Night Shelf:** superficie operativa principal y paneles administrativos.
- **Case Blue:** caja, bloque elevado y agrupación secundaria.
- **Screen White:** texto principal y títulos.
- **Dusty Lavender:** texto secundario, metadata y estados silenciosos.
- **Soft Signal Line:** bordes y divisores de baja intensidad.
- **Projection Panel:** paneles translúcidos sobre el fondo nocturno.
- **Control Background, Control Border y Quiet Control:** campos, botones secundarios y estados neutros.

### Derived Tones

Cada color de señal tiene variantes derivadas para usos puntuales, además de su tono base.

- **Rampa de carátula** (Poster Red/Teal/Gold/Violet Mid, Poster Deep): degradé de 3 paradas — señal brillante, tono medio apagado, casi negro (`#0a0c1d`) — para el fallback de portada del DVD Case cuando no hay imagen real.
- **Tinte de chip** (Chip Tint Red/Teal/Gold/Violet): texto pálido sobre el chip de estado de la tarjeta y sobre el ícono de placeholder de carátula. Es una familia distinta de Text Pink, Text Cyan Soft y Text Gold Soft (el tono más suave que ya usan kickers y mensajes de feedback en toda la app): resuelven contraste en superficies distintas y no se intercambian.
- **Danger:** fuera de las 4 señales. Text Danger Soft es el texto de mensajes de error; Danger Border y Danger Ink son el borde y el texto de una acción destructiva; Danger es el borde y fondo ambiental de una zona de riesgo (por ejemplo, eliminar una cuenta). Es la única familia roja que no es Playhead Pink.

**The Signal Hierarchy Rule.** Playhead Pink llama a actuar, CRT Cyan confirma y orienta, Rental Sticker Gold destaca valor o excepción y Tape Violet estructura; no intercambiar sus roles por decoración.

## Typography

### Excepción Home U2-P.2 (2026-09-06)

Opción B elegida por el usuario: **Barlow Condensed 600 normal** en títulos de lomos
y categorías en el corte inicial; **IBM Plex Mono 400 normal** en consola, playlist
y datos de Home. P.4 reemplaza sólo el rol de placas/categorías por Oswald 400.
Fuentes WOFF2 autoalojadas, latin/latin-ext a demanda, `font-display: swap`, sin pesos
ni cursivas sintéticos. Fallbacks: Arial Narrow/Trebuchet y Courier New respectivamente.
Implementación acotada a `#homeView` en `home-type.css`: la marca global, Colección,
Club, formularios y el dossier conservan su tipografía. P.2 no cambió la construcción
de los lomos; P.3 fue autorizada posteriormente el 2026-09-07 y se describe abajo.
Las reglas globales siguientes siguen vigentes fuera de estos roles de Home.

### Lomos Home U2-P.3 (2026-09-07)

Una hilera de cajas con cuerpo, no trazos separados. El asset existente del lomo se
encuadra al 174% de ancho para quitar su margen transparente visual, sin alterar sus
bytes. Cajas de 72–84 px en escritorio, 68 px en móvil; separación entre cajas de
6 px. Mantener las proporciones del mueble general para P.5.

Rotulación cálida `#dfcba9`, Barlow Condensed 600 normal, lectura inferior-superior.
Escala 20/18/16 px según longitud (hasta 22, hasta 36, más de 36 caracteres), columnas
balanceadas para títulos largos. Pie independiente: año de 14 px y placa VHS de 12 px,
ambos Plex 400. VHS es firma de la interfaz, no formato factual de la obra. El tipo
real sigue accesible en el botón y en la fila Tipo de la ficha.

La caja seleccionada tiene borde dorado y leve elevación; el foco sigue siendo cyan.
El título completo permanece en HTML, nombre accesible y tooltip; no comprimir letras
ni bajar de 16 px para esconder un caso extremo. No aplica a cajas de otras superficies.

### Placas y altura Home U2-P.3/P.4 (elección del 2026-09-07)

El usuario eligió **Oswald 400 + opción de lomo B**. Las placas usan el asset
`home-category-plaque-v1.png`: metal ennegrecido, marco de latón y tornillos, con texto
HTML dorado y conteo real Plex. `border-image` preserva las esquinas. No hay Bebas Neue
en producción. Oswald WOFF2 latin/latin-ext local, con OFL, sin síntesis.

En escritorio las placas de 48 px suben al travesaño; título 20 px y tracking .12em.
Su ancho se limita al grupo y a 440 px. Los nombres que no caben conservan el texto
completo accesible y en tooltip. En móvil la placa fluye antes de su fila, título de
18 px, líneas libres y sin elipsis. Mantener selección cálida y foco cyan existentes.

El carril sube de 18.44% a 8.8% y deja 60 px superiores para señalización. La base del
lomo y su ancho no se mueven: en el mueble de 640 px gana 43.7 px de alto. Móvil usa
280 px de alto y el mismo ancho 68 px. La opción B añade canto interior de 5 px,
luz lateral y sombra corta, sin perspectiva, sin escalar letras ni rehacer el VHS.
La consola sigue pendiente de P.6; el poste derecho se resuelve en P.5.

### Continuidad del mueble Home U2-P.5 (2026-09-07)

En escritorio el mueble se prolonga entre 72 y 112 px fuera del borde derecho de
`homeView`; el contenedor recorta ese excedente y el poste terminal del raster queda
fuera de cuadro. El asset completo se escala como una sola pieza, preservando el
registro entre marco, estante y consola. No repetir una franja ni fabricar una unión.

El carril de categorías compensa el excedente: conserva márgenes operables dentro del
viewport y permite llevar el último lomo completamente a la vista. No hay scroll
horizontal de página. En móvil continúa la composición apilada sin este sobreancho.
P.5 no reordena la consola ni cambia su contenido; esa composición pertenece a P.6.

### Consola de ficha breve Home U2-P.6 (2026-09-07)

La franja inferior se lee como una única consola funcional, no como una portada en
miniatura seguida de varios paneles independientes. En escritorio mantiene cuatro
zonas: acciones centradas en la placa izquierda; título/año, tipo, género y sinopsis;
dos marcos de imagen; créditos y estado resumido. El antiguo panel lateral «Ficha
detalle» desaparece y VHS queda como firma visual pequeña dentro del bloque de estado.

Los marcos sólo muestran `backdrop_image` y `page_image` reales. Ante ausencia o error
de carga conservan su lugar y muestran un fallback técnico «Sin imagen»; nunca se
inventa una imagen factual. Créditos usan dirección, guion y reparto; estado resume
acceso, estado personal y duración. Los valores extensos se eliden visualmente en la
consola compacta, conservan el valor completo como `title` y siguen disponibles en la
ficha. IBM Plex Mono gobierna todo este nivel.

En móvil el orden pasa a título/datos/sinopsis, dos imágenes 16:9, créditos/estado y
acciones. Los botones mantienen 44 px mínimos y el contenido no produce scroll
horizontal de página. No reinstalar miniportada, carrusel o panel de formato separado.

### Ajustes de aceptación Home U2-P.7 (elección del 2026-09-08)

El usuario eligió **1A / 2A / 3A**. En móvil el preview compartido se acopla debajo
de la categoría activa; al cambiar de estante se mueve con la selección y al volver a
desktop regresa a la consola fija. No duplicar fichas, estado ni IDs. Los listeners del
carril deben ignorar eventos que nacen dentro del preview acoplado.

La consola desktop usa la mayor altura disponible dentro de su bahía material: comienza
en 68,25 % y ocupa 21 % del mueble. La placa de acciones acompaña esa expansión. No se
reduce ni reescala el estante de lomos. Créditos y estado suben a 11 px; a 860 px o menos
usan 12 px y admiten salto de línea. A 360 px o menos pasan a una sola columna.

La separación conceptual queda visible con los nombres `Cartelera disponible` y
`Videoteca · Tu archivo por categoría`. La región inferior toma su nombre accesible de
Videoteca y el rótulo desaparece junto con el mueble cuando no hay categorías.

### Integración material Home U4 (dirección elegida el 2026-09-09)

La dirección visual U4 reemplaza la pared de ladrillo por una consola semiilustrada de
metal oscuro, latón contenido, serigrafía, biseles y sombras internas. Cyan y magenta son
reflejos o señales funcionales, no focos del fondo. La opción B original es una referencia
valorada, pero sus dos implementaciones fueron rechazadas el 2026-09-09; ninguna es una
base visual aprobada.

Las ventilaciones y leyendas `Archivo / Películas / Memoria` y
`Rebobinar / Explorar / Conservar` son detalles decorativos aprobados; no obligan a una
columna lateral independiente. Su soporte puede cambiar para mejorar la composición.
Los rieles deben continuar fuera del borde derecho en cada ancho desktop. Fondo, marco,
placas y lomos comparten escala de grano, luz, desgaste y profundidad de contacto.

La elección entre assets y CSS sigue abierta: se permite material raster elaborado y
segmentado cuando aporta el volumen de la referencia. Retirar el ruido no implica
eliminar textura, espesor ni identidad VHS. Texto y controles siguen siendo HTML.
La nueva comparación vive en `docs/design/u4-2-options-v2/`; U4.3–U4.5 implementarán
las uniones de cartelera, estante y ficha dentro de la composición que se elija.

**Dirección de trabajo, 2026-09-09:** el owner autorizó desarrollar la videoteca
empotrada: fondo y frente como un material continuo, con aberturas hacia adentro.
El plan y la referencia aportada están en `docs/design/u4-2-inset-library-plan.md`.
La B inicial deja de ser la topología de trabajo. El owner aprobó el acabado U4.2a el
2026-09-10. `docs/design/u4-2a-material-kit-v1/` entrega un kit compuesto de CSS y
fuentes RGB, no PNG transparentes. El owner aprobó el encuentro U4.2b en
`docs/design/u4-2b-integrated-junction-v1/` y pidió ampliar la playlist. U4.2c integra
esa base en Home mediante `home-inset.css` + `home-material.css`, reemplazando los
imports de la antigua carcasa. U4.2 espera la revisión visual de esta integración.
La textura pertenece al frente común; los bordes sólo añaden el espesor
de las aberturas, sin fondos exteriores opacos de cada módulo. La geometría de esquina
y la luz se mantienen al variar el tamaño; los textos y controles siguen vivos.

La playlist desktop tiene altura natural: seis filas completas de al menos 38 px,
texto de 13 px, sin scroll interno en 1280, 1440 y 1920. La abertura superior tiene
mínimo 484 px; no se comprime la Home entera para hacerla caber en 720 px de alto.
El frente llega a 1680 px útiles (main de 1744 px con padding lateral de 32 px).
El estante se prolonga hasta el borde derecho del viewport; su piso y retorno se
calculan desde la altura del VHS, no desde la scrollbar. Hasta 860 px se conserva
el reflow existente, con scroll local de tablas/lomos y sin overflow de la página.

**Reencuadre propuesto U4.2d.1, 2026-09-10 — todavía aislado:** el owner cuestionó
la salida unilateral y las dos consolas. `docs/design/u4-2d-1-composition/` compara
la base productiva anterior con un frente centrado de hasta 2240 px, margen fluido,
dos retornos finos y estante desplazable dentro de la abertura. Conserva las seis
filas y los VHS de 308 px; oculta el panel inferior sólo en la muestra. No cambia
material ni fuentes. U4.2d.2 conectará filas/lomos a la consola superior sin alterar
la programación; d.3 consolidará contenido y retirará el componente inferior real.
U4.3 pulirá la consola resultante; el antiguo alcance de U4.5 queda absorbido allí.
La propuesta no sustituye las reglas productivas hasta su aceptación e integración.

**U4.2d.2 implementada, 2026-09-11:** la consulta superior se identifica por origen
y clave, independiente de la programación de filas y de la rotación del póster.
Seleccionar un VHS cambia la consulta, no esas dos fuentes. La selección explícita
de fila toma prioridad; Hoy/Ayer y activación explícita conservan su semántica.
Club mantiene su detalle sin edición personal. El componente inferior permanece
transitoriamente hasta d.3; no se considera la consola única consolidada todavía.
Evidencia: `docs/design/u4-2d-2-selection.md`.

**U4.2d.3 integrada, 2026-09-11:** el frente productivo ahora comparte ancho centrado
de hasta 2240 px; la estantería desplaza su contenido dentro de dos retornos finos.
Se retiraron el host y el renderizador inferiores. La única consola superior reúne
contexto/origen, acciones de ficha y categoría, título, sinopsis, dos imágenes,
créditos, acceso, estado y duración. Sustituye la onda decorativa y miniportada;
no cambia las seis filas ni los VHS de 308 px. El marco del póster mantiene 436 px
de altura para no deformarse por la densidad de los créditos. En móvil la consola
se apila; la playlist y cada rail tienen desplazamiento local. Impeccable guió
la agrupación por significado y la comprobación de densidad/extremos.
El laboratorio d.1 ya no ofrece una comparación «Anterior» basada en CSS actual:
sus capturas conservan la historia. Evidencia actual: `docs/design/u4-2d-3-evidence/`.
Aceptación visual del owner el 2026-09-12; sigue U4.3 para pulido material de esta consola.

**Evolución planificada, 2026-09-12 — todavía sin implementación:** U5 revisa el
gesto anterior de selección: elegir un VHS deberá cambiar la lista a su conjunto,
manteniendo la cartelera Hoy/Ayer independiente. U6 agrega una cartelera derecha
para la consulta; se estudia simetría/ancho antes de congelar la retícula U4.3.
U7 investiga los dos espacios de imágenes de la consola y U8 un lomo terminal «Al azar»,
apagado y con «?» decorativo sólo si el resultado no está disponible. U9 prevé
sonido opcional de foco; MW1 deja la revisión mobile web al final, con Kotlin prioritario.
Estas decisiones de comportamiento son futuras: el renderer actual todavía sigue d.2/d.3.
Plan y elecciones pendientes: `docs/design/home-evolution-backlog-2026-09-12.md`.

### Estudio conjunto U4.3 / U6.1 / U7.5 — 2026-09-12

**Afinación U4.4, 2026-09-13:** placas unidas al travesaño continuo, VHS a 2 px
de la base sin levantarse en hover ni selección. Sombras cortas y desgaste contenido
preservan el material existente. Selección magenta con indicador de forma; foco
cyan en lomo o placa, sin enmarcar el módulo completo. Las imágenes mantienen
reserva y estados 0/1/2; «Revisar imágenes en ficha» abre dossier personal o ficha
compartida según origen. El owner separó U7.5a visual de U7.5b datos/galería.
Evidencia y límites del gate U4.6: `docs/design/u4-4-visual-gate/README.md`.

Comparador aislado en `docs/design/u4-3-u6-1-u7-5/`: A aloja consola en el centro;
B usa una franja común dentro de la abertura superior. Ambas conservan dos marcos
simétricos, seis filas y una única consola; ninguna repone el panel bajo la biblioteca.
B fue elegida e integrada en la Home real (cierre técnico 2026-09-13). El material
y las tipografías aprobadas se conservan; datos y acciones comparten una sola base.
Derecha deriva de la consulta, izquierda conserva su programación. Los diálogos
pausan la rotación para preservar el foco de retorno. La lista aún sigue el contrato
d.2/d.3; el cambio automático de fuente espera U5.

Imágenes desde campos actuales: cero muestra ausencia, una ocupa el espacio conjunto,
dos URLs distintas ocupan dos ventanas. Carga/error reservan geometría y no bloquean
la ficha. Corrección y procedencia persistidas esperan el contrato U7. Evidencia:
`docs/design/u4-3-b-integration/`.

Contenido confirmado: preferir dos imágenes distintas de la misma obra, permitiendo
panorámica + portada aunque esa portada esté a la derecha. Si falta material se puede
repetir una imagen como fallback de presentación; nunca contarlo como dos assets.

**Ajuste del owner, 2026-09-24:** la consola de consulta pasa a una etiqueta en tres
columnas (opción A): contexto y «Ver colección» en una línea sobre el título, año ·
tipo · género · duración, sinopsis a tres líneas; créditos con la etiqueta sobre el
valor (sólo los que tienen dato); acceso y estado como sellos separados, y «Ver más» /
«Editar mi ficha» a la derecha. Sale la tira de imágenes de la consola, con «Revisar
imágenes en ficha» y el sello VHS: la portada ya vive en el marco «En consulta».
El rótulo `Videoteca · Tu archivo por categoría` deja de verse en escritorio (sigue
como nombre accesible y visible en móvil) y los VHS suben de 308 a 348 px. La
contratapa de «Ver más» se muestra sola sobre el fondo difuminado, sin marco ni
barra: un toque fuera de la caja la cierra y «Cerrar» sólo se dibuja como X con
foco de teclado.

**U8 — VHS «Al azar», 2026-09-26:** la biblioteca termina en una bahía propia (no
cuenta como sección editorial) con placa «AL AZAR», el alcance vigente («Disponibles»
o «Todo») y un único lomo con el mismo material. Estados: inicial «Elegir una obra»;
ocupado «Eligiendo…» con `aria-busy`; disponible con título y año reales; no
disponible con caja apagada y «?» tenue decorativo detrás de un título legible; fuera
de alcance y sin obras con una nota breve y salida («Elegir otra», «Incluir no
disponibles», «Abrir colección»). Sólo se mueve la etiqueta: A rebobina el rótulo
420 ms y asienta el resultado en 260 ms; B pasa títulos reales ocultos a lectores
de pantalla. Movimiento reducido muestra el resultado directo; un solo anuncio final.

**Display Font:** Arial Narrow (con Trebuchet MS como fallback)
**Body Font:** Space Grotesk (con Trebuchet MS, Verdana y system-ui como fallbacks)
**Label/Mono Font:** Courier New

**Character:** la tipografía condensada e itálica aporta energía de afiche y carátula; el cuerpo geométrico mantiene lectura operativa; la monoespaciada introduce lenguaje de señal, inventario y etiqueta técnica.

### Hierarchy
- **Display** (900, fluida, 0.95): marca y encabezados verdaderamente principales.
- **Feature** (900, fluida, 0.88): títulos cinematográficos dentro del spotlight.
- **Title** (900, 24px base, 1.12): títulos de obra; debe reducirse por longitud sin cortar palabras.
- **Body** (400, 16px, 1.5): controles, párrafos y contenido de trabajo.
- **Label** (800, 10px, tracking amplio, uppercase): metadata, kicker, estados y microcopy técnico.

**The Condensed Display Rule.** La tipografía condensada, itálica y en mayúsculas pertenece a marca, títulos de obra y momentos cinematográficos; nunca usarla para párrafos, formularios largos o instrucciones.

## Layout

El contenido vive dentro de un contenedor de hasta 1500px, con márgenes laterales generosos en escritorio y compactos en móvil. La búsqueda se organiza como una consola horizontal; la colección usa una grilla autoajustable de cajas con proporción 2:3 y separación flexible.

La densidad cambia en 1100px, 860px, 640px y 440px. A partir de 640px la cabecera se apila, el spotlight adopta una proporción más alta, su selector de recomendaciones se desplaza horizontalmente, la colección mantiene dos columnas y la ficha ocupa el viewport completo. Los objetos de formato fijo deben conservar proporciones y tracks estables para que títulos, badges y estados no desplacen la composición.

La complejidad administrativa usa divulgación progresiva. En `Colección`, estado, disponibilidad y tipo permanecen visibles; director, género, década, rango de años, fuente y memoria personal viven en `Más filtros`. Los chips activos son la lectura humana del estado enlazable. Filtros cotidianos, métricas y mantenimiento pueden compartir el lenguaje visual, pero no deben competir dentro del mismo momento de decisión.

## Elevation & Depth

El sistema es plano por defecto y táctil cuando representa un objeto. Paneles, formularios y navegación se separan mediante tono, borde y jerarquía; cajas, spotlight, menús flotantes y ficha reciben sombras estructurales que comunican material, superposición o apertura.

### Shadow Vocabulary
- **Header Signal:** `0 12px 36px rgba(0,0,0,.34), 0 1px 22px rgba(255,62,165,.12)` para separar la cabecera sin convertirla en una card.
- **Spotlight Lift:** `0 20px 44px rgba(0,0,0,.32)` para sostener la marquesina cinematográfica.
- **DVD Case:** `0 14px 28px rgba(0,0,0,.4), -2px 0 13px rgba(120,92,255,.12)` para expresar carcasa y lomo.
- **Utility Overlay:** `0 18px 44px rgba(0,0,0,.52), 0 0 24px rgba(120,92,255,.12)` para menús que flotan sobre la colección.
- **Detail Dossier:** `0 28px 90px rgba(0,0,0,.72), 0 0 34px rgba(34,216,229,.16)` para la ficha modal.

**The Tactile Object Rule.** Las sombras y transformaciones pertenecen a objetos materiales, overlays y cambios de estado; las secciones operativas normales no deben flotar como cards decorativas.

## Shapes

Los controles operativos usan esquinas pequeñas y rectas. Los resultados genéricos pueden abrirse levemente, mientras que las cajas de DVD conservan una silueta asimétrica con lomo marcado. La forma totalmente redondeada se reserva para chips y estados compactos.

Los bordes son finos, violetas o cyan según contexto. Las barras laterales de color indican estado o jerarquía funcional, no ornamentación. Evitar cards dentro de cards y contenedores redondeados alrededor de cada sección.

## Components

### Buttons
- **Shape:** rectos y compactos, con radio mínimo.
- **Primary:** Playhead Pink o su gradiente, texto claro y peso alto; una acción primaria por contexto.
- **Hover / Focus:** hover más profundo o ligeramente atenuado; foco cyan de 3px con offset visible.
- **Quiet:** superficie azul oscura para salir, limpiar o ejecutar acciones secundarias.

### Chips
- **Style:** píldora pequeña con borde de señal y texto compacto.
- **State:** cyan para confirmación, dorado para advertencia o puntuación y neutro para metadata.

### Cards / Containers
- **Corner Style:** las cajas usan silueta asimétrica; paneles operativos no deben imitar esa forma.
- **Background:** portada o fallback expresivo al frente; ficha técnica oscura al reverso.
- **Shadow Strategy:** sólo la caja material recibe elevación permanente.
- **Internal Padding:** compacto y estable para proteger la proporción 2:3.

### Inputs / Fields
- **Style:** fondo profundo, borde violeta-gris, radio mínimo y altura consistente.
- **Focus:** outline cyan visible, sin depender sólo de cambios de color.
- **Error / Disabled:** advertencia dorada para problemas recuperables; menor contraste para deshabilitado sin perder legibilidad.

### Navigation
- `Inicio`, `Colección`, `Bandeja` y `Club` forman el único grupo de navegación primaria. El estado activo usa tinta cyan y un relleno tonal.
- `Al azar` es un comando dorado separado de los destinos; su alcance vive dentro del menú de cuenta junto con preferencias y administración. En móvil, las cuatro vistas ocupan la barra inferior y las utilidades permanecen en la cabecera.
- El rosa de acción usa tinta `ink-on-signal`; nunca texto blanco sobre Playhead Pink para tamaños normales.

### Spotlight
- Marquesina panorámica con imagen real, gradientes de legibilidad, título condensado y CTA magenta. Debe poder pausarse y reducir protagonismo cuando el usuario entra en una tarea operativa.

### DVD Case
- Componente firma con proporción 2:3, lomo, brillo, sticker y reverso técnico. El flip comunica exploración en dispositivos con hover; el acceso a detalle no puede depender exclusivamente de esa interacción.

### Detail Dossier
- Ficha amplia y jerárquica con portada, identidad de la obra, estados personales, sinopsis y secciones técnicas progresivas. En móvil ocupa el viewport completo y mantiene una salida persistente.

## Do's and Don'ts

### Do:
- **Do** usar Playhead Pink, CRT Cyan, Tape Violet y Rental Sticker Gold con roles semánticos estables.
- **Do** mantener controles técnicos, portadas táctiles y jerarquía personal en cada nueva superficie.
- **Do** preservar la proporción 2:3, el lomo y la materialidad de las cajas cuando se represente una obra.
- **Do** revelar metadata, fuentes y mantenimiento mediante divulgación progresiva.
- **Do** verificar títulos largos, dos columnas móviles, foco visible y reducción de movimiento.

### Don't:
- **Don't** convertir Movie Inbox en un dashboard SaaS genérico de cards redondeadas.
- **Don't** copiar la composición, navegación o lenguaje visual de Netflix.
- **Don't** reemplazar el mundo nocturno por minimalismo pálido, neutro o excesivamente aireado.
- **Don't** usar sombras, gradientes o neón sin una función de jerarquía, material o estado.
- **Don't** ocultar disponibilidad, intención de ver y memoria personal detrás de metadata externa.
