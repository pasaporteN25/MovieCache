# Inicio: estanterías editoriales (U1.2)

- **Modo y trabajo:** explorar una programación personal sin salir de Inicio. Las filas
  no inventan categorías: representan las secciones editoriales existentes y no vacías,
  en el orden que entrega el servidor: `available`, `followed`, `memory`, `route` o
  `recent`, y `anniversary`.
- **Contrato de datos:** cada estantería conserva su título, descripción, acción y
  hasta seis entradas de `/api/items`; el orden estable, el motivo de cada entrada y el
  destino `Catálogo` o `Club` ya pertenecen a `EditorialHomeService`. Una fila vacía no
  se muestra y no se agregan rutas, filtros ni consultas nuevas.
- **Tesis visual:** una tira horizontal de etiquetas compactas deja ver el conjunto;
  elegir una revela debajo una ficha breve con portada, motivo, año, dirección/género y
  una acción explícita para abrir el detalle correcto. Es una aproximación estructural
  a una estantería de videoclub; los activos y la caja VHS reutilizable siguen siendo
  U1.3.
- **Interacción y límites:** cada fila tiene un único punto de Tab con selección
  roving. Flechas izquierda/derecha y Home/End recorren las opciones; clic o Enter
  actualizan la ficha y mantienen el foco. La acción de cabecera conserva el destino
  editorial existente. En móvil, la tira hace scroll táctil horizontal y la ficha queda
  debajo; con `prefers-reduced-motion` no se requiere animación.
- **Fuera de alcance:** no se cambia el selector principal U1.1, el detalle, las
  acciones de Club, la semántica de disponibilidad ni se implementa todavía un componente
  VHS/asset definitivo.
