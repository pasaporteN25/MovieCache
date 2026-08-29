# Tareas — Movie Inbox

Tablero en Markdown, versionado en el repo. Columnas = estado (`Backlog` / `En curso` /
`Hecho`). Dentro de `Backlog`, las tareas se agrupan por frente. Cada tarea tiene alcance
de archivo/línea concreto, dependencias explícitas y un nivel de modelo sugerido —
mecánica de un solo archivo sin decisiones → chico; pocos imports cruzados ya resueltos →
medio; requiere criterio, coordina 3+ archivos o toca semántica sutil (matching,
identidad) → grande. Nunca asignar una tarea de "requiere criterio" a un modelo chico.

Al cerrar una tarea: moverla a `Hecho` con fecha y commit, no borrarla. Al abrir un frente
nuevo (Integraciones, Landing, lo que sea), agregar una sección `### Frente: X` nueva acá
mismo — este archivo es el tablero completo, no uno por fase.

---

## Backlog

La cola se ejecuta en el orden de las secciones y tareas, salvo que una dependencia
explicita diga lo contrario. Una tarea bloqueada por una decision externa no detiene la
cola: se documenta aca y se toma la siguiente accionable. Los conteos de errores son una
foto diagnostica, no un criterio estable entre versiones de herramientas.

### Frente: Busqueda, comparacion y composicion de fuentes

Diagnostico del 2026-08-26: la busqueda local principal usa titulos, aliases, IDs y
archivos; `directors` existe en el modelo pero se excluye deliberadamente de la
evidencia de identidad. Las tres fuentes externas reciben hoy casi la misma consulta:
IMDb hace una sola llamada al endpoint de sugerencias, Wikipedia busca en ingles y
espanol agregando `film`/`pelicula`, y FilmAffinity envia el texto literal. El puente de
aliases de Wikidata para IMDb se activa solo si IMDb devolvio filas pero todas quedaron
debajo del umbral; no se activa cuando la sugerencia vino vacia. Esto explica por que
agregar `Jacopetti` puede ayudar a FilmAffinity sin rescatar necesariamente IMDb o
Wikipedia. Ademas, `runSearch()` restablece el modo `browse`, por lo que editar la
consulta durante `Comparar` pierde el contexto y ejecuta una busqueda comun.

#### [Q5] Definir autoridad y conflicto campo por campo
- **Alcance**: crear una matriz versionada para titulo/aliases, ano/tipo, creditos,
  imagenes, fechas y descripcion. Manual y `locked_fields` ganan siempre; IMDb puede ser
  autoridad de identidad y datos estructurados cuando [F1] demuestre disponibilidad,
  mientras Wikipedia puede aportar la descripcion/sinopsis mas completa. FilmAffinity
  y futuras fuentes solo completan los campos autorizados, con procedencia y frescura.
- **Criterio de cierre**: ADR y fixtures de conflicto para cada familia de campos,
  incluyendo vacios, listas, valores divergentes, fuente caida y dato manual. No existe
  una prioridad global de fuente ni un overwrite silencioso.
- **Depende de**: resultados de [F1]; [F3] extiende la matriz si TMDb se aprueba.
- **Modelo sugerido**: Grande. Es una decision de producto y preservacion de datos.

#### [Q6] Crear una ficha compuesta sin altas manuales duplicadas
- **Alcance**: agrupar resultados externos solo mediante identidad fuerte y presentar
  una candidata unificada con procedencia por campo. Agregar una vez debe crear o
  enriquecer una unica ficha: por ejemplo, identidad/titulos estructurados desde IMDb y
  sinopsis desde Wikipedia. Si las fuentes no pueden vincularse con seguridad,
  permanecen separadas y se ofrece Comparar en lugar de combinarlas.
- **Criterio de cierre**: al agregar `tt0180396` desde cualquiera de sus nombres, la
  ficha conserva aliases espanol/original/ingles, links confirmados y la mejor
  descripcion disponible sin pedir tres altas ni una fusion manual; el historial,
  `locked_fields`, deshacer e idempotencia siguen protegidos.
- **Depende de**: [Q3], [Q5].
- **Modelo sugerido**: Grande. Une identidad, enrichment, procedencia, UX e historial.

### Frente: Fuentes externas y especializacion de anime

#### [F1] Prototipo opcional del indice oficial no comercial de IMDb
- **Alcance**: disenar un comando explicito que descargue/indexe localmente los TSV
  oficiales elegidos por el administrador; nunca incluirlos en el paquete ni activar
  la descarga por defecto. Medir disco, primera carga y actualizacion diaria.
- **Datos iniciales**: `title.basics` y `title.akas`; agregar
  `title.crew`/`title.principals`/`name.basics` solo si el prototipo demuestra que la
  instancia puede sostener el indice.
- **Regla de uso**: el prototipo mide y expone datos; la autoridad y el merge se
  deciden en [Q5], nunca mediante una prioridad global de IMDb. Manual y
  `locked_fields` siempre ganan.
- **Decision del owner (2026-08-29)**: uso personal/no comercial confirmado — el
  proyecto es abierto y funciona como una mini biblioteca personal, no como un
  servicio distribuido comercialmente. Atribucion resuelta: una mencion visible en
  "Acerca de" del panel de administracion citando el dataset no comercial de IMDb, mas
  conservar la procedencia (mismo mecanismo que ya usan los campos que llena Wikidata)
  en cualquier campo que este dataset complete, para que sobreviva a exportaciones
  JSON/CSV y a una futura coleccion compartida via [P2]. Sin bloqueo pendiente: listo
  para prototipar.
- **Modelo sugerido**: Grande. Toca licencias, almacenamiento, CLI, enrichment,
  procedencia y migraciones.

#### [F2] Autoridad de anime sostenible
- **Decision del owner (2026-08-29)**: Jikan (envoltorio no oficial de MyAnimeList)
  como fuente primaria en vivo — trade-off consciente y aceptado para un uso
  personal/no comercial, sin pedir permiso escrito a AniList por ahora.
  `anime-offline-database` se suma como secundaria: aunque quedo archivada el
  2026-07-04, su ultimo snapshot sigue siendo util como indice offline (mismo patron
  que el dataset no comercial de IMDb en [F1]), no como fuente en vivo.
- **Alcance ampliado respecto del original**: ya no es "elegir una fuente", es componer
  dos con roles distintos. Antes de programar el adaptador hace falta una pasada de
  diseño corta (mismo criterio que uso [Q3] para componer IMDb con el puente de
  Wikidata) que defina: que resuelve cada una (Jikan = busqueda y datos en vivo;
  `anime-offline-database` = cruce de IDs/aliases o respaldo si Jikan no responde), como
  se etiqueta la procedencia de cada dato, y que pasa cuando difieren.
- **Dependencias**: ninguna externa — la eleccion de fuente ya esta decidida. Wikidata
  multilingue sigue siendo el camino soportado mientras esto no se implemente.
- **Modelo sugerido**: Grande. Dos fuentes con roles distintos, no un adaptador simple.

#### [F3] Evaluar TMDb como fuente estructurada opcional
- **Alcance**: revisar licencia, atribucion, limites, uso de API key, campos disponibles
  e IDs cruzados. Comparar completitud y conflictos contra las fuentes actuales sobre
  el corpus sintetico, sin enviar catalogos personales.
- **Criterio de cierre**: ADR con decision integrar/no integrar, matriz de campos y
  costos operativos; solo si se aprueba, crear una tarea separada de adaptador.
- **Depende de**: —
- **Modelo sugerido**: Grande. Requiere investigacion legal y criterio de producto.

#### [F4] Permitir API keys opcionales por fuente
- **Idea del owner (2026-08-29)**: seguir usando fuentes abiertas/sin key como default
  (Wikipedia, Wikidata, FilmAffinity, IMDb via sugerencias, Jikan) tal como funcionan
  hoy, pero dejar que quien lo desee sume sus propias API keys para fuentes que las
  requieren (por ejemplo TMDb, si [F3] se aprueba). Nunca obligar a nadie a crear una
  cuenta o pagar para usar Movie Inbox.
