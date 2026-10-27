# Inicio, búsqueda de alta y Club por personas — análisis 2026-10-21

Insumo para decidir; no es un brief ni un ADR. Pedido del owner: (1) sacar la cartelera
duplicada de Inicio y alargar su lista, (2) una búsqueda visible arriba para agregar obras,
(3) agregar directores/actores como colecciones de Club, (4) definir la relación Club ↔
datos propios, con duplicados y bajas. Todas las referencias `archivo:línea` se verificaron
contra `feature/search-workbench-v011` el 2026-10-21.

Tareas en `tareas.md`, frente **[IP]**. Preguntas para el owner en §7.

---

## 1. Diagnóstico

### 1.1 Cartelera duplicada y lista corta (punto 1)

- La cabecera de Inicio es `cartelera automática | tabla | cartelera consultada | consola`
  (`src/movie_inbox/web/static/js/surfaces/home.js:404-423`). La izquierda es el póster
  rotativo «Hoy/Ayer en cartel» (`home.js:373-383`, autoplay cada 6,5 s en `home.js:41`);
  la derecha es «Tu selección» (`home.js:889-900`).
- **Al entrar, las dos muestran la misma obra.** La selección arranca en la primera fila
  de la programación (`home.js:119-135`) y el carrusel también arranca en el índice 0
  (`home.js:137-148`). Fue aceptado así en U6 («si ambas obras coinciden, se permite la
  misma portada», `docs/design/home-evolution-backlog-2026-09-12.md:141-152`). En la
  práctica la misma obra aparece tres veces: póster izquierdo, fila 01 y póster derecho.
- **La lista corta tiene dos causas, no una.** La programación diaria es exactamente
  `featured` (`home.js:93-105`), con un tope en el servidor de 6 obras
  (`src/movie_inbox/application/home_service.py:18-23`). Además sólo entran obras
  disponibles **y con imagen** (`home_service.py:166-181`): un catálogo con pocas portadas
  muestra menos de 6. La tabla se dimensiona para 6 filas (`home.js:414-415`).
- Estantes: el servidor manda hasta 5 secciones de 6 obras (`home_service.py:18-19`), y el
  cliente dibuja como máximo 4 (`home.js:42`, `home.js:629`). La quinta, que suele ser
  efemérides (`home_service.py:72-73`), nunca se ve en escritorio.
- `PRODUCT.md:113-118` dice «entre una y cuatro obras»; el código dice 6. El contrato
  está desactualizado.
- Espacio: según U6, los dos marcos con su separación ocupan 274×2 + 16×2 = 580 px antes
  de la tabla (`home-evolution-backlog-2026-09-12.md:154-156`). Sacar un marco libera
  ~290 px para la tabla.

### 1.2 Búsqueda para agregar (punto 2)

- Ya existen los botones «Buscar» y «Agregar» en la cabecera global
  (`src/movie_inbox/web/static/index.shell-open.html:29-35`). «Agregar» lleva a Colección
  en modo `add` con fuentes externas activas (`web/static/js/core/router.js:53-70`).
  Inicio no tiene ningún campo de texto.
- El modo `add` ya se puede abrir por URL con la consulta: `?view=catalog&mode=add&q=…`
  (`router.js:240-262`). La mesa de búsqueda U12 ya mezcla resultados locales y externos,
  marca los que ya tenés y manda los dudosos a revisión (CHANGELOG `[Sin publicar]`).
  Para que Inicio busque, entonces, alcanza con un campo que construya esa URL.
  No hace falta un motor nuevo.
- La búsqueda por dirección existe como descubrimiento explícito: prefijo `director:`
  (`src/movie_inbox/domain/search.py:31`, `search.py:62-77`) y casilla en Colección
  (`web/static/index.collection.html:44-47`). Se resuelve en `_search_by_director`, que
  está separada del puntaje por título (`application/search_service.py:87-117`). **No
  hay búsqueda por actor.**

### 1.3 Personas como colecciones de Club (punto 3)

- **Hoy no existe la entidad persona.** `directors` y `cast` son `list[str]`
  (`src/movie_inbox/domain/models.py:148-150`; `catalog.schema.json:104-106`).
- Wikidata **sí** entrega ids de persona (P57/P161, `external/wikidata.py:21-23`,
  `wikidata.py:300-309`), pero se descartan: sólo se guarda la etiqueta
  (`wikidata.py:384-405`). TMDb hace lo mismo con `credits` (`external/tmdb.py:374-380`).
