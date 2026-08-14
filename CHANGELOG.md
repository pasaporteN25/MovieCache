# Changelog

Los cambios relevantes del proyecto se documentan en este archivo.

## [Sin publicar]

## [0.2.1] - 2026-08-13

### Corregido

- La version del paquete, la version runtime y la documentacion ahora identifican la
  release estable de forma consistente; el tag `v0.2.0` conservaba por error los
  metadatos internos de `0.2.0rc2`.

## [0.2.0] - 2026-08-13

### Cambiado

- La cabecera separa navegación, descubrimiento y cuenta: `Inicio`, `Colección`,
  `Bandeja` y `Club` son destinos; `Al azar` queda como comando y su alcance se
  configura desde el menú de cuenta.
- El visor precalcula métricas y documentos de búsqueda al cargar el catálogo y evita
  reconstruir la grilla o el Inicio editorial cuando su contenido visible no cambió.
- Se incorporaron tokens semánticos para superficies, texto, acciones, radios y escala
  tipográfica, con un piso de 10 px para etiquetas técnicas.

### Corregido

- Las acciones rosas alcanzan contraste AA con tinta oscura y el título conserva una
  alternativa visible en el modo de alto contraste de Windows.
- Las listas dinámicas dejaron de anunciar paneles completos a lectores de pantalla;
  el diálogo de descripción ahora posee nombre, descripción y retorno de foco.
- El retrato decorativo del carnet de acceso ya no crea un landmark vacío.

### Pruebas

- Se agregó un smoke de Chromium para navegación por teclado, semántica de diálogos,
  targets táctiles y ausencia de overflow en escritorio y móvil.

## [0.2.0-rc2] - 2026-08-13

### Agregado

- Busqueda local del lado del servidor sobre titulos originales, espanoles, ingleses,
  aliases, nombres de archivo, IDs, links y metadata, con ranking compartido para
  buscar y comparar antes de agregar.
- Resultados externos separados en estanterias de Wikipedia, IMDb y FilmAffinity, con
  carga progresiva independiente, timeout y reintento por fuente, y comparacion
  enriquecida contra todo el catalogo. Cada estanteria aparece apenas responde sin
  esperar a las otras fuentes.
- Fechas de estreno normalizadas con precision, pais, tipo y procedencia en JSON v6 y
  SQLite v4, mas la seccion editorial `Estrenadas un dia como hoy` cuando hay fecha
  completa confiable.
- Acceso presentado como carnet de videoclub, manteniendo errores genericos y sin
  enumerar usuarios antes de autenticar.
- Explorador grafico de carpetas limitado a las raices autorizadas del servidor y
  comprobacion de lectura antes de registrar una biblioteca.
- Agrupacion de `CD1/CD2` y variantes `disc` como una sola decision del Scanner,
  conservando cada archivo fisico y su tamano en el inventario.

- Imagen Docker multi-stage sin privilegios, Compose con estado persistente, secret para el owner, biblioteca de solo lectura, healthcheck y configuracion local mediante `.env`.
- Guia de importacion inicial, operacion, backup y actualizacion de una instancia Docker nueva.
- Perfil de ejemplo para montar hasta ocho unidades de OMV/Debian en slots de solo lectura.
- Descarga autenticada del catalogo personal en JSON portable o CSV desde Administrar.
- Precarga progresiva y deduplicada de portadas despues del primer acceso autenticado, con prioridad para imagenes visibles, reintentos con backoff y estado compacto en Administrar.
- Placeholders estables y carga diferida de portadas con prioridad para el primer viewport, ficha y spotlight.
- Inicio editorial diario y estable con una cartelera disponible, recomendaciones explicables desde el catalogo personal y obras pendientes de colecciones seguidas.
- Cartelera diaria con hasta cuatro recomendaciones disponibles, sinopsis, selector
  manual y compatibilidad temporal con el campo `hero` anterior de `/api/home`.
- Filtros rapidos y avanzados acumulables en `Coleccion`, con facetas para
  disponibilidad, estado, tipo, fuente, director, genero, decada, rango de anos y
  memoria personal.
- Acciones editoriales que trasladan su criterio real a `Coleccion` mediante URLs
  restaurables y chips removibles por valor.