- **Alcance a definir**: donde se guardan las keys (por instancia, por miembro), como
  se habilita/deshabilita una fuente segun haya o no key configurada, que pasa con el
  catalogo si se borra una key despues de enriquecer datos con ella, y como esto
  interactua con `locked_fields`/procedencia. El propio owner senala que esto necesita
  un analisis de diseño importante antes de poder asignarle un modelo de tamaño real.
- **Depende de**: nada tecnicamente, pero es el prerrequisito real si [F3] aprueba
  integrar TMDb (esa fuente no funciona sin key).
- **Modelo sugerido**: sin definir todavia — pendiente de un analisis de diseño previo.
  Prioridad baja, al final de la cola de este frente.

### Frente: Bibliotecas y curaduria

#### [C1] Disenar el contrato para grupos de 3+ duplicados
- **Alcance**: reemplazar la descomposicion C(n,2) por un caso de grupo sin implementar
  todavia el merge N-a-1. Definir identidad del caso, orden, conflictos, historial,
  deshacer y comportamiento si el grupo cambia durante la revision.
- **Criterio de cierre**: ADR y fixtures sinteticas de 3 y 4 entradas que permitan
  implementar sin decisiones pendientes.
- **Depende de**: [T2].
- **Modelo sugerido**: Grande. Es una decision de producto y consistencia de datos.

#### [C2] Implementar resolucion N-a-1 de duplicados
- **Alcance**: cola, detalle, comparador, auto-resolucion segura, historial y deshacer
  para el contrato aprobado en [C1]. Mantener cero merges automaticos con conflictos.
- **Criterio de cierre**: pruebas de dominio, servicio, HTTP y navegador para 3+ items,
  incluidos cambios concurrentes y rollback.
- **Depende de**: [C1].
- **Modelo sugerido**: Grande. Cambio transversal y sensible a perdida de datos.

### Frente: Privacidad e historial Git

#### [P2] Compartir disponibilidad fisica como coleccion de Club (contrato de [P1])
- **Alcance**: el admin puede elegir compartir, como una coleccion de Club mas (mismo
  mecanismo que ya usan las colecciones seguibles), los titulos que el escaneo local
  marca `en_catalogo`. Nunca viaja ruta, nombre de archivo, nota ni ningun otro estado
  operativo del escaneo — la coleccion solo expone lo que cualquier coleccion ya expone
  hoy (identidad del titulo), con la disponibilidad fisica como señal derivada.
- **Criterio de cierre**: opt-in explicito (por biblioteca o por instancia, a definir
  en diseño), pruebas negativas confirmando que ruta/archivo/nota/estado operativo
  nunca aparecen en el payload de Club aunque la coleccion este activa, y actualizar el
  invariante de privacidad de `CLAUDE.md` para reflejar el alcance exacto aprobado —
  recien al implementar esto, no antes.
- **Depende de**: [P1], decision ya tomada (ver Hecho, 2026-08-29).
- **Modelo sugerido**: Grande. Frontera critica de privacidad, aunque el contrato ya
  esta acotado.

### Frente: Superficie publica y despliegue

#### [W1] Definir contrato de presentacion publica
- **Alcance**: decidir landing estatica o endpoint de solo lectura, campos permitidos,
  cache, revocacion, rate limit y aislamiento respecto de sesiones/CSRF privados.
- **Criterio de cierre**: ADR, esquema versionado y threat model; ningun catalogo se
  publica por defecto.
- **Depende de**: [T4].
- **Modelo sugerido**: Grande. Define una nueva frontera de confianza.

#### [W2] Implementar landing publica opt-in
- **Alcance**: construir la presentacion aprobada en [W1] sin reutilizar endpoints ni
  tokens privados; controles owner para activar, previsualizar y revocar.
- **Criterio de cierre**: pruebas de aislamiento/autorizacion/cache y aceptacion visual
  responsive; instancia nueva permanece privada.
- **Depende de**: [W1].
- **Modelo sugerido**: Grande. Backend, seguridad y frontend publico.

#### [D1] Documentar HTTPS guiado para homeservers
- **Alcance**: receta soportada para reverse proxy (primero Nginx), certificados,
  headers, WebSocket si aplica, renovacion y diagnostico; Movie Inbox no termina TLS.
- **Criterio de cierre**: configuracion de ejemplo validada en un entorno descartable y
  checklist que no exponga el servicio accidentalmente.
- **Depende de**: —
- **Modelo sugerido**: Medio. Documentacion operativa con impacto de seguridad.

#### [W3] Disenar paquetes compartibles y sincronizacion entre homeservers
- **Alcance**: casos de uso, identidad de instancia, export/import firmado o manual,
  conflictos, revocacion y privacidad. No asumir un servicio central.
- **Criterio de cierre**: ADR y prototipo descartable sin red publica involuntaria;
  implementacion productiva queda como tarea posterior.
- **Depende de**: [W1] y contrato portable estable.
- **Modelo sugerido**: Grande. Distribucion, conflictos y modelo de amenazas.

### Frente: Clientes, integraciones y nuevos medios

#### [A1] Definir API versionada y sesiones para dispositivos
- **Alcance**: contrato minimo para login contra URL HTTPS elegida, catalogo,
  busqueda/detalle y cambios personales; expiracion/revocacion sin administrar Scanner.
- **Criterio de cierre**: OpenAPI/versionado, threat model y pruebas de compatibilidad
  servidor-cliente antes de iniciar una app.
- **Depende de**: [T4], [D1].
- **Modelo sugerido**: Grande. Prerrequisito de cualquier cliente externo.

#### [A2] Cliente Android basico
- **Alcance**: login seguro, lectura/busqueda/detalle y edicion de estado, fecha vista,
  puntaje y review; disponibilidad fisica solo lectura, sin offline ni administracion.
- **Criterio de cierre**: MVP contra la API de [A1], matriz de compatibilidad y pruebas
  de red/autenticacion/ciclo de vida.
- **Depende de**: [A1].
- **Modelo sugerido**: Grande. Proyecto cliente multiplataforma potencial.

#### [I1] Evaluar Radarr, Sonarr y Letterboxd
- **Alcance**: separar importacion, enlaces e inventario; revisar autenticacion,
  licencias, IDs, webhooks/rate limits y que datos personales saldrian de la instancia.
- **Criterio de cierre**: matriz y ADR por integracion; cada aprobada genera su propia
  tarea de adaptador.
- **Depende de**: [A1] para contratos externos estables y [L1] para inventario.
- **Modelo sugerido**: Grande. Tres productos con semanticas distintas.

#### [M1] Definir verticales de juegos y musica
- **Alcance**: investigar modelos, fuentes, disponibilidad y UX separados; no agregar
  valores a `kind` ni reciclar campos audiovisuales antes de la decision.
- **Criterio de cierre**: ADR por vertical con recomendacion avanzar/descartar y backlog
  independiente si se aprueba.
- **Depende de**: despues de estabilizar los frentes anteriores.
- **Modelo sugerido**: Grande. Descubrimiento de producto, no un cambio de enum.

---

## En curso

*(vacío)*

## Hecho

### Frente: Busqueda, comparacion y composicion de fuentes

#### [Q1] Mantener el contexto al refinar una busqueda de Comparar
`runSearch()` ahora ramifica por `collectionSearchMode` antes de resetear nada: en
`compare` reusa `searchCatalogForMerge(query)` (ya hacia busqueda local pura sin
`incomingResult`, solo no se llamaba desde aca) para refinar unicamente el catalogo
local, sin tocar `selectedManualIndex`/`manualResults` (el resultado externo fijo). En
`link` reusa `searchManual("all")` (ya evitaba `loadLocalSearchResults` fuera de modo
`browse`) para refinar solo fuentes externas, sin tocar `selectedExistingIdForSearch`/
`catalogMergeResults` (la ficha local fija). Cero resultados no saca del modo porque
ninguna de las dos funciones reusadas resetea `collectionSearchMode` por si misma.
`clearManualSearch()` (boton "Volver a la coleccion" y Escape) sigue siendo la unica
salida explicita, sin cambios.

