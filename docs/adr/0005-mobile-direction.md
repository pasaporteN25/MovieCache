# ADR-0005: dirección del cliente móvil

- **Estado:** aceptada — 2026-09-07
- **Tarea:** [MB1]. Decisión de arquitectura, sin implementación.
- **Reemplaza el supuesto de:** [A2], que queda suspendida hasta reespecificarse.
- **Se apoya en:** ADR-0002 (paquetes portables) y ADR-0003 (API de dispositivo v1).

## Contexto

El owner fijó un norte el 2026-09-07: **la aplicación móvil tiene que ser independiente**.
Debe funcionar sin instancia web y sin despliegue Docker detrás, y bastarse a sí misma.
Sincronizar catálogos y usuarios con una instancia es **opcional y lo inicia una persona**,
por ejemplo con un QR. Además considera que charadas importa más en el teléfono que en la
web.

Eso no es lo que dice [A2] hoy. ADR-0003 especificó un **cliente delgado**: URL HTTPS,
sesión Bearer, lectura del catálogo *del servidor*, `PATCH` de estado personal, y
explícitamente sin offline. Son dos productos distintos, no dos tamaños del mismo.

## Decisión

### 1. El cliente es autónomo; el servidor es un par opcional

Una instalación móvil sola es una configuración soportada de primera clase, no un modo
degradado. El teléfono tiene su propio almacén local y su propio catálogo. Una instancia
web, cuando existe, es **otro par**, no la fuente de verdad.

El habilitador ya está: `catalog.schema.json` es un contrato portable versionado (v9) con
round-trip probado contra SQLite. El cliente guarda ese mismo documento.

### 2. Qué guarda el teléfono, y qué no

El cliente guarda la **capa de obra y la capa personal**: identidad, títulos, año, tipo,
IDs externos, géneros, duración, imágenes, y `status`, `watched_at`, `rating`, `review`.

No guarda la **capa operativa**: rutas, nombres de archivo, bibliotecas, `library_id`,
estado del Scanner, decisiones de curaduría ni preferencias de otros miembros. No es sólo
privacidad — un teléfono no tiene los discos del usuario, así que esos campos no
significan nada ahí. Esto coincide con la allowlist que ADR-0003 ya definió para la API de
dispositivo, y con la invariante 4.

Consecuencia deliberada: `en_catalogo` viaja como **lectura**, no como algo que el
teléfono pueda afirmar. Sólo el servidor que escanea discos sabe si el archivo existe.

### 3. La sincronización es opt-in, la inicia una persona y nunca borra

Ningún dispositivo sondea, anuncia ni acepta conexiones entrantes. Una sincronización
ocurre porque alguien la pidió, en ese momento.

**La sincronización nunca borra.** Una obra ausente de un lado significa "todavía no
llegó", nunca "fue eliminada". Sin esta regla, un teléfono recién instalado vaciaría el
catálogo del servidor en el primer intercambio. Borrar es una acción local y explícita en
cada lado; propagar bajas exige tombstones y su propio ADR.

### 4. Convergencia de estado personal: fusión a tres bandas, conflicto a la persona

Es la decisión difícil y la razón de ser de este documento. `status`, `watched_at`,
`rating` y `review` se editan en los dos lados sin conexión.

Se descarta **last-write-wins**: pierde datos en silencio, y silencio es exactamente lo
que este proyecto no hace con lo ambiguo (principio de producto 3, `decide_match`, la
previsualización antes de escribir en importaciones, curaduría y retirada).

La regla es una **fusión a tres bandas**, como la de un merge de control de versiones:

| Situación respecto de la base | Resultado |
| --- | --- |
| Sólo un lado cambió | Se aplica ese cambio |
| Ambos cambiaron al mismo valor | Converge, sin conflicto |
| Ambos cambiaron a valores distintos | **Conflicto: decide la persona** |
| Ninguno cambió | Nada |

La **base** es el estado registrado en la última sincronización exitosa con ese par —
el mismo rol que el *receipt* de ADR-0002, y por eso se reusa ese concepto.

Dos propiedades que esto compra y que last-write-wins no da:

