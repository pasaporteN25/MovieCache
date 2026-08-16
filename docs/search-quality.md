# Calidad de busqueda y matching

Este documento define el gate de calidad de `v0.3.0`. Su objetivo es evitar otra
iteracion basada solamente en ejemplos positivos: una busqueda no mejora si encuentra
el resultado esperado pero tambien presenta decenas de obras irrelevantes.

**Estado:** el gate del corpus dorado (seccion "Metricas y gate de v0.3.0") pasa:
`movie-inbox search-lab run --enforce` sale con codigo 0 y CI lo hace cumplir en cada
cambio. Las 4 fallas de abajo estan resueltas en los caminos que ejercita el corpus
(`search_catalog_items`, `rank_catalog_candidates`, `external/registry.py`,
`application/search_evaluation.py`). El problema #3 quedo resuelto para el caso
concreto de un mismatch *confirmado* (mismo titulo, año o tipo distinto) en Catalogo
y Comparar; `domain/matching.py::rank_candidates` (usado solo por
`cli/match_external_links.py`) sigue sin ese filtro, sin evidencia de que haga falta
hoy. Ver `CHANGELOG.md` (`[Sin publicar]`) para el detalle de cada fix.

## Problemas verificados

El comportamiento tenia cuatro fallas diferentes (ver "Estado" arriba):

1. La coincidencia de terminos acepta subcadenas en ambas direcciones sin proteger
   tokens cortos. Un articulo como `a` puede hacer que un titulo no relacionado puntue
   como coincidencia fuerte para una consulta que contenga esa letra.
2. La busqueda local permite que descripcion, review, reparto, genero y tags superen un
   umbral general muy bajo. Eso puede ser util para descubrimiento, pero no debe
   mezclarse con resultados por titulo.
3. El ranking de candidatas conserva cualquier `match_score > 0`, incluso cuando la
   decision es `insufficient_evidence`. La similitud difusa produce valores mayores que
   cero para casi cualquier par de titulos.
4. Las fuentes externas se ordenan por puntaje pero no aplican un umbral de rechazo.
   La interfaz progresiva hace visibles hasta ocho resultados por fuente, incluidos los
   de relevancia minima.

La concurrencia por fuente no es la causa de estos falsos positivos. Debe conservarse:
mejora el tiempo percibido y permite que una fuente falle sin bloquear a las demas.

## Cuatro contextos, cuatro contratos

| Contexto | Objetivo | Evidencia permitida | Prioridad |
|---|---|---|---|
| Catalogo | Encontrar una ficha que el usuario recuerda | Titulos, aliases, ID, archivo; metadata secundaria separada | Precision primero |
| Fuentes externas | Encontrar una obra fuera del catalogo | Titulos, aliases, ano, tipo, ID y fuente | Recall controlado |
| Comparar/merge | Decidir si dos fichas representan la misma obra | ID externo o titulo, ano y tipo compatibles | Cero falsos auto-match |
| Scanner | Identificar un archivo fisico | Titulo limpio, ano, tipo, IDs y decisiones previas | Cero falsos auto-match |

La normalizacion de texto puede compartirse. Los campos, umbrales y significado de un
score no deben compartirse implicitamente entre estos contextos.

## Laboratorio de busqueda

El primer incremento sera un `Search Lab` de desarrollo, no destructivo y disponible
solo para el owner cuando una feature flag lo habilite.

- Nunca expondra endpoints de escritura ni trabajara sobre la unica copia de una base.
- Usara un export o snapshot de catalogo montado en solo lectura.
- Ejecutara el algoritmo baseline y el candidato sobre la misma consulta.
- Mostrara score, campo coincidente, razon, evidencia y clasificacion
  `aceptada/revisar/rechazada`.
- Permitira marcar resultados como relevantes o irrelevantes y exportar esas decisiones
  al corpus de casos dorados.
- Las fuentes externas funcionaran por defecto con respuestas grabadas. El modo live
  sera manual y sus latencias se mediran por separado.

El runner automatizado y los fixtures son la fuente de verdad. La vista web sera una
herramienta para inspeccionar y etiquetar casos, no un segundo algoritmo.

