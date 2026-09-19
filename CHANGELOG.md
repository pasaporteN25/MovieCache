# Changelog

Los cambios relevantes del proyecto se documentan en este archivo.

## [Sin publicar]

Va a ser la **0.9.0**. La versión está abierta en la rama `release/0.9.0` y se cierra al
fusionar su PR contra `master`; hasta entonces se le pueden sumar cambios. Todavía no está
pulida: varias capacidades nuevas del servidor no tienen pantalla —cada entrada lo dice— y
el trabajo visual de Inicio sigue en curso.

### Antes de actualizar

- **Hacé un backup: las bases no vuelven atrás.** La 0.9.0 migra `instance.db` del esquema
  v11 al v22 y la base del catálogo (`movie-inbox.db`) del v5 al v6 apenas las abre, y
  guarda un catálogo JSON en el formato v10 —antes v9— en cuanto lo escribe. La 0.8.0 se
  niega a abrir cualquiera de las tres ("newer than supported"): volver a la 0.8.0 exige
  restaurar el backup (`movie-inbox backup` o, en Docker, `bash scripts/docker-backup.sh`).
  Un catálogo JSON suelto no lo cubre `movie-inbox backup`: copialo antes.
- **Si usás el índice local de IMDb, regeneralo** con `movie-inbox imdb-dataset sync`. Su
  formato cambió, y hasta regenerarlo la instancia enriquece como si no lo tuviera y no
  muestra puntajes de IMDb.
- `pip install` y la imagen de Docker instalan solos `segno`, la dependencia nueva.
- No se retira nada: subcomandos, opciones de la CLI, rutas web, variables de entorno y
  campos del JSON portable y de la base del catálogo siguen como en la 0.8.0. Lo único que
  cambia en ellos es que suman un campo, `personal_changed_at` (ver más abajo), y por eso
  suben de versión.

### Agregado

- Inicio ahora se presenta como una videoteca empotrada: una cartelera diaria a la
  izquierda, otra de consulta a la derecha y una consola única. La obra consultada se
  conserva separada de la rotación Hoy/Ayer y sus acciones respetan si pertenece al
  catálogo personal o a una colección seguida del Club.
- La estantería usa lomos VHS más legibles, placas de categoría activables y material
  compartido de petróleo/latón. Las imágenes de la consola reservan su espacio, admiten
  cero, una o dos imágenes y dejan abrir la ficha aunque una carga falle.

- La instancia puede decir dónde se ve en streaming cada obra del catálogo propio. El
  owner elige en Administrar qué mercados se consultan, cuál es el predeterminado y si
  los miembros pueden elegir el suyo; las plataformas se traen de TMDb, con la
  atribución a JustWatch que exigen sus términos. Cada consulta se guarda como una
  observación fechada: se refresca a los 30 días y deja de servirse a los 180. Tener el
  archivo y estar en una plataforma siguen siendo cosas distintas, y "no lo consultamos"
  nunca se presenta como "no está disponible". La ficha todavía no lo muestra.
- Los puntajes públicos de IMDb y de TMDb se sirven al lado del puntaje propio, nunca en
  su lugar: ningún camino lleva un puntaje público al puntaje personal. Los de IMDb
  salen del índice local; los de TMDb se guardan con fecha, igual que la disponibilidad.
  Un puntaje con menos de 50 votos llega marcado como poco representativo. La ficha
  todavía no los muestra.
- Con el índice local de IMDb configurado, la instancia lo usa como primera fuente para
  siete campos —título, título original, títulos alternativos, tipo de obra, año,
  duración y géneros—, como ya indicaba la política de autoridad; los títulos
  alternativos se suman a los que ya había en vez de reemplazarlos. Se consulta sólo por
  identificador de IMDb, nunca por título, y una instalación sin índice enriquece igual
  que antes.
- Mazos de charadas deterministas sobre el catálogo propio y las colecciones seguidas:
  las mismas opciones sobre las mismas obras dan el mismo mazo, con un código corto para
  que dos jugadores comprueben que tienen el mismo. La dificultad se sugiere sólo en los
  extremos; el resto lo decide una persona, y esa decisión sobrevive a cualquier
  recálculo. Todavía no tiene pantalla.
- Una API versionada para clientes de dispositivo, bajo `/api/v1/`, con su contrato
  publicado en `docs/openapi/device-api-v1.openapi.json`. Cubre lo que necesita un
  teléfono: iniciar, renovar y cerrar su sesión, listar, buscar y leer el catálogo
  propio, y editar estado, fecha de visionado, puntaje y review. Las sesiones son por
  dispositivo: el acceso vence a los 15 minutos y la renovación a los 30 días, viajan
  sólo en el encabezado `Authorization` —nunca en una cookie ni en la URL—, se guardan
  como hashes y se invalidan al cambiar la contraseña o al desactivar o archivar la
  cuenta; el inicio de sesión tiene límite de intentos. Cada obra se identifica con un
  id opaco que no revela rutas ni archivos, y que no cambia al rotar el token de la API
  ni al mover el archivo del catálogo. Scanner, administración y Curaduría quedan
  afuera. Todavía no hay aplicación que la use.
