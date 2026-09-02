# Despliegue en servidor

## Topologia propuesta

```text
Git push / pull request
        |
        v
GitHub Actions: compile + tests
        |
        v
revision aprobada en el servidor
        |
        v
systemd -> Uvicorn/FastAPI + login -> 127.0.0.1:8765
        |
        v
Nginx -> HTTPS -> navegador

/opt/movie-inbox            codigo del checkout
/var/lib/movie-inbox        SQLite y cache persistentes
/var/backups/movie-inbox    exportaciones JSON
```

Nginx debe hacer proxy al proceso HTTP. No debe apuntar al repo, publicar la base SQLite ni servir el directorio de backups.

## CI y despliegue son etapas distintas

El workflow de GitHub prueba cada push a `master` y cada pull request. Tambien puede ejecutarse la misma validacion en cualquier host con `bash scripts/check.sh`. CI no necesita acceder al servidor ni a los catalogos.

El primer despliegue puede ser manual y auditable:

1. Actualizar el checkout a un commit cuyo workflow haya pasado.
2. Crear un entorno virtual e instalar con `python -m pip install -e .`.
3. Importar el JSON inicial a una ruta persistente con `movie-inbox db import`.
4. Crear el owner y adoptar ese catalogo con `movie-inbox account bootstrap`.
5. Ejecutar el proceso bajo un usuario sin privilegios mediante `systemd`.
6. Exportar JSON periodicamente hacia un volumen de backups distinto.

Una automatizacion posterior puede hacer esos pasos al publicar una version. No es necesario instalar un runner de CI en el servidor.

Antes de promover una candidata, ejecutar tambien el gate de comportamiento de
[release-checklist.md](release-checklist.md). Ese recorrido valida el scanner contra una
ruta descartable y confirma que una unidad ausente o ilegible no retire disponibilidad
ya verificada.

Una preparacion minima del host seria:

```bash
sudo useradd --system --home /var/lib/movie-inbox --shell /usr/sbin/nologin movie-inbox
sudo install -d -o movie-inbox -g movie-inbox /var/lib/movie-inbox /var/lib/movie-inbox/member-catalogs /var/backups/movie-inbox
cd /opt/movie-inbox
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

El checkout puede pertenecer al usuario de despliegue y ser solamente legible para `movie-inbox`. La base y el cache si deben pertenecer al usuario del servicio.

El backup debe incluir `instance.db`, el catalogo del owner y todo `--member-catalog-dir`, incluso los archivos que pertenezcan a cuentas archivadas. La base de instancia conserva la relacion necesaria para restaurarlos; una exportacion JSON aislada no incluye usuarios, privacidad ni archivo de miembros.

Antes de activar `systemd`, crear el owner desde una terminal:

```bash
sudo -u movie-inbox /opt/movie-inbox/.venv/bin/movie-inbox account bootstrap \
  --instance-db /var/lib/movie-inbox/instance.db \
  --catalog /var/lib/movie-inbox/movie-inbox.db \
  --username lucas
```

La contrasena se solicita sin eco. Para automatizacion se admite `--password-file`, usando un archivo temporal legible solamente por `movie-inbox`.

## Ejecutar la aplicacion

El proceso de aplicacion debe seguir escuchando solamente en loopback. `--public-origin` habilita ese origen exacto para validacion de `Host` y escrituras del navegador; no cambia la direccion de escucha:

```bash
/opt/movie-inbox/.venv/bin/movie-inbox serve \
  /var/lib/movie-inbox/movie-inbox.db \
  --instance-db /var/lib/movie-inbox/instance.db \
  --member-catalog-dir /var/lib/movie-inbox/member-catalogs \
  --host 127.0.0.1 \
  --port 8765 \
  --public-origin https://inbox.example.com \
  --public-presentation-origin https://cartelera.example.com \
  --forwarded-allow-ips 127.0.0.1 \
  --image-cache-dir /var/lib/movie-inbox/image-cache \
  --image-cache-total-mb 512 \
  --image-cache-warm-mode after-access \
  --image-cache-warm-interval-seconds 3 \
  --library-root /srv/media/peliculas \
  --no-open