- Para detectar duplicados, el director sólo **corrobora**: puede volver «posible» un
  título sin año, pero nunca une dos obras (`domain/work_identity.py:424-431`).
  `domain/matching.py` no menciona `director` ([Q4]).
- Colecciones de Club hoy: `CuratedCollection` con `visibility ∈ {private, published}` y
  `source_kind ∈ {builtin, import, user}` (`domain/collections.py:13-14`), con un `CHECK`
  en SQLite (`infrastructure/identity_repository.py:124-140`). Para [P2] se agregó la
  columna discriminadora `derived_library_id`, porque cambiar ese `CHECK` exige recrear la
  tabla (`collections.py:52-57`). Hay un precedente de colección «por persona»: la semilla
  de Akira Kurosawa (`infrastructure/starter_collections.py`, instalada en
  `web/app.py:277`). Sus obras llevan enlace a Wikipedia y no tienen id de persona.
- Sólo el owner crea colecciones, por importación y privadas
  (`web/routers/imports.py:156-166`). Las publicadas son la semilla y las de [P2].

### 1.4 Relación Club ↔ datos propios, duplicados y bajas (punto 4)

- **Seguir no copia.** Seguir o dejar de seguir sólo inserta o borra una fila de
  `collection_follows` (`infrastructure/collection_repository.py:146-176`). Copiar al
  catálogo es explícito, deja los campos personales en neutro, pone `en_catalogo=False` y
  conserva la procedencia en `collection_sources` (`domain/collections.py:152-185`).
  Además pasa por `catalog_membership`: lo dudoso queda en `review`
  (`application/collection_service.py:76-139`).
- Las colecciones nunca llevan `en_catalogo` ni `_availability`
  (`domain/collections.py:21`). La disponibilidad física es del inventario de la
  instancia, no de la colección (PRODUCT.md:100-102).
- «Dejar de seguir» se ejecuta sin confirmar (`web/static/js/surfaces/club.js:377-411`).
  Hoy está bien, porque no destruye nada.
- Lo que leen las colecciones seguidas: la sección «faltantes de colecciones seguidas» de
  Inicio (`home_service.py:292-342`), Charadas (`application/charades_service.py:4`) y la
  API de dispositivos (`web/routers/device_catalog.py:211-245`). Al dejar de seguir, la
  API responde 404 a la colección (`device_catalog.py:278-281`).
- Duplicados de obra: [X12] ya resuelve «misma obra» por id externo compartido y
  «posible» por título más corroboración (CHANGELOG `[Sin publicar]`). Duplicados de
  persona: no existen como concepto.

---

## 2. Opciones y recomendación por punto

### 2.1 Inicio sin cartelera duplicada

| Opción | Pros | Contras |
| --- | --- | --- |
| **A. Quitar la izquierda (carrusel automático)** y dejar «Tu selección» | Sobrevive el póster que sigue la consulta, el que usan VHS, al azar [U8] y Club. Libera ~290 px para la tabla. Se va el autoplay, que es carga visual y de accesibilidad | Se pierde la rotación «en cartel» como gesto. La marca «al aire» queda sólo en la fila (`is-on-air`, `home.js:390`) |
| B. Quitar la derecha | La cartelera del día queda como portada fija | Rompe U8 y la consulta de Club/VHS, que muestran su obra ahí (`home.js:421`). Va contra U6.2 |
| C. Dejar las dos y que no coincidan al entrar | Cambio mínimo | No resuelve la queja: siguen dos marcos y la tabla sigue apretada |

**Recomendación: A.** La lista queda así:

- Tabla ancha con «Hoy/Ayer» y «Volver a programación» en su cabecera, como ahora
  (`home.js:407-413`).
- `HOME_FEATURED_LIMIT` pasa de 6 a 12. En escritorio entran 10 filas visibles y el resto
  se desplaza dentro de la tabla.
- La programación deja de exigir imagen para entrar a la lista; la imagen sólo pesa para
  elegir la primera obra seleccionada. Si no, el tope sube y la lista sigue corta.
- `HOME_SHELF_BAY_LIMIT` se iguala a `HOME_SECTION_COUNT` (5) para que la efeméride se vea.
- Se actualiza PRODUCT.md:113-118.
- Las instantáneas de Hoy/Ayer (`infrastructure/home_snapshot_repository.py`) ya recortan
  con `[:HOME_FEATURED_LIMIT]` (`home_service.py:109`, `:144`). Una de 6 sigue siendo
  válida y no hace falta migrarla.

