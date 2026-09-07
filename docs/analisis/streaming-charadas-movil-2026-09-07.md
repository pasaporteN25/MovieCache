# Análisis: disponibilidad en streaming, charadas y dirección móvil

**Fecha:** 2026-09-07. **Estado:** análisis aceptado por el owner, sin código escrito.
**Alcance:** tres ejes nuevos planteados por el owner más una revisión del estado móvil.
No modifica ningún contrato vigente; propone frentes para `tareas.md`.

Este documento registra decisiones tomadas por el owner el 2026-09-07 y el relevamiento
que las sostiene. Lo que está marcado como **decidido** ya no se rediscute; lo que está
marcado como **abierto** bloquea la tarea que lo menciona, no el frente entero.

---

## 0. Reparto de trabajo entre agentes

**Decidido.** El trabajo se divide por especialidad y corre en paralelo:

- **Claude** — infraestructura, backend, modelo de datos, capas, contratos externos,
  migraciones, pruebas. Los tres ejes de este documento y la deuda de [F1].
- **Codex** — dirección visual y frontend de presentación: [U2-P] y sus derivados.

Consecuencia operativa: los dos frentes tocan archivos distintos casi siempre, pero
`tareas.md` es compartido. Quien abra un frente nuevo agrega su sección y evita
reescribir las ajenas. Ver también la sección homónima en `CLAUDE.md`.

---

## 1. Estado verificado del repositorio

Relevamiento hecho el 2026-09-07 leyendo código, no documentación.

- **Streaming: no existe nada.** `grep -i "streaming|provider|justwatch|netflix|plataforma"`
  sobre `src/` devuelve únicamente `anime_offline` (otro sentido de "provider").
  Punto de partida limpio.
- **Back office: existe y es real.** `index.admin.html` tiene siete secciones
  (Resumen, Bibliotecas, Miembros, Carteleras públicas, Base de datos, Fuentes externas,
  Matching), `web/routers/admin.py` expone endpoints solo-owner y `css/admin.css` les da
  forma. Una sección nueva encaja sin inventar arquitectura.
- **Settings genéricos: no existen.** Registrado en [Q3]: el idioma preferido quedó como
  constante fija `("es","en")` porque *"no existe infraestructura de settings en el
  proyecto"*. Es la deuda que el eje 1 paga.
- **Precedentes de estado de instancia:** `media_libraries`, `library_exclusion_rules`,
  `user_privacy_preferences`, `public_presentations`, todos con tabla dedicada, servicio,
  router y sección de admin. El patrón está probado cuatro veces.
- **Migraciones:** `instance_migrations` y `schema_migrations` existen y funcionan.
- **TMDb: integrado y opt-in.** [F4.1], [F4.2], [F5.1], [F5.2], [F5.3] dejaron token por
  archivo, adaptador, gateway condicional, rate limiting con `Retry-After`, cooldown,
  health en admin, atribución visual y — clave — retirada auditable con preview, purga,
  historial y undo (`domain/external_retirement.py`,
  `application/external_retirement.py`, `/api/integrations/tmdb/retirement/*`).
  **Pero nunca se ejecutó contra la API real:** 4 pruebas de smoke live quedan saltadas
  por falta de token. Ver sección 6.1.
- **Sin WebSocket, deliberadamente.** `docs/deployment.md:209`. La receta de Nginx está
  escrita asumiéndolo.
- **JSON portable v9.** `catalog.schema.json` es un contrato versionado con round-trip
  completo contra SQLite. Es el activo que habilita la dirección móvil de la sección 5.

---

## 2. Eje 1 — Regiones y plataformas (back office)

### Decidido

- **Tabla dedicada, no key-value genérico.** `streaming_regions` y `streaming_providers`
  con migración propia, siguiendo el patrón de `media_libraries`. Un settings genérico
  invitaría a que cualquier cosa futura se cuele sin contrato ni validación.
- **La lista de plataformas es semilla editable, no enum en código.** Mismo criterio que
  `starter_collections.py` usa para la colección de Kurosawa. Arranque: Netflix, Prime
  Video, HBO Max, Paramount+, Apple TV+, Disney+.
- **Argentina es la región inicial.** El modelo soporta varias desde el día uno para no
  migrar después.
