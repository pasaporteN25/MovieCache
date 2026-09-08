# [A2.0] Cómo llegar a probar Movie Inbox en un teléfono Android

**Fecha:** 2026-09-07. **Tarea:** [A2.0], la primera de [A2] y la que bloquea el resto.
**Contrato del cliente:** `docs/briefs/android-client-v2.md`. **Dirección:** ADR-0005.

## Antes de nada: "probar la app en Android" son dos cosas distintas

Y una de las dos ya se puede hacer hoy.

| | Qué es | Estado |
| --- | --- | --- |
| **Camino A** | La web actual, abierta en el navegador del teléfono | **funciona hoy** |
| **Camino B** | La aplicación Android nativa de [A2] | no existe todavía |

No son sustitutos. El camino A sirve para ver contenido real en una pantalla real esta
semana. El camino B es el producto que decidió ADR-0005: uno que funciona **sin instancia
detrás**, que es justo lo que el navegador nunca va a hacer.

---

## Camino A — la web en el teléfono, hoy

### Qué hace falta

1. **Servir por HTTPS.** Un teléfono en la red de casa no va a entrar a la instancia sin
   eso, y el navegador va a bloquear cosas aunque entre. La receta reproducible —Nginx,
   certificado, hosts privado y público separados, renovación y diagnóstico— está en
   [`docs/deployment.md`](../deployment.md), secciones 1 a 4.
2. **Cuentas creadas de antemano.** No hay registro público: el owner las crea desde
   `Administrar`.

### Qué esperar, porque ya está medido

[MB2] midió la web con emulación real de dispositivo a 390 y 320 px
(`docs/design/mb2-mobile-audit-2026-09-07.md`):

| Superficie | Estado en un teléfono |
| --- | --- |
| Inicio | limpia |
| Colección | sana |
| Ficha | sana |
| Club | limpia |
| **Bandeja** | **rota**: desborda 317 px a 390 y 387 px a 320 |

**No empieces por Bandeja.** Está medida como rota y hacer tropezar a alguien con un
desborde conocido gasta la sesión sin aprender nada nuevo. El arreglo es del frente
visual.

Si además querés probar con otra persona, el protocolo de sesión —las cuatro tareas, qué
anotar y qué **no** anotar— está escrito al final de ese mismo documento.

---

## Camino B — la aplicación nativa

### Estado del entorno, medido en esta máquina el 2026-09-07

```
java -version   ->  1.8.0_471        (hace falta 17 o superior)
gradle -v       ->  command not found
ANDROID_SDK_ROOT / ANDROID_HOME / JAVA_HOME  ->  ninguna definida
proyecto Android en el repositorio           ->  no existe
```

**Ninguna parte de [A2] es ejecutable acá hoy.** Esto no es un detalle que se resuelve al
pasar: es literalmente la tarea [A2.0].

### Dónde corre cada cosa

Conviene fijarlo antes de copiar comandos, porque el proyecto tiene dos entornos:

- **El servidor** corre en Docker sobre Linux (o nativo, ver [`docs/docker.md`](../docker.md)).
  Nada de lo que sigue lo toca.
- **La compilación de Android corre en Windows**, en esta máquina. Todos los comandos de
  abajo son de PowerShell, en el host, no adentro del contenedor.

### Paso 1 — Instalar Android Studio

Es el camino corto y el recomendado: trae **el JDK 17, el Android SDK y Gradle** en una
sola instalación, ya conectados entre sí. Instalar las tres piezas por separado funciona,
pero multiplica las formas de equivocarse en las rutas.

```powershell
winget install --id Google.AndroidStudio --source winget
```

Si `winget` no está disponible, el instalador está en
<https://developer.android.com/studio>.

Al abrirlo por primera vez, el asistente ofrece descargar el SDK. Aceptá el
**Android SDK Platform** más reciente y el **Android SDK Build-Tools**; son los dos que
Gradle necesita para compilar.

### Paso 2 — Comprobar que quedó bien

Cerrá y volvé a abrir la terminal antes de esto: las variables nuevas no aparecen en una
sesión ya abierta.

```powershell
$env:JAVA_HOME; (Get-Command java).Source; java -version
```

Tiene que decir **17 o superior**. Si sigue diciendo `1.8.0_471`, el `java` viejo está
antes en el `PATH`; Android Studio usa su propio JDK igual, así que esto no bloquea, pero
conviene saberlo para no confundirse después.

```powershell
Test-Path "$env:LOCALAPPDATA\Android\Sdk"
```

Tiene que devolver `True`. Esa es la ruta por defecto del SDK en Windows.

### Paso 3 — Crear el proyecto y compilar una vez

El repositorio **no tiene** proyecto Android todavía, así que crearlo es parte de [A2.0].
Desde Android Studio: *New Project* → *Empty Activity* → Kotlin, con el módulo dentro de
este repositorio. El brief v2 fija lo demás (Compose, Hilt con KSP, coroutines).

El criterio de cierre de [A2.0] es exactamente este comando, en verde:

```powershell
.\gradlew.bat assembleDebug
```

Cuando eso compile, [A2.0] está cerrada y [A2.1] se puede empezar.

### Paso 4 — Verlo en un teléfono

Dos opciones, y conviene la segunda para lo que querés:

- **Emulador**, desde el *Device Manager* de Android Studio. Sirve para desarrollar. Ojo:
  para el emulador, la máquina anfitriona es `10.0.2.2`, no `localhost` — por eso el brief
  v2 permite esa excepción de HTTP **sólo** en la variante `debug`.
- **Tu teléfono por USB**: activá *Opciones de desarrollador* y *Depuración por USB*,
  conectalo, y Android Studio lo ofrece como destino. Es lo que de verdad querés probar,
  porque el punto de ADR-0005 es cómo se siente en la mano.

---

## Lo que falta decidir antes de [A2.1], y es tuyo

1. **Quién escribe el cliente.** El reparto vigente pone infraestructura de un lado y lo
   visual del otro. Una aplicación Android es un tercer tipo de trabajo —Kotlin, Compose,
   ciclo de vida de Android— y conviene decidirlo **antes** de A2.1, no durante.
2. **Autenticación local.** Si la aplicación sirve sin servidor, ¿alcanza la pantalla de
   bloqueo del teléfono o querés PIN o biometría propios? Las reviews y las notas son datos
   personales.
3. **Primer arranque.** Crear local o aparear: las dos tienen que funcionar, falta decidir
   cuál se ofrece primero y qué pasa si alguien crea datos y después aparea.

## Por qué el orden es este y no el del brief viejo

El brief v1 arrancaba por el login y dejaba el modo offline fuera de alcance. ADR-0005
decidió lo contrario, así que las entregas se invirtieron: **almacén local primero, juego
después, sincronización al final**.

La consecuencia práctica es buena: **A2.1, A2.2 y A2.3 no necesitan nada del servidor**. Se
puede construir y probar una aplicación que sirve sola antes de escribir una línea de
sincronización. Y [A2.3] es charadas, cuyo backend ya está entregado — o sea que el primer
entregable con valor visible no depende de que la sincronización exista.
