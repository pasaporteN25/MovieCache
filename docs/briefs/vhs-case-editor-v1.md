# Caja VHS y edición por tareas

THESIS: Colección se recorre como cajas de videoclub; consultar una contratapa y editar son pasos explícitos.
OWN-WORLD: Caja negra gastada, cinta crema con fibrón, petróleo y metal del Inicio. Sticker Movie Inbox con VHS, cigarrillo y humo de película.
STORY: Acercar la caja, leer el reverso, tocar Editar ficha y encontrar un grupo de campos.
FIRST VIEWPORT: Portada completa y datos debajo; al acercarse, la caja crece proporcionalmente un 4,5% sin mover la grilla ni ocultar datos. Editor con navegación lateral y guardar fijo.
FORM: Dirección y muestras aprobadas por Lucas el 2026-09-28; sin sorteo. Fondo fotográfico diferido por pedido explícito.

## Entrega
- Caja: imagen sin recorte, cinta adicional sobre portada real conservada pero inactiva; fallback negro con cinta grande. Mouse y teclado equivalentes, toque abre directamente. Movimiento reducido sin animación.
- Contratapa: las cinco identidades comparten título, sinopsis, imagen junto a datos/créditos y memoria; quitar metadatos duplicados del encabezado; sticker algo menor que la muestra, en espacio propio, abre edición del catálogo personal.
- Marca: originales PNG transparentes y tamaños derivados, guardados en el proyecto.
- Editor: Mi registro, Datos de la obra, Imágenes, Disponibilidad y enlaces; Opciones avanzadas separadas. Formularios persistentes al navegar; guardar todos los cambios; protección al salir; permisos del Club sin cambios.
- Validar conservación de borradores entre secciones, guardado, conflicto, vuelta y foco; revisar escritorio y móvil.

## Pendiente deliberado
La imagen ambiental del primer mockup de edición se resolverá al final en otra iteración, similar pero distinta. Por ahora se usa el fondo petróleo existente.

## Retoque visual — 2026-09-29

Datos y créditos comparten columna de dos tercios junto a la imagen. En contenedores
menores a 400 px se apilan para no comprimir las etiquetas. Los créditos vacíos
muestran una sola nota. Sinopsis al 96% del tamaño base, con mínimo de 11 px.
El contenido completo conserva scroll cuando hace falta: recortar 5/6 líneas,
«Leer más/menos», detección de desborde y restauración de foco quedan pendientes
como interacción separada. No simular ese comportamiento ocultando contenido.

La variante `.collection-zoom-title` permanece en `core/card.js` y en
`css/vhs-experience.css`, sin selectores que la activen. No confundir con la cinta
activa de `.dvd-placeholder`. Su reactivación requiere una nueva decisión visual.
