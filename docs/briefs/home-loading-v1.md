# Carga de Inicio · release/0.10.0

- **Modo:** operar. La espera debe ser reconocible, breve y recuperable.
- **Forma:** HTML inicial con los dos marcos de cartelera, seis filas de texto,
  consulta compacta y tres grupos de seis lomos VHS. Comparte grilla, tamaños y
  materiales con Inicio; los placeholders no son controles ni datos inventados.
- **Señal:** «Preparando tu videoteca» y «Cargando cartelera y estantes…». Sólo pulsa
  un punto de luz; sin barridos sobre toda la pantalla ni animaciones por lomo.
  Movimiento reducido deja la señal estática. Skeleton decorativo oculto a lectores
  de pantalla; mensaje de estado y `aria-busy` describen la carga.
- **Tiempo:** sesión y catálogo se solicitan en paralelo. Ambos deben terminar bien
  antes de aplicar el catálogo. Se conservan autenticación, redirección de cambio
  de contraseña y los llamados habituales a `loadCatalog()`.
- **Fallo:** se retira el skeleton, el encabezado indica «Carga interrumpida» y un
  mensaje ofrece «Reintentar». Al reintentar reaparece la estructura y, si resulta
  bien, el foco vuelve al título de Inicio.

## Medición y validación · 2026-09-25

Medición local con catálogo descartable de dos obras y demora artificial de 350 ms
en cada respuesta de sesión/catálogo, tres navegaciones por versión. Mediana hasta
Inicio disponible: **885 ms antes / 517 ms después**, aproximadamente 42% menos.
El inicio de ambas consultas pasa de secuencial a prácticamente simultáneo.
No es un benchmark del catálogo personal ni del servidor de producción.

44 pruebas de navegador y 26 pruebas JS aprobadas. La cobertura incluye consultas
simultáneas, catálogo retenido hasta recibir sesión, error/reintento y foco,
desaparición del skeleton, movimiento reducido y anchos entre 320 y 1920 px.
Revisión visual en 1440 y 390 px. El detector informa avisos de paleta respecto de
DESIGN.md histórico: se conserva la estética petróleo/latón de Inicio vigente.

Suite general completada: 1105 pruebas, 9 omitidas y los mismos dos fallos previos
en `test_external_partial_rate_limit.py` (temporización de los límites externos),
sin cambios en esos módulos. Ruff, formato, mypy, sintaxis JS y `git diff --check`
aprobados.
