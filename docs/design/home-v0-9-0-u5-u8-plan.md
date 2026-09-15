# Home — corte visual v0.9.0: U5 y U8

> **Cambio de alcance del owner, 2026-09-14:** U8 completa queda para otra release
> sin número asignado. Las secciones U8 siguientes conservan el diseño futuro,
> pero ya no son requisito de v0.9.0. El cierre vigente está en
> `v0-9-0-visual-closeout.md`: U4.6b, zoom U5.3.4/U6.5, higiene/changelog y gate V9.

2026-09-13. Plan de ejecución solicitado por el owner. Modo: Operate.
Extiende `home-evolution-backlog-2026-09-12.md`; no reemplaza la estética B aceptada.
Estado al 2026-09-14: U5.1.3/U5.2/U5.3.1–3 implementadas;
evidencia en `u5-first-delivery/` y `u5-long-list-gate/`. U5.3.4 tiene evidencia
desktop/reflow/foco; aceptación manual del owner completa U5.3.4/U6.5
(`u5-u6-owner-acceptance/`). U5.4–5 completadas con gate local
en `u5-integration-gate.md`; U8 sigue pendiente.
No declara completas las épicas ni aprobada la publicación.

**Confirmación del owner, 2026-09-14:** la lista mostrará las mismas obras del
estante seleccionado (actualmente hasta seis propuestas), no toda la colección
asociada. Queda resuelta la pregunta de alcance que precedía a la implementación.
Primera entrega ejecutada: U5.1.3 + U5.2 + U5.3.1–2, con pruebas del contrato y
cabecera/retorno visibles. Luego se completaron listas largas y U5.4–5.
Siguiente frente: U4.6b y gate de release. U8 diferida.

## Objetivo y frontera de versión

Completar la Home nueva y conectar estante/lista/consulta antes de v0.9.0.
La presencia física del sorteo se difiere. Se preservan dos carteleras simétricas, consola única,
material petróleo/latón, tipografías y geometría de VHS de U4.4.

El owner confirma que el resultado al azar se revela en el lomo y actualiza consola
y cartelera derecha; **no abre ficha automáticamente**. La abre «Ver más».
Se proponen alcance personal completo en Home y conservación de la lista al sortear,
coherentes con el plan anterior; no sortear sólo el estante ni incluir Club sin copia.

Los retoques no bloqueantes descubiertos después podrán ir a un fix posterior.
No se posponen selección equivocada, permisos, pérdida de datos, controles inutilizables
o CI roto. U4.6b y el gate de release siguen vigentes. No se fusiona ni etiqueta por
cerrar este documento. U7.5b, U9 y MW1 quedan fuera de este corte.

## Evidencia de partida — U5.1.1

- `application/home_service.py`: `HOME_SECTION_LIMIT = 6`, secciones recortadas y
  `limits.section_items` explícito. La lista del estante representa esa selección
  editorial, no todo el catálogo de su género/director/colección. No ampliar la API
  para prometer un conjunto completo en este incremento.
- `home.js`: `playlistEntries()` ya lee `section.items`; `activateHomeShelf()` ya
  coordina fuente y consulta. `selectHomeShelfEntry()` todavía cambia sólo consulta:
  ése es el gesto a revisar, no reconstruir tabla ni carteleras.
- Las claves necesitan origen: `selectionSource` + `selectedEntryKey`; Club y catálogo
  pueden tener IDs iguales. El autoplay ya está separado de la selección.
- `catalog-data.js` carga `/api/items`; `web/routers/catalog.py` devuelve `rows` sin
  paginación en ese endpoint. Home puede reutilizar el catálogo cargado para el sorteo;
  no hay evidencia que justifique crear otra API ahora.
- `randomCandidates()` usa `items` fuera de Colección. En Colección, filtros sin
  resultados caen silenciosamente en todo el catálogo: revisar ese borde en U8.1/3,
  no trasladar el fallo al nuevo lomo. `openRandomDetail()` acopla sorteo y apertura:
  separar resultado/presentación sin romper el comando fuera de Home.
- Los tests JS actuales esperan que un VHS no cambie la lista. Migrarlos con pruebas
  de independencia del autoplay, no borrar esos escenarios.

