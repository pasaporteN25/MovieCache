# FilmAffinity `topics.php` — análisis 2026-10-27

Insumo para decidir; no es un brief ni un ADR. Pedido del owner: sumar al backlog «hacer
algo con la página `topics.php` de FilmAffinity» y traer opciones de implementación.
No se escribió código de producción ni se tocó `tareas.md`: el borrador de entrada está en §9.

Las referencias `archivo:línea` y `archivo` se leyeron en `feature/turban` el 2026-10-27.
Todo lo de la web se midió el mismo día contra el sitio real (ver §1.6 por cuántos pedidos
se hicieron). Lo que no se pudo verificar está marcado **[NO VERIFICADO]**.

---

## 1. Hallazgos

### 1.1 Qué es

`https://www.filmaffinity.com/es/topics.php` es el índice de «Películas por temas» (el
menú del sitio lo llama así). Cada **topic** es una etiqueta temática de la ficha de una
obra («Ajedrez», «Adopción», «Alzheimer», «11-S», «3-D»…). Cada topic tiene su página,
que lista las fichas que llevan esa etiqueta. Hay también `abouttopics.php`, que explica
el origen.

**No son listas de usuarios ni listas ordenadas por un editor.** `abouttopics.php` dice
que el equipo de FilmAffinity asigna los topics a las fichas, que el sitio habla de «más de
400» topics existentes, y que usuarios registrados con antigüedad pueden recibir un permiso
temporal para asignar topics a muchas películas, previa solicitud. Es una **taxonomía
curada por el sitio con colaboradores de confianza**, no un ranking ni una lista de
usuario (las listas de usuario son otra cosa, `listsrank.php`). Esto importa para §4:
la pertenencia a un topic es una afirmación de FilmAffinity sobre una ficha, no una
identidad.

### 1.2 Índice (`topics.php`)

Verificado:

- Una sola página HTML de ~178 KB, sin paginar, con **489 topics** (489 enlaces
  distintos a `movietopic.php?topic=ID`). Responde 200 sin redirección.
- Agrupada por inicial: `<div id="topic_#">`, `topic_A`… con botones de salto.
- Cada topic es un `<a class="btn … topic" href="https://www.filmaffinity.com/es/movietopic.php?topic=149274&nodoc">`
  con el nombre y un `<span class="badge …">133</span>` con la cantidad. La cantidad usa
  punto de miles en español (`4.794`).
- Hay un buscador del lado del cliente («Busca topics / temas»), no una URL de búsqueda.
- `<link rel="alternate" hreflang>` para ~20 variantes de país (`es`, `en`, `mx`, `ar`,
  `us`…). Mismos IDs de topic en todas las variantes (por los `href` de los alternates).
- `og:type` = `website`, `og:url` percent-encoded, sin `<link rel="canonical">`.

### 1.3 Página de un topic (`movietopic.php`)

Probado con «Ajedrez» (`topic=149274`):

- **URL de entrada → redirección.** `movietopic.php?topic=149274&nodoc` responde **303** a
  `…?topic=149274&orderby=avg-desc&chv=grid&nodoc` (orden por nota media descendente,
  vista de pósters), con `cache-control: no-store`. `urllib` sigue la 303 con GET sin
  cookies y llega bien (probado con `curl -L` sin jar de cookies y con `fetch_text`). La
  URL canónica de trabajo es, entonces, la ya redirigida. `nodoc` es un parámetro de
  presentación; su efecto exacto **[NO VERIFICADO]**.
- **Es paginado de a 30 fichas.** `&p=2`, `&p=3`: `<ul class="pagination">` dentro de
  `nav.pager-bs`, enlaces relativos (`movietopic.php?…&p=2`). La página 2 respondió 200 con
  30 fichas, numeradas 31 a 60 (`div.position-grid`). Página 1: 30 fichas, ~160 KB; sirve
  bajo el tope de 800 000 bytes de `fetch_text` (`external/common.py`, `response.read(800_000)`).
