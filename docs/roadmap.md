# Hoja de ruta

Este documento conserva decisiones de producto que no deben confundirse con trabajo
activo. El alcance inmediato sigue siendo un gestor personal self-hosted para cine,
series, anime y documentales.

## Hitos de producto

### v0.3.0: confianza en busqueda, matching e inventario — publicado 2026-08-17

Gate de salida cumplido: cero falsos positivos conocidos en auto-match y merge,
metricas minimas del corpus dorado (`movie-inbox search-lab run --enforce`, gate real
en CI) y prueba manual con snapshot de catalogo sin escrituras. Detalle completo de lo
publicado, en `CHANGELOG.md` bajo `[0.3.0]`.

Dos items de esta version no se resolvieron a tiempo y pasan a v0.4.0 porque son
arquitectura de informacion, no ranking (ver abajo): disponibilidad efectiva unica sin
llegar a Curaduria, y cola de revision sin organizar por causa/confianza.

Un tercer item queda sin version asignada: la comparacion entre baseline y algoritmo
candidato en Search Lab. `movie-inbox search-lab` sigue midiendo unicamente el ranking
productivo actual; ese incremento no tiene fecha todavia.

### v0.4.0: coherencia de interfaz — publicado 2026-08-22

Aplico el backlog de Impeccable sobre la Bandeja (Scanner y Curaduria) una vez
estabilizada la semantica de v0.3.0: los 4 P1 de la critica del 2026-08-14 (alcance
mezclado, "sin coincidencia" presentado como ausencia comprobada, disponibilidad
manual contradiciendo la efectiva, cola sin triage) quedaron resueltos, mas una pasada
completa de consistencia del sistema de diseño (`extract`/`typeset`/`adapt`/`polish`:
tokens de color y tipografia, paridad de foco por teclado, terminologia).

Gate de salida: una nueva critica con puntaje sobre la misma superficie, **29/40**
contra el 22/40 del 2026-08-14. Detalle completo en `CHANGELOG.md` bajo `[0.4.0]`.

La critica de cierre encontro una capa nueva del mismo problema que esta version vino
resolviendo, mas chica que los 4 P1 originales pero real. Dos arreglos puntuales
cerraron el mismo dia (border-radius mobile de Curaduria/Scanner); pasan a un
incremento posterior, sin version asignada todavia. De los cuatro, uno ya esta
cerrado:

- **Cerrado.** Scanner segui­a sin historial ni deshacer — el P2 original de la
  critica del 14/08, nunca cerrado formalmente. Vincular a identidad existente,
  omitir y crear-y-vincular tienen ahora una `Actividad` propia (persistente o por
  sesion) con deshacer que restaura el estado exacto previo a la decision,
  incluidas las candidatas detectadas y, para crear, el alta en el catalogo.
  Deshacer se rechaza si algo mas toco el caso desde entonces.

Quedan tres:

- Casos duplicados con mismo titulo y año son indistinguibles en la cola, el detalle y
  el titulo del comparador de fusion.
- Curaduria no tiene la navegacion por flechas ni la busqueda que si tiene Scanner,
  pese a compartir la misma forma de pantalla.
- El estado de decision del comparador de fusion no esta anunciado para lectores de
  pantalla (`aria-live`).

### v0.5.0: cliente basico

La hipotesis de trabajo es un primer cliente Android en Kotlin para una instancia
self-hosted. Debe confirmarse antes de congelar el alcance de v0.4.0.

- Inicio de sesion seguro contra una URL HTTPS elegida por el usuario.
- Lectura, busqueda y detalle del catalogo personal.
- Cambio de estado, fecha de vista, puntaje y review.
- Disponibilidad fisica en modo lectura y apertura de links externos.
- Sin administracion, Scanner, importaciones, curaduria avanzada ni uso offline en la
  primera entrega.

Este hito requiere antes una API versionada y documentada, sesiones aptas para
dispositivos y pruebas de compatibilidad entre servidor y cliente.

## Implementado en el incremento de descubrimiento y scanner

- Buscar el catalogo personal en el servidor, incluyendo titulos originales,
  espanoles, ingleses, aliases, nombres de archivo e identificadores externos.
- Separar visualmente los resultados locales, Wikipedia, IMDb y FilmAffinity, con
  carga progresiva por fuente.
- Usar el mismo ranking al buscar, comparar y agregar para detectar duplicados antes
  de escribir.
- Conservar fechas de estreno con precision y procedencia, y usarlas para una seccion
  editorial `Estrenada un dia como hoy` cuando exista fecha completa confiable.
- Presentar el acceso como carnet de videoclub sin revelar perfiles antes de iniciar
  sesion.
- Permitir al owner explorar solamente las raices habilitadas por el servidor,
  comprobar una ruta antes de registrarla y mantener las rutas ocultas a miembros.
- Omitir directorios auxiliares como `extras` y `sample`, y tratar archivos
  multipartes (`cd1`, `cd2`, `disc1`, `part2`) como una sola obra con varios archivos.

Estas capacidades quedan protegidas por pruebas de busqueda, esquema, fechas de
estreno, scanner, persistencia SQLite y seguridad de las rutas. La validacion visual
del login, las estanterias por fuente y el explorador de carpetas forma parte del gate
del mismo incremento.

## Siguientes incrementos

- Mejorar el enrichment con una fuente estructurada opcional, evaluando TMDb y sus
  condiciones de uso antes de agregar una API key a la instancia.
- Permitir reglas de exclusion configurables por biblioteca, partiendo de defaults
  seguros.
- Disenar una landing o endpoint publico de presentacion separado de la API privada.
  No debe reutilizar tokens de sesion ni exponer catalogos por defecto.
- Definir el contrato de integracion de esa futura landing. Los endpoints actuales
  son privados, requieren sesion y token anti-CSRF, y no constituyen una API publica.
- Mantener HTTPS en el reverse proxy del homeserver (por ejemplo, Nginx) y documentar
  despues una opcion guiada para certificados; Movie Inbox no termina TLS por si solo.
- Investigar paquetes compartibles y sincronizacion explicita entre homeservers sin
  convertir una instancia en un servicio publico involuntario.

## En investigacion

- Juegos y musica requieren modelos verticales propios. No se agregaran como valores
  de `kind` hasta definir campos, fuentes, disponibilidad y experiencias de detalle
  especificas para cada medio.
- Clientes Kotlin, Radarr, Sonarr, Letterboxd y otras integraciones siguen siendo
  direcciones validas, pero se priorizan despues de estabilizar busqueda, scanner,
  backup y contratos de datos.
