# U2-R.7d: regresión y cierre contractual

Fecha: 2026-09-06. Estado: **U2-R aceptada; sin gates rojos abiertos**.

## Veredicto de integridad

**Pasa.** Inicio conserva un sistema específico de Movie Inbox: cartelera física,
playlist CRT, mueble continuo con lomos HTML, consola inferior y contratapa VHS. Los
assets aportan materialidad; títulos, metadata, acciones, estado, foco y nombres
accesibles permanecen en el DOM. El cierre no introdujo contenido decorativo engañoso
ni volvió a una grilla intercambiable de tarjetas.

La lectura acordada es cartelera/playlist superior y exploración inferior coordinadas,
pero no acopladas de forma destructiva. Un lomo actualiza categoría y ficha inferiores;
sólo activar el módulo reprograma la playlist. El brief, la implementación y las pruebas
ya expresan ese mismo contrato.

## Audit Health Score final

| # | Dimensión | Score | Evidencia principal |
| --- | --- | --- | --- |
| 1 | Accesibilidad | 3/4 | Teclado, foco visible/retorno, roles/nombres, touch real, forced colors y reduced motion cubiertos. |
| 2 | Performance | 3/4 | Imágenes lazy salvo cartelera prioritaria, autoplay acotado y movimiento opcional; no se hizo profiling de campo. |
| 3 | Responsive | 4/4 | Sin overflow horizontal en cinco viewports; 720p fluye antes que comprimir y móvil conserva targets críticos de 44×44 px. |
| 4 | Theming | 3/4 | Jerarquía de señales coherente; persisten tonos materiales heredados aún no inventariados en `DESIGN.md`. |
| 5 | Integridad de implementación | 4/4 | Modelo de estado, semántica y lenguaje visual son coherentes y propios del producto. |
| **Total** |  | **17/20 — Bueno** | **U2-R puede cerrar.** |

## Resumen ejecutivo

- Issues verificados al cierre: **P0 0 · P1 0 · P2 0 · P3 0**.
- El primer pase completo encontró un gate rojo de test: una respuesta de red tardía
  podía competir con el evento sintético usado para validar el fallback de poster.
- La prueba ahora espera el error real antes de recorrer `load → error`; el caso aislado
  y la suite completa quedaron verdes.
- Ruff también encontró dos fragmentos pendientes de formato; se aplicó su formateador
  sólo a los archivos señalados.
- Los smoke tests TMDB en vivo siguen siendo voluntarios y se omiten sin token; ninguna
  ruta U2-R depende de ellos.

## Gates integrados

| Corte | Resultado | Evidencia |
| --- | --- | --- |
| R7a · encuadre desktop | Cerrado | `u2-r7a-visual-gate-2026-09-06.md` y seis capturas versionadas |
| R7b · contenido/estados | Cerrado | `u2-r7b-content-state-matrix-2026-09-06.md` |
| R7c · interacción/a11y | Cerrado | `u2-r7c-interaction-accessibility-gate-2026-09-06.md` |
| R7d · regresión/contrato | Cerrado | este documento, brief/revisión actualizados y suites completas |

## Verificación final

- Suite general: **560 tests OK**, **4 skipped** por token TMDB live voluntario.
- Suite `BrowserInterfaceTests`: **31/31 OK**.
- Matriz focal R7c: **10/10 OK**.
- Ruff lint: **OK**.
- Ruff format: **180 archivos formateados**.
- mypy estricto: **177 archivos sin issues**.
- `compileall` sobre `src`, `scripts` y `tests`: **OK**.
- `node --check`: **26 módulos JavaScript OK**.
- `git diff --check`: **OK**.

## Detector técnico

El detector de `impeccable` sobre `src/movie_inbox/web/static` informó 147 entradas:
146 avisos consultivos de color/tipografía y un warning `side-tab`. El único warning fue
descartado en contexto: `home.css` dibuja con bordes transparentes el triángulo de 6 px
del selector activo; no aplica un borde lateral grueso a una tarjeta.

Los avisos consultivos confirman una deuda documental, no 146 defectos de interfaz:
130 tonos literales y 16 escalas tipográficas no figuran en la definición estructurada
de `DESIGN.md`. Predominan sombras, desgaste y tonos materiales anteriores a R7. No se
normalizan automáticamente porque hacerlo sin revisión visual puede borrar la identidad
de los objetos VHS.

## Patrones y hallazgos positivos

- La separación `carouselItemId` / `playlistSource` / selección manual evita que el
  temporizador robe foco o cambie la obra explorada.
- Los controles complejos usan botones/tablas reales, roving tabindex, estados ARIA y
  un equivalente de puntero, teclado y touch.
- Los fallbacks de poster conservan estructura y nombre aunque falle la red.
- La altura insuficiente degrada a flujo vertical; no se resuelve ocultando sinopsis,
  hechos o acciones.
- Las variantes personal/Club mantienen el permiso de edición en el punto de render.

## Límites y próximas acciones no bloqueantes

Una pasada manual exhaustiva con NVDA/VoiceOver y profiling con hardware objetivo
mejorarían la evidencia de release, pero no hay un fallo concreto de U2-R que dependa de
ellas. La transición vertical de cartelera y una señal derivada de medios reales siguen
aisladas en U2-X.1/U2-X.2. El siguiente frente funcional habilitado es U3.

Si se decide formalizar la paleta material heredada, conviene ejecutar
`$impeccable document` sobre los tonos realmente visibles y luego repetir
`$impeccable audit`; no corresponde tokenizar cada sombra de forma mecánica.
