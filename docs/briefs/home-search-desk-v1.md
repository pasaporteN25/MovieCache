# IP1/IP2 — Inicio como mostrador de búsqueda

Dirección elegida por el owner el 2026-10-26 (concepto B), todavía sin implementar.
Modo: Operate. Reemplaza la cabecera de Inicio descrita en
`home-cartelera-winamp-v1.md` y redefine IP1 e IP2 del análisis
`docs/analisis/inicio-busqueda-club-personas-2026-10-21.md` (§2.1 y §2.2). El modelo
de personas (IP3 a IP6) no cambia.

## Trabajo y audiencia

La persona llega a Inicio con un título en la cabeza, a menudo después de buscarlo en
Google. Hoy tiene que ir a Colección y escribirlo otra vez. Inicio no tiene campo de
texto y repite la misma obra tres veces: el póster izquierdo, la fila 01 y el póster
derecho. El objetivo es pasar de «pensé en una película» a «ya está en mi archivo», o
a saber que ya la tenía, en pocos segundos y sin salir de Inicio cuando la coincidencia
es exacta. Para todo lo demás, el buscador ofrece ampliar hacia Colección.

## Dirección

Mostrador con un solo póster. Se conserva el mundo material de Home (petróleo, metal,
placas, VHS) y su DESIGN.md. Sólo cambia la composición de la cabecera.

- **Mitad superior.** A la izquierda, el buscador como pieza del mueble. A la derecha,
  un único marco de póster (el actual «Tu selección»). El póster muestra el resultado
  resaltado y, sin búsqueda activa, la sugerencia del día. Sigue siendo el destino de
  Al azar (U8) y de las consultas de Club y VHS.
- **Mitad inferior.** El estante VHS, como hoy.
- **Se quitan:** el carrusel «Hoy/Ayer en cartel» con su autoplay, la tabla de
  programación tipo Winamp y la tabla de Hoy/Ayer. La programación diaria sobrevive
  como fuente de las sugerencias. Las instantáneas de Hoy/Ayer
  (`infrastructure/home_snapshot_repository.py`) se conservan sin migrar.

## Interacción

**Campo vacío con foco.** Debajo del campo se abre un panel con dos grupos:
«Recientes», con las últimas 5 búsquedas, borrables una por una o todas, y
«Sugerencias», con 3 a 5 obras: disponibles esta noche, de la programación del día y
faltantes de colecciones seguidas.

**Escribiendo.** El desplegable agrupa:

1. **En tu colección.** Búsqueda local inmediata.
2. **Para agregar.** Los 3 primeros resultados externos. Aparecen cuando la escritura
   se detiene, a partir de 3 caracteres, con la fuente rotulada.
3. **Personas.** Sólo cuando exista IP3. Hasta entonces no se muestra el grupo.

Cada fila externa lleva uno de tres estados:

- **Ya la tenés.** Abre la obra en Movie Inbox.
- **+ Pendiente.** Sólo cuando el servidor responde que la obra falta y no detecta
  duplicados posibles. Agrega como pendiente sin salir de Inicio.
- **Revisar.** Ante cualquier coincidencia dudosa. Abre Colección en modo agregar con
  la consulta y el comparador de U12. Nunca agrega desde Inicio.

Las flechas mueven la selección y el póster la sigue. Enter sobre una fila ejecuta su
acción. El pie del desplegable dice «Ampliar en Colección (N)». Enter sin fila
seleccionada amplía, es decir, navega a `?view=catalog&mode=add&q=…`, y Atrás vuelve a
Inicio con la consulta. Escape cierra el desplegable y devuelve el póster a la
sugerencia del día. `/` enfoca el buscador desde cualquier vista.

**Pegar un enlace.** Una URL de una fuente que `domain/search.py` ya reconoce
(Wikipedia, IMDb, FilmAffinity, MyAnimeList o TMDb, según
`EXTERNAL_LINK_HOSTS` en `domain/catalog.py`) devuelve un único resultado identificado
por su id, con los mismos tres estados. Wikidata y Letterboxd no están en esa lista.
Sumarlos es una decisión aparte.

## Reglas que no se rompen

- El desplegable no tiene matching propio. Consume el mismo endpoint de U12 con un
  límite chico. Si el servidor responde `review` o `possible_duplicate`, la fila dice
  «Revisar».
- «+ Pendiente» escribe por el mismo camino que Colección (`catalog_membership` y
  matching conservador). Agregar como pendiente nunca toca `en_catalogo`.
- «Disponible» describe el inventario físico, y «Pendiente» y «Vista» describen el
  estado personal. Nunca se presentan como intercambiables.
- Las búsquedas recientes son personales y nunca aparecen en Club ni en vistas
  compartidas.

## Estados y rangos

- **Catálogo vacío.** El buscador hace de bienvenida («Buscá la primera película que
  querés recordar»), sin sugerencias ni estantes vacíos.
- **Sin resultados.** Ofrece «Ampliar en Colección» y la opción de pegar un enlace.
- **Fuente externa caída o lenta.** La búsqueda local sigue. La fuente muestra su
  aviso sin bloquear el resto.
- **Sin imagen.** El póster muestra la placa tipográfica que ya existe para obras sin
  portada.
- **Títulos largos y obras de 0 a 3 resultados por grupo.** Ningún grupo vacío ocupa
  lugar.
- **Móvil.** El campo ocupa todo el ancho arriba. El póster se oculta mientras se
  escribe y el desplegable ocupa la pantalla. Sin scroll lateral a 320 px.
- **Teclado y lector de pantalla.** Patrón combobox con etiqueta visible, grupos
  anunciados y foco estable. Movimiento reducido: el póster cambia sin transición.

## Decisiones abiertas

| Decisión | Propuesta |
| --- | --- |
| Dónde se guardan las búsquedas recientes | En el servidor, por usuario, para que también le sirvan al cliente Android. La alternativa es `localStorage` |
| Costo de las fuentes externas mientras se escribe | Mínimo 3 caracteres, pausa de escritura y caché de respuestas. Medir contra los límites de Wikipedia e IMDb |
| Botones «Buscar» y «Agregar» de la cabecera global | «Agregar» sigue llevando a Colección. «Buscar» enfoca el campo cuando ya estás en Inicio |
| Sumar Wikidata o Letterboxd al pegado de enlaces | Fuera de esta entrega |

## Entrega

1. **IP1 — Mostrador con un solo póster.** Quitar el carrusel, el autoplay y la tabla
   de programación. Estante VHS en la mitad inferior. La programación queda como
   fuente de sugerencias. Actualizar PRODUCT.md («entre una y cuatro obras») y
   DESIGN.md.
2. **IP2 — Buscador con desplegable y ampliación.** Panel de recientes y sugerencias,
   grupos de resultados, los tres estados, pegado de enlaces y ampliación hacia
   Colección.
3. Pruebas: actualizar, sin borrarlas, `tests/js/home-selection.test.mjs`,
   `tests/browser/test_ui_browser.py`, `tests/browser/test_home_random.py` y
   `tests/browser/home_*_metrics.js`. Agregar pruebas de navegador para Enter
   (amplía), Atrás (vuelve con la consulta), «Revisar» (nunca agrega) y pegado de
   enlace. Revisión visual a 390, 1280, 1440 y 1920 px. Reabre el gate visual de
   Inicio aceptado en U4/U6.

No incluye el modelo de personas ni un matching nuevo.