- **El conteo del índice no es el listable.** El índice decía 133 para Ajedrez; la página
  dice «Total **63 / 133**» y «Se excluyen Documentales. Consideradas únicamente fichas
  con nota media». O sea: la lista excluye documentales y obras sin nota media. Cuántas de
  las 70 faltantes son documentales y cuántas no tienen nota **[NO VERIFICADO]**. Otros
  `orderby` y filtros además de `avg-desc` **[NO VERIFICADO]**.
- **Tres vistas** (`chv=grid|list|slist`). Los datos que sirven cambian según la vista:
  - `grid`: por ficha sólo `data-movie-id`, `href` a `/es/filmNNN.html`, `title` del
    enlace (con sufijo de tipo: «Gambito de dama (Miniserie de TV)», «El juego de Geri (C)»),
    nota media y póster. **No trae año.** Con un título sin año, la regla conservadora del
    repo manda todo a revisión.
  - `list` (`chv=list`): probada. Por ficha, `div.movie-card[data-movie-id]`, título en
    `div.mc-title > a`, **año** en `span.mc-year`, país (bandera con `alt`), director
    (`div.mc-director`, enlaces a `name.php?name-id=…`) y reparto. Es la vista a usar:
    trae título + año + id + director en un pedido, y `FilmAffinityParser` ya reconoce la
    clase `mc-title` (`external/filmaffinity.py`, `handle_starttag`). Sinopsis y demás
    campos de esa vista **[NO VERIFICADO]** (no se leyeron).
- **IDs de ficha:** `film723978` en `/es/film723978.html`; el mismo número aparece en
  `data-movie-id`. Es el mismo patrón que `_FILM_PATH` (`filmaffinity.py:20`). Que el ID
  de ficha sea idéntico entre variantes de país **[NO VERIFICADO]** (parece, por los
  `hreflang`, pero no se comparó una ficha en dos países).
- Tamaño real: un topic de N fichas listables cuesta `ceil(N/30)` pedidos. «Adolescencia»
  declara 4.794 en el índice: serían ~160 pedidos si todo fuera listable. Por eso hace
  falta un tope (§3).
- Hay un gráfico «Fichas por año» (datos en JS embebido, `chartData`) y «Otros topics
  relacionados» (enlaces a otros topics). Sirven como posible sugerencia de temas
  (opción 3), pero no se parsearon.

### 1.4 Lo que ya hace hoy el repo con estas URL

- `external_source_name` mapea `filmaffinity.com` a `filmaffinity` para **cualquier**
  URL del dominio (`domain/catalog.py`). Pegar una URL de topic en el buscador de Inicio
  entra por `parse_search_query` con `source="filmaffinity"` y `canonical_url` poblado
  (`domain/search.py:79-81`).
- `FilmAffinityAdapter._from_pasted_url` sólo acepta `/xx/filmNNN.html`
  (`filmaffinity.py:20,52-60`); con cualquier otro camino devuelve `[]`. Es decir: **hoy
  pegar una URL de topic no hace nada, en silencio.** Cualquier opción mejora esa
  experiencia mínima.
- Las fichas ya traen topics: `FilmAffinityMetadataParser` documenta que el `<dd>` de
  género «también lista etiquetas de topic más amplias después de un `|` que no cuentan
  como géneros» (`tests/test_external_filmaffinity.py`, comentario sobre `HEAT_FILM_PAGE_HTML`).
  No se leyó una ficha real hoy para ver si esas etiquetas llevan enlace al topic
  **[NO VERIFICADO]**.
- `catalog_membership` (`collection_service.py:58-62`) ya da `present/missing/review` sin
  mirar créditos. Los campos `filmaffinity_url` ya cuentan como enlace externo
  (`domain/catalog.py`, `COVERAGE_LINK_SOURCES`), lo que permite `present` por id
  compartido si [X12] lo trata como id fuerte (confirmarlo al implementar).
- Ya existe un camino de **borradores de importación** (48 h, hasta 20 por usuario,
  vista previa, clasificación y «crear colección local privada» sólo para el owner;
  `application/import_service.py:36-54`, `web/routers/imports.py:131-166`) y un
  precedente de borrador alimentado por otra fuente (el del teléfono,
  `append_device_items`). Una opción de importación no tiene que inventar el destino.

### 1.5 Términos de uso y `robots.txt`

Leído hoy:

