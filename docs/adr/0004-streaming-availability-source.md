# ADR-0004: Fuente de disponibilidad en plataformas de streaming

- **Estado:** aceptada con condiciones — 2026-09-07
- **Tarea:** [S2]. Evaluación, sin implementación. La implementación queda en [S3].
- **Depende de:** [F5.4], que dejó la credencial de TMDb operativa. Sin ella esta
  evaluación no era contestable.
- **Precede a:** [S1] (nombres y semilla de plataformas) y [S3] (consulta y persistencia).

## Contexto

El owner quiere saber si un título de su catálogo está disponible en una plataforma de
streaming en Argentina, con una tolerancia declarada de desfasaje de **1 a 2 meses**. Las
plataformas de interés inicial son Netflix, Prime Video, HBO Max, Paramount+, Apple TV+ y
Disney+. El modelo debe admitir más países desde un back office.

Esta evaluación se hizo **contra la API real**, no contra documentación. Los números de
abajo son mediciones del 2026-09-07 y son una foto: la disponibilidad cambia por
definición.

## Decisión

**Usar TMDb como fuente de disponibilidad**, mediante los endpoints
`/watch/providers/regions`, `/watch/providers/movie|tv` y
`/{movie|tv}/{id}/watch/providers`. Los datos son de JustWatch, servidos por TMDb.

No hace falta credencial nueva, adaptador nuevo, host nuevo en la allowlist ni presupuesto
de rate limit adicional: reutiliza por completo lo que [F5.1]–[F5.3] ya construyeron.

## Evidencia medida

### Región

Argentina está soportada. `/watch/providers/regions` devuelve **139 regiones**, con
`AR` presente. El modelo multi-país de [S1] tiene sustento real.

### Plataformas en Argentina

`/watch/providers/movie?watch_region=AR` devuelve **59 proveedores**. De los seis pedidos:

| Plataforma pedida | Presente | Nombre exacto en la API |
| --- | --- | --- |
| Netflix | sí | `Netflix` |
| Prime Video | sí | `Amazon Prime Video` |
| HBO Max | sí | `HBO Max` |
| Paramount+ | sí | `Paramount Plus` |
| Disney+ | sí | `Disney Plus` |
| Apple TV+ | sí, con trampa | `Apple TV` |

**Trampa de nomenclatura, relevante para la semilla de [S1]:** la API no usa `Apple TV+`
ni `Max`. El servicio por suscripción de Apple aparece como **`Apple TV`**, mientras que
`Apple TV Store` es alquiler/compra y `Apple TV Amazon Channel` es un canal revendido. Una
coincidencia por subcadena sobre `"Apple TV"` los confunde a los tres. Los nombres tienen
que guardarse literales y verificarse contra la API, no escribirse de memoria.

### Estructura de la respuesta

Por país, la respuesta trae `link` más hasta cinco categorías de oferta: `flatrate`
(incluido en suscripción), `rent`, `buy`, `ads` (gratis con publicidad) y `free`.

El `link` apunta a `themoviedb.org/.../watch?locale=AR`, no a JustWatch.

**Consecuencia de producto:** `flatrate` y `rent` no significan lo mismo. Decir "Disponible
en Google Play" cuando en realidad se alquila a un precio sería engañoso. Se recomienda que
`en_plataforma` sea verdadero sólo para `flatrate`, `free` y `ads`, y que alquiler y compra
se presenten aparte, con otro verbo. Queda como decisión abierta.

### Cobertura real, por tipo de obra

Veinte títulos, elegidos para parecerse al catálogo del owner y no sólo a los éxitos.

| Categoría | Con datos AR | Observación |
| --- | --- | --- |
| Taquilleras recientes | sí | `Dune: Part Two` en HBO Max |
| Series grandes | sí | `The Sopranos` en HBO Max |
| Cine argentino | sí | `El secreto de sus ojos` en Netflix y Prime |
| Exclusivas Apple TV+ | sí | `Severance`, `Ted Lasso`, `CODA` |
| Anime clásico | parcial | `Akira` sólo alquiler/compra, sin suscripción |
| Cine de autor | **engañoso** | ver abajo |
| Obras oscuras | no | `Addio Zio Tom`: 2 países en total |