```

La app usa un solo worker de Uvicorn. SQLite serializa escrituras, el cache de busquedas vive en memoria y la cola progresiva de portadas se coordina dentro de ese proceso; agregar workers antes de medir carga sumaria contencion, descargas duplicadas y estados divergentes sin aportar valor para un catalogo personal.

Cada `--library-root` habilita unicamente ese arbol para el scanner administrado. El
usuario `movie-inbox` necesita lectura y traversal sobre esas carpetas, pero no
escritura. No se recomienda habilitar `/`, `/home` ni un punto de montaje que contenga
datos ajenos a la biblioteca. Las rutas registradas y los reportes de archivos viven en
`instance.db` y solamente se entregan a endpoints de owner.

El proxy de imagenes acepta solamente los hosts conocidos de Wikimedia, IMDb y FilmAffinity. Si una fuente confiable nueva usa otro dominio, se agrega con `--image-host host.example`; no se recomienda permitir dominios aportados por usuarios. El cache se puede inspeccionar y mantener sin detener el servicio con `movie-inbox cache info|prune|clear --dir /var/lib/movie-inbox/image-cache`.

`--forwarded-allow-ips` nunca debe configurarse con `*` si Uvicorn acepta conexiones que no provienen exclusivamente del proxy. Con Nginx local alcanza `127.0.0.1`.

## systemd

La plantilla [movie-inbox.service.example](../deploy/movie-inbox.service.example) ejecuta el servicio con un usuario sin privilegios, reinicio ante fallos y acceso de escritura limitado a `/var/lib/movie-inbox`.

```bash
sudo cp deploy/movie-inbox.service.example /etc/systemd/system/movie-inbox.service
sudo systemctl daemon-reload
sudo systemctl enable --now movie-inbox
curl http://127.0.0.1:8765/healthz
sudo systemctl status movie-inbox
```

Antes de iniciarla hay que reemplazar dominio, rutas y usuario en la unidad. El healthcheck no devuelve rutas ni datos del catalogo.

## Nginx, HTTPS y acceso por Internet

La configuración soportada usa **dos nombres HTTPS** que terminan en el mismo Nginx
local y un solo proceso Movie Inbox en loopback:

| Host | Expone | No expone |
| --- | --- | --- |
| `inbox.example.com` | Login, aplicación autenticada, API privada e imágenes cacheadas | `/p/` y `/public/` |
| `cartelera.example.com` | Solo `/p/{capacidad}`, `/public/v1/...` y los tres assets de la cartelera | Login, `/api/`, Club, catálogo, imágenes cacheadas y el bundle general |

El segundo host no es una forma de iniciar sesión alternativa: su única finalidad es
mantener la capacidad pública fuera del origen que contiene la cookie privada. Ambos
nombres deben resolver hacia el servidor y aceptar TCP 80/443. HTTP-01 de Let's
Encrypt usa estrictamente el puerto 80; si no se puede abrir, hay que optar por DNS-01,
no desviar el servicio a un puerto no estándar. [Documentación de desafíos de Let's
Encrypt](https://letsencrypt.org/docs/challenge-types/).

### 1. Preparar el proceso y el DNS

Usar los nombres reales en la unidad y reiniciar antes de poner Nginx en producción:

```bash
sudoedit /etc/systemd/system/movie-inbox.service
sudo systemctl daemon-reload
sudo systemctl restart movie-inbox
curl --fail http://127.0.0.1:8765/healthz
```

La línea `ExecStart` debe conservar `--host 127.0.0.1` y declarar ambos orígenes:

```text
--public-origin https://inbox.example.com \
--public-presentation-origin https://cartelera.example.com \
--forwarded-allow-ips 127.0.0.1
```

El segundo argumento amplía solamente la allowlist de `Host` de la app para que Nginx
pueda entregarle la cartelera; login, CSRF y las escrituras siguen aceptando únicamente
`--public-origin`. Nunca usar `*` en `--forwarded-allow-ips`: Nginx sobrescribe
`X-Forwarded-For` con la IP que recibió y Uvicorn confía solo en el proxy loopback.

### 2. Emitir el certificado sin publicar la app HTTP

En Debian/Ubuntu instalar Nginx, Certbot y crear un webroot que no pertenece al repo ni
a la aplicación:

```bash
sudo apt install nginx certbot
sudo install -d -o root -g root -m 0755 /var/lib/letsencrypt
sudo cp deploy/nginx.movie-inbox.http-bootstrap.conf.example \
  /etc/nginx/sites-available/movie-inbox
sudo ln -s /etc/nginx/sites-available/movie-inbox \
  /etc/nginx/sites-enabled/movie-inbox
sudo nginx -t
sudo systemctl reload nginx
```

Reemplazar los dos dominios de la plantilla antes de copiarla. El bootstrap responde
solo a `/.well-known/acme-challenge/` y devuelve `404` para todo lo demás, por lo que
no deja una app HTTP expuesta mientras se emite el primer certificado.

```bash
sudo certbot certonly --webroot -w /var/lib/letsencrypt \
  --cert-name movie-inbox \
  -d inbox.example.com -d cartelera.example.com
