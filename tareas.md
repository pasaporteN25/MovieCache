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

## Resumen operativo

| Orden | Tarea | Resultado esperado | Dependencia |
| --- | --- | --- | --- |
| 1 | [U1] | Inicio videoclub: selector A + estanterias C | cierre v0.7.0 |
| 2 | [A1] | API versionada para dispositivos | D1 |
| 3 | [A2] / [I1] | Cliente Android / evaluacion de integraciones | A1 |
| 4 | [M1] | Descubrimiento de verticales propias | frentes previos estables |

- **En curso:** ninguna tarea; [D1], [W3], [U1.1] y [U1.2] ya tienen validacion y cierre verificables.
- **Cerrado recientemente:** [C2], [D1], [W1], [W2], [W3], [U1.1] y [U1.2]. El detalle verificable
  permanece en `Hecho`.
- **Lectura:** `Backlog` contiene solo trabajo pendiente; `Hecho` preserva decisiones,
  pruebas y commits sin mezclarlo con la cola.

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

### Frente: Fuentes externas y especializacion de anime

La epica [F2] quedo cerrada en tres entregas: contrato de composicion [F2.1], fuente
en vivo [F2.2] e indice/fallback [F2.3]. La evaluacion [F3] se dividio
en terminos/operacion [F3.1] y matriz/decision [F3.2], ambas cerradas; su implementacion
queda aislada en [F5]. [F4] se dividio en contrato de secretos/ciclo de vida [F4.1] e
ingreso operativo seguro [F4.2], ambas cerradas. La numeracion decimal expresa partes
de una epica, no una fase adicional del roadmap. [F5] queda dividido en nucleo de
consulta [F5.1], identidad/retirada [F5.2] y cumplimiento/UX [F5.3] (las tres cerradas).
[F5] queda completo.

### Frente: Superficie publica y despliegue

### Frente: Inicio videoclub (candidato v0.8.0)

**Decisión 2026-09-01.** La lámina generada 1 es una referencia de dirección, no un
asset ni contenido de la aplicación. El rediseño no comienza durante v0.7.0: primero
se cierran [D1] y [W3] y se publica ese incremento. El objetivo posterior no es sumar
un tema decorativo sino reorganizar Inicio: arriba la variante A como selector principal
y abajo la variante C como estanterías de descubrimiento. La cartelera pública puede
adoptar el mismo sistema visual más adelante, pero conserva el contrato aislado de
[W1]/[W2] y nunca gana acciones privadas.

#### [U1.3] Crear un kit VHS reutilizable y aplicar el sistema por superficie
- **Alcance**: abrir un trabajo de arte separado para producir el kit de activos
  (marco/caja VHS, texturas y variantes) y su licencia; los títulos, estados y botones
  se renderizan como HTML localizado, nunca dentro de una imagen. Implementar el
  componente con estados cerrada, seleccionada y abierta, `prefers-reduced-motion` y
  fallback sin animación. Aplicarlo primero a Inicio privado; evaluar en una tarea
  posterior la adaptación de la cartelera pública sin ampliar su payload v1.
- **Criterio de cierre**: assets auditables, componente reutilizable y pruebas visuales
  de escritorio/móvil/teclado; no hay requests externos ni contenido de owner dentro
  de los assets.
- **Depende de**: [U1.2].
- **Modelo sugerido**: Grande. Requiere una dirección de arte coherente y preserva
  accesibilidad, i18n y los límites de privacidad públicos.

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

Sin tareas activas.

## Hecho

### Frente: Inicio videoclub

#### [U1.1] Definir el selector fijo de Inicio a partir de la variante A
**Cerrado 2026-09-02, commit `f6a1c60`.** El carrusel inferior se reemplazó por un
selector editorial fijo que gobierna una única ficha panorámica, sin tocar las secciones
inferiores. `docs/briefs/home-selector-v1.md` fija el contrato: una a cuatro opciones,
estado vacío existente, orden selector → ficha en móvil y ninguna ruta/dato nuevo. El
selector usa botones nativos con roving tabindex; flechas, Home/End, Enter y clic
actualizan la ficha y conservan el foco, mientras `Ver ficha` abre el dossier ya
existente. `tests/browser/test_ui_browser.py` cubre foco, teclas, activación y ancho
móvil; la suite de navegador completa quedó en verde.

#### [U1.2] Convertir la variante C en estanterías horizontales con señales reales
**Cerrado 2026-09-02, commit `d5eae4b`.** `docs/briefs/home-shelves-v1.md` registra el
contrato de las filas sin modificar `/api/items`: el orden y los datos provienen de
`EditorialHomeService` (`available`, `followed`, `memory`, `route`/`recent` y
`anniversary`), cada una conserva hasta seis obras, su razón y su destino existente;
las vacías se omiten. La interfaz presenta etiquetas compactas en una tira horizontal
con selección roving y una ficha breve de portada, procedencia, metadatos y acción
explícita al detalle. Flechas, Home/End, Enter y clic actualizan la selección sin
trampas de foco; móvil conserva scroll táctil dentro de la tira, no de la página. La
prueba de navegador cubre esa interacción y el ancho; la caja VHS/activos reutilizables
quedan deliberadamente para [U1.3].

### Frente: Superficie publica y despliegue

#### [D1.1] Fijar la topología privada/pública de HTTPS
**Cerrado 2026-09-01.** La receta soportada separa `inbox` (login y aplicación) de
`cartelera` (solo `/p/`, `/public/` y tres assets mínimos), ambos detrás de Nginx y
contra un único Uvicorn loopback. `--public-presentation-origin` permite ese segundo
host en la allowlist de `Host`, pero no se agrega a los orígenes de login/CSRF. Las
pruebas confirman que el host público admite una lectura anónima uniforme y rechaza el
login con `invalid_origin`.

#### [D1.2] Documentar proxy, certificado, renovación y diagnóstico
**Cerrado 2026-09-01.** `docs/deployment.md` describe bootstrap ACME sin aplicación
HTTP, certificado SAN, Nginx de dos hosts, cabeceras reenviadas sin spoofing de IP,
HSTS opt-in, ausencia deliberada de WebSocket y hook de renovación. Las plantillas de
Nginx restringen la cartelera a sus rutas/activos y quitan de los logs cualquier
capacidad. Docker, systemd, `.env` y el checklist de release usan los nuevos orígenes.

#### [D1.3] Ejecutar la validacion descartable de la receta Nginx
**Cerrado 2026-09-02.** El workflow `tests` #76 para `f3287f2` termino exitoso e
incluyo la comprobacion temporal de ambos templates con `nginx -t`. El error observado
en el run #75 correspondia a `a8009da`, anterior a `ea2b68e`, que normaliza las rutas
Windows al pedir repositorios de catalogo durante el retiro externo. La regresion queda
cubierta por `tests/test_external_retirement.py`; la ejecucion local del modulo y la
suite completa la reproducen en verde. El checklist conserva hosts separados, loopback
y renovacion como controles de release.

#### [W3] Disenar paquetes compartibles y sincronizacion entre homeservers
**Cerrado 2026-09-02.** Se dividio y cerro en tres partes para separar las decisiones
de confianza del experimento de formato. `docs/adr/0002-homeserver-package-exchange.md`
define el limite de intercambio entre owners sin servicio central; el contrato y
prototipo son offline y no abren rutas, listeners ni clientes HTTP. La implementacion
productiva queda como trabajo posterior: identidad persistida, receipts, preview privado,
firma interoperable y pairing directo requieren sus propias tareas.

##### [W3.1] Casos de uso, identidad y privacidad
**Cerrado 2026-09-02.** El intercambio aprobado es de una coleccion curada que dos
owners ya decidieron compartir, por archivo o un canal que eligieron; no hay cuenta
global, directorio, DNS, descubrimiento ni relay. Cada homeserver futuro se identifica
con un UUID aleatorio persistente, sin usuario, host o dominio. El payload excluye por
allowlist rutas, archivos, bibliotecas, disponibilidad, estado personal, procedencia,
sesiones, configuracion y enlaces remotos.

##### [W3.2] Contrato, conflictos y revocacion
**Cerrado 2026-09-02.** `docs/homeserver-package-v1.schema.json` fija el manifiesto
versionado, la coleccion portable y su integridad SHA-256. El modo manual exige confirmar
digest/origen por un canal independiente; `ed25519` queda reservado para una entrega con
JCS, claves locales, rotacion y vectores cruzados, no se simula una firma. El importador
futuro primero hara preview privado: IDs externos compatibles+tipo sugieren merge, IDs
incompatibles lo bloquean y titulo/año/director nunca fusionan solos. Un paquete es una
foto: revocarlo no borra una copia ajena y la sincronizacion/pairing quedan fuera de v1.

