# [U7.1] Diagnóstico de cobertura de imágenes

**Fecha:** 2026-09-12. **Tarea:** [U7.1], primera parte de [U7] ("Completar las dos
ventanas de imágenes de consola"). El plan de la épica está en
`docs/design/home-evolution-backlog-2026-09-12.md`, que le asigna a lógica la identidad,
el contrato y la adquisición, y al frente visual el consumo y los estados.

**Estado:** la herramienta está entregada y probada sobre catálogos sintéticos. **Falta
la corrida sobre el catálogo real**, que toca datos personales y espera la autorización
del owner. Hasta esa corrida no hay números que entregarle a [U7.2]: lo que sigue explica
qué va a medir y cómo leerlo.

## Qué mide

Por cada obra, las dos ranuras que hoy alimentan las ventanas de la consola,
`page_image` y `backdrop_image`. Cada una queda en uno de cuatro estados:

| Estado | Qué significa | Qué lo arregla |
| --- | --- | --- |
| **vacía** | El campo no tiene dirección. | Adquisición: [U7.2]. |
| **rechazada** | Hay dirección, pero el proxy no la serviría: host fuera de la lista permitida, esquema o puerto no estándar, credenciales en la URL. | La lista de hosts o una dirección mal cargada. No hace falta ningún proveedor. |
| **sin caché** | El proxy la serviría, pero todavía no se descargó: la primera vista la baja. | El calentador de caché, no la adquisición. |
| **en caché** | Lista para mostrarse sin salir a la red. | — |

"Rechazada" usa **las mismas reglas que `serve`**: la misma validación de direcciones y
la misma lista de hosts, incluidos los que se agregan con `--image-host`. Así el número
dice exactamente lo que el servidor rechazaría, y no una aproximación.

Además de los estados cuenta tres cosas:

- **Imágenes distintas por obra, de 0 a 2.** Dos tamaños de la misma imagen cuentan como
  una: el mismo póster de TMDb en `w500` y en `original`, una miniatura de Wikimedia y su
  archivo, las variantes `_V1_` de Amazon para IMDb, y los tamaños de FilmAffinity y de
  MyAnimeList. Un host desconocido no se pliega nunca: ante la duda, el diagnóstico
  prefiere decir que son dos imágenes distintas antes que prometerle a la consola una
  segunda ventana que no existe.
- **Identidad**: **TMDb** (tiene `tmdb_id` o enlace a TMDb), **otra** (IMDb, Wikidata o
  MyAnimeList, sin TMDb) o **ninguna**. Un título que parece correcto no cuenta como
  identidad.
- **Con menos de dos imágenes, por identidad**: las obras que no llenan las dos ventanas,
  separadas por identidad. Es el número del que arranca [U7.2].

Todo sale por **origen** —catálogo o Club— y por **tipo** —película, serie, anime,
documental—. Club son las colecciones que la cuenta puede abrir, y cada obra cuenta una
sola vez aunque esté en varias listas, con la misma clave entre almacenes que usa el mazo
de charadas.

## Qué no mide, y por qué

Sin red **no se puede distinguir**:

- una dirección que ahora responde 404;
- un proveedor caído;
- un proveedor que no tiene imagen para esa obra.

El calentador de caché lleva la cuenta de sus fallas sólo en memoria, mientras el servidor
corre, así que tampoco hay un registro que leer después. Esas tres causas son de [U7.2]:
se miden sobre una muestra chica y con autorización para salir a la red, nunca
descargando el catálogo entero.

## Cómo leer el resultado

| Lo que aparece | Qué quiere decir para [U7.2] y [U7.3] |
| --- | --- |
| Muchas obras **TMDb** con menos de dos imágenes | Son candidatas directas a `/movie/{id}/images` o `/tv/{id}/images`: la identidad está confirmada y se puede preguntar por id. |
| Muchas con **otra** identidad | Antes de pedir imágenes hay que llegar a una identidad TMDb por un id que ya se tiene (IMDb o Wikidata), u otro proveedor. Nunca por título. |
| Muchas con **ninguna** | La imagen no es el problema: falta identidad, y eso va a revisión humana (invariante 3). |
| Muchas **rechazadas** | No es adquisición: es la lista de hosts o direcciones mal cargadas. |
| Muchas **sin caché** | Tampoco es adquisición: es el calentador. |
| El hueco concentrado en un **tipo** | Probablemente ese tipo necesita otra fuente, y [U7.2] tiene que evaluarla aparte. |

## Cómo se ve, sobre un catálogo sintético

Nueve obras inventadas en el catálogo y dos en una colección de Club; ninguna es del
catálogo del owner. Salida completa del total y de un segmento:

```
Cobertura de imágenes: 11 obras, sin descargar nada.

Total (11 obras)
  Póster:      vacía 4 · rechazada 1 · sin caché 3 · en caché 3
  Panorámica:  vacía 9 · rechazada 0 · sin caché 1 · en caché 1
  Imágenes distintas: 0: 5 · 1: 5 · 2: 1
  Identidad:   TMDb 6 · otra 3 · ninguna 2
  Con menos de dos imágenes, por identidad: TMDb 5 · otra 3 · ninguna 2

Catálogo, película (6 obras)
  Póster:      vacía 2 · rechazada 1 · sin caché 1 · en caché 2
  Panorámica:  vacía 4 · rechazada 0 · sin caché 1 · en caché 1
  Imágenes distintas: 0: 3 · 1: 2 · 2: 1
  Identidad:   TMDb 4 · otra 1 · ninguna 1
  Con menos de dos imágenes, por identidad: TMDb 3 · otra 1 · ninguna 1
```

Los demás segmentos siguen igual: serie, anime y documental del catálogo, y película de
Club. En el ejemplo, una de las dos imágenes "distintas" que se esperarían de la segunda
película es el mismo póster pedido en dos tamaños, y cuenta como una.

## Cómo correrlo

Con las mismas rutas que usa `serve` para esa instancia:

```
movie-inbox images coverage <catálogo> --instance-db <instance.db>
```

- `--image-cache-dir` y `--image-host` funcionan igual que en `serve`. Sin
  `--image-cache-dir`, busca `.catalog-cache/images` junto al catálogo, como `serve`.
- `--user` elige la cuenta cuyas colecciones de Club se cuentan; sin él, la del owner.
- `--json` imprime lo mismo en JSON, para guardarlo o compararlo después.

**No descarga nada ni consulta a ningún proveedor**, y **sólo imprime totales**: no nombra
títulos, direcciones ni rutas. La salida se puede compartir sin compartir el catálogo.

## Lo que sigue

1. **Corrida real**, con autorización del owner.
2. Con esos números, **[U7.2]**: medir sobre una muestra chica las causas que necesitan
   red, y evaluar las imágenes de TMDb sobre identidad confirmada.