Un segundo punto de reset independiente, no listado en el diagnostico original:
`restoreRoute()` forzaba `browse` en cada `popstate` porque el modo nunca viajaba en
la URL. Se sumaron `mode`/`link_id` a `COLLECTION_ROUTE_KEYS`; en `link` restaura con
fidelidad completa (la ficha local es un id estable); en `compare` restaura el modo y
re-busca localmente por texto, aceptando como limite conocido que el resultado externo
puntual (efimero, no tiene id estable) no se reconstruye cruzando una navegacion real
— documentado en el plan, no una omision.

Verificado con 2 pruebas de navegador nuevas (externo→local conservando el resultado
fijo hasta con cero resultados; local→externo conservando la ficha fija, incluida
navegacion atras real del browser) mas toda la suite existente sin tocar un assert:
15 pruebas de navegador, 334 pruebas unitarias, Ruff, formato, mypy y `compileall`
en verde.
2026-08-26.

#### [Q2] Hacer reproducible el diagnostico multilenguaje por fuente
El contexto `external` de Search Lab nunca ejecutaba codigo real de `external/*.py`
— puntuaba una lista de candidatos ya escrita a mano, sin paso de construccion de
consulta ni fallback. `tests/test_layering.py` prohibe importar `external` desde
`application/`, asi que el mecanismo nuevo (`search_lab/recorded_responses.py`) vive
en `search_lab/`, no ahi: parchea `fetch_text` en dos lugares, no uno —
`external.common.fetch_text` cubre IMDb/Wikipedia/Wikidata (que resuelven `fetch_text`
via los globals de `common.py` en tiempo de llamada), pero FilmAffinity hace
`from ... import fetch_text` y llama el nombre suelto, un binding independiente que
solo se corrige parcheando `external.filmaffinity.fetch_text` tambien — confirmado
leyendo como `test_external_filmaffinity.py` ya lo hace asi, no como el diseño
original del agente de plan asumia.

`search_lab/external_diagnostics.py` corre los adaptadores reales contra las
respuestas grabadas, puntua cada candidato crudo con el mismo `external_result_score`
que ya usa produccion, y distingue "la fuente no la devolvio" de "la descarto por
umbral" de "aceptada fuera del top-k" — sin reimplementar el filtro de
`registry.py::_rank_batch`. `fallback_used` sale de las URLs efectivamente pedidas
(gratis, sin instrumentar los adaptadores): confirmado que Wikipedia tiene su propio
fallback (`_resolve_title`, `redirects=1&titles=`), no solo IMDb con el puente de
Wikidata — hallazgo nuevo, no estaba en el diagnostico original. `evaluate_gate`
(antes `_evaluate_gate`, promovida publica) se reusa tal cual para el nuevo umbral
`recall_at_5`, sin duplicar "pasa si se cumple cada umbral declarado".

Corpus nuevo (`external_diagnostics_v1.json`, separado de `v1.json` — formas
incompatibles, ver el hallazgo de layering) con 3 casos reales verificados en vivo:
Addio zio Tom (dispara el puente de Wikidata solo cuando hace falta — "Goodbye Uncle
Tom" no lo necesita, ya puntua 100 directo), City of God (titulo conocido en ingles
distinto del original), y The Fly 1986 (descarta el original de 1958 y la secuela de
1989 por año, no solo por texto). Fanny & Alexander y "Verano 1993 (2017)" no
necesitaron el harness nuevo — ya pasaban contra candidatos puntuados a mano, sumados
a `v1.json` en la fase 0 de este mismo trabajo, junto con la caracterizacion del
hallazgo de `"Verano 1993"` sin calificar (ver `[Q7]` mas abajo, en el frente de
bibliotecas).

Nuevo subcomando `movie-inbox search-lab external-diagnostics --enforce`, mismo
patron que `run`/`compare`; segundo paso agregado al job `search-lab` ya existente en
CI. Verificado con 12 pruebas nuevas de la logica de diagnostico (incluida una que
parchea `urlopen` para confirmar que "corre sin red" es algo que un test realmente
verifica, no solo cierto por omision), 7 del mecanismo de respuestas grabadas
(concurrencia real via `ThreadPoolExecutor`, restauracion del parche tras una
excepcion, el caso de FilmAffinity que expuso el bug de un solo punto de parche), y 3
de cobertura CLI — mas la suite completa sin tocar un assert existente.
2026-08-26.

#### [Q7] Desambiguar un ano sin calificar dentro del titulo
Sin una referencia de titulos no hay forma de saber de antemano si un token de año
ambiguo (`"Verano 1993"`) desambigua o es parte del titulo, asi que
`parse_search_query` dejo de elegir una sola lectura: `SearchIntent` conserva la
primaria sin cambios (`.title`/`.year`, igual que siempre para "Heat 1995" y para
cualquier consulta con 0 o 2+ tokens de año) y suma `alternate_title`/
`alternate_title_key` — la lectura sin dividir — solo cuando el split fue
genuinamente ambiguo. `external_result_score` (`domain/search.py`) y
`_catalog_search_score` (`application/search_service.py`, la ruta paralela de
Catálogo/Comparar — problema y fix independientes, `_catalog_search_score` no llama a
`external_result_score`) puntúan contra las dos lecturas y toman el máximo, pero solo
si la alternativa alcanza `SearchStrategy.ambiguous_year_alternate_floor` (82.0, el
mismo corte que `text_match_score` ya usa para su nivel "contains") — sin ese piso, la
alternativa podria rescatar un candidato de año equivocado pero titulo parecido
(verificado que no lo hace: `"It 2017"` contra `it-1990` sigue en 25.0).

Criterio de cierre mas modesto que "gana el ranking": la obra real deja de
descartarse por debajo del umbral de aceptacion (13.0 → 100.0 en el caso Verano), no
necesariamente supera a un homonimo con match exacto de titulo+año (ese homonimo
sigue en 112.0, legitimamente — sin señal para preferir uno u otro, los dos quedan
visibles para revision humana, que es la invariante real). Confirmado leyendo
`domain/matching.py`/`application/library_service.py` que ninguno importa
`domain.search` — el gate de auto-match y la clasificacion real de Scanner quedan
fuera del alcance de este fix por completo, no solo en la practica sino en el codigo.

Fix chico adicional, mismo problema en otro lugar: el prefiltro de catalogos grandes
(`_catalog_search_positions`, ≥200 items, sin cobertura de tests hasta ahora) elegia
posiciones por el termino exacto mas raro de un solo pool de terminos: mezclar ahi los
terminos de la lectura alternativa arriesgaba que un termino raro solo-alternativo
(`"1993"`) ganara la seleccion y excluyera candidatos primarios legitimos que no lo
comparten. Se eligen posiciones mas raras por interpretacion por separado y se unen,
protegido con un caso nuevo de 250+ items.

Caso nuevo en el corpus dorado (`external-verano-1993-unqualified-year`, contexto
`external`) protegido por `movie-inbox search-lab run --enforce` (26→29 casos totales,
26→26 estrictos — las 3 fallas estrictas restantes son preexistentes, confirmado
corriendo el gate antes de este cambio: mismos 3 casos de identidad de remakes, sin
relacion con año). Ademas, 2 pruebas de caracterizacion de `tests/test_search.py`
pasaron a afirmar el comportamiento corregido en vez de solo documentarlo, y 2 pruebas
nuevas en `tests/test_search_service.py` (rescate vía catalogo, y el mismo rescate
cruzando el prefiltro de catalogos grandes).
2026-08-28.

#### [Q3] Planificador acotado de consultas multilenguaje
IMDb tenia un puente propio a Wikidata para rescatar resultados de baja puntuacion con
alias confirmados, pero `if (results and ...)` (`imdb.py:71-78`) cortaba en el primer
operando falso — una sugerencia vacia nunca llegaba a llamar
`fetch_wikidata_title_matches`. Wikipedia y FilmAffinity no tenian ningun mecanismo de
respaldo propio fuera del fan-out en/es existente de Wikipedia.

