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

#### [Q2] Hacer reproducible el diagnostico multilenguaje por fuente
- **Alcance**: ampliar Search Lab con respuestas externas grabadas y una traza local
  por fuente: intencion normalizada, variantes consultadas, cantidad antes/despues del
  umbral, fallback utilizado y causa de descarte. No registrar catalogos, rutas ni
  consultas personales fuera de la instancia.
- **Corpus inicial**:
  - `Adios tio Tom`, `Adiós tío Tom`, `Addio zio Tom` y `Goodbye Uncle Tom` deben
    apuntar a `tt0180396` sin exigir el apellido del director.
  - `Fanny & Alexander` debe encontrar la misma obra que `Fanny and Alexander`,
    `Fanny och Alexander` y `Fanny y Alexander`: puntuacion y conjunciones traducidas
    no pueden cortar la recuperacion de aliases.
  - `Verano 1993` no debe interpretarse como titulo `Verano` estrenado en 1993;
    `Verano 1993 (2017)` debe conservar `1993` dentro del titulo y usar solamente
    `2017` como ano de estreno para encontrar `Estiu 1993`.
  - Sumar obras cuyo titulo conocido en espanol o ingles no es el original y consultas
    negativas que compartan palabras o personas.
- **Criterio de cierre**: un reporte permite distinguir "la fuente no devolvio la obra"
  de "Movie Inbox la descarto", mide Recall@5 por idioma/fuente y corre en CI sin red.
  Las pruebas separan normalizacion de puntuacion, expansion de aliases y parsing de
  ano para saber cual de las tres etapas produjo cada regresion.
- **Depende de**: —
- **Modelo sugerido**: Grande. Define el gate que debe proteger los cambios siguientes.

#### [Q3] Planificador acotado de consultas multilenguaje
- **Alcance**: generar variantes por obra y por capacidad de fuente, usando aliases
  confirmados por Wikidata/IDs y el idioma preferido de la instancia; no traducir texto
  libre ni concatenar personas a ciegas. Corregir especialmente el camino de IMDb para
  que una sugerencia vacia pueda activar la resolucion por alias/ID, no solo una tanda
  de resultados con score bajo. Deduplicar por identidad fuerte y respetar un
  presupuesto de llamadas, timeout y cache por plan.
- **Regla de seguridad**: un alias aumenta recall, pero no habilita auto-match sin ID
  compartido o titulo, ano y tipo compatibles. Un fallo de una variante no invalida las
  demas ni queda cacheado como vacio valido.
- **Criterio de cierre**: el corpus de [Q2] cumple Recall@5 sin director, Wikipedia puede
  aprovechar aliases fuera del titulo de articulo en ingles/espanol e IMDb conserva el
  `tt...` correcto; latencia y cantidad maxima de requests quedan presupuestadas.
- **Depende de**: [Q2].
- **Modelo sugerido**: Grande. Cambia recuperacion, ranking, cache y concurrencia.

#### [Q4] Agregar busqueda por direccion como descubrimiento explicito
- **Alcance**: permitir buscar la filmografia local por una sintaxis/campo visible como
  `director:Jacopetti` y evaluar la misma pista para fuentes externas. Una coincidencia
  por direccion debe rotularse como descubrimiento y nunca mezclarse con el score de
  titulo usado por Comparar, merge o Scanner.
- **UX**: ofrecer una forma descubrible de activar/quitar el filtro y mostrar
  "coincide por direccion"; el texto libre actual conserva precision por titulo.
- **Criterio de cierre**: encontrar obras locales por director, combinar
  titulo+director como pista externa sin degradar los negativos de [Q2], y garantizar
  que compartir director no produzca una candidata segura ni una fusion automatica.
- **Depende de**: [Q2], [Q3].
- **Modelo sugerido**: Grande. Introduce un segundo contrato de busqueda, no otro peso
  dentro del matching de identidad.

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

#### [Q7] Desambiguar un ano sin calificar dentro del titulo
- **Alcance**: `domain/search.py::_split_disambiguating_year` no puede distinguir "año
  parte del título" de "año que desambigua" cuando la consulta trae un solo token con
  forma de año — `"Verano 1993"` se lee como título `Verano` + año `1993`, mientras que
  la forma calificada `"Verano 1993 (2017)"` ya funciona bien porque el segundo token
  desambigua sin ambigüedad. Encontrado y caracterizado al alcanzar [Q2] (ver
  `docs/search-quality.md`, sección "Hallazgo abierto"), no arreglado ahí — ninguna
  tarea de este tablero declaraba el parser de año en su alcance.