- Endpoint autenticado `/api/home` con seleccion determinista, limites estrictos, deduplicacion entre secciones y degradacion parcial cuando las colecciones no estan disponibles.
- Backups completos de instancia en archivos `.tar.gz` atomicos, con checksum SHA-256, verificacion de bases requeridas, exclusion del cache y retencion configurable.
- Servicio de mantenimiento de Compose, wrapper con bloqueo/reinicio/healthcheck y timer systemd diario para automatizar backups en OMV o Debian.

### Cambiado

- El antiguo carrusel automatico fue reemplazado por una cartelera de seleccion manual;
  `Random` conserva la exploracion impredecible como una accion independiente.
- Las cards secundarias de Inicio eliminan leyendas contextuales repetitivas y dejan la
  explicacion en el encabezado de seccion o la ficha.
- Bibliotecas separa archivos vinculados, ambiguos y nuevos en vez de agrupar los dos
  ultimos bajo un unico contador de revision.

### Corregido

- La busqueda de Wikipedia resuelve primero titulos y URLs exactos, conserva resultados
  si falla uno de los idiomas y ya no permite que un error transitorio quede cacheado
  como una respuesta vacia durante 15 minutos.
- La busqueda local y externa separa titulo, ano, URL e identificador antes de puntuar;
  `Evil Dead Burn 2026` y su URL de Wikipedia encuentran la misma obra sin relajar las
  reglas conservadoras de merge.

- El wrapper de backup prepara y valida la ruta host interpolada por Compose antes de
  detener la aplicacion, evitando mounts fallidos cuando el directorio aun no existe.
- El scanner reconcilia titulos exactos y unicos sin ano contra entradas heredadas que
  ya poseen evidencia fisica, manteniendo remakes y casos sin procedencia en revision.
- El servicio Docker de backup puede leer archivos privados `0600` del usuario interno
  mediante la capacidad minima `DAC_READ_SEARCH`, conservando el volumen fuente en
  modo de solo lectura y sin acceso de red.
- El wrapper resuelve el destino desde el perfil Compose `maintenance` y rechaza
  argumentos o comodines accidentales en lugar de diagnosticar incorrectamente `.env`.
- Las carpetas `extra`, `extras`, `sample` y `samples` ya no aportan videos al scanner.
- Los textos editoriales conservan tildes y `anos` se muestra correctamente como
  `años`; el repositorio declara UTF-8 y finales LF para codigo y documentacion.

- Los mounts multi-disco ya no intentan crear sus destinos sobre el filesystem raiz de solo lectura.
- La importacion Docker puede leer catalogos desde `/imports` sin intentar crear un lock en ese mount de solo lectura.

## [0.2.0-rc1] - 2026-08-04

### Agregado

