# U5 — primera entrega conectada

2026-09-14. Implementados U5.1.3, U5.2 y U5.3.1–2, con el alcance confirmado por
el owner: la lista muestra las mismas obras del estante, no toda la colección.
U5.1.2 queda contrastada en los recorridos básicos de esta entrega; el gate completo
de fuentes, escalas, zoom y errores asíncronos sigue en U5.3.3–4/U5.4–5.

## Cambios

- VHS y placa programan la lista del estante y la consulta; el póster izquierdo
  conserva jornada, selección de rotación y temporizador independiente.
- Cabecera integrada con «Selección del estante», nombre, cantidad y «Volver a
  programación». Volver conserva la jornada y el póster en rotación; consulta la
  primera obra diaria válida. Pulsar el día ya activo también permite volver.
- Las placas son botones dentro de encabezados, no regiones enteras clicables.
  Estado activo magenta y foco cyan distintos; cada estante tiene parada de teclado
  en placa y lomo recordado. Tab pasivo no selecciona.
- Memoria por clave de obra y estante, resistente a reordenamiento; eliminación
  resuelve primera válida. Fuente eliminada vuelve a diaria con aviso.
- Alineación de fila/lomo limitada al scroll de sus contenedores, sin scrollIntoView
  de documento. La búsqueda del lomo incluye el origen para no confundir IDs de Club.

## Evidencia

Servidor de revisión con catálogo sintético: `scripts/serve_u4_2c_review.py`,
`http://127.0.0.1:49963/` durante esta sesión. No se modificó el catálogo personal.

- `shelf-1440.png`: cabecera del estante, fila/consulta sincronizadas, seis filas
  completas, dos carteleras y consola única.
- `header-320.png`: reflow acotado del nuevo control; no certifica mobile web.
  La cabecera fija y navegación móvil existentes siguen siendo trabajo MW1.
- `metrics.json`: 1280/1920/390/320, sin overflow horizontal de documento y sin
  scroll vertical local para seis filas. En 1440 se midió además 55 px de cabecera,
  seis filas y cero scroll local. Nombres largos/20/100 tienen prueba de render,
  **no** gate visual completo de lista larga todavía.
- Clic VHS y ArrowRight: consulta «Órbitas de papel» → «La habitación 27», foco en
  el lomo correspondiente y `scrollY = 315` antes/después.
- Club: placa → lista/consulta externa, cero controles de edición personal;
  ficha compartida abre y al cerrar vuelve a `consultation-view` del mismo origen.
- Ayer desde Club: fuente diaria «Cartelera de ayer», primera obra seleccionada,
  placa Club desactivada. Retorno a programación mueve foco al control del día.

## Pruebas y límites

Ejecutados y aprobados:

```powershell
node --experimental-vm-modules --test tests/js/home-selection.test.mjs tests/js/home-images.test.mjs
.venv/Scripts/python.exe -m unittest tests.test_package_layout tests.test_home_service -q
node --check src/movie_inbox/web/static/js/surfaces/home.js
node --check src/movie_inbox/web/static/js/core/bootstrap.js
git diff --check
```

20 pruebas JS y 17 Python. Fixtures dedicados en `tests/js/fixtures/home-sources.mjs`:
0/1/6/20/100 entradas y claves coincidentes entre catálogo/Club. Se migraron las
expectativas JS del gesto anterior preservando el ensayo del autoplay independiente.
Detector Impeccable, scope layout sobre `home-inset.css`: sin hallazgos.

Refinamiento con Impeccable, dentro de la composición/materiales B; sin assets,
frameworks ni endpoints nuevos. Se solicitó la revisión independiente que pide la
skill, pero el revisor no pudo ejecutarse por límite de uso. Sigue pendiente esa
revisión; no se sustituye por una certificación propia.

No se ejecutó el runner completo histórico de navegador ni el gate de release.
Restan U5.3.3–4/U5.4–5 y U4.6b; U8 no se implementó en esta entrega.
Sin commit, push, merge ni cambio de versión.