- **La región es por usuario, no por instancia.** Corrección explícita del owner sobre la
  recomendación original. El modelo resultante tiene dos niveles:
  1. El **admin** define qué regiones existen en la instancia y si los usuarios pueden
     elegir la suya.
  2. Cada **usuario** elige su región entre las habilitadas; si no eligió, o si el admin
     no habilitó la edición, cae a la región por defecto de la instancia.

  Precedente directo: `user_privacy_preferences` ya modela una preferencia por usuario
  con defaults de instancia y overrides.

### Nota de implementación

La credencial de la fuente externa sigue siendo **de la instancia**, como fijó [F4.1].
Región por usuario y credencial por instancia no se contradicen: el owner acepta los
términos y administra la cuota; cada usuario elige sobre qué mercado consulta.

---

## 3. Eje 2 — Disponibilidad en streaming

### El camino corto

TMDb expone disponibilidad por plataforma y por país (los datos son de JustWatch). Si la
evaluación lo confirma, **no hace falta fuente ni credencial nueva**: el token, el
adaptador, el gateway, el backoff, el health y la atribución ya están.

**A verificar antes de escribir código**, con el rigor de [F3.1] (nada de esto se da por
confirmado en este documento):

- Cobertura real de Argentina y de cada plataforma que importa.
- Si el uso de datos de disponibilidad exige **atribución adicional a JustWatch**, además
  del aviso de TMDb que ya se muestra.
- Si el tope de retención de caché de seis meses de los términos aplica a este dato.
  Determinante: el owner aceptó un desfasaje de 1–2 meses, que cae holgado dentro de seis
  meses, pero el dato pasa a ser **persistido**, no cacheado, y [F3.1] ya dejó escrito que
  *"una ficha persistida exige procedencia y una vía de purga; no alcanza con llamarla
  caché"*. Esa vía de purga ya existe y se extiende, no se reinventa.

Alternativas a evaluar en la misma matriz: JustWatch no tiene API pública abierta; hay
APIs comerciales tipo *Streaming Availability* en RapidAPI (freemium, requiere key); el
scraping queda descartado por criterio del proyecto.

### Riesgo 1 — `en_catalogo` (invariante 2 de `CLAUDE.md`)

**Decidido.** `en_catalogo` conserva su significado exacto: **disponibilidad física
local**. La disponibilidad en streaming es un campo separado, `en_plataforma`, verdadero
cuando la obra está en al menos una plataforma. Son tres ejes independientes:

> tengo el archivo (`en_catalogo`) · **está en una plataforma** (`en_plataforma`) ·
> quiero verla / la vi (`status`)

Nunca se escribe disponibilidad de streaming dentro de `en_catalogo`, y `en_plataforma`
no vuelve verdadero a `en_catalogo`.

**Precisión de implementación:** `en_catalogo` es un booleano declarado y persistido;
`en_plataforma` es **derivado** de un snapshot con fecha de consulta. No conviene
persistirlo como campo gemelo que puede quedar desincronizado del snapshot que lo
justifica: se calcula al leer, a partir de las filas de disponibilidad vigentes.

### Riesgo 2 — honestidad temporal

**Decidido por el owner.** La ficha dice *"Disponible en Netflix"*, sin fecha. El dato de
cuándo se consultó vive en `Administrar`, junto al resto de la información de la fuente.

Queda registrado el riesgo que esto acepta: un dato de hasta ~2 meses se presenta sin
marca de frescura, y una plataforma puede haber retirado el título en el medio. El owner
lo aceptó a sabiendas para un producto personal. Mitigación barata que no cambia el texto
pedido: exponer la fecha en el atributo `title` del elemento y en `Administrar`, no en el
texto visible.

### Riesgo 3 — privacidad de las plataformas contratadas

**Decidido, y la propuesta del owner es mejor que la original.** Se informan **todas** las
plataformas donde está la obra, sin preguntar ni inferir qué contrata el usuario. La
personalización se hace con una lista de **plataformas ignoradas**: el usuario oculta las
que no le sirven.

Por qué es mejor: nunca se construye un modelo de "qué paga este usuario". Una lista de
plataformas ignoradas es semánticamente débil — ignorar Netflix no implica no tenerlo, y
tenerlo no implica no ignorarlo — mientras que una lista de suscripciones sería dato
personal duro bajo la invariante 4.

Corrección a la intuición del owner: **no es más complejo, es más simple.** No hay modelo
de suscripción, no hay vinculación de cuentas por plataforma, no hay estado que expire.
Es un filtro de presentación sobre un snapshot compartido.

