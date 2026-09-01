# Hoja de ruta

Este documento conserva decisiones de producto que no deben confundirse con trabajo
activo. El alcance inmediato sigue siendo un gestor personal self-hosted para cine,
series, anime y documentales.

## Hitos de producto

### v0.3.0: confianza en busqueda, matching e inventario — publicado 2026-08-17

Gate de salida cumplido: cero falsos positivos conocidos en auto-match y merge,
metricas minimas del corpus dorado (`movie-inbox search-lab run --enforce`, gate real
en CI) y prueba manual con snapshot de catalogo sin escrituras. Detalle completo de lo
publicado, en `CHANGELOG.md` bajo `[0.3.0]`.

Dos items de esta version no se resolvieron a tiempo y pasan a v0.4.0 porque son
arquitectura de informacion, no ranking (ver abajo): disponibilidad efectiva unica sin
llegar a Curaduria, y cola de revision sin organizar por causa/confianza.

El incremento posterior de comparacion entre baseline y algoritmo candidato ya esta
implementado: `movie-inbox search-lab compare --candidate ...` ejecuta ambos rankings
sobre el mismo corpus y genera reportes JSON/HTML sin modificar produccion. El gate
productivo sigue usando la estrategia publicada hasta que una candidata demuestre una
mejora sin falsos auto-match.

### v0.4.0: coherencia de interfaz — publicado 2026-08-22

Aplico el backlog de Impeccable sobre la Bandeja (Scanner y Curaduria) una vez
estabilizada la semantica de v0.3.0: los 4 P1 de la critica del 2026-08-14 (alcance
mezclado, "sin coincidencia" presentado como ausencia comprobada, disponibilidad
manual contradiciendo la efectiva, cola sin triage) quedaron resueltos, mas una pasada
completa de consistencia del sistema de diseño (`extract`/`typeset`/`adapt`/`polish`:
tokens de color y tipografia, paridad de foco por teclado, terminologia).

Gate de salida: una nueva critica con puntaje sobre la misma superficie, **29/40**
contra el 22/40 del 2026-08-14. Detalle completo en `CHANGELOG.md` bajo `[0.4.0]`.

La critica de cierre encontro una capa nueva del mismo problema que esta version vino
resolviendo, mas chica que los 4 P1 originales pero real. Dos arreglos puntuales
cerraron el mismo dia (border-radius mobile de Curaduria/Scanner). De los cuatro
hallazgos restantes, los dos mas dificiles ya estan cerrados:

- **Cerrado.** Scanner seguia sin historial ni deshacer — el P2 original de la
  critica del 14/08, nunca cerrado formalmente. Vincular a identidad existente,
  omitir y crear-y-vincular tienen ahora una `Actividad` propia (persistente o por
  sesion) con deshacer que restaura el estado exacto previo a la decision,
  incluidas las candidatas detectadas y, para crear, el alta en el catalogo.
  Deshacer se rechaza si algo mas toco el caso desde entonces.
- **Cerrado.** Casos duplicados con mismo titulo y año eran indistinguibles en la
  cola, el detalle y el titulo del comparador de fusion. Ahora distinguen por
  fuente, fecha de alta y archivo local; ademas, un boton nuevo resuelve solos los
  pares que no necesitan criterio humano (identicos, o que solo difieren en un
  campo vacio de un lado) reusando el motor de fusion existente sin logica nueva
  de decision, y deja en la cola —ya bien diferenciados— los que si tienen un
  conflicto real de datos personales.

Los dos restantes, mas un caso borde que dejo pendiente el punto anterior y una
pasada de higiene de repositorio encontrada en el camino, pasan a formar v0.5.0 (ver
abajo) en vez de quedar sin version asignada.

### v0.5.0: cierre de coherencia de interfaz y limpieza — publicado 2026-08-24

