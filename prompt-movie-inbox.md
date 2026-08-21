# Prompt maestro — Movie Inbox

> Pegar tal cual en Claude Code, en la raíz del repo.
> Está pensado para varias sesiones: el agente hace una fase, para, y vos revisás.

---

Trabajás sobre **Movie Inbox**, un gestor self-hosted de catálogo audiovisual. Python +
FastAPI + SQLite, frontend vanilla sin build step. Versión estable v0.2.1, con v0.3.0 en
curso.

Antes de escribir una sola línea, leé estos archivos completos: `PRODUCT.md`, `DESIGN.md`,
`docs/roadmap.md`, `CHANGELOG.md` (sección `[Sin publicar]`), `tests/test_layering.py`,
`pyproject.toml` y `.github/workflows/tests.yml`. No son documentación decorativa: son
contratos vigentes y algunos están verificados por tests.

## Invariantes que no se negocian

Si una tarea parece exigir romper alguna de estas, **pará y preguntame** en vez de decidir
por tu cuenta.

1. **Layering.** `domain/` y `application/` no importan `infrastructure`, `external`, `web`
   ni `cli`. `tests/test_layering.py` lo verifica por AST.
2. **Terminología de PRODUCT.md.** `en_catalogo` (disponibilidad física) es independiente de
   `to_watch` y `watched`. Archivo físico, identidad compartida y ficha personal son tres
   cosas distintas y nunca se presentan como intercambiables.
3. **Matching conservador.** Una coincidencia dudosa requiere revisión humana. Descripción,
   review, reparto, género o tags nunca convierten una obra en candidata de identidad.
   Cero falsos positivos conocidos en auto-match es el gate de salida de v0.3.0.
4. **Privacidad.** Las vistas compartidas nunca exponen rutas, archivos locales, notas ni
   estado operativo. El owner no tiene excepción.
5. **Correcciones manuales y campos bloqueados** sobreviven a cualquier enriquecimiento
   posterior.
6. **JSON portable.** `catalog.schema.json` es un contrato versionado. SQLite es la fuente
   de verdad; JSON sigue siendo formato de importación, exportación y backup.

## Cómo quiero que trabajes

- **Una fase por sesión.** Al terminar una fase, pará y hacé un resumen de qué cambió y qué
  gate quedó verde. No arranques la siguiente sin que yo lo confirme.
- **Plan primero.** En fases 3, 4 y 5, entrá en plan mode y mostrame el plan antes de tocar
  archivos.
- **Verde antes de avanzar.** `python -m unittest discover -s tests` tiene que pasar al final
  de cada fase. Si una fase requiere romper un test temporalmente, decímelo explícitamente.
- **Commits chicos y atómicos**, con mensaje que explique el *por qué*. No commitees sin que
  yo lo pida.
- **Actualizá `CHANGELOG.md`** (sección `[Sin publicar]`) con cada cambio de comportamiento
  visible al usuario. Seguí el estilo que ya está: en español, orientado a lo que cambia para
  la persona, no a la implementación.
- Los archivos personales (`scripts/*.json`, `catalog*.json`, `.catalog-cache/`, `.movie-inbox/`)
  son datos reales míos. No los leas para "entender el dominio" ni los uses como fixtures.

---

## Gestión de tareas (a partir de 2026-08-18)

El trabajo más allá de esta fase (Enriquecimiento y cobertura de links, Search Lab, y lo
que se sume después — Integraciones, Landing) se trackea en `tareas.md` (raíz del repo),
un tablero en Markdown con columnas Backlog/En curso/Hecho, agrupado por frente, con
alcance de archivo/línea y nivel de modelo sugerido por tarea. Se eligió Markdown en vez
de un kanban autohosteado (se evaluó Kanboard) para no sumar infraestructura nueva que
mantener. Leerlo junto con este archivo al arrancar una sesión nueva.

## Progreso (actualizado 2026-08-19)

Fases 0, 1, 2, 3 y 4 cerradas. v0.3.0 publicado. Fase 5 (v0.4.0): los 4 P1
(P1-c, P1-a, P1-b, P1-d) están cerrados. El gate final de Fase 5 —correr
`$impeccable audit` de nuevo sobre la misma superficie— ya se ejecutó: 16/20
(contra 22/40 de la corrida del 2026-08-14; escalas distintas, no
comparables directo). Encontró un P1 propio (contraste de `--control-border`,
cerrado) y un P2 propio (caching HTTP de estáticos, cerrado), más 4
hallazgos "P3" menores que se están cerrando uno por uno con aprobación
previa de cada uno: `extract` (colores literales → tokens, **cerrado**),
`typeset` (`font-family` y `font-size`, **cerrado**), `adapt` (**cerrado**,
ver abajo — investigación grande, hallazgo chico) y `polish`. Queda solo
`polish`. Sesión nueva a partir de acá — no hace falta releer el historial
de conversación, esto + `CLAUDE.md` + `git log` alcanza.

También en esta sesión, del tablero `tareas.md` (frente Enriquecimiento y
cobertura de links): `[E3]` y `[E4]` cerrados (commit `062f69b`), y un bug
suelto de la pasada de `extract` corregido — el `rgba(69, 76, 120, .66)`
de `catalog.css` que había quedado con el valor viejo de `--control-border`
(commit `bea4a43`). `[E6]` sigue en Backlog a pedido de Lucas.

**Fase 5, P3 (`$impeccable adapt`) cerrado (2026-08-19).** Investigación
grande, resultado chico — y vale documentar por qué, para que una sesión
futura no asuma que "adapt" tiene tanto por corregir como tuvo `typeset`.
Scan mecánico (`detect.mjs --scope layout`) dio 0. Leí — no solo grepeé —
los 34 bloques `@media (max-width: ...)` de los 12 archivos CSS que
tienen alguno. El patrón fue consistente en todos lados salvo uno: los
controles interactivos suben a `min-height: 44px` (o más) dentro de su
breakpoint móvil, coherente con el token `--touch-target: 44px` y con las
inserciones de `env(safe-area-inset-*)` donde hace falta. Confirmé además
dos cosas puntuales que `DESIGN.md` promete explícitamente: la navegación
principal sí se convierte en barra inferior fija en móvil (con safe-area y
objetivos de 52px), y el flip por hover del DVD Case en `core-card.css`
está detrás de `@media (hover: hover) and (pointer: fine)` con el acceso a
la ficha cableado como `data-click` en toda la tarjeta — nunca depende
exclusivamente del hover, tal como pide `DESIGN.md`.