- **No depende de relojes confiables.** La detección de "ambos cambiaron" es una
  comparación contra la base, no una carrera de timestamps. El desfasaje de reloj entre un
  teléfono y un servidor es real y no puede decidir qué review sobrevive. Las marcas de
  tiempo sirven para ordenar la presentación, no para resolver.
- **El conflicto tiene una interfaz que ya existe.** El comparador de fusión de v0.4.0/
  v0.5.0 ya muestra dos versiones de una obra y pide una decisión. Un conflicto de
  sincronización es ese mismo problema.

La comparación es **por campo**: cambiar el puntaje en el teléfono y la review en la web
converge sin molestar a nadie.

`locked_fields` y las correcciones manuales siguen ganando (invariante 5). Un puntaje
público nunca entra por acá ([F3.2]).

### 5. El QR aparea; no transporta

Un QR **no puede llevar un catálogo**: el máximo de un QR versión 40 con la corrección de
errores más baja ronda los 2953 bytes, y en la práctica útil es menos. Un catálogo de 300
obras no entra ni cerca.

El QR lleva el **apareamiento**: origen, identidad técnica de la instancia y un token de un
solo uso. La transferencia viaja después por HTTPS en la red local. Es el mismo rol que
cumple un QR en cualquier emparejamiento de dispositivos, y respeta la exigencia de
ADR-0002 de que una sincronización directa requiere pairing iniciado por ambas partes.

### 6. Qué le falta a [A1] para ser el canal

**[A1] no se tira: se convierte en el transporte de la sincronización.** Pero v1, leído
contra este ADR, tiene tres huecos concretos, verificados en el código el 2026-09-07:

1. **No hay ninguna marca de tiempo.** `_device_item_payload` expone `id`, datos de obra y
   `personal`, sin `updated_at`, versión ni revisión. Sin eso no se puede saber qué cambió
   desde la última base salvo comparando el catálogo entero.
2. **El id opaco no es una clave de sincronización durable.** Se deriva con
   `_opaque_item_id(secret, catalog_id, source_reference, catalog_item_id)` donde `secret`
   es `viewer_config.api_token`. Si ese token rota, o si cambia el archivo de origen del
   catálogo, **cambian todos los ids**. Sirve dentro de una sesión viva; no para un cliente
   que guarda ids entre reconfiguraciones del servidor.
3. **No hay feed de cambios ni exportación masiva**, sólo paginación por cursor sobre todo
   el catálogo.

Los tres se resuelven **de forma aditiva** — campos y rutas nuevas, sin cambiar el
significado de ninguno existente — así que caben dentro de v1 según la propia regla de
versionado de ADR-0003.

### 6.1 Qué se implementó de [A1.4], y qué no — 2026-09-07

De los tres huecos, **sólo el segundo era de corrección**. Los otros dos resultaron ser
optimizaciones, y construirlos ahora habría sido peor que no hacerlo.

**Hecho: la clave durable.** El secreto pasa de `viewer_config.api_token` a un secreto
persistente por instancia, y la ruta absoluta del archivo de origen se reemplaza por la
posición de esa fuente. Los ids de obra sólo son únicos dentro de un archivo —`load_items`
concatena las fuentes sin deduplicar—, así que la fuente sigue participando de la clave,
pero sin llevar una ruta. Verificado de punta a punta: rotar el `api_token` deja los ids
idénticos, y siguen siendo opacos.

**No hecho, y a propósito: las marcas de tiempo.** No existe hoy ninguna marca que
registre una edición personal: `curation_updated_at` la escriben sólo curaduría y fusión,
y `patch_personal` no toca ninguna. Exponer `curation_updated_at` como `updated_at` sería
**peor que no exponer nada**, porque un cliente construiría su lógica de fusión sobre una
marca que no cambia cuando cambia un puntaje. Agregar una marca real toca el contrato
portable `catalog.schema.json`, que es una decisión más grande que "aditivo a la API de
dispositivo" y merece tomarse aparte.

