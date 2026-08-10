# Despliegue con Docker Compose

Este es el primer despliegue soportado de Movie Inbox con Docker. Crea una instancia
nueva dentro del contenedor, importa el catalogo existente a SQLite y conserva todo el
estado en un volumen nombrado. No relocaliza todavia un `instance.db` creado fuera del
contenedor porque esa base guarda rutas absolutas de catalogos personales.

## Que configura cada capa

- `.env` define rutas del host, puerto, origen publico y nombre del owner.
- `compose.yaml` fija las rutas internas, el volumen persistente y los limites de
  seguridad.
- El secret `owner_password` entrega la credencial inicial como archivo, nunca como
  variable de entorno.
- La interfaz administra nombres, subrutas y frecuencias solamente dentro de los
  slots `/media/library/disco1` a `/media/library/disco8`.

El proceso corre sin privilegios, no recibe capabilities Linux, usa un filesystem raiz
de solo lectura y monta la biblioteca fisica como `read_only`. Solamente
`/var/lib/movie-inbox` es persistente y escribible.

## Preparacion

Se requiere Docker Engine o Docker Desktop con Docker Compose v2.

En PowerShell, desde la raiz del repositorio:

```powershell
Copy-Item .env.example .env
New-Item -ItemType Directory -Force .\media, .\imports, .\secrets
Copy-Item .\scripts\catalogv4.json .\imports\catalogv4.json
```

Editar `.env` y configurar al menos:

```dotenv
MOVIE_INBOX_PUBLIC_ORIGIN=http://localhost:8765
# Primera unidad o arbol multimedia.
MOVIE_INBOX_MEDIA_PATH=D:/Peliculas
MOVIE_INBOX_IMPORT_PATH=./imports
MOVIE_INBOX_OWNER_USERNAME=lucas
MOVIE_INBOX_IMAGE_CACHE_MB=512
MOVIE_INBOX_IMAGE_WARM_MODE=after-access
MOVIE_INBOX_IMAGE_WARM_INTERVAL_SECONDS=3
```

Crear `secrets/owner-password.txt` con una contrasena inicial larga. El archivo queda
ignorado por Git. En Linux debe ser legible por el UID `10001` del contenedor y no por
otros usuarios:

```bash
mkdir -p imports media secrets
cp .env.example .env
printf '%s' 'CAMBIAR_ESTA_CONTRASENA' > secrets/owner-password.txt
sudo chown 10001:10001 secrets/owner-password.txt
sudo chmod 600 secrets/owner-password.txt
```

No se debe guardar la contrasena real dentro de `.env` ni de `compose.yaml`.

## Cache progresivo de portadas

El volumen `movie-inbox-data` conserva `/var/lib/movie-inbox/image-cache` al reiniciar o
recrear el contenedor. Despues de que un usuario abre su catalogo, un unico worker del
servidor descarga una portada cada tres segundos. Las portadas que la pantalla solicita
en ese momento tienen prioridad; la respuesta del catalogo no espera a la cola. Las
colecciones y catalogos compartidos se incorporan solamente cuando alguien los abre y
las URLs repetidas se descargan una sola vez para toda la instancia.

El owner puede consultar el estado en `Administrar > Base de datos`. Para detener el
trabajo de fondo sin perder ni deshabilitar el cache existente:

```dotenv
MOVIE_INBOX_IMAGE_WARM_MODE=off
```

Cambiar estas variables requiere recrear el contenedor con `docker compose up -d`. No
usar `docker compose down --volumes`: ese comando elimina tambien bases, catalogos y
portadas persistentes.

## Importacion inicial

Construir la imagen:

```powershell
docker compose build
```

Importar el JSON una sola vez antes del primer `up`:

```powershell
docker compose run --rm movie-inbox db import `
  /imports/catalogv4.json `
  --db /var/lib/movie-inbox/movie-inbox.db
```

El importador verifica el documento canonico completo. Si la base ya existe, rechaza el
reemplazo salvo que se solicite `--replace`; no usar esa opcion durante una instalacion
normal.

## Inicio y operacion

```powershell
docker compose up -d
docker compose ps
docker compose logs -f movie-inbox
```

La aplicacion queda disponible en `http://localhost:8765`. El inicio cotidiano se reduce
a `docker compose up -d`; las rutas y opciones permanecen en `.env` y Compose.

En `Administrar > Bibliotecas`, registrar `/media/library/disco1`, no la ruta
`D:/Peliculas` del host. Compose es la unica capa que conoce la ruta fisica externa.

## Varias unidades en OMV o Debian