**Residuo a cuidar:** la lista de ignoradas sigue siendo una preferencia por usuario y no
debe aparecer en payloads compartidos (Club, carteleras públicas, exportaciones). Mismo
tratamiento que `user_privacy_preferences`.

**Interacción con `en_plataforma`:** el snapshot subyacente se guarda crudo y compartido;
la lista de ignoradas se aplica al leer, para ese usuario. Es decir, `en_plataforma` se
evalúa sobre las plataformas no ignoradas de quien mira. Si se filtrara el snapshot en
origen, el dato dejaría de ser compartible y cacheable, y su significado quedaría atado a
quién preguntó.

---

## 4. Eje 3 — Charadas

### Qué es, corregido

**No es un juego multidispositivo sincronizado.** Es un **generador determinista** de
paquetes de títulos, más un temporizador. Se juega con uno o dos celulares
desincronizados: si dos jugadores eligen las mismas opciones, obtienen el **mismo paquete
de nombres**; saltear un título ya salido es responsabilidad del jugador, no del sistema.

Consecuencia: **cero infraestructura de tiempo real**, y por lo tanto ningún conflicto con
la decisión de no usar WebSocket. También lo vuelve el primer candidato natural para
funcionar sin servidor (ver sección 5).

### Mecánica decidida

- **Dificultad por categorías:** fácil, medio, medio alto, difícil, y quizá alguna más.
  El criterio se define durante el desarrollo del juego, no ahora.
- **Temporizador con tres opciones de tiempo por dificultad**, escalando con ella:
  fácil 1 / 2 / 3 minutos; medio 1:30 / 2:30 / 4 minutos; y así hacia arriba. Tocar la
  opción arranca la cuenta; se puede reiniciar.
- **Mínimo de datos: 300 obras.** Hoy hay ~30 (Kurosawa). Plan del owner: sumar al Club
  unos 10 directores conocidos.

### El riesgo real del determinismo

"Mismas opciones → mismo paquete" sólo se cumple si **ambos teléfonos miran los mismos
datos**. Si uno sincronizó el catálogo y el otro no, las mismas opciones producen paquetes
distintos y el juego se rompe en silencio.

Por lo tanto la semilla del generador no puede ser sólo las opciones elegidas: tiene que
incluir una **identidad del conjunto de datos** (una huella del catálogo o colección de
origen). Y esa huella debe ser visible en la interfaz, para que dos jugadores puedan
verificar de un vistazo que están jugando el mismo mazo.

Precedente reutilizable: `back-cover.js` ya mapea un ID opaco a una de cinco plantillas
estables mediante un hash puro. La ronda se construye igual.

### El problema de la dificultad, y una fuente que ya tenemos

Actuar un título depende de dos cosas: **qué tan representable es el título** y **qué tan
conocida es la obra**. Una película que nadie del grupo conoce es imposible de adivinar,
por fácil que sea su título.

- **Representabilidad:** hay señales locales suficientes hoy — cantidad de palabras,
  longitud, nombres propios, sustantivos concretos contra abstractos, género, año.
- **Notoriedad:** **no tenemos ninguna señal**, y es la mitad que más pesa.

Hay dos fuentes posibles para la notoriedad y conviene elegir después de activar TMDb; el
detalle y la decisión pendiente están en la sección 6.3.

Si el algoritmo no rinde, el fallback declarado por el owner es clasificación manual con
él depurando. Conviene diseñar el modelo de datos para que la clasificación manual sea
posible desde el día uno, no como parche.

### Sobre las 300 obras

Aritméticamente el plan cierra: 10 directores × 20–30 obras ≈ 200–300.

Dos advertencias prácticas:

1. **El mínimo que importa no es el total, es el de cada balde.** 300 obras repartidas en
   cuatro dificultades dan ~75 por balde, que alcanza para una noche. Si el reparto sale
   desparejo, el balde flaco es el que define si el juego funciona.
2. **Un catálogo de autor sesga el mazo entero.** Kurosawa, Tarkovski y compañía producen
   un mazo donde casi todo cae en "difícil". Para que existan los baldes fáciles hacen
   falta títulos masivamente conocidos, que no son los que un catálogo curado de cinéfilo
   tiende a acumular. Vale la pena elegir los 10 directores con ese criterio en mente, o
   aceptar una fuente de títulos populares aparte.

### Relación con [M1] — corregido