- Un dispositivo se puede aparear con una cuenta mediante un ticket de un solo uso, sin
  que viaje una contraseña: una sesión web lo emite para su propia cuenta y el servidor
  lo dibuja como QR. El ticket vence a los cinco minutos, y cambiar la contraseña o
  desactivar la cuenta lo anula junto con las sesiones. `serve` puede servir HTTPS por su
  cuenta con un certificado propio (`--ssl-certfile`, `--ssl-keyfile`) y calcula la
  huella que el QR le lleva al teléfono; `movie-inbox pairing-pin` la imprime para cuando
  HTTPS lo termina un proxy. Todavía no hay pantalla que muestre el QR ni aplicación que
  lo escanee.
- La API de dispositivo también recibe el alta sin conexión —lo que un teléfono agrega
  sin red entra en un borrador que no vence y pasa por la revisión de siempre— y sirve
  las colecciones seguidas, la disponibilidad en streaming, los puntajes públicos y lo
  que un teléfono necesita para repartir sin conexión el mismo mazo de charadas que el
  servidor. La disponibilidad y los puntajes de TMDb llegan con la fecha en que el
  teléfono tiene que dejar de mostrarlos.
- Cada obra recuerda cuándo cambió por última vez su estado (`status`, junto con la fecha
  de visionado), su puntaje y su review, y la API de dispositivo lo informa en
  `personal.changed_at`. Sólo informa: no decide qué lado de un conflicto gana, porque el
  reloj de un teléfono puede estar mal. Un campo que nunca se editó no figura, y las obras
  que ya existían empiezan sin marcas: se llenan a medida que se editan. Es un campo nuevo
  del JSON portable (`personal_changed_at`, esquema v10) y de la base del catálogo (v6), y
  sobrevive a `movie-inbox db export` e `import`.
- `PATCH /api/v1/catalog/items/{id}/personal` acepta un `base` opcional: el valor que el
  cliente tenía de cada campo cuando lo bajó. Si el servidor ya no vale eso, responde `409
  personal_conflict` y no escribe nada, en vez de pisar en silencio un cambio que hizo la
  web u otro teléfono. Sin `base`, sigue como antes: gana el último. Antes de esto, un
  teléfono que subía lo que vio al bajar perdía sin aviso lo que otro dispositivo había
  cambiado en el medio.
- Un teléfono cuya respuesta de renovación se perdió en un corte puede reintentar con el
  token que le queda: el anterior sigue valiendo 120 segundos después de reemplazado, y
  cada reintento devuelve un par nuevo. La ventana no se extiende con los reintentos y sólo
  vale el token inmediatamente anterior. El vencimiento sigue contándose desde la última
  sincronización.
- Cada cuenta ve los teléfonos que apareó —nombre, cuándo se creó la sesión y cuándo se
  usó por última vez— y puede desconectar cualquiera: `GET /api/device-sessions` y
  `DELETE /api/device-sessions/{id}`, para cualquier cuenta y sólo sobre las propias. El
  teléfono desconectado queda afuera en su próxima llamada y tiene que volver a aparearse.
  La respuesta no trae nada que sirva para autenticar. Todavía no hay pantalla que lo
  muestre.
- Un teléfono puede preguntar qué pasó con las obras que mandó sin conexión:
  `POST /api/v1/catalog/drafts/receipts` responde, por cada id que generó, si sigue esperando
  revisión, si se aplicó —y entonces trae el id de la obra en que se convirtió, para que
  enlace su copia local con la del servidor en vez de tener las dos—, si se descartó y por
  qué, o si el servidor no tiene registro y hay que reenviarla. Un reintento que llega
  después de que el borrador se aplicó o se borró en la web ya no agrega las obras otra vez:
  antes sólo se miraba el borrador mientras seguía esperando. Una obra dudosa nunca se enlaza
  a una candidata del catálogo, y un borrador aplicado no se reabre, así que lo que quedó sin
  aplicar se informa como descartado. Los recibos ya resueltos se olvidan al año; los
  pendientes no.
- Vectores de prueba para el cliente Android, calculados por el propio servidor y
  verificados en cada corrida de pruebas: la huella del certificado con los payloads del QR
  (`docs/briefs/pairing-certificate-v1-vectors.json`) y la normalización de títulos
  (`docs/briefs/title-normalization-v1-vectors.json`).
