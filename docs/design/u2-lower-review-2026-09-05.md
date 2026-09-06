# U2: revisión inferior y hoja de ruta

Fecha: 2026-09-05. Revisión del árbol de trabajo original, actualizada con las correcciones
aplicadas por partes hasta el 2026-09-06.

Método: dos evaluaciones independientes (design_review y detector_evidence), más comprobación visual e interacción en navegador local con catálogo sintético. Referencia: boceto aportado por el usuario y brief de recuperación vigente. La cabecera corregida se conserva.

## Diagnóstico

U2-R quedó aceptada el 2026-09-06. El mueble continuo, las acciones inferiores y la
contratapa determinista conservan su identidad; los defectos originales de lectura,
selección, altura útil y flujo móvil fueron corregidos sin reemplazar el sistema por una
composición genérica.

R.4n, R.5, R.6 y el gate integral R.7 están terminados. Los fixes correctivos se
incorporaron en el orden siguiente, preservando la historia del trabajo.

## Orden de implementación sugerido

| Orden | Prioridad | Tarea acotada | Criterio de aceptación |
| --- | --- | --- | --- |
| 1 | P1 | Reparar lectura de lomos. Reservar la mayor parte del alto al título; llevar año y señal de formato a un pie compacto. Ajustar ancho/alto sin deformar el shell. | A 1280×720 se reconoce cada título; ningún bloque queda reducido a una franja de letras cortadas. Títulos largos mantienen identidad legible y nombre accesible completo. |
| 2 | P1 | Corregir selección directa de otra categoría. Activar la categoría inferior y recordar su obra en el mismo gesto. | Click o Enter en cualquier lomo visible actualiza selección y ficha inferior a esa obra, sin exigir click previo en el hueco del módulo. |
| 3 | P1 | Dar altura útil a la consola inferior y redistribuir su contenido. Reducir primero espacio decorativo; evitar encajar mediante microtexto u ocultación sistemática. | Título, año, dirección y sinopsis breve legibles en los tres tamaños desktop; acciones sin recortes. Metadata principal propuesta de 12 px o más. Zoom/altura insuficiente permiten flujo vertical. |
| 4 | P2 | Resolver orientación y espacios entre categorías. Comparar carteles pequeños por grupo con rótulo de categoría activa; ajustar mínimos de ancho para grupos cortos. | Se entiende qué grupo se explora y que el recorrido continúa; una categoría con pocas obras no genera un hueco desproporcionado. |
| 5 | P1 | Completar R.6: recomponer la ficha móvil con sus nuevos contenedores y revisar cabecera. | A 390×844, portada, título, sinopsis y acciones tienen un flujo legible. La marca no se parte en una columna de fragmentos y no tapa la exploración. |
| 6 | Cierre | Ejecutar R.7 después de estos fixes y actualizar los contratos escritos. | Comparación visual con boceto, teclado, touch, zoom, permisos y estados vacíos; no cerrar únicamente por tests verdes. |

Primera entrega recomendada: tarea 1 solamente. Revisar su resultado visual antes de pasar a la siguiente. No hace falta rediseñar toda la home de nuevo.

## Estado de aplicación

- [x] Tarea 1: lectura de lomos corregida y verificada en los tres tamaños desktop.
- [x] Tarea 2: selección directa corregida para click y Enter, manteniendo independiente
  la playlist superior.
- [x] Tarea 3: altura útil y legibilidad de la consola inferior.
- [x] Tarea 4: orientación y espacios entre categorías.
- [x] Tarea 5: recuperación móvil de R.6.
- [x] Tarea 6: gate integral R.7 y actualización final de contratos.

## Evidencia comprobada

- **Consola corregida:** el mueble conserva una altura útil de **640 / 640 / 700 px** y
  la pantalla central mide aproximadamente **114 / 114 / 124 px** a 1280×720,
  1440×900 y 1920×1080. Título, año, dirección y sinopsis de dos líneas permanecen
  visibles; metadata y sinopsis computan 12 px, las acciones miden al menos 36 px y no
  desbordan su panel. A 720p la página usa flujo vertical en vez de comprimir el mueble.
- **Prioridad de contenido:** la ficha inferior usa primero la descripción propia,
  después el extracto de Wikipedia y deja el motivo editorial como último fallback.
  Los placeholders decorativos del poster ceden su texto cuando el panel es compacto.
- **Categorías corregidas:** cada grupo desktop muestra una placa con nombre y cantidad
  de títulos, mientras la consola conserva el rótulo de categoría activa. Los grupos de
  una o dos obras miden **192–220 px** en vez de forzar 460–680 px; el espacio entre
  grupos queda en **20–36 px**. Los controles aparecen sólo si hay overflow real y
  reflejan los límites del recorrido. Las placas permanecen ocultas visualmente en móvil.
- **Móvil corregido:** a **390×844** la cabecera baja de aproximadamente **338 px** a
  **168 px** y la marca pasa de una columna de **75 px** a una línea útil de **336 px**.
  La preview deja la grilla exterior de 100 px + resto: display y acciones se apilan,
  mientras portada y texto usan **92 px + 212 px** dentro de la ficha. La sinopsis
  computa **15/21,75 px**, los botones miden **44 px**, el fondo inferior permite
  desplazarlos por encima de la navegación fija y no aparece overflow horizontal.
  Una portada rota revela el placeholder propio; una carga válida lo oculta. La variante
  personal conserva dos acciones y la del Club sólo su acción pública.