La suposición previa era errónea. **[M1] es un catálogo de videojuegos y música**: qué
poseo, en qué consola, qué quiero conseguir. Charadas no es una versión de eso ni compite
con eso: es una superficie de juego sobre el catálogo audiovisual existente. Son dos
frentes distintos y ninguno bloquea al otro. Charadas no agrega valores a `kind`.

---

## 5. Dirección móvil — cambio de norte

### Estado verificado hoy

Lo bueno, comprobado contra el código:

- `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`.
- Breakpoints coherentes en todo el proyecto: 860 / 640 / 440 / 360 px.
- `a11y.css` cubre `prefers-reduced-motion`, `forced-colors` y `(hover: none) and
  (pointer: coarse)`.
- La suite de navegador prueba móvil de verdad: 390×844 y 320×720, contexto Playwright
  con `is_mobile=True` y touch real, targets de 44×44 px, cero overflow horizontal,
  poster roto, títulos largos.
- [U2-R.6] fue una auditoría móvil explícita con mediciones reales.

Lo que falta:

- **No hay PWA:** cero manifest, cero service worker, cero iconos, cero offline.
- **El diseño es desktop-first.** El criterio de cierre de U2-R fue *"móvil no queda peor
  que antes de U2"*: móvil fue preservado y reparado con rigor, no diseñado.
- **Bandeja e Importaciones son el eslabón débil:** rompen recién en 700–1120 px y son las
  superficies más densas del producto.
- **Sin registro público:** cada tester necesita una cuenta creada desde Admin.

### El norte nuevo

**Decidido por el owner.** La aplicación móvil debe ser **independiente**, no un cliente
delgado: tiene que poder funcionar sin servidor web ni instancia dockerizada. La
sincronización con una instancia web es **opcional**, iniciada por el usuario, por ejemplo
mediante QR. Y charadas se considera más importante en móvil que en web.

Esto **no es [A2]**. [A2] está especificada como cliente delgado contra la API de [A1]:
login contra una URL HTTPS, lectura del catálogo del servidor, patch de estado personal,
explícitamente sin offline. Lo que el owner quiere es otro producto. **[A2] necesita
reespecificación antes de tomarse**, no sólo ejecución.

### Lo que juega a favor

- `catalog.schema.json` v9 es un contrato portable versionado con round-trip completo.
  Es exactamente lo que hace viable un cliente autónomo que después sincroniza.
- **[W3] / ADR-0002 aporta los principios, no el formato.** *(Corregido el 2026-09-07 en
  ADR-0005: la afirmación original era demasiado fuerte.)* El formato `.mipkg` excluye por
  contrato estado de visionado, rating, review y notas — justo lo que una sincronización
  de dispositivo debe llevar, así que el formato no se reusa. Sí se reusan sus principios:
  previsualizar antes de escribir, digest de integridad, sin servicio central, decisión
  explícita del owner, receipts y "nunca fusionar por parecido".
- Charadas es el primer entregable ideal de esta dirección: datos de sólo lectura, sin
  sincronización, sin red, y es lo que el owner más quiere en el teléfono.

### Corrección técnica sobre el QR

Un QR **no puede transportar un catálogo**. El máximo teórico de un QR versión 40 con la
corrección de errores más baja ronda los 2953 bytes binarios, y en la práctica útil es
bastante menos. Un catálogo de 300 obras no entra ni cerca.

El QR sirve como **portador del apareamiento**: origen, identidad y un token de un solo
uso. La transferencia real viaja después por HTTP en la red local, o por archivo. Es el
mismo rol que cumple el QR en cualquier emparejamiento de dispositivos.

### El problema difícil que hay que nombrar ahora

Sincronización **bidireccional de estado personal** — `status`, `watched_at`, `rating`,
`review` — editado en dos lados sin conexión. El proyecto tiene precedentes fuertes de
resolución conservadora (`locked_fields`, correcciones manuales que sobreviven al
enriquecimiento, matching conservador, historial de curaduría con deshacer), pero ninguno
resuelve esto: son políticas de *enriquecimiento*, no de *convergencia entre réplicas*.

Es la decisión más difícil de toda la dirección móvil y conviene tomarla en un ADR antes
de escribir la primera línea del cliente, no después.

---

## 6. Deuda de fuentes externas

### 6.1 TMDb — activación y validación real (se toma primero)

**Decidido por el owner:** esta tarea va antes que los tres ejes.

