# Caja, contratapa y editor VHS

Implementación de la dirección aprobada, `release/0.10.0`, 2026-09-29.
[Contrato de diseño](../../briefs/vhs-case-editor-v1.md).

## Resultado

- Colección abre la contratapa; el sticker menor abre la ficha para editar.
- La portada se conserva completa. Acercamiento con mouse o foco, sin mover la grilla;
  cinta pequeña abajo, caja negra con cinta grande para imágenes ausentes o fallidas.
- Editor por tareas con formularios persistentes y guardado conjunto. Se mantienen
  conflictos, privacidad, enlaces, disponibilidad y bloqueos por campo.
- Guardado lento bloquea cambiar de obra, cerrar o iniciar otra transición. El destino
  se captura antes de guardar. Al terminar se conserva la página larga de Colección.
- El fondo fotográfico está explícitamente diferido.

## Evidencia

Capturas de navegador sobre catálogos temporales y datos de prueba; no datos del usuario.

- `cases-with-artwork.png`: grilla con portada real de prueba, fallo de imagen y títulos largos.
- `case-artwork-focus.png`: portada completa y cinta pequeña al enfocar.
- `collection-desktop.png`, `case-focus.png`: reposo y foco con fallback.
- `back-cover-desktop.png`: sticker con espacio propio.
- `editor-1440.png`, `editor-1000.png`, `editor-390.png`, `editor-320.png`: editor adaptable.

[Marca y prompts](../../../src/movie_inbox/web/static/img/brand/README.md).
Fuente local [Permanent Marker](https://github.com/google/fonts/tree/main/apache/permanentmarker),
licencia Apache 2.0 conservada junto al archivo.

## Revisión

Impeccable Finish Reviewer revisó la entrega. Se atendieron sus cuatro observaciones:
documentación durable, navegación durante guardado lento, títulos largos y marco material.
El detector se ejecutó una vez (`detector.json`, anterior a las correcciones): la fuente
se incorporó al sistema; los avisos de color/radio reflejan materiales de la dirección
aprobada. La transición de altura afecta exclusivamente al frente absoluto de una caja,
no a su lugar en la grilla (verificado), dura 260 ms y se desactiva con movimiento reducido.

## Verificación

Pruebas de navegador: guardado y conflictos, secciones, regreso/foco, respuesta demorada,
imágenes, variantes de contratapa, Colección/Inicio, enlaces y responsive. Pruebas HTTP
y de paquete verifican también las rutas estáticas y el empaquetado de assets.
Comandos usados: `unittest`, `node --experimental-vm-modules --test tests/js/*.test.mjs`,
Ruff, mypy y `git diff --check`. Resultados finales se registran en `tareas.md`.