##### [W3.3] Prototipo descartable sin red
**Cerrado 2026-09-02.** `scripts/homeserver_package_prototype.py` construye e
inspecciona exclusivamente un `.mipkg` manual (`manifest.json` + `payload.json`): JSON
estricto, allowlist, limite de 1 MiB, digest, nombres ZIP exactos y sin extraccion.
No importa catalogos ni modifica la aplicacion. `tests/test_homeserver_package_prototype.py`
cubre ronda completa, manipulación/doble entrada y campos privados/ZIP extra rechazados.

#### [W2.1] Persistir snapshots y separar la lectura publica
Se suma la migracion de instancia v11 con `public_presentations`: guarda solo el hash
SHA-256 de una capacidad URL-safe de 256 bits y un snapshot allowlist v1 de hasta 200
obras. El router publico propio sirve unicamente `GET`/`HEAD` para `/p/{capacidad}` y
`/public/v1/presentations/{capacidad}`; no interpreta cookies, no emite sesiones y
responde `404` uniforme para capacidades inexistentes, invalidas o revocadas. La
lectura lleva `no-store`, CSP sin terceros, `no-referrer`, robots cerrados y limite de
20 en rafaga / 60 por minuto por IP+capacidad.
2026-09-01.

#### [W2.2] Dar controles privados y revocables al owner
El panel admin permite elegir una coleccion propia, previsualizar el snapshot, crear la
cartelera, refrescarla de forma deliberada y revocarla. La URL con capacidad plana se
muestra una sola vez al crearla; listados posteriores guardan solo su resumen. Todo el
flujo owner usa las rutas privadas autenticadas y CSRF existentes; la pagina publica
queda desligada de Club, del catalogo personal y de tokens privados.
2026-09-01.

#### [W2.3] Publicar una cartelera responsive y verificar el limite
La landing anonima renderiza el contrato v1 como cartelera de videoclub sin imagenes,
IDs, enlaces externos ni estado de visitante. El navegador pide el JSON con
`credentials: omit`. Las pruebas HTTP verifican allowlist profunda, aislamiento con y
sin cookie, cabeceras, revocacion y ausencia de `Set-Cookie`; la prueba Playwright
abre una instancia anonima en viewport movil y valida la cartelera completa.
2026-09-01.

#### [W1.1] Delimitar la presentacion publica y su privacidad
**Cerrado 2026-09-01.** El ADR-0001 decide que la primera superficie publica no es
Club ni un catalogo personal: es una presentacion de disponibilidad activada por un
owner, construida desde un snapshot curado y sin publicacion implicita de cuentas,
bibliotecas o colecciones. La URL lleva una capacidad URL-safe aleatoria de 256 bits de
la que el servidor conserva solo el hash; no hay slugs, listado, busqueda ni OpenAPI
publica. El contrato excluye explicitamente identidad de miembro, IDs, rutas, archivos,
inventario, estado/review/nota personales, decisiones, procedencia, imagenes y enlaces
externos. El snapshot se refresca solo por accion del owner, por lo que un cambio de
Club, scanner o catalogo no ensancha la exposicion por arrastre.

#### [W1.2] Versionar payload y operacion segura
**Cerrado 2026-09-01.** `docs/public-presentation-v1.schema.json` define la allowlist
cerrada (`additionalProperties: false`): encabezado editorial y hasta 200 obras con
titulo, titulo original, ano, tipo, generos y duracion. El transporte sera
`/p/{capacidad}` mas `/public/v1/presentations/{capacidad}`, con `schema_version: 1`;
un cambio incompatible abre v2. La respuesta de contenido usa `Cache-Control: no-store`
para que revocar sea efectivo en la siguiente consulta, sin CORS ni cookies; solo assets
sin datos del owner podran ser inmutables. El limite fijado es rafaga de 20 y 60
lecturas/minuto por capacidad+IP, con `429`/`Retry-After`; los IDs invalidos, revocados
o inexistentes responden el mismo `404` generico.

#### [W1.3] Aislar sesiones y documentar amenazas
**Cerrado 2026-09-01.** El ADR exige router y servicio propios, exclusivamente
`GET`/`HEAD`, sin importaciones de `/api/*`, `SessionCatalog`, `PrivacyService` o
`CollectionService`, sin leer ni emitir cookies y sin escrituras. Las acciones del owner
siguen privadas y protegidas por CSRF; preview tampoco usa una capacidad. El modelo de
amenazas cubre enumeracion, fuga de campos, CSRF/sesion, revocacion, abuso, tracking,
cache y XSS, con verificaciones concretas para [W2]. La configuracion soportada para
Internet separa host publico y privado; [D1] proveera la receta HTTPS. El tablero y la
hoja de ruta reflejan que [W2]/[W3] dependen de estas tres partes. No se modifico el
comportamiento de la instancia: hoy continua completamente privada por defecto.

### Frente: Busqueda, comparacion y composicion de fuentes

#### [F2.1] Definir composicion, identidad y autoridad para anime
La decision del owner del 2026-08-29 se conserva: Jikan es la opcion primaria aceptada
para uso personal/no comercial, sin pedir permiso escrito a AniList por ahora, y
`anime-offline-database` es secundaria. La epica no era una sola tarea: faltaba el
contrato que evita mezclar dos bases con edades y semanticas distintas. Queda cerrado
asi:

1. **Roles**. Jikan es la fuente primaria de busqueda y metadata en vivo. Se consulta
   `/anime` para candidatos y solo despues de una seleccion se habilitan detalle y
   staff; no se multiplica el costo por cada tarjeta. `anime-offline-database` es un
   indice secundario local: aporta aliases e IDs cruzados, y puede responder con su
   propia procedencia cuando Jikan esta caido, limitado o no encuentra nada. Una fila
   offline nunca se rotula `jikan`.
2. **Identidad**. [F2.2] agrego dos campos canonicos: `mal_id` y
   `myanimelist_url`. Un `mal_id` compartido es evidencia fuerte de identidad; dos IDs
   MAL distintos son un conflicto y nunca se fusionan automaticamente solo por titulo
   y año. Direccion/staff sigue siendo descubrimiento, no identidad, igual que [Q4].
3. **Mapeo Jikan**. `title`/`title_japanese`/`title_english`, `titles` y `synonyms`
   alimentan titulo, original, ingles y aliases; no se inventa un titulo español si la
   respuesta no lo declara. `year` o `aired.from`, `synopsis`, imagen, generos y
   productores llenan sus equivalentes; `kind` es `anime`. `score`, `rank`,
   popularidad, episodios y duracion por episodio no se copian a `rating` ni a
   `duration_minutes`: esos campos locales tienen otra semantica. Staff puede aportar
   direccion solo en el detalle elegido.
4. **Autoridad/conflictos**. Se conserva la decision de [Q5]: autoridad significa
   orden de relleno, no sobreescritura. Manual/`locked_fields` gana siempre; Jikan
   llena vacios; el snapshot offline solo completa vacios, une aliases/IDs compatibles
   y nunca pisa a Jikan. Cada campo guarda la fuente y URL reales en
   `metadata_sources`. Un conflicto de identidad queda para Comparar/Curaduria.
5. **Resiliencia**. `429` respeta `Retry-After`; timeout/5xx abren cooldown visible en
   health y habilitan fallback si existe indice. Una respuesta vacia exitosa se
   distingue de un error: el indice puede buscar aliases, pero no cambia el estado de
   Jikan. Sin indice configurado, la app se degrada a las fuentes actuales.
6. **Licencia/atribucion**. Jikan se declara no oficial, no afiliado a MyAnimeList y
   responsabiliza al consumidor por respetar sus terminos; no se usaran rutas
   autenticadas. `anime-offline-database` esta bajo ODbL 1.0/DbCL 1.0: snapshot e
   indice quedan separados, reconstruibles y no empaquetados; la UI/CLI muestra
   atribucion al presentar sus datos. Esto es una restriccion de producto, no una
   opinion legal sobre usos futuros.