- `movie-inbox images coverage` cuenta, por causa, por qué las obras no llenan las dos
  ventanas de imágenes de la consola: campo vacío, dirección que el proxy rechazaría o
  imagen todavía sin caché, y cuántas imágenes distintas tiene cada obra —dos tamaños de
  la misma imagen cuentan como una—. Lo separa por tipo, por origen —catálogo o Club— y
  por identidad. No descarga nada ni consulta proveedores, y sólo imprime totales: no
  nombra títulos, direcciones ni rutas.

### Cambiado

- Elegir un VHS programa la lista con el conjunto editorial de ese estante, actualiza
  consola y cartelera de consulta, y ofrece «Volver a programación» sin alterar el
  carrusel diario. Teclado, foco, anuncios de selección y listas largas conservan el
  contexto al cambiar fuente, día, tamaño o disponibilidad.

- La búsqueda del catálogo dejó de leer una coincidencia de letras como si fuera una
  palabra compartida. Un artículo en común ya no acerca dos títulos, una palabra corta
  metida adentro de otra más larga ya no cuenta, y la comparación de respaldo mide las
  palabras con contenido en vez de las cadenas crudas: buscar "The Fly" ya no trae
  "M. Butterfly" por encima de "The Flies".
- Un término corto encuentra el título al que pertenece. "Ed" llega a "Ed Wood", y un
  título de una sola letra como "M" se puede buscar por su propio título, con o sin año;
  antes la consulta se descartaba entera. Nada de esto habilita un auto-match nuevo: la
  aceptación se sigue decidiendo con la misma evidencia de identidad de siempre.
- El índice local de IMDb ocupa unas siete veces menos: guarda sólo los tipos de obra y
  las regiones que el catálogo usa. Un índice construido antes se detecta como viejo y
  pide volver a sincronizarse.
- La instalación suma una dependencia, `segno`, que dibuja en el servidor el QR de
  apareamiento. Es Python puro y no trae dependencias propias.

- Guardar desde la ficha ya no borra los campos que no se mandaron: `POST /api/personal`
  escribe sólo el puntaje, la fecha o la review que recibe, en vez de tomar los que faltaban
  como vacíos. Acepta además un `base` —lo que tenía cada campo cuando se abrió la ficha— y,
  si ya no coincide, responde 409 `personal_conflict` sin escribir. Un pedido sin ningún
  campo es un 400. **La ficha todavía manda los tres campos y no manda `base`**, así que el
  caso de un teléfono que sube un puntaje mientras la ficha está abierta no queda cerrado
  hasta que la ficha lo use; ver `tareas.md`, [X8.4].

### Corregido

- Abrir una colección, refrescar una importación y armar la pantalla de inicio dejan de
  ponerse lentos a medida que crece el catálogo. Las tres comparaban cada ficha contra
  el catálogo entero y volvían a normalizarlo de cero en cada comparación: con 5000
  fichas y una colección de 200, eso eran 25 de los 28 segundos que tardaba la página.
  Ahora el catálogo se prepara una vez por pantalla.
- Compartir la disponibilidad de una biblioteca dejaba de funcionar en silencio si la
  biblioteca tenía dos copias de la misma película y una se había escaneado antes de que
  su ficha se enriqueciera: la obra se reportaba dos veces, la colección no se llegaba a
  crear y la única señal era que el interruptor volvía sin publicar nada. Ahora las
  copias se cuentan juntas, como siempre debieron.
- Un mismo artículo de Wikipedia dejó de aparecer dos veces en su estante. Wikipedia se
  alcanza por dos caminos —su buscador y una resolución por título exacto— y las dos
  filas traían el mismo artículo con direcciones que sólo se diferenciaban en cómo
  estaban escapados los paréntesis de "The Fly (1986 film)". Como casi toda ficha de
  cine está desambiguada así, pasaba seguido, y justo cuando la consulta estaba en otro
  idioma que el artículo.
- Cuando una fuente externa contesta pero nada de lo que trae sirve, Movie Inbox vuelve
  a intentar con un título alternativo confirmado, igual que hacía cuando la respuesta
  venía vacía. Antes bastaba con que la fuente devolviera cualquier cosa para que no se
  reintentara: buscar "Der Untergang" en FilmAffinity traía cinco películas y ninguna
  era la buscada, y el reintento que la encuentra no llegaba a correr.
- FilmAffinity vuelve a encontrar una película buscada por su título original. Cuando la
  búsqueda resuelve a una sola película el sitio no devuelve un listado sino la ficha, y
  Movie Inbox la leía como si fuera un listado: devolvía los enlaces de navegación de la
  propia página ("Ficha", "Imágenes") como si fueran películas, y la que se estaba
  buscando quedaba afuera. Buscar "Sen to Chihiro no kamikakushi" devolvía ocho filas y
  ninguna era El viaje de Chihiro, que estaba arriba de todo en la respuesta.
