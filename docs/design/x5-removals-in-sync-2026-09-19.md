# [X5] Bajas que viajan en la sincronización — diseño

**Fecha:** 2026-09-19. **Estado:** propuesta que se implementa por partes; las decisiones
marcadas como revisables las puede cambiar el owner sin rehacer lo demás. Aplica la enmienda
del 2026-09-14 de ADR-0005: *los borrados viajan*, sólo como registro explícito, y unir
duplicados cuenta como borrar el duplicado.

## Qué pasa hoy

- **Borrar** (`CatalogService.delete_item`) quita la fila y no deja nada. Un teléfono que tenía
  la obra ve un 404 en su `GET`, igual que si nunca hubiera existido.
- **Unir** (`CurationWorkflowService.merge`, `merge_group`, `auto_resolve_duplicates`) deja
  una obra y hace desaparecer las otras. La historia de Curaduría guarda el antes y el después
  para poder deshacer, pero es del servidor y no sale por la API.
- **Deshacer** en Curaduría devuelve las obras con el mismo `id`.
- El id que ve el teléfono (`_opaque_item_id`) es un HMAC de `(cuenta, posición de la fuente,
  id de la obra)` con el secreto durable de la instancia.

## Qué se decide

### 1. Dónde vive el registro: `instance.db`, no el catálogo

Una tabla `device_removals` en `instance.db`, como la de recibos ([X6]). Un registro es
`(catalog_id, device_id) → motivo, unida_a, fecha`, con **el id opaco que el teléfono conoce**,
no el id interno.

Por qué no en cada catálogo: hay dos formatos de almacén (JSON y SQLite) y el registro es
estado de sincronización, no dato de la obra. Ponerlo en el catálogo obliga a subir el esquema
portable (`catalog.schema.json`, v11) para algo que no es contrato de obras, y a repetirlo en
las dos implementaciones. **Costo asumido:** la baja y su registro son dos escrituras en dos
bases, sin transacción común. Se borra primero y se registra después, así que la falla
posible es una baja **sin** registro. Eso degrada al caso de hoy (404, la persona decide en el
teléfono) y nunca inventa una baja: un registro sin baja no puede pasar.

### 2. Qué cuenta como baja

Sólo lo que una persona hizo por un camino explícito de la aplicación:

| Camino | Registro |
| --- | --- |
| Borrar una obra en la web | `deleted` |
| Borrar desde un teléfono (ver 5) | `deleted` |
| Unir dos obras, o un grupo, en Curaduría (manual o con "resolver los seguros") | `merged`, con la obra que quedó |

Y al revés: **deshacer** una unión devuelve las obras, así que borra sus registros. Además el
consultar da prioridad a lo que existe: si un id está en el catálogo, está presente aunque
sobre un registro.

**Fuera de alcance, anotado:** deshacer una operación del Scanner también quita obras que la
operación había creado. No se registra: esas obras las agregó un proceso, no una decisión
sobre una obra, y un teléfono que ya las bajó las ve como "ausentes sin registro", que es el
camino seguro.

### 3. Cómo pregunta el teléfono

`POST /api/v1/catalog/items/status` con hasta 100 ids, y por cada uno:

| `state` | Quiere decir | Qué hace el teléfono |
| --- | --- | --- |
| `present` | Sigue en el catálogo | Nada |
| `removed` | Una persona la quitó (`reason`: `deleted` o `merged`, con `merged_into` y `removed_at`) | Aplica la baja; si tenía cambios pendientes: `deleted` → decide la persona; `merged` → pasan a `merged_into` |
| `unknown` | Ni está ni hay registro | **Nunca se borra**: sigue el camino de hoy ("ya no está en tu instancia") |

Es una ruta nueva y **no** un 410 en `GET /items/{id}`: el 404 de esa ruta ya está en el
contrato, y cambiar lo que responde rompería a un cliente fiel a él (ADR-0003: sólo aditivo).
Es del mismo estilo que los recibos de altas ([X6.3]).

Una unión encadenada (A→B y después B→C) se responde con el final: `merged_into` es la última
obra de la cadena que se conoce, y si esa también se borró el `state` es `removed` con
`deleted`. Si el final de la cadena no tiene registro (por ejemplo, ya pasó el plazo del
punto 4), se devuelve tal cual y el teléfono pregunta por esa obra a su vez.

### 4. Cuánto duran los registros

**365 días**, como los recibos resueltos. La llave de un teléfono vence al mes de la última
sincronización y un teléfono que vuelve a aparear la misma cuenta conserva sus datos, así que el
plazo tiene que cubrir con margen el peor caso razonable. *Revisable.*