- **`robots.txt`** (Cloudflare, `last-modified` 2026-04-08): sólo `User-agent: *` con
  `Disallow` de `/*?FASID`, `/*&FASID`, `/*/sharerating`, `/*/userratings`,
  `/*/userrating` y `/*/names-together`. **`topics.php` y `movietopic.php` no están
  prohibidos.** No hay `Crawl-delay` ni `Sitemap` en lo leído. Sí hay un `Disallow` sobre
  las votaciones de usuarios: relevante porque demuestra qué considera vedado el sitio
  (datos de usuarios), y sugiere no tocar `userratings` ni `names-together`.
- **«Política de Privacidad y condiciones de uso»** (`/es/private.php`, ~27 000 caracteres
  de texto): la parte «CONDICIONES DE USO» trata de cuentas personales e intransferibles,
  varias cuentas, manipulación de votos, insultos en críticas/listas, críticas escritas
  con IA (actualización noviembre 2025) y bloqueo de cuentas. **No encontré ninguna
  cláusula que mencione scraping, acceso automatizado, bots de lectura, reutilización o
  extracción de contenido**; sólo habla de «bots» en el sentido de votaciones
  sistematizadas. El pie dice «© 2002-2026 … All Rights Reserved». Búsqueda de
  palabras clave, no lectura legal línea a línea; el texto en `/es/` puede diferir de
  otros países **[NO VERIFICADO]**.
- Conclusión práctica, **sin ser asesoramiento legal**: acceso técnico permitido por
  `robots.txt`; las condiciones no prohíben ni autorizan expresamente la lectura
  automatizada; el contenido está protegido por copyright y «todos los derechos
  reservados». Lo prudente es lo mismo que hoy hace el repo con las fichas: **un pedido
  por acción explícita del usuario, con tope, con caché, sin recorrer el sitio**, y
  guardar sólo hechos mínimos (título, año, id, enlace), no pósters, notas medias, textos
  ni críticas. Hay además un riesgo de derecho sobre bases de datos (extracción
  sustancial) si se replicara un topic completo y se redistribuyera: se mitiga con tope,
  privado por defecto y enlace de vuelta. Para Cloudflare: los pedidos hechos hoy
  pasaron sin desafío; qué pasa con más ritmo **[NO VERIFICADO]**.

### 1.6 Cuánto se pidió para investigar

Diez pedidos al sitio, con 3-4 s entre cada uno: `robots.txt`; `topics.php`;
`movietopic?topic=149274&nodoc` (303); su destino canónico; `…&p=2` (con `fetch_text`);
`…&chv=list`; `abouttopics.php`; `private.php`; `legal.php` (404, adivinado); y una
repetición con `-L` para comprobar la redirección sin cookies. Se identificaron como
`MovieInboxResearch/0.1 (+https://github.com/pasaporteN25/MovieCache …)`, salvo el de
`fetch_text` (el `User-Agent` genérico del repo). El sitio puso cookies `FSID`/`FCD`; no
hizo falta guardarlas para que las páginas respondieran.

### 1.7 User-Agent

`fetch_text` manda `MovieInbox/0.2 (+local personal catalog)` a todo lo que no sea
Wikimedia, y el comentario de `external/common.py` dice a propósito que no se le cuenta a
un sitio que no lo pidió quién lo consulta. Se mantiene (pregunta 6 del §8).

---

## 2. Qué se quiere resolver

«Hacer algo con topics» puede significar cuatro cosas distintas, y cada opción cubre una:

1. Ver qué hay en un tema que te interesó (explorar).
2. Llevarte un tema al catálogo o al Club (acopiar).
3. Descubrir temas que no sabías que existían (descubrir).
4. No perder la referencia (anotar).

---

## 3. Opciones

Constantes comunes a las opciones 1 y 2: vista `chv=list`, orden por defecto
`avg-desc`, 30 fichas por página, **un pedido por página y no más de 1 pedido cada 2 s**,
caché de 15 minutos (como `SEARCH_CACHE_TTL_SECONDS` de `external/registry.py`), 429
anotado con `note_rate_limit` y mostrado como «FilmAffinity pide esperar N s».

### Opción 1 — Vista previa al pegar la URL (sin escribir nada)