- Buscar una película por su título original en otro idioma vuelve a encontrarla en
  Wikipedia y en FilmAffinity. El reintento con un alias confirmado por Wikidata ya
  existía, pero la fila que encontraba llegaba sin rastro de la consulta que la había
  encontrado, así que el puntaje la descartaba salvo que el título de mercado se
  pareciera al original. "Der Untergang" contra "El hundimiento" daba 13.9 sobre un piso
  de 28; ahora la fila viaja con el título original que la encontró.
- La colección que publica una biblioteca ya no sale ordenada por un identificador
  interno. Se lee alfabéticamente por el título que se muestra, igual que la grilla del
  catálogo, y una película ya no cambia de lugar en una colección que otros están
  mirando sólo porque el enriquecimiento le encontró un id.
- La descarga de los datasets de IMDb vuelve a verificar el certificado en modo
  estricto. La excepción que se había agregado culpaba a la cadena de Amazon por lo que
  en realidad hacía un antivirus que intercepta HTTPS; sin él, la cadena verifica sin
  relajar nada.
- Los resultados de TMDb dejan de mostrarse como "Sin fuente". La etiqueta faltaba en el
  frontend desde que la fuente existe, y además de verse mal le quitaba un dato real a
  la desambiguación de duplicados, que compara etiquetas.
- Traer los datos de una obra desde una dirección de FilmAffinity deja de fallar cuando
  el sitio responde vacío. Python 3.11.16 y 3.14.7 cambiaron por dentro el lector de HTML
  de la biblioteca estándar, que empezó a guardar su estado con un nombre que el lector de
  fichas de FilmAffinity ya usaba para el suyo: con una respuesta vacía, el pedido
  terminaba en un error en vez de volver sin datos. Pasa desde esas versiones de Python, y
  la imagen de Docker toma la última 3.11 cada vez que se reconstruye.
- Bajar el catálogo a un teléfono por páginas ya no se corta cuando el servidor se reinicia
  a mitad: el cursor se firmaba con el token de la API, que `serve` regenera al azar en
  cada arranque, y la página siguiente respondía 400. Ahora se firma con el secreto
  durable de la instancia, el mismo que fija los ids de las obras.
- Esa misma descarga por páginas ya no se saltea una obra ni repite otra cuando el
  catálogo cambia mientras se baja: paginaba por posición, así que una obra agregada o
  quitada corría todas las siguientes. Ahora retoma después de una clave estable —título,
  año e id—. La búsqueda sigue paginando por posición, porque su orden es por relevancia.
- El contrato de la API de dispositivo declara los rechazos que el servidor ya daba y no
  avisaba: 409 (`draft_busy`, `device_draft_full`, `draft_limit_reached`) al enviar altas
  sin conexión, y 400 al pedir una página con un cursor inválido.

## [0.8.0] - 2026-09-02

### Agregado

- Inicio reemplaza el carrusel por un selector editorial fijo, navegable con flechas,
  Inicio/Fin, Enter y foco de teclado, y suma estanterías horizontales para las
  categorías editoriales existentes sin abrir nuevos endpoints ni alterar el catálogo.
- Las tarjetas y su preview reutilizan un kit visual de VHS con estados explícitos,
  movimiento reducido, foco visible y adaptación móvil. El asset genérico generado
  para el cassette está auditado, versionado y se distribuye dentro del paquete.

### Cambiado

- La pantalla principal mantiene la selección y el desplazamiento de estantería al
  cambiar de categoría, por teclado, puntero o touch, conservando los estados vacíos
  y los límites de privacidad de cada sección.

## [0.7.0] - 2026-09-02

### Agregado

- El owner puede crear una cartelera publica opt-in desde una coleccion propia. Cada
  enlace usa una capacidad opaca almacenada solo como hash, sirve un snapshot v1
  minimizado y puede refrescarse o revocarse sin exponer Club, sesiones, catalogos,
  IDs, rutas, imagenes ni estado personal.
- Jikan incorpora direccion desde staff solamente al elegir una candidata, con un
  presupuesto maximo de dos llamadas, atribucion visible y cooldown por fuente para
  `429`/`Retry-After`, timeouts y errores 5xx.
- `movie-inbox anime-dataset sync/stats/lookup` construye de forma opt-in un indice
  SQLite atomico desde un snapshot local de `anime-offline-database`, conserva fecha,
  licencia y hash, y consulta títulos multilingues, MAL e IDs cruzados sin tocar el
  catalogo.
