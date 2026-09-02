# Inicio: selector editorial fijo (U1.1)

- **Modo y usuario:** operar/explorar. Una persona llega a Inicio para decidir qué ver
  desde su propia programación, no para administrar el catálogo.
- **Tesis:** las recomendaciones del día dejan de ser un carrusel inferior. Forman un
  selector fijo, siempre visible, que gobierna una única ficha panorámica. La lista es
  la navegación; la ficha es el contexto. Las secciones editoriales inferiores no se
  modifican en esta entrega.
- **Interacción:** cada recomendación es un botón nativo con selección roving. Flechas
  verticales u horizontales y Home/End recorren circularmente las opciones; Enter o
  clic actualiza la ficha visible; `Ver ficha` conserva la apertura del dossier. Tab
  entra y sale una sola vez del selector, sin trampas de foco.
- **Estados y límites:** una a cuatro recomendaciones; con una sola sigue existiendo
  una selección clara; sin datos queda el vacío actual. En móvil, la lista aparece
  antes de la ficha y permite scroll táctil horizontal, sin ocultar controles. Carga,
  fecha, errores y navegación principal permanecen intactos.
- **Accesibilidad y alcance:** conserva foco tras cambiar, anuncia el estado con
  `aria-pressed` y no convierte una región estructural en live region. No se agregan
  imágenes, datos, rutas ni acciones públicas; las estanterías VHS y los assets son
  trabajo de U1.2/U1.3.
