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

El incremento posterior de comparacion entre baseline y algoritmo candidato ya esta
implementado: `movie-inbox search-lab compare --candidate ...` ejecuta ambos rankings
sobre el mismo corpus y genera reportes JSON/HTML sin modificar produccion. El gate
productivo sigue usando la estrategia publicada hasta que una candidata demuestre una
mejora sin falsos auto-match.

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
cerraron el mismo dia (border-radius mobile de Curaduria/Scanner). De los cuatro
hallazgos restantes, los dos mas dificiles ya estan cerrados:

- **Cerrado.** Scanner seguia sin historial ni deshacer — el P2 original de la
  critica del 14/08, nunca cerrado formalmente. Vincular a identidad existente,
  omitir y crear-y-vincular tienen ahora una `Actividad` propia (persistente o por
  sesion) con deshacer que restaura el estado exacto previo a la decision,
  incluidas las candidatas detectadas y, para crear, el alta en el catalogo.
  Deshacer se rechaza si algo mas toco el caso desde entonces.
- **Cerrado.** Casos duplicados con mismo titulo y año eran indistinguibles en la
  cola, el detalle y el titulo del comparador de fusion. Ahora distinguen por
  fuente, fecha de alta y archivo local; ademas, un boton nuevo resuelve solos los
  pares que no necesitan criterio humano (identicos, o que solo difieren en un
  campo vacio de un lado) reusando el motor de fusion existente sin logica nueva
  de decision, y deja en la cola —ya bien diferenciados— los que si tienen un
  conflicto real de datos personales.

Los dos restantes, mas un caso borde que dejo pendiente el punto anterior y una
pasada de higiene de repositorio encontrada en el camino, pasan a formar v0.5.0 (ver
abajo) en vez de quedar sin version asignada.

### v0.5.0: cierre de coherencia de interfaz y limpieza — publicado 2026-08-24

Incremento chico a proposito: agrupa lo que quedo pendiente del gate de cierre de
v0.4.0 mas higiene de repositorio encontrada en el camino, para poder probar bien lo
construido hasta aca antes de seguir. Desglose de tareas concreto, con alcance de
archivo/linea y modelo sugerido por tarea, en `tareas.md` (frentes "Cierre de
coherencia de interfaz" e "Higiene de repositorio").

Gate final de release cumplido el 2026-08-24: 322 pruebas unitarias y 13 pruebas de
navegador en verde, mas Ruff, formato, mypy, compileall y `git diff --check`.

- Curaduria tiene paridad con Scanner para busqueda libre sin acentos y navegacion
  circular por flechas, incluida la pestaña `Actividad` (`tareas.md` [V5-2], [V5-3]).
- El estado combinado de decision del comparador se anuncia como una sola region viva
  y describe el boton final (`tareas.md` [V5-1]).
- Cuando dos duplicados empatan hasta en archivo, fuente y fecha de alta —y solo
  quedan distinguibles por un conflicto real de datos personales—, cola, detalle y
  comparador agregan un fallback posicional 1 de 2 / 2 de 2 (`tareas.md` [V5-4]).
- La salida vieja de checks y la licencia duplicada salieron del repo; los ignores de
  datos personales bajo `scripts/` son recursivos y el catalogo anidado que habia
  escapado dejo de estar trackeado sin borrarse del disco (`tareas.md` [H1-H3]).
- IMDb conserva titulos originales, traducidos y aliases solo cuando Wikidata los
  vincula al mismo identificador de la obra; las consultas con acentos se normalizan
  sin perder letras.
- El carnet de acceso lleva la accion final debajo de las credenciales, mantiene el
  feedback dentro del objeto y conserva el orden visual, tactil y de teclado.

Explicitamente fuera de esta version, anotado para no perderlo pero sin tomar
todavia:

- **Grupos de 3+ duplicados identicos.** La deteccion (`annotate_duplicate_items()` en
  `domain/catalog.py`) ya los agrupa correctamente, pero la cola los presenta como
  pares (`_duplicate_cases()` en `application/curation_service.py` descompone cada
  grupo en C(n,2) casos). Colapsarlos en un solo caso tocaria el comparador de fusion
  (pensado para 2 entradas, no N) y el boton de auto-resolucion que ya itera de a
  pares — es mas que un ajuste de presentacion, probablemente necesita su propio hilo
  de diseno como el que definio la desambiguacion de v0.4.0.
- **Visibilidad de archivos escaneados para miembros comunes, a discrecion del
  admin.** Hoy los archivos y rutas locales nunca se exponen en vistas compartidas,
  sin excepcion ni para el owner. Habilitar esto relajaria una invariante dura de
  privacidad documentada en `CLAUDE.md` — es una decision de producto aparte, no un
  ajuste de esta version.
- **Purgar `scripts/scripts/catalogv4.json` del historial de git.** [H3] deja de
  trackearlo hacia adelante, pero el archivo ya esta en `origin/master` desde
  2026-08-01. Sacarlo de la historia requiere reescribir commits y probablemente un
  force-push — decision de Lucas, no delegable a una tarea de `tareas.md`.

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
- **Cliente basico (Android/Kotlin).** Hipotesis de trabajo: un primer cliente Android
  para una instancia self-hosted, con inicio de sesion seguro contra una URL HTTPS
  elegida por el usuario, lectura/busqueda/detalle del catalogo personal, cambio de
  estado/fecha de vista/puntaje/review, y disponibilidad fisica en modo lectura — sin
  administracion, Scanner, importaciones, curaduria avanzada ni uso offline en la
  primera entrega. Movido fuera de v0.5.0 a proposito: `PRODUCT.md` ya aclaraba que no
  es la etapa inmediata, y tiene prerequisitos propios sin empezar (API versionada y
  documentada, sesiones aptas para dispositivos, pruebas de compatibilidad
  servidor-cliente). Candidato natural para v0.6.0 una vez confirmada la hipotesis y
  resueltos esos prerequisitos.
- Radarr, Sonarr, Letterboxd y otras integraciones siguen siendo direcciones validas,
  pero se priorizan despues de estabilizar busqueda, scanner, backup y contratos de
  datos.
