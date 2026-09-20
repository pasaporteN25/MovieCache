# v0.9.0 — cierre del frente visual

2026-09-14. El owner prioriza cerrar la candidata actual y difiere **U8 completa**
a otra release, sin número asignado. Este documento sustituye la secuencia de
release del plan `home-v0-9-0-u5-u8-plan.md`, no sus decisiones de diseño futuro.

## Alcance congelado

**Ampliación del owner, 2026-09-19:** sin apuro por cerrar, se incorpora la ficha
con puntajes públicos, streaming e indicadores compactos; conserva el dossier y
prioriza obra/registro personal. Incluye X8.4 para guardar sin pisar cambios de otro
dispositivo. Brief `../briefs/detail-public-context-v1.md`. Este ajuste sustituye
la restricción de retoques de este corte sólo para ese frente; no reabre U8/U9/MW1.

Home U4/U5 y cartelera derecha U6 ya integradas, más U7.5a con imágenes actuales.
No agregar VHS al azar/animación, nuevas APIs de imágenes, sonido ni auditoría
móvil integral. Conservar el botón Al azar actual. Móvil sólo smoke de reflow.
Corregir bloqueos de uso, permisos, selección, foco y regresiones; nuevos retoques
cosméticos no bloqueantes van al fix posterior.

## V9.V1 — regresión de navegador (U4.6b)

1. Correr `python -m unittest tests.browser.test_ui_browser -v` con `.venv`.
2. Inventariar cada fallo: contrato retirado, defecto actual o dependencia externa.
3. Migrar assertions de consola inferior/onda/carcasa retiradas preservando teclado,
   fecha, fuente, origen, diálogo y reflow. No borrar tests ni debilitarlos para aprobar.
4. Corregir regresiones actuales dentro del frente visual; separar backend si aparece.
5. Volver a correr la suite completa, no sólo el subconjunto U5 de 15 casos.

Salida: suite completa verde y registro de fallos corregidos. U5 ya aporta 15
Chromium + 26 JS + 17 Python; esa evidencia no reemplaza este gate completo.

## V9.V2 — zoom y cierre espacial (U5.3.4/U6.5)

**Cerrado por aceptación manual del owner, 2026-09-14.** Capturas originales,
alcance y límites en `u5-u6-owner-acceptance/`. Se conserva debajo el procedimiento
solicitado como antecedente; no implica una nueva medición automatizada.

1. Usar zoom real de página **200%** en navegador de escritorio; registrar tamaño
   de ventana y nivel de zoom. Viewport reducido, CSS zoom y escala del dispositivo
   no son evidencia equivalente. Si el navegador integrado sigue sin permitirlo,
   usar Chrome/Edge disponible o pedir una verificación manual guiada al owner.
2. Revisar controles accesibles, foco visible, lista/consulta/dos carteleras sin
   solapamiento, scroll local y ausencia de overflow horizontal del documento.
3. Confirmar seis filas a zoom normal en 1280/1440/1920; a 200% puede cambiar la
   composición responsive, pero ninguna acción debe perderse.
4. Consolidar el estado U6.2–4 contra evidencias de U4.3/U4.4/U5.4–5; son base
   implementada, no una orden de volver a diseñarla. Completar estados faltantes.

Salida: evidencia real del zoom y cierre coherente de U5.3.4/U6.5 y sus padres.

## V9.V3 — higiene, changelog y gate local

- Ruff/formato de cambios visuales y scripts de QA que se incluirán en el repo.
- Mypy completo, compilación, suites JS/Python/navegador y `git diff --check`.
- Changelog en `[Sin publicar]`: Home empotrada, dos carteleras, consola única,
  fuente sincronizada, imágenes actuales y accesibilidad. No anunciar U8.
- Revisar el diff y separar entregables de capturas/prototipos; no eliminar archivos
  ni incluir trabajo ajeno a ciegas. No cambiar todavía `0.9.0.dev0` a estable.

Diagnóstico local de esta planificación: Ruff detectó 61 hallazgos en
`test_ui_browser.py`, `test_package_layout.py`, `serve_u4_2c_review.py` y los tres
necesitan formato. Mypy sobre los dos archivos de tests pasó; los tres errores
históricos de packaging no deben seguir listados como fallos actuales.
Esto no es el resultado de lint/mypy globales.

**Actualización 2026-09-14:** el formateo mecánico y las correcciones de tipos dejan
Ruff, `ruff format --check`, mypy y compilación globales en verde. Se actualizó
`CHANGELOG.md` sin anunciar U8. `python -m unittest discover -s tests -v` ejecutó
881 pruebas: 880 pasan; `test_frontend_assets_are_served_without_inline_code` aún
espera `.spotlight-stage` en el CSS monolítico y debe migrar a los módulos CSS actuales
como parte de U4.6b. Repetir la suite después de ese ajuste antes de marcar V9.V3.

## V9.V4 — candidata y publicación coordinada

1. Revisar/agrupar cambios locales y preparar commit; confirmar publicación al PR.
2. Verificar PR de `release/0.9.0` contra `master`, diff y CI del commit exacto.
3. Ensayar upgrade 0.8.0 → 0.9.0 en Docker sobre copia descartable con backup,
   checksum y restauración. Seguir `docs/release-checklist.md` completo.
4. Responsable de release sincroniza versión/changelog/README/CLAUDE/roadmap;
   CI vuelve a verde. Owner fusiona con merge commit y etiqueta `v0.9.0`.

No se encontró Docker ni `gh` en PATH al planificar; el PR/CI no fue verificado.
Docker requiere un host con Compose y copia autorizada, no el catálogo único.
El CLI ausente no impide revisar el PR por otro medio disponible.

No se hizo commit, push, merge, tag, despliegue ni cierre ficticio de gates en
esta planificación. El primer tramo ejecutable es **V9.V1**, seguido de V9.V3;
el único dato externo imprescindible para V9.V4 es dónde ensayar el upgrade seguro.