Único hallazgo real: `core-merge.css:322`, dentro del breakpoint de 640px,
`.merge-show-all { min-height: 34px; }` — el toggle "mostrar todos los
campos" del comparador de fusión, que en desktop mide 38px, se achicaba
en móvil a 34px — más chico que su propio default de escritorio y por
debajo del mínimo táctil, exactamente al revés del patrón que aparece
~15 veces en los otros 11 archivos. Corregido a 44px, mismo patrón exacto
que ya usan `curation.css`, `scanner.css` e `imports.css`. Un cambio de
una línea.

Los valores de breakpoint no son uniformes (`scanner.css` usa 1120px/
700px, `imports.css` 980px/700px, `login.css` 760px, contra los 1100/860/
640/440 que documenta `DESIGN.md`) — leí el contenido real detrás de cada
uno antes de asumir que era un bug, y son quiebres genuinos por el ancho
interno de cada grid, no deriva arbitraria; `adapt.md` del propio skill
pide breakpoints por contenido en vez de perseguir tamaños de dispositivo
fijos, así que se dejaron como están.

Nota aparte, no de producto: el testing en vivo con la herramienta de
browser mostró `window.innerWidth` desactualizado después de una
navegación SPA con el viewport ya redimensionado (`visualViewport.width`,
el ancho real de `<html>`/`<body>` y cada medición directa de elemento
seguían mostrando 390px correctamente) — lo rastreé con varias mediciones
independientes antes de concluir que es una rareza de la herramienta de
testing, no un bug de Movie Inbox, y no seguí insistiendo con eso.
Verificado con `scripts\check.ps1` en verde (301 tests). Queda `polish`.

**Fase 5, P3 (`$impeccable typeset`) cerrado (2026-08-19).** Segunda mitad:
los 49 `design-system-font-size` que había quedado sin tocar (ver la entrada
de abajo para la primera mitad, `font-family`). A diferencia de esa primera
mitad, acá cada sitio pedía criterio real, así que se leyeron los 49 en
contexto completo y se agruparon por rol antes de tocar nada — un Plan agent
rehizo la categorización de forma independiente desde los archivos reales
(no desde mi resumen) y encontró 3 sitios que se me habían pasado
(`core-card.css:259`, `curation.css:252` y `:272`); verifiqué esas 3
correcciones a mano contra el archivo antes de confirmarlas. El agent
también confirmó que ningún JS del frontend lee `getComputedStyle`,
`offsetHeight` ni nada equivalente sobre estas clases — la única función
relacionada, `titleSizeClass()` en `core/format.js`, solo mapea longitud de
string a un nombre de clase fijo, nunca lee un tamaño renderizado. Encontré
(y confirmé leyendo el archivo) que `club.css` define
`.dvd-placeholder strong.title-medium` pero nunca `.club-card h4.title-medium`
— un hueco real donde `titleSizeClass()` puede asignar esa clase a un `h4`
que cae silenciosamente al tamaño base; es un bug de una regla faltante, no
de un valor de tamaño, así que quedó anotado sin tocar.

Entré en plan mode (obligatorio en Fase 5) con la categorización completa y
verificada. Dos decisiones necesitaban mi input, no el del agente:
"¿además de unificar, qué otras opciones hay?" para el cluster más grande
(11 encabezados de sección, 18-42px en 8 pantallas) — resueltas por
catalogar cada valor distinto como su propio token con su valor actual
(cero cambio visual), fusionando solo los dos pares que ya eran idénticos
byte a byte (32px/32px, 34px/34px) en vez de inventar escalones nuevos; y
si un cluster de "número de estadística" (22px en 3 archivos, más 25px y
20px en otros dos) se unifica a 22px — confirmé que sí. Esos son los
**únicos 2 cambios de valor real de las 49** (`club.css:334` 25→22px,
`imports.css:215` 20→22px); las otras 47 son cero cambio visual.

36 tokens nuevos en `tokens.css` (agrupados por familia: rampa faltante de
15px reencontrada 5 veces en archivos sin relación → `--text-compact`;
cluster de estadística → `--text-stat`; una marca "↔" de comparador
idéntica en `core-merge.css` y `curation.css` → `--text-comparator-mark`;
dos cascadas de truncado de título por longitud —`core-card.css` y
`club.css`— mantenidas como familias separadas porque los valores son
parecidos pero nunca idénticos, sin evidencia de duplicado real; el resto,
roles de un solo uso con su propio nombre). Reemplazo de los 49 con un
script (no a mano) que verificó la cantidad esperada de ocurrencias antes
de cada reemplazo — falló en seco si algo no cuadraba, no corrigió nada
silenciosamente. `DESIGN.md` suma `compact` (15px) y `stat` (22px) al
frontmatter; el resto queda component-scoped para una futura pasada de
`document`, igual que los tokens de `extract`.

Verificado con `scripts\check.ps1` en verde (301 tests) y `getComputedStyle`
contra el mismo catálogo sintético (Inicio, Colección, Club, Curaduría) —
14 selectores representativos de los 6 grupos, todos resuelven exactamente
al valor esperado, incluida la marca de comparador compartida entre dos
archivos. `detect.mjs --scope type` pasó de 77 hallazgos (al arrancar esta
tarea de `typeset`) a **0** — `font-family` y `font-size` quedan
completamente cerrados. Quedan `adapt` y `polish`.