- **Evidencia concreta**: `external_result_score("Verano 1993", ...)` puntúa 112.0
  contra una obra homónima no relacionada y solo 13.0 contra la obra real con alias
  perfecto — un falso positivo con confianza, no solo un falso negativo.
- **Riesgo**: ningún fix basado en regex distingue los dos casos sin una señal externa
  (una referencia de títulos, o preferir la interpretación que realmente encuentra
  candidatas); hay que evitar romper `catalog-it-remake` (`"It 2017"`, donde sacar el
  año sí es correcto) al resolver esto.
- **Depende de**: —
- **Modelo sugerido**: Grande. Toca el parser compartido por catálogo, comparación y
  Scanner — un cambio ciego ahí es exactamente el tipo de regresión silenciosa que
  `docs/search-quality.md` pide evitar.

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
- **Dependencias**: confirmar el modo personal/no comercial y resolver atribucion en
  interfaz/exportacion antes de distribuir la capacidad.
- **Modelo sugerido**: Grande. Toca licencias, almacenamiento, CLI, enrichment,
  procedencia y migraciones.

#### [F2] Autoridad de anime sostenible
- **Alcance**: obtener permiso escrito de AniList para este producto o seleccionar una
  fuente activa con licencia que permita catalogo/seguimiento. Repetir la evaluacion de
  disponibilidad, limites, IDs cruzados, aliases y atribucion antes de programar un
  adaptador.
- **Descartes actuales**: Jikan es no oficial; `anime-offline-database` quedo archivada
  el 2026-07-04; AniList prohibe por defecto servicios competidores de tracking.
- **Dependencias**: decision legal/de producto externa. Hasta entonces, Wikidata
  multilingue es el camino soportado.
- **Modelo sugerido**: Grande. No empezar la implementacion sin cerrar la fuente.

#### [F3] Evaluar TMDb como fuente estructurada opcional
- **Alcance**: revisar licencia, atribucion, limites, uso de API key, campos disponibles
  e IDs cruzados. Comparar completitud y conflictos contra las fuentes actuales sobre
  el corpus sintetico, sin enviar catalogos personales.
- **Criterio de cierre**: ADR con decision integrar/no integrar, matriz de campos y
  costos operativos; solo si se aprueba, crear una tarea separada de adaptador.
- **Depende de**: —
- **Modelo sugerido**: Grande. Requiere investigacion legal y criterio de producto.

### Frente: Bibliotecas y curaduria

#### [L1] Reglas de exclusion configurables por biblioteca
- **Alcance**: partir de los defaults seguros actuales (`extras`, `sample`, multipartes)
  y definir reglas adicionales por biblioteca con preview antes de aplicar. Persistir
  configuracion sin reinterpretar inventario historico silenciosamente.
- **Criterio de cierre**: esquema y migracion, validacion de rutas/patrones, UI owner,
  pruebas de preview/aplicacion y recuperacion ante una regla invalida.
- **Depende de**: [T2] para que el nuevo contrato nazca tipado.
- **Modelo sugerido**: Grande. Toca scanner, persistencia, seguridad y UI.

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

#### [P1] Decidir visibilidad opcional de archivos para miembros
- **Alcance**: definir si el admin puede compartir existencia, nombre o ruta de archivos
  y con que granularidad; hacer threat model antes de relajar la invariante actual.
- **Criterio de cierre**: ADR de producto/privacidad. Si se rechaza, conservar la regla
  dura; si se aprueba, crear contrato exacto para [P2].
- **Depende de**: decision del owner.
- **Modelo sugerido**: Grande. Puede exponer estructura del servidor.

#### [P2] Implementar visibilidad de archivos aprobada
- **Alcance**: aplicar exclusivamente el contrato de [P1] en servicio, API y UI, con
  default privado y migracion segura.
- **Criterio de cierre**: pruebas negativas por rol/campo, opt-in explicito y ninguna
  ruta expuesta fuera del alcance aprobado.
- **Depende de**: [P1] aprobada.
- **Modelo sugerido**: Grande. Frontera critica de privacidad.

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