- **Gate visual integral:** una home sintética de seis funciones y cuatro categorías se
  comparó en 1280×720, 1440×900 y 1920×1080. No hay overflow horizontal; la escena
  completa entra en 1080p y las alturas menores usan flujo vertical sin comprimir la
  consola. Capturas y mediciones: `u2-r7a-visual-gate-2026-09-06.md`.
- **Estados e interacción:** vacío, 1/2/4 categorías, contenido extenso, posters
  ausentes/rotos, permisos personal/Club, cinco contratapas, click, Enter, flechas,
  temporizador, retorno de foco, touch real, nombres accesibles y reduced motion quedaron
  cubiertos. Matrices: `u2-r7b-content-state-matrix-2026-09-06.md` y
  `u2-r7c-interaction-accessibility-gate-2026-09-06.md`.

### Hallazgos originales, resueltos

- **Lomos:** a 1280×720 el título dispone de aproximadamente **7,94 px de alto**, mientras la metadata vertical consume **72 px**. Causa: `core-vhs.css:12` distribuye `5px minmax(0, 1fr) auto`; la metadata de `core-vhs.css:41` desplaza al título cuando `home.css:1804` comprime el lomo. La captura muestra letras amputadas. El espacio entre lomos ya es pequeño (5–8 px); reducirlo no corrige la causa.
- **Selección:** pulsar directamente una obra de `Tu archivo pide memoria` mantiene la ficha de `Disponible esta noche`. El foco llega al lomo pulsado, pero su `aria-pressed` sigue falso. `home.js:546` recuerda el índice sin cambiar `activeHomeSectionId`; `home.js:846` renderiza la categoría anterior. `bootstrap.js:20` procesa solo el control más cercano.
- **Consola (diagnóstico previo):** el display medía aproximadamente **55 / 72 / 88 px de alto** a 1280×720, 1440×900 y 1920×1080. La cascada ocultaba la sinopsis en los tres tamaños y reducía metadata/hechos a **8/7 px**. A 720p también desaparecían hechos y placeholders, y los botones bajaban a 20 px de alto. La geometría exterior entraba, pero el contenido perdía utilidad.
- **Móvil (diagnóstico previo):** la estructura quedaba dentro de una grilla de
  **100 px + 209 px**, con acciones a la izquierda y toda portada/ficha a la derecha;
  la marca también aparecía fragmentada verticalmente. La corrección R.6 elimina ambos
  defectos sin trasladar el mueble material de desktop al breakpoint móvil.
- **Contenido (diagnóstico previo):** `home.js` priorizaba `reason.detail` sobre la
  sinopsis. La corrección aplicada reserva ese valor como último fallback detrás de la
  descripción y el extracto.
- **Lo que funciona:** `Ver más` abre la contratapa con sinopsis, créditos y dos espacios de fotograma; Escape devuelve el foco al botón de origen. El mueble es un único asset, con títulos en HTML y acciones doradas a la izquierda. Hay pruebas existentes de teclado, permisos, overflow y ausencia de escrituras al explorar.

## Decisiones de contrato

1. **Relación con la lista superior:** recomendado mantener la selección de lomos independiente y actualizar solo la ficha inferior. Alternativa: sincronizar ambas. El código reciente separa selección, pero activar el contenedor aún cambia la playlist y el brief exige sincronización. Unificar contrato y tests tras decidir; no revertir automáticamente lo corregido arriba.
2. **Categorías (resuelta 2026-09-06):** se recuperan placas pequeñas por grupo,
   conservando el mueble continuo y el rótulo activo inferior. El espacio deja de actuar
   como única separación, y los grupos cortos pasan a dimensionarse por su contenido.

La decisión final conserva dos gestos distintos: seleccionar un lomo actualiza la
categoría y la ficha inferiores sin cambiar la playlist superior; activar explícitamente
el contenedor reprograma la playlist con esa estantería y recupera su lomo recordado. El
brief y las pruebas ya describen el mismo contrato. La decisión visual sobre categorías
adoptó las placas compactas para la tarea 4.

## Alcance y límites de validación

La aceptación final usó una home sintética completa con seis funciones, hasta cuatro
categorías, contenido extenso y posters válidos, ausentes o rotos. Se midieron
1280×720, 1440×900, 1920×1080, 390×844 y 320×720. No se usaron catálogos personales.

El gate recorrió el árbol accesible calculado por Chromium mediante roles y nombres,
foco visible, teclado, un contexto táctil real y `prefers-reduced-motion`. Esto cierra la
cobertura automatizable de U2-R; una campaña manual exhaustiva con NVDA/VoiceOver sigue
siendo una mejora de release y no se presenta como ejecutada.

El detector de `impeccable` sobre todo `src/movie_inbox/web/static` informó 146 avisos
consultivos de documentación de color/tipografía y un warning. El warning `side-tab` fue
verificado como falso positivo: corresponde al triángulo del selector de cartelera, no
a un borde lateral de tarjeta. No quedaron hallazgos P0/P1. El score integral se mantiene
en **17/20 — Muy bueno**.

La regresión final ejecutó 560 pruebas generales y 31 de navegador; Ruff, formato, mypy
estricto, `compileall`, sintaxis de 26 módulos JavaScript y `git diff --check` quedaron
verdes. Cuatro smoke tests TMDB se omitieron porque requieren un token voluntario real.
El primer pase completo expuso una carrera de prueba entre el error de red real de un
poster y un evento sintético de carga; se estabilizó esperando el estado de error antes
de verificar el recovery y la suite completa volvió a verde.

Fuera de esta entrega: nuevas texturas, animación vertical de cartelera, fotogramas reales, U3/Colección y rediseño móvil completo. Los placeholders de fotogramas son una decisión aceptada, no una integración faltante que deba bloquear el cierre.
