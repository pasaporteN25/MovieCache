# Cliente Android v3 — plan de construcción

**Fecha:** 2026-09-07. **Reemplaza** `android-client-v2.md`.
**Motivo:** el owner fijó cuatro decisiones que v2 no contemplaba, y una de ellas cambia
la puerta de entrada del producto.
**Actualizado el 2026-09-11:** las notas fechadas de abajo marcan qué quedó construido del
lado servidor y qué no. El estado vive en `tareas.md`, [A2].

## Qué cambió respecto de v2

| | v2 (2026-09-07, mañana) | v3 (esta) |
| --- | --- | --- |
| Primer arranque | **sin cuenta y sin instancia** | **requiere cuenta creada en la web** |
| Apareamiento | entrega tardía (A2.4) | **primera entrega** |
| Primer hito | charadas con datos locales | **ver tu catálogo real en el teléfono** |
| Sincronización | bidireccional | bidireccional, confirmado |
| Alta sin conexión | mencionada | **caso de uso central** |

La decisión de la cuenta es la que más ordena. v2 permitía crear un catálogo local sin
instancia, y eso arrastraba el peor problema del diseño: alguien crea datos en el teléfono,
después aparea, y hay que fusionar dos historias **que nunca compartieron una base**. Con
cuenta obligatoria siempre existe una base común desde el primer minuto, y la
sincronización pasa de ser un problema abierto a uno acotado.

**ADR-0005 queda enmendada por esto** — ver su sección 7.

## El caso de uso que manda

> "Poder guardar películas en la colección sin necesidad de estar frente a la computadora
> o en casa."

Ese es el centro. No es "ver el catálogo en el teléfono": es **agregar** desde el teléfono,
sin conexión, sin perder nada. Todo lo de abajo está ordenado alrededor de eso.

---

## La distinción que sostiene todo el diseño

Un cambio hecho sin conexión puede ser de dos clases, y **necesitan mecanismos distintos**.
Confundirlas sería el error caro de este proyecto.

### Editar una obra que ya existe de los dos lados

Hay una **base compartida**: la obra estaba en el teléfono y en el servidor cuando se
sincronizaron por última vez. Entonces se puede hacer fusión a tres bandas, por campo:

| Local vs base | Servidor vs base | Resultado |
| --- | --- | --- |
| igual | cambió | se toma el del servidor |
| cambió | igual | se toma el local |
| cambió | cambió, al mismo valor | converge solo |
| cambió | cambió, distinto | **decide la persona** |

Sin relojes, sin "gana el último". Es lo que decidió ADR-0005 y no cambia.

### Agregar una obra que no existe en ningún lado

**No hay base.** No es una fusión: es una **importación**. Y el proyecto ya tiene un camino
de importación acotado, con revisión humana de lo ambiguo, que funciona y está probado.

Tratar un alta como si fuera una fusión obligaría a inventar una base que no existe. Tratarla
como importación reusa todo lo que ya hay.

---

## Cómo funciona un alta sin conexión, en concreto

Estás en el colectivo. Alguien te nombra *El botón de nácar*. La abrís y la guardás.

**1. En el momento, sin red.** El teléfono tiene la réplica completa de tu catálogo, así que
puede hacer algo útil ya: normaliza el título con **las mismas reglas que el servidor** y te
avisa si se parece a algo que ya tenés. Es un aviso, no una decisión — vos seguís si querés.

Eso exige portar `title_match_key` y la normalización a Kotlin. **Es la misma técnica que ya
usa charadas**: el generador se reimplementó portable a propósito, con vectores de prueba del
servidor para garantizar que las dos implementaciones coinciden. Acá igual.

**2. Se guarda como borrador local.** Id generado en el cliente, marcado como no enriquecido
y con origen `telefono`. Aparece en la lista al instante — ese es el punto: guardarla y
olvidarte.

**No expira.** A diferencia de los borradores de importación, que mueren a las 48 h, uno
offline puede esperar días a que haya red. Hacerlo expirar sería exactamente el defecto que
la decisión vino a evitar. Sólo lo cierra la persona.

**3. Al sincronizar.** El borrador se empuja al servidor, que sí tiene red y sí puede
enriquecer. Y ahí decide el matching que ya existe:

- **Identidad fuerte que coincide** con una obra del catálogo → se une a ella, y el teléfono
  se entera.
- **Ambigua** → va a la cola de revisión que ya existe, y el teléfono la muestra como
  "pendiente de revisión". Nadie decide por vos.
- **Claramente nueva** → se crea, enriquecida.

El invariante 3 se respeta sin esfuerzo: **el teléfono nunca decide identidad**. Avisa, y el
servidor enriquece cuando puede, y lo dudoso lo mira una persona.

> **Cómo quedó construido, 2026-09-09 (`f6e36e1`).** El servidor **no** enriquece al
> recibir: sería una llamada de red que haría esperar —o fallar— a un teléfono que acaba de
> recuperar señal. Guarda lo que la persona escribió en un borrador por cuenta, que no
> vence, y el enriquecimiento corre al revisar. Y como el teléfono manda título y año, no
> una identidad fuerte, una obra que ya tenés no se une sola: vuelve como `review`, porque
> un parecido de título no es identidad. El invariante 3 queda igual de respetado, con un
> paso más en manos de la persona.