Diseno descartado antes de escribir codigo: una orquestacion nueva en `registry.py`
(segunda ronda de `ThreadPoolExecutor` solo para fuentes debiles). Un agente Plan
encontro 2 problemas reales verificando el codigo real: `_run_adapter` ya actualiza
`self._health` internamente sin relanzar, asi que capturar la excepcion en la ronda
nueva no evita que el estado de salud quede pisado por una race entre variantes
concurrentes de la misma fuente; y el harness de diagnostico de [Q2]
(`search_lab/external_diagnostics.py`) llama a los adaptadores directo, nunca pasa por
`registry.py` — un mecanismo ahi hubiera quedado invisible para su propio gate.

Diseno final: cada adaptador se auto-contiene, mismo patron que IMDb ya tenia.
`registry.py` no cambio en absoluto. IMDb ahora tambien dispara el puente con
sugerencia vacia, sintetizando una fila nueva por cada alias confirmado (antes solo
enriquecia filas que la sugerencia ya habia devuelto) — `fetch_wikidata_title_matches`
(`external/wikidata.py`) gano `year`/`kind` gratis, reusando `wikidata_kind`/
`wikidata_claim_year` contra `claims` ya en memoria, sin llamada de red nueva.
Wikipedia y FilmAffinity ganan un mecanismo compartido nuevo,
`external/query_variants.py::alias_variants()`: hasta 2 alias confirmados por
Wikidata como reintento cuando su propia busqueda vuelve vacia, ordenados por
capacidad de fuente (FilmAffinity prioriza `spanish_title`, Wikipedia prioriza
`original_title` porque ya cubre en/es por si solo) y con un piso de confianza
textual reusado de `EXTERNAL_RELEVANCE_THRESHOLD` — nunca traduce texto libre ni
concatena director/reparto, por construccion. "Idioma preferido de la instancia" es
la constante `PREFERRED_ALIAS_LANGUAGES = ("es", "en")`, decision explicita del owner
tras confirmar que no existe ningun mecanismo de configuracion por instancia en el
proyecto y que ningun criterio de cierre exige que sea editable.

Presupuesto explicito: maximo 2 variantes extra por fuente debil, timeout de 4s para
esas llamadas (mitad del default de 8s). Un fallo de variante nunca invalida las
demas (try/except aislado por intento) ni queda cacheado como vacio valido (la cache
de `registry.py` sigue sin tocar, con su TTL corto de 30s para vacio ya existente).

Verificado con 12 pruebas nuevas contra codigo real (sintesis de IMDb, alias/año/tipo
de Wikidata, reintento de Wikipedia/FilmAffinity, ordenamiento y piso de
`query_variants.py`), 2 pruebas de [Q2] arregladas por el mismo motivo que un gap de
fixture encontrado en esa misma tarea, y ambos gates de Search Lab en verde sin
regresiones (26/29 casos estrictos, mismos 3 preexistentes sin relacion con esta
tarea). Limitacion documentada a proposito: el corpus de diagnostico de [Q2] no gano
casos nuevos para el camino de Wikipedia/FilmAffinity — construir uno contra datos
reales resulto mas dificil de lo esperado (la busqueda de Wikipedia rara vez vuelve
genuinamente vacia contra titulos reales conocidos) y se paro la exploracion en vivo
antes de gastar mas cupo de API publica en algo no critico; la logica queda cubierta
por pruebas unitarias directas contra codigo real, no por el corpus con datos en vivo.
2026-08-29.

#### [Q4] Agregar busqueda por direccion como descubrimiento explicito
`directors: list[str]` ya existia en el modelo (poblado desde Wikidata P57 y
FilmAffinity) pero `_search_values()` lo excluia deliberadamente del buscador
principal. `"director:Jacopetti"` ahora se reconoce como su propio tipo de consulta:
`parse_search_query()` hace un early-return con `director_query`/`director_query_key`
seteados y titulo/año vacios, en vez de leerse como una consulta de titulo vacia.

Hallazgo real durante el diseño, no asumido: el primer diseño agregaba el nombre del
director como un fallback mas en la cadena de cada adaptador dando por sentado que el
resto del pipeline externo seguia funcionando. Un agente Plan verifico que no
alcanzaba: `registry.py::_rank_batch` puntua cada resultado con
`external_result_score()`, que compara texto de consulta contra TITULO — un apellido
de director no aparece en el titulo de una pelicula por diseño, y el caso real
("Jacopetti" contra "Mondo Cane") confirmo que el score cae muy por debajo del umbral
de aceptacion. Sin arreglar esto, la busqueda externa por director hubiera devuelto
cero resultados siempre, en silencio. `external_result_score()` gano un branch
explicito: en modo director, confia en el ranking propio de la fuente para cualquier
candidato con titulo reconocible, en vez de re-puntuar localmente. Localmente,
`search_catalog_items()` delega a `_search_by_director()`, una funcion separada que
nunca toca `_catalog_search_score`/`_search_values` — "nunca mezclarse con el score de
titulo" se cumple por construccion, no por un flag dentro del scoring compartido.
Ambos caminos reusan `text_match_score`/`EXTERNAL_RELEVANCE_THRESHOLD` ya existentes.

Seguridad verificada por lectura directa: `domain/matching.py` no tiene ninguna
referencia a `director`. Confirmado en vivo (servidor real, catalogo sintetico) que
dos obras distintas del mismo director no producen match ni fusion automatica, y que
`rank_catalog_candidates()`/`_candidate_query()` nunca puede emitir `director:...` por
si solo, asi que el flujo automatico de Comparar jamas entra en modo-director. IMDb
contribuye poco o nada para un nombre de director suelto (su endpoint descarta nodos
de persona, el puente de Wikidata exige un IMDb id con forma `tt...`) — documentado
como limite estructural aceptado, no perseguido con logica nueva; Wikipedia si aporta
valor real, confirmado en vivo encontrando y etiquetando la biografia del propio
director.

Toggle nuevo en Coleccion ("Buscar por direccion"), mismo patron que el checkbox
existente de fuentes externas — antepone `director:` al texto ya escrito, asi que
nadie necesita conocer la sintaxis para usarla. Verificado con 17 pruebas nuevas
(parseo, scoring en modo director, `_search_by_director`, fallback en los 3
adaptadores, seguridad de `decide_match`, etiquetado HTTP) mas un servidor real con
catalogo sintetico probado a mano: busqueda local y Wikipedia en vivo, ambas
etiquetando correctamente "coincide por direccion". Sin prueba de navegador
permanente nueva — la verificacion manual (red real, ambos caminos) ya cubrio mas
terreno que una mockeada tipica, y el cambio es un toggle mas una etiqueta, no una
maquina de estados nueva como el trabajo de modo comparar/vincular de [Q1] que
justifico cobertura Playwright nueva ahi. Suite completa, ambos gates de Search Lab,
Ruff y mypy estricto en verde sin regresiones.
2026-08-29.

### Frente: Tipado y capacidad de entrega

#### [T1] Primera ampliacion estricta: contratos, identidad y privacidad de Application
El gate obligatorio pasa de 18 a 28 modulos estrictos: suma contratos de repositorio y
servicios de autenticacion, miembros y privacidad. La lista queda protegida y
sincronizada entre `pyproject.toml`, PowerShell, shell y CI. El unico defecto del corte
se corrigio en la frontera compartida: `shared_watch_history()` acepta una `Sequence`
covariante en vez de exigir una lista invariante. No se agregaron ignores ni se bajo el
nivel de mypy. El diagnostico amplio de `src` baja de 174 a 173 avisos; los restantes
siguen planificados por capas en [T2-T5]. Verificado con mypy estricto sobre los 28
modulos, 334 pruebas, Ruff, formato, compileall, parser de PowerShell y
`git diff --check`.
2026-08-25, commit `4b0f19e`.

#### [T2] Tipar el resto de Application
Los servicios de catalogo, importacion, scanner, curaduria, home, busqueda y evaluacion
quedaron bajo mypy estricto. Se corrigieron contratos invariantes para aceptar
`Sequence`, se tiparon payloads de decision y procedencia, y se mantuvieron las
dependencias de infraestructura fuera de Application. Verificado sobre los 22 modulos
de la capa y sus pruebas enfocadas.
2026-08-25, commit `2114cf6`.