- Un indice configurado completa aliases e IDs de resultados Jikan y funciona como
  respaldo rotulado cuando la fuente viva falla o vuelve vacia. Sin indice, no agrega
  accesos al filesystem ni cambia el comportamiento de la instancia.
- `tmdb_id`/`tmdb_url` quedan como identidad fuerte de movie/TV: un ID compartido con el
  mismo tipo de medio auto-matchea, un ID o tipo de medio en conflicto bloquea el merge
  automatico. El owner puede previsualizar y purgar de forma auditable toda contribucion
  TMDb persistida (respetando ediciones manuales, `locked_fields` y valores respaldados
  tambien por otra fuente) con historial y deshacer.
- La estanteria de busqueda y el panel de salud muestran TMDb unicamente cuando la
  instancia tiene el token configurado, con el logo oficial y el aviso de no-endoso
  exigidos por sus terminos. `429`/`Retry-After`, backoff y cache muy por debajo del
  tope de seis meses ya se heredaban del mecanismo generico de fuentes externas.
- La receta de despliegue separa el host privado de la aplicacion del host publico de
  cartelera, ambos por HTTPS y con Uvicorn limitado a loopback. Incluye bootstrap ACME,
  renovacion, cabeceras de proxy sin spoofing y validacion temporal de Nginx en CI.
- El contrato de paquetes entre homeservers define una coleccion portable por archivo,
  identidad tecnica de instancia, integridad, conflictos, revocacion y privacidad sin
  servicio central. El prototipo manual es solo offline: no abre red ni importa datos
  de la instancia; Ed25519 queda reservado para una entrega interoperable posterior.

### Cambiado

- Curaduria presenta cada componente conectada de duplicados como un solo caso de dos
  o mas entradas. La mesa permite elegir la identidad superviviente y resolver valores
  de todo el grupo; la combinacion N-a-1, su historial y Deshacer son una unica
  operacion atomica incluso cuando participan varios catalogos.
- La resolucion automatica cuenta y procesa grupos, no pares obsoletos: un conflicto
  personal conserva intactos todos los miembros para revision humana.

### Corregido

- Una fusion revisada ya no completa silenciosamente un campo vacio marcado en
  `locked_fields`; el valor bloqueado se conserva salvo decision humana explicita.

## [0.6.0] - 2026-08-31

### Agregado

- La hoja de ruta convierte las direcciones pendientes en un backlog ordenado con
  alcance, dependencias, criterio de cierre y decisiones bloqueantes separadas de la
  cola ejecutable.
- El gate de mypy estricto cubre los 103 módulos de producto y toda la suite de tests,
  protegido de forma consistente en PowerShell, shell y CI. Los tests conservan solo
  excepciones acotadas para callbacks dinámicos y atributos de fixtures Playwright;
  ningún paquete de producto usa `ignore_errors` ni reglas rebajadas.
- El enriquecimiento de Wikidata aprovecha la entidad ya descargada para
  incorporar duración en minutos, países, idiomas originales, productores y
  compositores. Los cinco campos forman parte del modelo portable, conservan
  procedencia y bloqueos, migran el JSON a schema v7 y hacen round-trip en
  SQLite v5, importaciones y exportaciones.
- Search Lab incorpora un corpus de respuestas externas grabadas y un gate reproducible
  por fuente e idioma. Distingue si una obra nunca fue devuelta o si Movie Inbox la
  descarto, sin consultar la red ni usar catalogos personales en CI.
- La consulta explicita `director:Nombre` y su control visible permiten descubrir la
  filmografia local y consultar fuentes externas. La coincidencia queda rotulada como
  direccion y nunca se usa como prueba de identidad, auto-match o merge.
- `movie-inbox imdb-dataset sync/stats/lookup` descarga de forma opt-in los datasets
  oficiales no comerciales `title.basics` y `title.akas`, construye un SQLite separado
  y ofrece consultas de solo lectura con atribucion. No toca el catalogo ni se activa
  al instalar o arrancar el servidor.
- Cada biblioteca puede sumar reglas de exclusion tipo glob sobre los defaults seguros,
  previsualizar el efecto y distinguir archivos recien excluidos de archivos ausentes.
- El admin puede publicar la disponibilidad confirmada de una biblioteca como coleccion
  de Club, editar titulo y descripcion y retirarla sin borrar seguidores. La coleccion
  comparte obras, nunca rutas, nombres de archivo ni estado operativo.
- Al agregar desde otra fuente, una identidad fuerte puede enriquecer la ficha existente
  en vez de crear un duplicado. La operacion conserva datos personales, queda en
  Actividad y puede deshacerse; las coincidencias ambiguas siguen requiriendo revision.