## Tramo 1 — U5: lista del estante y retorno visible

| Subtarea | Entrega comprobable | Dependencia |
| --- | --- | --- |
| U5.1.1 | Auditoría de payload, límite y estado existente (arriba) | Completada |
| U5.1.2 | Matriz de interacción, copy y recuperación de fuente (abajo) | Contrato y gate extendido verificados |
| U5.1.3 | Fixtures diaria + dos estantes, Club/ID coincidente, vacío y 1/6/20/100 filas | Implementada |
| U5.2 | Enlace mínimo de fuente/consulta; memoria por origen y fallback válido | Implementada; gate U5.5 verificado |
| U5.3.1 | Cabecera: fuente, nombre y cantidad; distinguir selección editorial | Implementada |
| U5.3.2 | Retorno explícito a programación y placa activable por clic/teclado | Implementada |
| U5.3.3 | Seis filas completas; listas largas con scroll local, cabecera y acciones estables | Implementada |
| U5.3.4 | Evidencia desktop, fuente larga, 0/1/6/20/100 filas y reflow acotado | Cerrada con aceptación manual del owner |
| U5.4–5 | Regresión de foco, permisos, autoplay y fuentes; gate de integración | Completadas; 15 Chromium + 26 JS + 17 Python |

### U5.1.2 — contrato de interacción

| Gesto | Lista y consulta | Izquierda / foco |
| --- | --- | --- |
| Tab pasivo | No cambia fuente ni selección | Sólo mueve foco |
| Clic/Enter/Espacio en VHS; flechas dentro del estante | Lista de ese estante y obra seleccionada | Autoplay independiente; foco queda en lomo |
| Activar placa | Lista de ese estante; selección recordada válida o primera | Foco en control estable; sin salto al comienzo del documento |
| Seleccionar fila / flechas en tabla | Consulta de esa fila; sincroniza lomo si existe | Foco en fila; izquierda no cambia |
| Autoplay | No cambia lista ni consulta | Sólo avanza póster izquierdo |
| Volver a programación | Lista diaria de la jornada mostrada; primera obra válida | No cambia jornada; foco vuelve a control diario estable |
| Hoy/Ayer | Lista diaria y primera obra válida de jornada pedida | Carga explícita; conservar contenido válido ante error |
| Nueva selección durante carga de día | Gana la selección más reciente | Ignorar respuesta/error obsoleto, liberar controles |
| Seleccionar póster izquierdo | Lista diaria y obra de ese póster | Mantiene jornada |
| Obra eliminada | Primera válida del mismo conjunto; vacío honesto si no quedan | Aviso único, sin acciones obsoletas |
| Fuente eliminada | Retorno a diaria, aviso breve | Recuperación de foco sin destino desconectado |
| Resultado al azar | Consulta/derecha del resultado; lista conserva su fuente | Izquierda independiente; no inventar fila seleccionada |

En cabecera: «Cartelera de hoy/ayer · N obras» para diaria; «Selección del estante»
+ nombre + «N obras» para fuente editorial. No decir «todos los títulos».
En fuente editorial mostrar «Volver a programación» además de Hoy/Ayer; los controles
de fecha describen programación, no filtros de la sección. Conservar «Ver colección»
como salida al conjunto filtrado más amplio cuando el descriptor lo permita.

Placa: botón real integrado al metal, misma dimensión/material, foco cyan y estado
activo distinguible de hover. No convertir toda la categoría en un botón anidado.
Cabecera: no añadir una nueva barra externa; usar el display existente. Nombre largo
puede ocupar dos líneas; no desplazar carteleras ni reducir otra vez toda la Home.
Más de seis filas sólo es fixture de robustez por ahora: scroll local con fila enfocada
visible, sin scroll vertical automático de página por seleccionar un VHS.

## Tramo 2 — U8: objeto terminal y revelación