**Fase 5, P3 (`$impeccable typeset`) parcial (2026-08-19).** Primer error a
corregir: le pedí al skill `audit` en vez de `typeset` — son comandos
distintos (`audit` es a11y/perf/responsive, no el review de heurísticas UX
que veníamos llamando "audit" en este archivo). El comando real que
corresponde a esta entrada de la cola es `typeset`, que hace su propio
análisis en vivo en vez de leer hallazgos guardados — corregido antes de
tocar nada.

El scan mecánico (`detect.mjs --scope type`) sobre `src/movie_inbox/web/static/css/`
completo dio 77 hallazgos: 28 `overused-font` y 49 `design-system-font-size`.
Los 28 eran el mismo patrón que ya resolvió `extract` para colores pero sin
tocar: `"Arial Narrow", "Trebuchet MS", sans-serif` (roles display/feature/title)
y `"Courier New", monospace` (rol label) repetidos como literales — 27 y 65
veces respectivamente, en los mismos 12 archivos — en vez de vivir en
`tokens.css` como el resto de los valores documentados en `DESIGN.md`.
Confirmé que las 27 y las 65 ocurrencias eran texto idéntico byte a byte
antes de tocar nada. Agregué `--font-display`, `--font-body` y `--font-label`
a `tokens.css` (mismo lugar que los tokens de color) y reemplacé las 92
ocurrencias por `var(...)` con un script, no a mano — mecánico y sin
excepciones que revisar. Verificado con `scripts\check.ps1` en verde (301
tests) y con `getComputedStyle` contra un catálogo sintético nuevo (Bandeja,
Colección, Club) confirmando que cada rol resuelve exactamente al mismo
valor que el literal que reemplazó. Efecto de lado: el scan mecánico bajó de
28 a 0 hallazgos de `overused-font` — no fue necesario un `ignore-value`,
porque el valor genérico que el detector reconoce (`"Arial Narrow"`/
`"Space Grotesk"`) ya no aparece como declaración `font-family:` literal en
ningún lado salvo dentro de la definición del token mismo, que el detector
no interpreta como una declaración de fuente.

Los 49 `design-system-font-size` quedan **sin tocar, a propósito**. No es un
hallazgo mecánico resolvible con un script: son valores realmente arbitrarios
(7px, 17px, 18px, 19px, 20px, 21px, 22px, 23px, 25px, 26px, 29px, 32px, 34px,
36px, 38px, 42px, 44px, ninguno de la rampa de `DESIGN.md`), repartidos en 12
archivos, y cada uno pide criterio real, no snapping mecánico. Dos ejemplos
concretos que muestran por qué: `curation.css` tiene dos encabezados con el
mismo rol visual (Arial Narrow, itálica, mayúsculas) en 42px (`.curation-heading h2`)
y 34px (`.curation-case-heading h3`) — dos pasos de jerarquía reales sin
nombre, no un error; y `.curation-thumb` usa `font-size: 7px` para un glifo de
fallback en una caja de 40×56px, que probablemente esté bien así (no es texto
de lectura) pero tampoco tiene un token que documente esa intención. Además
encontré (no vía el detector, que solo mira literales) que `.dvd-case`
`.title-short`/`.title-medium` en `core-card.css` resuelven a `35px` en
runtime — el rol `title` de `DESIGN.md` documenta `24px` fijo, así que hay un
tercer caso de tamaño no documentado, probablemente detrás de un `clamp()` o
cálculo que el scan estático no puede leer.

Pendiente para la próxima sesión de esta misma tarea: decidir, caso por caso
y con capturas o el browser real, cuáles de los 49 (más el de `core-card.css`)
son pasos de rampa nuevos que merecen nombre propio en `DESIGN.md`, cuáles
deberían alinearse a un rol existente, y cuáles son excepciones legítimas
como el glifo de 7px. `adapt` y `polish` siguen sin arrancar.

**Fase 5, P3 (`$impeccable extract`) cerrado (2026-08-18).** Los ~150
colores literales de `core-card.css`, `home.css`, `catalog.css`,
`core-detail.css` y `club.css` que no pasaban por `tokens.css` ni por el
frontmatter de `DESIGN.md` quedaron formalizados como tokens. La mayoría
(~110) eran el mismo patrón: `rgba(R, G, B, alpha)` con el RGB exacto de un
color de señal ya existente, escrito a mano porque CSS no permite
`rgba(var(--hex), alpha)` sin un triplete RGB aparte — se agregaron 11
tokens `--x-rgb` (`--red-rgb`, `--teal-rgb`, `--gold-rgb`, `--violet-rgb`,
`--case-rgb`, `--paper-rgb`, `--cream-rgb`, `--muted-rgb`, `--ink-rgb`,
`--line-rgb`, `--text-pink-rgb`) y se migraron todas las ocurrencias a
`rgba(var(--x-rgb), alpha)`. El resto eran dos familias reales sin nombrar:
la rampa de 3 paradas del fallback de carátula (`.poster-1..4`, un color de
señal cada uno, con tono medio apagado y remate casi negro) y el tinte
pálido de los chips de estado / ícono de placeholder — confirmé con Lucas
que esta segunda familia es intencionalmente distinta de los `--text-*-soft`
que ya existían para kickers y mensajes de feedback (dos roles de contraste
distintos, no un duplicado), así que se sumó como familia nueva
(`--chip-tint-*`) en vez de fusionarla. También apareció una familia
"danger" real (bordes/fondos de zona peligrosa y de botón destructivo) que
no es ninguno de los 4 colores de señal y no estaba documentada; se
formalizó con 3 tokens nuevos (`--danger-rgb`, `--danger-border`,
`--danger-ink`).

Encontrados y corregidos 4 casos concretos de valores casi duplicados dentro
del mismo rol (no drift real de paleta, sino la misma intención escrita a
mano dos veces con un dígito de diferencia): el remate del degradé violeta
de carátula, el ícono "sin portada" de la ficha (distinto del de Colección),
y dos bordes de advertencia dorados en Colección — los cuatro casos quedan
en el CHANGELOG. Se dejaron sin tocar, a propósito, dos hallazgos fuera del
alcance de esta pasada: los stops de degradé únicos del spotlight de Inicio
(un solo uso cada uno, tokenizarlos sería sobre-extracción) y un
`rgba(69, 76, 120, .66)` en `catalog.css` que resultó ser una copia
hardcodeada del valor VIEJO de `--control-border` (antes del fix de
contraste del P1) que el P1 nunca actualizó — sigue mostrando el borde de
bajo contraste original en ese único punto; queda anotado para una sesión
aparte, no se tocó sin confirmación.

