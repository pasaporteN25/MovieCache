# ADR-0003: API v1 para clientes de dispositivo

- Estado: aceptado
- Fecha: 2026-09-02
- Alcance: [A1.1]

## Contexto

Las rutas privadas actuales bajo `/api/` pertenecen a la shell web: combinan la cookie
`movie_inbox_auth`, el header anti-CSRF `X-Movie-Inbox-Token`, `Origin` y payloads que
conservan detalles internos necesarios para esa interfaz. Un cliente nativo no debe
imitar esa combinación ni recibir rutas, nombres de archivos, paths de catálogo,
administración, Scanner, Curaduría o Club por conveniencia.

El primer cliente será Android y se conectará a una URL HTTPS que el usuario elige. La
instancia continúa siendo self-hosted y no aparece un servicio central, una cuenta
externa ni sincronización offline por esta decisión.

## Decisión

### Límite de la superficie

La API de dispositivo vive exclusivamente bajo `/api/v1/`. Su contrato está en
[`docs/openapi/device-api-v1.openapi.json`](../openapi/device-api-v1.openapi.json) y
es la fuente normativa de nombres, tipos y códigos de error. Ese documento se publica
en el repositorio; la instancia no habilita Swagger ni OpenAPI público en runtime.

La primera versión cubre solamente:

- crear, renovar y revocar una sesión del dispositivo;
- conocer la identidad autenticada;
- listar, buscar y leer obras del catálogo personal;
- modificar estado, fecha de visionado, puntaje y review propios;
- leer una proyección compacta de disponibilidad, sin datos de bibliotecas.

Quedan deliberadamente fuera de v1: Scanner, administración de miembros y bibliotecas,
Curaduría, importaciones, Club, cartelera pública, configuración de proveedores,
operaciones masivas, escritura de metadata compartida y búsquedas externas. Esas rutas
no se “descubren” desde el cliente ni se conceden por ser owner.

### Autenticación y transporte

El cliente acepta una URL base HTTPS con certificado válido y envía credenciales solo a
`POST /api/v1/auth/login`. A1.2 emitirá pares opacos de access/refresh token asociados
a un dispositivo; el access token viaja en `Authorization: Bearer`, nunca en una cookie
ni en la URL. El refresh token se usa solamente en la renovación y el cliente debe
guardarlo en almacenamiento seguro de la plataforma. Cerrar o revocar borra el estado
de esa sesión sin afectar las sesiones web ni otros dispositivos.

La API no usa el header de token ni la comprobación `Origin` de la shell web: son una
defensa CSRF para cookies y no un sustituto de autenticación de un cliente nativo. No
se habilita CORS para convertirla en API de navegador. HTTP, certificados inválidos,
hosts redirigidos a otro origen y tokens en query string son configuraciones no
soportadas.

### Datos y versionado

Cada obra expone un `id` opaco dentro del catálogo autenticado; no contiene el path,
el nombre de archivo ni la referencia de fuente que usa el servidor para persistirla.
La disponibilidad se resume como estado y conteo, siempre de solo lectura. Las
mutaciones personales usan `PATCH` parcial e idempotente sobre ese `id`; `null` borra
un campo opcional. Una respuesta nunca incluye password, hashes, tokens, rutas,
cookies, `source_file`, `_source_file`, inventario detallado, historial de Scanner ni
preferencias de otros miembros.

La versión mayor forma parte de la ruta. Cambios incompatibles crean `/api/v2/`; v1 no
se ensancha cambiando el significado de un campo. Agregar campos opcionales o códigos
de error es compatible: clientes deben ignorar campos desconocidos y tratar enums
desconocidos como no accionables. Las respuestas JSON incluyen
`X-Movie-Inbox-Api-Version: 1` y los errores usan el sobre estable
`{"error":{"code":"..."}}`, no el sobre histórico de `/api/`.

## Modelo de amenazas

| Amenaza | Control decidido | Prueba de A1.2/A1.3 |
| --- | --- | --- |
| Reutilizar la cookie o el token anti-CSRF web | rutas, tokens, dependencia y persistencia separadas | una cookie web o `X-Movie-Inbox-Token` no autentica `/api/v1` |
| Interceptar credenciales o tokens | HTTPS obligatorio, Bearer solo en header, sin query/cookies | HTTP y token en query se rechazan; no hay `Set-Cookie` |
| Robo de un token de larga vida | access breve, refresh opaco persistido como hash, rotación y revocación por dispositivo | refresh, logout y revocación invalidan el token anterior |
| Fuerza bruta de login | mismo límite por IP+usuario que el acceso web, respuesta uniforme | intentos fallidos devuelven `429` y `Retry-After` |
| Exponer rutas o inventario al miembro | serializador allowlist específico, disponibilidad resumida | fixtures con paths y archivos no los filtran |
| Escalada hacia administración/Scanner | allowlist de rutas y scopes de dispositivo | owner y miembro reciben el mismo conjunto de rutas de dispositivo |
| Incompatibilidad silenciosa | versión por ruta, especificación estática y pruebas de contrato | el servidor prueba el contrato v1 y un cliente fixture contra él |

## Consecuencias

A1.1 fija el contrato sin declarar endpoints productivos todavía. A1.2 implementará
el almacenamiento y ciclo de vida de sesiones por dispositivo; A1.3 implementará los
serializadores/rutas y las pruebas de compatibilidad contra esta especificación. A2
puede consumir solo una versión de A1 cerrada y no debe usar los endpoints web
históricos como atajo.
