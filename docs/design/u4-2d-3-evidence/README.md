# U4.2d.3 — Consolidación de la Home

2026-09-11. Implementación terminada; aceptación visual del owner el 2026-09-12. Datos de demostración descartables;
no se modificó el catálogo personal. Las capturas corresponden a la aplicación real.

## Resultado

- Ancho común centrado (máximo 2240 px), estante contenido entre ambos cantos.
- Una sola consola superior: contexto/origen, ficha/edición/colección, título,
  sinopsis, dos imágenes, créditos, acceso, estado, duración y firma VHS.
- Retiro real de `homeShelfPreview`, su renderizador y la onda/miniportada anteriores.
- Se preservan selección independiente de programación/autoplay, seis filas y VHS
  de 308 px. Póster de altura estable para no deformar el asset al crecer la consola.
- Avisos breves de selección; retorno al botón de ficha/edición incluso cuando el
  autoplay reemplaza el DOM durante el diálogo. No se guardó ninguna edición.

## Verificación

Aplicación FastAPI real con fixture temporal: `scripts/serve_u4_2c_review.py`.
El script imprime URL y credenciales de demostración al arrancar; no usa el catálogo
del usuario. Las dos imágenes repetidas son datos de prueba, no una propuesta visual.

- Escritorio 1280, 1440 y 1920: seis filas sin scroll vertical interno, sin overflow
  horizontal de página ni de consola. Máximo ancho comprobado también a 2482.
- VHS → consola; origen y anuncio correctos, sin fila diaria seleccionada por error.
- `Ver más` y `Editar mi ficha`: obra correcta, foco recuperado al cerrar tras autoplay.
- `Ver colección`: navega al catálogo; Club: detalle compartido y ninguna edición personal.
- Vacía: sin consola huérfana ni host inferior. Sin imágenes: dos fallbacks explícitos.
- 390 px: título largo y contexto envuelven, botones de 44 px, consola apilada y
  desplazamiento horizontal local de tabla/rails, no de la página.
- `node --experimental-vm-modules --test tests/js/home-selection.test.mjs`: **8/8**.
- `.venv/Scripts/python.exe -m unittest tests.test_package_layout tests.test_home_service tests.test_home_snapshot_repository`: **20/20**.
- Syntax checks de Home/detail y `git diff --check`: sin errores; detector Impeccable
  de layout final sobre ambos CSS: `[]`. No sustituye inspección visual.

## Capturas

- `desktop-1280.png`, `desktop-1440.png`, `desktop-1920.png`, `desktop-2482.png`.
- `mobile-390.png`: consola larga, con foco visible en edición.
- `empty-1440.png`, `missing-1440.png`: extremos sin contenido/imágenes.

## Límites y siguiente paso

No se ejecutó la suite completa de navegador por shell: QA conectado mediante CUA.
Se migró el test focal de selección compartida a la consola única; las aserciones
geométricas históricas de U2 y la consola inferior aún requieren migración en U4.6.
El fixture enriquece créditos sólo en el payload editorial; la ficha completa puede
mostrar `Sin dato` para esos mismos campos. No es una diferencia productiva inducida.
U4.3 debe pulir la integración material y densidad de la consola definitiva, especialmente
créditos a anchos intermedios y encuentro del marco del póster con la pantalla.
U4.4 conserva placas/VHS. Sin commit solicitado; base U4.2 aceptada el 2026-09-12.
U4.3/U4.4/U4.6 siguen pendientes; el plan de evolución U5–U9/MW1 debe informar su encaje.
