# Sinopsis expandible de la contratapa

Entrega en `release/0.10.0`, 2026-09-29. La sinopsis presenta hasta seis líneas.
«Leer más» se ofrece sólo si el párrafo realmente desborda a ese ancho y con la
fuente cargada. Al expandir se muestra completo y la contratapa desplaza su contenido
si hace falta. «Leer menos» contrae y conserva el botón enfocado y visible. Al abrir
otra obra, el estado vuelve a compacto. Sin JavaScript el texto queda completo.

Las cuatro capturas muestran el mismo dato largo ficticio, cerrado y abierto a
1440 y 390 px. El móvil puede necesitar scroll incluso cerrado porque imagen,
datos, créditos y registro tienen que seguir accesibles en una caja de altura fija.

Verificación: prueba de navegador con sinopsis corta y larga, dos anchos, teclado,
foco, reflujo y cambio de obra; prueba de imágenes/plantillas y suite JS. El gate
completo de release y CI se anotan en `docs/release-0.10.0-preparation.md`.