| Subtarea | Entrega comprobable | Dependencia |
| --- | --- | --- |
| U8.1 | Cerrar alcance, disponibilidad efectiva, vacío y recorrido fuera de Home | Auditoría inicial arriba; recorrido Home confirmado |
| U8.2.1 | Composición terminal con placa «AL AZAR» y un único lomo reutilizable | U8.1 + U5 |
| U8.2.2 | Lámina/fixture de estados y copy; reutilizar asset y texto HTML | U8.2.1 |
| U8.2.3 | Integración del objeto, foco y navegación; no cuenta como sección editorial | U8.2.2 |
| U8.3 | Resultado compartido, selección única y no repetición inmediata | U8.1 |
| U8.4.1 | Comparación real A rebobinado / B tira de títulos; elegir antes de cerrar efecto | U8.2.2 |
| U8.4.2 | Implementar efecto elegido en etiqueta, no en la caja ni todo el rail | U8.3 + U8.4.1 |
| U8.4.3 | Reduced motion directo, concurrencia y anuncio único | U8.4.2 |
| U8.4.4 | Gate visual/performance y capturas de estados finales | U8.4.3 + U8.5 |
| U8.5–6 | Conectar botón/lomo/consulta y verificar flujo completo | U8.2–4 |

### Estados del objeto

- Inicial: placa AL AZAR, etiqueta «Elegir una obra», sin película ficticia.
- Ocupado: control estable, «Eligiendo…», `aria-busy`; sin secuencia de anuncios.
- Disponible: título y año reales, acento habitual; «Otro al azar» accesible.
- No disponible: material secundario apagado y «?» decorativo tenue; título legible
  y texto semántico «No disponible». El signo no representa identidad dudosa.
- Sin candidatos: motivo contextual y salida a preferencia/Colección; nunca lomo
  animándose indefinidamente ni botón deshabilitado sin explicación.
- Resultado fuera de alcance al activar sólo disponibles: conservar consulta como
  consulta, aclarar que no es elegible y ofrecer nuevo sorteo; no sorteo oculto.
- Error/obra retirada: fin de ocupado, mensaje y reintento explícito, sin acción a ID viejo.

Propuesta de animación A: etiqueta rebobinada 450–700 ms, título final elegido antes
del efecto. B: tira breve de títulos decorativos, misma duración; sin imágenes ajenas
ni apariencia de premio/casino. A es recomendación, todavía no elección aprobada.
El foco no se desmonta; los clics mientras está ocupado se coalescen en la acción
actual, no generan una cola. Reduced motion muestra resultado directamente y evita
scroll animado. Un solo anuncio final con título/estado; no sonido (U9 fuera de corte).

## Entregas y gate de v0.9.0

1. Alcance confirmado el 2026-09-14; preparar U5.1.3 y construir U5.2 + U5.3.1–2
   como primera entrega visible, verificando la matriz de interacción.
2. U5.1.3/U5.3.3–4 + U5.4–5: pruebas y capturas en 1280/1440/1920; smoke 390/320,
   zoom 200%, errores de carga, Club y retorno de ficha. No declarar cierre por mockup.
3. **Otra release:** U8.1–3 + U8.2: estados del lomo y comparación U8.4.1 para elegir el efecto.
4. **Otra release:** U8.4.2–4 + U8.5–6: flujo conectado, 0/1/muchos candidatos, disponibilidad, clic
   rápido, navegación, autoplay simultáneo y movimiento reducido.
5. Completar U4.6b, lint/tipos del frente visual y changelog; revisar diff propio y
   actualizar el PR con autorización. Gate local/CI y upgrade con backup según V9.
6. Sólo entonces cierre de versión por el responsable de release. Retoques posteriores
   van al fix, no se convierten en nuevas épicas que bloqueen indefinidamente v0.9.0.

## Estado del PR y coordinación

Checkout verificado: `release/0.9.0`, remoto `pasaporteN25/MovieCache`. Documentación
V9 registra PR abierto contra `master`; no se pudo verificar número, diff remoto ni CI
en esta revisión (CLI `gh` ausente y consulta HTTP fallida). Hay cambios visuales locales
sin commit que por tanto no están incluidos aún en el PR. No se hizo push, commit,
merge, cambio de versión ni acceso a catálogos personales para preparar este plan.

Se conserva todo el trabajo ajeno; no se crea otro PR ni se dispara otro agente.
U5.2/U8.3 son dependencias técnicas acotadas del flujo, no una autorización para ampliar
datos/API, rehacer backend o incorporar galería U7.5b. Si requieren ese crecimiento,
documentar el traspaso y consultar antes de implementarlo.