**Alcance.** En el buscador de Inicio (IP2), pegar una URL `movietopic.php?topic=…`
muestra una tarjeta «Tema de FilmAffinity: Ajedrez — 63 fichas listables» y la primera
página (30) como filas: título, año, director y estado contra tu catálogo («Ya la tenés»,
«Te falta», «Revisar»). Sin agregar, sin guardar, sin colección. Con «Ver más» pide la
página siguiente. Un enlace «Abrir en FilmAffinity». Pegar la URL de `topics.php` no hace
nada nuevo (o muestra «índice de temas» con enlace; ver opción 3).

**Costo.** 1 pedido para ver (30 fichas), +1 por cada «Ver más», tope 90 fichas (3
páginas) en pantalla. Sin tabla nueva. Caché en memoria de 15 minutos.

**Capas.**

- `external/filmaffinity.py`: `FilmAffinityTopicParser` (vista `list`: id, título, año,
  director, tipo por sufijo) y `fetch_filmaffinity_topic(topic_id, page)`; detección de la
  URL `movietopic.php` (hoy `_from_pasted_url` devuelve `[]`: queda `[]` para el buscador
  de obras, porque un topic no es una obra).
- `domain/`: reconocimiento puro de la URL de topic y limpieza del sufijo de tipo del
  título, sin I/O (junto a `domain/search.py`/`titles.py`).
- `application/`: un servicio de vista previa que reciba un puerto/callable para traer la
  página (la capa `application` no importa `external`, `tests/test_layering.py`) y
  compare contra `CatalogComparisonIndex`/`catalog_membership`.
- `web/`: endpoint de lectura, p. ej. `GET /api/external/topics/preview?url=&page=`,
  autenticado, aparte del endpoint de U12 de obras.

**Riesgos.** El HTML es de un tercero y cambia: el parser tiene que fallar con claridad
(«FilmAffinity cambió el formato») y **nunca devolver lista vacía como si el tema no
tuviera fichas**. Mismo riesgo de términos que el resto del cliente de FilmAffinity, pero
el menor: lectura a pedido, sin persistencia. Matching: la fila usa los mismos estados que
U12; «presente» sólo por id compartido o por la regla de siempre (título+año); lo dudoso
es «Revisar». El tema no decide nada de identidad. Privacidad: nada sale de la instancia
hacia el Club. Hay que decidir cómo se ve el título cuando el sufijo dice «(C)» o «Miniserie».

**Pruebas sin red.** Fixtures recortados y fechados (§7).

### Opción 2 — Importar un tema como colección de Club (con pertenencia por `catalog_membership`)

**Alcance.** Desde la vista previa, «Importar como colección»: el owner trae hasta N
fichas del tema a un **borrador de importación** (reutiliza `import_service`: 48 h, vista
previa, clasificación, aplicación) y de ahí «crear colección local privada» y/o «copiar
faltantes al catálogo» con los mismos botones y límites de hoy (`add_to_catalog`: 500
máx.). La colección lleva título «Tema FilmAffinity: Ajedrez», descripción con aviso de
origen («selección de FilmAffinity, incompleta: sin documentales ni obras sin nota») y
enlace de vuelta, `source_kind="import"`. Cada ítem: `id = "filmaffinity:film723978"`
(estable), título, año, `filmaffinity_url`. Sin pósters, sin nota media, sin sinopsis, sin
topics como campo de la obra. La pertenencia de una obra tuya se calcula siempre con
`catalog_membership` (obra por obra), nunca por el hecho de estar en el tema.

**Costo.** `ceil(N/30)` pedidos secuenciales (a 1 cada 2 s). Tope por defecto **90
fichas** (3 pedidos, ~6 s) y máximo configurable **150** (5 pedidos); nunca se pasa de
500, el límite de copia. No hay refresco automático: «Actualizar» es un reimporte
manual que crea otro borrador. Guardado: lo que ya guarda una colección importada; el
HTML crudo no se guarda.

