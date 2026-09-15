# ADR-0006: Radarr como fuente de inventario de películas

- **Estado:** aceptada con condiciones — 2026-09-07
- **Tarea:** [I1]. Evaluación, sin implementación.
- **Evidencia:** `docs/analisis/i1-radarr-sonarr-letterboxd-2026-09-07.md`
- **Relacionadas:** ADR-0007 (Sonarr, misma API, veredicto distinto), ADR-0004 (plantilla).

## Contexto

El Scanner descubre archivos recorriendo un directorio y tiene que **adivinar qué obra es
cada archivo** a partir del nombre. Es el punto donde el invariante 3 más se tensiona: una
coincidencia dudosa va a revisión humana, y por eso la Bandeja existe.

Radarr resuelve ese mismo problema desde el otro lado. Descarga películas sabiendo de
antemano qué obra son, y guarda esa identidad.

## Decisión

**Aceptar Radarr como fuente de inventario opcional**, leyendo `/api/v3/movie`.

El argumento es uno solo y está medido: Radarr entrega `tmdbId`, que es la identidad fuerte
que `decide_match` ya reconoce. Un archivo que llega por Radarr empareja con
`shared_tmdb_id` a 1.0; el mismo archivo descubierto por el Scanner llega como un nombre a
interpretar. **Radarr no acelera el Scanner: le evita adivinar.**

No reemplaza al Scanner. Radarr sólo conoce lo que administra él, así que una película
copiada a mano al disco le es invisible. Son dos fuentes del mismo hecho y conviven.

## Condiciones de la aceptación

### 1. Es inventario, y sólo inventario

Alimenta `en_catalogo` —tener el archivo— y nada más. Nunca `to_watch` ni `watched`, que
son estado personal y que el invariante 2 obliga a mantener independientes. Radarr no sabe
si el owner vio la película; sabe que el archivo está.

### 2. Lo operativo no cruza a las vistas compartidas

`path`, `folderName` y `sizeOnDisk` son datos operativos. El invariante 4 los deja fuera de
Club sin excepción, y esto no crea una nueva: son exactamente la clase de dato que ya está
prohibida. Tampoco entran al catálogo portable.

### 3. La credencial se trata como la de TMDb

La clave de API va por el camino que fijó [F4.1]: archivo del lado del servidor, entrada
por el admin, nunca literal de CLI, formulario web, SQLite, catálogo, exportación, fixture
ni log. No pasa por el chat en ningún momento.

### 4. Falta decidir el transporte, y no es un detalle

Radarr casi siempre corre en la red local y casi siempre por `http`. La instancia hoy exige
HTTPS con certificado válido para lo que sale a internet. Una excepción para la red local
es defendible, pero **tiene que ser una decisión explícita y acotada**, no algo que se cuele
como configuración. Queda abierta.

### 5. Opt-in, y sin degradar a quien no lo tenga

Una instancia sin Radarr tiene que comportarse exactamente como hoy: sin accesos de red
nuevos, sin campos nuevos, sin advertencias. El precedente es el índice de IMDb.

## La compuerta que decide si esto se construye

**No sé si el owner corre Radarr.** Si no lo corre, esta integración vale cero y no debería
construirse por más limpia que sea la evidencia. Es la primera pregunta a contestar antes
de abrir la tarea de adaptador, y es del owner, no mía.

## Alternativas consideradas

| Opción | Veredicto |
| --- | --- |
| **Leer `/api/v3/movie` periódicamente** | **elegida**, es la superficie mínima |
| Webhook de Radarr (`On Import`) al servidor | reserva: más fresco, pero expone un endpoint de escritura y exige autenticar el que llama |
| No integrar y dejar sólo el Scanner | estado actual, sigue siendo válido si no hay Radarr |

El webhook es tentador porque evita el sondeo, pero abre una superficie de escritura que
hay que autenticar y limitar. Conviene sólo si la lectura periódica resulta insuficiente,
que todavía no está demostrado.

## Qué queda abierto

1. **Si el owner corre Radarr.** Bloquea todo lo demás.
2. **Transporte en red local** (condición 4).
3. **Qué gana la precedencia** cuando el Scanner y Radarr dicen cosas distintas del mismo
   archivo. Recomendación: Radarr, por traer identidad en vez de inferirla — pero es una
   decisión de producto y no debería quedar implícita en el orden de ejecución.
4. **Cada cuánto se lee**, y si un resultado se guarda fechado como hicieron [S3] y [F6.2].
   A diferencia de TMDb, acá no hay tope contractual de retención: el dato es del owner y
   está en su propia red.
