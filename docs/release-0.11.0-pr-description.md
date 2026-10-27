# Título propuesto

release: 0.11.0

# Cuerpo listo para el PR #3

## Ramas

Usar `feature/nombre-del-feature` o `release/x.x.x`. Preferir la release para el
trabajo individual e integrar features en ella antes de proponerla a `master`.
Este PR conserva su rama histórica como alias de `release/0.11.0` porque GitHub
no permite sustituir la rama de origen de un PR existente.

## Descripción

Reúne la candidata 0.11.0: búsqueda local/externa unificada y revisión de coincidencias
(U12), ids durables de dispositivo (X11), identidad común y enriquecimiento Wikidata
(X12), selección para comparar/unir desde búsqueda y mejoras de cabecera/navegación
de ficha. Centra los rótulos de Inicio y agrega tres opciones interactivas para elegir
el rediseño de los controles de Colección, todavía sin aplicar una a producción.

Incluye reglas de ramas para Claude/Codex, una plantilla mínima de PR y un estado
ordenado de master, release y backlog. El alcance sigue abierto: no es el cierre
ni el tag definitivo de 0.11.0.

Antes de actualizar, guardar backup de `instance.db`: la migración v23→v25 impide
abrir esa base con 0.10.0. X11 cambia una vez los ids de réplicas anteriores;
sincronizar sus cambios pendientes antes de renovar la réplica.

Validación local: 1.159 pruebas unitarias (9 omitidas), checks de Ruff/formato/mypy,
gates Search Lab y pruebas de navegador sobre fixtures descartables. Evidencia de
rótulos y maquetas responsive en `docs/design/collection-controls-v1/`.
