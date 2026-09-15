# Home — evolución del archivo visual

2026-09-12. Plan de producto y diseño; avance de integración al 2026-09-13. El tablero ejecutable
está en `tareas.md`. Modo: Operate, con exploración de la biblioteca personal.
Se preservan el frente empotrado, material petróleo/latón, tipografía acordada,
VHS con títulos HTML y la consola única aceptada en U4.2d.3.

## Decisiones y lectura del pedido

El owner acepta visualmente d.3 y pide seis frentes de evolución:

| Épica | Resultado | Prioridad en el frente visual |
| --- | --- | --- |
| U5 | La lista Winamp sigue el conjunto del VHS seleccionado | Próximo cambio de comportamiento de Home |
| U6 | Segunda cartelera a la derecha para la obra consultada | Diseñar composición junto con U5 |
| U7 | Completar los dos espacios de imágenes de la consola con imágenes de la obra | Investigación de cobertura antes de ampliar el contrato |
| U8 | Un VHS especial «Al azar» al final de la biblioteca, con revelación animada | Después de definir selección y composición |
| U9 | Sonido opcional al enfocar un VHS, fácilmente silenciable | Posterior, prescindible para las demás épicas |
| MW1 | Revisar la web desde navegadores de celular y corregir lo necesario | Última prioridad; Android/Kotlin por delante |

Confirmado por el owner durante esta planificación:

- Izquierda conserva programación/rotación Hoy/Ayer; derecha muestra la obra consultada.
- Elegir un VHS cambia automáticamente la lista al conjunto de su estante.
- Los placeholders del pedido son los **dos espacios de imágenes de la consola**.
- El VHS al azar se apaga y muestra «?» tenue **si el resultado no está disponible**,
  no por el solo hecho de desactivar «Al azar solo entre disponibles».

Precisión resuelta el 2026-09-13:

| Decisión | Recomendación | Alternativa | Afecta |
| --- | --- | --- | --- |
| Apertura al terminar el sorteo | **Confirmado:** revelar VHS y actualizar consulta/derecha; ficha sólo mediante Ver más | Descartada: abrir ficha automáticamente después de revelar | U8.1/U8.5 |

La revelación sin apertura automática queda confirmada. La elección del efecto
U8.4 sigue pendiente de comparar muestras. Corte v0.9.0 y subdivisión ejecutable:
`home-v0-9-0-u5-u8-plan.md`; ese documento actualiza la secuencia histórica siguiente.

**Contenido de imágenes confirmado el 2026-09-12:** preferir dos imágenes distintas
de la misma obra; pueden ser panorámica + portada, aunque la portada también esté en
la cartelera derecha. Si falta material se permite repetir la única imagen disponible.
La repetición es un fallback de presentación, no dos assets distintos ni cobertura
adicional. No se buscan imágenes de otra obra para llenar el hueco. U7.1–U7.4 ya
incluyen investigación de proveedores/API; no abrir una épica duplicada.

**Corte conjunto U4.3/U6.1/U7.5, actualizado 2026-09-13:** B elegida e integrada
en la Home real; U6.1 cerrada y U4.3 implementada. Comparador histórico en
`docs/design/u4-3-u6-1-u7-5/`; evidencia actual en `docs/design/u4-3-b-integration/`.
U7.5 integra 0/1/2 imágenes y estados de carga/error usando los campos existentes;
procedencia y corrección persistida siguen pendientes de U7.2–4. U5 conserva su
implementación pendiente. No declara completas las épicas U6/U7.

## Historia que cambia, sin borrar lo anterior

`docs/design/u2-lower-review-2026-09-05.md`, «Decisiones de contrato», conserva la
elección anterior: un lomo cambia la consulta y sólo activar la categoría reprograma
la tabla. U4.2d.2 mantuvo esa distinción al compartir la consola superior.
Por eso no hay que restaurar toda una versión vieja: existe ya `playlistSource`,
la tabla admite fuentes de estante y `activateHomeShelf()` recupera su selección.
U5 revisa el gesto que cambia esa fuente. Los cierres U2-R/d.2 siguen siendo válidos
para su alcance y fecha; sus tests se deben adaptar al contrato nuevo, no omitir.

La programación automática, la fuente de lista y la consulta siguen siendo conceptos
distintos. El nuevo gesto coordina lista y consulta, sin acoplarlas al autoplay.

## Orden y dependencias