### 2.2 Búsqueda arriba en Inicio

| Opción | Pros | Contras |
| --- | --- | --- |
| **A. Campo en la cabecera de Inicio que abre Colección en `mode=add&q=`** | Reusa U12 completo: matching, comparador, revisión, «ya la tenés». Nada nuevo que pueda equivocarse | Sacás al usuario de Inicio (con regreso conservado por U10) |
| B. Resultados en línea dentro de Inicio | Inmediato | Duplica la mesa U12 y su lógica de revisión. Dos superficies que pueden divergir en el matching conservador |
| C. Agrandar el botón «Agregar» de la cabecera global | Barato | No es un campo visible; no responde al pedido |

**Recomendación: A.** El campo va en la barra del spotlight, en el lugar de
«Programación personal / Cartelera disponible» (`index.home.html:10-15`). Enter abre
Colección para agregar. Si el owner decide el punto 3, un selector «Obra | Persona» al
lado manda a la búsqueda de personas (§2.3). Sin autocompletado en la primera fase. Los
botones de la cabecera global quedan como están. En móvil, el campo ocupa todo el ancho
arriba de la tabla.

### 2.3 Personas como colecciones de Club

| Opción | Pros | Contras |
| --- | --- | --- |
| A. **Vista derivada por nombre** (`directors`/`cast` que contengan el texto) | Sin datos nuevos | El nombre no es identidad: homónimos, transliteraciones («Kurosawa Akira»), créditos incompletos. Sólo muestra lo que ya tenés, no sirve para descubrir. Es exactamente lo que prohíbe el invariante 3 si después decide qué copiar |
| B. **Vista derivada por id** (obras del catálogo cuyo crédito tenga ese QID) | Exacta | Exige guardar ids de persona en cada obra, con migración de catálogo y `catalog.schema.json` v11. Sigue sin mostrar lo que te falta |
| **C. Persona persistida por id externo y filmografía persistida como colección** | Muestra lo que falta (que es el pedido). Reusa follow, Club, Inicio, API v1 y Charadas sin caminos nuevos. La identidad es el QID, no el nombre | Hace falta refrescar la filmografía. Es una tabla y una columna nueva en `instance.db` |

**Recomendación: C.** Ver §3.

---

## 3. Modelo de datos propuesto

Todo en `instance.db` (v25 → v26), nada en el catálogo personal.

```
people
  id            TEXT PK        -- "wikidata:Q8006" (canónico)
  wikidata_id   TEXT UNIQUE    -- Q8006
  tmdb_person_id TEXT NULL     -- sólo si Wikidata lo declara (P4985); nunca por nombre
  name          TEXT           -- etiqueta es|en, para mostrar
  description   TEXT           -- «director de cine japonés (1910–1998)», para desambiguar
  birth_year, death_year, image_url
  redirected_from TEXT NULL    -- QID fusionado en Wikidata
  refreshed_at, created_at

curated_collections
  + derived_person_id TEXT NULL REFERENCES people(id)   -- mismo patrón que derived_library_id
  + derived_person_role TEXT NULL CHECK IN ('director','cast')
  UNIQUE (derived_person_id, derived_person_role)
```

- **Identidad de persona = QID de Wikidata, y nada más.** Un nombre, una descripción o
  una coincidencia de créditos nunca crean ni unen personas. Sin QID no hay colección de
  persona. TMDb queda como fuente secundaria y sólo se vincula si el propio Wikidata
  declara P4985.
- **Una colección por (persona, rol).** «Kurosawa director» y «Mifune actor» son
  colecciones distintas. Una persona que dirige y actúa tiene dos, y se elige cuál seguir.
- **Ítems de la colección:** las obras donde la persona figura con ese rol en Wikidata,
  traídas con `haswbstatement:P57=Q…` / `P161=Q…` (búsqueda de la API de Wikidata) o con
  SPARQL. El ítem lleva `id = "wikidata:Q…"` (estable entre refrescos) y pasa por
  `normalize_collection_item` (sólo campos compartibles, `collections.py:68-74`). El
  orden es cronológico por año y luego `collection_items_in_reading_order` como desempate
  (`collections.py:102-121`).
