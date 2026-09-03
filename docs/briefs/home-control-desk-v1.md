# Mostrador de control (U2.0)

## Alcance de esta entrega

U2.0 resuelve únicamente la **arquitectura de información** de la cabecera compartida:
qué botones son destinos, cuáles son utilidades y cómo se agrupan, antes de que U2.1
reemplace visualmente la cabecera por el escenario del videoclub. No toca la cartelera
ni las estanterías inferiores de Inicio; esas son U2.1 y U2.2.

## Destinos y utilidades

- **Destinos** (`.primary-nav`, sin cambios): `Inicio`, `Colección`, `Bandeja`, `Club`.
  Conservan sus IDs, rutas, atajos y estado activo existentes.
- **Utilidades** (`.header-utilities`), en orden: `Buscar`, `Agregar`, `Al azar`,
  `Usuario`. `Al azar` y `Usuario` (`#systemMenu`) ya existían y no cambian de
  comportamiento; `Buscar` y `Agregar` son nuevas y quedan documentadas acá porque no
  tenían home global previo.

## `Buscar`

Navega a `Colección` (mismo destino que el botón de navegación) y además mueve el foco
al campo `#query`, listo para escribir. Reusa `resetCollectionFilters`,
`clearManualSearch` y `syncRoute` ya existentes; no agrega una ruta ni un modo nuevo.

## `Agregar`

**Decisión del owner, 2026-09-02.** Hoy no existe una entrada global para crear una
obra manualmente: esa creación vive dentro del flujo de Bandeja/Scanner, atada a un
archivo detectado, y no es lo que este botón debe abrir. La intención de producto es
que `Agregar` termine siendo "buscar para agregar a mi colección" con una superficie de
búsqueda propia, separada de examinar la colección — lo que a su vez implica repensar
`Colección` (que hoy mezcla buscador, filtros y grilla en una sola vista densa) para que
sólo muestre la colección, probablemente con una transición parecida a la de las
estanterías VHS.

Ese rediseño de `Colección`/búsqueda es una tarea aparte, todavía sin numerar, y queda
fuera de U2. Por ahora, `Agregar` **navega a `Colección`** igual que el botón de
navegación (`goToCollectionRoot`), sin foco especial en el buscador ni un modo nuevo.
Es una redirección interina, no la superficie final; su rótulo y agrupación junto a
`Buscar` ya dejan lista la arquitectura para cuando ese rediseño exista.

## Fuera de alcance

- No se cambia `/api/home` ni ningún otro contrato editorial.
- No se toca la cartelera de Inicio ni las estanterías (U2.1/U2.2).
- No se rediseña `Colección` ni su buscador (tarea futura, ver arriba).
- El acomodo de `Al azar` respecto al menú de cuenta que ya describe `DESIGN.md` es una
  discrepancia preexistente entre diseño e implementación; U2.0 no la resuelve porque no
  es parte de lo que esta entrega pidió mover.

## Accesibilidad

- `Buscar` y `Agregar` son botones nativos con texto visible (no sólo ícono), heredan el
  tamaño táctil de 44px en móvil y el foco visible cyan del resto de la app.
- El orden de tabulación queda: destinos (`Inicio` → `Colección` → `Bandeja` → `Club`) y
  luego utilidades (`Buscar` → `Agregar` → `Al azar` → `Usuario`), sin trampas de foco.
- No dependen de hover; funcionan igual con teclado, puntero y touch.