#### [T3] Tipar Infrastructure y External
Los repositorios, parsers y adaptadores externos quedaron alineados con los contratos
de Application. Las respuestas JSON remotas permanecen como `object` hasta validar su
forma y luego se normalizan con helpers compartidos; IMDb, Wikipedia y Wikidata ya no
suponen listas o diccionarios confiables antes de comprobarlos. Verificado sobre los 27
modulos de ambas capas y sus pruebas de red, esquema y persistencia.
2026-08-25, commit `d0f4b47`.

#### [T4] Tipar Web y CLI
FastAPI, payloads HTTP, seguridad, dependencias, routers y comandos CLI completaron el
gate. `strict = true` queda como regla global de mypy y todo `src/movie_inbox` —103
modulos de producto— pasa sin overrides por paquete ni `ignore_errors`.
2026-08-25, commit `c32c25a`.

#### [T5] Evaluar y cerrar el tipado de tests
El contrato obligatorio ahora ejecuta `mypy src/movie_inbox tests` en PowerShell, shell
y CI, protegido por una prueba de empaquetado. Los fixtures corrigen opcionales,
genericos, falsos protocolos e inputs remotos ambiguos. Los cuerpos de todos los tests
se verifican; solo se permiten helpers sin firma completa cuando imitan callbacks
dinamicos y, dentro de `tests.browser`, `attr-defined` por los recursos que
Playwright/unittest instala en `setUpClass`. No hay `ignore_errors`. Verificado sin
hallazgos sobre 139 archivos.
2026-08-25, commit `07d8850`.

### Frente: Privacidad e historial Git

#### [S1] Decidir la purga del catalogo personal del historial
Lucas confirmo la purga tras verificar que `scripts/scripts/catalogv4.json` seguia
alcanzable desde `origin/master` (commits `a21314a` y `ad53ec9`) en un repositorio
publico. Decision: purgar, no conservar la historia.
2026-08-26.

#### [S2] Ejecutar y verificar la purga del historial
`git filter-branch --index-filter 'git rm -r --cached --ignore-unmatch ...'` sobre un
clon espejo aislado (nunca el repositorio de trabajo), sin abrir el archivo en ningun
momento. Backup completo (`git bundle create --all`) guardado antes de reescribir.
Verificado con `git rev-list --objects` contra las referencias reales (rama y tags,
excluyendo los refs de respaldo de `filter-branch`) que el blob queda inalcanzable.
128 commits y 5 tags (`v0.2.0`, `v0.2.1`, `v0.3.0`, `v0.4.0`, `v0.5.0`; `v0.1.0` es
anterior al archivo y no cambio) reescritos con force-push coordinado. El repositorio
de trabajo local se resincronizo (`fetch` + `reset --hard` + retag) sin perder cambios
pendientes reales, que se conservaron con `git stash` durante la resincronizacion.
- **Fuera de alcance, ejecutado aparte**: el archivo sigue en disco, sin tocar, fuera
  de Git — es dato personal real de Lucas.
2026-08-26.

#### [P1] Decidir visibilidad opcional de archivos para miembros
Decision: la regla dura se mantiene para ruta, nombre de archivo, nota y estado
operativo del escaneo — ninguno de los cuatro se expone jamas en una vista compartida,
sin excepcion para el owner, exactamente como ya fija el invariante de `CLAUDE.md`. Se
aprueba un unico carve-out acotado: el admin puede elegir compartir, como una coleccion
de Club mas (mismo mecanismo que ya usan las colecciones seguibles), los titulos que el
escaneo local marca `en_catalogo` — disponibilidad fisica derivada, nunca el archivo o
la ruta que la origino. Contrato exacto para implementar, en [P2].
2026-08-29.

### Frente: Enriquecimiento Wikidata

#### [E6] Extraer campos gratis del Wikidata ya descargado
La opción B incorpora los cinco campos acordados: `duration_minutes` desde P2047,
`countries` desde P495, `original_languages` desde P364, `producers` desde P162 y
`composers` desde P86. Duración es un entero positivo opcional en minutos; los otros
cuatro campos son listas multivalor. La extracción reutiliza la entidad y el batch de
labels existentes, respeta rangos preferidos, convierte minutos/segundos/horas y no
entra en la evidencia de identidad ni en el ranking de búsqueda.

Los campos atraviesan `CatalogItem`, procedencia y bloqueos, merge manual/automático,
API, importación y exportación. El contrato portable migra de JSON v6 a v7 con defaults
sin pérdida y SQLite migra de v4 a v5 con una columna nullable para la duración; las
listas reutilizan `metadata_values`. Verificado con 325 pruebas unitarias, 13 pruebas
reales de navegador, Ruff, mypy, compilación y Search Lab en verde.
2026-08-24, commit `9f9ebb2`.

### Frente: Cierre de coherencia de interfaz (v0.5.0)

Los 4 hallazgos que dejo el gate de cierre de Fase 5 (critica del 2026-08-22, 29/40)
tenian un ranking de mas simple a mas dificil. Los 2 mas dificiles (historial/deshacer
de Scanner, desambiguar duplicados) ya estan cerrados — ver `docs/roadmap.md` y las
entradas fechadas 2026-08-22 en `prompt-movie-inbox.md`. Los 2 mas simples y el caso
borde que la fase de desambiguacion dejo explicitamente pendiente quedaron cerrados en
este incremento. Los 4 se agrupan aca como el contenido de v0.5.0 (ver
`docs/roadmap.md`) — un incremento chico a proposito, para probar bien lo construido en
v0.4.0 antes de seguir.

#### [V5-1] `aria-live` en el estado de decision del comparador de fusion
- **Archivos**: `src/movie_inbox/web/static/index.dialogs.html` (lineas 276-289, el
  `<footer class="merge-comparator-footer">` del dialogo de fusion).
- **Que hacer**: envolver el `<div>` de la linea 281 (que contiene `#mergeDecisionStatus`
  y `#mergeDecisionMeta`, ambos actualizados juntos desde `core/merge.js`) con
  `aria-live="polite"` en ese mismo `<div>` — no en cada hijo por separado, para que un
  lector de pantalla anuncie un solo cambio combinado en vez de dos anuncios sueltos.
  Mismo patron que ya usa `#mergeComparatorFeedback` cuatro lineas arriba (linea 277,
  tambien `aria-live="polite"`) — copiar ese criterio, no inventar uno nuevo. Agregar
  ademas `aria-describedby="mergeDecisionStatus"` al boton `#confirmReviewedMerge`
  (linea 287) para que un lector de pantalla enfocado en el boton conozca el estado
  actual de la decision. No hace falta tocar `core/merge.js`: el contenido ya se
  actualiza via `textContent`, alcanza con marcar el contenedor una vez.
- **Depende de**: —
- **Modelo sugerido**: Chico. Dos atributos HTML, patron ya usado 4 lineas arriba en el
  mismo archivo, sin logica nueva.
- **Verificacion**: `scripts\check.ps1` en verde; confirmar a mano en el navegador que
  el atributo sobrevive despues de que `merge.js` reemplaza el `textContent` del `<div>`.
- **Cierre**: el estado combinado usa una unica region `aria-live` y el boton final la
  referencia con `aria-describedby`; cubierto por HTTP y Playwright real.
  2026-08-24, commit `ad53ec9`.

#### [V5-2] Buscador de texto libre en la cola de Curaduria
- **Archivos**: `src/movie_inbox/web/static/index.inbox-curation.html` (nav de tabs,
  lineas 2-18, agregar el input ahi), `src/movie_inbox/web/static/js/core/fields.js`
  (registrar el campo, junto a `curationQueue` en la linea 113),
  `src/movie_inbox/web/static/js/core/bootstrap.js` (wireo, junto a la linea 175),
  `src/movie_inbox/web/static/js/surfaces/inbox-curation.js` (`visibleCurationCases()`
  linea 268, nueva funcion `searchCurationQueue`), `src/movie_inbox/web/static/css/curation.css`.