U4.3/U4.4/U4.6 conservan el pulido pendiente. Antes de congelar la retícula de U4.3,
conviene hacer U6.1 (estudio de espacio) junto con U5.1 (contrato de interacción).
Esto evita pulir una zona que deba recomponerse inmediatamente. Es una dependencia
de diseño; no declara implementadas U5/U6 ni habilita a cerrar U4 por anticipado.

Secuencia propuesta dentro de Home:

1. U5.1 + U6.1: estados y comparación de espacio con la base aceptada.
2. Resolver el encaje con U4.3; mantener U4.4 y su materialidad de VHS/placas.
3. U5.2–U5.5: lista sincronizada y retorno explícito a Hoy/Ayer.
4. U6.2–U6.5: composición elegida, portada consultada y validación.
5. U7.1–U7.2 pueden investigarse mientras el diseño anterior se resuelve; su
   implementación sólo empieza con contrato de imágenes/identidad definido.
6. U8: integra el sorteo con la consulta existente; U9 después de la interacción estable.
7. MW1 al final del backlog: recibe la Home final, sin competir con el cliente Kotlin.

Cada épica puede entregar su propia comparación/fixture; no hace falta un framework
nuevo. HTML/CSS/JS modular resuelven composición y efectos. Python se necesita para
identidad, adquisición de imágenes, contratos persistentes o sorteo de catálogo completo.

## U5 — Lista Winamp del conjunto seleccionado

**Trabajo:** explorar un estante viendo sus obras también en la lista superior,
con la misma selección en lomo, fila, consola y cartelera derecha.

| Gesto | Fuente de lista | Consulta / derecha | Cartelera izquierda |
| --- | --- | --- | --- |
| Clic/tap en un VHS | Conjunto de ese estante | Ese VHS | Conserva programación y rotación |
| Flecha sobre VHS dentro del conjunto | Mismo conjunto | VHS alcanzado | Conserva programación y rotación |
| Activar placa/categoría | Su conjunto | Selección recordada válida, o primera obra | Conserva programación y rotación |
| Flecha/clic en fila | Fuente actual | Esa fila, sincronizada al lomo si corresponde | Conserva programación y rotación |
| Autoplay izquierdo | Conserva fuente actual | Conserva consulta | Avanza sólo el póster diario |
| Hoy/Ayer o volver a cartelera diaria | Jornada elegida | Primera selección válida de esa jornada | Jornada elegida |
| Elegir explícitamente el póster izquierdo | Jornada mostrada | Obra del póster | Conserva jornada |
| Sortear desde módulo especial | A definir en U8.1; recomendado no sustituir la lista por todo el catálogo | Resultado único del sorteo | Conserva programación |

«Conjunto» significa las obras pertenecientes a la sección mostrada, no resultados
inferidos por título. U5.1 comprobará si son todas sus obras o una muestra editorial
acotada: la lista debe identificar ese alcance, sin anunciar que muestra el catálogo
completo de un director cuando sólo recibió seis propuestas. Club sigue separado.

- **U5.1 — Contrato y recorrido.** Distinguir foco pasivo de selección: Tab no cambia
  la fuente; clic/tap y navegación con flechas del rail sí seleccionan. Definir
  activación de placa visible mediante control semántico y retorno diario. Dibujar
  recorrido VHS → fila → consulta y estados de fuente vacía/removida. Auditar el límite
  editorial y decidir rótulo «Selección de…» si la lista es una muestra. Salida: matriz
  confirmada y fixture de dos conjuntos con claves coincidentes de distinto origen.
- **U5.2 — Coordinación de estado.** Reutilizar `playlistSource`, `selectionSource`,
  `selectedEntryKey` y selección recordada por estante. Actualizar el gesto en
  `home.js`, preservando carrusel independiente; evitar reinicios del temporizador
  causados sólo por consultar. Si la obra desaparece, resolver dentro del mismo
  conjunto primero; si desaparece el conjunto, retorno diario explícito y aviso breve.
- **U5.3 — Fuente y navegación visibles.** Cabecera de tabla con nombre de conjunto,
  cantidad/alcance y retorno a Hoy/Ayer. Nada depende de enfocar un contenedor oculto.
  Más de seis entradas: decidir scroll local o «Mostrar más» sin agrandar toda la Home;
  seis entradas diarias siguen completas. Evitar scroll del documento al seleccionar.
- **U5.4 — Teclado, permisos y escala.** Mantener roving focus, selección de fila/lomo,
  anuncios únicos y retorno de diálogos. La ausencia de un lomo visible no invalida
  una fila del conjunto. Club muestra detalle compartido y no edición personal.