- **Relación con el catálogo propio: calculada, nunca guardada.** «La tenés» / «te falta»
  / «revisar» sale de `catalog_membership` (`collection_service.py:58-62`), que compara
  identidad de obra (ids externos, título y año) y **nunca personas**. Que «Rashomon» de
  tu catálogo tenga «Akira Kurosawa» en `directors` no la mete en la colección ni la une
  con nada. Así se cumple el invariante 3: el reparto ayuda a **encontrar** la persona y
  su filmografía, pero la pertenencia de una obra tuya se decide con el matching de obras
  de siempre.
- **¿Vista derivada o persistida?** Persistida, por tres razones. (1) Una vista sobre el
  catálogo sólo podría ver obras que ya tenés, y el pedido es descubrir. (2) Una vista
  sobre texto de créditos haría que el nombre decida la pertenencia, lo que viola el
  invariante 3. (3) La API de dispositivos necesita ids estables y una lista paginable
  (`device_catalog.py:247-290`), y una instantánea persistida y versionada (`version`,
  `updated_at`) se la da gratis.
- **Refresco:** manual («Actualizar filmografía») y opcional en segundo plano, con el
  mismo patrón lento de [X12]. Agrega obras nuevas y **no saca** obras que Wikidata deja
  de listar: las marca para revisión del owner.
- El catálogo **no cambia** en este frente: `catalog.schema.json` sigue en v10. Guardar
  QIDs de créditos en las obras (opción B) queda para más adelante y no lo exige esta
  función.

---

## 4. Duplicados

**Obras**

| Caso | Tratamiento |
| --- | --- |
| La misma obra en dos colecciones (Kurosawa director y Mifune actor) | Es esperado. Cada colección tiene su ítem. Al copiar la segunda vez, `catalog_membership` dice `present` y no se duplica (`collection_service.py:108-110`) |
| La obra de la colección ya está en tu catálogo con otro idioma o enlace | Si comparte id externo, es la misma obra ([X12]). Si sólo coincide el título, es `review` y aparece en el comparador. Nunca se une sola |
| Dos ítems con distinto QID y mismo título y año dentro de una filmografía | Se conservan los dos (remake, versión TV). Los distingue Wikidata, no nosotros |
| La colección de persona se superpone con la semilla Kurosawa | No se unen colecciones. Al crear Q8006 se avisa que «ya existe una colección curada con un nombre parecido». Es una pista por texto, sólo informativa |

**Personas**

| Caso | Tratamiento |
| --- | --- |
| Búsqueda «Kim Ki-duk» devuelve dos QIDs | Se listan **todos** los candidatos con descripción, años de vida, imagen y 2-3 obras conocidas. **Nunca se elige solo**, aunque uno sea más popular. Sin elección no se crea nada |
| Un candidato no es humano (P31≠Q5) o no tiene obras con ese rol | Se descarta del listado de candidatos (no es una persona-director/actor útil) |
| La misma persona ya existe (mismo QID) | Se reusa la colección existente y se ofrece seguirla. `UNIQUE` lo garantiza |
| Wikidata fusionó dos QIDs (redirección) | Al refrescar, si el QID redirige, se adopta el canónico y se guarda `redirected_from`. Si el canónico ya tiene colección, el owner decide desde Curaduría si unificarlas. Mientras tanto quedan las dos |
| Mismo nombre, QIDs distintos, y el usuario sospecha que son la misma persona | Revisión humana. No hay unión automática de personas |
| Variantes de nombre en créditos («Kurosawa Akira», «黒澤明») | Irrelevante para la identidad. Sólo se usan para ayudar a buscar |

**Entra en revisión humana:** elegir entre homónimos; unificar colecciones tras una
redirección; obras que la filmografía deja de listar; cualquier obra con
`catalog_membership = review` antes de copiar.

---

## 5. Bajas de colecciones del Club y conflictos

Regla rectora, sin excepciones: **dejar de seguir borra sólo tu fila de
`collection_follows`.** Nunca toca el disco, el inventario, el catálogo, `en_catalogo`,
el estado personal ni otras colecciones.

| Caso | Comportamiento |
| --- | --- |
| (a) Obras de la colección que están en disco (`en_catalogo`) | No pasa nada con ellas. Si las copiaste, siguen en tu catálogo con su disponibilidad. Si no, nunca estuvieron en tu catálogo. La disponibilidad es del inventario, no de la colección |
| (b) La persona comparte obras con otra colección seguida o con tu catálogo | No hay conteo de referencias porque seguir no copia. Las otras colecciones siguen mostrando esas obras y tu catálogo no cambia |
| (c) Obra compartida con otra colección seguida | Sigue apareciendo en «faltantes de colecciones seguidas» de Inicio por la colección que todavía seguís (`home_service.py:305-315`) |
| (d) Dar de baja una colección de la que copiaste obras | Las copias quedan y su `collection_sources` también, como historia. La ficha muestra «copiada de X (ya no la seguís)» |