- **Que hacer**: Scanner ya tiene exactamente este patron resuelto — `#scannerQueueSearch`
  (`index.inbox-scanner.html:27-30`, un `<label class="scanner-queue-search">` con
  `<span class="sr-only">` + `<input type="search">`), el estado `scannerQueueQuery`
  (`inbox-scanner.js:22`), el filtro por texto dentro de `visibleScannerQueue()`
  (`inbox-scanner.js:242-258`, normaliza con `normalizeText` y compara contra
  titulo/año/tipo/nombre de archivo/ruta/biblioteca) y `searchScannerQueue(event)`
  (`inbox-scanner.js:268-271`) wireado en `bootstrap.js:180`. Portar el mismo patron a
  Curaduria 1 a 1: agregar el mismo bloque de input (adaptando la clase a
  `.curation-queue-search` y el id a `curationQueueSearch`) dentro de
  `index.inbox-curation.html`, cerca de la nav de tabs; agregar
  `export let curationQueueQuery = "";` en `inbox-curation.js`; sumar el mismo filtro
  por texto dentro de `visibleCurationCases()` (que hoy solo filtra por
  `curationFilter`, no por texto) usando los campos disponibles de `entry.primary`
  (titulo, año, tipo) — mirar `curationQueueItem()` en la linea 394 para confirmar que
  campos trae cada `entry`; agregar `searchCurationQueue(event)` identica a la de
  Scanner; registrar el campo en `fields.js` y wirear el evento `input` en
  `bootstrap.js`, junto a `handleCurationClick`. En CSS, copiar la regla
  `.scanner-queue-search` de `scanner.css` adaptada a `.curation-queue-search` en
  `curation.css`.
- **Depende de**: —
- **Modelo sugerido**: Medio. Mecanico y con un patron de referencia completo ya
  funcionando, pero toca 5 archivos distintos.
- **Verificacion**: catalogo sintetico con varios casos en Curaduria, confirmar que
  escribir en el buscador filtra la cola igual que en Scanner, incluidos los acentos
  (`normalizeText` ya los maneja). `scripts\check.ps1` en verde.
- **Cierre**: busqueda por titulo, ano y tipo portada desde Scanner, con prueba de
  navegador que encuentra `Akira` al escribir `akira` sin acento.
  2026-08-24, commit `ad53ec9`.

#### [V5-3] Navegacion por flechas del teclado en la cola de Curaduria
- **Archivos**: `src/movie_inbox/web/static/js/surfaces/inbox-curation.js` (nueva
  `moveCurationQueueSelection`, nueva `focusSelectedCurationItem`),
  `src/movie_inbox/web/static/js/core/bootstrap.js` (wireo, junto a la linea 175),
  `src/movie_inbox/web/static/css/curation.css` (confirmar que ya alcanza con el
  `:focus-visible` de `.curation-queue-item` que el pase de `polish` de Fase 5 ya
  agrego — no deberia hacer falta CSS nuevo).
- **Que hacer**: portar `moveScannerQueueSelection`/`focusSelectedScannerItem`
  (`inbox-scanner.js:281-296`) a Curaduria, reusando el estado que ya existe ahi
  (`curationFilter`, `selectedCurationCaseId`, `visibleCurationCases()`,
  `renderCuration()`, `curationHistory` — no hace falta crear ninguno nuevo). Ojo con
  un detalle: la fila de Curaduria marca "seleccionada" con la clase `selected`
  (`curationQueueItem()`, linea 402: `` `curation-queue-item ${selected ? "selected" :
  ""}` ``), **no** `active` como en Scanner — `focusSelectedCurationItem` tiene que
  buscar `.curation-queue-item.selected`; copiar el selector de Scanner tal cual haria
  foco en el elemento equivocado (ninguno, silenciosamente, sin error visible). Igual
  que `moveScannerQueueSelection` resuelve para la pestaña "Actividad"
  (`scannerQueueFilter === "history" ? scannerHistory : visibleScannerQueue()`), la
  version de Curaduria tiene que ramificar sobre `curationFilter === "history"` con
  `curationHistory` — Scanner tuvo un bug real por olvidar esta rama (ver la entrada
  fechada 2026-08-22 en `prompt-movie-inbox.md`), no repetirlo aca. Wirear `keydown`
  sobre `fields.curationQueue` (no sobre `fields.inboxView`, que ya tiene el `click`
  generico) en `bootstrap.js`.
- **Depende de**: — (independiente de [V5-2]; si se resuelven en sesiones distintas,
  avisar de todas formas que ambas tocan `bootstrap.js` y `fields.js` para evitar un
  conflicto de merge chico).
- **Modelo sugerido**: Medio. Sin decisiones de diseño pendientes (ya se decidio aca
  duplicar el patron de Scanner adaptado, no generalizar un helper compartido — la
  cantidad de estado especifico de cada modulo no lo justifica), pero hay que prestar
  atencion a los 2 detalles señalados arriba para no introducir un bug silencioso.
- **Verificacion**: catalogo sintetico con 3+ casos en Curaduria, confirmar que las
  flechas mueven la seleccion igual que en Scanner, incluida la pestaña "Actividad".
  `scripts\check.ps1` en verde.
- **Cierre**: flechas verticales y horizontales recorren circularmente pendientes e
  historial, conservando foco sobre `.curation-queue-item.selected`; verificado en
  ambas ramas con Playwright. 2026-08-24, commit `ad53ec9`.

#### [V5-4] Señal de respaldo cuando archivo, fuente y fecha tambien empatan entre duplicados
- **Archivos**: `src/movie_inbox/web/static/js/surfaces/inbox-curation.js`
  (`curationQueueItem()` linea 394, `curationRecord()` linea 472),
  `src/movie_inbox/web/static/js/core/merge.js` (`renderMergeComparator()` linea 157,
  `mergeEntrySummary()` linea 199).
- **Que hacer**: caso borde dejado pendiente al cerrar la fase de desambiguacion de
  duplicados (ver la entrada fechada 2026-08-22 en `prompt-movie-inbox.md`): cuando dos
  casos duplicados con mismo titulo/año ademas comparten archivo local, fuente y fecha
  de alta, las 3 señales que ya se muestran no alcanzan para diferenciarlos. Si ademas
  todos los campos personales coincidieran, "Resolver duplicados claros" ya los
  fusiona solos sin que el usuario los vea — asi que este caso solo aparece cuando hay
  un conflicto real de datos personales (ej. dos puntajes distintos) y el usuario
  necesita alguna forma de saber cual fila es cual. Resolucion propuesta: cuando las 3
  señales existentes coinciden por completo entre los dos lados de un caso, agregar un
  ultimo recurso puramente posicional — "Duplicado 1 de 2" / "Duplicado 2 de 2" (o
  redaccion similar), calculado en el momento segun el orden en que ya llegan
  agrupados, sin necesidad de guardar ningun id nuevo. Mostrar esta numeracion
  unicamente cuando las 3 señales coinciden por completo — si al menos una difiere, no
  hace falta.
- **Depende de**: —
- **Modelo sugerido**: Medio. Toca los mismos 4 puntos de renderizado que la fase 1 de
  desambiguacion (mismo patron, mismo estilo de cambio aditivo), pero la regla de
  producto ya esta decidida aca.
- **Verificacion**: catalogo sintetico con 2 "Heat" identicas en archivo/fuente/fecha
  pero con rating distinto (9 y 3) — confirmar que la cola y el comparador muestran
  ahora una numeracion en vez de dos filas indistinguibles. `scripts\check.ps1` en
  verde.
- **Cierre**: el fallback `Duplicado 1 de 2` / `Duplicado 2 de 2` aparece unicamente
  cuando empatan las tres senales, en cola, detalle, titulo y resumen del comparador;
  verificado con un par sintetico de `Heat`. 2026-08-24, commit `ad53ec9`.

---

### Frente: Higiene de repositorio