- **U5.5 — Gate.** Pruebas de transiciones entre fuentes, autoplay, Hoy/Ayer, posterior
  eliminación de obra, conjuntos vacíos y 1/6/20/100 entradas. Migrar las aserciones
  antiguas que exigen que un clic en VHS deje la lista diaria; conservar las que
  prueban independencia del póster. Comparación visual de cabecera y selección.

**Cierre:** un VHS elegido aparece seleccionado en la lista de su conjunto; el usuario
identifica de inmediato qué está viendo y cómo volver a la jornada. Rotación y Club
no producen consultas cruzadas. No cambia metadata ni preferencias personales.

## U6 — Dos carteleras en una composición simétrica

**Trabajo:** izquierda propone; derecha confirma visualmente la obra que se consulta.
Dos marcos no implican dos consolas ni dos carruseles automáticos.

La composición candidata es `cartelera diaria | lista + consola | cartelera consultada`.
Los dos marcos comparten tamaño, nivel, luz, material y profundidad. La derecha usa
una placa como «EN CONSULTA», su título en contenido accesible y portada real;
el texto definitivo de placa se evalúa en U6.1. No promete «HOY» para una obra ajena
a la programación diaria. Si ambas obras coinciden, se permite la misma portada:
los roles son distintos y las placas lo explican.

Con medidas actuales, sólo marcos (274×2), separación (16×2) y tabla mínima (760)
suman **1340 px**, antes de biseles/padding. No entran en el interior disponible a
1280. Es aritmética de CSS actual, no una validación de prototipo futuro.

- **U6.1 — Estudio de composición.** Comparar a 1280×720, 1440×900, 1920×1080 y
  2482×1254: A) marcos pares más estrechos, centro amplio; B) marcos actuales en grande,
  compactos en intermedio con columnas secundarias progresivas. Hacer visible título,
  año y selección; director/géneros/duración pueden pasar a ficha/resumen cuando
  falta ancho. Medir nombres largos y ancho de la consola con créditos completos.
  Proponer umbral por espacio disponible, sin escalar toda la página ni reducir letra
  para encajar. Mostrar mockup/HTML aislado antes de implementación.
- **U6.2 — Contrato de portada consultada.** Derivar obra y origen de la consulta,
  sin crear otra selección independiente. Casos de catálogo, Club y azar; clave
  compuesta por origen. Portada ausente/rota: fallback de la misma obra y estado claro;
  nunca queda visible la portada de la consulta anterior. Sin consulta: marco neutral.
- **U6.3 — Composición y assets.** Adaptar `home-inset.css`/`home-material.css` y
  renderer de Home. Primero reutilizar marco y bezel aprobados; rehacer o segmentar
  sólo si la ventana no admite el nuevo ancho sin distorsión. Textos y botones HTML.
  La consola ocupa el centro o una franja común según la variante elegida; no reaparece
  el panel inferior. Ambas portadas completas, sin recorte accidental por simetría.
- **U6.4 — Interacción y carga.** La derecha se actualiza con la consulta; no autoplay
  propio. Recomendado clic en portada derecha abre la misma ficha que «Ver más»;
  mantener acciones de Club. Carga visible prioritaria y cancelación/ignorancia de
  respuestas de obra anterior; transición corta sin retrasar selección ni acciones.
- **U6.5 — Gate.** Capturas de roles distintos/iguales, Club, largo, vacío y error de
  imagen en cada ancho. Seis filas completas donde se conserve el contrato desktop,
  controles legibles y foco sin salto. Probar zoom 200% con reflujo. En ancho insuficiente
  se documenta la composición adaptada; el gate profundo de celular pertenece a MW1.

**Cierre:** ambas carteleras forman el frente aceptado, el centro sigue legible y la
derecha representa exactamente la consulta. U4.3 recibe el encaje elegido.

## U7 — Imágenes reales para los dos espacios de consola

**Trabajo:** que la obra tenga una presencia visual rica sin llenar huecos con imágenes
ajenas ni contenido inventado. Preferir dos imágenes distintas; repetir una sola
queda permitido cuando no hay alternativa de la misma obra.