`DESIGN.md` se actualizó en el mismo commit: 13 colores nuevos en el
frontmatter, más *backfill* de 4 tokens que ya existían en `tokens.css`
desde antes pero nunca habían llegado al frontmatter (`text-pink`,
`text-cyan-soft`, `text-gold-soft`, `text-danger-soft`) porque hacía falta
nombrarlos para explicar por qué la familia de chip-tint es distinta. Los
otros 7 tokens de `tokens.css` que también faltan en `DESIGN.md`
(`text-soft`, `text-highlight`, `surface-deep`, etc., sin relación con este
hallazgo) quedaron sin tocar a propósito, para una futura pasada de
`$impeccable document`.

Verificado con `scripts\check.ps1` en verde (263 tests + `git diff --check`)
y un script de verificación numérica que resuelve cada `var()` nuevo contra
`tokens.css` y lo compara valor por valor contra el literal que reemplazó en
las ~150 ocurrencias — 100% idéntico salvo los 4 cambios aprobados de
arriba. Recorrido manual en browser real contra un catálogo sintético (4
obras sin portada, una por cada color de señal, para forzar los 4 degradés
de `poster-N`): verificado vía `getComputedStyle` además de inspección
visual, confirmando que `.poster-3` resuelve al degradé dorado exacto y que
`.dvd-front-status.catalogued`/`.danger-zone`/`.action-danger` resuelven a
los tokens nuevos correctos. Cero errores de consola. No se armó una cuenta
de Club para este recorrido — `club.css` se verificó solo por el script
numérico, ya que no introduce ningún token nuevo (reusa exactamente los
mismos `--x-rgb` ya confirmados en las otras cuatro pantallas).

Quedan `typeset`, `adapt` y `polish` — cada uno para una sesión/aprobación
aparte, según lo pedido.