Encontrado al mover `scripts/` a `codigoLegacy/` en la sesion del 2026-08-22 (ver
`prompt-movie-inbox.md`), marcado pero no tocado en su momento por estar fuera del
pedido puntual de esa sesion. Las 3 tareas son independientes entre si.

#### [H1] Borrar `check-output.txt` (salida de instalacion vieja, trackeada por error)
- **Archivos**: `check-output.txt` (raiz del repo, ~770 KB), `.gitignore`.
- **Que hacer**: confirmado leyendo el contenido — es la salida cruda de una corrida
  vieja de instalacion/tests (lineas de `pip install`, no datos personales),
  commiteada por accidente el 2026-08-10 (commit visible en `origin/master`).
  `git rm check-output.txt`; agregar `/check-output.txt` a `.gitignore` para que una
  futura corrida de `scripts\check.ps1`/`check.sh` que alguien redirija a ese nombre no
  lo vuelva a trackear.
- **Depende de**: —
- **Modelo sugerido**: Chico.
- **Nota**: ya esta en `origin/master`; borrarlo solo lo saca de commits futuros, sigue
  recuperable del historial si hiciera falta. No requiere reescribir historia.
- **Cierre**: archivo eliminado y `/check-output.txt` agregado a `.gitignore`.
  2026-08-24, commit `ad53ec9`.

#### [H2] Borrar `scripts/LICENSE` (duplicado exacto de `LICENSE`)
- **Archivos**: `scripts/LICENSE`.
- **Que hacer**: confirmado byte a byte identico a la `LICENSE` GPLv3 de la raiz
  (`diff` sin salida). Buscar primero si algo referencia esta ruta (`grep -r
  "scripts/LICENSE"` sobre el repo) — no deberia haber nada, pero confirmarlo antes de
  borrar. `git rm scripts/LICENSE`.
- **Depende de**: —
- **Modelo sugerido**: Chico.
- **Cierre**: hash identico confirmado, referencias revisadas y copia eliminada.
  2026-08-24, commit `ad53ec9`.

#### [H3] Cerrar el hueco de `.gitignore` que dejo trackeado un catalogo personal anidado
- **Archivos**: `.gitignore` (patrones `/scripts/*.json`, `/scripts/*.csv`,
  `/scripts/*.txt`).
- **Que hacer**: estos 3 patrones no alcanzan una subcarpeta anidada como
  `scripts/scripts/`, asi que `scripts/scripts/catalogv4.json` (catalogo personal
  real) quedo trackeado desde el commit `a21314a` (2026-08-01) y ya esta en
  `origin/master`. Cambiar los 3 patrones a su forma recursiva (`scripts/**/*.json`,
  `scripts/**/*.csv`, `scripts/**/*.txt`, sin la barra inicial, para que apliquen a
  cualquier profundidad) y correr `git rm --cached scripts/scripts/catalogv4.json`
  (sin `-f`, **sin abrir ni leer el archivo** — es dato personal real, la regla de
  `CLAUDE.md` aplica igual aca; el archivo sigue en disco, solo deja de trackearse).
  Revisar con `git ls-files scripts/` si este mismo hueco dejo pasar algun otro
  archivo personal anidado antes de dar la tarea por cerrada.
- **Depende de**: —
- **Modelo sugerido**: Chico — cambio de patron + `git rm --cached`, sin necesidad de
  abrir el archivo.
- **Importante, fuera del alcance de esta tarea**: esto solo detiene el tracking hacia
  adelante. El archivo sigue en el historial de git y ya llego a `origin/master` desde
  2026-08-01 — purgarlo de la historia (`git filter-repo` o similar) requiere reescribir
  historia y probablemente un force-push a un repo con datos personales ya expuestos en
  el remoto. Es una decision de Lucas, no de esta tarea — ver `docs/roadmap.md`.
- **Cierre**: patrones recursivos aplicados y el unico catalogo anidado que habia
  escapado dejo de estar trackeado sin abrirse ni borrarse del disco. La purga del
  historial sigue deliberadamente fuera de alcance. 2026-08-24, commit `ad53ec9`.

---

### Frente: Bibliotecas y curaduria

#### [L1] Reglas de exclusion configurables por biblioteca
`scan_media_files()` (`infrastructure/library_scanner.py`) ya aceptaba un parametro
`excluded_dirs` ademas de los defaults seguros (`extras`/`sample`/etc.), pero
`ManagedLibraryService.execute_run()` nunca se lo pasaba — el punto de extension existia
sin nada conectado a una biblioteca real. Un agente Plan encontro una violacion de
layering real en el primer diseño: la validacion de patrones y el predicado de
coincidencia no podian vivir en `infrastructure/library_scanner.py` si
`application/library_service.py` necesitaba reusarlos para calcular que inventario
existente quedaria oculto por una regla nueva (`tests/test_layering.py` prohibe ese
import por AST) — fueron a `domain/libraries.py`, junto a
`normalize_library_name`/`normalize_missing_ratio` que ya vivian ahi.

