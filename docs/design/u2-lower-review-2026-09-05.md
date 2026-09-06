# U2: revisión inferior y hoja de ruta

Fecha: 2026-09-05. Revisión del árbol de trabajo actual, incluidos cambios sin commit. No se modificó la interfaz ni el estado del backlog.

Método: dos evaluaciones independientes (design_review y detector_evidence), más comprobación visual e interacción en navegador local con catálogo sintético. Referencia: boceto aportado por el usuario y brief de recuperación vigente. La cabecera corregida se conserva.

## Diagnóstico

U2 está cerrada como base técnica; la aceptación visual sigue pendiente en U2-R. El mueble continuo, las acciones inferiores y la contratapa determinista ya existen. La sensación de trabajo incompleto proviene sobre todo de la pérdida de lectura y de una selección defectuosa, no de falta de assets.

R.4n y R.5 figuran terminadas, pero R.6 (móvil) y R.7 (aceptación integral) siguen pendientes. Conviene incorporar los siguientes fixes correctivos antes de R.7, preservando la historia del trabajo realizado.

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
- [ ] Tarea 5: recuperación móvil de R.6.
- [ ] Tarea 6: gate integral R.7 y actualización final de contratos.

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

- **Lomos:** a 1280×720 el título dispone de aproximadamente **7,94 px de alto**, mientras la metadata vertical consume **72 px**. Causa: `core-vhs.css:12` distribuye `5px minmax(0, 1fr) auto`; la metadata de `core-vhs.css:41` desplaza al título cuando `home.css:1804` comprime el lomo. La captura muestra letras amputadas. El espacio entre lomos ya es pequeño (5–8 px); reducirlo no corrige la causa.
- **Selección:** pulsar directamente una obra de `Tu archivo pide memoria` mantiene la ficha de `Disponible esta noche`. El foco llega al lomo pulsado, pero su `aria-pressed` sigue falso. `home.js:546` recuerda el índice sin cambiar `activeHomeSectionId`; `home.js:846` renderiza la categoría anterior. `bootstrap.js:20` procesa solo el control más cercano.
- **Consola (diagnóstico previo):** el display medía aproximadamente **55 / 72 / 88 px de alto** a 1280×720, 1440×900 y 1920×1080. La cascada ocultaba la sinopsis en los tres tamaños y reducía metadata/hechos a **8/7 px**. A 720p también desaparecían hechos y placeholders, y los botones bajaban a 20 px de alto. La geometría exterior entraba, pero el contenido perdía utilidad.
- **Móvil:** la nueva estructura sigue dentro de una grilla de **100 px + 209 px**: acciones a la izquierda y toda portada/ficha a la derecha. Se verificó además la marca fragmentada verticalmente en la cabecera. La restauración móvil continúa siendo trabajo real pendiente.
- **Contenido (diagnóstico previo):** `home.js` priorizaba `reason.detail` sobre la
  sinopsis. La corrección aplicada reserva ese valor como último fallback detrás de la
  descripción y el extracto.
- **Lo que funciona:** `Ver más` abre la contratapa con sinopsis, créditos y dos espacios de fotograma; Escape devuelve el foco al botón de origen. El mueble es un único asset, con títulos en HTML y acciones doradas a la izquierda. Hay pruebas existentes de teclado, permisos, overflow y ausencia de escrituras al explorar.

## Decisiones de contrato

1. **Relación con la lista superior:** recomendado mantener la selección de lomos independiente y actualizar solo la ficha inferior. Alternativa: sincronizar ambas. El código reciente separa selección, pero activar el contenedor aún cambia la playlist y el brief exige sincronización. Unificar contrato y tests tras decidir; no revertir automáticamente lo corregido arriba.
2. **Categorías (resuelta 2026-09-06):** se recuperan placas pequeñas por grupo,
   conservando el mueble continuo y el rótulo activo inferior. El espacio deja de actuar
   como única separación, y los grupos cortos pasan a dimensionarse por su contenido.

Para la primera decisión se adoptó la recomendación: la selección del lomo actualiza la
categoría y la ficha inferiores sin cambiar la playlist superior. Activar explícitamente
el contenedor conserva la sincronización histórica hasta unificar el contrato en R.7.
La decisión visual sobre categorías adoptó las placas compactas para la tarea 4.

## Alcance y límites de validación

Se inspeccionó la mitad inferior con tres categorías y 18 obras sintéticas, en 1280×720, 1440×900, 1920×1080 y 390×844. El fixture no tenía posters y dejó vacía la cartelera superior; esta revisión no certifica el encuadre de una home completa con seis funciones. No se usaron catálogos personales.

El detector sobre `index.home.html` devolvió cero hallazgos; ese escaneo no cubre el CSS/JS externo y no invalida los defectos visuales. No se ejecutaron suites completas, pruebas de lector de pantalla, touch real ni zoom: quedan para el gate. Las pruebas existentes de geometría no verifican suficiente lectura interna y la de selección activa el módulo antes del lomo, omitiendo el fallo reproducido.

No se asigna una nota global de usabilidad con cobertura parcial. La revisión independiente valoró positivamente identidad/materialidad y detectó problemas de reconocimiento, jerarquía y respuesta a la selección. Usuario habitual: no puede leer títulos; baja visión: microtexto; primera visita: ficha de una obra distinta a la elegida.

No hubo overlay inyectado: la API disponible admite evaluación de DOM de solo lectura. Se usaron capturas y mediciones directas. Pestañas temporales cerradas y viewport restaurado; servidor de revisión detenido al entregar. Snapshot de revisión asociado al target `src-movie-inbox-web-static-index-home-html`; no se encontró lista de exclusiones.

Fuera de esta entrega: nuevas texturas, animación vertical de cartelera, fotogramas reales, U3/Colección y rediseño móvil completo. Los placeholders de fotogramas son una decisión aceptada, no una integración faltante que deba bloquear el cierre.