Incremento chico a proposito: agrupa lo que quedo pendiente del gate de cierre de
v0.4.0 mas higiene de repositorio encontrada en el camino, para poder probar bien lo
construido hasta aca antes de seguir. Desglose de tareas concreto, con alcance de
archivo/linea y modelo sugerido por tarea, en `tareas.md` (frentes "Cierre de
coherencia de interfaz" e "Higiene de repositorio").

Gate final de release cumplido el 2026-08-24: 322 pruebas unitarias y 13 pruebas de
navegador en verde, mas Ruff, formato, mypy, compileall y `git diff --check`.

- Curaduria tiene paridad con Scanner para busqueda libre sin acentos y navegacion
  circular por flechas, incluida la pestaña `Actividad` (`tareas.md` [V5-2], [V5-3]).
- El estado combinado de decision del comparador se anuncia como una sola region viva
  y describe el boton final (`tareas.md` [V5-1]).
- Cuando dos duplicados empatan hasta en archivo, fuente y fecha de alta —y solo
  quedan distinguibles por un conflicto real de datos personales—, cola, detalle y
  comparador agregan un fallback posicional 1 de 2 / 2 de 2 (`tareas.md` [V5-4]).
- La salida vieja de checks y la licencia duplicada salieron del repo; los ignores de
  datos personales bajo `scripts/` son recursivos y el catalogo anidado que habia
  escapado dejo de estar trackeado sin borrarse del disco (`tareas.md` [H1-H3]).
- IMDb conserva titulos originales, traducidos y aliases solo cuando Wikidata los
  vincula al mismo identificador de la obra; las consultas con acentos se normalizan
  sin perder letras.
- El carnet de acceso lleva la accion final debajo de las credenciales, mantiene el
  feedback dentro del objeto y conserva el orden visual, tactil y de teclado.

Explicitamente fuera de esta version, anotado para no perderlo pero sin tomar
todavia:

- **Grupos de 3+ duplicados identicos.** La deteccion (`annotate_duplicate_items()` en
  `domain/catalog.py`) ya los agrupa correctamente, pero la cola los presenta como
  pares (`_duplicate_cases()` en `application/curation_service.py` descompone cada
  grupo en C(n,2) casos). Colapsarlos en un solo caso tocaria el comparador de fusion
  (pensado para 2 entradas, no N) y el boton de auto-resolucion que ya itera de a
  pares — es mas que un ajuste de presentacion, probablemente necesita su propio hilo
  de diseno como el que definio la desambiguacion de v0.4.0.
- **Visibilidad de archivos escaneados para miembros comunes, a discrecion del
  admin.** Hoy los archivos y rutas locales nunca se exponen en vistas compartidas,
  sin excepcion ni para el owner. Habilitar esto relajaria una invariante dura de
  privacidad documentada en `CLAUDE.md` — es una decision de producto aparte, no un
  ajuste de esta version.
- **Purgar `scripts/scripts/catalogv4.json` del historial de git.** [H3] deja de
  trackearlo hacia adelante, pero el archivo ya esta en `origin/master` desde
  2026-08-01. Sacarlo de la historia requiere reescribir commits y probablemente un
  force-push — decision de Lucas, no delegable a una tarea de `tareas.md`.

### v0.6.0: descubrimiento multilingue y operacion familiar — publicado 2026-08-31

Cierra el primer tramo de la secuencia priorizada abierta despues de v0.5.0. La
busqueda puede diagnosticar recuperacion por idioma y fuente sin red, reintenta con
aliases confirmados, conserva titulos con anos ambiguos y ofrece un modo explicito de
descubrimiento por director sin convertirlo en evidencia de identidad. El indice local
oficial de IMDb queda disponible como prototipo opt-in y separado del catalogo real.

En la operacion familiar, las bibliotecas aceptan exclusiones propias y pueden publicar
su disponibilidad verificada como una coleccion de Club sin exponer rutas ni archivos.
Agregar desde otra fuente puede enriquecer una identidad fuerte existente con historial
y deshacer, y la matriz de autoridad deja explicito que ningun proveedor pisa datos ya
cargados o bloqueados. El contrato para duplicados N-a-1 queda caracterizado, pero su
implementacion visual sigue fuera del alcance de esta version.

Gate local de salida cumplido el 2026-08-31: 477 pruebas unitarias y 15 pruebas de
navegador, mas Ruff, formato, mypy estricto, compileall, los dos gates de Search Lab y
`git diff --check`. El pipeline remoto valida ademas Linux, Windows 3.14, wheel limpio y
el ciclo Docker completo con estado persistente y backup privado.

## Implementado en el incremento de descubrimiento y scanner

- Buscar el catalogo personal en el servidor, incluyendo titulos originales,
  espanoles, ingleses, aliases, nombres de archivo e identificadores externos.
- Separar visualmente los resultados locales, Wikipedia, IMDb, FilmAffinity y Jikan, con
  carga progresiva por fuente.
- Usar el mismo ranking al buscar, comparar y agregar para detectar duplicados antes
  de escribir.
- Conservar fechas de estreno con precision y procedencia, y usarlas para una seccion
  editorial `Estrenada un dia como hoy` cuando exista fecha completa confiable.
- Presentar el acceso como carnet de videoclub sin revelar perfiles antes de iniciar
  sesion.
- Permitir al owner explorar solamente las raices habilitadas por el servidor,
  comprobar una ruta antes de registrarla y mantener las rutas ocultas a miembros.
- Omitir directorios auxiliares como `extras` y `sample`, y tratar archivos
  multipartes (`cd1`, `cd2`, `disc1`, `part2`) como una sola obra con varios archivos.

Estas capacidades quedan protegidas por pruebas de busqueda, esquema, fechas de
estreno, scanner, persistencia SQLite y seguridad de las rutas. La validacion visual
del login, las estanterias por fuente y el explorador de carpetas forma parte del gate
del mismo incremento.

## Secuencia priorizada desde 2026-08-25

`tareas.md` es la fuente de verdad para alcance, dependencias, criterio de cierre y
estado. Esta hoja conserva solamente la secuencia de producto. Una decision bloqueada
no inmoviliza el resto de la cola.

### 1. Capacidad de entrega

1. **Cerrado 2026-08-25.** [T1] extendio el gate estricto de 18 a 28 modulos.
2. **Cerrado 2026-08-25.** [T2] completo Application.
3. **Cerrado 2026-08-25.** [T3] completo Infrastructure y External.
4. **Cerrado 2026-08-25.** [T4] completo Web y CLI: los 103 modulos de producto pasan
   mypy estricto.
5. **Cerrado 2026-08-25.** [T5] incorporo tests al gate: 139 archivos pasan en local y
   CI con excepciones acotadas para callbacks dinamicos y fixtures Playwright.

El baseline diagnostico inicial de 174 errores fuera de `domain` quedo cerrado sin
`ignore_errors` ni overrides sobre codigo de producto. [Q1], [Q2], [Q7], [Q3], [Q4],
[L1], [F1], [Q5], [Q6], [C1] y [P2] tambien cerraron (ver `tareas.md`). [F2] ya tiene decision
del owner tomada (2026-08-29) y queda lista para una pasada de diseño — confirmar el
estado de cada uno en `tareas.md` antes de tomar el siguiente item.

### 2. Calidad de datos y bibliotecas

1. **Cerrado.** [Q1] Conservar la intencion al refinar una busqueda de Comparar.
2. **Cerrado.** [Q2] Corpus y diagnostico reproducible de recuperacion multilenguaje
   por fuente. De paso encontro que `"Verano 1993"` sin calificar se leia como titulo
   `Verano` + año `1993` — cerrado por separado en [Q7] (ver abajo).
3. **Cerrado 2026-08-28.** [Q7] Un año sin calificar dentro del titulo ya no descarta
   en silencio el resultado real: `parse_search_query` ofrece la lectura sin dividir
   como alternativa cuando el split es ambiguo, y el scoring de externas y catalogo la
   toma en cuenta solo si el match de texto es casi verbatim — sin tocar el gate de
   auto-match ni la clasificacion real de Scanner. Detalle en `tareas.md`.
4. **Cerrado 2026-08-29.** [Q3] IMDb dispara su puente de Wikidata tambien con
   sugerencia vacia (antes solo con resultados de score bajo); Wikipedia y
   FilmAffinity ganan un reintento acotado con alias confirmados
   (`external/query_variants.py`) cuando su propia busqueda vuelve vacia. Idioma
   preferido de la instancia queda como constante fija (`("es", "en")`), decision
   explicita del owner — no existe infraestructura de settings en el proyecto y
   ningun criterio de cierre exigia que fuera editable. Detalle en `tareas.md`.
5. **Cerrado 2026-08-29.** [Q4] `"director:X"` se reconoce como su propio tipo de
   consulta (`SearchIntent.director_query`), nunca una consulta de titulo vacia.
   Localmente delega a `_search_by_director()`, separada por completo del scoring de
   titulo; en fuentes externas, `external_result_score()` confia en el ranking propio
   de la fuente para modo-director en vez de comparar contra texto de titulo (un
   apellido no aparece en un titulo por diseño). `domain/matching.py` queda sin
   ninguna referencia a `director` — verificado en vivo que compartir director no
   produce match ni fusion automatica. Detalle en `tareas.md`.
6. **Cerrado 2026-08-29.** [F1] `movie-inbox imdb-dataset sync/stats/lookup` descarga
   `title.basics`/`title.akas` y arma un `.db` SQLite propio, sin tocar el catalogo
   real. Medidas reales: descarga 704 MB en ~8s, indexado de 12,7M titulos + 59,1M
   alias en ~24 min, `.db` resultante de ~8,1 GB. Dos bugs que solo una corrida real
   encontro (TLS estricto de Python 3.13+ contra la cadena de CloudFront del sitio,
   `UnicodeEncodeError` imprimiendo alias fuera de cp1252) quedaron corregidos.
   Detalle en `tareas.md`.
7. **Cerrado 2026-08-29.** [Q5] Matriz de autoridad por familia de campo: define qué
   fuente se prueba primero cuando un campo está vacío (`[F1]` → Wikipedia → IMDb →
   FilmAffinity, según la familia), pero un campo ya completado nunca se pisa —
   decisión explícita del owner. Sin cambios a `domain/catalog.py`; `tests/
   test_metadata_authority.py` prueba la política contra las funciones de merge ya
   existentes. Detalle en `tareas.md`.
8. **Cerrado 2026-08-29.** [Q6] `decide_match` (el mismo gate conservador ya probado en
   Scanner) ahora tambien corre en `/api/add`: una fuente nueva que matchea fuerte con
   una ficha existente se combina en ella (`auto_merge_on_add`, con historial y
   deshacer) en vez de crear una segunda ficha o pedir una fusion manual. Verificado
   en vivo contra Wikipedia real: dos altas del mismo "Heat" (español e ingles)
   terminan en una sola ficha con datos acumulados. Lo que `decide_match` no acepta
   sigue igual que antes. Detalle en `tareas.md`.
9. **Cerrado 2026-08-29.** [L1] Reglas de exclusion adicionales por biblioteca, encima
   de los defaults seguros existentes (`extras`, `sample`, etc.): patrones tipo glob
   validados en `domain/libraries.py` y persistidos por biblioteca, aplicados por
   `scan_media_files()`. Un archivo previamente disponible que una regla nueva empieza
   a excluir se distingue en el mismo dry run existente (`run.newly_excluded`) en vez
   de confundirse en silencio con uno borrado del disco. Detalle en `tareas.md`.
10. [F3] Evaluacion de TMDb; un adaptador solo nace si el ADR la aprueba.
11. **Decision tomada 2026-08-29.** [F2] Jikan como fuente de anime primaria,
    `anime-offline-database` como secundaria/offline. Falta una pasada de diseño corta
    (como componen las dos) antes de programar el adaptador.
12. **Cerrado 2026-08-30.** [C1] Contrato para grupos de 3+ duplicados: un caso deja de
    representar un par y pasa a representar la componente conexa de
    `_duplicate_refs`/`_duplicate_deferred_refs` (`members: [...]`, no
    `primary`/`secondary`). De paso documento con una tabla trazada que
    `auto_resolve_duplicates()` hoy infla `needs_review` con ruido de referencias
    obsoletas del mismo lote (solo 1 de 4 "needs_review" era un conflicto real en el
    grupo de prueba) — ADR y fixtures de caracterizacion, sin tocar produccion; mismo
    alcance que [Q5]. Detalle en `tareas.md`.
13. [C2] Resolucion N-a-1 segun el contrato ya cerrado en [C1] — listo para tomar
    tamaño y programarse.
14. [F4] API keys opcionales por fuente (ej. TMDb), sin dejar de ser abierto por
    default. Prioridad baja a pedido del owner — necesita su propio analisis de diseño
    antes de poder tomar tamaño.

### 3. Superficie publica y operacion

1. **Cerrado 2026-09-01.** [W1] fijo el contrato y threat model de presentacion
   publica opt-in: una capacidad opaca de solo lectura, snapshot minimo, sin cache de
   contenido y separada de Club/sesiones privadas. Ver ADR-0001 y esquema v1.
2. [W2] Landing publica aislada de sesiones y endpoints privados.
3. [D1] HTTPS guiado mediante reverse proxy soportado.
4. [W3] Diseno de paquetes/sincronizacion entre homeservers sin servicio central
   involuntario.

### 4. Clientes e integraciones

1. [A1] API versionada y sesiones revocables para dispositivos.
2. [A2] Cliente Android basico, candidato a un hito posterior una vez cerrado [A1].
3. [I1] Evaluar Radarr, Sonarr y Letterboxd sobre contratos ya estables.
4. [M1] Investigar juegos y musica como verticales propias, nunca como simples valores
   nuevos de `kind`.

### Decisiones que pueden interrumpir la cola cuando el owner las resuelva

- **Resuelta 2026-08-26.** [S1]/[S2]: Lucas eligio purgar. El catalogo personal
  anidado quedo inalcanzable en rama y tags de `origin/master` (128 commits y 5 tags
  reescritos con backup previo); ver `tareas.md`.
- **Resuelta 2026-08-29, implementada 2026-08-31.** [P1]/[P2]: ruta, archivo, nota y
  estado operativo del escaneo siguen sin exponerse nunca en una vista compartida — la
  regla dura no cambia. Unico carve-out aprobado, ya implementado: el admin puede
  activar "compartir disponibilidad" por biblioteca, publicando una coleccion de Club
  de solo lectura con los titulos confirmados — nunca ruta ni archivo, el titulo de la
  biblioteca es lo unico nuevo que se expone, opt-in y editable. Verificado en vivo
  contra un servidor real que el payload de `/api/collections` no contiene
  `library_id`/`library_name`/ruta/nombre de archivo en ningun lugar. Detalle completo
  en `tareas.md`.
