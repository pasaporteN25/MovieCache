# [I1] Radarr, Sonarr y Letterboxd — matriz y evidencia medida

**Fecha:** 2026-09-07. **Tarea:** [I1], evaluación sin implementación.
**Decisiones:** ADR-0006 (Radarr), ADR-0007 (Sonarr), ADR-0008 (Letterboxd).
**Plantilla:** la misma de [S2] / ADR-0004, por decisión registrada en el backlog.

## Qué se midió, y qué no

Las tres integraciones se evaluaron **contra el código real de Movie Inbox**: qué decide
`decide_match`, qué reconoce `external_source_name`, qué parsea `parse_import_content`.
Eso está medido y es reproducible.

Lo que **no** está medido es el otro lado: no hay una instancia de Radarr ni de Sonarr en
esta máquina, y no se pidió ni se usó ninguna exportación de Letterboxd del owner. Los
datos de esas tres fuentes se construyeron sintéticamente **con la forma que documenta
cada proveedor**, y la forma sí está verificada contra su documentación al 2026-09-07.

Esta es una diferencia real con [S2], donde sí se midió contra la API viva de TMDb. Lo que
sigue vale para decidir si vale la pena construir; una activación tendría que revalidarse
contra una instancia real, exactamente como [F5.4] hizo con TMDb.

## Los tres no son la misma clase de cosa

El alcance de [I1] pide separar tres usos que se confunden fácil, y el reparto no es
parejo:

| | Qué aporta | Capa que toca | Corre en |
| --- | --- | --- | --- |
| **Radarr** | inventario de películas | operativa (`en_catalogo`) | la red local |
| **Sonarr** | inventario de series | operativa (`en_catalogo`) | la red local |
| **Letterboxd** | historial personal | personal (`watched`, `rating`, `review`) | la nube, cuenta ajena |

Radarr y Sonarr compiten con el **Scanner**. Letterboxd compite con la **capa personal**.
Que estén en la misma tarea es un accidente del backlog, no un parecido real.

## Matriz

| Criterio | Radarr | Sonarr | Letterboxd |
| --- | --- | --- | --- |
| Acceso | API local, sin invitación | API local, sin invitación | **API sólo por invitación**, sin garantía |
| Autenticación | `X-Api-Key` | `X-Api-Key` | OAuth2 (si te aprueban) |
| Licencia del producto | GPL-3.0 | GPL-3.0 | servicio propietario |
| Identidad primaria | **`tmdbId`** | `tvdbId` | ninguna: título, año y un slug |
| ¿La reconoce el proyecto? | **sí**, es la identidad fuerte | **no**, TVDB no existe acá | **no** |
| Emparejamiento medido | `shared_tmdb_id`, 1.0 | `shared_tmdb_id` si viene; si no, título+año | título+año, sin desempate posible |
| Unidad de archivo | película = obra | **episodio ≠ obra** | no aplica |
| Webhooks | sí (Connect) | sí (Connect) | no |
| Rate limit | ninguno documentado (es local) | ninguno documentado (es local) | el que imponga la aprobación |
| Costo para el owner | ya lo corre o no | ya lo corre o no | **export requiere Pro** |
| ¿Sale dato personal de la instancia? | **no** | **no** | **no**, en el sentido de lectura |
| Veredicto | **aceptada con condiciones** | **rechazada por ahora** | **rechazada como integración** |

## Evidencia medida

### Radarr: cae justo en la identidad fuerte que el proyecto ya tiene

`/api/v3/movie` devuelve por película `tmdbId`, `imdbId`, `title`, `year`, `hasFile`,
`sizeOnDisk`, `path`, `folderName` y `monitored`. `tmdbId` es su clave primaria: Radarr
está construido sobre TMDb.

Eso importa porque `domain/matching.py` ya trata `tmdb_id` como identidad fuerte. Medido
con una respuesta con la forma documentada:

```
accepted=True  reason=shared_tmdb_id  score=1.0
```

Es el camino más fuerte que tiene `decide_match`, y es exactamente el que el Scanner **no**
puede tomar: el Scanner parte de un nombre de archivo y tiene que adivinar el título. La
diferencia no es de comodidad, es de calidad de identidad. Radarr sabe qué obra es cada
archivo porque él mismo la descargó sabiéndolo.

**Lo que Radarr no resuelve:** sólo conoce lo que administra él. Una película copiada a
mano al disco le es invisible. No reemplaza al Scanner; cubre otra parte del mismo estante.

### Sonarr: la misma API, dos problemas que no son de plomería

El recurso `/api/v3/series` trae `tvdbId`, `imdbId` y `tmdbId`. Medido:

```
con tmdbId presente:   accepted=True  reason=shared_tmdb_id
con tvdbId solamente:  accepted=True  reason=exact_title_year
```

