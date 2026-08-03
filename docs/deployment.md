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
  --public-origin https://movies.example.com \
  --forwarded-allow-ips 127.0.0.1 \
  --image-cache-dir /var/lib/movie-inbox/image-cache \
  --image-cache-total-mb 512 \
  --library-root /srv/media/peliculas \
  --no-open
```

La app usa un solo worker. SQLite serializa escrituras y el cache de busquedas vive en memoria; agregar workers antes de medir carga sumaria contencion y estados duplicados sin aportar valor para un catalogo personal.

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

## Nginx y acceso

La plantilla [nginx.movie-inbox.conf.example](../deploy/nginx.movie-inbox.conf.example) termina HTTPS, limita el cuerpo a 2 MB, preserva el `Host` publico y reenvia headers al proceso local. Movie Inbox presenta su propio login; `auth_basic` puede agregarse como una segunda barrera, pero no es necesario para el flujo normal.

```bash
sudo cp deploy/nginx.movie-inbox.conf.example /etc/nginx/sites-available/movie-inbox
sudo ln -s /etc/nginx/sites-available/movie-inbox /etc/nginx/sites-enabled/movie-inbox
sudo nginx -t
sudo systemctl reload nginx
```

Movie Inbox autentica la cuenta antes de entregar el visor. La cookie de sesion es `HttpOnly`, `SameSite=Strict` y `Secure` bajo este origen HTTPS; el token opaco nunca aparece en la URL y SQLite guarda solamente su hash. El token anti-CSRF, la validacion de `Origin` y la sesion se exigen juntos. Uvicorn no registra access logs y Nginx omite el log del proxy de imagenes para no guardar URLs del catalogo.

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
- Cada `--library-root` es especifico, existe al arrancar y el usuario del servicio tiene
  acceso de solo lectura; las rutas no aparecen en respuestas para miembros.
- La restauracion desde una exportacion JSON fue probada.

La automatizacion de deploy sigue fuera del workflow de CI por ahora: primero conviene hacer un despliegue manual completo y verificar backup/restauracion.

El repositorio todavia no publica `Dockerfile` ni `compose.yaml`. El empaquetado Docker
queda planificado despues de estabilizar el scanner en un servidor real; debera montar
datos y backups como volumenes persistentes y cada biblioteca en modo de solo lectura.
