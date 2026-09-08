# Cliente Android v2 — reespecificación de [A2]

> **Reemplazado el 2026-09-07 por `android-client-v3.md`.** El owner decidió que la
> aplicación **requiere una cuenta creada en la web**, lo que convierte al apareamiento en
> la primera entrega en vez de la cuarta, y puso el alta sin conexión como caso de uso
> central. No se borra: su análisis de por qué v1 no servía, el bloqueo de entorno medido y
> las decisiones de seguridad que sobreviven de v1 siguen siendo la base de v3.

**Fecha:** 2026-09-07. **Reemplaza** `docs/briefs/android-client-v1.md`.
**Motivo:** ADR-0005 fijó una dirección que v1 no contempla.

## Por qué v1 no sirve como está

v1 especificaba un **cliente delgado**: su primera entrega era "URL de instancia HTTPS,
login, refresh y token seguro", su segunda leía el catálogo *del servidor*, y el modo
offline estaba **explícitamente fuera de alcance**.

ADR-0005 decidió lo contrario: el teléfono es **autónomo**, funciona sin instancia detrás,
y sincronizar es opcional. Eso no reordena las entregas de v1 — las invierte. Un cliente
que arranca por el login no puede convertirse después en uno que funciona sin servidor;
el almacén local no es una capa que se agrega, es sobre lo que se construye el resto.

## Lo que sí sobrevive de v1

v1 hizo trabajo real de seguridad que sigue valiendo, y se conserva **para cuando exista
sincronización**, no como punto de partida:

- Android nativo con Kotlin y Compose. Confirmado por el owner el 2026-09-07: no es PWA
  ni multiplataforma.
- Hilt con KSP, coroutines y `StateFlow`. El repositorio es el límite de errores: la
  interfaz no recibe excepciones de red ni DTOs.
- Tokens en Android Keystore, nunca en preferencias sin cifrar, logs, analytics, URI,
  portapapeles ni backups.
- HTTPS con certificado válido; la excepción de `http://10.0.2.2` vive sólo en `debug`.
- Ignorar campos opcionales desconocidos, respetar `X-Movie-Inbox-Api-Version` y no usar
  `/api/` histórico, cookies ni `X-Movie-Inbox-Token`.

## Bloqueo de entorno, verificado

Medido en la máquina de trabajo el **2026-09-07**, igual que en la nota del 2026-09-02:

| | Estado | Necesario |
| --- | --- | --- |
| JDK | **1.8.0_471** | 17 o superior |
| Gradle | no encontrado | requerido |
| Android SDK | sin `ANDROID_SDK_ROOT` ni `ANDROID_HOME` | requerido |
| Proyecto Android | no existe en el repo | — |

**Ninguna parte de [A2] es ejecutable acá hoy.** Esto no es un detalle de configuración
que se resuelve al pasar: es la primera tarea, y hasta que esté hecha el resto es papel.

## El orden nuevo

Invertido respecto de v1: almacén local, después juego, después sincronización.

| Parte | Entrega | Depende de |
| --- | --- | --- |
| **A2.0** | Entorno: JDK 17+, Android SDK, Gradle Wrapper y un `assembleDebug` que compile | — |
| **A2.1** | Proyecto Android y **almacén local**. Funciona sin red y sin cuenta | A2.0 |
| **A2.2** | Leer y editar en local: explorar, buscar, abrir una obra, estado personal | A2.1 |
| **A2.3** | **Charadas**: mazo, categorías y temporizador, sin red | A2.1 |
| **A2.4** | Apareamiento por QR con una instancia | A2.1 + **[A1.4]** |
| **A2.5** | Sincronización con fusión a tres bandas y resolución de conflictos | A2.4 |
| **A2.6** | Imágenes: miniatura local y portada completa en segundo plano | A2.2 |

**A2.1, A2.2 y A2.3 no necesitan nada del servidor.** Es la consecuencia práctica más útil
de ADR-0005: se puede construir y probar una aplicación que sirve sola antes de escribir
una línea de sincronización.

### A2.1 — Almacén local

