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
New-Item -ItemType Directory -Force .\backups, .\media, .\imports, .\secrets
Copy-Item .\scripts\catalogv4.json .\imports\catalogv4.json
```

Editar `.env` y configurar al menos:

```dotenv
MOVIE_INBOX_PUBLIC_ORIGIN=http://localhost:8765
# Primera unidad o arbol multimedia.
MOVIE_INBOX_MEDIA_PATH=D:/Peliculas
MOVIE_INBOX_IMPORT_PATH=./imports
MOVIE_INBOX_BACKUP_PATH=./backups
MOVIE_INBOX_BACKUP_RETENTION_DAYS=14
MOVIE_INBOX_OWNER_USERNAME=lucas
MOVIE_INBOX_IMAGE_CACHE_MB=512
MOVIE_INBOX_IMAGE_WARM_MODE=after-access
MOVIE_INBOX_IMAGE_WARM_INTERVAL_SECONDS=3
```

Crear `secrets/owner-password.txt` con una contrasena inicial larga. El archivo queda
ignorado por Git. En Linux debe ser legible por el UID `10001` del contenedor y no por
otros usuarios:

```bash
mkdir -p backups imports media secrets
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

## Probar una biblioteca real

Primero confirmar desde el contenedor que el mount existe y contiene videos. Este
comando solo cuenta extensiones conocidas y no modifica nada:

```bash
docker compose exec -T movie-inbox python -c '
from pathlib import Path
from movie_inbox.infrastructure.library_scanner import DEFAULT_EXTENSIONS
root = Path("/media/library/disco1")
print("root:", root)
print("exists:", root.is_dir())
print("videos:", sum(1 for path in root.rglob("*") if path.is_file() and path.suffix.lower() in DEFAULT_EXTENSIONS))
'
```

Despues, como owner:

1. Abrir `Administrar > Bibliotecas` y crear una biblioteca.
2. Usar un nombre reconocible, por ejemplo `Peliculas principal`.
3. Elegir `/media/library/disco1` o una subcarpeta interna; nunca la ruta del host.
4. Dejar la frecuencia en `Manual` durante la prueba.
5. Ejecutar `Probar recorrido` y esperar a que termine.
6. Revisar descubiertos, coincidencias, nuevos, ambiguos y errores de lectura.
7. Ejecutar `Aplicar inventario` solamente cuando el recorrido de prueba sea coherente.
8. Abrir `Bandeja > Scanner` para revisar los casos nuevos o ambiguos ya inventariados.

`Probar recorrido` guarda el reporte, pero no disponibilidad ni archivos del inventario.
`Aplicar inventario` vuelve a leer el directorio y persiste el inventario compartido.
No modifica `status`, fecha de vista, rating o review. Un disco ausente, un error de
permisos o una desaparicion masiva conservan el ultimo inventario valido.

El scanner administrado vincula automaticamente las coincidencias fuertes y deja los
titulos nuevos o dudosos en la Bandeja. Elegir una candidata solo confirma la identidad
fisica. `Agregar obra y vincular` aparece solamente cuando no hay candidatas y comprueba
de nuevo el catalogo personal antes de crear una obra pendiente. Un titulo exacto con
otro ano tambien se considera una coincidencia revisable: el Scanner bloquea la nueva
ficha y permite vincular la existente. Si se trata realmente de otra obra, se agrega
primero desde el buscador general y luego se aplica un nuevo recorrido. La disponibilidad
proviene del inventario compartido; no se marcan vistas ni se modifican rating o review.

### Reconciliar un inventario heredado

Los contadores de una biblioteca separan cuatro estados: `Archivos` es el total fisico,
`Vinculados` tiene identidad confirmada, `Comparar` posee candidatas ambiguas y `Nuevos`
no encontro ninguna obra candidata. Las dos ultimas categorias aparecen en
`Bandeja > Scanner`; no deben interpretarse juntas como errores de matching.

Para instalaciones creadas desde el antiguo dump de archivos, un recorrido puede
reconciliar automaticamente una coincidencia con ano ausente solamente cuando el titulo
normalizado es exacto y unico, y la entrada previa conserva evidencia de inventario local.
Titulos repetidos, anos incompatibles y entradas sin procedencia fisica permanecen para
revision manual. Despues de actualizar, ejecutar primero `Probar cambios` y aplicar el
inventario solamente si la nueva distribucion es coherente. El inventario usa ruta y
huella, por lo que repetir el recorrido no duplica archivos sin cambios.

Las decisiones y pendientes aplicados viven en `instance.db` y sobreviven a una
actualizacion o recreacion normal del contenedor. Un `dry_run` conserva solamente el
reporte; el inventario y la cola se escriben al usar `Aplicar inventario`. Nunca usar
`docker compose down --volumes` durante esta recuperacion.

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

## Backups automaticos

El servicio `movie-inbox-backup` monta el volumen persistente en modo de solo lectura y
escribe fuera de Docker. Cada ejecucion crea un `.tar.gz` atomico, lo vuelve a leer,
comprueba que incluya `movie-inbox.db` e `instance.db` y publica un checksum SHA-256.
Conserva catalogos de miembros, cuentas, privacidad, colecciones e inventario. El cache
de portadas se omite porque es reproducible.

