# Opción B — integración real de Home

2026-09-13. B elegida por el owner tras el comparador U4.3/U6.1/U7.5.
**U4.3 implementada; U6.1 cerrada por elección. Sin commit solicitado.**
Este corte no cierra U4.4/U4.6, U5, el gate completo U6 ni adquisición/corrección U7.

## Resultado

Dos carteleras comparten una abertura: izquierda Hoy/Ayer, derecha «En consulta».
La consola única ocupa el ancho común debajo de las dos, antes de la biblioteca.
No hay un segundo panel bajo el estante. Se preservan material y assets aprobados,
portadas completas, Oswald/Barlow/Plex y VHS existentes. La retícula de B se trasladó
a `home-inset.css`, no se agregó una segunda hoja de overrides de producción.

La derecha deriva de la consulta existente, incluyendo origen Club; no posee estado
de selección ni autoplay propios. Abre la misma ficha que Ver más y omite edición
personal para Club. Foco de póster y botón se distinguen aunque compartan acción.
Al abrir un diálogo se pausa el autoplay para no destruir el control de retorno.

U5 sigue pendiente: clic en VHS cambia consulta/derecha; activar categoría cambia
lista. El comparador simulaba el contrato futuro de U5; la implementación no toma
esa simulación por autorización para completar toda la épica.

## Imágenes: corte U7.5 con contrato actual

Se consumen `backdrop_image` y `page_image`, sin nuevas APIs ni URLs inventadas.
Dos URLs distintas: dos ventanas. Una URL: ventana amplia. Cero: ausencia explícita.
Se colapsan URLs idénticas; esto no sustituye el dedupe canónico del futuro resolver.
El owner permite repetir cuando falta material, pero no exige hacerlo por defecto.
Se conserva aquí la ventana amplia comparada; no se almacena un asset duplicado.

Carga y error tienen texto propio y `aria-busy` se limpia al terminar. La región
reserva 184 px: error/ausencia no bloquean acciones ni desplazan la biblioteca por
una descarga. Los errores de nodos anteriores no modifican las imágenes actuales.
Procedencia, elección/corrección manual persistida y galería portable siguen U7.2–4.
No se añade un enlace de corrección que la ficha todavía no pueda cumplir.

## QA conectada

Aplicación FastAPI real con catálogo y usuario desechables, iniciada con
`.venv/Scripts/python.exe scripts/serve_u4_2c_review.py`. El proceso sólo escucha en
loopback, imprime puerto aleatorio y credenciales de la muestra. No usa datos reales.
Se incorporó al helper el caso «Imagen fallida», con un 404 intencional.

| Ancho | Marco | Consola | Resultado |
| --- | --- | --- | --- |
| 1280 | 206 px | 1166 px | 6 filas, marcos pares, sin overflow |
| 1440 | 206 px | 1319 px | 6 filas, marcos pares, sin overflow |
| 1920 | 261 px | 1780 px | 6 filas, marcos pares, sin overflow |
| 2482 | 274 px | 2192 px | 6 filas, marcos pares, sin overflow |
| 390 | 148 px | 303 px | Smoke emulado; tabla/consulta sin solapamiento |

En todos: una consola, ancho interior completo, seis filas sin scroll vertical local
en muestra poblada y última fila por encima de la consulta. Las columnas secundarias
ceden por breakpoint; no se escala la letra para hacer caber dos marcos.

Verificado además:

- abrir/cerrar ficha desde derecha devuelve foco a derecha;
- abrir/cerrar desde Ver más devuelve foco a Ver más, también con error de imagen;
- en error real, ventana válida cargada y ventana fallida muestran estados separados;
- seleccionar VHS de título largo actualiza derecha y consola sin desbordes;
- origen Club: ficha correcta, sin edición personal, retorno al póster derecho;
- sin imágenes: ausencia honesta; editorial vacía: sin acciones ni portada antiguas;
- independencia de autoplay/consulta y claves coincidentes entre fuentes en tests.

13 pruebas JS pasan con `node --experimental-vm-modules --test tests/js/home-selection.test.mjs tests/js/home-images.test.mjs`.
17 pruebas Python pasan con `.venv/Scripts/python.exe -m unittest tests.test_package_layout tests.test_home_service -q`.
El entorno no tiene pytest; se usó el runner unittest del proyecto. Scan de layout
sin hallazgos. No equivale a haber migrado/corrido toda la suite de navegador U4.6.

Capturas `b-real-{ancho}.png`: vistas parciales de la app real con fixture, no el
comparador. `b-real-1440.png` muestra la composición superior y
`b-real-1440-shelf.png` el estante. Las medidas de la matriz provienen del DOM:
el capturador de página completa dejó zonas sin pintar, por lo que se conservaron
capturas de viewport, no evidencia de página completa.
Limitaciones: no teléfono físico, zoom 200% ni auditoría completa de orden de foco
móvil; MW1/U6.5 conservan esos gates. La lista de conjuntos extensos espera U5.

## Siguiente trabajo visual

U4.4: contacto de VHS con suelo, anclaje de placas, contraste/desgaste e iluminación
coherentes con el frente. Luego U4.6/gate final. U5.3 aporta cabecera/retorno de lista
tras su contrato de lógica; U7.5 restante necesita datos; U8.2–3 diseña el VHS al azar.
