# ADR-0007: Sonarr como fuente de inventario de series

- **Estado:** rechazada por ahora, con condición de reapertura — 2026-09-07
- **Tarea:** [I1]. Evaluación, sin implementación.
- **Evidencia:** `docs/analisis/i1-radarr-sonarr-letterboxd-2026-09-07.md`
- **Relacionadas:** ADR-0006 (Radarr, misma API, aceptada).

## Contexto

Sonarr es el hermano de Radarr para series: mismo linaje de código, misma API, misma
autenticación por `X-Api-Key`, misma licencia. La expectativa razonable era que el
veredicto fuera el mismo.

No lo es, y el motivo no es la API.

## Decisión

**No integrar Sonarr todavía.** No por calidad de la fuente, sino porque el modelo de datos
de Movie Inbox no puede expresar hoy lo que Sonarr tiene para decir.

## Los dos motivos, en orden de importancia

### 1. La unidad de archivo no coincide con la unidad de obra

Este es el que bloquea.

Movie Inbox razona por **obra**: una serie es una fila del catálogo, y `en_catalogo` dice
si el owner la tiene. Sonarr guarda archivos por **episodio**, y lo informa como
`episodeFileCount` sobre `totalEpisodeCount`. Medido sobre un caso realista: **3 de 86
episodios, 3,5 %**.

`en_catalogo` es un booleano. Para esa serie:

- `true` le dice al usuario que la tiene, y no la tiene.
- `false` le dice que no tiene nada, y tiene tres episodios.

**Ninguna de las dos respuestas es cierta.** No es un caso borde: una serie a medio
descargar es el estado normal de una serie. Y es un problema de la clase que protege el
invariante 2, donde la terminología tiene que significar una sola cosa y no puede
estirarse según convenga.

Integrar Sonarr antes de resolver esto obligaría a elegir una mentira cómoda, que es
exactamente lo que el proyecto viene evitando en `en_catalogo`, en `en_plataforma` y en el
`known: false` de disponibilidad.

### 2. La clave primaria de Sonarr es la única que el proyecto no sabe leer

Sonarr está construido sobre TVDB. `EXTERNAL_LINK_HOSTS` conoce Wikipedia, IMDb,
FilmAffinity, MyAnimeList y TMDb — no TVDB. Medido:

```
https://thetvdb.com/series/the-sopranos   -> ''   (no es fuente reconocida)
https://www.themoviedb.org/tv/1398        -> 'tmdb'
```

El recurso de serie **sí** trae `tmdbId` e `imdbId`, y cuando vienen el emparejamiento es
fuerte (`shared_tmdb_id`). Pero arriba son secundarios y opcionales, y cuando falta
`tmdbId` la coincidencia cae a título+año.

Esto es reparable —se podría agregar TVDB como identidad reconocida— pero es trabajo real
y no tiene sentido hacerlo antes de resolver el punto 1.

## Qué reabriría esta decisión

Una sola cosa, y es de producto, no de código:

> **Decidir qué significa "tener" una serie parcialmente descargada**, y cómo se le muestra
> a alguien.

Las salidas posibles, sin recomendación fuerte porque la decisión es del owner:

- Un tercer estado de disponibilidad para series (*parcial*), con el conteo al lado. Es lo
  más honesto y lo más caro: toca el esquema portable, que hoy está en v9.
- Un umbral configurable, del estilo del `max_missing_ratio` que ya existe en bibliotecas
  administradas. Barato, pero sigue colapsando un conteo en un booleano.
- Tratar la serie como disponible si hay al menos un episodio, y decir el conteo aparte.
  Es la lectura más laxa y la que más se parece a lo que hace el Scanner hoy.

Con esa decisión tomada, Sonarr vuelve a la mesa y la parte técnica es corta: la API ya
está entendida y el adaptador se parece mucho al de Radarr.

## Lo que no es motivo de rechazo

Conviene dejarlo escrito para que nadie lo relitigue: la API de Sonarr es buena, es local,
no tiene rate limit relevante, no saca dato personal de la instancia y su licencia GPL-3.0
no alcanza a este proyecto por consumir su API. Nada de eso es el problema.
