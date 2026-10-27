# Prompt de implementación — IP1/IP2, Inicio como mostrador de búsqueda

Este archivo es el punto de entrada para el agente que implementa IP1 e IP2. Está
pensado para Sonnet, solo o como orquestador de subagentes. Leelo entero antes de
tocar nada.

---

Sos el agente que implementa IP1 e IP2 de Movie Inbox en la rama
`feature/home-search-desk`, que sale de `release/0.11.0` y vuelve a ella por PR con
merge commit. No crees otras ramas, no fusiones el PR y no toques `master`.

## 0. Antes de empezar (secuencial, obligatorio)

1. Leé, en este orden: `CLAUDE.md`, `AGENTS.md`, `docs/briefs/home-search-desk-v1.md`
   (el brief, que es el contrato de esta entrega), §1.1 y §1.2 de
   `docs/analisis/inicio-busqueda-club-personas-2026-10-21.md`, `PRODUCT.md`, las
   secciones Home de `DESIGN.md`, `tests/test_layering.py` y el frente [IP] al final
   de `tareas.md`.
2. Corré `scripts\check.ps1` (o `bash scripts/check.sh`) y anotá el resultado de
   base. Si algo falla antes de tocar nada, informalo y no lo arregles como parte de
   esta entrega.
3. Las invariantes de `CLAUDE.md` mandan. Si una tarea parece exigir romper alguna
   (matching conservador, `en_catalogo` independiente del estado personal,
   privacidad de Club, layering), pará y preguntá.
4. No uses archivos personales como fixtures (lista en `CLAUDE.md`). Todas las
   pruebas usan datos descartables.

## Contratos fijos

Están definidos acá para que las tareas paralelas no se pisen. No los cambies sin
avisar.

**C1. Pertenencia de resultados externos.** `GET /api/search` acepta
`membership=true` (por defecto `false`, y sin él la respuesta es idéntica a la de
hoy). Con `membership=true`, cada elemento de `results` y de `sources.*.results`
lleva:

```json
"_membership": { "state": "present" | "review" | "missing", "item_id": "<id local>" | null }
```

- `present`: la misma clasificación que hoy da `duplicate` o `strong_match` en
  `CatalogService.append_item` (`application/catalog_service.py:147-177`).
  `item_id` es la obra local.
- `review`: `possible_duplicate_candidates` devuelve candidatas. `item_id` es `null`.
- `missing`: ninguna de las anteriores.
- Es de sólo lectura, no escribe nada y no hace red extra (no llama a
  `enrich_selected_result`).

**C2. Recientes.** En esta entrega se guardan en `localStorage` del navegador, con
la clave `movie-inbox:recent-searches:<username>`. Hasta 5 entradas, sin duplicados
(comparando sin mayúsculas ni acentos), la más nueva primero. Cada lectura y
escritura va en try/catch, y si falla la UI funciona sin recientes. Nunca se mandan
al servidor. Es una decisión provisoria: el brief deja abierto guardarlas en el
servidor más adelante, así que encapsulalas en un módulo con
`list()/add(q)/remove(q)/clear()` para poder cambiar el almacenamiento sin tocar la
UI.

**C3. Integración del buscador con Inicio.** El buscador vive en archivos nuevos y
se comunica con `home.js` sólo por esta interfaz:

- `mountHomeSearch(container, { onPreview(entry | null), onExpand(query) })`, que
  exporta el módulo del buscador.
- `previewHomeEntry(entry | null)`, que exporta `home.js`. Con `null`, el póster
  vuelve a la sugerencia del día.
- `entry` es un objeto con la misma forma que usan los pósters de Inicio hoy
  (título, año, imagen e id local si existe). Si hace falta, adaptalo dentro del
  módulo del buscador.

**C4. Ampliar.** Navega a `?view=catalog&mode=add&q=<consulta>` usando las funciones
de `js/core/router.js` (ver cómo se restaura `mode` en `router.js:240-262`), nunca
armando `location.href` a mano. Atrás vuelve a Inicio.

**C5. Agregar desde el desplegable.** «+ Pendiente» sólo aparece con
`_membership.state === "missing"`. Hace `POST /api/add` con el resultado, igual que
`catalog-search.js:884-905`, y maneja todas las respuestas:

- `added`: la fila pasa a «Agregada».
- `duplicate` o `merged_into_existing`: pasa a «Ya la tenés». Puede pasar, porque
  `/api/add` enriquece y C1 no.
- `possible_duplicate`: pasa a «Revisar» y no reintenta.
- Error: mensaje en la fila y se puede reintentar.

Nunca manda `action: "force"` ni `target_id`. `item_from_search_result` ya deja
`status: "to_watch"` y `en_catalogo: false`, y no hay que cambiarlo.

## Tareas

Las tareas de la misma ola se pueden hacer en paralelo, porque tienen archivos
distintos. Si trabajás con subagentes, asigná a cada uno sólo los archivos de su
tarea. Si un subagente necesita tocar un archivo ajeno, que lo informe en vez de
editarlo. Commiteá una tarea por commit, con mensaje en castellano y estilo
conventional (`feat:`, `test:`, `docs:`).