El proceso de mantenimiento conserva `cap_drop: ALL` y recibe solamente
`DAC_READ_SEARCH`. Esa capacidad es necesaria para incluir archivos privados `0600`
creados por el usuario interno de Movie Inbox, como el historial de curacion, sin dar
escritura sobre el volumen de datos, que permanece montado en modo de solo lectura. El
servicio tampoco tiene red y su filesystem raiz sigue siendo de solo lectura.

Este archivo cubre todos los datos administrados por Movie Inbox, pero no el despliegue
del host. `.env`, `compose.override.yaml` y `secrets/owner-password.txt` deben tener una
copia protegida separada; tampoco se copian los videos montados en modo de solo lectura.

En OMV o Debian, configurar una ruta de otro filesystem cuando sea posible:

```dotenv
MOVIE_INBOX_BACKUP_PATH=/srv/backups/movie-inbox
MOVIE_INBOX_BACKUP_RETENTION_DAYS=14
```

La variable debe vivir en `/opt/movie-inbox/.env`; cambiar solamente la documentacion o
crear el directorio no modifica la interpolacion de Compose. El wrapper resuelve la ruta
efectiva, la muestra y la crea con permisos restrictivos antes de detener la aplicacion.
Prepararla manualmente sigue siendo recomendable para comprobar el filesystem elegido:

```bash
mkdir -p /srv/backups/movie-inbox
chmod 700 /srv/backups/movie-inbox
cd /opt/movie-inbox
docker compose config --quiet
docker compose config | grep -A2 -B2 '/backups'
```

El bind conserva `create_host_path: false`: una ejecucion directa de
`docker compose run movie-inbox-backup` requiere que la ruta ya exista. Usar
`scripts/docker-backup.sh` evita esa diferencia y valida que el destino sea escribible.

### Prueba manual

El wrapper usa `flock`, detiene brevemente la aplicacion, crea el backup, vuelve a
iniciarla y espera su healthcheck. Si el backup falla tambien intenta restaurar el
servicio:

```bash
cd /opt/movie-inbox
bash scripts/docker-backup.sh
ls -lh /srv/backups/movie-inbox
```

El comando no recibe rutas ni comodines: no agregar `*` al final. Para inspeccionar el
mount efectivo del servicio, incluido su perfil de mantenimiento:

```bash
docker compose --profile maintenance config | grep -A3 -B3 '/backups'
```

Verificar nuevamente cualquier archivo sin extraerlo:

```bash
archive=$(find /srv/backups/movie-inbox -maxdepth 1 -name '*.tar.gz' -printf '%T@ %p\n' \
  | sort -nr | head -n1 | cut -d' ' -f2-)
docker compose run --rm --no-deps movie-inbox-backup \
  backup verify "/backups/$(basename "$archive")"
```

`docker compose run` reemplaza el `command` de creacion para esa ejecucion y conserva
el entrypoint `movie-inbox` de la imagen.

### Programacion diaria

Instalar las unidades de ejemplo y revisar `OnCalendar` si se prefiere otro horario:

```bash
cd /opt/movie-inbox
install -m 0644 deploy/movie-inbox-backup.service.example \
  /etc/systemd/system/movie-inbox-backup.service
install -m 0644 deploy/movie-inbox-backup.timer.example \
  /etc/systemd/system/movie-inbox-backup.timer
systemctl daemon-reload
systemctl enable --now movie-inbox-backup.timer
systemctl start movie-inbox-backup.service
systemctl status movie-inbox-backup.service --no-pager
systemctl list-timers movie-inbox-backup.timer
```

Consultar ejecuciones posteriores:

```bash
journalctl -u movie-inbox-backup.service -n 100 --no-pager
```

El timer usa `Persistent=true`: si el servidor estaba apagado a las 03:30, systemd
ejecuta la tarea pendiente al volver. Los archivos completos mas antiguos que
`MOVIE_INBOX_BACKUP_RETENTION_DAYS` se eliminan junto con su checksum.

La unidad se ejecuta como root porque controla Docker; acceso al socket de Docker ya
equivale a privilegios de administrador. El directorio de backups debe permanecer con
modo `0700` y las unidades no deben aceptar parametros provenientes de la web.

### Alcance y restauracion

La descarga JSON de `Administrar > Base de datos` sigue siendo complementaria: permite
recuperar las obras de ese usuario, pero no cuentas ni estado de instancia. Para probar
un backup completo, primero validar el checksum y extraerlo en una carpeta temporal o
en otro proyecto Compose; no sobrescribir el volumen activo como primera prueba:

```bash
cd /srv/backups/movie-inbox
archive=$(find . -maxdepth 1 -name '*.tar.gz' -printf '%T@ %p\n' \
  | sort -nr | head -n1 | cut -d' ' -f2-)
sha256sum --check "$(basename "$archive").sha256"
mkdir -p /tmp/movie-inbox-restore-test
tar -xzf "$archive" -C /tmp/movie-inbox-restore-test
find /tmp/movie-inbox-restore-test/movie-inbox -maxdepth 2 \
  \( -name 'movie-inbox.db' -o -name 'instance.db' \) -ls
```

Al menos una copia debe vivir fuera del volumen y, preferentemente, fuera del mismo
disco fisico. Una restauracion destructiva sigue siendo una operacion manual para evitar
reemplazar por accidente una instancia sana.

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