`domain/libraries.py` gano `validate_exclusion_pattern` (normaliza NFC, recorta,
rechaza vacio/demasiado largo/con `/` o `\`/solo asteriscos), `matches_excluded_pattern`
(NFC + casefold + `fnmatch.fnmatchcase`, nunca compila regex) y
`path_matches_excluded_pattern` (solo componentes de directorio del path relativo,
nunca el nombre de archivo) — mas `ManagedLibrary.exclusion_patterns` y
`LibraryScanRun.newly_excluded`. `library_scanner.py` cambio una sola linea (coincidencia
exacta por `matches_excluded_pattern`): como ningun nombre de `DEFAULT_EXCLUDED_DIRS`
tiene caracteres especiales de fnmatch, es un superset estricto sin cambio de
comportamiento para los defaults actuales.

Persistencia nueva: tabla `library_exclusion_rules` (schema v9, mismo patron de script
completo que v5, no el `ALTER TABLE` con branch propio de v8) con `ON DELETE CASCADE`
contra `media_libraries`, mas `library_scan_runs.newly_excluded_json`.
`replace_exclusion_rules()` (`library_repository.py`) reemplaza el conjunto completo de
forma atomica (`BEGIN IMMEDIATE`) y recibe `created_at` del llamador en vez de leer el
reloj el mismo, siguiendo la convencion ya existente en ese repositorio — encontrado por
grep antes de correr nada: un `_utc_now()` que se asumio existente ahi en realidad solo
existe en otros archivos.

El hueco de producto real que cierra esta tarea, no un simple rename: un archivo que
deja de aparecer por una regla nueva y uno borrado del disco producian exactamente el
mismo `available = 0`, sin ninguna señal que los distinga. `_classify_scan()`
(`library_service.py`) ahora separa, dentro de los items previamente disponibles no
reclamados por la corrida, cuales coinciden con una regla de exclusion vigente
(`path_matches_excluded_pattern`) — esos salen en un preview propio
(`run.newly_excluded`, mismo `PREVIEW_LIMIT` que ya usa el preview de descubiertos) en
vez de contarse en silencio como "missing" generico. Visible en el mismo dry run ya
obligatorio antes de aplicar (`queue_scan` ya bloqueaba `apply` sin una prueba exitosa
previa — reusado tal cual, sin una segunda pasada de seguridad nueva).

Endpoint nuevo `POST /api/libraries/{id}/exclusion-rules`, con forma de error propia
(`{"ok": false, "reason": "invalid_patterns", "errors": [{"pattern", "reason"}, ...]}`)
en vez de la string unica de `error_response()` — `admin-libraries.js` no podia mostrar
cual patron especifico fallo con el mecanismo existente. Frontend dentro del slot de
"Opciones avanzadas" que ya existia: alta/baja de filas, guardado como reemplazo
atomico del conjunto completo (nunca alta/baja individual contra el servidor), con
`libraryExclusionRulesErrorMessage()` leyendo el array estructurado. Verificado en
servidor real, no solo con pruebas unitarias: crear una biblioteca con una regla nueva
a la vez que se crea (el id todavia no existe hasta que responde el POST principal);
guardado persiste y una reapertura del dialogo la precarga; quitar la regla y
re-escanear recupera el archivo; volver a agregarla muestra "1 archivo ya registrado
quedo excluido por una regla" en vez de mezclarse con "missing"; un patron invalido
(`"a/b"`) se rechaza con el motivo especifico sin cerrar el dialogo ni descartar el
resto del formulario.

398 pruebas (crecio desde 393 al empezar, en 2 fases con esa cobertura nueva), mypy
estricto, Ruff (lint y formato), `compileall` y `git diff --check` en verde en cada
fase. Fuera de alcance, explicito desde el diseño: reglas a nivel de archivo individual
(solo carpetas, mismo alcance que los defaults ya tienen), alta/baja individual de
reglas por endpoints separados, un endpoint de preview sincrono aparte del dry run
existente, y una prueba de navegador Playwright nueva para este dialogo (no tenia
cobertura de ese tipo antes tampoco; verificacion manual con servidor real, mismo
criterio que [Q4]).
2026-08-29.

---

### Cerrado en sesiones anteriores

#### [E3] Reportar cobertura en `movie-inbox db info`
`show_info()` en `cli/database.py` suma 5 líneas nuevas usando `linked_sources()`/
`external_link_coverage()` de [E1]: con Wikipedia, con IMDb, con FilmAffinity, con
los 3, sin ninguno. Test nuevo en `tests/test_sqlite_repository.py` con un catálogo
sintético de 4 ítems (0/1/2/3 fuentes) que verifica las 5 líneas.
2026-08-19, commit `062f69b`.

#### [E4] Exponer cobertura en Curaduría y en `/api/items`
`build_curation_payload()` suma un bucket `partial_link` (ítems con 1 o 2 de 3
fuentes, vía `external_link_coverage()`), separado de `missing_link` (0 fuentes,
sin cambios). El router de `/api/items` ya calculaba `with_link`/`without_link`
para el log de la línea 84 pero no los incluía en la respuesta; ahora viajan bajo
una clave `links` nueva en el JSON. Test nuevo de `partial_link` en
`tests/test_curation.py` (4 ítems, 0/1/2/3 fuentes) y test HTTP nuevo en
`tests/test_view_http.py` para la clave `links` de `/api/items`.
2026-08-19, commit `062f69b`.

#### [E8] Unificar el gate de Wikipedia por título en `decide_match`
`fetch_wikipedia_by_title()`/`fetch_wikipedia_by_wikidata_title()` en
`external/wikipedia.py` pasaron de `wikipedia_match_score() >= 3` a juntar
candidatas y decidir con `decide_match` (mismo gate conservador que
`match_external_links.py`). Los 3 llamadores reales (`enrich`, `import`, el
auto-enrich en vivo de la webapp) heredan el fix sin cambios propios.
`wikipedia_match_score`/`normalize_match_text`/`strip_html` quedaron sin uso
y se borraron. 4 tests nuevos en `tests/test_external_metadata.py`.
2026-08-18, commit `d29b3bb`.

#### [E7] FilmAffinity: fetch de metadata dedicado
`fetch_filmaffinity_metadata(url)` nuevo en `external/filmaffinity.py` lee
el microdata schema.org de la ficha (género, reparto, dirección, guion,
sinopsis, título original), verificado contra una página real
(`film267267.html`, Heat 1995) capturada en vivo, no markup asumido.
Conectado en `fetch_metadata()`. La nota media del sitio está disponible en
el HTML (`content="7.5"`) pero deliberadamente no se trae: `CatalogItem.rating`
es el puntaje personal 0-10, no hay campo de "nota externa" en el schema
todavía. Primer fixture y primeros tests del archivo, en
`tests/test_external_filmaffinity.py`.
2026-08-18, commit `8176477`.

#### [S0-a..d] Search Lab: ranking intercambiable (candidato vs. baseline) — frente cerrado
Las 4 tareas planificadas en la sesión anterior se implementaron en orden en
esta sesión, cada una verificada con `scripts\check.ps1` completo (284 tests
al cierre) antes de pasar a la siguiente. `domain/search_strategy.py` nuevo:
`SearchStrategy` (dataclass congelado, 9 umbrales con nombre) +
`PRODUCTION_BASELINE`, enhebrado como parámetro opcional por
`domain/search.py`, `domain/matching.py`, `application/search_service.py` y
`application/search_evaluation.py` — comportamiento default intacto,
verificado por la suite completa sin tocar un assert. El Scanner real
(`ManagedLibraryService._classification`) también acepta estrategia, sin
cambio de comportamiento para el Scanner en producción.
`movie-inbox search-lab compare --candidate ruta.json` nuevo, con reporte
JSON y HTML de 2 columnas; probado en vivo contra el corpus dorado, no solo
con tests.

Dos correcciones reales a la especificación original del tablero, encontradas
al implementar: `SearchStrategy` tenía que ir en `domain/`, no en
`application/` como decía la tarea — `domain/matching.py` lo necesita, y
`domain/` no puede importar `application/`. Y la lógica de comparar
(`compare_search_strategies`) fue a `application/search_evaluation.py`, no a
`cli/search_lab.py`, siguiendo el mismo patrón que ya usan
`evaluate_search_corpus`/`inspect_catalog_search`. También apareció una
tercera copia del `0.72` del Scanner (en `library_service.py::review_file`,
la confirmación manual de un candidato) que la investigación original no
había visto — quedó sincronizada contra
`PRODUCTION_BASELINE.scanner_review_floor`.
2026-08-19, commits `6ddab22` (S0-a), `7f67759` (S0-b), `2dabde9` (S0-c),
`37fe6bb` (S0-d).

#### [E1] Función real de cobertura 0–3 (no booleana)
`linked_sources(item)`/`external_link_coverage(item)` nuevos en
`domain/catalog.py`, reusando `KNOWN_LINK_HOSTS`/`source_url_field`/
`trusted_external_url` ya existentes en vez de hardcodear la lista de
fuentes aparte. 3 tests en `tests/test_matching.py`.
2026-08-19, commit `362c02c`.

#### [E2] Arreglar el gate de enlaces múltiples en `match_external_links.py`
Los dos bugs descritos eran reales: el loop pasó de `has_external_link`
(salta apenas hay 1 link) a `external_link_coverage(item) >=
args.target_coverage` (flag nuevo, default 3). Y
`merge_best_candidate_per_missing_source()` reemplazó el merge de solo
`candidates[0]` — ahora agrupa candidatas aceptadas por fuente y mergea la
mejor de cada fuente que todavía falta. Primer test de extremo a extremo del
archivo: un ítem sin links con Wikipedia e IMDb aceptados en la misma
corrida termina con ambos `wikipedia_url` e `imdb_url` (antes solo uno
sobrevivía). 5 tests en `tests/test_match_external_links.py` (nuevo).
2026-08-19, commit `c56aba6`.

#### [E5] Extraer sinopsis completa de Wikipedia
El endpoint REST summary que se probaba primero no puede devolver el
artículo completo bajo ningún parámetro — es estructuralmente un resumen.
`fetch_wikipedia_metadata()` unificado para usar `action=query` con el
artículo completo como único mecanismo (sigue siendo una sola llamada de
red). `_split_wikipedia_sections()`/`_find_synopsis_section()` nuevos en
`external/wikipedia.py` ubican la sección "Argumento"/"Plot"/"Sinopsis"
aprovechando que `explaintext=1` sin `exintro=1` conserva los marcadores
`== Título ==` como texto plano — incluye el caso de subsección anidada
(`===` dentro de una `==`), confirmado en vivo contra los artículos reales
de "Heat" y "El padrino". `infer_kind_from_text`/`infer_year` siguen
recibiendo solo la intro, no la sinopsis completa, para no arriesgar una
clasificación de tipo equivocada por una mención tardía ajena al género
real de la obra. Sin cambios de frontend — cada consumidor de
`wikipedia_extract` ya trunca o es una vista de detalle que se beneficia
directamente de una sinopsis más completa. 6 tests en
`tests/test_external_metadata.py`.
2026-08-19, commit `85ed572`.

*(mover acá con fecha y commit al cerrar)*
