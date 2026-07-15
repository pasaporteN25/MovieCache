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
systemd -> movie-inbox serve -> 127.0.0.1:8765
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

## Limite actual

El servidor incluido escucha solamente en loopback y sus defensas actuales estan pensadas para uso local directo. Antes de exponerlo mediante Nginx deben resolverse en conjunto:

- autenticacion de usuarios o acceso privado mediante VPN;
- origen publico permitido y validacion segura de headers del proxy;
- persistencia o estrategia de renovacion del token de sesion;
- TLS, limites de peticion, logs y reinicios del servicio;
- permisos del usuario del proceso sobre base, cache y backups;
- restauracion probada desde una exportacion JSON.

Hasta cerrar esa fase, Nginx no debe publicar el visor en Internet. Una opcion temporal segura es entrar al servidor por Tailscale/VPN y usar un tunel SSH hacia el puerto loopback.
