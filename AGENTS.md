# Instrucciones para Codex y otros agentes

Leé `CLAUDE.md`, `SDD.md`, `PRODUCT.md`, `DESIGN.md` y `tareas.md` antes de trabajar.
Las invariantes y los gates de esos documentos aplican también a Codex.

## Ramas y pull requests

- Las ramas nuevas se llaman `feature/nombre-del-feature` o `release/x.x.x`.
- Para el trabajo individual de una versión abierta, usar su rama `release/x.x.x`.
- Una feature aislada se integra en la release mediante merge commit. No usar
  prefijos `codex/`, `claude/`, `feat/` ni ramas personales.
- `master` es la rama estable: recibe el merge de la release, nunca commits directos.
- Un PR de release propone `release/x.x.x` hacia `master` y reúne el alcance de esa
  versión. Usar `.github/pull_request_template.md`; completar sólo la descripción.
- No fusionar la release ni publicar un tag sin pedido del owner.
- Excepción transitoria: el PR #3 conserva `codex/search-workbench-v011` como alias
  remoto de `release/0.11.0`, porque GitHub no permite sustituir su rama de origen.
  Trabajar en la release y actualizar ambos refs al mismo commit al publicar avances.
  Esta excepción termina al cerrar el PR #3; no habilita ramas nuevas con ese prefijo.

Conservar trabajo ajeno, datos privados y el historial. Antes de integrar o publicar,
revisar cambios locales y ejecutar los checks pertinentes.