Fuentes verificadas el 2026-08-31: [README oficial de Jikan](https://github.com/jikan-me/jikan-rest/blob/master/README.MD),
[OpenAPI v4](https://raw.githubusercontent.com/jikan-me/jikan-rest/master/storage/api-docs/api-docs.json),
[README del snapshot](https://github.com/manami-project/anime-offline-database),
[licencia](https://github.com/manami-project/anime-offline-database/blob/master/LICENSE)
y [ultimo release](https://github.com/manami-project/anime-offline-database/releases/tag/2026-27).
El ultimo snapshot declara 41.537 entradas y 65% revisadas; el repo fue archivado el
2026-07-04, por eso es respaldo finito y no autoridad viva. Una consulta live de
control a Jikan devolvio `504` porque no pudo conectar con MyAnimeList: evidencia
concreta de que [F2.3] no es optimizacion prematura. Este item cierra el diseño; la
identidad, red y UI ya comenzaron a materializarse en [F2.2], mientras que el indice
offline sigue separado en [F2.3].
2026-08-31.

#### [F2.2] Integrar Jikan como fuente de anime en vivo
Jikan queda integrado como cuarta fuente, conservando `mal_id` y
`myanimelist_url` como identidad canonica de punta a punta. La busqueda usa una sola
consulta liviana; al seleccionar un candidato se permiten solamente detalle y staff,
con un maximo de dos llamadas adicionales. Staff aporta direccion solo para roles
`Director` y una falla en esa consulta no descarta el resto de la ficha.

La resiliencia es por fuente: `429` respeta `Retry-After`, mientras timeout y `5xx`
abren cooldowns acotados. Health expone estado, codigo, vencimiento y segundos hasta
el reintento; las respuestas fallidas no entran al cache. En la interfaz, Jikan tiene
estanteria y estados propios, reintento visible, atribucion y aviso de no afiliacion a
MyAnimeList. La pasada de diseño Impeccable convirtio cooldown, procedencia y fallback
en estados legibles y accesibles, sin agregar colores literales nuevos.

Quedaron cubiertos sin red: seleccion y staff, fallo parcial de staff, `429` con
`Retry-After`, timeout, `503`, health/cooldown, cache, identidad fuerte y envio de una
ficha desde navegador. Verificacion conjunta de [F2.2]-[F2.3]: 520 tests, Ruff,
formato, mypy estricto, sintaxis JavaScript y `git diff --check` en verde.
2026-08-31, commit `322d741`.

#### [F2.3] Construir indice offline de anime y fallback
Se incorporo `movie-inbox anime-dataset sync/stats/lookup` para construir de forma
atomica un SQLite separado y versionado desde un JSON/JSONL provisto por el owner. La
aplicacion no descarga ni distribuye el dataset: exige licencia ODbL/DbCL, URL HTTPS y
registra fecha, SHA-256, version y estadisticas. El indice conserva `mal_id`, IDs
cruzados, titulos y sinonimos con normalizacion Unicode y busqueda multilingue.

Con Jikan disponible, el indice solo completa aliases e IDs compatibles y conserva
la autoridad/procedencia de cada dato. Si Jikan responde vacio, `429`, `5xx` o
timeout, el resultado offline aparece como fuente propia dentro de la estanteria de
anime; nunca se rotula como Jikan. La activacion es opt-in por
`--anime-offline-index` o `MOVIE_INBOX_ANIME_OFFLINE_INDEX`; Docker cuenta con un
overlay de ejemplo que monta el archivo en modo solo lectura. Sin indice configurado
no hay llamadas al filesystem ni filas fantasma.

El build de control con el snapshot oficial `2026-27` proceso 41.520 entradas utiles
y omitio 17, genero 248.348 titulos/aliases y 189.506 referencias cruzadas en 7,9 s.
El indice resultante midio 77,5 MB y el snapshot de 62.331.124 bytes verifico el
SHA-256 publicado `8a63189782176fe19e00eca275288ba855ce54d6cb4d7ae97ec71450f861b1aa`.
El snapshot y el indice temporales se eliminaron despues de la medicion. Docker no
estaba instalado en el host de validacion; la estructura del overlay quedo cubierta
por una prueba automatizada.
2026-08-31, commit `322d741`.

#### [F3.1] Evaluar terminos y costo operativo de TMDb
TMDb es viable para esta app personal solo como fuente opcional. Requiere token/API
key; el uso no comercial puede usar la API sujeto a sus terminos, mientras que el
comercial necesita acuerdo escrito separado. La UI que consuma datos debe mostrar el
logo y el aviso prominente exigido: “This product uses TMDB and the TMDB APIs but is
not endorsed, certified, or otherwise approved by TMDB.” Los datos cacheados no
pueden conservarse mas de seis meses y, al terminar el uso, hay que dejar de llamar y
retirar el contenido sujeto a esos terminos. El cache de busqueda actual (15 minutos)
entra holgadamente, pero una ficha
persistida exige procedencia y una via de purga; no alcanza con llamarla “cache”.

El limite legacy de 40 requests cada 10 segundos ya no es el contrato; la
documentacion publica describe un techo aproximado de 40 requests por segundo que
puede cambiar, exige respetar `429` y recomienda backoff. El costo funcional se acota
con busqueda liviana y detalle bajo demanda, usando `append_to_response` cuando
corresponda. Una key nunca viaja al navegador, logs, export ni respuestas grabadas.

Fuentes oficiales verificadas el 2026-08-31: [terminos de API](https://www.themoviedb.org/api-terms-of-use),
[autenticacion](https://developer.themoviedb.org/v4/docs/authentication-application) y
[rate limiting](https://developer.themoviedb.org/docs/rate-limiting). Decision:
**apto con condiciones**, nunca default; [F4] debe resolver secretos/activacion antes
de implementar [F5]. Investigacion de terminos, no asesoramiento legal.
2026-08-31.

#### [F3.2] Comparar campos y decidir la integracion de TMDb
La evaluacion se hizo contra el contrato sintetico del proyecto, sin catalogos
personales ni una key prestada. La matriz resultante es:

| Familia | Aporte TMDb | Autoridad/transformacion acordada |
| --- | --- | --- |
| Identidad | `id`, IMDb y Wikidata externos | `tmdb_id` propio; IDs cruzados validan, uno divergente bloquea auto-merge |
| Titulos | original, localizado, traducciones y alternativos | une aliases; IMDb/Wikipedia conservan el orden de [Q5]; nunca traduce texto libre |
| Descripcion | `overview` localizado | Wikipedia primero; TMDb solo llena vacio antes del snippet IMDb/FilmAffinity |
| Estructurados | fecha, runtime, generos, pais e idioma original | normalizar vocabularios; llena vacios, no pisa manual ni `locked_fields` |
| Creditos | cast y crew con roles | mapear roles conocidos; personas nunca son evidencia de identidad |
| Imagenes | poster y backdrop por idioma/tamaño | candidato principal para `backdrop_image`; conservar URL/procedencia TMDb |
| Puntaje publico | `vote_average`/conteo | fuera de alcance: nunca se copia al `rating` personal |

La API documenta busqueda por titulos originales, traducidos y alternativos; detalle
localizable, traducciones, creditos e IDs externos cubren huecos reales de las fuentes
actuales. Referencias: [busqueda de peliculas](https://developer.themoviedb.org/reference/search-movie),
[idiomas](https://developer.themoviedb.org/docs/languages),
[detalle](https://developer.themoviedb.org/reference/movie-details),
[traducciones](https://developer.themoviedb.org/reference/movie-translations),
[creditos](https://developer.themoviedb.org/reference/movie-credits) e
[IDs externos](https://developer.themoviedb.org/reference/movie-external-ids).

Corpus de aceptacion transferido a [F5]: `Addio Zio Tom` prueba original/aliases e ID
IMDb; `Fanny & Alexander`, equivalencia de `&`/`and`; `Verano 1993 (2017)`, que el año
interno del titulo no desplace al año de estreno; y un homonimo movie/TV, que el tipo
no se pierda. [Q2]-[Q3] ya resolvieron localmente las dos primeras formas de variacion
y [Q4] la ambiguedad del año; TMDb debe recibir titulo/año/idioma estructurados y no
reimplementar ese parser. No se hizo una llamada live porque toda llamada exige key:
la comprobacion empirica queda como criterio de [F5], despues de [F4], con respuestas
grabadas sin secretos.

**ADR**: integrar TMDb de forma opt-in mediante [F5]. No reemplaza a las tres fuentes
actuales ni a [F2]; complementa campos con la politica fill-only de [Q5]. Esta decision
cierra [F3] y separa correctamente investigacion de implementacion.
2026-08-31.

#### [F4.1] Definir alcance, activacion y ciclo de vida de credenciales externas
La credencial de una fuente pertenece a la **instancia**, no a cada miembro: el owner
acepta los terminos y administra cuota, atribucion y retirada para todos los catalogos
servidos por ese proceso. La configuracion base sigue usando solo fuentes sin secreto;
una fuente con key se registra unicamente cuando su credencial valida esta presente.
Esto evita cuentas obligatorias y garantiza que una instalacion sin TMDb mantenga el
comportamiento actual.

Los secretos viven solo en archivos del servidor y en memoria del proceso. No se
aceptan como valor literal de CLI, variable con el token, formulario web, SQLite,
catalogo, export, fixture o log. La variable de entorno opcional contiene solamente la
ruta al archivo. El estado observable se reduce a `configured`/`not configured`, nunca
devuelve parte de la key.

Quitar la credencial desactiva las llamadas en el siguiente arranque, pero no borra
silenciosamente metadata ya incorporada. [F5] debe marcar toda contribucion persistida
con procedencia `tmdb` y proveer una retirada explicita y auditable. Esa operacion no
puede tocar valores manuales, campos bloqueados ni datos que otra fuente tambien
respalde; desactivar y purgar son decisiones distintas. Con esto quedan resueltas las
decisiones que bloqueaban la implementacion y [F5] puede recibir la credencial por
inyeccion sin conocer archivos ni variables de entorno.
2026-08-31, commit `96f07fb`.

#### [F4.2] Implementar ingreso seguro y opt-in de TMDb por instancia
`ExternalSourceCredentials` mantiene el API Read Access Token fuera del `repr` y de la
igualdad de `ViewerConfig`. `movie-inbox serve` acepta
`--tmdb-read-access-token-file` o la ruta
`MOVIE_INBOX_TMDB_READ_ACCESS_TOKEN_FILE`, limita el archivo a 16 KiB y rechaza vacios,
multilinea o whitespace. El arranque muestra solo si la credencial esta preparada y
aclara que el adaptador pertenece a [F5]; sin archivo queda vacia y no se hace ninguna
llamada.

Docker conserva `compose.yaml` sin TMDb y agrega el overlay explicito
`compose.tmdb.example.yaml`, que monta el archivo como secret de solo lectura. `.env`
guarda solo su ruta y la guia documenta activacion/desactivacion. Cobertura de regresion:
token con newline final, ausencia, vacio, multilinea, tamaño excesivo, `repr` y salida
sin filtraciones, mas contrato del overlay. Verificado junto al gate completo: 494
pruebas unitarias, Ruff, formato, mypy estricto, `compileall` y `git diff --check`.
Docker Compose no estaba instalado en el host de trabajo, por lo que el `config` real
del overlay queda como smoke de [F5.3]/CI antes de usar una credencial voluntaria.
2026-08-31, commit `96f07fb`.

#### [F5.1] Implementar el nucleo opt-in de TMDb
El gateway se configura al crear la app: sin API Read Access Token conserva exactamente
Wikipedia, IMDb, FilmAffinity y Jikan; con token agrega `TmdbAdapter` y su entrada de
health. El secreto queda en memoria del servidor, fuera del `repr`, y se envia solamente
como `Authorization: Bearer`; nunca forma parte de URL, respuesta, cache key o log.

La busqueda usa una sola llamada `/search/multi`, filtra personas y mantiene movie/TV
como `pelicula`/`serie`. Un `tt...` usa `/find?external_source=imdb_id` y conserva el
vinculo IMDb como evidencia para que el ranking no descarte una respuesta sin titulo
parecido al identificador. Una URL TMDb directa se valida por esquema, host exacto y
ruta `/movie|tv/{id}`. El detalle se pide solo al seleccionar y agrupa en una llamada
`append_to_response`: traducciones, titulos alternativos, creditos, IDs externos,
fechas e imagenes. Mapea `tmdb_id`, IMDb/Wikidata, runtime solo de peliculas, pais,
idioma original, generos, direccion, guion, produccion, musica, reparto, poster y
backdrop; ignora deliberadamente `vote_average`/popularidad y nunca toca `rating`.

El corpus sin red cubre `Addio Zio Tom`, `Fanny & Alexander`, `Verano 1993`, `Verano
1993 (2017)`, un homonimo movie/TV, busqueda por IMDb ID y detalle de ambos tipos. En el
camino se corrigio el parser compartido: `Verano 1993 (2017)` dejaba el titulo espurio
`Verano 1993 ()`; ahora conserva `Verano 1993` y separa `2017` para el ranking. El host
publico TMDb y `image.tmdb.org` quedaron en sus allowlists; la materializacion inicial
ya conserva procedencia `tmdb`, mientras las reglas fuertes de conflicto/purga siguen
aisladas en [F5.2].

Contrato contrastado el 2026-08-31 con documentacion oficial:
[autenticacion](https://developer.themoviedb.org/docs/authentication-application),
[multi search](https://developer.themoviedb.org/reference/search-multi),
[find](https://developer.themoviedb.org/docs/finding-data),
[detalle de peliculas](https://developer.themoviedb.org/reference/movie-details) y
[detalle de series](https://developer.themoviedb.org/reference/tv-series-details).
No hubo key ni llamada live: capturas reales, atribucion visual, `429` y smoke del
corpus pertenecen expresamente a [F5.3]. Verificado con 506 pruebas unitarias, Ruff,
formato, mypy estricto, `compileall` y `git diff --check`.
2026-08-31, commit `cbc5dc7`.

#### [F5.2] Integrar identidad, procedencia y retirada de datos TMDb
`tmdb_id`/`tmdb_url` quedan como identidad fuerte de movie/TV en `decide_match`: un ID
compartido con el mismo tipo de medio (movie/tv, inferido de la URL o de `kind`) auto
matchea con confianza 1.0; un ID compartido con tipo distinto o dos IDs TMDb distintos
bloquean el merge automatico, igual que ya hacia `mal_id` para anime. `domain/models.py`
y `infrastructure/schema.py` suman `tmdb_url` como campo portable; el schema JSON sube a
v9 con migracion v8→v9 y SQLite/import-export hacen round-trip completo.

`domain/external_retirement.py` implementa `retire_tmdb_metadata()`: recorre
`METADATA_FIELDS` y solo vacia un campo cuando TMDb es su unico contribuyente
registrado; procedencia compuesta conserva el valor y solo saca `tmdb` de la etiqueta;
`locked_fields` gana siempre. `release_dates` tiene procedencia por fila, asi que sus
filas TMDb se pueden quitar sin tocar fechas de otra fuente. Si la referencia principal
(`url`/`source`) era TMDb, cae al primer enlace restante entre Wikipedia/IMDb/
FilmAffinity/Jikan o queda `local_files`/`retired`.

`application/external_retirement.py` (`TmdbRetirementService`) expone preview
(`preview_id` determinístico por hash del estado "antes"), purga con confirmacion
explicita que rechaza un preview desactualizado o un catalogo de solo lectura, historial
persistente y undo que restaura el estado exacto previo — con rollback si falla el
registro de historial o la escritura de deshacer. `web/routers/integrations.py` expone
las cuatro operaciones solo al owner bajo `/api/integrations/tmdb/retirement/*`.

**Criterio de cierre**: `tests/test_external_retirement.py` cubre preview/purga/
historial/undo sobre catalogo JSON y SQLite, catalogo de solo lectura y preview
desactualizado bloqueando la purga, rollback ante fallo de historial, conservacion de
campos manuales/bloqueados/compartidos y round-trip CSV con procedencia e identidad
TMDb intactas; `tests/test_matching.py` y `tests/test_metadata_authority.py` cubren
conflicto/coincidencia de `tmdb_id` y tipo de medio. Verificado con 533 pruebas
unitarias, Ruff, formato, mypy estricto, `compileall` y `git diff --check`.
2026-09-01, commit `0bc436c`.

#### [F5.3] Exponer TMDb con cumplimiento, resiliencia y validacion real
La estanteria y el health de TMDb quedan condicionados a la misma señal que ya usaba
el backend: `externalHealth.sources.tmdb`, presente unicamente cuando el servidor tiene
el token cargado (heredado de `/api/items` en cada carga de pagina). `catalog-search.js`
suma `isExternalSourceConfigured()`/`configuredExternalSources()` y los usa en
`requestedExternalSources()` (no se pide la fuente sin configurar), `renderManualResults()`
(la seccion ni se renderiza) y el panel admin (`renderDatabaseMenu()` en
`catalog-grid.js` solo agrega la fila TMDb si hay health). Verificado en vivo con dos
instancias reales del servidor: con token, la busqueda de "Heat" muestra la estanteria
TMDb (con error controlado por token invalido, sin crash) y la fila en `Administrar →
Fuentes externas`; sin token, ninguna de las dos aparece — cero estanteria fantasma,
cero fila fantasma. `hasExternalLink()`/`isExternalResult()` suman el host
`themoviedb.org` para que un resultado o item TMDb participe en merge/comparacion igual
que las demas fuentes.

Atribucion: `static/img/tmdb-logo.svg` es el logo oficial "blue_short" descargado de
`themoviedb.org/about/logos-attribution` (asset publico del brand kit de TMDb, pensado
para este uso). Se sirve por `/static/img/*.svg` (nuevo tipo de contenido en
`web/assets.py`, empaquetado via `pyproject.toml`) junto al aviso textual exacto
exigido por los terminos ya investigados en [F3.1]: "Este producto usa TMDb y sus APIs
pero no está avalado, certificado ni aprobado de ninguna forma por TMDb."; se renderiza
siempre que la estanteria TMDb existe, sin condicionar a que haya resultados.

Rate limit/backoff/cooldown y el TTL de cache ya eran genericos en
`external/registry.py` (`_source_error_state()`, cooldowns por `Retry-After`) y cubrian
TMDb automaticamente porque `TmdbAdapter` deja propagar `HTTPError`/`TimeoutError` sin
capturarlos; no hizo falta código nuevo, solo prueba de integracion real:
`test_tmdb_429_with_retry_after_opens_a_real_cooldown` (usa el adapter real via
`default_source_adapters("secret")`, no un fake) y
`test_search_cache_ttl_stays_far_under_the_six_month_retention_cap` (15 min contra el
tope de 6 meses de los terminos). `tests/test_external_tmdb_live_smoke.py` agrega un
smoke opt-in sobre el corpus ya recorded (`Addio Zio Tom`, `Fanny & Alexander`,
`Verano 1993 (2017)`, homonimo `Heat` movie/TV vía `tt0113277`) gateado por la variable
de entorno `MOVIE_INBOX_TMDB_LIVE_SMOKE_TOKEN`; sin ella queda `skipped`, nunca corre en
CI ni afecta el gate. El banner de arranque de `server.py` ("adapter pending F5") quedo
actualizado a texto correcto ahora que el adapter existe.

**Criterio de cierre**: `tests/test_external_tmdb.py` (cooldown real + TTL),
`tests/test_view_http.py::test_tmdb_attribution_logo_is_served_as_svg`,
`tests/test_server_cli.py` (banner actualizado) y verificacion manual en navegador de
ambos estados (configurado/no configurado) para estanteria, atribucion y panel admin.
Verificado con 540 pruebas unitarias (536 activas + 4 skipped del smoke opt-in), Ruff,
formato, mypy estricto, `compileall` y `git diff --check`.
2026-09-01.

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

#### [Q5] Definir autoridad y conflicto campo por campo
`merge_metadata_field()` (`domain/catalog.py:619-644`) es hoy "solo llena vacios" para
todo campo simple (`after = before or incoming_value`, verificado ejecutandolo): una
vez que un campo tiene cualquier valor, ninguna fuente nueva lo cambia jamas, sin
importar cual sea mas confiable — solo `locked_fields` (revisado primero, incluso
sobre un campo vacio) o una edicion manual (que no pasa por esta funcion) pueden
pisarlo. Esto choca con como suena "IMDb es autoridad" en el alcance original de la
tarea, asi que se lo señale al owner antes de diseñar nada. **Decision explicita del
owner (2026-08-29): autoridad = orden de relleno, nunca pisa lo ya completado.** La
matriz de abajo define que fuente se prueba primero cuando un campo esta vacio; el
comportamiento actual de "una vez lleno, queda asi salvo `locked_fields`/edicion
manual" no cambia.

Las 24 `METADATA_FIELDS` en 7 familias (la tarea nombraba 6; sumo "Datos
estructurados" porque duracion/paises/idiomas/genero no encajaban en ninguna de las
otras sin forzarla):
1. **Identidad** (title, original_title, alternative_titles): [F1] → Wikipedia
   (incluye lo que trae de Wikidata; ambos quedan como `source: wikipedia` en
   `metadata_sources`, nunca como `wikidata` — la unica llamada a
   `fetch_wikidata_metadata()` vive adentro de `external/wikipedia.py:316` y hereda su
   `source` — verificado por grep) → IMDb (cliente en vivo) → FilmAffinity.
   `alternative_titles` es list-field (union, nunca pisa nada) y se arma con los akas
   de [F1] filtrados por `region` a mercados hispano/anglofonos (no por `language`: en
   la prueba real contra "Heat" ningun aka tenia `language` poblado, todas se
   distinguian solo por `region`).
   - `spanish_title`/`english_title`: [F1] NO participa (`TitleLookupResult` solo
     expone `primary_title`/`original_title` como escalares) — Wikipedia (label por
     idioma via Wikidata) → FilmAffinity (`spanish_title` unicamente).
2. **Clasificacion** (year, kind): [F1] → Wikipedia → IMDb. FilmAffinity no aporta
   `kind` (confirmado leyendo `filmaffinity.py`: no hay ninguna extraccion de tipo en
   todo el archivo), si aporta `year`. **Regla obligatoria**: el `title_type` crudo de
   IMDb jamas se pasa directo a `incoming["kind"]` — `domain/normalization.py::
   normalize_kind()` tiene su propio vocabulario hardcodeado, separado e incompleto, y
   nunca devuelve "sin opinion": confirme ejecutandolo que `normalize_kind("tvMiniSeries")`
   y `normalize_kind("tvEpisode")` devuelven ambos `"pelicula"` (no un error, un
   default silenciosamente incorrecto). Traduccion antes de tocar `kind`:
   `movie`/`tvMovie`/`short`/`tvShort`/`tvSpecial` → `pelicula`;
   `tvSeries`/`tvMiniSeries` → `serie`; `tvEpisode`/`tvPilot`/`videoGame`/cualquier
   otro → excluido (nunca fija el `kind` de la ficha entera a partir de un episodio
   suelto; este catalogo no trackea episodios individuales). La regla existente de que
   `kind` solo sube de `pelicula` a `{serie,anime,documental}`, nunca baja, no cambia.
3. **Datos estructurados** (duration_minutes, countries, original_languages, genres):
   `duration_minutes` ← [F1] (`runtime_minutes`, rename directo) → Wikipedia. `genres`
   ← [F1] (string separado por comas) → Wikipedia → FilmAffinity — el string de [F1]
   se une sin ningun codigo nuevo, `merge_lists`/`normalize_tags` ya hacen
   `.split(",")` sobre cualquier string crudo (`domain/catalog.py:216-223`, probado en
   vivo). `countries`/`original_languages`: solo Wikipedia hoy, ni FilmAffinity ni [F1]
   los aportan.
4. **Creditos** (producers, composers, directors, writers, cast): `producers`/
   `composers`: solo Wikipedia (FilmAffinity no los aporta, confirmado — su unico mapeo
   de nombres es `{"director": "directors", "actor": "cast"}`). `directors`/`writers`/
   `cast`: Wikipedia → FilmAffinity. [F1] no aporta nada aca (`title.crew`/
   `title.principals` quedan fuera de alcance — las medidas reales de [F1], 8,1 GB para
   2 de 7 datasets posibles, desaconsejan sumarlos sin una razon de mucho peso).
5. **Imagenes** (page_image, backdrop_image): Wikipedia → IMDb. FilmAffinity no aporta
   ninguna imagen hoy. `backdrop_image`/`tmdb_id` no tienen fuente real todavia —
   reservados para si [F3] aprueba TMDb, sin decision pendiente ahora.
6. **Fechas** (release_dates): sin cambios — ya tiene su propio mecanismo
   (`merge_release_dates`) con procedencia por fila y su propio "solo llena lo vacio"
   por subcampo, correcto y suficiente. Solo Wikipedia lo alimenta hoy.
7. **Descripcion** (description, wikipedia_extract): Wikipedia (articulo) → IMDb
   (snippet corto) → FilmAffinity (sinopsis). `wikipedia_extract` es exclusivo de
   Wikipedia por definicion.

**Identificadores cruzados, excluidos de la matriz** (wikipedia_title, wikidata_id,
tmdb_id): cada uno pertenece a una sola fuente por definicion, sin conflicto posible.

Criterio de cierre cumplido con "ADR y fixtures", no una implementacion: este repo no
tiene un formato de ADR separado (confirmado — ningun `docs/adr/` ni archivo `*adr*`
existe; el precedente real de [P1]/[Q3]/[F1] es escribir la decision como esta misma
prosa). `tests/test_metadata_authority.py` (10 tests nuevos) ejercita solo funciones
ya existentes (`merge_metadata_field`, `merge_lists`, `normalize_kind`,
`normalize_item`) con datos sinteticos — cero cambios a `domain/catalog.py` ni a
ningun camino de produccion — cubriendo las 5 categorias del cierre: vacios, listas
(incluido el genero de [F1] uniendose sin codigo nuevo), valores divergentes (la
prueba concreta de la politica elegida), fuente caida (un `incoming` normalizado sin
nada que aportar no toca el valor existente — encontre y arregle un bug real en mi
propio diseño de este fixture antes de escribirlo: llamar `merge_metadata_field` con
un diccionario armado a mano que OMITE una clave en vez de setearla en `""` hace que
`after = "" or None` de `None`, que `!= ""`, y dispara una escritura falsa atribuida a
una fuente que nunca menciono el campo — no pasa en produccion porque
`merge_into_existing` siempre normaliza `incoming` primero, asi que los fixtures
rutean por `normalize_item()` para reflejar esa precondicion real) y dato manual (dos
fixtures: bloquear un campo vacio con `locked_fields` impide incluso su primer
llenado, y el tag `source: "manual"` sobrevive intacto a un merge automatico
posterior). Un fixture extra prueba en vivo la trampa de `normalize_kind()` descrita
arriba. Fuera de alcance, explicito: decidir si una fila de una fuente corresponde a
una ficha dada (eso ya lo gobierna `domain/matching.py` y el invariante de matching
conservador de `CLAUDE.md`); escribir el codigo real que orqueste el orden de esta
matriz (trabajo de quien integre esto al catalogo real, probablemente junto con [Q6]).
2026-08-29.

#### [Q6] Crear una ficha compuesta sin altas manuales duplicadas
`CatalogService.append_item()` (`application/catalog_service.py`) solo evitaba
duplicados con igualdad exacta de id/URL y una heuristica **lexica** de solapamiento
de palabras del titulo (`possible_duplicate_candidates`) — un par entre idiomas sin
ninguna palabra en comun (ej. "El Padrino" vs "The Godfather") no disparaba nada y
creaba dos fichas sin vincular en silencio. El proyecto ya tenia el gate correcto para
esto — `decide_match()` (`domain/matching.py`, cero falsos positivos conocidos, ya
usado para auto-aceptar sin intervencion humana en Scanner y en las herramientas CLI
batch) — pero nunca se llamaba desde `/api/add`; ahi solo rankeaba candidatas para un
humano en "Comparar". `append_item` ahora corre `decide_match` contra los items
existentes antes de caer en la heuristica lexica de siempre: si acepta exactamente
uno, no crea una ficha nueva — la responde como `"strong_match"` y el router
(`web/routers/catalog.py`) la combina en la ficha existente. Todo lo que
`decide_match` no acepta sigue exactamente igual que antes (misma interjeccion
Combinar/Agregar igual/Cancelar, o alta normal).

Hallazgo real durante el diseño, verificado ejecutandolo en un REPL antes de escribir
nada: el unico metodo existente para "item existente + resultado externo"
(`CurationWorkflowService.merge()`) usa `apply_reviewed_merge()`
(`domain/merge_review.py`) — una implementacion de merge separada y distinta de
`merge_metadata_field()` (la que [Q5] ya probo). `_default_choice()` ahi decide "el
lado que tiene valor gana" **antes** de mirar si el campo esta bloqueado: un campo
`locked_fields` pero vacio en el lado sobreviviente queda con `default_choice="right"`,
nunca pide una decision humana, y `apply_reviewed_merge(left, right, "left", {})`
escribe el valor entrante encima de un campo bloqueado en silencio — reproducido tal
cual con datos sinteticos reales. Esto ya afecta `auto_resolve_duplicates()` en
produccion HOY (llama `merge(choices={})` sin ningun humano de por medio),
completamente independiente de esta tarea — quedo anotado aparte para arreglar. Por
eso mismo, el mecanismo nuevo de esta tarea (`CurationWorkflowService.auto_merge_on_add()`)
compone directo `_capture` + `merge_into_existing` + `_commit_operation`, sin pasar
nunca por `apply_reviewed_merge` — hereda historial y deshacer gratis, sin heredar ese
bug. Si el catalogo cambio entre el chequeo y la confirmacion (`CurationConflict`), cae
a un alta normal en vez de reintentar.

Verificado contra datos reales, no solo tests sinteticos: servidor real con una ficha
local "Heat" (1995, sin links), agregar el resultado de Wikipedia en español la
combino en la misma ficha (via `exact_title_year`) trayendo sinopsis completa,
reparto, generos, mas de 60 alias reales en todos los alfabetos y `wikidata_id` en una
sola llamada; agregar despues el resultado de Wikipedia en ingles combino en la MISMA
ficha otra vez (esta vez via `shared_wikidata_id`) sin tocar los campos ya llenos — dos
altas reales, una sola ficha final, sin pedir fusion manual ninguna de las dos veces.
Fuera de alcance, explicito y verificado: no todo par del mismo titulo entre fuentes se
auto-combina, solo lo que `decide_match` ya acepta — FilmAffinity nunca resuelve
`wikidata_id` (confirmado leyendo su parser), asi que un alta de "Calor" despues de
"Heat" sigue la heuristica lexica de siempre, sin cambios; cerrar ese hueco de raiz
pediria mejorar la resolucion de identidad cruzada entre fuentes, alcance mayor a esta
tarea.
455 pruebas (crecio desde 449 al empezar), mypy estricto, Ruff, `compileall` y
`git diff --check` en verde en cada fase — una de mis propias pruebas nuevas hacia una
llamada de red real de ~5s a Wikipedia hasta que la mockee igual que ya hacia la
prueba vecina.
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

#### [P2] Compartir disponibilidad fisica como coleccion de Club (contrato de [P1])
El admin puede activar, por biblioteca, "compartir disponibilidad" — publica una
coleccion de Club de solo lectura con los titulos confirmados y disponibles de esa
biblioteca, regenerada automaticamente en cada recorrido aplicado. El diseño original
(basado en `AvailabilityService.decorate_items()`, ya usado para decorar el catalogo
personal) se abandono por completo: reproduje yo mismo, con datos sinteticos, que
dejaba pasar `_availability.sources` (con `library_id`/`library_name`) intacto a traves
del allowlist de nivel superior de `normalize_collection_item()`, y que copiar un item
compartido al catalogo personal dejaba un `_availability` obsoleto y contradictorio.

El diseño final evita esa superficie de fuga por construccion en vez de filtrarla
despues: `LibraryRepository.availability_records()` (ya existente, usado hoy solo por
`AvailabilityService`) ya devuelve exactamente lo seguro —
`work_identity(item)` (`domain/libraries.py`, docstring propio: "catalog-independent
evidence that can be shared safely") como `identity`, con `library_id`/`library_name`
como claves **hermanas**, nunca mezcladas adentro. `collection_item_from_availability_record()`
(`domain/collections.py`) arma el item de coleccion solo a partir de `identity` +
`work_key` (id estable entre recorridos), sin tocar jamas `library_id`/`library_name`.
De paso cerre una fuga latente e independiente: `COLLECTION_ITEM_FIELDS` heredaba
`_availability` de `SHARED_CATALOG_FIELDS` (pensado para un llamador distinto y ya
seguro que reconstruye un sub-dict limpio) — cualquier item de catalogo personal con
`_availability` poblado habria pasado ese bloque intacto por cualquier otro camino que
use `normalize_collection_item()`. Ahora excluido explicitamente.

`curated_collections` gana `derived_library_id` (columna nueva anulable, FK a
`media_libraries` con `ON DELETE CASCADE` — confirmado en vivo que borrar la biblioteca
borra en cascada la coleccion derivada y los seguidores de otros usuarios, comportamiento
correcto y ahora cubierto por un test dedicado). `source_kind` sigue siendo `'user'`
para estas: cambiar el CHECK constraint existente habria pedido el "recrear tabla" de
12 pasos que SQLite exige y que este repositorio nunca uso en 9 migraciones — confirmado
en vivo que `ALTER TABLE ... DROP CONSTRAINT` ni siquiera es sintaxis valida. Insertar
`""` (el default del dataclase) en esa columna FK anulable tampoco es lo mismo que
`NULL` — confirmado en vivo que SQLite valida `""` como un valor real y lo rechaza —
asi que todo punto de escritura convierte `"" → None` explicitamente.

Dos bugs reales, no hipoteticos, encontrados durante la implementacion (no en el
diseño) y arreglados antes de escribir un solo test que los cubriera:
1. `library_repository.py::_library(row)` es un constructor explicito campo por campo,
   sin comodin. Sin mapear la columna nueva, toda lectura de una biblioteca volvia con
   el default del dataclase (`False`) sin importar lo que dijera la base — y como
   `update_library()`/`set_active()` cargan-y-reconstruyen via `dataclasses.replace()`,
   **cualquier edicion no relacionada (renombrar, tocar el horario) reiniciaba en
   silencio el flag de compartir a apagado**. Reproducido y arreglado antes de escribir
   el test que lo prueba.
2. El gancho nuevo en `execute_run()` (justo despues de que `complete_run()` termina
   bien, todavia dentro del mismo `try`) tenia que capturar `Exception` ancho, no
   `CollectionRepositoryError` como en el borrador original. Traze que el `except
   Exception` de mas afuera de `execute_run()` llama `_fail_run()` → `complete_run()`
   una segunda vez con la foto vieja (pre-recorrido) de la biblioteca — el `UPDATE
   library_scan_runs` tiene guarda (`WHERE status='running'`, no-op en la segunda
   llamada) pero el `UPDATE media_libraries` que sigue no tiene ninguna, y pisaria sin
   condicion `verified_at`/`last_scan_at`/`status` con los valores viejos, revirtiendo
   un recorrido que ya habia terminado bien. Un test nuevo fuerza una excepcion que NO
   es `CollectionRepositoryError` durante el sync y confirma que el estado de la
   biblioteca sobrevive intacto.

Frontend: los 3 controles (activar/desactivar, titulo, descripcion opcional) viven
juntos dentro de "Opciones avanzadas" — mismo `<details>` que ya aloja las reglas de
exclusion de [L1] — con un unico guardado (`saveLibraryShareSettings`, mismo patron
secuencial que `saveLibraryExclusionRules`). El borrador original separaba un checkbox
en la tarjeta (guardado al toque) de los campos de texto en el dialogo (guardados recien
al enviar) — dos mecanismos de guardado independientes para el mismo estado, con una
ventana real donde uno pisaba al otro; se unifico antes de implementar. Deliberadamente
no anidado en `libraryAutomationControl()`, que se esconde entero para bibliotecas con
`schedule === "manual"` (el caso mas comun de uso personal) porque solo controla la
automatizacion del recorrido, sin relacion con compartir disponibilidad.

Verificado en vivo contra un servidor real, no solo con pruebas unitarias: biblioteca
creada, recorrido de prueba + aplicado, archivo confirmado via la cola del escaner,
"compartir disponibilidad" activado con el campo de titulo en blanco (confirma que cae
al nombre de la biblioteca) — la respuesta real de `/api/collections` contenia
unicamente `title`/`year`/`kind`/`file_count` del item, cero `library_id`, cero
`library_name`, cero ruta, cero nombre de archivo, en ningun lugar del payload.
Desactivar despublica (`visibility: "private"`) sin borrar la coleccion ni sus
seguidores.

Suite completa (477 pruebas, crecio desde 463 al empezar) + mypy estricto + Ruff +
`compileall` + `git diff --check` en verde en cada una de las 4 fases (esquema+dominio,
repositorio, aplicacion, web+frontend). `CLAUDE.md` invariante #4 actualizado con la
excepcion exacta y acotada que aprobo el owner. Fuera de alcance, explicito: editar
titulo/descripcion de cualquier OTRA coleccion (builtin/import) — esta tarea construyo
la primera capacidad de edicion de colecciones del proyecto, deliberadamente acotada a
colecciones derivadas de una biblioteca; exponer `derived_library_id` en cualquier
respuesta HTTP (queda interno); el bug ya reportado aparte de `apply_reviewed_merge`
(no relacionado).
2026-08-31.

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

#### [C1] Disenar el contrato para grupos de 3+ duplicados
Hoy `build_curation_payload`/`_duplicate_cases` (`application/curation_service.py:20-76`)
descompone cualquier grupo de duplicados que ya arma `annotate_duplicate_items`
(union-find real y transitivo sobre claves `url:`/`title-year:`,
`domain/catalog.py:493-575`) en C(n,2) casos independientes por par. Un trio identico
sin ningun dato produce hoy 3 casos `duplicate` (`counts.duplicates: 3`), verificado
ejecutandolo, en vez de mostrarle al humano una sola decision.

No es solo una molestia de UX. `CurationWorkflowService.auto_resolve_duplicates()`
(`application/curation_workflow.py:191-229`) consume esa misma lista estatica de pares
y la procesa en orden con `merge(choices={})`. Traze un grupo real de 4 (dos sin dato,
`rating=9` y `rating=4` en los otros dos) par por par: heat-a+heat-b y heat-a+heat-c
fusionan sin problema (heat-a termina con `rating=9`); heat-a+heat-d es un conflicto
real (`MergeReviewError: Missing decision for protected field: rating`, 9 contra 4);
los 3 pares restantes (heat-b+heat-c, heat-b+heat-d, heat-c+heat-d) fallan con
`CurationItemNotFound` porque heat-b y heat-c ya no existen — se fusionaron en pasos
anteriores del mismo lote. Resultado: `{"resolved": 2, "needs_review": 4}`, pero de
esos 4 "needs_review" **solo 1 es un conflicto real**; los otros 3 son ruido de
referencias obsoletas. Para un grupo totalmente limpio de N la formula deterministica
(verificada ejecutando el codigo real para N=3 y N=4) es `resolved = N-1`,
`needs_review = C(N,2)-(N-1)` — coincide con el test ya existente
`test_auto_resolve_merges_an_identical_trio_down_to_one_survivor` (N=3:
`resolved=2, needs_review=1`) y con el nuevo `test_auto_resolve_on_a_quartet_with_
one_conflict_leaves_mostly_stale_reference_noise` (N=4 con un conflicto real:
`resolved=2, needs_review=4`, con la tabla completa arriba). Cuanto mas grande el
grupo, mas ruido fantasma tapa el conflicto real — y en un grupo de 3+, un campo con
valores distintos puede terminar descartado por orden de procesamiento sin que ningun
humano lo vea, en tension directa con "coincidencia dudosa = revision humana" de
`CLAUDE.md`. Ya afecta produccion hoy; esta tarea documenta el problema con precision,
no lo corrige (eso es [C2]).

**Contrato nuevo**: un caso `duplicate` deja de representar un par y pasa a representar
una **componente conexa** del grafo de aristas `pending`/`deferred` que ya calcula
`annotate_duplicate_items` en cada item (`_duplicate_refs`/`_duplicate_deferred_refs`) —
no el grupo crudo de union-find (nunca se achica) ni una lista estatica de pares.
Forma: `{id, type: "duplicate", status, reason, evidence, members: [...]}`, con
`members` (2+) reemplazando `primary`/`secondary`. Verificado con un prototipo Python
descartable (no comiteado; usa sin modificarlas las funciones reales
`curation_item_reference`, `_duplicate_evidence`, `_item_summary`, `_case_digest`) en 5
escenarios: (1) trio limpio sin decisiones, hoy 3 casos por par → nuevo 1 caso de 3
miembros; (2) grupo de 4 con 1 conflicto real pero sin decisiones aun (vista de cola,
no de auto-resolve) → sigue siendo 1 caso de 4 miembros, sigue pidiendo revision humana
porque nada se fusiono todavia; (3) cortar solo la arista A-B de un trio (una decision
`not_duplicate`) → sigue siendo 1 caso de 3 miembros, A y B quedan unidos igual via C
transitivamente — confirmado tambien con codigo real, no solo el prototipo, en
`tests/test_curation.py::test_not_duplicate_on_one_edge_of_a_trio_still_leaves_a_
connected_path`; (4) cortar las 2 aristas que tocan A → recien ahi A queda aislado y
B-C forma su propio caso de 2; (5) grupo entre archivos (mismo id crudo, `_source_file`
distinto) ya funciona hoy sin cambios a nivel de pares — confirmado con codigo real en
`tests/test_curation.py::test_cross_file_group_with_colliding_ids_is_disambiguated_by_
source_file` (3 casos por par con `ref` compuesto correctamente disambiguado hoy;
bajo el contrato nuevo colapsan a 1 caso de 3 miembros). `load_items()` ya aplana todos
los catalogos antes de anotar duplicados, asi que un grupo entre archivos ya es el caso
normal, no una excepcion a disenar aparte.

Las 2 decisiones que quedaban abiertas, resueltas aca y no delegadas a [C2]:
**evidencia** de un caso-grupo = union deduplicada (orden de primera aparicion) de
`_duplicate_evidence(a, b)` para cada arista que sigue conectando directamente a dos
miembros — un grupo de 2 da la misma lista de hoy, uno heterogeneo muestra todas las
razones en vez de una elegida al azar; **orden de la cola** (`_case_sort_key`, hoy lee
`case["primary"]["title"]`) = titulo (casefold) mas chico alfabeticamente entre todos
los miembros, generalizacion directa sin criterio nuevo.

**Correccion de encuadre**: `_case_digest(*values)` ya es variadico y ya se llama hoy
con un par pre-ordenado alfabeticamente — ya es insensible al orden, hoy, para 2
elementos, sin cambios de codigo. El id de un caso-grupo
(`_case_digest(*sorted(member_refs))`) extiende ese mismo patron a N, no inventa nada.
Esto es distinto de `merge_review_id` (`domain/merge_review.py:154-161`), que serializa
`[snapshot(left), snapshot(right)]` como arreglo — `sort_keys` ordena las claves
*dentro* de cada snapshot pero no el orden del arreglo, asi que
`merge_review_id(left, right) != merge_review_id(right, left)` en general (verificado:
dos hashes distintos con los mismos snapshots invertidos). Un borrador anterior de este
diseño asumia que un futuro "id de revision de grupo" generalizaria `merge_review_id`
— es incorrecto decirlo asi: ese hash es de **contenido** (concurrencia optimista
dentro de `merge()`, que esta tarea no toca), el id del caso-grupo es de **identidad**
(que referencias componen el caso). Si [C2] necesita un chequeo de staleness N-a-1, es
una decision propia de [C2], no algo que este diseño resuelva de antemano.

**Conexion con la tarea de fondo `task_47d7cd43`** (bug de
`apply_reviewed_merge`/`_default_choice` en `domain/merge_review.py`, encontrado
durante [Q6]: un campo bloqueado pero vacio puede quedar pisado porque el chequeo de
"que lado tiene valor" corre antes que el de `protected`/`locked_fields`):
`auto_resolve_duplicates` ya pasa por ese mismo camino hoy. Si [C2] resuelve un grupo
de N encadenando fusiones de a pares (una de las formas de implementacion que este
diseño deja abiertas), ese bug se dispara potencialmente varias veces por grupo — se
nombra aca explicitamente para que [C2] decida con conocimiento: esperar el arreglo, o
asegurarse de que su propio mecanismo de eleccion de campo para N vias no herede el
mismo orden de chequeos, igual que [Q6] evito este camino componiendo
`merge_into_existing` directo en vez de reusar `apply_reviewed_merge`.

**Cambio de contrato visible**: `counts.duplicates` pasa de contar pares a contar
grupos — con los mismos datos, un trio hoy reporta 3 y con el contrato nuevo reporta 1.
No es una regresion ni perdida de datos, es la consecuencia directa de no mostrar la
misma decision tres veces; vale una linea en el CHANGELOG cuando [C2] lo implemente.

Cumple el criterio de cierre con ADR y fixtures, no una implementacion — mismo alcance
que [Q5], sin formato de ADR separado en este repo (ver precedente citado ahi): cero
cambios a `curation_service.py`/`curation_workflow.py`/al frontend. 3 tests nuevos
sobre codigo ya existente sin ningun prototipo comiteado: el de la tabla de 4 items
arriba (`tests/test_curation_workflow.py`) y los 2 de conectividad/cross-file citados
arriba (`tests/test_curation.py`). El caso de trio limpio N=3 no se reimplementa, ya
esta cubierto por el test existente citado arriba. Fuera de alcance, explicito: la
implementacion real del contrato de grupo, el arreglo de `auto_resolve_duplicates` o de
`task_47d7cd43`, y el frontend (`inbox-curation.js`/`merge.js`) que hoy asume
literalmente 2 items ("Entrada A"/"Entrada B") — todo eso es [C2].
2026-08-30.

#### [C2] Implementar resolucion N-a-1 de duplicados
`application/curation_service.py` aplica el contrato de [C1]: cada componente conexa
de aristas pendientes/pospuestas produce un unico caso `duplicate` con `members` (2+),
ID estable por referencias ordenadas, evidencia deduplicada de todas las aristas y
orden alfabetico por el menor titulo del grupo. `counts.duplicates` cuenta decisiones
reales, no `C(n,2)` pares repetidos.

`domain/merge_review.py` suma una revision N-vias: cada campo expone el valor de todos
los miembros, permite elegir la ficha superviviente y combina listas, fechas, archivos
y disponibilidad sin escrituras intermedias. Los campos personales con valores en
conflicto siguen siendo obligatorios. En el mismo cambio se cerro `task_47d7cd43`: si un
campo vacio esta en `locked_fields`, su vacio queda como eleccion segura en vez de ser
rellenado silenciosamente por otro miembro; dos valores bloqueados distintos exigen una
decision humana.

`CurationWorkflowService.merge_group()` captura todos los miembros, valida un
`review_id` de contenido, calcula el resultado completo en memoria y recien entonces
aplica una unica transicion multi-catalogo. El historial registra `merge_group` como una
sola operacion; un fallo al escribirlo revierte todos los catalogos y Deshacer restaura
cada miembro en su posicion. Una edicion concurrente invalida la revision sin cambios
parciales. `auto_resolve_duplicates()` usa este mismo camino: un grupo limpio cuenta
como un caso resuelto y un unico conflicto deja el grupo entero intacto con
`needs_review: 1`, eliminando el ruido de referencias ya borradas de [C1]. Las decisiones
grupales (`pending`/`deferred`/`not_duplicate`) tambien son atomicas y reversibles.

La API acepta entre 2 y 50 referencias, valida su pertenencia y conserva tanto la
referencia publica (`source-N`) como la interna para no filtrar rutas ni perder
decisiones al volver a cargar la cola. `inbox-curation.js` muestra todas las fichas y
busca sobre cualquiera de ellas; `merge.js` genera selectores de superviviente y de
campo para N entradas, con estados de carga/error, foco visible, `aria-live`, textos
largos y composicion responsive. La prueba Playwright recorre un grupo de tres, cambia
el superviviente, resuelve un puntaje protegido y verifica el POST grupal.

**Cierre**: pruebas de dominio, workflow, HTTP y navegador cubren trio identico,
cuarteto con conflicto real, catalogos cruzados, rollback de historial, revision
desactualizada, decision grupal, undo y campo bloqueado vacio. Verificado con 546
pruebas (`4` omisiones opcionales), Ruff, formato, mypy estricto, sintaxis JavaScript,
detector Impeccable y `git diff --check`. 2026-09-01, commit `1d5ebc8`.

---

### Frente: Fuentes externas y especializacion de anime

#### [F1] Prototipo del indice no comercial de IMDb
Comando nuevo `movie-inbox imdb-dataset sync/stats/lookup` que descarga
`title.basics.tsv.gz`/`title.akas.tsv.gz` desde `datasets.imdbws.com` y los indexa en
un `.db` SQLite propio, separado de `catalog.db` e `instance.db` — deliberadamente
desconectado del catalogo real: no toca `domain/catalog.py`, `metadata_sources` ni
ningun merge, eso es trabajo de [Q5]. Un agente Plan encontro una violacion de
layering real en el primer diseño (`application/` importando `infrastructure`/
`external` directo) — se elimino la capa `application/` por completo, siguiendo el
mismo patron que `cli/database.py`/`cli/backup.py` ya usan para herramientas sin nada
mas que inyectar. Tambien encontro que cada `sync` reconstruye el indice entero desde
cero, asi que no hace falta una tabla de migraciones — un `PRAGMA user_version` simple
alcanza (`stats`/`lookup` piden re-correr `sync` si no coincide, en vez de migrar en
el lugar), y que la descarga en si (no solo el build del indice) necesitaba el mismo
patron atomico de archivo temporal + `os.replace()` que ya usan `schema.py`/
`image_proxy.py`/`backup.py`, para que una conexion cortada a mitad de descarga no
deje un `.tsv.gz` truncado en la ruta final.

Verifique yo mismo los terminos reales de IMDb contra su Help Center (no asumidos):
la atribucion exigida es el string exacto "Information courtesy of IMDb
(https://www.imdb.com). Used with permission." — aparece en la salida de `sync` y de
`lookup` cada vez que se muestran datos reales. El uso personal para armar un indice
offline propio esta explicitamente permitido ("except for individual personal use").

Dos bugs reales que ningun test sintetico iba a encontrar, solo la corrida real contra
datos reales los mostro: (1) la cadena de certificados de CloudFront de
`datasets.imdbws.com` tiene un CA intermedio sin "Basic Constraints" marcado como
critico — Python 3.13+ activa `VERIFY_X509_STRICT` por defecto y rechaza el
handshake (confirmado que curl acepta el mismo sitio sin problema); se relaja
unicamente esa bandera, solo para este host, sin tocar cadena de confianza ni
verificacion de hostname. (2) `lookup` reventaba con `UnicodeEncodeError` imprimiendo
el primer aka fuera de cp1252 (la codepage por defecto de consola en Windows) —
`title.akas` tiene titulos en todos los alfabetos que IMDb rastrea; `main()` ahora
reconfigura `stdout` a UTF-8 antes de imprimir. Test de regresion nuevo que reproduce
el crash con un `TextIOWrapper` real en cp1252, sin depender de una consola real.

Medidas reales obtenidas (permiso explicito del owner antes de descargar, dado que el
tamaño exacto era justamente lo que faltaba medir): `title.basics.tsv.gz` 215.6 MB en
2.6s, `title.akas.tsv.gz` 488.4 MB en 5.2s — la descarga en si es rapida y barata.
12.749.320 titulos y 59.128.959 alias indexados; el build del indice tardo 1433.8s
(~24 minutos) y el `.db` resultante ocupa 8102.6 MB en disco — bastante mas grande que
los ~704 MB descargados, por el texto descomprimido mas los indices sobre ~72 millones
de filas. Verificado con `lookup --title "Heat" --year 1995` contra el indice real:
encuentra la pelicula y un episodio de TV homonimo de 1995 por separado, con docenas
de alias reales en cirilico/CJK/griego/etc. renderizando correctamente tras el fix de
codificacion.

435 pruebas (crecio desde 421 al empezar, en 3 fases mas los 2 fixes), mypy estricto,
Ruff, `compileall` y `git diff --check` en verde en cada fase — todas con datasets
sinteticos chicos, sin tocar la red; ningun test real descarga nada. Fuera de alcance,
explicito desde el diseño: tocar el catalogo real o `metadata_sources` (es [Q5]),
`title.crew`/`title.principals`/`name.basics` (solo si esta base demuestra que la
instancia los sostiene), actualizacion incremental real (cada `sync` reconstruye
entero a proposito, para medir si eso es viable a diario — 24 minutos de CPU sugiere
que en produccion conviene correrlo en un horario programado, no bajo demanda), y
locking entre procesos para `sync` corriendo a la vez que `lookup`/`stats` (riesgo
real mencionado por el agente Plan — puede fallar con `PermissionError` en Windows,
sin riesgo de corrupcion; documentado como restriccion de uso).
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