- Una matriz de autoridad por familia de campo documenta el orden de relleno entre
  fuentes. Ninguna fuente pisa un valor ya cargado y `locked_fields` mantiene prioridad.
- El contrato para grupos de tres o mas duplicados y sus casos de caracterizacion dejan
  preparada la implementacion N-a-1 sin ocultar los limites actuales del flujo por pares.

### Cambiado

- El planificador externo reintenta Wikipedia y FilmAffinity con un numero acotado de
  aliases confirmados; IMDb tambien puede reconstruir una candidata por ID cuando su
  endpoint de sugerencias vuelve vacio.
- Los anos ambiguos dentro del titulo conservan una lectura literal segura: `Verano
  1993` puede recuperar `Estiu 1993`, mientras `(2017)` sigue funcionando como ano de
  estreno y los remakes no ganan evidencia automatica incorrecta.
- La busqueda conserva alfabetos no latinos, reutiliza lecturas de catalogo sin cambios
  y prefiltra catalogos grandes. El benchmark sintetico de 10.000 obras redujo una
  consulta exacta de aproximadamente 1,43 s a 0,17 s.
- El catalogo personal que habia quedado en el historial publico fue purgado de ramas y
  tags remotos sin leerlo ni borrar la copia local ignorada.

### Corregido

- El carnet de acceso recupera una proporción horizontal y un botón `Entrar`
  compacto, sin la leyenda técnica `Validar //`.
- La opción para mostrar la contraseña pasa del checkbox a un botón de ojo
  accesible integrado en el campo de contraseña.
- La búsqueda conserva títulos japoneses y otros alfabetos en vez de reducirlos
  a una clave vacía; la evidencia multilingüe de Wikidata consulta español,
  inglés y japonés.
- Una ficha `anime` y un resultado externo `película`/`serie` con el mismo
  título y año vuelven a aparecer al comparar como revisión de formato, sin
  convertirse en combinación automática.
- Refinar el texto durante `Comparar` o al buscar una referencia conserva la ficha y el
  modo originales incluso con cero resultados, reintentos y navegacion atras.
- El backup de Docker valida permisos con el usuario real del contenedor de mantenimiento
  en vez de exigir que el runner de CI pueda escribir el directorio `root:root`; el
  parser de `docker compose config` deja de emitir advertencias por escapes de `awk` y
  el gate inspecciona el archivo privado desde el propio contenedor de mantenimiento.

## [0.5.0] - 2026-08-24

### Agregado

- Las 3 decisiones del Scanner (vincular a identidad existente, crear una
  ficha nueva y vincularla, u omitir el archivo) quedan registradas en una
  `Actividad` propia del Inventario (persistente o solo por sesión, igual
  que Curaduría) y pueden deshacerse: la operación restaura el estado
  exacto previo a la decisión, incluidas las candidatas detectadas
  originalmente y, para una ficha creada, su alta en el catálogo. Deshacer
  se rechaza si algo más tocó el caso después de la operación —por
  ejemplo, el enriquecimiento en segundo plano de una ficha recién creada.
- Cuando dos fichas duplicadas comparten título y año, la cola de
  Curaduría, el panel de detalle y el título del comparador de fusión ya
  no las muestran como texto idéntico: ahora distinguen por fuente
  (Wikipedia, IMDb, FilmAffinity, archivo local...), fecha de alta y
  archivo local asociado cuando existe.
- Nuevo botón "Resolver duplicados claros" en Curaduría: combina solo los
  pares de duplicados que no necesitan criterio humano (idénticos, o que
  difieren únicamente en un dato que un lado tiene vacío) y deja en la
  cola —ya con las señales de desambiguación de arriba— los que sí
  tienen un conflicto real (por ejemplo, dos puntajes distintos
  cargados). Cada combinación queda en `Actividad` y puede deshacerse
  individualmente.
- Curaduría suma búsqueda libre por título, año y tipo, sin distinguir
  mayúsculas ni acentos, y navegación circular con flechas por la cola
  visible. El mismo control de teclado funciona en `Actividad`.
- Si dos duplicados empatan también en archivo, fuente y fecha de alta,
  la cola, el detalle y el comparador los identifican como `Duplicado 1
  de 2` y `Duplicado 2 de 2` para que un conflicto personal real siga
  siendo resoluble sin inventar una identidad nueva.

### Cambiado

- Los lanzadores de compatibilidad con v0.1 (`txt_to_catalog.py`,
  `scan_library.py`, `view_catalog.py`, `enrich_catalog.py`,
  `match_external_links.py`, `migrate_catalog.py`) y los shims de import
  `catalog_*.py` se movieron de `scripts/` a `codigoLegacy/`, fuera de
  Git: nadie los ejecuta dentro de una instancia Docker, donde el camino
  es `movie-inbox <subcomando>` dentro del contenedor.