### Incremento 1 implementado

El primer incremento entrega el runner determinista, el corpus dorado `v1` empaquetado
y una inspeccion HTML/JSON de exports. Reutiliza sin cambios los cuatro caminos
productivos actuales y registra score, campo, razon, evidencia y aceptacion.

```powershell
movie-inbox search-lab run --json reports/baseline.json --html reports/baseline.html
movie-inbox search-lab run --enforce
movie-inbox search-lab inspect backups/catalog.json "Heat" --mode catalog --html reports/heat.html
```

El primer comando siempre permite registrar la baseline aunque el gate falle. El
segundo se reserva para CI y retorna un estado distinto de cero si no se cumplen los
umbrales. `inspect` solo admite un export JSON, nunca una base SQLite viva; tampoco
consulta fuentes externas ni crea archivos de bloqueo. La vista owner con feature flag,
el etiquetado y la comparacion baseline/candidato pertenecen al incremento siguiente.

## Corpus inicial

Cada caso declarara `context`, consulta, resultado esperado, resultados prohibidos,
ano/tipo opcionales y evidencia requerida. El corpus inicial debe incluir:

- Titulos cortos y ambiguos: `It`, `Up`, `Us`, `Heat`, `Crash`, `The Gift`.
- Titulos numericos: `1917`, `1984`, `2001: A Space Odyssey`.
- Remakes: `The Fly`, `Suspiria`, `Dune` y obras con igual titulo y distinto ano.
- Titulos multilenguaje: `La Belle Personne`, `La bella persona`,
  `The Beautiful Person`.
- Obras recientes o con metadata incompleta, comenzando por `Evil Dead Burn`.
- Series y anime, comenzando por `Tantei Monogatari`.
- Nombres de archivo con release, codec, resolucion, grupo y multipartes.
- Consultas negativas que comparten actores, palabras de descripcion o articulos, pero
  no identidad de obra.

Los casos provenientes de un catalogo real deben anonimizar rutas y datos personales
antes de entrar al repositorio.

## Metricas y gate de v0.3.0

- Precision de auto-match y auto-merge: `100%` en el corpus dorado.
- Cero resultados `insufficient_evidence` presentados como coincidencia segura.
- Precision@5 de busqueda local por titulo: al menos `90%`.
- MRR de busqueda local por titulo: al menos `0.90`.
- Recall@5 externo sobre respuestas grabadas: al menos `90%`.
- Ninguna consulta negativa aprobada por descripcion, review, reparto, genero o tags en
  los contextos de merge y Scanner.
- Resultados de baja confianza ocultos por defecto y contados por separado.
- Rendimiento local medido con catalogos sinteticos de 2.000 y 10.000 obras; la red se
  evalua por fuente y no forma parte del tiempo del ranking local.

Una mejora no entra a `master` si aumenta recall a costa de falsos positivos en merge
o Scanner. En esos flujos, dejar un caso para revision es mejor que unir obras distintas.

## Secuencia de implementacion

1. [Completado] Crear fixtures y runner con el comportamiento actual como baseline observable.
2. Agregar pruebas negativas que reproduzcan los falsos positivos conocidos.
3. Separar `catalog_search`, `external_lookup`, `identity_candidates` y
   `scanner_candidates`. Parcial: tienen umbrales propios ahora, pero
   `rank_catalog_candidates` sigue llamando a `search_catalog_items` por dentro,
   no son caminos completamente independientes.
4. [Completado] Corregir tokens cortos, stopwords, umbrales y evidencia por campo.
5. [Completado] Filtrar por relevancia dentro de cada adaptador externo sin perder
   resultados exactos recientes o multilenguaje.
6. Integrar el reporte al Search Lab y calibrar con decisiones humanas. El reporte ya
   existe; falta el proceso de calibración con revisión humana.
7. Recién entonces ajustar la presentacion final de resultados y el triage del Scanner.

No se incorporaran embeddings, modelos de IA ni nuevas APIs durante este gate. Primero
debe existir una baseline determinista, explicable y reproducible.
