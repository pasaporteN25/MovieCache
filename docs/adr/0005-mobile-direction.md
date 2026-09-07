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

## Qué queda abierto

1. **Multi-usuario en el teléfono.** El owner habló de sincronizar "catálogos y usuarios".
   Si un teléfono guarda más de una cuenta, hace falta decidir aislamiento y cifrado en
   reposo. Este ADR asume **una cuenta por instalación** hasta que se resuelva.
2. **Qué tan lejos llega el offline.** Buscar en fuentes externas y enriquecer necesitan
   red por definición. Falta decidir si el teléfono puede dar de alta una obra sin
   metadata y completarla después, o si el alta exige conexión.
3. **Imágenes.** Las portadas son el grueso del tamaño. Falta decidir si viajan, se
   re-descargan o se degradan a un marcador.
4. **Plataforma.** Este ADR no elige entre Android nativo, KMP o PWA; fija el
   comportamiento que cualquiera de las tres tiene que cumplir. La elección depende de
   [MB2], la auditoría móvil con usuarios reales.
