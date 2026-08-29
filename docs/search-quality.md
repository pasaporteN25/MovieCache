# Calidad de busqueda y matching

Este documento define el gate de calidad de `v0.3.0`. Su objetivo es evitar otra
iteracion basada solamente en ejemplos positivos: una busqueda no mejora si encuentra
el resultado esperado pero tambien presenta decenas de obras irrelevantes.

**Estado:** el gate del corpus dorado (seccion "Metricas y gate de v0.3.0") pasa:
`movie-inbox search-lab run --enforce` sale con codigo 0 y CI lo hace cumplir en cada
cambio. Las 4 fallas de abajo estan resueltas en los caminos que ejercita el corpus
(`search_catalog_items`, `rank_catalog_candidates`, `external/registry.py`,
`application/search_evaluation.py`). El problema #3 quedo resuelto para el caso
concreto de un mismatch *confirmado* (mismo titulo, año o tipo distinto) en Catalogo
y Comparar; `domain/matching.py::rank_candidates` (usado solo por
`cli/match_external_links.py`) sigue sin ese filtro, sin evidencia de que haga falta
hoy. Ver `CHANGELOG.md` (`[Sin publicar]`) para el detalle de cada fix.

## Problemas verificados

El comportamiento tenia cuatro fallas diferentes (ver "Estado" arriba):

1. La coincidencia de terminos acepta subcadenas en ambas direcciones sin proteger
   tokens cortos. Un articulo como `a` puede hacer que un titulo no relacionado puntue
   como coincidencia fuerte para una consulta que contenga esa letra.
2. La busqueda local permite que descripcion, review, reparto, genero y tags superen un
   umbral general muy bajo. Eso puede ser util para descubrimiento, pero no debe
   mezclarse con resultados por titulo.
3. El ranking de candidatas conserva cualquier `match_score > 0`, incluso cuando la
   decision es `insufficient_evidence`. La similitud difusa produce valores mayores que
   cero para casi cualquier par de titulos.
4. Las fuentes externas se ordenan por puntaje pero no aplican un umbral de rechazo.
   La interfaz progresiva hace visibles hasta ocho resultados por fuente, incluidos los
   de relevancia minima.

La concurrencia por fuente no es la causa de estos falsos positivos. Debe conservarse:
mejora el tiempo percibido y permite que una fuente falle sin bloquear a las demas.

## Cuatro contextos, cuatro contratos

| Contexto | Objetivo | Evidencia permitida | Prioridad |
|---|---|---|---|
| Catalogo | Encontrar una ficha que el usuario recuerda | Titulos, aliases, ID, archivo; metadata secundaria separada | Precision primero |
| Fuentes externas | Encontrar una obra fuera del catalogo | Titulos, aliases, ano, tipo, ID y fuente | Recall controlado |
| Comparar/merge | Decidir si dos fichas representan la misma obra | ID externo o titulo, ano y tipo compatibles | Cero falsos auto-match |
| Scanner | Identificar un archivo fisico | Titulo limpio, ano, tipo, IDs y decisiones previas | Cero falsos auto-match |

La normalizacion de texto puede compartirse. Los campos, umbrales y significado de un
score no deben compartirse implicitamente entre estos contextos.

## Revision de anime, multilenguaje y latencia (2026-08-25)

La normalizacion anterior conservaba solamente `a-z0-9`: una consulta o alias en
japones se convertia en una clave vacia. La normalizacion productiva conserva ahora
letras y numeros de cualquier sistema de escritura, pero sigue ignorando diacriticos
latinos. Wikidata busca evidencia de titulo en espanol, ingles y japones y solo la
asocia a un resultado de IMDb cuando la entidad confirma el mismo `tt...`.

`anime` describe el medio en Movie Inbox, mientras que IMDb y otras fuentes suelen
devolver solo el formato de lanzamiento (`pelicula` o `serie`). Mismo titulo y ano con
esa unica diferencia ya no desaparece del comparador ni se presenta como una
contradiccion generica: queda visible como
`exact_title_year_anime_kind_review`. Sigue sin ser auto-match; la decision humana y
el gate de cero falsos positivos se conservan.

Para catalogos grandes, el ranking usa el termino exacto menos frecuente como
prefiltro cuando existe y conserva el camino difuso completo para consultas sin un
ancla exacta. Sobre 10.000 obras sinteticas, `Anime Title 9876` paso de unos 1.430 ms y
60 resultados genericos a unos 170 ms y una unica coincidencia. La lectura del
catalogo tambien queda en cache por firma de archivo; cualquier cambio de tamano o
fecha de modificacion invalida la copia. El corpus suma titulo japones nativo y la
taxonomia anime/formato y mantiene el gate en verde con 28 casos.