**Primer problema: TVDB no existe en este proyecto.** `EXTERNAL_LINK_HOSTS` conoce
Wikipedia, IMDb, FilmAffinity, MyAnimeList y TMDb. Medido:

```
https://thetvdb.com/series/the-sopranos   -> ''
https://www.themoviedb.org/tv/1398        -> 'tmdb'
```

La clave primaria de Sonarr es la única de las tres que el catálogo no sabe leer. Cuando
`tmdbId` viene, no hay problema; cuando no viene —y arriba es opcional— el emparejamiento
cae a título+año, que es más débil.

**Segundo problema, el que de verdad bloquea: la unidad no coincide.** Movie Inbox razona
por obra; Sonarr guarda archivos por episodio, y lo informa como `episodeFileCount` sobre
`totalEpisodeCount`. Medido sobre un caso realista:

```
3/86 episodios = 3.5%
```

`en_catalogo` es un booleano. Decir `en_catalogo: true` para una serie con 3 de 86
episodios le dice al usuario algo falso, y decir `false` también. **No hay respuesta
correcta con el modelo actual**, y eso es un problema de la clase que protege el invariante
2: la terminología tiene que significar una sola cosa.

### Letterboxd: el export no trae ningún identificador

El export son cinco CSV. `diary.csv` tiene estas columnas, y ninguna más:

```
Date, Name, Year, Letterboxd URI, Rating, Rewatch, Tags, Watched Date
```

No hay `tmdbId` ni `imdbId`. La `Letterboxd URI` es un acortador (`boxd.it/2a1b`) o un slug
(`letterboxd.com/film/heat-1995/`). Medido contra el propio proyecto:

```
https://boxd.it/2a1b                    external_source_name=''  trusted=''
https://letterboxd.com/film/heat-1995/  external_source_name=''  trusted=''
```

Ninguna de las dos es una fuente externa reconocida. Resolverlas a un `tmdb_id` exige
**abrir la página y leer el HTML**, que es scraping — el mismo criterio por el que ADR-0004
descartó JustWatch siendo la fuente original del dato.

**Qué pasa hoy si se importa igual.** El parser existente lo acepta sin tocar nada: las
tres filas se parsean, `Name` y `Year` caen solos en `title` y `year` por `CSV_ALIASES`, y
`Watched Date` necesita un `column_map` explícito. Y el emparejamiento se porta mejor de lo
esperado:

```
titulo ingles del export contra ficha en castellano:
  accepted=True  reason=exact_title_year  score=1.0
```

Los títulos alternativos de la ficha hacen el trabajo: `The Secret in Their Eyes` encuentra
`El secreto de sus ojos`. Ese era el riesgo más obvio y **no** se materializa.

El riesgo que sí queda es el homónimo:

```
homonimo sin IDs del lado entrante: accepted=True  reason=exact_title_year
```

Dos obras distintas con el mismo título y el mismo año se aceptan como la misma, y el CSV
**no tiene con qué desempatar**. Es el mismo techo que ya tiene cualquier importación TXT,
no una regresión; pero es la razón por la que esto no puede correr sin una persona mirando.

## Sobre las licencias

Radarr y Sonarr son GPL-3.0, igual que Movie Inbox. De todos modos la pregunta no se
plantea: consumir una API REST por HTTP no crea una obra derivada del servidor, así que la
licencia de ellos no alcanza a este proyecto por esta vía. Investigación de términos, no
asesoramiento legal.

Letterboxd es un servicio propietario y su API tiene términos que sólo se conocen al ser
aprobado. Eso es parte de por qué no puede ser una dependencia.

## Sobre datos personales que salen de la instancia

El alcance de [I1] pide mirarlo explícitamente, y la respuesta es más simple de lo que
parece: **en ninguna de las tres formas aceptadas sale nada**.

- Radarr y Sonarr corren en la red local del owner. La instancia les pregunta; no les
  cuenta nada.
- El camino aceptado de Letterboxd es leer un archivo que el owner ya descargó. Leer no
  es publicar.

La única variante donde saldría dato personal es **escribir** hacia Letterboxd —marcar
vistas, subir puntajes—, y queda explícitamente fuera de las tres decisiones.

## Fuentes

Documentación verificada el 2026-09-07:
[API de Letterboxd (por invitación)](https://letterboxd.com/api-beta/),
[copia de tus datos de cuenta](https://letterboxd.zendesk.com/hc/en-us/articles/15179196880911-Can-I-get-a-copy-of-my-account-data),
[importar datos a Letterboxd](https://letterboxd.com/about/importing-data/),
[objetos Movie y Series de Radarr/Sonarr](https://arrapi.kometa.wiki/en/latest/objs.html),
[wiki de Servarr](https://wiki.servarr.com/radarr/system),
[licencia de Radarr](https://github.com/Radarr/Radarr/blob/develop/LICENSE) y
[licencia de Sonarr](https://github.com/Sonarr/Sonarr/blob/develop/LICENSE.md).