- Los ignores de datos personales bajo `scripts/` ahora cubren cualquier
  profundidad. El catálogo anidado que había escapado deja de estar
  trackeado sin borrarse del disco; también se retiran una salida vieja
  de checks y la copia redundante de la licencia.

- Los checks locales instalan las dependencias de desarrollo y ejecutan el mismo gate
  Ruff/mypy que CI antes de compilar y correr la suite.

### Corregido

- La búsqueda externa de IMDb ya conserva títulos originales, traducidos y
  alias encontrados por Wikidata cuando todos apuntan al mismo identificador
  de IMDb. También normaliza correctamente consultas con acentos, por lo que
  búsquedas como `Adiós tío Tom` y `Addio zio Tom` encuentran la ficha titulada
  `Goodbye Uncle Tom` sin usar reparto o dirección como prueba de identidad.
- El carnet de acceso presenta `Entrar` debajo de las credenciales como franja
  de validación, respeta el mismo orden visual y de teclado y deja el feedback
  dentro del carnet en anchos intermedios y móviles.
- La migracion de instancia v8 completa sin perdida las columnas de snapshot personal
  del historial de Scanner en bases que ya hubieran aplicado la definicion temprana de
  v7. Las instalaciones nuevas y las v7 ya completas convergen al mismo esquema.
- El smoke test de Docker Compose reintenta una unica salida transitoria de `up`, pero
  sigue fallando y mostrando estado/logs si el servicio no llega realmente a saludable.
- El estado combinado de decisiones del comparador de fusión se anuncia
  como una única región viva y el botón final lo usa como descripción,
  evitando dos avisos separados para lectores de pantalla.

## [0.4.0] - 2026-08-22

### Agregado

- La Bandeja distingue alcance compartido de personal: los modos pasan a
  llamarse `Tu catálogo` e `Inventario de la instancia · Admin`, una franja
  persistente muestra qué de los tres estados (archivo físico, identidad
  compartida, ficha en tu catálogo) afecta la decisión actual, y el aviso de
  pendientes separa cuántos son tuyos de cuántos son del inventario en vez
  de sumarlos en un solo número.
- La cola de Scanner se organiza por causa y confianza en vez de solo
  `Comparar`/`Sin coincidencia`: cada caso se etiqueta como `Falta identidad`,
  `Conflicto de año/tipo`, `Probable ficha existente` o `Sin señales`, tanto
  en la fila de la lista como en el detalle, con filtros nuevos para cada
  una. Cuando un caso tiene más de 3 candidatas, se muestran las 3 de mayor
  similitud y el resto queda un clic atrás en "Ver N candidatas más".

### Corregido

- Curaduría y el comparador de fusión ya no muestran `manual: sí/no`. Ahora
  presentan la misma disponibilidad efectiva que Colección y la ficha:
  `Disponible` (o no) con su procedencia — inventario verificado, declaración
  manual, o ambas — en vez de lenguaje de implementación.
- Las confirmaciones de Scanner (vincular, crear obra, omitir) vuelven a
  mostrarse: el aviso quedaba oculto por error cada vez que Scanner estaba
  activo, así que ninguna confirmación exitosa era visible hasta ahora.
- Dos acentos dorados de advertencia (borde de error de búsqueda y de razón
  de coincidencia en Colección) y el ícono de "sin portada" de la ficha
  usaban tonos ligeramente distintos entre pantallas; ahora usan el mismo
  Rental Sticker Gold documentado en todos lados.
- Scanner ya no presenta "sin candidata" como "obra ausente": el mensaje pasa
  a ser `No encontramos una coincidencia segura`, aclara que la comprobación
  automática no es exhaustiva, y ofrece buscar en tu catálogo antes de dar de
  alta una ficha nueva. Cada candidata muestra además su procedencia
  (`En tu catálogo` / `Catálogo compartido`) junto a la razón de confianza.
- El borde superior/inferior de la barra de filtros de Colección usaba un tono
  de `--control-border` desactualizado, de antes del ajuste de contraste del
  P1-a; ahora usa el mismo color que el resto de la interfaz.
- El fondo del comparador de fusión, la ficha y el diálogo de cambios sin
  guardar usaban el mismo tono oscuro escrito a mano tres veces; el título
  cinematográfico del spotlight y su estado vacío usaban blanco puro en vez
  del blanco documentado; ahora los tres comparten los mismos tokens.
- La cola del Scanner y el comparador de fusión no mostraban ningún cambio
  visual al enfocar con teclado una fila o candidata que sí reacciona al
  pasar el mouse; ahora el foco por teclado se ve igual que el hover.