- Paquete instalable `movie-inbox` con subcomandos `account`, `import`, `scan`, `serve`, `migrate`, `enrich`, `match`, `db` y `cache`.
- Estructura `src/movie_inbox` con capas de dominio, aplicacion, infraestructura, clientes externos y web.
- Clientes separados para Wikipedia, Wikidata, IMDb y FilmAffinity, con registro concurrente y cache compartido.
- HTML, CSS y JavaScript del visor como assets estaticos empaquetados.
- Aplicacion FastAPI y servidor Uvicorn con endpoints compatibles con el visor existente.
- Healthcheck sin datos sensibles, validacion de origen publico y confianza restringida de headers de proxy.
- Plantillas endurecidas de `systemd` y Nginx para ejecutar con SQLite fuera del checkout.
- Lanzadores compatibles en `scripts/` para conservar los comandos de v0.1.
- Contrato de repositorio compartido para separar los casos de uso de la persistencia.
- Repositorio SQLite transaccional seleccionable por extension, manteniendo JSON como importacion, exportacion y backup.
- Tablas normalizadas para obras, aliases, IDs externos, archivos, tags y procedencia, con estructura reservada para temporadas y episodios.
- Importacion JSON a SQLite con verificacion y backup previo al reemplazo, exportacion reversible e inspeccion de la base.
- Checks reproducibles para PowerShell y Bash, y CI en GitHub Actions para Linux y Windows.
- Documentacion del modelo de despliegue con codigo y datos persistentes separados.
- Bloqueo entre procesos y escrituras atomicas compartidas por el visor, migrador y scanner.
- Scanner Python incremental para una biblioteca, con `dry-run`, estado persistente, reportes y modo `watch`.
- Deteccion de archivos nuevos, modificados y movidos mediante ruta relativa y huella parcial.
- Proteccion ante discos desconectados y escaneos parciales antes de marcar archivos no disponibles.
- Esquema v4 con identidad de biblioteca, ruta relativa, huella, ultimo avistamiento y disponibilidad por archivo.
- Modelos canonicos para catalogo, archivos locales y procedencia de metadata.
- Migraciones explicitas desde formatos legacy y esquemas v1, v2, v3 y v4.
- Token por sesion, validacion de origen/host y respuestas HTTP con estados reales en el visor.
- Limite de cuerpo aplicado durante la lectura del stream y documentacion OpenAPI deshabilitada.
- El token del cache de imagenes sale de la URL y pasa a una cookie `HttpOnly` con `SameSite=Strict`.
- Proteccion SSRF del cache de imagenes, incluida la validacion de redirecciones.
- Allowlist exacta para hosts de imagenes y proxy limitado a JPEG, PNG, WebP, GIF y AVIF; SVG remoto queda rechazado.
- Cache de imagenes con limite total configurable, limpieza LRU, escrituras atomicas y comandos `info`, `prune` y `clear`.
- Job de CI que construye e instala el wheel en un entorno limpio y prueba comando, assets y healthcheck.
- Matching conservador y auditable con motivo y evidencia por candidato.
- Pruebas de regresion para seguridad HTTP, esquema, repositorios JSON/SQLite, gateways externos, modelos, capas y matching.
- Contratos durables de producto y diseno para preservar el posicionamiento, lenguaje visual y reglas de interaccion de Movie Inbox.
- Navegacion del visor separada en `Inicio`, `Coleccion`, `Bandeja`, `Club` y `Administrar`, con las tareas operativas fuera de la pantalla de descubrimiento.
- Inicio con spotlight pausable y una seleccion breve de obras disponibles en el catalogo.
- Coleccion con busqueda explicita, filtros combinables, orden, chips activos y carga incremental.
- Administracion dedicada para resumen, base de datos, fuentes externas, matching y duplicados.
- Cards de proporcion estable 2:3 con titulo, ano, disponibilidad, estado personal y puntuacion visible cuando existe.
- Navegacion movil inferior para `Inicio`, `Coleccion`, `Bandeja`, `Club` y `Random`, con cabecera compacta, areas seguras y controles tactiles.
- Coleccion movil en dos columnas con busqueda y filtros compactos, titulos adaptativos y feedback de pulsacion sin depender de hover.
- Ficha tipo dossier con registro personal en modo lectura, edicion explicita y acciones inmediatas para estado y disponibilidad.
- Navegacion contextual entre fichas, variante `Otro al azar` y confirmacion para guardar o descartar borradores antes de salir.
- Bandeja principal con contador de pendientes y colas dedicadas para posibles duplicados, entradas sin link y casos pospuestos.
- Decisiones de curaduria persistentes para `Posponer`, `No son duplicados` y `No requiere referencia`, con opcion de devolver un caso a pendientes.
- Esquema JSON v5 y esquema SQLite v3 para guardar el estado de referencias y las decisiones sobre pares duplicados.
- Comparador de merges campo por campo compartido por la Bandeja y los resultados externos, con seleccion explicita de la identidad superviviente.
- Proteccion de estado, fecha de vista, puntaje, review y notas ante conflictos; listas, links y archivos locales admiten combinacion controlada.
- Historial de las ultimas 50 decisiones de curaduria con Deshacer exacto para merges, casos pospuestos y descartes.
- Modos de historial persistente o limitado a la sesion, limpieza confirmada y bloqueo de restauraciones que pisarian ediciones posteriores.
- Autenticacion local con owner inicial, contrasenas `scrypt`, sesiones opacas persistidas por hash y limite de intentos de login.
- Base de instancia separada para cuentas, sesiones y pertenencia del catalogo, sin contaminar importaciones o exportaciones JSON.
- Bootstrap interactivo o mediante `movie-inbox account bootstrap`, con adopcion no destructiva del catalogo existente.
- Pantalla de acceso, identidad activa en el menu y cierre de sesion con revocacion inmediata.
- Ciclo de vida local de miembros con alta, desactivacion, reactivacion y reset de acceso desde Administrar.
- Contrasena temporal con cambio obligatorio y rotacion de la sesion al confirmar la credencial personal.
- Catalogos SQLite vacios creados automaticamente para miembros dentro de un directorio administrado.
- Resolucion del catalogo por sesion en todas las lecturas, mutaciones, merges, curacion y tareas en segundo plano.
- Referencias opacas de fuentes en la API para no exponer rutas absolutas ni aceptar rutas de catalogos ajenos.
- Privacidad opt-in por usuario para compartir catalogo, estado, fecha de vista, actividad, puntajes y reviews dentro de la instancia.
- Overrides por obra para compartir o mantener privados rating y review sin cambiar el default del usuario.
- Vista `Club` de solo lectura con estantes por miembro, actividad opcional y fichas compartidas sin rutas, archivos locales, notas ni metadata operativa.
- Edicion de username y nombre del catalogo, baja reversible de miembros y restauracion con nueva contrasena temporal.
- Colecciones locales persistentes, seguimiento independiente por usuario y copia selectiva al catalogo personal sin heredar disponibilidad, estado, rating o review.
- `Club` dividido en `Colecciones` y `Miembros`, con seleccion masiva, conteo de faltantes, deteccion de obras presentes y bloqueo de coincidencias ambiguas.
- Coleccion inicial versionada `Akira Kurosawa`, instalada una sola vez y disponible sin depender de una consulta de red durante el arranque.
- Esquema de instancia v3 con preferencias de privacidad, overrides por item, catalogos de miembros archivados, colecciones curadas y seguimientos.
- Bandeja de importaciones autenticada para TXT, CSV y JSON, con archivo o texto pegado, asignacion opcional de columnas y limites de 8 MiB, 10.000 filas y profundidad JSON.
- Borradores privados por usuario, limitados a 20, que persisten solamente filas normalizadas y expiran automaticamente a las 48 horas; el contenido original y las rutas locales no se guardan.
- Previsualizacion con estados `Nueva`, `Presente`, `Revisar` e `Invalida`, deduplicacion conservadora contra el catalogo y dentro del propio origen.
- Importacion idempotente al catalogo personal con controles para estado, fecha de vista, puntaje y review.
- Creacion de colecciones locales privadas desde un borrador para el owner, sin copiar registro personal ni modificar el catalogo.
- Esquema de instancia v4 con `import_drafts` e `import_draft_items` para retencion acotada y aislamiento por usuario.
- Scanner administrado desde `Administrar > Bibliotecas`, con rutas limitadas por `--library-root`, recorrido de prueba obligatorio, ejecucion manual y frecuencias horaria o diaria.
- Inventario fisico compartido por la instancia, separado de los catalogos personales y visible para miembros sin publicar rutas, nombres internos ni fingerprints.
- Disponibilidad con procedencia: la declaracion manual y la presencia verificada por el servidor se conservan como senales independientes.
- Cola `Bandeja > Scanner` exclusiva del owner para confirmar identidades nuevas, elegir coincidencias conservadoras o ignorar archivos.
- Ejecuciones persistentes con recuperacion tras reinicios, bloqueo de recorridos simultaneos, historial acotado y proteccion ante discos desmontados o bajas masivas.
- Esquema de instancia v5 con `media_libraries`, `library_scan_runs` y `library_files`.