### Ola 1 (paralelo)

**T1. Backend: pertenencia en la búsqueda (C1).** Modelo sugerido: Sonnet.
- Archivos: `application/catalog_service.py`, `web/routers/search.py`, y
  `web/catalog_api.py` si hace falta un helper. Pruebas en `tests/test_search.py` o
  en un `tests/test_search_membership.py` nuevo.
- Extraé de `append_item` la clasificación (duplicate, strong_match,
  possible_duplicate o ninguna) a una función pura reutilizable, en `application/` o
  en `domain/` si no hace I/O. `append_item` tiene que seguir haciendo exactamente lo
  mismo: las pruebas existentes de alta y duplicados quedan intactas.
- Pruebas: los tres estados con un catálogo sintético; mismo título con otro año da
  `review`; un id externo compartido da `present`; sin `membership` la respuesta es
  igual a la de antes; el catálogo no cambia después de la consulta;
  `test_layering` sigue en verde. No se agrega ninguna regla de matching nueva.

**T2. Backend: pegar un enlace.** Modelo sugerido: Sonnet.
- Archivos: `external/*.py` de las fuentes que haga falta y pruebas con respuestas
  grabadas (`tests/test_search_lab_recorded_responses.py` o similares). Sin red real
  en las pruebas.
- Hoy TMDb y Wikipedia resuelven una URL propia (`intent.source == self.name`).
  Verificá IMDb, FilmAffinity y Jikan. Para cada fuente de `EXTERNAL_LINK_HOSTS`
  (`domain/catalog.py:38`), pegar su URL tiene que devolver un único resultado de
  esa obra, con su URL canónica, para que C1 lo clasifique por id.
- Wikidata y Letterboxd quedan fuera.

**T3. Frontend: IP1, mostrador con un solo póster.** Modelo sugerido: Sonnet.
- Archivos: `web/static/index.home.html`, `web/static/js/surfaces/home.js`, los
  `web/static/css/home*.css` que correspondan y `tests/js/home-selection.test.mjs`.
- Quitá el carrusel izquierdo, el autoplay (`HOME_AUTOPLAY_INTERVAL_MS`,
  `tickHomeAutoplay`, `syncHomeAutoplay`, `handleHomeVisibilityChange` y sus
  llamadas), la tabla de programación tipo Winamp y los controles Hoy/Ayer como
  tabla. Dejá un contenedor vacío a la izquierda (`#homeSearchSlot`) y el único
  póster a la derecha.
- La programación diaria (`editorialHome.featured`) queda como datos. Exportá un
  helper `homeSuggestions(limit = 5)` que devuelva de 3 a 5 entradas sin repetir:
  primero disponibles del día y después faltantes de colecciones seguidas, a partir
  de las secciones que ya llegan.
- Implementá `previewHomeEntry` (C3). Al azar (U8) y las consultas de Club y VHS
  siguen mostrando su obra en el póster.
- El estante VHS queda en la mitad inferior, sin cambios de comportamiento.
- No toques `home_service.py`, los límites del servidor ni las instantáneas de
  Hoy/Ayer.
- Actualizá `home-selection.test.mjs` a la selección sin carrusel: actualizá las
  pruebas, no las borres.
- Visual: seguí las secciones Home de `DESIGN.md`. Si tenés Impeccable, usalo en
  modo refinamiento sobre el mundo existente, no como rediseño.

**T4. Frontend: el buscador (C2, C3, C4, C5).** Modelo sugerido: Sonnet.
- Archivos nuevos: `web/static/js/surfaces/home-search.js`,
  `web/static/js/core/recent-searches.js`, `web/static/css/home-search.css` y
  `tests/js/home-search.test.mjs`. No edita archivos existentes: el enganche es T5.
- Patrón combobox accesible: etiqueta visible, `aria-expanded`,
  `aria-activedescendant`, grupos con nombre y `role="status"` para conteos.
- Campo vacío con foco: grupos «Recientes» (C2, borrables una por una o todas) y
  «Sugerencias». Las sugerencias llegan por parámetro desde `homeSuggestions` y no
  se piden al servidor.
- Escribiendo:
  - «En tu colección»: `GET /api/search?q=…&external=false&catalog=true`, con 150 ms
    de pausa.
  - «Para agregar»: `GET /api/search?q=…&external=true&catalog=false&membership=true`,
    desde 3 caracteres y con 400 ms de pausa. Mostrá los 3 primeros por
    `_search.score`, con la fuente rotulada.
  - Cada tecla aborta las peticiones anteriores (`AbortController`). Si una fuente
    falla, «En tu colección» sigue y se avisa sin bloquear.
- Estados por fila según C1 y C5. «Revisar» y «Ya la tenés» nunca escriben.
  «Ya la tenés» abre la obra local por `item_id`.