Base existente: `page_image` y `backdrop_image` en esquema/repositorios; el adaptador
TMDB ya devuelve poster/backdrop; `ImageCacheWarmer.register_items()` encola ambos
y el proxy valida hosts y acota bytes/cache. **Calentar una URL no descubre una imagen
faltante**: separar adquisición de metadata, selección visual y descarga/cache.
Los espacios de la contratapa son hoy placeholders distintos; este pedido no extiende
automáticamente U7 a esa superficie. Se puede reutilizar el contrato después.

- **U7.1 — Auditoría de cobertura.** Medir con fixture y, sólo cuando se tome la tarea,
  un diagnóstico local de conteos agregados: sin portada, sin panorámica, una/dos
  imágenes distintas, URLs rotas, identidad confirmada/ambigua. Segmentar cine,
  series, anime/documentales y Club. No descargar todo el catálogo para medir.
  Entregar causas: campo vacío, URL mala, cache frío, error de proveedor o falta real.
- **U7.2 — Estrategia de adquisición.** Evaluar primero proveedor ya configurado y
  TMDB `/movie/{id}/images` o `/tv/{id}/images` sobre identidad confirmada. Su API
  aporta backdrops/posters/logos; un backdrop no es necesariamente un fotograma:
  rótulo «Imagen de la obra» salvo procedencia suficiente. Comparar cobertura,
  calidad, idioma, imágenes sin texto y coste/latencia con muestra pequeña.
  Respetar imágenes corregidas/bloqueadas y matching conservador. Sin identidad fuerte,
  proponer candidata para revisión en vez de elegir por título parecido.
- **U7.3 — Contrato portable y autoridad.** Si se eligen dos panorámicas, los dos
  escalares actuales no bastan: diseñar una lista acotada de assets con ID estable,
  URL, rol, dimensiones, proveedor, origen/atribución, idioma y selección manual.
  Versionar esquema/intercambio y soporte JSON/SQLite/API; mantener los escalares
  legados para compatibilidad y no obligar al cliente Kotlin a leer campos exclusivos
  del DOM. Definir autoridad de imagen y metadatos de atribución por asset. Responsabilidad
  principal de lógica/datos; el frente visual especifica consumo/estados.
- **U7.4 — Resolver y cache.** Orden estable: elección manual válida → assets existentes
  de esa identidad → consulta acotada a proveedor configurado. Priorizar obra consultada,
  límites/reintentos/backoff y respuestas obsoletas. Dedupe por asset/ruta canónica;
  no basta una URL de distinto tamaño para considerar imágenes distintas. Si no hay
  dos imágenes, no fabricar un segundo asset: el renderer puede repetir el único
  disponible como fallback autorizado, sin contarlo como dos imágenes distintas.
  Tokens y descarga quedan en servidor.
- **U7.5 — Integración visual y corrección.** Marco con dimensiones reservadas, carga,
  error, una imagen y ninguna. Recomendado, si sólo hay una imagen, usar el espacio
  conjunto para esa imagen en vez de agrandar un cartel vacío; comparar con mantener
  dos ventanas antes de fijar el comportamiento. El comparador incluye además repetir
  la imagen disponible, permitido por el owner. Corrección desde la ficha existente,
  con preview, procedencia y bloqueo cuando el contrato lo soporte. `Ver más` siempre
  disponible; errores de proveedor no vacían la consulta.
- **U7.6 — Gate de identidad/cobertura.** Misma obra con títulos traducidos, remake del
  mismo título, película/serie homónima, anime sin TMDB, Club, imagen borrada y offline.
  Probar compatibilidad de intercambio, cache acotado y no sobrescritura de selección
  manual. Reportar mejora de cobertura por causa, no prometer 100% de imágenes.