**El hueco concreto:** [F5] está marcada completa y el código lo está — adaptador,
gateway, identidad, procedencia, retirada, atribución, backoff. Pero **TMDb nunca se
ejecutó contra la API real**. Cada cierre lo dejó explícitamente pendiente:

- [F3.2]: *"No se hizo una llamada live porque toda llamada exige key: la comprobacion
  empirica queda como criterio de [F5]"*.
- [F5.1]: *"No hubo key ni llamada live"*.
- [F5.3]: la validación en navegador se hizo **con un token inválido** (*"con error
  controlado por token invalido, sin crash"*). El camino "configurado" se probó; el
  camino "configurado **y válido**" no. Nunca se renderizó un resultado real de TMDb.
- [F4.2]: el overlay `compose.tmdb.example.yaml` nunca se validó con un `docker compose
  config` real porque Compose no estaba instalado en el host.

Verificado hoy, 2026-09-07: `tests/test_external_tmdb*.py` corre 17 pruebas — 13 pasan y
**4 quedan saltadas**, las del smoke live gateado por
`MOVIE_INBOX_TMDB_LIVE_SMOKE_TOKEN`. Docker tampoco está instalado en este host.

**Alcance de la tarea:**

1. Cargar un API Read Access Token real por el camino ya construido
   (`--tmdb-read-access-token-file` o `MOVIE_INBOX_TMDB_READ_ACCESS_TOKEN_FILE`, que
   lleva la **ruta**, nunca el token).
2. Correr el smoke live sobre el corpus ya acordado en [F3.2] — `Addio Zio Tom`,
   `Fanny & Alexander`, `Verano 1993 (2017)`, homónimo `Heat` movie/TV.
3. Validar en un servidor real con token **válido**: estantería con resultados de verdad,
   atribución visible, fila en `Administrar → Fuentes externas`, y el alta de una obra
   entrando por el flujo de enriquecimiento y materialización.
4. Smoke del overlay de Docker, si hay un host con Compose disponible.

**Expectativa realista:** es probable que aparezcan bugs, y ese es el punto. El precedente
es [F1], donde la corrida real contra datos reales encontró dos fallas que ningún test
sintético iba a encontrar (TLS estricto contra la cadena de CloudFront, `UnicodeEncodeError`
imprimiendo alias fuera de cp1252). Un adaptador que nunca habló con su servidor no está
validado, está escrito.

**Lo que no se hace:** provocar un `429` real golpeando la API a propósito. El cooldown ya
está probado contra un `429` sintético con el adaptador real; forzar uno de verdad sería
abusar del servicio.

**Nota de credenciales:** el token es un secreto y no debe pasar por el chat. Se crea el
archivo del lado del servidor y se apunta la ruta. Ojo con una asimetría del diseño: la
variable de producción lleva la **ruta**, pero `MOVIE_INBOX_TMDB_LIVE_SMOKE_TOKEN` — la
del test opt-in — lleva **el token**. Conviene exportarla sólo en la sesión de shell donde
se corre el smoke, y nunca escribirla en un script, un `.env` versionado o el historial.

**Por qué inspira al resto:** sin credencial funcionando, [S2] no se puede responder. La
cobertura real de Argentina, qué plataformas devuelve y si exige atribución a JustWatch
sólo se averiguan consultando. Esta tarea es literalmente el prerrequisito del eje 2.

#### Cierre 2026-09-07

Ejecutada. El smoke live pasó 4/4 sobre el corpus de [F3.2] y la verificación en navegador
se hizo con token válido sobre una instancia descartable con catálogo sintético — nunca se
tocó el catálogo personal del owner. Salud real de las cinco fuentes en `Administrar`, y un
alta de `Blade Runner` entró por enriquecimiento y materialización conservando `tmdb_id`
78, `imdb_url` y `wikidata_id` derivados de `external_ids`, duración sólo de película y
procedencia `tmdb` en los 24 campos aportados — la condición que [F5.2] necesita para que
la retirada auditable funcione.

Tres hallazgos que sólo una corrida real podía producir:

1. **La interceptación TLS de un antivirus local** rompía TMDb, IMDb, FilmAffinity y Jikan
   por igual. Se resolvió excluyendo los hosts en el antivirus, no en el código.
2. **La relajación de `VERIFY_X509_STRICT` de [F1] no hacía falta.** Su diagnóstico
   culpaba a la cadena de CloudFront; la causa real era el mismo antivirus. Con los hosts
   excluidos, la cadena real de Amazon verifica bajo el estricto por defecto y también
   contra `certifi` solo. Eliminada en el commit `a08298c`.
3. **TMDb no tenía etiqueta en el frontend.** `SOURCE_LABELS` (`js/core/format.js`) nunca
   recibió su entrada, así que cada resultado real se mostraba como `Sin fuente`. Cosmético
   en la tarjeta, pero `duplicateSignalsCollide()` compara etiquetas y no fuentes crudas,
   de modo que dos obras de fuentes distintas sin etiqueta colapsaban en una sola señal y
   el fallback de desambiguación de [V5-4] perdía un dato real. Corregido, con una prueba
   estructural que exige que toda fuente registrable tenga etiqueta.

**Pendiente acotado:** el smoke del overlay `compose.tmdb.example.yaml` sigue sin correr —
Docker no está instalado en el host de trabajo. Queda como en [F4.2], esperando un host con
Compose.

**Hallazgo abierto, no corregido:** `duplicateSignalsCollide()` compara etiquetas de
presentación en vez de fuentes crudas. Agregar la etiqueta de TMDb tapa el síntoma actual,
pero cualquier fuente futura sin entrada en el mapa reintroduce el mismo defecto. Merece
tarea propia; no se tomó por disciplina de alcance.

### 6.2 IMDb — el índice desconectado

Hallazgo del relevamiento, no la tarea que se toma primero. Sigue siendo real y vale la
pena tomarlo después.

**El hueco concreto**

[F1] entregó `movie-inbox imdb-dataset sync/stats/lookup`: un índice SQLite propio con
12.749.320 títulos y 59.128.959 alias, **deliberadamente desconectado del catálogo real**
— no toca `domain/catalog.py`, `metadata_sources` ni ningún merge.

Pero [Q5] fijó la matriz de autoridad por familia de campo y puso a **[F1] primero** para
clasificación (`year`, `kind`) y para otras familias. Es decir: **la política de autoridad
nombra como fuente primaria a un índice que producción no puede consultar.** El prototipo
existe, la política lo asume, y el cable entre los dos no está.

Cerrarlo es valioso por sí mismo y además desbloquea el resto de lo conversado:

- Es una fuente **local, offline, sin rate limit y sin credencial**. Ninguna de las otras
  cuatro lo es.
- Agregándole `title.ratings` da la señal de notoriedad que la dificultad de charadas
  necesita.
- Un índice local es exactamente el tipo de componente que un cliente móvil autónomo
  puede llevar consigo, o consultar durante una sincronización.

### Costos reales medidos en [F1], a tener presentes

Descarga ~704 MB en pocos segundos; el build del índice tarda ~24 minutos y el `.db`
resultante ocupa ~8,1 GB. No es un componente que se instale por defecto ni que viaje a un
teléfono entero: cualquier diseño tiene que tratarlo como opt-in del lado servidor, o
extraer de él un subconjunto mucho más chico.

### 6.3 Dos caminos para la señal de notoriedad de charadas

La dificultad de charadas necesita saber qué tan conocida es una obra (sección 4). Con la
corrección de arriba aparecen dos fuentes posibles, y conviene elegir recién después de
6.1:

- **TMDb `vote_count`** — online, gratis en la misma llamada que ya se hace, sin índice de
  8 GB. Disponible apenas la credencial funcione.
- **IMDb `title.ratings`** — offline, sin rate limit, pero exige el índice completo.

El primero es mucho más barato y probablemente alcanza. Ambos chocan con la misma regla de
[F3.2], que dejó el puntaje público fuera de alcance: sea cual sea, **no puede tocar
`rating` personal ni presentarse como valoración**. Usarlo como señal de notoriedad para
dificultad de juego es un uso distinto del prohibido, pero necesita decisión explícita.

---

## 7. Encaje en el backlog

Cola vigente antes de este análisis: **1** [U2-P] · **2** [U3] · **3** [A2] · **4** [I1] ·
**5** [M1].

[U2-P] y [U3] pasan a Codex. Lo de abajo es la cola de Claude y **no tiene dependencias
con el trabajo visual**, salvo donde se indica.

### Frente: Fuentes externas — deuda de validación

- **[F5.4] Activar y validar TMDb contra la API real.** Token real por el camino de
  [F4.2], smoke live sobre el corpus de [F3.2], validación en navegador con token válido,
  alta real entrando por enriquecimiento y materialización, y smoke del overlay de Docker
  si hay host con Compose. Corregir lo que la corrida real encuentre. *Medio en código,
  Grande en criterio si aparecen bugs de contrato.* **Sin dependencias — se toma primero.
  Prerrequisito de [S2].**
- **[F6.1] Conectar el índice de [F1] a búsqueda y matching.** Cerrar el hueco entre la
  matriz de autoridad de [Q5] y el prototipo desconectado. Opt-in, sin volverse
  obligatorio para una instalación que no lo indexó. *Grande. Sin dependencias, pero va
  después de F5.4 por decisión de prioridad.*
- **[F6.2] Señal de notoriedad y puntajes públicos.** **Mitad de datos cerrada
  2026-09-07.** El owner decidió **tomar las dos fuentes en vez de elegir una**, para que
  el lector compare en lugar de que se le imponga una vara, con su propio puntaje al lado.
  `title.ratings` entra al índice liviano y se lee al mostrar, nunca se guarda en el
  catálogo. `GET /api/ratings` lo expone. La regla de [F3.2] sigue firme y ahora es
  estructural: un puntaje público nunca llega a `rating` personal.
  - **Pendiente, para Codex:** presentarlos en la ficha, junto al puntaje propio, con la
    atribución de IMDb que exigen sus términos (`attribution.imdb` viene en la respuesta).
    Un puntaje con menos de 50 votos llega marcado `is_meaningful: false` — merece verse
    distinto, porque un 9,9 de tres personas al lado de un 8,3 de setecientas mil invita
    una comparación que no existe.
  - **Pendiente, mío:** los puntajes de TMDb. Se dejaron fuera a propósito: mostrarlos
    exige guardar un número que envejece o una llamada de red por vista, o sea el mismo
    tratamiento de snapshot fechado que [S3] le dio a la disponibilidad. Los de IMDb no
    tienen ese problema porque salen del índice local y el owner controla cuándo se
    re-sincroniza.

### Frente: Disponibilidad en streaming

- **[S1] Back office de regiones y plataformas.** Tablas dedicadas, migración, servicio,
  endpoints solo-owner, sección de admin. Región por usuario con habilitación del admin y
  default de instancia. *Grande.*
- **[S2] Evaluar fuentes de disponibilidad.** **Cerrada 2026-09-07 —
  `docs/adr/0004-streaming-availability-source.md`.** TMDb elegida, medida contra la API
  real: AR soportada entre 139 regiones, 59 proveedores, las seis plataformas pedidas
  presentes. Dos condiciones: atribución obligatoria a JustWatch con cláusula de
  revocación, y el tope de retención de seis meses aplica al snapshot. Hallazgo propio de
  este catálogo: el cine de autor tiene cobertura engañosa — o no aparece, o aparece sólo
  en plataformas marginales que la lista de ignoradas va a esconder.
- **[S3] Consulta, persistencia y procedencia.** **Cerrada 2026-09-07 — commit `1e0b2b7`.**
  Snapshot fechado en tabla propia, refresco perezoso a los 30 días, corte contractual a
  los 180, `en_plataforma` derivado al leer y la retirada de TMDb extendida para
  borrarlos. El catálogo portable no se tocó: sigue en schema v9.
- **[S4] Superficie: ficha, filtros, plataformas ignoradas.** **Asignada a Codex el
  2026-09-07** por decisión del owner: es trabajo de presentación y encaja con el
  rediseño de Colección de [U3]. El backend ya está entregado y probado; ver el traspaso
  más abajo.

#### Traspaso de [S4] a Codex

El backend está completo. Lo que falta es sólo mostrarlo.

**Lo que hay que consumir:**

- `GET /api/streaming/availability` — devuelve `{"availability": {<item_id>: {...}}}` para
  el catálogo de quien llama. Sólo trae las obras que tienen identidad TMDb; una obra
  ausente del mapa significa **"no sabemos"**, nunca "no está disponible".
- Cada fila trae `en_plataforma` (booleano ya derivado, con las plataformas ocultas del
  usuario aplicadas), `available_on`, `acquire_on`, `checked_at`, `region_code`, `link` y
  `known`.
- `GET`/`POST /api/streaming/preferences` — lee y escribe la región elegida y la lista de
  `ignored_providers` del usuario. El `POST` rechaza con `400` un id de plataforma que no
  existe en la región activa.

**Tres reglas que la interfaz no puede romper:**

1. **`known: false` no es "no disponible".** Es "no lo consultamos". Merece un texto
   distinto, no un tilde en gris.
2. **`available_on` y `acquire_on` no son lo mismo.** Lo primero se mira con la
   suscripción; lo segundo se alquila o se compra. Decisión del owner: sólo lo primero
   es "Disponible en X"; lo segundo necesita otro verbo, tipo "se consigue en".
3. **La atribución a JustWatch es obligatoria** donde se muestre disponibilidad, y es
   distinta del aviso de TMDb que ya existe. Los términos incluyen una cláusula de
   revocación de acceso a toda la API, así que no es opcional. Texto y detalle en
   `docs/adr/0004-streaming-availability-source.md`.

**Decisión del owner sobre la fecha:** la ficha dice "Disponible en Netflix" sin fecha; el
`checked_at` se informa en `Administrar`. El dato puede tener hasta dos meses.

### Frente: Charadas

- **[G1] Contrato de datos, generador determinista y dificultad.** **Cerrada 2026-09-07 —
  `docs/briefs/charades-v1.md`.** Semilla = opciones + huella del mazo, mostrada en
  pantalla para que dos jugadores verifiquen que están en el mismo. Mínimo de 300 obras y
  **25 por balde**, porque el balde flaco es el que define si el juego funciona.
  **Hallazgo medido:** la clasificación automática de dificultad **no funciona** — el
  conteo de votos mide atención cinéfila global, no reconocimiento en la sala, y no
  distingue `Los siete samuráis` (370k, pocos) de `Batman` (400k, todos). Se automatizan
  sólo los extremos y la banda intermedia va a revisión humana, que pasa a ser el camino
  principal y no un plan B. Una dificultad puesta a mano sobrevive a cualquier recálculo.
  Se calcula en el servidor y viaja como un campo chico.
- **[G2] Implementar generador y temporizador.** *Medio. Depende de G1 y de la decisión
  móvil de MB1.*

### Frente: Dirección móvil

- **[MB1] ADR de dirección móvil.** **Cerrada 2026-09-07 —
  `docs/adr/0005-mobile-direction.md`.** Cliente autónomo con almacén propio; el servidor
  es un par opcional. La sincronización la inicia una persona y **nunca borra**. La
  convergencia de estado personal es una **fusión a tres bandas** contra la base de la
  última sincronización: si sólo un lado cambió se aplica, si ambos cambiaron distinto
  decide la persona — sin depender de relojes confiables. El QR aparea, no transporta.
  [A2] queda suspendida hasta reespecificarse y [A1] gana una extensión aditiva.
  Ampliada el mismo día con cuatro decisiones más del owner: **Android nativo con
  Kotlin**; dar de alta sin conexión produce un **borrador que no expira** (a
  diferencia de los de importación, que mueren a las 48 h); las imágenes usan
  **miniatura local más portada en segundo plano**; y **una cuenta por instalación**.
  Consecuencia para charadas: la dificultad se calcula en el servidor y viaja como un
  campo chico, porque el índice IMDb de ~1,1 GB no va al teléfono.
- **[MB2] Auditoría móvil con usuarios reales.** Inicio, Colección, ficha y Club en
  teléfono, con cuentas creadas de antemano y HTTPS servido según [D1.2]. Insumo para MB1.
  *Medio.* **Sin dependencias — puede hacerse ya.**

### Nota sobre [I1]

[I1] (Radarr, Sonarr, Letterboxd) y [S2] son la misma clase de trabajo: evaluación de
integraciones externas con matriz y ADR. Conviene usar la misma plantilla para no
reinventarla dos veces.

---

## 8. Decisiones abiertas

1. **[F5.4]** — el owner tiene que crear el API Read Access Token en su cuenta de TMDb y
   dejarlo en un archivo del servidor. El token no pasa por el chat. Bloquea el arranque.
2. **[F6.2] / [G1]** — usar un conteo de votos público como señal de notoriedad para
   dificultad de juego, sin que toque `rating` personal ni se presente como valoración.
3. **[G1]** — criterio de dificultad definitivo, y si se acepta una fuente de títulos
   populares además del catálogo curado, para que los baldes fáciles existan.
4. **[MB1]** — convergencia de estado personal editado sin conexión en dos réplicas.
