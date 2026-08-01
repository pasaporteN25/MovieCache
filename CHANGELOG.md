# Changelog

Los cambios relevantes del proyecto se documentan en este archivo.

## [Sin publicar]

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
- Navegacion del visor separada en `Inicio`, `Coleccion` y `Administrar`, con las tareas operativas fuera de la pantalla de descubrimiento.
- Inicio con spotlight pausable y una seleccion breve de obras disponibles en el catalogo.
- Coleccion con busqueda explicita, filtros combinables, orden, chips activos y carga incremental.
- Administracion dedicada para resumen, base de datos, fuentes externas, matching y duplicados.
- Cards de proporcion estable 2:3 con titulo, ano, disponibilidad, estado personal y puntuacion visible cuando existe.
- Navegacion movil inferior para `Inicio`, `Coleccion`, `Bandeja` y `Random`, con cabecera compacta, areas seguras y controles tactiles.
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

### Corregido

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