**Capas.** Igual que la opción 1 más: `application/import_service.py` (o un servicio
vecino) con un origen de borrador «tema FilmAffinity» (filas ya normalizadas, igual que
`append_device_items` recibe filas del teléfono), y un endpoint en `web/routers/imports.py`
que arma el borrador. `external/` sigue siendo el único lugar que sabe HTML; `application/`
sólo ve filas con campos de colección (`COLLECTION_ITEM_FIELDS`).

**Riesgos.**

- *Términos de uso:* es el caso de mayor exposición porque conserva una selección derivada
  de un tema. Se mitiga con tope, privado, sin datos de nota ni imágenes, enlace al
  original, y siempre por acción del owner.
- *Privacidad de Club (invariante 4):* la colección es privada del owner por defecto
  (`visibility=private`). **Publicarla en el Club** la muestra a los miembros de la
  instancia; no expone rutas ni estado operativo, pero sí es una selección ajena
  republicada: decisión del owner (pregunta 3). Nunca lleva `en_catalogo` ni
  `_availability` (`domain/collections.py:21`).
- *Matching conservador (invariante 3):* el tema, su descripción y sus etiquetas **no
  entran** al matching. El id `film…` sirve para «misma obra» sólo si ya está en el
  catálogo como `filmaffinity_url`; si no, título+año → `review`. Los sufijos de tipo se
  usan para presentar y nunca para unir. Sin año válido → siempre `review`.
- *Fragilidad:* la lista no es el tema completo (documentales y sin nota quedan fuera), y
  la numeración cambia cuando cambian las notas medias; un reimporte puede traer otro
  orden. El orden por nota **no** se guarda como orden de lectura (usar año, como la
  semilla de Kurosawa).
- *Duplicados:* el mismo tema importado dos veces crea dos colecciones; se avisa
  («ya importaste este tema el …») con el ID de topic guardado en la procedencia, y no se
  fusionan solas. Mismo patrón que «colección parecida» de IP3.
- *Charadas/API v1:* una colección importada sigue las reglas actuales de colecciones
  seguidas; si se publica entra a Charadas y a `/api/v1/collections` (pregunta 5).

**Pruebas sin red.** Fixtures de §7 más: el borrador contiene exactamente las filas del
fixture; sin `en_catalogo` ni `_availability`; una obra del catálogo con otro título y el
mismo director queda `missing`; una con el mismo `filmaffinity_url` es `present`; tope
respetado; 429 a mitad deja un borrador parcial marcado, no uno «completo».

### Opción 3 — «Descubrir» temas como sugerencias

**Alcance.** Un estante «Temas de FilmAffinity» en Inicio o en el buscador (campo vacío):
muestra unos pocos temas del índice (por ejemplo al azar o los que más fichas tienen) con
enlace a la vista previa de la opción 1. Variante ambiciosa: «temas parecidos a lo que
tenés», que exigiría saber qué topics tiene cada obra de tu catálogo.

**Costo.** Índice: 1 pedido de ~178 KB, caché de 24 h en memoria o archivo de la
instancia (el índice cambia poco; cuánto **[NO VERIFICADO]**). La variante ambiciosa
cuesta **un pedido de ficha por obra** del catálogo (miles): descartada. Alternativa
barata: usar el `|` del género que ya se lee en las fichas enriquecidas (§1.4) como pista
local de temas, sin pedidos nuevos, pero esos textos ya existen sólo en las obras
enriquecidas con FilmAffinity y requeriría un campo nuevo (`topics`) y revisar
`catalog.schema.json`: alcance de otro frente.

**Capas.** `external/filmaffinity.py` (`fetch_topics_index`), `application/` (selección
de sugerencias, sin ningún nombre de tema decidiendo identidad), `web/` (un endpoint),
`static/js` (estante: es trabajo del frente de presentación, no se detalla acá).

**Riesgos.** Poca ventaja sin la opción 1 (un tema sin vista previa es sólo un enlace
externo). Los nombres de tema son texto de FilmAffinity (hechos cortos, bajo riesgo).
Fragilidad: el índice es una sola página con `a.topic`; es la más simple de parsear pero
también la más cambiable. No hay privacidad de Club involucrada. **No** se debe incluir en
el repo una copia estática de los 489 topics: se quedaría vieja y sería una réplica del
índice.

