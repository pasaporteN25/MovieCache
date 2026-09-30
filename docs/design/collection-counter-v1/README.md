# U10 — Mostrador de Colección

Implementado y verificado el 2026-09-28 en `release/0.10.0`.
Dirección y tareas: [brief](../../briefs/collection-counter-v1.md).

## Referencia y resultado

- `concept.png`: muestra generada con ImageGen y aprobada por el usuario. No es
  captura productiva; sus títulos, portadas y estados son ilustrativos.
- `viewport-{1920,1440,1280,390,320}.png`: primer viewport del renderer real.
- `actual-{1920,1440,1280,390,320}.png`: páginas completas del mismo renderer.

Todas las capturas reales usan datos sintéticos y una instancia desechable. Incluyen
una imagen cargada (fixture Metropolis existente), una portada que falla, fallbacks,
título extremo y estados personales/disponibilidad combinados. No se publica ningún
catálogo personal. La cabecera «Browser Test» identifica explícitamente el fixture.

Se conservó la composición aprobada, compactando la placa y usando botones de filtro
en lugar de desplegables. La textura y los biseles proceden del kit real de Inicio;
la imagen generada no se usa como fondo ni como controles rasterizados.

## Verificación

- 61 pruebas de Chromium: `BrowserInterfaceTests`, `CollectionCounterTests`,
  `test_home_random` y `test_detail_context`. Incluye seis pruebas nuevas de U10.
- 34 pruebas JS: `node --experimental-vm-modules --test tests/js/*.test.mjs`.
- 73 pruebas HTTP: `python -m unittest tests.test_view_http -q`.
- Ruff check y formato de ambos archivos de prueba modificados: aprobados.
- Mypy sobre `test_collection_counter.py` y sintaxis de los módulos JS modificados: aprobados.
- `git diff --check`: aprobado.
- Revisión independiente Impeccable: aplicadas correcciones de filas móviles,
  acceso externo, foco al cargar, opciones compactas y documentación.
- `detector.json`: una pasada; 51 avisos informativos de paleta, tamaño y radios.
  Son derivados del kit material aprobado y de la tipografía documentada en U10;
  no hay hallazgos de severidad superior a advisory. No se cambió el sidecar antiguo.

Casos verificados: búsqueda+filtros, limpiar consulta/limpiar todo, URL antigua
`mode=search`, Agregar y volver con contexto, 0/15/65 obras, carga 30→60→65 sin
reemplazar nodos anteriores, foco en primera obra nueva, recarga e historial con
cantidad/posición, ficha y regreso, acceso a externos, fallos de imagen, títulos
largos, 320/390/640/860/1280/1440/1920 px, foco visible y movimiento reducido.

Reproducir capturas en PowerShell:

```powershell
$env:COLLECTION_EVIDENCE = '1'
.venv/Scripts/python.exe -m unittest tests.browser.test_collection_counter -v
```

Alcance: sin cambios de matching, endpoints, permisos ni datos personales. Se mantiene
el envío explícito de consultas por Enter/Buscar y el mínimo previo de dos caracteres.
La release continúa abierta; este trabajo no publica ni despliega la aplicación.