### Decision sobre nuevas fuentes

- AniList ofrece la mejor API en tiempo real para titulos, sinonimos y relaciones,
  pero sus [terminos](https://docs.anilist.co/guide/terms-of-use) prohiben usarla en
  servicios competidores de listas o seguimiento sin una autorizacion expresa.
- Jikan es un intermediario no oficial sobre MyAnimeList y no ofrece un contrato de
  datos mas firme que la fuente original.
- `anime-offline-database` tiene licencia ODbL/DbCL y buenos cruces, pero su repositorio
  fue archivado el 2026-07-04; no es una dependencia sostenible para datos nuevos.
- Hasta contar con permiso o una fuente mantenida con licencia compatible, se mejora
  Wikidata —ya integrado y trazable— en vez de agregar una cuarta estanteria fragil.

IMDb tampoco se puede priorizar globalmente con el camino actual: la seleccion de un
resultado de IMDb obtiene la ficha completa mediante Wikidata/Wikipedia; no extrae la
pagina de IMDb. IMDb solo autoriza el uso no comercial gratuito de sus
[datasets oficiales](https://www.imdb.com/interfaces/) y desaconseja scraping. Una
integracion futura debe ser opcional, indexar localmente `title.basics`, `title.akas`,
`title.crew`, `title.principals` y `name.basics`, mostrar atribucion y definir prioridad
por campo. Las correcciones manuales y `locked_fields` siguen por encima de toda
fuente externa.

### Hallazgo cerrado: un ano sin calificar dentro del titulo ([Q7], 2026-08-28)

Al alcanzar [Q2] (`tareas.md`), verificado directamente corriendo
`parse_search_query`/`external_result_score`: `"Verano 1993"` sin calificar
se interpreta como titulo `Verano` estrenado en 1993 — exactamente el
mal-parseo que el corpus ya evita para su forma calificada,
`"Verano 1993 (2017)"` (dos tokens de año, el ultimo es inequivocamente el
disambiguador). Con un solo token no hay señal sintactica local que
distinga "año parte del titulo" de "año que desambigua": el mismo patron
que hace bien `"It 2017"` (`catalog-it-remake`, quitar el año final es lo
correcto) hace mal `"Verano 1993"` (quitarlo no lo es). La consecuencia era
real, no cosmetica: contra una obra distinta homonima ("Verano", 1993) la
consulta sin calificar puntuaba 112.0; contra la obra real, con un alias
perfecto (`spanish_title: "Verano 1993"`, año real 2017), puntuaba apenas
13.0 — el año mal separado disparaba la penalidad de año distinto,
descartando la obra real por debajo del umbral de aceptación (28.0).

**Fix**: sin una referencia de titulos, no hay forma de saber de antemano
cual de las dos lecturas es la correcta — así que `parse_search_query` ya
no elige una sola. `SearchIntent` conserva la lectura primaria (año
separado, sin cambios para "Heat 1995" ni para ninguna consulta con 0 o 2+
tokens de año) y agrega `alternate_title`/`alternate_title_key` — la
lectura sin dividir — solo cuando el split fue genuinamente ambiguo (un
solo token de año, con texto real antes). `external_result_score` y
`_catalog_search_score` (`application/search_service.py`, la ruta paralela
de Catálogo/Comparar) puntúan un candidato contra las dos lecturas y toman
el máximo, pero solo si la lectura alternativa alcanza
`SearchStrategy.ambiguous_year_alternate_floor` (82.0 — el mismo corte que
`text_match_score` ya usa para su nivel "contains", no un número nuevo
inventado para esto). Ese piso es lo que evita que la alternativa rescate
un candidato con año equivocado pero titulo parecido (`"It 2017"` contra el
`it-1990` de año distinto sigue puntuando 25.0, por debajo del piso) — solo
un alias verbatim o casi verbatim cruza la barrera.

**Criterio de cierre real, más modesto que "gana el ranking"**: la obra real
deja de descartarse por debajo del umbral (13.0 → 100.0 en el caso Verano).
No es criterio que supere siempre a un homonimo con match exacto de
titulo+año — ese homonimo (`"Verano"`, 1993) sigue puntuando 112.0,
legitimamente, porque para esa consulta es un match tan valido como el
otro sin señal para preferir uno u otro. Ambos quedan visibles para
revision humana, que es la invariante real que importa (`CLAUDE.md`:
coincidencia dudosa = revisión humana, nunca auto-match) — y ese camino
(`domain/matching.py::decide_match`, la clasificación real de Scanner) no
importa `domain.search` en absoluto, así que este fix no lo toca.

Caso nuevo en el corpus dorado (`external-verano-1993-unqualified-year`,
`search_lab/corpus/v1.json`) protege el fix vía
`movie-inbox search-lab run --enforce`, no solo pruebas unitarias.
Detalle completo en `tareas.md`, [Q7].

### Planificador de variantes multilenguaje ([Q3], 2026-08-29)

IMDb tenía un puente propio a Wikidata que rescataba resultados de baja
puntuación con alias confirmados, pero solo si la sugerencia inicial no
volvía vacía (`if (results and ...)` cortaba en el primer operando falso
antes de siquiera llamar a `fetch_wikidata_title_matches`). Wikipedia
cubre en/es por sí mismo cada llamada, pero nunca intentaba un alias fuera
de esas dos ediciones. FilmAffinity no tenía ningún mecanismo de respaldo.

**Fix**: cada adaptador se auto-contiene, mismo patrón que IMDb ya tenía —
`registry.py` no cambió en absoluto, sigue llamando `adapter.search(query)`
una vez por fuente sin saber si el adaptador hizo trabajo extra por dentro.
IMDb ahora también dispara el puente con sugerencia vacía, sintetizando una
fila nueva por cada alias confirmado en vez de solo enriquecer filas que la
sugerencia ya había devuelto. Wikipedia y FilmAffinity ganan un mecanismo
nuevo compartido (`external/query_variants.py::alias_variants()`): cuando
su propia búsqueda vuelve vacía, hasta 2 alias confirmados por Wikidata se
prueban como reintento — ordenados por capacidad de fuente (FilmAffinity,
sitio solo en español, prioriza `spanish_title`; Wikipedia, que ya cubre
en/es, prioriza `original_title`, que es justo lo que le falta). Nunca
traduce texto libre ni concatena director/reparto — la regla se cumple por
construcción, solo se leen campos de alias ya confirmados por Wikidata.

**Constante de idioma, no setting nuevo**: "idioma preferido de la
instancia" es `PREFERRED_ALIAS_LANGUAGES = ("es", "en")` fijo en código
(`query_variants.py`), decisión explícita del owner — no existe ningún
mecanismo de configuración por instancia en el proyecto hoy (confirmado
buscando en todo `application/`/`infrastructure`/`web`: sin tabla, sin
servicio, sin UI), y ningún criterio de cierre de esta tarea exige que sea
editable. Si más adelante hace falta (instancia con biblioteca no
hispanohablante), es una decisión de producto aparte, no una que esta
tarea deba resolver por adelantado.

**Presupuesto**: como máximo 2 variantes extra por fuente débil, solo
cuando esa fuente volvió vacía. Las llamadas de reintento usan un timeout
de 4s (`VARIANT_RETRY_TIMEOUT_SECONDS`, la mitad del default de 8s) por
ser una mejora de mejor esfuerzo sobre una búsqueda que ya falló. Peor caso
por fuente: Wikipedia y FilmAffinity ~8s + hasta 2×4s = 16s; IMDb sin
cambio de presupuesto (~8s + hasta 10s de puente, ya existente). Como las 3
fuentes corren en paralelo (`ThreadPoolExecutor` de `registry.py`, sin
tocar), el techo real de `GET /api/search` es el máximo de los tres, no la
suma.

**Limitación conocida, documentada a propósito**: el corpus dorado de [Q2]
(`external_diagnostics_v1.json`) no ganó casos nuevos para el mecanismo de
Wikipedia/FilmAffinity — se intentó construir uno contra datos reales
(mismo estándar que los 3 casos existentes), pero encontrar una búsqueda
que la propia cobertura de Wikipedia deje genuinamente vacía (no solo
irrelevante: `gsrsearch` casi siempre devuelve algo) resultó más difícil de
lo esperado contra títulos reales, y se paró la exploración en vivo contra
la API pública antes de gastar más cupo en algo no crítico. El mecanismo sí
queda cubierto por pruebas unitarias directas contra el código real
(`tests/test_external_metadata.py`, `tests/test_external_query_variants.py`),
verificadas por ejecución, no solo revisadas — la brecha es puntual al
corpus con datos en vivo, no a la cobertura de la lógica en sí.

### Búsqueda por dirección como descubrimiento explícito ([Q4], 2026-08-29)

`directors: list[str]` ya existía en el modelo (poblado desde Wikidata P57
y FilmAffinity) pero `_search_values()` lo excluía deliberadamente del
buscador principal. `"director:Jacopetti"` ahora se reconoce como su
propio tipo de consulta — `parse_search_query()` hace un early-return con
`director_query`/`director_query_key` seteados y título/año vacíos — en
vez de leerse como una consulta de título vacía.

**Hallazgo real durante el diseño, no asumido**: el primer diseño agregaba
el nombre del director como un fallback más en la cadena de cada
adaptador y daba por sentado que el resto del pipeline externo seguía
funcionando. Verificado que no alcanza: `registry.py::_rank_batch`
puntúa cada resultado con `external_result_score()`, que compara texto de
consulta contra TÍTULO — un apellido de director no aparece en el título
de una película por diseño, y el caso real ("Jacopetti" contra "Mondo
Cane") confirma que el score cae muy por debajo del umbral de aceptación
por el camino difuso normal. Sin arreglar esto, la búsqueda externa por
director hubiera devuelto cero resultados siempre, en silencio.
`external_result_score()` gana un branch explícito: en modo director,
confía en el ranking propio de la fuente para cualquier candidato con
título reconocible, en vez de re-puntuar localmente (no hay nada sensato
que comparar). Localmente, `search_catalog_items()` delega a
`_search_by_director()`, una función separada que nunca toca
`_catalog_search_score`/`_search_values` — "nunca mezclarse con el score
de título" se cumple por construcción, no por un flag dentro del scoring
compartido. Ambos caminos reusan `text_match_score`/`EXTERNAL_RELEVANCE_
THRESHOLD` ya existentes, sin umbrales nuevos inventados.

**Seguridad, verificada por lectura directa**: `domain/matching.py` no
tiene ninguna referencia a `director` — cero código que tocar. Confirmado
en vivo (servidor real, catálogo sintético) que dos obras distintas del
mismo director no producen match ni fusión automática, y que
`rank_catalog_candidates()`/`_candidate_query()` nunca puede emitir
`director:...` por sí solo, así que el flujo automático de Comparar jamás
entra en modo-director.

IMDb contribuye poco o nada para un nombre de director suelto — su
endpoint de sugerencias descarta cualquier `qid` que no sea de
película/serie (un nodo de persona queda afuera) y el puente de Wikidata
exige un IMDb id con forma `tt...` (un nodo de persona no la tiene).
Documentado como límite estructural aceptado, no perseguido con lógica
nueva — confirmado además en vivo que Wikipedia sí aporta valor real: una
búsqueda real de "director:Jacopetti" con fuentes externas activas
encontró y etiquetó correctamente la biografía del propio director en
Wikipedia.

Toggle nuevo en Colección ("Buscar por dirección"), mismo patrón que el
checkbox existente de fuentes externas — antepone `director:` al texto ya
escrito, así que nadie necesita conocer la sintaxis para usarla; tipearla
directamente también funciona. Verificado con un servidor real (no solo
tests unitarios): catálogo local y Wikipedia en vivo, ambos etiquetando
correctamente "coincide por dirección".

## Laboratorio de busqueda

El primer incremento sera un `Search Lab` de desarrollo, no destructivo y disponible
solo para el owner cuando una feature flag lo habilite.

- Nunca expondra endpoints de escritura ni trabajara sobre la unica copia de una base.
- Usara un export o snapshot de catalogo montado en solo lectura.
- Ejecutara el algoritmo baseline y el candidato sobre la misma consulta.
- Mostrara score, campo coincidente, razon, evidencia y clasificacion
  `aceptada/revisar/rechazada`.
- Permitira marcar resultados como relevantes o irrelevantes y exportar esas decisiones
  al corpus de casos dorados.
- Las fuentes externas funcionaran por defecto con respuestas grabadas. El modo live
  sera manual y sus latencias se mediran por separado.

El runner automatizado y los fixtures son la fuente de verdad. La vista web sera una
herramienta para inspeccionar y etiquetar casos, no un segundo algoritmo.

### Incrementos implementados

El primer incremento entrega el runner determinista, el corpus dorado `v1` empaquetado
y una inspeccion HTML/JSON de exports. Reutiliza sin cambios los cuatro caminos
productivos actuales y registra score, campo, razon, evidencia y aceptacion.

```powershell
movie-inbox search-lab run --json reports/baseline.json --html reports/baseline.html
movie-inbox search-lab run --enforce
movie-inbox search-lab inspect backups/catalog.json "Heat" --mode catalog --html reports/heat.html
```

El primer comando siempre permite registrar la baseline aunque el gate falle. El
segundo se reserva para CI y retorna un estado distinto de cero si no se cumplen los
umbrales. `inspect` solo admite un export JSON, nunca una base SQLite viva; tampoco
consulta fuentes externas ni crea archivos de bloqueo. La vista owner con feature flag,
el etiquetado y la calibracion humana siguen pendientes.

`compare` ya ejecuta el mismo corpus con la estrategia productiva y una estrategia
candidata configurable, y genera un reporte JSON/HTML de dos columnas sin cambiar el
ranking real:

```powershell
movie-inbox search-lab compare --candidate estrategia-candidata.json --html reports/compare.html
```

## Corpus inicial

Cada caso declarara `context`, consulta, resultado esperado, resultados prohibidos,
ano/tipo opcionales y evidencia requerida. El corpus inicial debe incluir:

- Titulos cortos y ambiguos: `It`, `Up`, `Us`, `Heat`, `Crash`, `The Gift`.
- Titulos numericos: `1917`, `1984`, `2001: A Space Odyssey`.
- Anos que pertenecen al titulo: `Verano 1993` no se reduce a `Verano` + ano 1993, y
  `Verano 1993 (2017)` conserva el primer numero como titulo y toma 2017 como estreno.
- Remakes: `The Fly`, `Suspiria`, `Dune` y obras con igual titulo y distinto ano.
- Titulos multilenguaje: `La Belle Personne`, `La bella persona`,
  `The Beautiful Person`; `Fanny & Alexander`, `Fanny and Alexander`,
  `Fanny och Alexander`, `Fanny y Alexander`; y `Estiu 1993`/`Verano 1993`.
- Puntuacion significativa y variantes de conjuncion: `&`, `and`, `och` e `y` deben
  resolverse mediante aliases confirmados, no sustituyendose globalmente entre idiomas.
- Obras recientes o con metadata incompleta, comenzando por `Evil Dead Burn`.
- Series y anime, comenzando por `Tantei Monogatari`.
- Nombres de archivo con release, codec, resolucion, grupo y multipartes.
- Consultas negativas que comparten actores, palabras de descripcion o articulos, pero
  no identidad de obra.

Los casos provenientes de un catalogo real deben anonimizar rutas y datos personales
antes de entrar al repositorio.

## Metricas y gate de v0.3.0

- Precision de auto-match y auto-merge: `100%` en el corpus dorado.
- Cero resultados `insufficient_evidence` presentados como coincidencia segura.
- Precision@5 de busqueda local por titulo: al menos `90%`.
- MRR de busqueda local por titulo: al menos `0.90`.
- Recall@5 externo sobre respuestas grabadas: al menos `90%`.
- Ninguna consulta negativa aprobada por descripcion, review, reparto, genero o tags en
  los contextos de merge y Scanner.
- Resultados de baja confianza ocultos por defecto y contados por separado.
- Rendimiento local medido con catalogos sinteticos de 2.000 y 10.000 obras; la red se
  evalua por fuente y no forma parte del tiempo del ranking local.

Una mejora no entra a `master` si aumenta recall a costa de falsos positivos en merge
o Scanner. En esos flujos, dejar un caso para revision es mejor que unir obras distintas.

## Secuencia de implementacion

1. [Completado] Crear fixtures y runner con el comportamiento actual como baseline observable.
2. [Completado] Agregar pruebas negativas que reproduzcan los falsos positivos conocidos.
3. Separar `catalog_search`, `external_lookup`, `identity_candidates` y
   `scanner_candidates`. Parcial: tienen umbrales propios ahora, pero
   `rank_catalog_candidates` sigue llamando a `search_catalog_items` por dentro,
   no son caminos completamente independientes.
4. [Completado] Corregir tokens cortos, stopwords, umbrales y evidencia por campo.
5. [Completado] Filtrar por relevancia dentro de cada adaptador externo sin perder
   resultados exactos recientes o multilenguaje.
6. Integrar el reporte al Search Lab y calibrar con decisiones humanas. El reporte ya
   existe; falta el proceso de calibración con revisión humana.
7. Recién entonces ajustar la presentacion final de resultados y el triage del Scanner.

No se incorporaran embeddings, modelos de IA ni nuevas APIs durante este gate. Primero
debe existir una baseline determinista, explicable y reproducible.
