# ADR-0002: paquetes portables entre instancias sin servicio central

- Estado: aceptado para prototipo; implementacion productiva pendiente
- Fecha: 2026-09-02
- Alcance: [W3]

## Contexto

Una instancia de Movie Inbox es privada por defecto. `Club` y la presentacion publica
resuelven necesidades distintas dentro de una instancia; no son un protocolo para
compartir datos entre homeservers. Reutilizar sus rutas, cookies, capacidades o
serializadores expondria mas informacion de la necesaria y convertiría una accion de
importacion local en una superficie de red.

El caso de uso aprobado es intercambiar una seleccion curada entre dos owners que ya
decidieron colaborar: por archivo, USB, carpeta sincronizada elegida por ellos o un
canal de mensajeria. Tambien debe poder importarse una copia vieja para conservar una
referencia, sin que eso cree una relacion de sincronizacion. No se presupone una cuenta
global, DNS publico, directorio de instancias, descubrimiento de peers ni relay.

## Decision

### Limite de v1

El formato es un paquete local `.mipkg` ZIP con dos archivos exactos:

1. `manifest.json`, con identidad tecnica de instancia, version, integridad y modo de
   confianza;
2. `payload.json`, con una sola coleccion curada y una allowlist cerrada de obras.

El contrato completo vive en
[`docs/homeserver-package-v1.schema.json`](../homeserver-package-v1.schema.json). La
referencia de implementacion bajo `scripts/` solo construye e inspecciona paquetes
**manuales**: no escucha puertos, no hace HTTP, no extrae el ZIP y no importa datos de
la aplicacion. Es deliberadamente descartable; demuestra el limite del formato antes
de sumar almacenamiento, claves o una API al producto.

Un paquete v1 contiene solamente titulo y descripcion editoriales de la coleccion, y
por obra posicion, titulos, ano, tipo, director y los IDs externos minimos. Excluye
por contrato: usuarios, nombres de instancia, dominios, rutas, archivos, bibliotecas,
disponibilidad, estado de visionado, rating, review, notas, bloques, decisiones de
curaduria, procedencia, historiales, tokens, cookies, configuracion y enlaces remotos.
El `instance_id` es un UUID aleatorio persistente del homeserver futuro; identifica una
instalacion tecnica, no una persona ni una direccion alcanzable.

Cada payload se codifica como JSON UTF-8 compacto y su SHA-256 se guarda en el
manifiesto. Eso detecta corrupcion o sustitucion accidental. No se presenta como firma
ni como prueba de autor: el modo `manual` exige que quien recibe confirme por un canal
independiente el digest y la identidad que esperaba.

### Confianza y claves

v1 reserva el modo `ed25519` para un paquete con firma separada `signature.ed25519`,
`key_id` y huella de clave. La implementacion productiva solo podra habilitarlo con una
biblioteca auditada, almacenamiento local de claves, rotacion y vectores de
interoperabilidad. La firma cubrira el manifiesto sin su bloque `proof` y el digest de
`payload.json`, serializados de forma canonica con JCS; firmar JSON no canonico seria
ambiguo entre lenguajes. JCS define una representacion JSON invariante para hashing y
firma, y Ed25519 esta especificado por EdDSA. No se inventa criptografia propia ni se
convierte SHA-256 en una afirmacion de identidad. [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html)
y [RFC 8032](https://www.rfc-editor.org/info/rfc8032/) son las referencias de diseno.

Hasta entonces, importar un paquete manual es una decision explicita del owner. Un
paquete firmado con una clave desconocida igualmente requiere aprobacion de esa clave
fuera de banda; una firma valida prueba control de una clave, no identidad humana. No
hay lista central de claves ni mecanismo de recuperacion remoto.

### Importacion, conflictos y revocacion

El futuro importador no modifica ningun catalogo al abrir un paquete. Primero crea un
preview privado y muestra origen, digest, modo de confianza y cada coincidencia. El
owner elige una de estas acciones:

| Situacion | Resultado por defecto |
| --- | --- |
| Nueva coleccion | Crear una coleccion privada local, sin seguimiento automatico |
| Mismo ID externo y mismo tipo | Sugerir fusion por obra, conservando la copia local ante campos editoriales distintos |
| IDs incompatibles o tipo distinto | Bloquear fusion automatica y pedir revision |
| Solo titulo/ano/director parecido | Nunca fusionar: crear copia o seleccionar manualmente |
| Nuevo paquete con el mismo origen | Comparar contra el receipt anterior; no sobrescribir una edicion local sin eleccion del owner |

Un paquete es una foto, no un canal de sincronizacion. La primera version productiva
no hara polling, webhooks, conexiones entrantes ni salientes. Una futura sincronizacion
directa requerira pairing iniciado por ambos owners, endpoint separado, TLS, lista de
peers explicitamente aprobada y otro ADR.

La revocacion no puede borrar copias que otro owner ya descargo. Revocar una clave o un
`package_id` localmente solo impide futuros imports o actualizaciones desde ese origen;
el owner receptor decide borrar su copia. Un receipt local conserva package/origin id,
digest, fecha de importacion, confianza y estado de revocacion, pero nunca archivos ni
credenciales del emisor. Esta limitacion se mostrara en la UI antes de exportar.

### Modelo de amenazas

| Riesgo | Control de W3 | Verificacion del prototipo |
| --- | --- | --- |
| Red publica involuntaria | Solo archivo local; no hay cliente ni servidor de red | inspeccion por subprocess, sin dependencias HTTP |
| ZIP malicioso o zip-slip | nombres exactos, sin extraccion, limite de tamanos y entradas duplicadas | rechaza entradas extra, duplicadas y payload alterado |
| Fuga de datos de instancia | esquema de payload por allowlist, sin reutilizar catalogo/Club | rechaza claves no permitidas, rutas y estado personal |
| Suplantacion de origen | manual requiere confirmacion fuera de banda; futuro Ed25519 + JCS | resultado explica que el digest no autentica al emisor |
| Falso merge | preview privado y evidencia fuerte por IDs + tipo | decision documentada; no hay importador que escriba |
| Revocacion ilusoria | receipts locales y sin promesa de borrar una copia ajena | limitacion declarada antes de producto |
| Enumeracion/seguimiento | no hay directorio, anuncios, URL remota ni telemetria | formato no contiene host, usuario ni URL |

## Consecuencias

La interoperabilidad empieza deliberadamente como transferencia de archivos y no como
una federacion. Eso deja abierta la posibilidad de colaborar entre homeservers sin
hacer una instancia descubrible ni mezclar permisos locales. Tiene dos costos
aceptados: el usuario debe confirmar paquetes manuales, y una copia importada puede
quedar desactualizada. Ambos costos son preferibles a automatizar una relacion de
confianza que aun no existe.

Trabajo posterior: persistir identidad de instancia y receipts, integrar el preview
privado, elegir una implementacion Ed25519/JCS mantenida, agregar pruebas cruzadas y
disenar pairing directo en una tarea nueva. Ninguna de esas partes queda habilitada por
este ADR.
