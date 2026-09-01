# ADR-0001: presentacion publica como capacidad de solo lectura

- Estado: aceptado
- Fecha: 2026-09-01
- Alcance: [W1]

## Contexto

Movie Inbox es una instancia personal/familiar con catalogos privados. `Club` permite
compartir catalogos y colecciones **entre miembros autenticados de la misma instancia**;
sus rutas `/api/community` y `/api/collections` dependen de sesion y no son una base
segura para publicar una pagina en Internet. El catalogo, la disponibilidad de una
biblioteca y toda metadata local contienen mas datos de los que una pagina publica
necesita.

La necesidad aprobada es una presentacion opcional de disponibilidad, no la exposicion
del catalogo personal ni un directorio de usuarios. Esta decision define el limite de
confianza antes de que [W2] agregue almacenamiento, endpoints o UI.

## Decision

### Forma y activacion

Una presentacion publica es un **snapshot curado de obras disponibles**, activado por
un owner de forma explicita. No existe una presentacion al crear una cuenta, una
biblioteca o una coleccion; las cuentas restauradas tambien comienzan privadas.

Al activarla, el servidor genera un identificador de capacidad aleatorio de al menos
256 bits, codificado URL-safe. Guarda solamente su hash y entrega el valor plano una
vez al owner. El valor no es un slug, username, id de catalogo ni id incremental. La
URL publica canonica sera `GET /p/{capacidad}` y devolvera una shell estatica minima;
esa shell obtiene unicamente `GET /public/v1/presentations/{capacidad}`. No hay indice,
buscador, listado, redireccion desde nombres humanos ni documentacion OpenAPI para
esas rutas.

La fuente se materializa como snapshot sanitizado al publicar o al refrescarlo
deliberadamente. Un cambio posterior del catalogo, de Club o del scanner no agrega
datos a una pagina publica por arrastre. [W2] puede permitir que el owner seleccione
una coleccion propia o de disponibilidad verificada como origen, pero no debe aceptar
un catalogo completo como atajo.

### Contrato de datos

El unico payload permitido es
[`docs/public-presentation-v1.schema.json`](../public-presentation-v1.schema.json).
Contiene titulo y descripcion que el owner eligio para la presentacion, y como maximo
200 obras con posicion, titulo, titulo original, ano, tipo, generos y duracion. Es una
allowlist cerrada; `additionalProperties: false` es parte del contrato, no una
preferencia de serializacion.

Quedan excluidos, incluso si existen en Club: identidad de owner/miembro, username,
ids internos o externos, URLs de fuentes, imagenes remotas, paths, nombres de archivo,
conteos o nombres de bibliotecas, disponibilidad por fuente, estado personal, fecha de
visionado, puntaje, review, notas, bloqueos, decisiones de curaduria, procedencia,
historial, cookies, tokens y errores internos. Una pagina publica comunica que las
obras de su snapshot estan disponibles; no enumera obras ausentes ni el inventario
real. Imagenes y enlaces externos quedan fuera de v1: habilitarlos requiere una
decision posterior sobre licencia, tracking y purga.

El contrato se versiona por ruta (`/public/v1/`) y por `schema_version: 1`. Un cambio
incompatible crea v2; no se ensancha v1 ni se reutiliza el esquema de exportacion JSON,
de Club o de catalogo.

### Aislamiento, cache y limites

Las rutas publicas se implementaran en un router y servicio propios. No pueden importar
ni llamar endpoints, dependencias o serializadores de `/api/*`, `SessionCatalog`,
`PrivacyService` o `CollectionService`. Son exclusivamente `GET`/`HEAD`, no escriben,
no requieren ni interpretan la cookie de sesion y no emiten `Set-Cookie`. No se les
aplica CSRF porque no producen efectos; toda accion del owner (activar, preview,
refrescar, revocar) sigue siendo una ruta privada autenticada con la proteccion CSRF
actual. Si un navegador envia una cookie privada por compartir host, la respuesta debe
ser exactamente la misma sin ella y nunca variar por cookie, usuario u origen.