**Pruebas sin red.** Fixture del índice recortado (tres iniciales, un badge `4.794`, un
nombre con barra «Acoso escolar / Bullying», un nombre con tilde).

### Opción 4 — Sólo enlazar / guardar la referencia

**Alcance.** El mínimo: reconocer la URL de topic (hoy se ignora en silencio), mostrar
«Esto es un tema de FilmAffinity, no una obra» con «Abrir en FilmAffinity», y permitir
guardar el enlace como **nota de referencia** en una colección propia (descripción) o en
la lista de recientes del buscador.

**Costo.** **0 pedidos.** Sin red, sin caché, sin tabla.

**Capas.** `domain/` (reconocer `movietopic.php?topic=ID` y normalizarlo a
`https://www.filmaffinity.com/es/movietopic.php?topic=ID`, sin `&nodoc`/`orderby`),
`web/` (mensaje del buscador). `external/` no cambia.

**Riesgos.** Casi ninguno (sin términos, sin fragilidad, sin Club). Costo de oportunidad:
no entrega ningún valor de catálogo. Debe cuidar que `nodoc` y los parámetros de
presentación no se guarden como identidad del tema; el identificador es sólo `topic=ID`.

**Pruebas.** Unitarias de la normalización; ninguna con red.

### Comparación

| | Pedidos | Persistencia | Riesgo de términos | Fragilidad HTML | Valor |
| --- | --- | --- | --- | --- | --- |
| 1 Vista previa | 1 a 3 por uso | ninguna | bajo | media | alto: ves qué te falta sin comprometer nada |
| 2 Importar | 3 a 5 por import | borrador y colección privada | medio | media | alto: acopiar y seguir en Club |
| 3 Descubrir | 1 por día | ninguna | bajo | media | medio, depende de 1 |
| 4 Enlazar | 0 | nota | nulo | nula | bajo, pero cierra el hueco del «no hace nada» |

---

## 4. Invariantes de CLAUDE.md, punto por punto

- **1 Layering.** Todo el HTML en `external/`; las reglas de URL y limpieza de título, en
  `domain/` (puras); los casos de uso, en `application/` recibiendo la fuente por inyección
  (sin importar `external`); `web/` sólo endpoints. `cli/` no se toca. Se corre
  `tests/test_layering.py` sin excepciones.
- **2 Terminología.** Un topic nunca marca `en_catalogo`, `to_watch` ni `watched`. «Te
  falta» es relación con el catálogo, no con el disco.
- **3 Matching conservador.** La pertenencia a un tema, el nombre del tema, los directores
  que muestra la fila y la sinopsis nunca deciden identidad. Sólo id `film…` ya conocido,
  o título+año por la regla de siempre, o `review`. El director de la fila (vista `list`)
  puede mostrarse; si se guarda, sólo como corroboración, igual que en
  `domain/work_identity.py:424-431`.
- **4 Privacidad.** Importación sólo del owner y privada por defecto; la publicación en
  Club es una decisión explícita. Ningún dato de ruta, archivo ni estado operativo.
- **5 `locked_fields`.** No aplica a las colecciones; si se copian al catálogo, la copia
  ya neutraliza campos personales y respeta lo que decide `catalog_membership`.
- **6 JSON portable.** Sin cambios en `catalog.schema.json` en las opciones 1, 2 y 4.
  Sólo la variante «topics como campo de la obra» (opción 3 ambiciosa) lo tocaría y queda
  fuera.

---

## 5. Pruebas con respuestas grabadas, sin red

Seguir el precedente del repo: HTML recortado y fechado dentro de la prueba o en
`tests/fixtures/` (como `HEAT_FILM_PAGE_HTML` en `tests/test_external_filmaffinity.py`,
con comentario de fecha, URL y qué se recortó), parchando `fetch_text` en
`movie_inbox.external.filmaffinity` como hacen esas pruebas. **Nunca red real**, tampoco
en el navegador (`tests/browser`: servir las respuestas desde un fixture local).

Fixtures a recortar de las respuestas reales (recortar a 3 a 5 fichas por página; las de
hoy quedaron sólo en un directorio temporal de la sesión, hay que recortarlas de nuevo):

