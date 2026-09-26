# [U7 B] Contrato y adquisición de imágenes — propuesta de lógica

**Fecha:** 2026-09-26. **Tareas:** [U7.2], [U7.3], [U7.4] (lógica) y el traspaso a
[U7.5b] (visual). **Estado:** opción A aprobada por el owner el 2026-09-26; cobertura real medida el mismo
día (abajo). Sin código todavía. El plan
(`docs/design/u7-u9-plan-2026-09-26.md`) pide ejemplos de payload y casos de
aceptación antes de implementar contrato o adquisición.

## Punto de partida verificado

- Cada obra tiene dos escalares: `page_image` (portada) y `backdrop_image`
  (panorámica). Ya tienen procedencia por campo (`metadata_sources`), bloqueo manual
  (`locked_fields`), export/import, SQLite y retirada de TMDb por procedencia.
- La contratapa (U7 A, `0970482`) ya dibuja 0/1/2 imágenes a partir de esos dos
  escalares, deduplicando tamaños de una misma imagen.
- **La llamada de detalle a TMDb ya pide las imágenes** (`append_to_response=…,images`,
  `include_image_language=es,en,null`), pero `tmdb_detail_result()` las descarta: sólo
  guarda el `poster_path`/`backdrop_path` por defecto. No hace falta una llamada nueva
  para tener candidatas.
- `backdrop_image` se puede corregir desde la ficha; `page_image` no está entre los
  campos editables (`EDITABLE_METADATA_FIELDS`).
- La panorámica sólo llega por TMDb. Wikipedia, IMDb y Jikan aportan portada.
- La herramienta de cobertura de U7.1 existe, pero **nunca corrió sobre el catálogo
  real** (U7.1c): no hay números de cuántas obras tienen identidad TMDb y les falta
  panorámica.

## Cobertura real — U7.1c, 2026-09-26

Corrida autorizada por el owner sobre la instancia nativa de Windows (catálogo JSON
registrado en su `instance.db`, caché de imágenes junto al catálogo). La herramienta
sólo lee: los archivos conservaron su fecha. Sólo se registran totales.

```
Total (2490 obras, incluye 31 de Club)
  Póster:      vacía 1140 · rechazada 0 · sin caché 516 · en caché 834
  Panorámica:  vacía 2490
  Imágenes distintas: 0: 1140 · 1: 1350 · 2: 0
  Identidad:   TMDb 0 · otra 1468 · ninguna 1022
```

Desglose de identidad del catálogo propio (2459 obras): IMDb 862, Wikidata 820
(606 sin IMDb), MyAnimeList 0, **TMDb 0**. En esta máquina tampoco hay token de TMDb
(`./secrets/` no existe).

**Consecuencia:** con la regla "sólo obras con `tmdb_id`", `fill` no completaría
ninguna obra. El camino real a las panorámicas pasa por **cruzar identidad por id**,
que se agrega como paso 0 más abajo. Las 1022 obras sin identidad no son un problema
de imágenes: les falta identidad y eso es revisión humana (invariante 3).

## Decisión central: ¿hace falta guardar una galería?

La preferencia registrada el 2026-09-12 es **dos imágenes distintas: portada +
panorámica**. Eso entra en los dos escalares que ya existen. Lo que falta no es
almacenamiento: es **llenarlos** cuando la identidad lo permite y **poder corregirlos**.

### Opción A — sin cambio de contrato (recomendada)

- Los escalares siguen siendo la selección. Ni `catalog.schema.json` (v10) ni SQLite
  cambian, y el cliente Android no se entera.
- Las candidatas se piden **bajo demanda** para la corrección, no se guardan.
- Procedencia, bloqueo, export/import y retirada de TMDb ya funcionan por campo.
- Límite: sin red o sin token no se pueden ver candidatas; lo guardado se sigue viendo.

### Opción B — galería persistida

- Campo nuevo `images` en el JSON portable (schema v11) y columna en SQLite (v7): lista
  acotada (≤ 8) de `{url, role, source, width, height, language}`; los escalares
  apuntan a la elegida.
- Sirve si más adelante se quieren más de dos imágenes, candidatas sin conexión o la
  galería en el cliente Android.
- Costo: migración, contrato versionado, retirada de TMDb extendida a la lista, y más
  superficie para Android (X11 sigue abierto).

La recomendación es A ahora; B se puede sumar después sin romper A, porque A no
inventa campos nuevos.

## Contrato propuesto (opción A)

### 1. Candidatas de una obra — `GET /api/items/{id}/image-candidates`

Sólo para obras del catálogo propio con `tmdb_id`. Club nunca.

```json
{
  "item_id": "a1b2c3",
  "identity": {"source": "tmdb", "media_type": "movie", "tmdb_id": "78"},
  "selected": {
    "page_image": {"url": "https://image.tmdb.org/t/p/w500/portada-ejemplo.jpg",
                   "source": "tmdb", "locked": false},
    "backdrop_image": {"url": "", "source": "", "locked": false}
  },
  "candidates": [
    {"role": "backdrop", "url": "https://image.tmdb.org/t/p/w780/panoramica-ejemplo.jpg",
     "key": "tmdb:/panoramica-ejemplo.jpg", "width": 3840, "height": 2160,
     "language": null, "votes": 12, "score": 5.6},
    {"role": "poster", "url": "https://image.tmdb.org/t/p/w500/portada-ejemplo.jpg",
     "key": "tmdb:/portada-ejemplo.jpg", "width": 2000, "height": 3000,
     "language": "en", "votes": 20, "score": 5.4}
  ],
  "attribution": "Imágenes provistas por TMDb.",
  "status": "ok"
}
```