### Corregido

- El scanner distingue rutas offline de errores de permisos, conserva siempre el ultimo inventario valido y cubre con pruebas de aceptacion la secuencia `Probar`, `Aplicar` y `Automatizar`, lecturas parciales y recuperacion tras reinicios.
- Bibliotecas y Scanner presentan ahora la secuencia real `Probar recorrido`, `Aplicar inventario` y automatizacion opcional; las frecuencias manuales ya no pueden activarse y el comparador explica diferencias, fuentes y alcance antes de vincular u omitir un archivo.
- El scheduler del scanner usa el ciclo de vida `lifespan` de FastAPI y la suite HTTP usa `httpx2`, evitando APIs retiradas y advertencias obsoletas en versiones actuales.
- Las consultas batch de metadata vuelven a continuar ante timeouts o respuestas invalidas, mientras el buscador conserva errores para el panel de salud.
- La ficha reinicia su scroll al cambiar de obra y las vistas restauran foco, URL y contexto sin conservar hashes ajenos.
- Formularios, estados deshabilitados y microtipografia comparten el mismo acabado; busquedas y comparaciones fallidas ofrecen recuperacion visible sin alertas tecnicas.
- La politica CSP del visor ya no necesita permitir JavaScript ni estilos inline.
- El visor vuelve a cargar catalogos tras completar el refactor que habia dejado normalizadores duplicados.
- Las expresiones regulares JavaScript embebidas ya no producen `SyntaxWarning` en Python.
- Los valores de texto `false` en metadata y archivos locales ya no se interpretan como verdaderos.
- Los dominios externos se validan por hostname exacto o subdominio, sin aceptar nombres como `imdb.com.example.org`.
- Los titulos iguales sin ano ya no se combinan automaticamente.
- Los catalogos futuros o mal formados ya no se leen como listas vacias ni se reescriben como v5.
- SQLite sincroniza solamente items y relaciones modificadas; los cambios de estado usan un `UPDATE` directo.
- Importacion y exportacion comparan documentos canonicos completos para detectar perdida de reviews, metadata, aliases o archivos.
- La normalizacion legacy ya no duplica un archivo local que tambien tiene `library_id` y `relative_path`.
- Los comandos batch ya no importan la interfaz web ni el importador monolitico.
- Los titulos largos y los estados de las cards se adaptan sin cambiar el alto de la grilla ni depender de hover en dispositivos tactiles.
- La busqueda local filtra una sola estanteria y reserva las cards auxiliares para fuentes externas o comparaciones explicitas.
- Consultas, filtros, orden y duplicados se restauran desde la URL sin alterar las estadisticas globales de otras vistas.
- `Ver coleccion` y la navegacion principal abren la estanteria sin una busqueda anterior; Atrás y Adelante restauran cada consulta desde la URL.
- La ruta de `Club` se restaura con Atras y Adelante sin revivir una busqueda anterior de la Coleccion.
- Los imports web descartan `local_path`, `local_name` y `local_files`, vuelven a comprobar coincidencias antes de escribir y no consultan fuentes externas durante la previsualizacion.
- El scanner indexa titulos y terminos una vez por recorrido, evitando comparar cada archivo contra todo el catalogo sin relajar las reglas de matching.
- Las copias identicas conservan IDs de inventario separados y la deteccion de movimientos prioriza siempre una ruta original que todavia existe.
- Las sugerencias del Scanner excluyen catalogos privados de miembros y las vistas compartidas eliminan nombres de bibliotecas incluso si un caller aporta procedencia detallada por error.