- Teclado: flechas mueven y llaman a `onPreview`; Enter ejecuta la acción de la fila
  o, sin fila, llama a `onExpand`; Escape cierra y llama a `onPreview(null)`. La
  consulta se guarda en recientes al ampliar o al ejecutar una acción, no en cada
  tecla.
- Pie: «Ampliar en Colección (N)», donde N suma local y externo.
- Si la consulta es una URL reconocida, el grupo externo muestra el único resultado.
  Podés detectarla en el cliente con la misma lista de hosts que
  `EXTERNAL_LINK_HOSTS`, sólo para cambiar el rótulo.
- Pruebas JS: recientes (tope, deduplicación, fallo de `localStorage`), elección de
  estados, orden por score, armado de URL de ampliación y abort de peticiones
  viejas. Mockeá `fetch`. Mientras T1 no esté listo, mockeá `_membership` según C1.

### Ola 2 (secuencial, después de T3 y T4)

**T5. Integración.** Modelo sugerido: Sonnet.
- Archivos: `home.js` (montaje), `index.home.html` (incluir CSS) y
  `index.shell-open.html` o el JS de la cabecera.
- Montá el buscador en `#homeSearchSlot` con `onPreview → previewHomeEntry` y
  `onExpand → C4`.
- `/` enfoca el buscador desde cualquier vista, salvo cuando el foco ya está en un
  campo de texto.
- En Inicio, el botón «Buscar» de la cabecera enfoca el campo. «Agregar» sigue igual.
- Móvil (≤860 px, `HOME_MOBILE_MEDIA`): el campo ocupa todo el ancho, el póster se
  oculta mientras el desplegable está abierto y el desplegable ocupa la pantalla. Sin
  scroll lateral a 320 px.
- Catálogo vacío: el buscador reemplaza el llamado principal de `#homeEmpty` y deja
  «Importar lista» y «Explorar Club» como acciones secundarias.

### Ola 3 (después de T5)

**T6. Pruebas de navegador y evidencia visual.** Modelo sugerido: Sonnet.
- Actualizá, sin borrar, `tests/browser/test_ui_browser.py`,
  `tests/browser/test_home_random.py`, `tests/browser/home_list_metrics.js` y
  `tests/browser/home_visual_metrics.js`.
- Nuevo `tests/browser/test_home_search.py` con estos casos:
  - Enter sin fila abre Colección en modo agregar con la consulta.
  - Atrás vuelve a Inicio.
  - «Revisar» nunca hace `POST /api/add`.
  - «+ Pendiente» agrega y la fila cambia.
  - `possible_duplicate` convierte la fila en «Revisar».
  - Pegar una URL muestra un único resultado.
  - Escape devuelve el póster a la sugerencia.
  - `/` enfoca el campo.
  - Una fuente caída no rompe el grupo local.
- Capturas a 390, 1280, 1440 y 1920 px en `docs/design/home-search-desk-v1/`, con
  un `README.md` corto como el de `docs/design/search-workbench-v1/`.
- Con Impeccable instalado, corré su detector una vez sobre los archivos de UI
  cambiados y corregí lo que marque.

### Ola 4 (cierre)

**T7. Documentación y gate.** Modelo sugerido: Sonnet, o Haiku si sólo queda
redactar.
- `PRODUCT.md`: reemplazá el párrafo de `Inicio` («entre una y cuatro obras») por la
  descripción del mostrador de búsqueda.
- `DESIGN.md`: agregá una sección «Inicio como mostrador de búsqueda (IP1/IP2)» con
  lo que quedó implementado, no con intenciones.
- `CHANGELOG.md`, en `[Sin publicar]`: entrada para IP1/IP2.
- `tareas.md`: marcá IP1 e IP2 con fecha y commit, sin reescribir secciones ajenas.
- Gate final: `scripts\check.ps1` en verde, la suite de navegador de Inicio en verde
  y `git diff --check` limpio. Pusheá la rama. El PR ya existe y apunta a
  `release/0.11.0`.

## Mapa de paralelismo

| Ola | Tarea | Archivos propios | Depende de |
| --- | --- | --- | --- |
| 1 | T1 | `catalog_service.py`, `routers/search.py`, pruebas de búsqueda | — |
| 1 | T2 | `external/*.py`, pruebas grabadas | — |
| 1 | T3 | `index.home.html`, `home.js`, `home*.css`, `home-selection.test.mjs` | — |
| 1 | T4 | archivos nuevos del buscador y sus pruebas | contrato C1 (mock) |
| 2 | T5 | `home.js`, `index.home.html`, cabecera | T3, T4 |
| 3 | T6 | `tests/browser/*`, `docs/design/home-search-desk-v1/` | T1, T2, T5 |
| 4 | T7 | `PRODUCT.md`, `DESIGN.md`, `CHANGELOG.md`, `tareas.md` | T6 |

Si trabajás solo, seguí el orden T1, T3, T4, T5, T2, T6, T7.

## Qué entregar al final

Un resumen corto con lo que se hizo por tarea (con hash de commit), cualquier
desvío de este prompt o del brief y por qué, lo que no se pudo verificar, y la
salida del gate final.
