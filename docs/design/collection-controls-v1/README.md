# Opciones del mostrador y rótulos de Inicio

Pedido del owner, 2026-10-04. [Brief](../../briefs/collection-controls-v1.md).

Abrir `index.html` desde un servidor estático en la raíz del repo. Las fuentes,
textura y colores pertenecen al sistema vigente; los datos son ilustrativos.
Las opciones todavía no están elegidas ni aplicadas a Colección productiva.

`verify.py` usa una instancia efímera de la app y el fixture de navegador del repo,
nunca el catálogo real. Requiere que la raíz se sirva en `127.0.0.1:8765` y las
dependencias de pruebas de navegador instaladas. Renderiza opciones a 1440/390/320
px y Home a 1440/390 px; `verification.json` registra overflow, texto y centrado.

- `compact-*`: selectores compactos y divulgación progresiva.
- `visible-*`: teclas de filtros agrupadas.
- `sidebar-*`: facetas laterales en escritorio, apiladas en móvil.
- `home-*`: app real con cartelera y portadas sintéticas; muestra «Ayer en cartel»
  y «Tu selección». «Hoy en cartel» sigue la misma placa y estilo.

Los rótulos usan Barlow Condensed local y se alinean con el centro de la placa del
asset, teniendo en cuenta el recorte vertical del marco. La revisión visual confirmó
la corrección en una segunda captura. Se conserva la tipografía/material del resto
de Home; no se modificó el tema global.