---

## Apareamiento: qué lleva el QR y por qué

El QR se escanea de la pantalla de tu instancia, o sea es un **canal fuera de banda
confiable**. Eso lo hace el lugar correcto para establecer confianza.

Lleva cuatro cosas, y ninguna es el catálogo:

1. **Origen** — el `https://host:puerto` de la instancia.
2. **Token de un solo uso**, de vida corta, que se canjea por una sesión de dispositivo.
3. **Identidad técnica** de la instancia y de la cuenta.
4. **Huella SPKI del certificado**, SHA-256 en base64: 44 caracteres.

El catálogo **no** entra: un QR llega a 2953 bytes en el mejor caso (versión 40, corrección
L, modo byte), y eso no alcanza ni para un puñado de obras. El QR aparea; la transferencia
va después por HTTPS.

### El detalle de certificado que hay que hacer bien

Verificado el 2026-09-07, y contradice la solución "obvia":

> **`CertificatePinner` de OkHttp no sirve para aceptar un certificado autofirmado.** El
> pinning se comprueba *después* de un handshake exitoso, así que un certificado que el
> trust manager de la plataforma rechaza falla antes de que el pin llegue a mirarse.

Entonces hay dos caminos según cómo sirvas la instancia, y la app tiene que soportar los dos:

- **Certificado de una CA pública** (Let's Encrypt, como documenta `docs/deployment.md`): la
  plataforma ya confía. El pin del QR se usa **encima**, como refuerzo. Nada especial.
- **Certificado autofirmado en la red local**: hace falta un **trust anchor propio**,
  construido en tiempo de ejecución a partir de lo que trajo el QR —`HandshakeCertificates`
  de `okhttp-tls`, o un `X509TrustManager` que acepte sólo el certificado cuya huella SPKI
  coincida con el pin—. Es confianza al primer uso, pero establecida fuera de banda por vos
  escaneando tu propia pantalla, que es una garantía real y no un `TrustManager` que acepta
  todo.

**Lo que nunca se hace:** un trust manager permisivo, ni deshabilitar la verificación de
hostname. Eso convertiría cualquier red hostil en un ataque trivial y tiraría abajo lo que
[A1.2] construyó.

### Una pregunta operativa que no es de código

Si tu instancia tiene dominio público con certificado de Let's Encrypt y estás en la red de
casa, el teléfono resuelve la IP pública y **puede que el router no haga hairpinning**. Las
salidas son DNS de horizonte partido, o servir también por IP local con certificado
autofirmado y pin. Conviene decidirlo antes de A2.1 porque cambia lo que va en el QR.

> **Resuelta el 2026-09-09.** La instancia está en la red local y no tiene dominio, así
> que sirve HTTPS en su propio proceso con un certificado autofirmado y el pin viaja en el
> QR. Receta en `docs/deployment.md`, "HTTPS en la red local, sin dominio".

La VPN, como dijiste, es del usuario: si el teléfono llega a la instancia, la app no
necesita saber cómo.

---

## Orden de entrega

Cambia respecto de v2 porque tu primer hito es ver tu catálogo real.

| Parte | Entrega | Servidor que hace falta |
| --- | --- | --- |
| **A2.0** | Entorno: JDK 17+, SDK, Gradle, `assembleDebug` verde | — |
| **A2.1** | Esqueleto, apareamiento por QR, descarga completa, **lectura offline** | **apareamiento** — hecho, falta la pantalla |
| **A2.2** | Edición personal offline y fusión a tres bandas | — (el `PATCH` ya existe) |
| **A2.3** | **Alta offline** con borradores que no expiran | **alta desde dispositivo** — hecho |
| **A2.4** | Charadas | **dificultad y clave de obra por la API de dispositivo** — falta |
| **A2.5** | Imágenes: miniatura local y portada en segundo plano | — |
| **A2.6** | Ampliar lo que viaja, en tu orden de prioridad | **colecciones, disponibilidad, puntajes** — hecho |

La columna de servidor dice cómo está al 2026-09-11, con sus commits en `tareas.md`, [A2].

### A2.1 — lo primero que vas a tener en la mano

Kotlin y Compose, Hilt con KSP, coroutines y `StateFlow`. **El repositorio es el límite de
errores**: la interfaz no recibe excepciones de red ni DTOs.

Escaneo del QR con **ZXing embebido** antes que ML Kit: para un único escaneo en el
apareamiento, ZXing no arrastra dependencia de Google Play Services, y ML Kit sin empaquetar
sí. Si más adelante hiciera falta escanear mucho, se reevalúa.

El almacén local es **Room**, y guarda la capa de obra y la capa personal con la forma del
contrato portable v9: identidad, títulos, año, tipo, IDs externos, géneros, duración,
imágenes, y `status`, `watched_at`, `rating`, `review`.

**No guarda la capa operativa** —rutas, archivos, bibliotecas, Scanner, curaduría—, y no sólo
por privacidad: un teléfono no tiene tus discos, así que esos campos no significan nada ahí.
`en_catalogo` viaja como lectura; el teléfono no puede afirmarlo.

Una cuenta por instalación.

### A2.2 — editar sin conexión

Room guarda por obra **dos versiones**: la `base` —el estado del servidor en la última
sincronización exitosa— y la local actual. La fusión de arriba corre contra esas dos más lo
que traiga el servidor.

**La base sólo avanza cuando una sincronización termina entera.** Una sincronización
interrumpida no puede dejar el teléfono creyendo que convergió: es la diferencia entre
recuperarse de un túnel y corromper la historia.

La interfaz de conflictos es trabajo real, no un diálogo de dos botones: tiene que mostrar
los dos valores, de cuándo es cada uno y dejarte elegir por campo.

### A2.6 — ampliar de a poco, en tu orden

Tal como pediste, y cada escalón es servidor más cliente:

1. **Catálogo y estado personal** — ya expuesto por la API v1.
2. **Colecciones seguidas** — expuestas desde el 2026-09-09.
3. **Disponibilidad en streaming** — ojo: es dato de TMDb con tope contractual de retención
   de 180 días. Ese tope **viaja con el dato**: el teléfono también tiene que dejar de
   mostrarlo cuando vence, o la copia local se convierte en la forma de incumplir los
   términos. Expuesta desde el 2026-09-09, y cada fila lleva su `expires_at`.
4. **Puntajes públicos** — lo que ya sirve `/api/ratings`; expuestos desde el 2026-09-09.

---

## Lo que hay que construir del lado servidor

Es mi mitad del trabajo. **Al 2026-09-11 está hecha salvo dos piezas**, marcadas abajo; el
detalle y los commits están en `tareas.md`, [A2].

- **Apareamiento.** Token de un solo uso con vida corta, endpoint de canje, y la pantalla
  que dibuja el QR en `Administrar`. Se apoya en las sesiones opacas revocables de [A1.2] y
  en la clave de sincronización durable de [A1.4], ya cerradas.
  **Hecho** (`334f4fe`, `e9bcaab`, `11dbe0b`), **salvo la pantalla**, que además no va en
  `Administrar`: cada cuenta aparea su propio teléfono.
- **Alta desde dispositivo.** Endpoint que recibe un borrador, lo enriquece y lo mete por el
  camino de importación y revisión que ya existe. Sin atajos que salteen la revisión.
  **Hecho** (`f6e36e1`), sin enriquecer al recibir: ver el paso 3 del alta, más arriba.
- **Exposición progresiva** de colecciones, disponibilidad y puntajes, en ese orden.
  **Hecho** (`9ff3ccd`, `7f24895`, `417f6d3`).
- **Dificultad de charadas por la API de dispositivo — falta.** Ni la dificultad ni la clave
  de obra con la que el generador calcula la huella del mazo viajan hoy al teléfono, así que
  no puede producir el mismo mazo que el servidor. Encontrado el 2026-09-11 al poner el
  tablero al día.

Todo aditivo —rutas y campos nuevos, sin cambiar el significado de ninguno existente—, así
que cabe en la v1 de la API según la regla de versionado de ADR-0003.

## Lo que sobrevive del brief v1

Trabajo de seguridad que sigue valiendo: tokens en Android Keystore y nunca en preferencias
sin cifrar, logs, analytics, URI, portapapeles ni backups; HTTPS con certificado válido, con
la excepción de `http://10.0.2.2` sólo en `debug`; ignorar campos opcionales desconocidos;
respetar `X-Movie-Inbox-Api-Version`; y no usar el `/api/` histórico, cookies ni
`X-Movie-Inbox-Token`.

## Decisiones tomadas acá, para no reabrirlas sin querer

- **`minSdk` 26** (Android 8). Cubre prácticamente cualquier teléfono en uso y evita
  compatibilidades viejas. Bajarlo después es barato; subirlo, no.
- **Room** para el almacén local, **WorkManager** para la sincronización en segundo plano.
- **ZXing embebido** para el QR, por no arrastrar Play Services.
- **Sin biblioteca de sincronización de terceros.** La fusión es de este dominio, con reglas
  propias por campo, y una biblioteca genérica traería su modelo de conflictos en vez del
  nuestro.

## Lo que sigue abierto

1. ~~**Hairpinning o DNS partido** para llegar a la instancia desde la red local.~~
   **Resuelto el 2026-09-09**, ver arriba.
2. **Autenticación local en el teléfono.** Con la cuenta viniendo de la instancia, la
   identidad está resuelta, pero falta decidir si la aplicación quiere PIN o biometría
   propios además de la pantalla de bloqueo. Las reviews y las notas son datos personales.
3. **Qué pasa si desaparean.** ¿Los datos locales se borran, se conservan de sólo lectura, o
   se ofrece exportarlos? Con cuenta obligatoria hay una respuesta razonable —conservar y
   permitir volver a aparear— pero conviene decidirla antes de A2.1, no después.
