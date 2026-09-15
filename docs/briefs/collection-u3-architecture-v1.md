# U3.1 — Arquitectura de Colección v1

**Estado:** aprobada por el usuario y congelada para implementación<br>
**Fecha:** 2026-09-08<br>
**Modo de superficie:** Operate<br>
**Implementación:** no incluida; este documento gobierna U3.2 y U3.3

## Trabajo y resultado

Colección es el destino operativo donde una persona examina su archivo, encuentra una
obra, amplía la búsqueda afuera, agrega una entrada o resuelve una coincidencia. Hoy esas
intenciones comparten una consola visualmente uniforme: `Agregar` sólo abre la raíz,
los filtros permanecen visibles aunque no afecten las tarjetas de búsqueda y
`Comparar` depende parcialmente de memoria en JavaScript.

El rediseño debe permitir reconocer la tarea activa sin aprender el modelo interno. El
éxito es que la persona pueda responder en todo momento: «¿estoy explorando, buscando,
agregando o resolviendo una coincidencia?», y volver sin perder consulta, filtros,
selección ni posición.

## Dirección elegida

Colección se organiza como un **mostrador de archivo con cinco modos explícitos**:
`explorar`, `buscar`, `agregar`, `comparar` y `vincular`. Los tres primeros forman el
selector de tarea estable; comparar y vincular son corredores de resolución con una
obra ancla visible. No son modales encima de la grilla ni variantes implícitas de un
mismo checkbox.

La grilla de cajas sigue siendo la superficie primaria. En `buscar`, la consulta se
comporta como otro filtro de esa misma grilla; no se crea una segunda representación
local con tarjetas genéricas. Las fuentes externas aparecen como una ampliación
secundaria. En `agregar`, ese orden se invierte: fuentes externas primero y
coincidencias locales como resguardo contra duplicados.

La identidad visual continúa «videoclub después de medianoche»: controles planos y
precisos, cajas materiales, señales cyan/magenta/doradas con función semántica. U3 no
reabre la Home ni convierte Colección en un dashboard de paneles redondeados.

## Anatomía estable

1. **Cabecera de tarea:** título `Colección`, selector `Explorar / Buscar / Agregar` y
   una línea breve que explica la intención activa.
2. **Entrada contextual:** ausente en explorar; consulta local en buscar; consulta de
   alta en agregar; consulta del lado opuesto en comparar/vincular.
3. **Controles de archivo:** Estado, Disponibilidad y Tipo siempre visibles en explorar
   y buscar. `Más filtros` contiene Dirección, Género, Década/rango, Fuente y Memoria.
4. **Lectura de estado:** chips activos, cantidad y orden forman una sola línea antes de
   resultados. Ningún filtro parece aplicarse a resultados que realmente lo ignoran.
5. **Resultados:** una grilla local persistente en explorar/buscar; estantes externos
   progresivos en buscar/agregar; corredor bilateral en comparar/vincular.

## Alcance y límites

- U3.2 puede cambiar `index.collection.html`, `css/catalog.css` y componentes de
  presentación de búsqueda, manteniendo endpoints y matching existentes.
- U3.3 implementa el contrato de URL/historial y las transiciones de modo.
- La ficha de detalle, Home, Club, Bandeja, algoritmos de búsqueda y política de
  matching quedan fuera de este rediseño.
- No se inventa un formulario de alta manual: si no hay fuente externa disponible, la
  interfaz lo explica y ofrece volver a buscar; no promete una capacidad inexistente.
- `Mezclar vista` es una presentación efímera: se conserva al abrir/cerrar una ficha y
  al volver dentro de la misma entrada de historial, pero no se promete como URL
  compartible.

## Estados y rangos obligatorios

- Catálogo: 0, 1, 2, 36, más de 36 y miles de obras.
- Consulta: vacía, 1 carácter, válida, larga, con acentos y `director:`.
- Resultado local: carga, encontrado, vacío y error recuperable.
- Fuentes externas: desactivadas, sin configurar, carga, parcial, fallback offline,
  cooldown, error por fuente, vacío y éxito.
- Resolución: ancla válida, ancla perdida al restaurar, candidato ambiguo, alta directa,
  vinculación, fusión revisada y alta forzada.
- Capacidades: lectura normal, escritura permitida y escritura no disponible. La UI se
  guía por capacidad del catálogo, no por asumir que `owner` siempre puede escribir.
- Responsive: 320, 390, 640, 860, 1280, 1440 y 1920 px; títulos y nombres de filtros
  largos; teclado, touch, foco visible y reduced motion.

## Reglas que el implementador no puede reinterpretar

- Editar la consulta en `comparar` conserva la obra externa y busca sólo el lado local.
- Editar la consulta en `vincular` conserva la obra local y busca sólo el lado externo.
- Salir de esos modos requiere `Volver`/`Terminar`, navegación o una acción explícita;
  escribir o enviar el campo nunca degrada silenciosamente a `buscar`.
- Los filtros de estantería sólo aparecen donde afectan de verdad el resultado local.
- `Agregar` abre `mode=add`, enfoca su consulta y cambia copy/jerarquía; no equivale a
  abrir Colección sin estado.
- Atrás/Adelante restaura modo, consulta, filtros, ancla, resultados recuperables,
  cantidad visible, foco razonable y posición de scroll.
- Una restauración incompleta muestra recuperación contextual; nunca cae en explorar
  sin explicar que perdió una comparación.

## Entregables vinculados

- Wireflow y contrato: `docs/design/u3-collection-wireflow-v1.md`.
- Evidencia del estado actual: `docs/design/u3-1-evidence/`.
- Captura reproducible: `scripts/capture_u3_1_audit.py`.

## Aprobación

El usuario aprobó esta arquitectura el 2026-09-08 y habilitó U3.2 y U3.3.