```

El nombre `movie-inbox` es el directorio del certificado compartido por los dos SAN,
no un hostname. Verificar los nombres que Certbot muestra antes de continuar.

### 3. Activar el proxy de dos hosts

Instalar [nginx.movie-inbox.conf.example](../deploy/nginx.movie-inbox.conf.example),
reemplazando los dominios de ejemplo, y validar antes de recargar:

```bash
sudo cp deploy/nginx.movie-inbox.conf.example /etc/nginx/sites-available/movie-inbox
sudo nginx -t
sudo systemctl reload nginx
```

La plantilla conserva `Host`, `X-Forwarded-Host` y el esquema HTTPS para el proceso
local. Sobrescribe —no concatena— `X-Forwarded-For` con `$remote_addr`, para que un
cliente de Internet no pueda falsificar su IP ante los límites de login o cartelera.
Nginx documenta `proxy_set_header` y las cabeceras por defecto en su [módulo de
proxy](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).

Las rutas de capacidad tienen `access_log off` en ambos hosts; una URL compartida no
termina en el access log de Nginx. La cartelera tampoco acepta el bundle general: solo
sus CSS y JavaScript mínimos. Actualmente Movie Inbox no usa WebSocket, por lo que la
plantilla no reenvía `Upgrade` ni `Connection: upgrade`; agregarlo sin una función que
lo requiera ensancharía la superficie innecesariamente.

La cabecera HSTS queda comentada deliberadamente. Habilitarla solo después de comprobar
ambos nombres por HTTPS y de decidir que no se volverá a servir HTTP; para revertir una
política ya publicada se envía temporalmente `max-age=0` desde HTTPS.

### 4. Renovar y diagnosticar

Crear un hook de despliegue para que Nginx relea certificados renovados:

```bash
sudo install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
printf '%s\n' '#!/bin/sh' 'systemctl reload nginx' | \
  sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx >/dev/null
sudo chmod 700 /etc/letsencrypt/renewal-hooks/deploy/reload-nginx
sudo certbot renew --dry-run
```

Certbot ejecuta los deploy hooks solamente cuando una renovación se completa; el
`--dry-run` confirma el recorrido sin consumir el certificado real. Consultar el timer
instalado por la distribución (`systemctl list-timers | grep certbot`) y sus registros
si una renovación falla. [Documentación de Certbot](https://eff-certbot.readthedocs.io/).

Después de cada cambio, estas comprobaciones deben pasar:

```bash
sudo ss -ltnp | grep 8765                 # solo 127.0.0.1:8765 o [::1]:8765
curl --fail https://inbox.example.com/healthz
curl -I https://cartelera.example.com/api/items       # 404 de Nginx
curl -I https://inbox.example.com/p/capacidad-falsa   # 404 de Nginx
curl -I https://cartelera.example.com/p/capacidad-falsa  # 404 uniforme de la app
sudo nginx -T
```

No copiar una capacidad real en una terminal compartida ni en un ticket: aunque Nginx
no la registra, el historial de shell podría conservarla. El diagnóstico de una URL
real se realiza creando una capacidad temporal y revocándola inmediatamente después.

Movie Inbox autentica la cuenta antes de entregar el visor privado. La cookie de sesión
es `HttpOnly`, `SameSite=Strict` y `Secure` bajo el origen HTTPS; el token opaco nunca
aparece en la URL y SQLite guarda solamente su hash. El token anti-CSRF, la validación
de `Origin` y la sesión se exigen juntos. Uvicorn no registra access logs y Nginx omite
el log del proxy de imágenes para no guardar URLs del catálogo.

## Checklist de publicacion

- Los checks pasan sobre el commit desplegado.
- El proceso corre como usuario sin privilegios.
- Catalogo, `instance.db`, cache y backups estan fuera de `/opt/movie-inbox`.
- El cache tiene un limite total y la allowlist contiene solamente proveedores de imagenes confiables.
- Nginx es el unico proceso publico y Uvicorn escucha en `127.0.0.1`.
- `--public-origin` coincide exactamente con el origen HTTPS del navegador.
- `--forwarded-allow-ips` contiene solamente la direccion del proxy.
- El owner fue creado y el login funciona a traves del origen HTTPS.
- `instance.db` no se publica y tiene un backup protegido separado.
- El timer de backup esta activo, su ultima ejecucion termino correctamente y el
  archivo mas reciente pasa `movie-inbox backup verify`.
- Cada `--library-root` es especifico, existe al arrancar y el usuario del servicio tiene
  acceso de solo lectura; las rutas no aparecen en respuestas para miembros.
- La restauracion desde una exportacion JSON fue probada.

La automatizacion de deploy sigue fuera del workflow de CI por ahora. El backup diario
si puede programarse en el host con las unidades systemd incluidas; una actualizacion
continua requiriendo un despliegue manual y una verificacion posterior.

El repositorio tambien publica una imagen reproducible y `compose.yaml` para instancias
nuevas. La guia [docker.md](docker.md) cubre importacion inicial, volumen persistente,
secret del owner y una biblioteca montada en modo de solo lectura. La relocalizacion de
un `instance.db` existente sigue pendiente porque sus catalogos conservan rutas
absolutas.
