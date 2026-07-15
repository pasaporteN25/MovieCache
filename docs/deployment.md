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
systemd -> Uvicorn/FastAPI -> 127.0.0.1:8765
        |
        v
Nginx -> HTTPS y autenticacion -> navegador

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
4. Ejecutar el proceso bajo un usuario sin privilegios mediante `systemd`.
5. Exportar JSON periodicamente hacia un volumen de backups distinto.

Una automatizacion posterior puede hacer esos pasos al publicar una version. No es necesario instalar un runner de CI en el servidor.

Una preparacion minima del host seria:

```bash
sudo useradd --system --home /var/lib/movie-inbox --shell /usr/sbin/nologin movie-inbox
sudo install -d -o movie-inbox -g movie-inbox /var/lib/movie-inbox /var/backups/movie-inbox
cd /opt/movie-inbox
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

El checkout puede pertenecer al usuario de despliegue y ser solamente legible para `movie-inbox`. La base y el cache si deben pertenecer al usuario del servicio.

## Ejecutar la aplicacion

El proceso de aplicacion debe seguir escuchando solamente en loopback. `--public-origin` habilita ese origen exacto para validacion de `Host` y escrituras del navegador; no cambia la direccion de escucha:

```bash
/opt/movie-inbox/.venv/bin/movie-inbox serve \
  /var/lib/movie-inbox/movie-inbox.db \
  --host 127.0.0.1 \
  --port 8765 \
  --public-origin https://movies.example.com \
  --forwarded-allow-ips 127.0.0.1 \
  --image-cache-dir /var/lib/movie-inbox/image-cache \
  --no-open
```

La app usa un solo worker. SQLite serializa escrituras y el cache de busquedas vive en memoria; agregar workers antes de medir carga sumaria contencion y estados duplicados sin aportar valor para un catalogo personal.

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

La plantilla [nginx.movie-inbox.conf.example](../deploy/nginx.movie-inbox.conf.example) termina HTTPS, limita el cuerpo a 2 MB, preserva el `Host` publico y reenvia headers al proceso local. Copiala despues de reemplazar dominio y certificados:

```bash
sudo htpasswd -c /etc/nginx/.htpasswd-movie-inbox lucas
sudo cp deploy/nginx.movie-inbox.conf.example /etc/nginx/sites-available/movie-inbox
sudo ln -s /etc/nginx/sites-available/movie-inbox /etc/nginx/sites-enabled/movie-inbox
sudo nginx -t
sudo systemctl reload nginx
```

El token embebido por Movie Inbox protege operaciones contra otras paginas web, pero no autentica personas: cualquiera que pueda abrir la portada recibe su propio acceso a la API de esa sesion. Las imagenes usan una cookie `HttpOnly` y no colocan el token en la URL; Uvicorn no registra access logs y Nginx omite el log de esa ruta para no guardar URLs de imagenes del catalogo. La plantilla conserva `auth_basic`; para un servicio estrictamente personal es preferible limitar Nginx mediante Tailscale/VPN y no publicarlo en Internet.

## Checklist de publicacion

- Los checks pasan sobre el commit desplegado.
- El proceso corre como usuario sin privilegios.
- SQLite, cache y backups estan fuera de `/opt/movie-inbox`.
- Nginx es el unico proceso publico y Uvicorn escucha en `127.0.0.1`.
- `--public-origin` coincide exactamente con el origen HTTPS del navegador.
- `--forwarded-allow-ips` contiene solamente la direccion del proxy.
- Hay autenticacion en Nginx o acceso limitado por VPN.
- La restauracion desde una exportacion JSON fue probada.

La automatizacion de deploy sigue fuera del workflow de CI por ahora: primero conviene hacer un despliegue manual completo y verificar backup/restauracion.