La imagen contiene ocho slots de montaje precreados. Esto permite conservar el
filesystem raiz de solo lectura: Docker no necesita crear directorios al iniciar el
contenedor. Copiar el ejemplo local, que queda ignorado por Git:

```bash
cp compose.omv.example.yaml compose.override.yaml
nano compose.override.yaml
docker compose config
```

Cada `source` debe ser una ruta real del host y cada `target` debe usar un slot distinto
entre `/media/library/disco1` y `/media/library/disco8`. La entrada `disco1` del override
reemplaza el mount configurado por `MOVIE_INBOX_MEDIA_PATH`; las restantes se agregan.
Compose carga el override automaticamente.

No usar symlinks como raices administradas. El scanner no sigue symlinks y rechaza una
raiz que lo sea. En OMV se recomienda usar la ruta estable del shared folder o resolverla
antes de configurar el source:

```bash
realpath /data/videos
findmnt /data/videos
```

Los nombres amigables se asignan en `Administrar > Bibliotecas`; no es necesario cambiar
el nombre interno del slot.

Para detener sin perder datos:

```powershell
docker compose down
```

No agregar `--volumes`: el volumen `movie-inbox-data` contiene el catalogo, usuarios,
colecciones, inventario y configuracion de bibliotecas.

## Nginx y acceso por red

Por defecto Compose publica `127.0.0.1:8765`, de modo que solamente el host y un proxy
local pueden conectarse. Para Nginx, mantener ese bind y cambiar:

```dotenv
MOVIE_INBOX_PUBLIC_ORIGIN=https://peliculas.example.com
MOVIE_INBOX_FORWARDED_ALLOW_IPS=IP_EXACTA_DEL_PROXY
```

No usar `*` para proxies confiables. Nginx termina HTTPS y reenvia al puerto loopback;
no debe servir el volumen de datos ni el directorio de imports.

Para acceso directo dentro de una LAN sin Nginx se puede cambiar
`MOVIE_INBOX_BIND_ADDRESS`, pero `MOVIE_INBOX_PUBLIC_ORIGIN` debe coincidir exactamente
con la URL usada por el navegador.

## Backup

Exportar un backup portable del catalogo:

```powershell
docker compose exec -T movie-inbox movie-inbox db export `
  /var/lib/movie-inbox/movie-inbox.db `
  --json /var/lib/movie-inbox/catalog-backup.json
docker compose cp `
  movie-inbox:/var/lib/movie-inbox/catalog-backup.json `
  .\catalog-backup.json
```

Para respaldar tambien usuarios, privacidad, colecciones y bibliotecas administradas,
detener primero el servicio y copiar el volumen completo:

```powershell
docker compose stop movie-inbox
docker compose cp movie-inbox:/var/lib/movie-inbox/. .\instance-backup
docker compose start movie-inbox
```

En OMV o Debian puede conservarse cada snapshot fuera del volumen de Docker:

```bash
cd /opt/movie-inbox
backup_dir="/srv/backups/movie-inbox/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
docker compose stop movie-inbox
docker compose cp movie-inbox:/var/lib/movie-inbox/. "$backup_dir/"
docker compose start movie-inbox
echo "Backup completo: $backup_dir"
```

Este snapshot contiene `movie-inbox.db`, `instance.db`, los catalogos de miembros,
colecciones, privacidad, configuracion del scanner y cache. La descarga JSON disponible
en `Administrar > Base de datos` es complementaria: permite restaurar las obras del
usuario que la genera, pero no reemplaza este respaldo completo de la instancia.

La copia completa debe guardarse fuera del host o volumen principal. Una restauracion se
ensaya primero sobre un proyecto Compose separado.

## Actualizacion

```powershell
git pull --ff-only
docker compose build --pull
docker compose up -d
docker compose ps
```

Compose recrea el contenedor y reutiliza el volumen. Las migraciones de SQLite se
ejecutan al abrir las bases; nunca se debe reemplazar el volumen por el filesystem de la
imagen. Una actualizacion normal no borra datos, pero antes de cambiar de version se
recomienda crear el snapshot completo anterior y comprobar que el directorio contiene
al menos `movie-inbox.db` e `instance.db`. No usar `docker compose down --volumes`.

## Limites de este incremento

- Admite hasta ocho unidades mediante slots de solo lectura; agregar mas requiere crear
  nuevos mountpoints en la imagen.
- No migra usuarios ni paths absolutos desde un `instance.db` de Windows.
- No incluye Nginx dentro de Compose; puede usarse el proxy del host documentado en
  `deployment.md`.
- No publica imagenes en un registry ni automatiza el deploy.