## [0.1.0] - 2026-07-13

### Agregado

- Importacion de URLs y titulos desde TXT hacia catalogos JSON/CSV.
- Enriquecimiento mediante Wikipedia, IMDb, FilmAffinity y Wikidata.
- Limpieza de nombres de releases y deteccion de posibles duplicados.
- Visor web local con busqueda, filtros, cards, detalle y paginado incremental.
- Operaciones CRUD sobre el JSON con confirmacion antes de eliminar.
- Estados `to_watch` y `watched`, fecha de visualizacion, puntaje y review.
- Titulos original, espanol e ingles, ademas de aliases alternativos.
- Genero, direccion, guionistas, reparto e imagen principal cuando estan disponibles.
- Registro independiente de disponibilidad fisica mediante `en_catalogo` y `local_files`.
- Busqueda y combinacion manual con resultados de fuentes externas.
- Deteccion y filtro de entradas duplicadas por URL o titulo/ano.
- Procedencia por campo y bloqueos para proteger correcciones manuales.
- Cache local de imagenes y cache temporal de busquedas externas.
- Adaptadores externos independientes con estado y latencia visibles.
- Escrituras atomicas, bloqueo por catalogo y backups rotativos.
- Esquema JSON versionado y migracion compatible con catalogos anteriores.
- Extension Chrome Manifest V3 para guardar pestanas y exportar JSON/CSV.
- Scanner Bash recursivo para crear un catalogo desde archivos de video.

### Datos

- Los estados personales (`status`, `watched_at`, `rating` y `review`) se mantienen separados de la disponibilidad fisica (`en_catalogo`).
- Los archivos generados, catalogos personales, reportes y backups no forman parte del repositorio.