**Fase 5, P1-d cerrado (2026-08-17).** La cola de Scanner se organiza por
causa y confianza en vez de solo `Comparar`/`Sin coincidencia`:
`scannerQueueCauseBucket()` nuevo en `inbox-scanner.js` clasifica cada caso
top-down en `Falta identidad` (`!detected_year`, prioridad — problema de
higiene del archivo, no de matching), `Conflicto de año/tipo` (alguna
candidata con `exact_title_year_mismatch`/`exact_title_kind_mismatch`),
`Probable ficha existente` (`exact_title_missing_year`) o `Sin señales`
(`else` incondicional — catch-all, no un set enumerado). Los 5 chips de
filtro reemplazan a los 2 viejos (no se agregan, la crítica pedía "no solo
por Comparar y Sin coincidencia"), y el header del panel de detalle se
unificó con el mismo vocabulario que la fila de la lista (antes decían cosas
distintas para el mismo caso). Cuando un caso tiene más de 3 candidatas se
muestran las 3 de mayor score (arreglado de paso: el array fusionado de
candidatas de scan-time + create-time-conflict no estaba ordenado por score,
sino por origen) y el resto queda en un `<details>` nativo "Ver N candidatas
más" — mismo patrón ya usado en `admin-libraries.js`.

Mi primer diseño de los 4 buckets tenía dos errores reales que un Plan agent
encontró y yo verifiqué a mano antes de implementar: (1) enumerar los
`reason` de "Sin señales" por lista cerrada tiene un hueco — si dos catalog
items distintos matchean ambos por `exact_title_year` (`len(accepted) > 1`
en `_classification()`), esas candidatas aparecen visibles con un `reason`
"aceptado" que ninguna lista cerrada cubre; el fix es un `else`
incondicional. (2) Clasificar por "la candidata de mayor score" invierte la
señal que la crítica quiere destacar — verifiqué a mano `candidate_score()`:
un año-mismatch con título exacto cae a `0.73` mientras un título apenas
parecido con año casualmente igual puede superar `0.9`; el fix es "¿hay
ALGUNA candidata con este reason?", no "¿cuál es el reason de la candidata
top?". Confirmado 100% Scanner — Curaduría no tiene ningún array de
candidatas con `score`/`reason` que agrupar por causa. También se confirmó
que "mantener merges automáticos solo para IDs externos o título+año
exactos" (la otra mitad del pedido de la crítica) ya estaba cerrado sin
código que tocar, y que no existe ninguna superficie de lote en todo el
proyecto — nada que revisar ahí. Verificado con 262 tests de Python
(`scripts\check.ps1` en verde) + 11 Playwright (2 nuevos, con fixture propio
de 5 candidatas para el tope 3 — score verificado a mano campo por campo) +
recorrido manual en browser real contra un catálogo sintético que ejercita
los 4 buckets (incluido el caso mixto de "Quartz Lantern Meridian", con
razones de dos buckets distintos en el mismo caso, priorizado correctamente).

**Fase 5, P1-b cerrado (2026-08-17).** Scanner deja de presentar "sin
candidata" como ausencia comprobada: la rama sin candidatas cambia de "Obra
ausente del catálogo" a "No encontramos una coincidencia segura", aclara que
la comprobación no es exhaustiva, y ofrece un botón "Buscar en tu catálogo"
(`findLocalMatchForItem()` nuevo en `core/search-bridge.js`, reusa
`runSearch()` de Colección) antes de permitir el alta. Cada candidata de
Scanner muestra además su procedencia — `En tu catálogo` o `Catálogo
compartido` — junto a la razón de confianza que ya existía; el backend la
calcula taggeando transitoriamente `catalog_universe()` (`_scope_owner`,
mismo patrón no persistido que `_availability` de P1-c) y sumando
`catalog_origin` a cada candidata en `_classification()` y en
`ensure_scanner_item()`. La crítica original pedía 3 etiquetas de procedencia
(`En tu catálogo` / `Identidad del inventario` / `Catálogo compartido`); un
Plan agent y yo confirmamos que el código solo sostiene 2 reales — toda
candidata de Scanner está respaldada por un catalog item real de alguna
cuenta, no existe una tercera fuente de "identidad sin ficha" — así que
colapsamos a 2 en vez de inventar una categoría sin dato detrás. De paso se
agregó un tie-break (`_better_candidate()`) para cuando la misma obra vive en
tu catálogo y en uno compartido a la vez: sin él, cuál "gana" en un empate de
score dependía del orden de iteración de las cuentas, no de nada semántico —
verificado con un test que deliberadamente lista la candidata compartida
primero. Verificado con 262 tests de Python (`scripts\check.ps1` en verde) +
9 Playwright + recorrido manual en browser real contra un catálogo sintético
con cuenta compartida (consola sin errores, layout mobile sin overflow).
Queda P1-d — triage de la cola por causa y confianza —, el más grande de los
cuatro, para una sesión aparte.

**Fase 5, P1-c cerrado (2026-08-17, commit `4771c5c`).** Presentador único de
disponibilidad: `core/availability.js` nuevo, adoptado en `card.js`, `merge.js`
e `inbox-curation.js`; backend decora la cola de Curaduría y compare/merge vía
`AvailabilityService` (solo para mostrar, nunca lo que persiste
`apply_reviewed_merge`). De paso se encontró y corrigió que el comparador
(`merge.js`) tenía el mismo bug que Curaduría — la crítica original lo daba
por ya resuelto y no lo estaba. Verificado con tests nuevos (unitario + HTTP +
Playwright) y recorrido manual en browser contra un catálogo sintético.

**Fase 5, P1-a cerrado (2026-08-17).** Franja persistente de 3 estados
(`Archivo físico`/`Identidad compartida`/`Ficha en tu catálogo`, colores
anclados en `DESIGN.md`) en `core/scope-strip.js` nuevo, cableada en
Curaduría y Scanner; modos rotulados por alcance (`Tu catálogo` /
`Inventario de la instancia · Admin`); badge de Bandeja separado en dos
(`#inboxBadge` + `#inboxScannerBadge`) en vez de sumado. Bug real encontrado
y corregido en el camino: el feedback de éxito de Scanner escribía en un
elemento que quedaba `display:none` en modo Scanner — ninguna confirmación
exitosa se veía. Todo frontend, cero cambios de backend. Verificado con
Playwright nuevo (incluida una regresión específica del bug) y recorrido
manual en browser. Quedan P1-b y P1-d — en ese orden, según la Fase 5 de
abajo.

- **Fase 0** — `CLAUDE.md` existe (63 líneas).
- **Fase 1** — ruff/mypy configurados, `lint` job en CI, reformateo aplicado.
  Reporte de limpieza del working tree entregado; `scripts/cleanup-workspace.ps1`
  propuesto y **sin ejecutar** (nada borrado todavía, es tu decisión).
- **Fase 2** — Gate de calidad de búsqueda de v0.3.0 **cerrado**:
  `movie-inbox search-lab run --enforce` pasa (Precision@5 0.91, MRR/Recall@5
  1.0, 0 resultados prohibidos, 0 falsos positivos de auto-match). Job
  `search-lab` agregado a CI como gate real. Quedan 3 ítems del roadmap de
  v0.3.0 sin tocar porque no son de ranking: Curaduría todavía muestra
  `manual: sí/no` crudo (es el P1-c de Fase 5), la cola del Scanner no está
  organizada por causa/confianza (P1-d de Fase 5), y no existe comparación
  baseline-vs-candidato en Search Lab (siguiente incremento, sin fecha).
- **Fase 3** — `tests/test_frontend_quality.py` recortado a
  `tests/test_design_tokens.py` (solo tokens CSS). Garantías reales migradas a
  `tests/browser/test_ui_browser.py`, organizado en 3 clases por superficie.
  `browser-smoke` mide ~13s local, muy por debajo del límite de 8 min.
- **Fase 4** — `app.js`/`style.css`/`index.html`/`web/app.py` partidos, cero
  cambios de comportamiento. `web/app.py` (2153 líneas) → `web/dependencies.py`
  + `web/responses.py` + 8 routers en `web/routers/`, `app.py` bajó a 15.0 KB.
  `index.html` → 11 fragments servidos por `assets.py::render_html()`.
  `style.css` → 14 archivos en `static/css/`. `app.js` → 21 módulos ES nativos
  en `static/js/core/` y `static/js/surfaces/` (sin bundler, `<script
  type="module">`), el más grande `detail.js` a 37.9 KB. 256 tests + 6
  Playwright + ruff + mypy + wheel-smoke + `scripts\check.ps1` en verde;
  `docker-smoke` no se pudo correr local (sin Docker en este entorno) pero usa
  el mismo empaquetado ya verificado por wheel-smoke. Todo commiteado en 8
  commits atómicos sobre `master` (CLAUDE.md; groundwork de assets.py/
  pyproject.toml; CSS; HTML; JS; routers; tests; este archivo +
  `fase-4-tareas.md`), sin pushear.
  Decisiones que se apartaron del plan original (detalladas en el resumen de
  la sesión): `tests/test_package_layout.py` y dos tests de
  `tests/test_view_http.py` perdieron asserts de copy/nombres de función
  contra archivos que ya no existen como blob único; se agregaron 3 hooks de
  test (`window.openDetail/closeDetail/openSearchDescription`) en
  `bootstrap.js` porque Playwright los llama directo y los módulos ES no
  filtran al scope global como el `app.js` viejo.
  Encontrados y corregidos 3 bugs reales introducidos por la extracción
  automática (no preexistentes): una copia duplicada de `apiFetch` en
  `router.js`, y dos imports faltantes (`localFiles`,
  `COLLECTION_MULTI_FILTER_KEYS`, `curationCounts`/`privacyPreferences`) —
  ninguno se hubiera visto sin correr la app en un browser real.

**v0.3.0 publicado (2026-08-17).** El gate de salida ya estaba cerrado desde la
Fase 2; lo que faltaba era el trámite de release. Actualizados: `pyproject.toml`
(→ `0.3.0`), `CHANGELOG.md` (`[Sin publicar]` → `[0.3.0] - 2026-08-17`, con un
`[Sin publicar]` nuevo y vacío arriba), `CLAUDE.md` (línea de versión estable) y
`docs/roadmap.md`. Dos items que no llegaron a tiempo —disponibilidad efectiva
unificada en Curaduría, cola organizada por causa/confianza— se reasignaron
formalmente a v0.4.0; en la práctica ya eran P1-c y P1-d de la Fase 5 de abajo, esto
solo alinea `docs/roadmap.md` con lo que este archivo ya decía. Un tercer item
(comparación baseline-vs-candidato en Search Lab) queda sin versión asignada a
propósito — no encaja en el tema de v0.4.0 ("coherencia de interfaz"), es trabajo de
ranking. Falta commitear estos cambios y taggear `v0.3.0`: no se hizo solo porque no
se commitea sin pedido explícito, y un tag debe apuntar a un commit que ya tenga el
bump — preguntar antes de commitear/taggear.

**Pregunta de mobile vs. Fase 5 — resuelta (2026-08-17).** Mobile no se adelanta a la
Fase 5 dentro de este repo: van a ser proyectos separados. La visión real de Lucas es
más ambiciosa que un cliente delgado online-only — uso sin conexión con sync
oportunista en LAN/VPN cuando el server esté alcanzable, no solo lectura remota
mientras el server esté arriba. Eso justifica un repo aparte (`movie-inbox-android` o
como se termine llamando), con su propio toolchain Kotlin/Gradle, para no mezclarlo
con este repo Python. El plan inicial de esa idea quedó capturado en
`movie-inbox-android-plan.md` (raíz de este repo) para retomar en otra sesión o con
otro agente — es una foto de dónde quedó la conversación, no un plan ejecutable
todavía. Lo que sí sigue siendo trabajo de *este* repo: la Fase 5 (v0.4.0) de abajo, y
eventualmente una capa `/api/v1/` con auth por usuario/dispositivo cuando se retome
mobile. Ninguna de las dos depende técnicamente de la otra (no comparten archivos con
`web/security.py`/`web/dependencies.py` ni entre sí) — es una decisión de dónde poner
la atención primero, no de dependencias de código.

---

# Fase 0 — CLAUDE.md

El repo no tiene `CLAUDE.md` ni `AGENTS.md`. Eso significa que cada sesión de agente
re-descubre las reglas desde cero y algunas se pierden.

Escribí un `CLAUDE.md` en la raíz que contenga, en forma compacta:

- Cómo correr tests, linters y el servidor local (sacalo del README y del workflow, no lo
  inventes).
- Las 6 invariantes de arriba, con puntero al archivo que las define.
- El mapa de capas: qué va en `domain/`, `application/`, `infrastructure/`, `external/`,
  `web/`, `cli/`, y qué NO va en cada una.
- La regla de que `scripts/` son lanzadores finos de compatibilidad (<25 líneas, verificado
  por `test_layering.py`) y que la lógica nueva va al paquete.
- Qué archivos son datos personales y no se tocan.

**Que sea corto.** Apuntá a menos de 100 líneas. Un CLAUDE.md largo se ignora. Todo lo que
ya está bien explicado en PRODUCT.md o DESIGN.md se referencia, no se copia.

**Gate:** existe `CLAUDE.md`, tiene menos de 100 líneas, y todo comando que menciona se puede
ejecutar tal cual.

---

# Fase 1 — Herramientas y limpieza

Esto va temprano a propósito: es barato y protege todo lo que viene después.

## 1a. Linter y type checker

`pyproject.toml` no tiene ruff, black ni mypy. El proyecto tiene ~100 módulos Python, varios
de 40-50 KB.

- Agregá `ruff` (lint + format) y `mypy` como dependencias opcionales `[dev]`.
- Configurá ruff en `pyproject.toml`. Empezá con un ruleset conservador (`E`, `F`, `I`, `UP`,
  `B`) y `line-length` coherente con el código actual — mirá qué ancho usa hoy, no impongas 88
  si el código está escrito a 100.
- Corré `ruff check --fix` y `ruff format`. **En un commit separado del resto**, para que el
  diff de reformato no se mezcle con cambios de lógica.
- Para mypy: arrancá en modo laxo con `--ignore-missing-imports`, y hacelo estricto SOLO en
  `src/movie_inbox/domain/` (que es puro y no tiene dependencias externas). Extenderlo al resto
  es trabajo para después.
- Sumá un job `lint` al workflow `.github/workflows/tests.yml`.

## 1b. Limpieza del working tree

Todo esto está gitignoreado, así que no afecta el repo, pero ensucia la carpeta y hace lento
cualquier listado o búsqueda:

- `scripts/.catalog-cache/images/` — ~536 MB, 843 archivos
- 15 archivos `scripts/catalogv3_links.*.bak.json` de ~1.7 MB cada uno
- `scripts/smoke-catalog.*.bak.json` (hasta 3.8 MB cada uno) + `catalogv2/v3/v4.json`
- `check-output.txt` en la raíz, 771 KB
- `.git.failed-init-backup/`, `scripts/.git.empty-backup/`, `scripts/.git.nested-backup/`
- `movie-inbox-main.bundle`, `movie-inbox-v0.1.0.bundle`

**No borres nada.** Son datos míos y algunos son backups de git. Hacé dos cosas:

1. Un reporte en pantalla: qué es cada grupo, cuánto pesa, y si es reproducible o no.
2. Proponé (sin ejecutar) un `scripts/cleanup-workspace.ps1` que mueva lo descartable a una
   carpeta `_to_delete/` con fecha. Yo decido después qué borrar.

Además, verificá si hay algo que **debería** estar en `.gitignore` y no está — corré
`git status --porcelain` y contame si aparece algún archivo generado o personal.

**Gate:** `ruff check` sale limpio, `mypy src/movie_inbox/domain` sale limpio, el job de lint
está en CI y pasa, la suite de tests sigue verde, y tengo el reporte de limpieza.

---

# Fase 2 — Cerrar v0.3.0

Según `docs/roadmap.md`, v0.3.0 es "confianza en búsqueda, matching e inventario" y el gate de
salida exige cero falsos positivos conocidos en auto-match y merge, más métricas mínimas del
corpus dorado.

`movie-inbox search-lab run` ya existe y mide el ranking productivo, pero hoy una baseline que
no alcanza los umbrales reporta `FAIL (baseline recorded)` y **retorna código 0**. O sea: no es
un gate, es un informe.

1. Corré `movie-inbox search-lab run --json reports/search-baseline.json --html reports/search-baseline.html`
   y mostrame los números actuales: Precision@5, MRR, Recall@5, resultados prohibidos y
   precisión de auto-match, en los cuatro contextos.
2. Decime, con esos números en la mano, **qué falta para poder activar `--enforce` sin que CI
   se ponga rojo**. Si falta trabajo de ranking, listámelo priorizado; no lo hagas todavía.
3. Si los números ya alcanzan: agregá un job `search-lab` al workflow con `--enforce` y
   dejalo como gate real.
4. Repasá `docs/roadmap.md` contra el `CHANGELOG` y decime qué ítems de v0.3.0 están hechos y
   cuáles no. El roadmap dice que Search Lab "todavía mide únicamente el ranking productivo
   actual" y que la comparación baseline vs candidato "comienza en el siguiente incremento" —
   confirmá si eso sigue siendo cierto.

**Gate:** sé exactamente qué falta para cerrar v0.3.0, con números, no con impresiones.

---

# Fase 3 — Destrabar los tests de frontend

`tests/test_frontend_quality.py` afirma que ciertos strings literales existen dentro de
`app.js` y `style.css`. Por ejemplo:

```python
self.assertIn("Conservar ambas y vincular", self.javascript)
self.assertIn("body.distinct_review_token", self.javascript)
self.assertIn("function prepareCatalogViewModel()", self.javascript)
self.assertIn("scanner-create-guard.is-confirming", self.css)
```

Eso no prueba comportamiento: prueba que un texto aparece en un archivo. Cualquier refactor
los rompe sin que nada esté realmente mal. **Hoy son un candado contra el trabajo de la fase 4
y de v0.4.0.**

Objetivo: cada garantía real que hoy protegen esos tests tiene que seguir protegida, pero
desde el lugar correcto.

1. Recorré `test_frontend_quality.py` test por test y clasificá cada assertion:
   - **Garantía real de comportamiento** → migrar a `tests/browser/test_ui_browser.py`
     (Playwright ya está en CI). Ejemplos: gestión de foco del diálogo, que las regiones
     estructurales no sean `aria-live`, que `Al azar` esté fuera del `<nav>`, que la
     disponibilidad efectiva no se presente como el flag manual.
   - **Garantía de diseño verificable estáticamente** → puede quedarse como test de archivo,
     pero sobre *tokens CSS*, no sobre strings de UI. El test de contraste AA y el de
     `--text-label: 10px` son legítimos: leen variables, no copy.
   - **Assertion sobre copy o sobre nombres internos de función** → borrar. `"Conservar ambas
     y vincular"` es copy que va a cambiar en v0.4.0; `"function prepareCatalogViewModel()"`
     es un detalle de implementación.
2. Escribí los tests de Playwright equivalentes ANTES de borrar los viejos. Quiero ver el
   solapamiento en un commit, y el borrado en el siguiente.
3. `tests/browser/test_ui_browser.py` hoy tiene 6 KB. Va a crecer bastante: organizalo por
   superficie (Colección, Bandeja, Ficha) y no en un solo test gigante.
4. Ojo: el job `browser-smoke` de CI tiene `timeout-minutes: 10`. Si la suite crece mucho,
   avisame antes de que se acerque al límite.

**Gate:** `test_frontend_quality.py` ya no contiene assertions sobre copy ni sobre nombres de
función; las garantías equivalentes corren en Playwright; `browser-smoke` pasa en CI y tarda
menos de 8 minutos.

---

# Fase 4 — Partir el frontend y `web/app.py`

Estado actual:

```
src/movie_inbox/web/static/app.js      393 KB   ← un solo archivo
src/movie_inbox/web/static/style.css   205 KB   ← un solo archivo
src/movie_inbox/web/static/index.html   57 KB
src/movie_inbox/web/app.py              87 KB
```

v0.4.0 es un rediseño transversal de interfaz. Hacerlo sobre un `app.js` de 393 KB es caro y
cada iteración mete el archivo entero en contexto.

**Esta fase no cambia comportamiento. Ni uno solo.** Si en el camino encontrás un bug, anotalo
y seguí; no lo arregles acá.

## 4a. Mapa antes de cortar

Primero, sin tocar nada: dame un mapa de `app.js`. Qué bloques hay, cuántas líneas ocupa cada
uno, qué estado global comparten, y dónde están los acoplamientos que van a doler. Mismo
ejercicio, más breve, para `style.css` y `web/app.py`.

Con ese mapa proponeme el corte. Mi hipótesis de partida, pero discutila si el código dice otra
cosa:

- Por superficie: `home`, `collection`, `inbox/scanner`, `inbox/curation`, `inbox/imports`,
  `club`, `admin`.
- Más un núcleo compartido: cliente HTTP + CSRF, presentador único de disponibilidad, estado
  y router, helpers de DOM, formateo.

## 4b. Ejecución

- **ES modules nativos** (`<script type="module">`). Sin bundler, sin build step, sin
  dependencias nuevas. Es una decisión deliberada del proyecto y la quiero mantener.
- Un módulo por vez, con la suite verde entre cada uno. No un big bang.
- CSS: partí en archivos por superficie más un `tokens.css` con las variables. Si `index.html`
  termina con muchos `<link>`, usá `@import` desde un `style.css` raíz y medí si el costo de
  red importa en localhost (probablemente no).

## 4c. Trampas concretas de este repo

Estas te van a morder si no las mirás antes:

1. **`pyproject.toml` empaqueta assets con globs planos:**
   ```toml
   [tool.setuptools.package-data]
   "movie_inbox.web" = ["static/*.html", "static/*.css", "static/*.js"]
   ```
   `static/*.js` **no matchea subdirectorios**. Si movés archivos a `static/js/`, la wheel sale
   sin ellos y el job `wheel-smoke` te lo va a decir tarde. Actualizá los globs.
2. **`scripts/wheel_smoke.py`** verifica assets empaquetados. Actualizalo en el mismo commit
   que cambie la estructura.
3. **`web/assets.py`** y el montaje de estáticos en FastAPI tienen que servir subdirectorios y
   devolver `Content-Type: text/javascript` para los módulos, o el browser los rechaza.
4. **`web/security.py`**: si hay CSP con `script-src`, los ES modules pueden requerir ajuste.
   Verificalo antes de cortar, no después.
5. **`tests/test_package_layout.py`** y **`tests/test_docker_packaging.py`** probablemente
   asumen la estructura actual. Leelos primero.

## 4d. `web/app.py`

87 KB en un módulo. Partilo en routers de FastAPI por superficie, alineados con el corte del
frontend. `app.py` queda solo con la creación de la app, middleware y el registro de routers.
Ojo con los imports circulares y con no violar el layering al hacerlo.

**Gate:** ningún archivo de `web/static/` supera 40 KB; `web/app.py` baja de 15 KB; los cuatro
jobs de CI pasan (tests, wheel-smoke, browser-smoke, docker-smoke); y el comportamiento observable
es idéntico — mismo resultado en la suite de Playwright, sin tests nuevos ni modificados salvo
imports.

---

# Fase 5 — v0.4.0: los 4 P1 de Impeccable

**Recién arrancá esta fase cuando las anteriores estén cerradas.** Sobre el frontend ya partido
esto es viable; sobre el monolito, no.

Leé `.impeccable/critique/2026-08-14T05-13-09Z__src-movie-inbox-web-static-index-html.md`
completo. Marca 4 P1 y un score de 22/40.

**Mi lectura, y quiero que la valides o la refutes antes de proponer nada:** los cuatro P1 son
el mismo problema con cuatro caras. La cadena
`archivo físico → identidad compartida → ficha personal` no es visible en pantalla, y por eso:

- **P1-a** — la Bandeja mezcla alcance compartido (Scanner, inventario de la instancia) y
  personal (Curaduría, tu catálogo) bajo una sola metáfora y un solo badge.
- **P1-b** — "Sin coincidencia" se presenta como ausencia comprobada ("Obra ausente del
  catálogo") cuando solo significa que el algoritmo no encontró candidata. Ese salto epistémico
  es lo que produjo duplicados como `1917`.
- **P1-c** — Curaduría muestra `manual: sí/no` mientras el resto de la app calcula
  disponibilidad efectiva (declaración manual **o** evidencia del servidor). Una misma ficha se
  ve `Disponible` en Colección y `manual: no` en Curaduría.
- **P1-d** — la cola está diseñada para casos, no para 600-700 casos: hasta 8 candidatas por
  caso, todas con el mismo peso visual, sin triage por causa ni confianza.

Si estás de acuerdo, el trabajo se ordena así:

1. **Un presentador único de disponibilidad**, compartido por Colección, ficha, Curaduría y
   comparador: `Disponible` + procedencia (`Inventario verificado`, `Declaración manual`, o
   ambas). Esto solo ya cierra P1-c. Es el cambio más chico y el de mayor retorno: empezá acá.
2. **Una franja de alcance persistente** durante toda la decisión, con los tres estados
   (`Archivo físico`, `Identidad compartida`, `Ficha en tu catálogo`), y cada CTA marcando qué
   filas cambia — antes y después. Separá los contadores del badge por alcance. Cierra P1-a.
3. **Procedencia en cada candidata** (`En tu catálogo`, `Identidad del inventario`, `Catálogo
   compartido`) más la razón de confianza. Y renombrar: `No encontramos una coincidencia segura`
   en vez de `Obra ausente del catálogo`, con búsqueda local prellenada antes de permitir el
   alta. Cierra P1-b.
4. **Triage de la cola por causa y confianza**: `Falta identidad`, `Probable ficha existente`,
   `Conflicto de año/tipo`, `Sin señales`. Top 3 candidatas visibles, el resto a demanda. Cierra
   P1-d. Es el más grande — dejalo último y proponemelo por separado.

También hay un P2 que vale la pena y es barato: **Scanner no deja recibo durable ni reversible**.
Al resolver, el caso desaparece y el feedback va a la franja general. Un recibo junto al detalle
(`Inventario compartido: 1 archivo vinculado a 1917` / `Tu catálogo: sin cambios`) más historial
con Deshacer, como ya tiene Curaduría.

Y las observaciones menores de terminología: `Scanner` → `Escáner` o `Archivos`, `Sin link` →
`Sin referencia`, y sacar `manual: sí/no` que es lenguaje de implementación.

**Restricción de diseño:** `DESIGN.md` es un contrato vigente y la auditoría dice explícitamente
que la estética funciona ("no hace falta rediseñar la estética para resolver este problema").
Esto es arquitectura de información, no un cambio de look. No toques la paleta, la tipografía ni
el vocabulario de sombras.

**Gate:** una nueva corrida de `$impeccable audit` sobre la misma superficie, con score y P1
count comparables contra la corrida del 2026-08-14. Y una prueba concreta: que yo pueda mirar
una sola pantalla y decir sin dudar qué entidad sobrevive después de `Combinar` y dónde quedan
los archivos.

---

## Arrancá

Confirmame que leíste los contratos, decime si algo de este plan te parece mal ordenado o mal
entendido, y empezá por la **Fase 0**.