La respuesta de contenido publico usa `Cache-Control: no-store`, sin excepcion. Asi
una revocacion es efectiva en la siguiente solicitud y no depende de purgas de CDN. Los
assets estaticos con hash pueden ser `immutable` porque no contienen contenido del
owner. La shell y el JSON tambien llevan `Referrer-Policy: no-referrer`,
`X-Robots-Tag: noindex, nofollow, noarchive`, una CSP sin conexiones o scripts de
terceros y no habilitan CORS. Un reverse proxy no debe registrar query strings ni
convertir la capacidad en una cabecera de analytics.

Cada lectura se limita por capacidad y por IP: rafaga maxima de 20 y hasta 60 lecturas
por minuto. El limite usa la IP directa, salvo que el proxy ya confiable de la instancia
haya sido configurado de forma explicita; nunca confia en `X-Forwarded-For` desde
Internet. Excederlo devuelve `429` con `Retry-After`, sin revelar si la capacidad
existia. Los identificadores invalidos, revocados o no existentes devuelven la misma
respuesta `404` generica, sin distinguir motivos.

Revocar borra o inutiliza el hash en una unica transaccion y corta todo acceso futuro.
Rotar crea una capacidad nueva y revoca la anterior; desactivar el owner, archivar su
cuenta o retirar el origen revoca todas sus presentaciones dentro de esa misma
transaccion. Preview nunca usa la capacidad: renderiza el snapshot candidato por una
ruta privada `no-store`.

### Superficie de despliegue

La primera implementacion puede vivir en el mismo proceso, pero la configuracion
soportada para acceso desde Internet debe permitir servir `/p/` y `/public/` desde un
host publico dedicado. El host privado conserva login y `/api/`; no se mezclan cookies
ni politicas de reverse proxy por conveniencia. [D1] documentara esa separacion junto
con HTTPS. Hasta que exista esa receta, una instancia sigue siendo privada por defecto.

## Modelo de amenazas

| Amenaza | Control decidido | Verificacion requerida en W2 |
| --- | --- | --- |
| Enumerar cuentas, colecciones o capacidades | capacidad aleatoria no enumerable, sin listados ni slugs, 404 uniforme | no hay endpoint de indice; ids invalidos/revocados dan la misma respuesta |
| Filtrar archivos, rutas o estado personal | snapshot construido por allowlist v1, no desde payloads de Club | tests de payload profundo contra cada campo prohibido |
| Reutilizar una sesion o provocar CSRF | router sin dependencias privadas, solo lectura, sin `Set-Cookie` | cookie presente/ausente produce mismo cuerpo; POST devuelve 405/404 |
| Acceder tras revocacion o desactivar una cuenta | hash invalidado transaccionalmente; contenido `no-store` | revocar, desactivar y archivar devuelven 404 en la siguiente lectura |
| Abusar del endpoint o descubrir capacidades por tiempo | rate limit por IP+capacidad, respuesta y tiempos uniformes dentro de lo razonable | 429 con `Retry-After`; prueba de cabeceras reenviadas no confiables |
| Rastrear visitantes o filtrar la URL por terceros | sin imagenes/enlaces/scripts externos, `no-referrer`, CSP, robots | CSP/referrer/robots y ausencia de URL externa en HTML y JSON |
| Proxy o cache servir contenido antiguo | `no-store`; host publico separado como configuracion soportada | cabeceras exactas y prueba de que no hay cache por cookie |
| XSS desde texto del owner o metadata | renderizado escapado, limites del esquema, CSP | textos hostiles se muestran como texto y no ejecutan codigo |

## Consecuencias

La primera landing es deliberadamente mas chica que Club y que una ficha interna. Evita
una fuga por composicion de campos y permite agregar una experiencia visual sin volver
publicos contratos privados. El costo es que el owner debe elegir y refrescar el
snapshot; automatizarlo, incluir imagenes, agregar analitica, enlaces de proveedores o
mostrar el catalogo completo requiere un ADR y una version posterior del contrato.

[W2] implementa este diseño y sus pruebas de aislamiento. [W3] puede reutilizar el
formato versionado, pero no la capacidad ni el esquema como mecanismo de sincronizacion.