- "Scanner" ya no aparece en los últimos lugares donde había quedado (el
  estado vacío de la cola, el buscador y el panel de administración de
  bibliotecas); todos dicen `Inventario`, como el resto de la Bandeja.
- "Sin link"/"con link" pasan a ser "Sin referencia"/"Con referencia" en
  Curaduría, Administración y las tarjetas de búsqueda, coherente con el
  resto del vocabulario en español de la interfaz.
- La mesa de trabajo de Curaduría se salía de la pantalla en mobile en vez
  de pasar a una columna (afectaba también, de forma latente, a Scanner);
  ahora se ajusta correctamente al ancho del dispositivo.

## [0.3.0] - 2026-08-17

### Agregado

- Inicio conserva por usuario las recomendaciones destacadas de hoy y ayer en
  `instance.db`; un selector reemplaza la misma marquesina sin modificar el catalogo.

- Primer incremento de Search Lab para `v0.3.0`: corpus dorado empaquetado, respuestas
  externas grabadas y runner de Precision@5, MRR, Recall@5, resultados prohibidos y
  precision de auto-match sobre los cuatro contextos productivos.
- `movie-inbox search-lab inspect` permite revisar un export JSON en los modos catalogo,
  identidad y Scanner, con reportes JSON/HTML, sin red, locks ni escrituras sobre el
  catalogo inspeccionado. `--enforce` convierte los umbrales en un gate optativo.

- La cola del Scanner permite separar casos para comparar de archivos sin coincidencia,
  buscar dentro de los pendientes y crear una obra en el catálogo personal antes de
  vincular su disponibilidad física.
- Cuando ninguna candidata corresponde, `Conservar ambas` permite crear una obra distinta
  mediante una comprobación en dos pasos. La confirmación queda ligada a las coincidencias
  revisadas y registra la nueva pareja como `No son duplicados`.

### Corregido

- `Estrenadas un dia como hoy` reserva sus obras sin ocupar el primer programa y se
  presenta al final, como quinta seccion cuando la cartelera editorial esta completa.

- Los títulos formados por años, como `1917`, `1984` y `2001: A Space Odyssey`, conservan
  una identidad válida durante el matching. Agregar desde el Scanner vuelve a comprobar
  coincidencias fuertes y reutiliza la obra existente para no introducir duplicados.
- El Scanner ya no usa la presencia previa de candidatas como permiso implícito para
  crear otra ficha. Un título exacto con año diferente queda bloqueado para comparación
  y una coincidencia descubierta en la comprobación final puede vincularse directamente.
- La Bandeja distingue `Vincular`, `Agregar obra y vincular` y `Conservar ambas`: esta
  última requiere revisar nuevamente las coincidencias antes de crear una ficha separada.
- Curaduría detecta el patrón heredado en el que un título numérico quedó guardado
  también como año, para poder revisar casos como `1917 / 1917` frente a `1917 / 2019`
  sin tratar como duplicados a todos los remakes con años diferentes.
- Las cards y la ficha ya no presentan como contradictorias la disponibilidad efectiva
  y la declaración manual. La interfaz muestra `Disponible` cuando existe inventario
  verificado y detalla por separado si también hubo una declaración manual.
- Buscar un título corto como `Up` o `Us` ya no devuelve obras sin relación cuyo
  título simplemente contiene esas letras (`Setup`, `Suspiria`).
- La búsqueda de Colección y el comparador ya no confunden reparto, descripción,
  género, tags, director o guionistas con coincidencias de título: buscar `Heat`
  ya no muestra una película distinta solo porque su reparto o su sinopsis
  mencionan esa palabra. Esos campos siguen visibles en la ficha, pero dejan de
  competir con el título en el buscador.
- Buscar un título con año (`It 2017`) ya no muestra una ficha con el mismo
  título y otro año (`It 1990`) como si fuera coincidencia. El comparador
  tampoco ofrece un remake de otro año como candidata para fusionar con la
  obra correcta.
- Wikipedia, IMDb y FilmAffinity ya no muestran resultados sin relación real
  con la búsqueda (una obra distinta, un año equivocado): antes se mostraban
  igual mientras hubiera lugar en la estantería.
- Buscar un título formado por un año, como `1917` o `1984`, ya encuentra la
  ficha correcta en vez de devolver la lista vacía. Lo mismo para un título
  que empieza con un año, como `2001: A Space Odyssey`.

### Search Lab

- `movie-inbox search-lab run --enforce` ya pasa contra el corpus dorado:
  Precision@5 0.91, MRR y Recall@5 en 1.0, cero resultados prohibidos, cero
  falsos positivos de auto-match. CI corre este gate en cada cambio.

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
