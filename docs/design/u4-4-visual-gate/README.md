# U4.4 / U4.6 / U7.5 — cierre del frente visual

2026-09-13. Operate. Refinamiento de B, sin cambio de mundo visual ni de contrato U5.

## Alcance acordado

El owner autoriza separar U7.5 visual de la integración futura U7.2–4. Se conservan
dos carteleras, consola única, Oswald/Barlow/Plex y assets petróleo/latón existentes.
No se modifica Android, el catálogo del usuario ni se hace commit.

## Implementación

- Placas apoyadas en el travesaño continuo, con sombra de contacto corta.
- VHS a 2 px de la base: hover y selección no levantan la caja. Desgaste y luz
  más contenidos; selección magenta con indicador de forma; foco cyan independiente.
- Foco de categoría aplicado a su placa, no a un rectángulo que cubra todo el estante.
- Imágenes: 0/1/2, reserva espacial, carga y error locales, imagen completa.
- «Revisar imágenes en ficha» conserva obra/origen y retorno de foco. Para catálogo
  indica el editor existente de panorámica; Club mantiene sólo consulta.
- No se promete edición de portada: el backend actual sólo admite `backdrop_image`
  en metadata. Portada, galería portable, procedencia y corrección completa quedan
  en U7.5b tras U7.2–4.

## Evidencia

U4.4 implementada y U4.6a/U7.5a verificadas. Las comprobaciones compartidas están en
`tests/browser/home_visual_metrics.js`; las aserciones de consola y placas del
runner Python consumen la misma sonda, sin coordenadas de la carcasa descartada.

`geometry.json`: 1280/1440/1920 y smoke 390/320. En los cinco: dos carteleras del
mismo ancho, una consola de ancho interior completo, seis filas sin scroll local,
sin solapamiento con consulta ni overflow de documento. En desktop: VHS de
76 × 308 px, a 2 px del suelo; placa de 54 px, a 4 px de la caja. Selección y hover
no transforman su posición. Móvil conserva desplazamiento local de cada estante.

`contrast.json`: valores computados contra el fondo opaco real de pantalla. Mínimo
de texto muestreado 9,58:1; foco cyan 11,24:1. No se extrapola ese cálculo a cada
píxel de las texturas raster: placas y lomos se revisaron visualmente.

Capturas de viewport (no página completa): `desktop-1280.png`, `desktop-1440.png`,
`desktop-1920.png`, `shelf-focus-1920.png`, `error-1440.png`, `mobile-390.png`.
La muestra repite una imagen técnica de Metropolis; no acredita cobertura del catálogo.

Recorridos comprobados en la aplicación real con fixture descartable:

- selección de lomo sin mover la base; foco de categoría visible sólo sobre su placa;
- revisión de imágenes personales abre dossier, no la contratapa sin editor;
- abrir Editar metadata, guardar panorámica y reabrir conserva URL; cerrar devuelve
  foco a `consultation-images`; no se modificó el catálogo del owner;
- Club abre ficha compartida sin edición personal y devuelve foco al mismo botón;
- una ventana cargada y otra con 404 mantienen estados independientes y `aria-busy=false`;
- sin imagen hay ausencia honesta; vacío no conserva carteleras ni consola anteriores;
- nombre largo actualiza consulta/derecha sin romper la composición.

14 tests JS y 17 de servicio/packaging Python pasan. Sintaxis del archivo Python
de navegador verificada. Scan de layout sin hallazgos y `git diff --check` limpio.

## Límites y pendiente U4.6b

Se migraron pruebas geométricas de cartelera, placas, consola y mueble; se conservan
las aserciones de recorrido lateral y pie VHS. La sonda geométrica y sus condiciones
se ejecutaron por el navegador conectado. **No se ejecutó la suite Python de navegador
completa**: sus tests históricos de interacción todavía referencian `.home-shelf-preview`
y la señal retirada. U4.6 no se marca completa hasta migrarlos y ejecutar esa regresión.
No equivale a una auditoría integral de accesibilidad ni a validación multibrowser.

Móvil es smoke de reflow/overflow, no rediseño: conserva cabecera/navegación fijas y
un fallback de portada largo con scroll propio. MW1 debe revisar en teléfono físico
la densidad y los elementos fijos. Zoom 200% y pruebas completas de foco siguen en U6.5.

## Auditoría técnica acotada (Impeccable)

| Dimensión | /4 | Evidencia / límite |
| --- | --- | --- |
| Accesibilidad | 3 | Contraste de pantalla, foco/origen y nombres; sin certificación integral |
| Rendimiento | 3 | Sin assets nuevos ni movimiento del layout; sin perfil de rendimiento |
| Responsive | 2 | Geometría estable; densidad y chrome fijo móvil pendientes MW1 |
| Theming | 3 | Mundo petróleo/latón preservado; algunos colores locales permanecen |
| Integridad | 3 | Consola única y rutas reales; deuda de regresión U4.6b explícita |
| Total | 14/20 | Bueno dentro del alcance, no cierre general de producto |

Hallazgos abiertos: P2 pruebas históricas incompatibles (U4.6b), P2 densidad móvil
(MW1), P2 corrección de portada/galería sin contrato (U7.5b). No bloquear Ver más
ni inventar fuentes para aparentar resolución. No se detectó un P0/P1 nuevo en los
recorridos revisados. El scan automático no sustituye esta revisión visual.