**Qué se conserva:** obras copiadas, estado personal (`status`, `watched_at`, `rating`,
`review`), `locked_fields`, procedencia, la persona y su colección (son de la instancia y
otros pueden seguirlas).

**Qué se borra:** la fila de seguimiento. Como consecuencia, la colección sale de Inicio,
de Charadas y de `/api/v1/collections` (404 en sus ítems, que ya es el comportamiento
documentado en `device_catalog.py:278-281`).

**Qué requiere confirmación:**

- Dejar de seguir no destruye nada y no necesita confirmación. Sí conviene avisar después,
  en el mensaje de estado: «tus N obras copiadas se quedan».
- Borrar la persona o su colección de la instancia es una acción del owner, con
  confirmación, y sólo se permite con cero seguidores. Si no, se despublica.
- **Se descarta** una opción «quitar también del catálogo lo copiado de acá». Si algún día
  se pide, tiene que ser una acción de catálogo aparte, ítem por ítem, que excluya obras
  con `en_catalogo`, estado personal, `locked_fields` o procedencia de otra colección.
  Además pasa por las bajas de [X5] (`device_removals`).

---

## 6. Privacidad, API de dispositivos y JSON portable

- **Privacidad (invariante 4):** una colección de persona sólo contiene metadata pública
  de obras, filtrada por `COLLECTION_ITEM_FIELDS`, sin `en_catalogo` ni `_availability`
  (`collections.py:21`). No cruza con el inventario. Quién sigue una colección no se
  expone. Riesgo concreto: `_summary` publica `owner.username`
  (`collection_service.py:163-166`). Para colecciones de persona creadas por un miembro,
  recomiendo no mostrar el creador (pregunta 3).
- **API v1:** las colecciones de persona seguidas salen por los mismos endpoints. Cambio
  aditivo en `docs/openapi/device-api-v1.openapi.json` (`CollectionSummary`): `kind:
  "curated" | "library" | "person"` y `person: {name, role, wikidata_id}` opcional. Los
  ids de ítem siguen opacos y estables porque el id interno es el QID de la obra. Hay que
  confirmar que el cliente Android tolera campos desconocidos (repositorio
  `../movieIndexAndroid`). No lo verifiqué.
- **Charadas:** el mazo incluye las colecciones seguidas (`charades_service.py:4`) y su
  huella cubre todas las obras elegibles. Seguir a un actor con 200 películas cambia el
  mazo y su huella. Recomendación: las colecciones de persona no alimentan Charadas
  salvo que se decida otra cosa (pregunta 5). Los vectores
  (`docs/briefs/charades-v1-vectors.json`) no cambian si se excluyen.
- **JSON portable:** `catalog.schema.json` no cambia (sigue en v10). Las personas viven
  en `instance.db`, igual que las colecciones. Sí hay que sumar `people` y la columna
  nueva al backup completo, que ya incluye colecciones (PRODUCT.md:109-112), y verificarlo
  en el docker-smoke.
- **`instance.db` v25 → v26:** migración con `CREATE TABLE people` y
  `ALTER TABLE curated_collections ADD COLUMN …` (sin recrear la tabla). Va en el
  CHANGELOG bajo «Antes de actualizar», como la v23→v25 actual.

---

## 7. Riesgos y preguntas abiertas

| # | Pregunta | Recomendación | ¿Bloquea? |
| --- | --- | --- | --- |
| 1 | ¿Se quita el carrusel izquierdo (opción A) y se pierde el autoplay? | Sí, opción A | **Bloquea IP1** |
| 2 | ¿Cuántas obras en la programación diaria y se deja de exigir imagen? | 12 obras, sin exigir imagen para la lista | **Bloquea IP1** |
| 3 | ¿Quién puede agregar personas: sólo el owner o cualquier miembro? ¿Se muestra quién la agregó? | Cualquier miembro activo. La colección es de la instancia y no muestra creador | **Bloquea IP3** |
| 4 | ¿Wikidata como única fuente de identidad de persona (sin QID no hay colección)? | Sí. TMDb sólo vinculado vía P4985 | **Bloquea IP3** |
| 5 | ¿Las colecciones de persona alimentan Charadas? | No, por defecto | No bloquea (default «no») |
| 6 | Una persona que dirige y actúa: ¿una colección por rol o una sola con filtro? | Una por rol | No bloquea |
| 7 | ¿Qué pasa con la semilla Kurosawa? ¿Se convierte en colección de persona? | Dejarla como curada y sólo avisar la superposición | No bloquea |
| 8 | ¿Roles además de dirección y reparto (guion, música)? | No en la primera entrega | No bloquea |
| 9 | ¿La búsqueda de Inicio va siempre a «agregar» o también a «buscar en mi colección»? | Siempre a agregar. U12 ya muestra lo que tenés | No bloquea |

