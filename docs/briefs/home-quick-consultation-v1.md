# Consulta rápida de Inicio · release/0.10.0

- **Modo:** operar/explorar. La barra permite identificar la obra elegida, consultar
  su resumen y abrir su ficha mientras se recorre la tabla o los VHS.
- **Dirección aprobada:** opción 2, barra desplegable. Conserva petróleo, latón y las
  tipografías de Inicio; no repite el póster «En consulta». Título y estados forman
  un grupo; «Resumen» y «Abrir ficha» quedan visibles y alineados en la cabecera.
- **Interacción:** cerrada al cargar un catálogo. El botón nativo «Resumen» alterna
  `aria-expanded` y controla una región inerte y oculta para lectores de pantalla
  mientras está cerrada. La apertura se conserva entre obras, estantes, rotación
  automática y cambios de día durante la sesión. El despliegue no reconstruye la
  cartelera, no cambia la selección y conserva el foco. Movimiento de 180 ms,
  desactivado con movimiento reducido.
- **Contenido:** sinopsis real, créditos disponibles, contexto editorial y acceso a
  la colección. Una razón editorial nunca se presenta como sinopsis. Sin sinopsis,
  se indica su ausencia; sin créditos, no se reserva una sección vacía. «Editar mi
  ficha» aparece en el resumen sólo para entradas del catálogo personal. Las obras
  del Club conservan su acción y origen propios.
- **Adaptación:** en móvil, acciones debajo de la identidad y contenido en una
  columna, objetivos táctiles de al menos 44 px. Títulos y créditos largos pueden
  envolver. En escritorio la sinopsis se resume a tres líneas y la ficha completa
  sigue a un clic.
- **Entrada de la ficha:** «Abrir ficha» acerca y endereza la contratapa VHS en
  360 ms, con una inclinación inicial leve y desaceleración. El fondo aparece en
  300 ms. Se anima la caja real en CSS, sin capturar ni transformar toda la página.
  El diálogo recibe el foco de inmediato; Escape o un clic fuera interrumpen la
  entrada y cierran sin espera. Movimiento reducido desactiva caja y fondo.
- **Alcance:** render de consulta, estilos en `home-inset.css`, una acción delegada
  y pruebas. Sin cambios al API, datos personales, selección editorial, carteles ni
  estantes. Colores y tipografías siguen la implementación vigente de Inicio;
  los avisos del detector sobre la paleta histórica de DESIGN.md no justifican
  reemplazar la estética aprobada.

## Validación · 2026-09-25

- 26 pruebas JS y 42 de navegador aprobadas. Verificación visual de escritorio y
  móvil; prueba de estabilidad del encabezado entre 320 y 1920 px, incluyendo 1000 px.
- Ruff, formato, mypy de la prueba modificada, sintaxis JS y `git diff --check`: OK.
- Tras agregar la animación: 42 pruebas de navegador aprobadas, incluyendo sus
  estados inicial/intermedio/final, cierre durante la entrada en 1280 y 390 px,
  reapertura, restitución del foco y movimiento reducido. Revisión visual en la
  app con datos descartables; Ruff, formato, mypy y sintaxis JS aprobados.
- Suite general: 1105 pruebas, 9 omitidas y 2 fallos en
  `test_external_partial_rate_limit.py`. Los módulos `external/common.py`,
  `external/registry.py` y esa prueba coinciden con HEAD: las dos lecturas sucesivas
  de `time.monotonic()` pueden ser iguales en este entorno, y `noted_at >= since`
  cuenta el límite anterior. Se reprodujo el problema por separado; queda fuera
  de esta implementación de Inicio.