**El hallazgo que más le importa a este catálogo.** El cine de autor no falla de forma
uniforme, y el promedio agregado (13 de 20 con datos) engaña:

- `Seven Samurai`, `Ran` y `Stalker` **no tienen datos para AR** en absoluto.
- `Persona`, `Rashomon`, `Tokyo Story` y `El ángel exterminador` **sí los tienen**, pero
  únicamente en plataformas marginales: `Artiflix`, `Cultpix` y `Plex` con publicidad.

Esto interactúa directamente con la lista de **plataformas ignoradas** decidida por el
owner: si ignora las plataformas de cola larga —que es lo natural—, esos títulos vuelven a
no mostrar nada. Para un catálogo de autor la función va a verse bastante más vacía que lo
que sugiere el 65 % agregado. No es un defecto de la fuente: esas obras realmente no están
en las plataformas grandes de Argentina.

## Condiciones de la aceptación

### 1. Atribución a JustWatch, obligatoria y con cláusula de revocación

La documentación de TMDb es explícita:

> "In order to use this data you must attribute the source of the data as JustWatch. If we
> find any usage not complying with these terms we will revoke access to the API."

Es una obligación **nueva y separada** del aviso de TMDb que [F5.3] ya implementó. La
superficie que muestre disponibilidad tiene que nombrar a JustWatch como fuente del dato.
Incumplirlo pone en riesgo el acceso a toda la API, no sólo a esta función.

### 2. El tope de retención de seis meses aplica

Los términos prohíben cachear más de seis meses cualquier información obtenida de TMDb, y
la disponibilidad no es una excepción. La tolerancia de 1 a 2 meses del owner entra
holgada, pero el snapshot es **dato persistido**, no caché: necesita fecha de consulta,
procedencia y una vía de purga, tal como [F3.1] ya había advertido para las fichas. Esa vía
existe (`TmdbRetirementService`) y [S3] debe extenderla, no reinventarla.

### 3. La honestidad temporal ya está decidida, y este dato la tensiona

El owner decidió que la ficha diga "Disponible en Netflix" sin fecha, y que la fecha viva
en `Administrar`. Las mediciones respaldan que el dato es volátil: cambia por acuerdos de
licencia sin previo aviso. La decisión se mantiene; queda registrado que acepta mostrar sin
marca visible un dato de hasta dos meses.

## Alternativas evaluadas

| Fuente | Cobertura | Costo | Veredicto |
| --- | --- | --- | --- |
| **TMDb** (JustWatch) | 139 regiones, 59 proveedores en AR | ya integrada, sin credencial nueva | **elegida** |
| Watchmode | 200+ servicios, 54 países, empareja por `tmdb_id` | 2500 pedidos/mes gratis, no comercial | reserva |
| Streaming Availability API | 20+ servicios, 60 países | freemium, key propia | reserva |
| JustWatch directo | la fuente original | **sin API pública oficial** | descartada |

JustWatch no publica una API pública para terceros; sólo existen wrappers de scraping y
servicios intermediarios. Eso choca con el criterio del proyecto de no depender de
scraping, así que queda descartada aunque sea el origen del dato.

Watchmode es la reserva real: empareja por `tmdb_id`, lo que haría la migración barata si
la cobertura de TMDb resultara insuficiente. Pero agrega una segunda credencial, un segundo
conjunto de términos y una segunda cuota, sin evidencia todavía de que haga falta.

## Qué queda abierto para [S1] y [S3]

1. **Semilla de plataformas**: guardar los nombres literales de la API y distinguir
   `Apple TV` de `Apple TV Store`. No escribirlos de memoria.
2. **Semántica de `en_plataforma`**: si `rent`/`buy` cuentan como disponibilidad o se
   presentan aparte. Recomendación: aparte.
3. **Dónde vive la atribución a JustWatch** en la interfaz.
4. **Frecuencia de refresco** dentro del tope de seis meses, y qué hacer con un título cuyo
   snapshot venció y todavía no se refrescó.

## Fuentes

Documentación verificada el 2026-09-07:
[watch providers de películas](https://developer.themoviedb.org/reference/movie-watch-providers)
y [términos de la API](https://www.themoviedb.org/api-terms-of-use). Alternativas:
[Watchmode](https://api.watchmode.com/). Investigación de términos, no asesoramiento legal.