Riesgos:

- La cobertura de Wikidata es despareja para actores secundarios y cine no occidental.
  Una filmografía incompleta se presenta como «según Wikidata» y nunca como completa.
- Hay que medir el costo de red. Una filmografía grande (un actor prolífico, 300 obras)
  necesita paginar y cachear. Usar el ritmo lento de [X12] y un tope por colección, por
  ejemplo 500, como `add_to_catalog` (`collection_service.py:92-93`).
- Sacar el marco izquierdo rompe las pruebas que lo nombran: `tests/js/home-selection.test.mjs`,
  `tests/browser/test_ui_browser.py`, `tests/browser/test_home_random.py`,
  `tests/browser/home_*_metrics.js`. Hay que actualizarlas, no borrarlas.
- La regresión visual de Inicio (U4/U6) estaba aceptada por el owner. Este cambio reabre
  ese gate.

---

## 8. Secuencia de entrega

Cada fase se puede cerrar y fusionar sola. IP1 e IP2 no dependen del modelo de personas.

1. **IP1 — Inicio con un solo póster y lista larga.** Quitar el carrusel izquierdo y su
   autoplay. `HOME_FEATURED_LIMIT=12`, la lista ya no exige imagen, se ven las 5
   secciones y se actualiza PRODUCT.md. *Tests:* `test_home_service` (12 obras, obras sin
   imagen en la lista, primera seleccionada con imagen); `home-selection.test.mjs` (la
   selección inicial sin carrusel); navegador a 1280/1440/1920 (tabla de 10 filas sin
   desborde y foco estable); `test_home_random` (al azar sigue en el póster derecho).
2. **IP2 — Búsqueda de alta en Inicio.** Un campo arriba que navega a
   `?view=catalog&mode=add&q=`, con regreso a Inicio. *Tests:* navegador (Enter abre el
   modo agregar con la consulta y los resultados externos activos; Atrás vuelve a Inicio;
   consulta vacía no navega); accesibilidad (etiqueta visible y orden de foco).
3. **IP3 — Modelo de persona (sólo backend).** `instance.db` v26, entidad `people`,
   columna `derived_person_id`/`role` y servicio de búsqueda de candidatos en Wikidata
   (P31=Q5, con descripción y años). *Tests:* migración v25→v26 sobre una base real
   sintética; dos homónimos devuelven dos candidatos y no se elige ninguno solo; mismo QID
   reusa la colección; QID redirigido; `test_layering` sigue verde; `domain/matching.py`
   sigue sin referencias a personas (prueba AST nueva).
4. **IP4 — Filmografía como colección de Club.** Crear, seguir y refrescar.
   *Tests:* los ítems pasan por `normalize_collection_item` y no llevan `en_catalogo` ni
   `_availability`; `catalog_membership` da `present/missing/review` sin mirar créditos
   (una obra del catálogo con el mismo director y otro título queda `missing`, no
   `present`); un refresco no mueve ids de ítem y no borra obras retiradas; tope de
   tamaño; el payload de `/api/collections` no expone creador ni seguidores.
5. **IP5 — UI de personas.** Selector «Obra | Persona» en la búsqueda de Inicio/Colección,
   elección entre homónimos y tarjeta de persona en Club. *Tests:* navegador (dos
   homónimos obligan a elegir; mismo QID ofrece seguir la existente; aviso de
   superposición con la semilla).
6. **IP6 — Bajas y API v1.** Mensaje después de dejar de seguir; `kind`/`person` en
   `CollectionSummary` de OpenAPI; Charadas excluye personas. *Tests:* dejar de seguir no
   cambia el catálogo, `en_catalogo` ni las copias con `collection_sources` (prueba
   explícita de los casos a–d de §5); `/api/v1/collections/{id}/items` responde 404
   después de la baja; validación de OpenAPI; el mazo de Charadas no cambia al seguir una
   persona; el backup completo incluye `people`.