- `status`: `ok`, `no_identity` (sin `tmdb_id`: 200 con lista vacía, no error),
  `unavailable` (TMDb apagado, sin token o caído: 200, lista vacía, reintentable),
  `rate_limited`.
- `key` es la identidad de la imagen sin tamaño: dos tamaños del mismo archivo son
  una sola candidata. Reusa las reglas de `image_coverage.py`.
- Orden estable: panorámicas sin texto primero (`language: null`), luego por votos y
  resolución; portadas en español, inglés y sin idioma, en ese orden.
- Máximo 8 por rol. Tamaños servidos: `w780` panorámica, `w500` portada.

### 2. Completar lo que falta — `POST /api/items/{id}/images/fill`

Lo llama la contratapa al abrirse si la obra tiene menos de dos imágenes. Es la
"prioridad de la obra consultada" del plan.

```json
// respuesta
{"filled": ["backdrop_image"], "kept": ["page_image"], "skipped_locked": [],
 "status": "ok", "item": { "...": "la obra actualizada" }}
```

- **Sólo completa vacíos.** Nunca reemplaza una URL existente ni toca un campo en
  `locked_fields` (invariante 5).
- Registra `metadata_sources[campo] = {"source": "tmdb", "url": <ficha TMDb>,
  "updated_at": …, "inferred": false}`. Así la retirada de TMDb lo borra como al resto.
- No usa título: sin `tmdb_id` devuelve `no_identity` y no hace nada (invariante 3).
- Un resultado negativo (TMDb no tiene panorámica) se recuerda por obra durante 7 días,
  en memoria del servidor, para no repetir la consulta cada vez que se abre la ficha.

### 3. Corregir — ficha editable existente

- `PATCH` de metadata con `page_image` o `backdrop_image` + bloqueo, como hoy la
  panorámica. Se agrega `page_image` a `EDITABLE_METADATA_FIELDS`.
- Elegir una candidata = guardar su URL y bloquear el campo. Pegar una URL manual
  sigue permitido (fuente `manual`), sujeta a la lista de hosts del proxy.
- Desbloquear y vaciar el campo permite que `fill` vuelva a completarlo.

### 4. Lote explícito — `movie-inbox images fill`

- CLI con `--limit` obligatorio (por ejemplo 50) y `--dry-run`, para el owner. Sólo
  obras con `tmdb_id`, mismo criterio fill-only, respetando el backoff de TMDb.
- Nunca corre sola: no hay calentamiento masivo automático.

## Casos de aceptación

| # | Situación | Resultado esperado |
| --- | --- | --- |
| 1 | Obra con `tmdb_id`, portada llena, panorámica vacía | `fill` guarda la mejor panorámica sin texto; procedencia `tmdb`; la contratapa pasa de 1 a 2 imágenes. |
| 2 | Panorámica bloqueada y vacía | `fill` no la toca (`skipped_locked`). |
| 3 | Panorámica manual existente | `fill` no la reemplaza aunque TMDb tenga otra. |
| 4 | Obra sin `tmdb_id`, con IMDb | `no_identity`; nada cambia; nunca se busca por título. |
| 5 | Obra de Club | Ni candidatas ni `fill`: 404 como cualquier obra ajena. |
| 6 | TMDb sin token, apagado o caído | `unavailable`; la contratapa sigue igual y se puede reintentar. |
| 7 | Mismo póster en `w500` y `original` | Una sola candidata (`key` igual). |
| 8 | TMDb no tiene panorámica | Se recuerda 7 días; no se repite la consulta al reabrir. |
| 9 | Retirada de TMDb | Las imágenes con procedencia `tmdb` se borran; las manuales quedan. |
| 10 | Export → import | Las URLs, su procedencia y los bloqueos vuelven iguales (ya cubierto hoy). |
| 11 | Dos aperturas rápidas de la misma obra | Un solo `fill` en vuelo por obra; la segunda espera el mismo resultado. |
| 12 | Elegir una candidata desde la ficha | Queda guardada y bloqueada; `fill` ya no la cambia. |

## Paso 0 — cruce de identidad por id (nuevo, a decidir)

Ninguna búsqueda por título. Sólo traducción entre ids que ya están en la obra:

- **IMDb → TMDb:** `GET /find/{imdb_id}?external_source=imdb_id` (862 obras).
- **Wikidata → TMDb:** propiedades P4947 (película) y P4983 (serie) de la entidad que
  la obra ya tiene (606 obras más, sin IMDb).

Regla propuesta: se guarda `tmdb_id` sólo si hay **un único resultado** y coincide
el **tipo** (película/serie) y el **año** con tolerancia de ±1. Cualquier otra cosa
(cero o varios resultados, tipo o año distintos, IMDb y Wikidata que apuntan a obras
diferentes) no se escribe y queda para Curaduría. Procedencia `tmdb` con
`inferred: true` para que se distinga de una identidad elegida a mano, y la retirada
de TMDb la borra junto con lo demás. `tmdb_id` bloqueado nunca se toca.

Corre sólo por el mismo lote explícito (`movie-inbox images fill --limit N`), nunca
en segundo plano. Requiere TMDb activo en la instancia donde corra.

## Lo que necesito del owner antes de implementar

1. ~~Opción A o B~~ — **A**, aprobada el 2026-09-26.
2. ~~Cobertura real~~ — medida el 2026-09-26 (arriba).
3. **Paso 0, cruce de identidad por id.** Sin él la entrega no llena ninguna obra.
   Propuesta: incluirlo con la regla de arriba (único resultado, tipo y año ±1).
4. **Dónde corre TMDb.** El token tiene que estar en la instancia real: la nativa de
   Windows o la de Docker en Linux. Va en `./secrets/`, como documenta
   `docs/docker.md`, en cualquiera de los dos casos.