**Investigación externa verificada 2026-09-12:** TMDB entrega múltiples imágenes por
obra y tamaños/configuración; exige atribución, logo aprobado y aviso en Acerca de/Créditos.
No equivale a que todas las imágenes sean de dominio público. Incorporar las atribuciones
existentes y revisar condiciones del uso concreto al desarrollar; no bloquear la propuesta
visual por no tener todavía un token de proveedor.
[Imágenes de películas](https://developer.themoviedb.org/reference/movie-images),
[imágenes de series](https://developer.themoviedb.org/reference/tv-series-images),
[tamaños](https://developer.themoviedb.org/docs/image-basics),
[atribución](https://developer.themoviedb.org/docs/faq).

## U8 — Un VHS «Al azar» al final del archivo

**Trabajo:** transformar el comando existente en un objeto reconocible del mueble,
que revele una obra real y permita repetir el sorteo.

Categoría especial terminal, después de todas las secciones editoriales presentes.
Un único lomo reutilizable, placa «AL AZAR» y gesto explícito «Otro al azar»;
es un módulo de comando, no una colección persistida ni un conjunto de películas
inventadas. El botón de cabecera/menú y el lomo llaman al mismo sorteo.

- **U8.1 — Alcance y recorrido.** Auditar `randomCandidates()` y `openRandomDetail()`:
  hoy el comando abre ficha, usa filtros de Colección cuando hay resultados, y en Home
  usa `items`. Confirmar que incluye todo el catálogo personal y no sólo la página
  cargada; si no, pasar el sorteo al servicio con filtros explícitos. Propuesta: Home
  sortea catálogo personal completo, sujeto a disponibilidad, independiente del estante
  activo; Colección conserva su alcance visible o lo documenta sin fallback silencioso.
  Club no entra sin copiar una obra al catálogo. Definir tratamiento de listas vacías.
- **U8.2 — Objeto y estados visuales.** Comparar lomo neutral inicial, ocupado,
  resultado disponible, resultado no disponible y sin candidatos. Título/año real al
  finalizar, misma altura/ancho y material del VHS existente. El apagado afecta tinta/
  material secundario; título y foco mantienen contraste. «?» tenue es decorativo,
  con texto semántico «No disponible» para evitar que parezca identidad desconocida.
- **U8.3 — Sorteo compartido.** Separar resultado de su presentación; elegir una sola
  vez por acción y usar el mismo ID en lomo, consola, derecha y ficha. Evitar repetición
  inmediata si hay más de un candidato; con uno, permitirlo. Definir uniformidad sobre
  candidatos y comprobar disponibilidad efectiva según la regla acordada. Si el switch
  pasa a sólo disponibles con un resultado no disponible, no conservarlo como elegible:
  marcar fuera de alcance y ofrecer sortear de nuevo, sin sorteo oculto al cambiar preferencia.
- **U8.4 — Revelación animada.** Prototipar A) rebobinado de etiqueta detrás de la caja,
  B) reemplazo por una tira breve de títulos. Recomendación A: consistente con el VHS,
  más legible y sin apariencia de casino. Duración tentativa 450–700 ms a validar;
  resultado elegido antes del efecto, títulos intermedios decorativos y ocultos al
  lector de pantalla. Clics repetidos coalescen/cancelan según contrato; nunca dos
  resultados finales distintos. Reduced motion: revelación directa, sin espera.
- **U8.5 — Integración/foco.** Botón global desde Home lleva al módulo terminal y
  revela sin perder referencia; reducir movimiento también afecta scroll programático.
  Foco permanece en un control estable. La consola y derecha muestran el resultado;
  la tabla conserva el conjunto salvo decisión explícita de U8.1. La apertura final
  de ficha se confirma con el owner. Fuera de Home, mantener comando usable sin
  obligar a navegar a la biblioteca. Un único anuncio al revelar, no por cada letra.
- **U8.6 — Gate.** 0/1/muchos candidatos, sólo disponibles/todo, resultado disponible/
  no disponible, cambio de switch, obra eliminada, clic rápido, teclado, autoplay
  simultáneo, offline y reduced motion. Medir animación sólo del lomo y sin relayout
  de toda la biblioteca. No marcar vista, puntuar, agregar ni editar por sortear.

**Cierre:** el sorteo se entiende y puede repetirse; título y estado representan la
misma obra que se consulta. El color apagado corresponde al resultado no disponible.
La animación puede desactivarse/reducirse. [W3C, animación por interacción](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html)
y [MDN, prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion).

## U9 — Sonido opcional al enfocar un VHS

**Trabajo:** sumar una respuesta breve del objeto, sin convertir recorrer títulos
en una secuencia molesta ni hacer que la información dependa del audio.

- **U9.1 — Diseño sonoro y gesto.** Presentar 2–3 samples originales o con licencia
  libre documentada: contacto de caja, clic mecánico suave, pulso digital contenido.
  Decidir si «onfocus» significa foco de teclado y selección táctil, o también hover;
  recomendado foco intencional, sin sonido por mero cruce del puntero. Volumen/duración
  muy breves y evaluación con auriculares/parlantes. No tomar audio de películas.
- **U9.2 — Preferencia visible.** Interruptor «Sonidos de la biblioteca» al alcance
  desde el menú, apagado por defecto como propuesta; opcional sample de prueba explícito.
  Definir persistencia por navegador o por cuenta/dispositivo. Recomendación dispositivo:
  evita encender sonido en un equipo porque se habilitó en otro. No confundir con el
  switch de disponibilidad del sorteo. Apagar debe cortar cualquier efecto actual.
- **U9.3 — Audio e intención.** Servicio JS pequeño, cargado sólo al habilitar.
  AudioContext inicializado/reanudado por gesto de usuario; el foco por sí solo no
  garantiza desbloquear audio. Silencio correcto si la política del navegador lo bloquea.
  No emitir en carga, autoplay, restauración de foco tras rerender o cierre de ficha.
  Debounce/coalescing para flechas mantenidas; un efecto por cambio intencional,
  sin superponer decenas de instancias. El menú no pide permiso de micrófono.
- **U9.4 — Gate.** Silenciar desde cualquier estado, recargar, almacenamiento bloqueado,
  navegación rápida, lector de pantalla, pestaña oculta, Safari/Chromium y audio suspendido.
  El resto de la interfaz funciona igual sin cargar el sample. Licencia/créditos incluidos.

MDN confirma activación por gesto y control del usuario. Es la razón para planificar
sonido como mejora optativa, sin prometer reproducción automática al primer foco:
[Web Audio, buenas prácticas](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices),
[políticas de autoplay](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay).

## MW1 — Revisión de mobile web, última prioridad

**Trabajo:** usar la web en un navegador de celular con lectura y acciones confiables.
El cliente Android/Kotlin sigue teniendo prioridad para la experiencia vertical principal.
No es un port de escritorio a una app nativa ni una migración PWA.

- **MW1.1 — Medición actual.** Revisar Home, Colección, ficha, Club, Bandeja y menú
  después de las nuevas épicas. 320/360/390/412–430 px y orientación horizontal,
  zoom/texto ampliado. Incluir navegación con barra del navegador visible/oculta,
  teclado virtual y safe areas. Emulación sirve como diagnóstico; validación real
  Android Chrome/iOS Safari se registra por dispositivo/versión, nunca se presume.
- **MW1.2 — Home y biblioteca táctiles.** Definir qué cartelera se prioriza al apilar;
  recomendación consulta cuando hay selección, diaria accesible sin duplicar altura
  permanentemente. Tabla: resumen/columnas progresivas o vista alternativa, con
  control local claro. VHS legibles y selección alcanzable; azar al final sigue descubrible.
  No intentar resolver a 320 px la simetría horizontal de escritorio.
- **MW1.3 — Ficha y utilidades.** Revisar menú completo, salida de diálogos, inputs con
  teclado virtual, botones cubiertos por barras persistentes, scroll interno y retorno
  a la obra. Targets táctiles efectivos, contraste y texto; no contar sólo la caja de
  un checkbox cuando su label amplía el objetivo.
- **MW1.4 — Bandeja / traspaso MB2.** Reutilizar la auditoría del 2026-09-07 como
  antecedente: medía 317/387 px de overflow en 390/320, no como medición vigente.
  Corregir cabecera, pestañas y scope-strip tras volver a medir. Esta tarea absorbe
  el traspaso «Bandeja en el teléfono» de MB2; no crear dos implementaciones paralelas.
- **MW1.5 — Gate y presupuesto.** Smoke reproducible más prueba en teléfono real
  cuando haya dispositivo disponible; informar limitaciones. Sin overflow de documento,
  controles tapables, selección/ficha correctas, teclado no oculta guardar/cancelar y
  preferencias de movimiento/audio respetadas. Arreglos acotados y lista separada de
  mejoras costosas, priorizadas contra Android antes de desarrollarlas.

## Responsabilidades y decisiones que un agente no debe inventar

Visual lleva U5/U6 composición, U7 consumo/estados, U8 objeto/animación, U9 sonido y
MW1 adaptación. Lógica recibe U7 identidad/contrato/adquisición y, si la auditoría lo
exige, U8 sorteo del catálogo completo. Cada traspaso debe incluir payload, estados,
compatibilidad y ejemplos verificables. No depende de asignar ahora otro agente.

Pendientes de elección al desarrollar: variante espacial U6.1, rótulo de derecha,
tratamiento de una sola imagen U7.5, efecto de revelación U8.4 y sample/hover/persistencia
U9.1–U9.2. Son decisiones de prototipo, con opciones concretas a presentar en esas tareas;
no bloquean registrar el backlog ni investigar la cobertura. Las dos preguntas activas
de esta planificación se resolverán con el owner antes de fijar sus recorridos.