1. **Índice:** tres iniciales, `a.topic` con badge `142`, `4.794`, nombre con `/` y tilde.
2. **Página de topic vista `list`, página 1:** una película con año, una miniserie, un
   corto «(C)», una ficha **sin año**, y el paginador con `p=2` y `p=3`.
3. **Página 2 y última página corta** (3 fichas, sin enlace «siguiente»).
4. **Tema vacío / sin fichas listables** (mensaje, no estructura rota).
5. **Redirección 303** (parchando `urlopen`, como hacen las pruebas de 429).
6. **HTML cambiado**: cero tarjetas sin mensaje de vacío ⇒ error «formato cambiado», no
   lista vacía.
7. **429** con `Retry-After` ⇒ `note_rate_limit` y mensaje con segundos.
8. **Desafío de Cloudflare** (página sin `all-topics` ni `movie-card`) ⇒ error claro.
9. Parser: nombres de atributos propios (no pisar el estado interno de `HTMLParser`, ver
   el comentario de `FilmAffinityMetadataParser` y `tests/test_external_html_parsers.py`).

Pruebas de contrato: `test_layering` (nada de `application` → `external`), una prueba que
verifica que el parser sólo emite los campos permitidos y que `catalog_membership` no mira
topics (equivalente a la prueba de IP4 para créditos).

---

## 6. Recomendación

**Hacer 1 y 2 en ese orden, con 4 como parche inmediato y 3 solo si después se extraña.**
Fundamento:

- 1 entrega casi todo el valor («qué me falta de este tema») con la menor exposición:
  lectura a pedido, sin persistencia, reutilizando U12 y el estado «Ya la tenés/Revisar».
  Arregla además el silencio de hoy al pegar la URL.
- 2 es incremental sobre 1 y reutiliza el sistema de borradores y colecciones, que ya
  resuelve vista previa, aplicación y límites, sin inventar tablas ni tocar el modelo de
  colecciones. Es donde está el riesgo de términos, y por eso va segunda, sólo del owner,
  con tope y privada.
- 4 cuesta casi nada y se hace dentro de 1 (el reconocimiento de URL es el mismo código).
- 3 vale poco sin 1, y su variante útil («temas parecidos») es cara o exige datos que
  hoy no existen.

**Fases**

0. **Spike y parser** (sin UI): `FilmAffinityTopicParser` y `fetch_filmaffinity_topic`
   con fixtures, errores explícitos (formato cambiado, desafío, 429) y la regla de caché.
   Se cierra con la suite verde y sin red.
1. **IP7 — Vista previa** (opción 1 + 4).
2. **IP8 — Importar** (opción 2), tras decidir las preguntas 3 y 4.
3. **IP9 — Índice de temas** (opción 3, sólo si el owner la quiere).

Antes de la fase 2 conviene revisar con el owner el riesgo de términos (pregunta 1), ya
que es la primera vez que una fuente genera una colección entera.

---

## 7. Qué NO se pudo verificar (resumen)

- Valor y efecto exacto de `nodoc`, de los otros `orderby` y de los filtros del topic.
- Por qué 133 en el índice se vuelven 63 en la página (cuántos son documentales y cuántos
  no tienen nota), y si el conteo del índice incluye series y cortos.
- Si el ID `filmNNN` es el mismo en todas las variantes de país.
- Si las etiquetas de topic de una ficha llevan enlace al topic.
- Qué datos más trae la vista `list` (sinopsis, duración).
- Frecuencia de cambio del índice y estabilidad de los IDs de topic a largo plazo.
- Comportamiento de Cloudflare con ritmo mayor al probado (10 pedidos separados).
- Que las condiciones de uso de otras variantes de país coincidan con la leída en `/es/`.
- Que el cliente Android tolere una colección nueva si se publicara (no aplica a 1 ni 4).
- Que [X12] trate `filmaffinity_url` como id fuerte de identidad (hay que confirmarlo
  leyendo `domain/work_identity.py` al implementar).

---

## 8. Preguntas abiertas para el owner