Pasado el plazo el registro se olvida y la respuesta es `unknown`. No hay una bandera de "mi
registro no llega tan atrás": un `unknown` ya significa "no lo borres", y ese es el
comportamiento correcto para un teléfono que estuvo un año sin sincronizar.

### 5. Bajas desde el teléfono

`POST /api/v1/catalog/items/{itemId}/removal` con `{"base": {...}}` o `{"force": true}`.

- **Sin `base` ni `force`** es un 400: una baja sin saber qué vio el teléfono no se aplica
  sola. Y la `base` tiene que traer los **cuatro** campos: una parcial (sólo el puntaje) no
  prueba lo que el teléfono vio y dejaría borrar una obra que alguien acaba de reseñar.
- **La regla del owner** —*una baja sobre una obra que se editó en el servidor después de la
  última sincronización de ese teléfono no se aplica sola*— se lee sobre el estado personal:
  si `status`/`watched_at`, `rating` o `review` valen hoy otra cosa que en la `base` (las mismas
  cuatro que ya entiende el `PATCH`, con la misma comparación normalizada de [X2]), la
  respuesta es **409 `removal_conflict`** y no se borra nada. Como con `personal_conflict`, el
  teléfono relee la obra con su `GET`; decide la persona, en el teléfono: conservar la obra, o
  repetir con `force: true`. La comprobación y el borrado ocurren en una sola transacción del
  repositorio, así que una edición no puede colarse en el medio.
- No se mira el resto de la ficha: enriquecer o corregir metadatos no es "editar la obra" en el
  sentido del owner. *Revisable.*
- **Idempotente:** pedir la baja de lo que ya está dado de baja responde 200, con cómo se fue
  (si se había unido a otra, lo dice: nunca se borra la que quedó). Un reintento después de un
  corte no puede fallar por haber funcionado.
- Una obra que no existe y no tiene registro es 404 `item_not_found`, como el resto.

### 6. El identificador durable que sugirió el owner

Evaluado, y **no hace falta para las bajas**. Lo que ya es durable y lo que no:

- El `id` interno de una obra **ya es durable**: se calcula una vez al crearla (hash de su URL,
  ruta o título y año), se guarda, y sobrevive a ediciones, enriquecimiento y a ser la obra
  que queda de una unión.
- Lo frágil es el id **del teléfono**, porque incluye la **posición de la fuente**
  (`source-1`, `source-2`): quitar o reordenar una fuente cambia todos los ids (caso 17).
  Las bajas registradas antes de ese cambio quedan viejas al mismo tiempo que la réplica, y el
  cliente ya frena ante un cambio masivo de ids.

Tres caminos, por costo:

| | Qué arregla | Costo |
| --- | --- | --- |
| **A. Dejarlo** | Nada más; las bajas funcionan | Cero |
| **B. Un id durable por fuente**, en lugar de la posición | El caso 17 de raíz, sin tocar las obras | Un campo en el almacén de cada catálogo (esquema portable v11 y SQLite v7) y una migración; los ids del teléfono cambian una vez |
| **C. Un uid nuevo por obra** (la idea del owner) | El caso 17, y la unicidad entre fuentes | Lo de B, más un campo por obra que hoy es el `id`, en importadores, snapshots de Curaduría y exportación |

**Recomendación: A ahora, B como tarea propia** (anotada como [X11]) **antes de que salga el
primer cliente instalado**, porque cambiar la derivación después obliga a una re-descarga y deja
huérfanos los cambios pendientes. C no compra nada que B no dé: el `id` de la obra ya cumple lo
que C pediría. Es una decisión del owner; nada de [X5] depende de ella, porque el registro se
guarda con el id que el teléfono ya conoce.

**Decidido el 2026-09-20: B, un id por fuente** ([X11]). No entra en la 0.9.0: es un requisito
para publicar el cliente Android (su v0.1.0). Cuando se haga, los registros de bajas, que
guardan el id derivado, se recalculan o se dejan caducar.

## Cómo se parte

1. **[X5.1]** Este diseño y la subdivisión.
2. **[X5.2]** El registro: tabla `device_removals` (esquema v23), su repositorio y el servicio.
3. **[X5.3]** Registrar al borrar una obra en la web.
4. **[X5.4]** Registrar al unir obras en Curaduría, y olvidar al deshacer.
5. **[X5.5]** La consulta `POST /api/v1/catalog/items/status`, con contrato y pruebas.
6. **[X5.6]** La baja desde el teléfono, con su conflicto.
7. **[X5.7]** Changelog y cierre.
