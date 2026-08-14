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
  control-border: "#454c78"
  quiet-control: "#222745"
typography:
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
  body:
    fontFamily: '"Space Grotesk", "Trebuchet MS", Verdana, ui-sans-serif, system-ui, sans-serif'
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0"
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

**The Signal Hierarchy Rule.** Playhead Pink llama a actuar, CRT Cyan confirma y orienta, Rental Sticker Gold destaca valor o excepción y Tape Violet estructura; no intercambiar sus roles por decoración.

## Typography

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