**No hecho: el feed de cambios.** La fusión a tres bandas no lo necesita para ser
correcta: la base vive en el cliente, así que comparar contra el estado actual completo
del servidor alcanza. Un feed es una optimización de transferencia, depende de las marcas
de tiempo que no existen, y con catálogos del orden de las cientos de obras no compra
nada. Queda pendiente de una necesidad real, no de una fecha.

## Corrección a una afirmación previa

En el análisis del 2026-09-07 escribí que ADR-0002 "ya resolvió este problema" y que se
reusa su contrato. **Es demasiado fuerte y lo corrijo acá.** El formato `.mipkg` excluye
por contrato el estado de visionado, rating, review y notas — justo lo que una
sincronización de dispositivo tiene que llevar. El *formato* no se reusa.

Lo que sí se reusa, y sigue siendo valioso, son sus **principios**: previsualizar antes de
escribir, digest de integridad, sin servicio central, decisión explícita del owner,
receipts locales y una tabla de conflictos con "nunca fusionar por parecido". ADR-0002
además anticipó exactamente este caso al decir que una sincronización directa exigiría
"otro ADR"; este es ese ADR.

## Consecuencias

**[A2] queda suspendida y hay que reespecificarla.** Su alcance actual —cliente delgado,
sin offline— describe otro producto. El orden nuevo es: almacén local primero, después
sincronización, y la interfaz encima.

**[A1] gana una extensión aditiva** con marcas de tiempo, una clave de sincronización
durable e independiente del `api_token`, y un feed de cambios.

**Charadas ([G1]/[G2]) se vuelve el primer entregable natural de esta dirección**: usa
datos de sólo lectura, no necesita sincronización, funciona sin red y es lo que el owner
más quiere en el teléfono. Sirve para probar el almacén local antes de construir la
sincronización.

**Se acepta un costo.** Una réplica local es más trabajo que un cliente delgado, y la
fusión a tres bandas obliga a construir una interfaz de conflictos en móvil. A cambio, la
aplicación sirve sin servidor, que es el requisito.

## Decisiones sumadas el 2026-09-07

Cuatro de los puntos abiertos originales quedaron resueltos por el owner el mismo día.

### 7. Dar de alta sin conexión produce un borrador, nunca una pérdida

**Decidido.** Estando offline se puede dar de alta una obra con lo que la persona sepa —
al menos un título. Eso crea un **borrador local pendiente de enriquecimiento**. Cuando
vuelve la red, la búsqueda y el enriquecimiento corren de forma asíncrona.

No hace falta inventar el concepto: `PRODUCT.md` ya define borradores privados para las
importaciones, y este es el mismo patrón aplicado a otro origen. Con **una diferencia
obligatoria**: los borradores de importación expiran a las 48 horas, y esa expiración acá
sería un defecto. Un borrador offline puede esperar días a que haya red, así que **no
expira**; sólo lo cierra la persona, resolviéndolo o descartándolo.

Al resolverse, el borrador entra por el camino de alta que ya existe, no por uno nuevo:
el matching sigue siendo conservador (invariante 3), y una coincidencia fuerte con una
obra ya presente se combina mediante `auto_merge_on_add` en vez de crear un duplicado
([Q6]). Una coincidencia dudosa queda para revisión humana, como en cualquier otro alta.

### 8. Las imágenes se re-descargan en segundo plano, con una miniatura local

**Decidido, en la variante mixta.** El teléfono guarda una **miniatura** por obra —
barata y disponible sin red — y **re-descarga la portada completa en segundo plano**.

Tampoco es una política nueva: es la que el servidor ya aplica, donde las portadas se
cargan progresivamente después del primer acceso y *"la navegación visible tiene prioridad
y nunca espera a que termine la cola global"* (`PRODUCT.md`). Se replica esa regla, no se
inventa otra.

Consecuencia: una portada ausente nunca bloquea una pantalla ni una sincronización. El
fallback ya existente de portada rota es el estado normal mientras la cola avanza.

### 9. Plataforma: Android nativo con Kotlin

**Decidido.** No es PWA ni multiplataforma. Eso fija el almacén local en las herramientas
del ecosistema y hace que el comportamiento definido arriba —réplica local, fusión a tres
bandas, cola de imágenes, borradores sin expiración— sea responsabilidad del cliente
Kotlin.