Guarda la **capa de obra y la capa personal**, con la forma del contrato portable
`catalog.schema.json` v9: identidad, títulos, año, tipo, IDs externos, géneros, duración,
imágenes, y `status`, `watched_at`, `rating`, `review`.

No guarda la **capa operativa** —rutas, archivos, bibliotecas, Scanner, curaduría—, y no
sólo por privacidad: un teléfono no tiene los discos del usuario, así que esos campos no
significan nada ahí. `en_catalogo` viaja como lectura; el teléfono no puede afirmarlo.

Una cuenta por instalación (ADR-0005). El primer arranque tiene que funcionar **sin
cuenta y sin instancia**: crear un catálogo local es una entrada legítima, no un modo
degradado.

La auditoría [MB2] respalda el recorte desde otro ángulo: Bandeja —Scanner y Curaduría—
es la única superficie con desborde real en un teléfono, y es exactamente la capa que este
cliente no lleva.

### A2.2 — Leer y editar, con borradores que no se pierden

Explorar, buscar localmente, abrir una obra y editar estado, fecha, puntaje y review.
Todo sin red.

Dar de alta sin conexión produce un **borrador pendiente de enriquecimiento**, y ese
borrador **no expira** — a diferencia de los de importación, que mueren a las 48 horas.
Un borrador offline puede esperar días a que haya red; hacerlo expirar sería exactamente
el defecto que la decisión vino a evitar. Sólo lo cierra la persona.

### A2.3 — Charadas

Primer entregable con valor visible, y el que valida el almacén local: usa datos de sólo
lectura, no necesita sincronización y funciona sin red.

El backend ya está entregado ([G2]) y el contrato en `docs/briefs/charades-v1.md`. El
generador es deliberadamente portable —FNV-1a más un LCG documentado— para que el cliente
produzca **el mismo mazo** que el servidor. Esa reimplementación en Kotlin es parte de
esta entrega, con pruebas que comparen contra vectores del servidor.

La dificultad **no se calcula en el teléfono**: sale del índice IMDb de ~1,1 GB y viaja
resuelta como un campo por obra.

### A2.4 y A2.5 — Apareamiento y sincronización

El QR lleva **origen, identidad técnica y un token de un solo uso**; no lleva el catálogo,
que no entra ni cerca en los ~2953 bytes de un QR. La transferencia va por HTTPS en la red
local.

La convergencia es la **fusión a tres bandas** de ADR-0005: contra la base de la última
sincronización, se aplica lo que cambió de un solo lado, converge lo que cambió igual en
los dos, y **decide la persona** cuando ambos cambiaron distinto. Por campo. La
sincronización **nunca borra**.

A2.5 incluye una interfaz de conflictos, que es trabajo real y no un diálogo de dos
botones.

## Prerrequisito de servidor: [A1.4]

Bloquea A2.4 y A2.5, **no** A2.1–A2.3. Es trabajo de servidor, o sea del frente de
infraestructura y no del cliente. ADR-0005 midió los tres huecos:

1. El payload de dispositivo **no tiene ninguna marca de tiempo**.
2. El id opaco **no es una clave durable**: se deriva con el `api_token` como secreto HMAC
   más la ruta del archivo de origen, así que rotar el token o mover el catálogo re-clavea
   todas las obras.
3. **No hay feed de cambios**, sólo paginación sobre todo el catálogo.

Los tres se resuelven de forma **aditiva** —campos y rutas nuevas, sin cambiar el
significado de ninguno existente—, así que caben en v1 según la propia regla de versionado
de ADR-0003.

## Qué queda abierto

1. **Quién escribe el cliente.** El reparto vigente pone la infraestructura de un lado y
   lo visual del otro; una aplicación Android es un tercer tipo de trabajo y conviene
   decidirlo antes de A2.1, no durante.
2. **Autenticación local.** Si la aplicación sirve sin servidor, ¿alcanza la pantalla de
   bloqueo del teléfono o quiere PIN/biometría propia? Las reviews y notas son datos
   personales. Abierta desde ADR-0005.
3. **Primer arranque.** Crear local o aparear: ambas deben funcionar, falta decidir cuál
   se ofrece primero y qué pasa si alguien crea datos y después aparea.
