# Edición explícita según permisos (U2.4) — y cierre de [U2]

## Qué hacía falta realmente

U2.2 ya había implementado la gate real (`Editar mi ficha` sólo para
`origin.kind === "catalog"`, ausente para `origin.kind === "collection"`) y U2.3 ya
conectaba `Ver más` al dossier compartido. Antes de escribir código nuevo, esta entrega
auditó las tres superficies que puede abrir Inicio para confirmar si faltaba algún
endurecimiento real o si el trabajo ya estaba hecho:

1. **`#detailDrawer`** (dossier personal, abierto por `Ver más`/`Editar mi ficha`).
   `openDetail(id)` sólo puede mostrar un `id` presente en `items`, que es siempre el
   catálogo del usuario autenticado (`/api/items` ya lo scopea server-side). Es
   estructuralmente imposible que este dossier muestre una obra ajena, así que su
   control de edición (`Editar registro`, ya existente) no necesitaba ninguna gate
   nueva: siempre es la obra propia.
2. **`homeShelfPreview()`** (previsualización de una estantería). `EditorialHomeService`
   sólo produce dos `origin.kind`: `catalog` (obra propia) y `collection`
   (recomendación de una colección seguida, todavía no agregada). No existe un tercer
   caso de "catálogo de otro miembro" en Inicio. La gate de U2.2 ya cubre exactamente
   esos dos casos.
3. **`#sharedDetailDialog`**, reusado por dos flujos de sólo lectura:
   `openHomeCollectionDetail()` (recomendación de Club desde Inicio) y
   `openSharedDetail()` (catálogo compartido de otro miembro, en Club). Ninguno de los
   dos arma nunca un botón de edición — sólo `Agregar a mi catálogo`/`Ver colección
   completa` en un caso, y filas de sólo lectura (`dt`/`dd`) en el otro.

Conclusión: el modelo de permisos ya estaba bien conectado de punta a punta. Lo que
faltaba era **verificarlo explícitamente con pruebas**, no escribir gates nuevas —
escribir código adicional sin una gate faltante real habría sido una abstracción sin
propósito.

## Pruebas nuevas

- `test_home_shelf_collection_entries_never_show_an_edit_action`: una entrada
  `origin.kind === "collection"` en una estantería nunca ofrece `Editar mi ficha`
  (ni en la previsualización ni en `#sharedDetailDialog` al abrir `Ver ficha del
  Club`), sólo `Agregar a mi catálogo`.
- `test_selecting_and_previewing_a_shelf_entry_never_mutates_the_catalog`: navegar con
  flechas/Home/End entre lomos, seleccionar uno con clic, abrir la previsualización,
  abrir el dossier con `Ver más` y cerrarlo con Escape no dispara ningún
  `POST`/`PATCH`/`PUT`/`DELETE` contra `/api/*` — se registra cada request de escritura
  durante la secuencia y se afirma que la lista queda vacía.

Junto con las pruebas ya existentes de U2.2/U2.3 (`Editar mi ficha` presente y
funcional para origen `catalog`, dossier/transición/cassette), esto cubre el cierre
pedido: "flujos de obra propia/obra de Club/solo lectura y pruebas de que no aparecen
controles de escritura donde no corresponden."

## [U2] queda completo

Con U2.0–U2.4 cerradas, Inicio quedó reconstruido como escenario de videoclub sin
cambiar `/api/home`, `/api/items` ni ninguna ruta existente: mostrador de control
(U2.0), cartelera-lista Winamp con ambientación auditada (U2.1), estanterías de lomos
con selector de categoría y previsualización basada en el marco VHS (U2.2), apertura
reversible hacia el dossier con su cassette negro permanente (U2.3), y el modelo de
permisos verificado de punta a punta (U2.4). El próximo frente pendiente en el tablero
es [A2] (cliente Android), que esta epopeya no tocó ni bloqueó.