Deja de depender de [MB2]: la auditoría móvil pasa a informar el diseño de las pantallas,
no la elección de plataforma.

### 10. Una cuenta por instalación

**Decidido.** El teléfono conoce **qué** cuenta es —la identidad viaja en el apareamiento—
pero guarda **una sola**. Varias cuentas en un mismo aparato exigirían aislamiento entre
almacenes y cifrado en reposo, porque las reviews y notas de una persona no deberían
leerse desde la sesión de otra en el mismo teléfono. Ese costo no se paga hasta que haya
un caso real que lo pida.

## Consecuencia para charadas

La señal de notoriedad que la dificultad necesita sale del índice IMDb, que pesa ~1,1 GB y
**no va al teléfono**. Por lo tanto la clasificación de dificultad se calcula **del lado
del servidor** y viaja como un campo chico por obra. Un teléfono nunca autónomo para
*clasificar*, sí autónomo para *jugar*. [G1] tiene que fijar ese campo.

## Enmienda del 2026-09-07: la cuenta es obligatoria

**Esta enmienda revierte una parte de la decisión original y cierra el punto 2 de lo que
quedaba abierto.** El owner decidió que **para usar la aplicación hay que tener una cuenta
creada en la instancia web**. El teléfono sigue funcionando sin conexión —ese punto no se
toca— pero ya no puede arrancar sin haber apareado al menos una vez.

### Qué deja de ser cierto

La sección 1 decía que crear un catálogo local sin instancia era "una entrada legítima, no
un modo degradado". **Deja de serlo.** La única entrada es: crear la cuenta en la web,
aparear por QR, y de ahí en adelante el teléfono se las arregla solo.

### Por qué es mejor, y no una restricción caprichosa

Elimina el problema más feo que arrastraba el diseño original: alguien crea datos en el
teléfono, después aparea, y hay que fusionar dos historias **que nunca compartieron una
base**. La fusión a tres bandas necesita una base común por definición; sin ella habría que
inventar una, y eso es la clase de decisión silenciosa que este proyecto evita.

Con cuenta obligatoria hay base común desde el primer minuto, y la sincronización pasa de
problema abierto a problema acotado.

### Qué reordena

El apareamiento era la entrega A2.4, después del almacén local y del juego. Ahora es **lo
primero**: sin aparear no hay cuenta, no hay datos y no hay aplicación. El plan de
construcción con el orden nuevo está en `docs/briefs/android-client-v3.md` del
repositorio del cliente, `movieIndexAndroid`, adonde se mudó el 2026-09-13.

### Qué no cambia

Todo lo demás de esta ADR sigue en pie: el teléfono es autónomo **después** de aparear, la
sincronización la inicia una persona y nunca borra, la convergencia es fusión a tres bandas
sin depender de relojes, el QR aparea y no transporta, dar de alta sin conexión produce un
borrador que no expira, y hay una cuenta por instalación.

## Qué queda abierto

1. **Autenticación local.** Con la cuenta viniendo de la instancia la identidad está
   resuelta, pero falta decidir si la aplicación quiere PIN o biometría propios además de la
   pantalla de bloqueo del teléfono. Las reviews y notas son datos personales y hoy en la
   web los protege una sesión.
2. ~~**Primer arranque.**~~ **Cerrado por la enmienda de arriba:** la única entrada es
   aparear contra una cuenta que ya existe. Queda como detalle menor qué pasa si alguien
   desaparea el teléfono — conservar los datos de sólo lectura y permitir volver a aparear
   es la respuesta razonable, pero conviene fijarla antes de A2.1.
3. **Varios teléfonos contra la misma instancia.** Funciona por construcción, porque la
   base de la fusión es **por par**, pero conviene fijarlo explícitamente antes de
   implementar.
4. **Llegar a la instancia desde la red local.** Si el certificado es de una CA pública para
   un dominio público, el teléfono en casa resuelve la IP pública y el router puede no hacer
   hairpinning. DNS de horizonte partido, o certificado autofirmado con su huella en el QR.
   Cambia lo que el QR lleva, así que se decide antes de A2.1.