| # | Pregunta | Recomendación | ¿Bloquea? |
| --- | --- | --- | --- |
| 1 | ¿Aceptás el riesgo de términos de leer páginas de FilmAffinity a pedido (las condiciones no lo prohíben ni lo autorizan, `robots.txt` lo permite)? | Sí para vista previa; para importar, sí con tope, privado y sin pósters/notas | **Bloquea IP7** |
| 2 | ¿Tope de fichas por importación? | 90 por defecto, 150 máximo | **Bloquea IP8** |
| 3 | Una colección de topic, ¿puede publicarse en el Club o queda siempre privada del owner? | Privada; publicar sólo con acción explícita y aviso de origen | **Bloquea IP8** |
| 4 | ¿Pueden importar los miembros o sólo el owner? | Sólo el owner (igual que el import de hoy) | **Bloquea IP8** |
| 5 | ¿Una colección de topic seguida alimenta Charadas y la API v1? | No por defecto, igual que personas (IP6) | No bloquea |
| 6 | ¿Se mantiene el `User-Agent` genérico para FilmAffinity o se identifica el proyecto, como se hace con Wikimedia? | Mantener, salvo que el sitio empiece a limitar | No bloquea |
| 7 | ¿Se aceptan documentales y obras sin nota fuera del tema (porque el sitio los excluye de la lista)? | Sí, avisando que la lista es incompleta | No bloquea |
| 8 | ¿Serie y cortos entran como obras de la colección o se filtran? | Entran, con el tipo como dato de presentación | No bloquea |
| 9 | ¿Interesa el estante de descubrimiento (opción 3)? | Posponer | No bloquea |
| 10 | ¿Reimportar un tema reemplaza, agrega o crea otra colección? | Crear otra y avisar; sin sincronización | No bloquea |

---

## 9. Borrador de entrada de backlog (para pegar en `tareas.md`, frente [IP])

No está aplicado en `tareas.md`. Redactado para el frente existente (prefijo `[IP]`,
siguiente número libre IP7).

```
- [ ] **[IP7] Vista previa de un tema de FilmAffinity al pegar su URL.** Cierre: pegar una URL `movietopic.php?topic=ID` en el buscador de Inicio muestra una tarjeta de tema con título, cantidad listable y hasta 30 filas (título, año, director) con «Ya la tenés», «Te falta» o «Revisar» calculados con `catalog_membership` y el índice de U12, sin escribir catálogo ni colecciones; «Ver más» pide la página siguiente con tope de 90 fichas; un pedido por página con caché de 15 minutos y 429 anotado; el tema, su nombre y sus etiquetas no entran al matching; el parser vive en `external/filmaffinity.py` y falla con mensaje claro (formato cambiado, desafío, 429) en vez de devolver una lista vacía; `test_layering` verde; pruebas con respuestas grabadas (índice, página 1, página 2, vacío, 303, 429, formato roto) sin red real; la URL de `topics.php` y la de un tema se reconocen como «tema de FilmAffinity, no una obra» con enlace externo; PRODUCT.md y CHANGELOG actualizados.
- [ ] **[IP8] Importar un tema de FilmAffinity como colección privada.** Cierre: desde la vista previa, el owner crea un borrador de importación de hasta 90 fichas (máximo 150) con ítems `filmaffinity:filmNNN` (título, año, `filmaffinity_url`), sin pósters, notas medias ni sinopsis; el borrador reutiliza vista previa, clasificación y «crear colección local privada»/«copiar faltantes» existentes; la colección declara el origen y la incompletitud («sin documentales ni obras sin nota») y enlaza al tema; nunca lleva `en_catalogo` ni `_availability`; una obra del catálogo con el mismo director y otro título queda `missing`; reimportar el mismo tema avisa y no fusiona; un 429 a mitad deja un borrador parcial marcado; publicarla en Club requiere acción explícita; pruebas sin red; CHANGELOG actualizado. Depende de IP7 y de las preguntas 1 a 4 del análisis.
- [ ] **[IP9] Índice de temas de FilmAffinity como sugerencias (opcional).** Cierre: un estante con temas tomados de `topics.php` (un pedido, caché de 24 h) enlaza a la vista previa de IP7; sin copia estática de los 489 temas en el repo; el nombre de un tema nunca decide identidad; fixture del índice grabado sin red. Depende de IP7 y de la pregunta 9.
```
