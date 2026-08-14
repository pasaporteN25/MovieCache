# Hoja de ruta

Este documento conserva decisiones de producto que no deben confundirse con trabajo
activo. El alcance inmediato sigue siendo un gestor personal self-hosted para cine,
series, anime y documentales.

## Hitos de producto

### v0.3.0: confianza en busqueda, matching e inventario

La prioridad completa de esta version es recuperar confianza en las decisiones de
identidad. No se agregaran nuevas fuentes ni tipos de contenido hasta contar con una
evaluacion repetible que mida falsos positivos y regresiones.

El primer incremento ya esta disponible como `movie-inbox search-lab`: incluye corpus
dorado empaquetado, respuestas externas grabadas, reportes JSON/HTML e inspeccion de
exports en modo de solo lectura. Todavia mide unicamente el ranking productivo actual;
la comparacion contra un algoritmo candidato comienza en el siguiente incremento.

- Construir el laboratorio no destructivo definido en
  [search-quality.md](search-quality.md), con casos dorados, respuestas externas
  grabadas y comparacion entre baseline y algoritmo candidato.
- Separar busqueda de descubrimiento, busqueda por titulo, comparacion de identidad y
  matching del Scanner. Compartiran normalizacion, pero no umbrales ni campos de
  evidencia.
- Exigir evidencia conservadora para sugerir un merge. Descripcion, review, reparto,
  genero o tags nunca podran convertir una obra en candidata de identidad.
- Filtrar resultados externos por relevancia minima y conservar los resultados de
  baja confianza solamente bajo divulgacion explicita.
- Hacer que Scanner confirme primero el inventario fisico. Agregar la obra al catalogo
  personal sera una accion posterior y opcional.
- Organizar la cola por causa y confianza para que la revision individual quede
  reservada a excepciones reales.
- Mostrar una unica disponibilidad efectiva con procedencia `inventario verificado`,
  `declaracion manual` o ambas en Coleccion, ficha, Curaduria y comparadores.

El gate de salida exigira cero falsos positivos conocidos en auto-match y merge,
metricas minimas del corpus dorado y una prueba manual con un snapshot de catalogo que
no permita escrituras.

### v0.4.0: coherencia de interfaz

Esta version aplicara el backlog de Impeccable una vez estabilizada la semantica de
v0.3.0. No se usara un rediseño para ocultar reglas de matching todavia cambiantes.

- Unificar el lenguaje visual y la arquitectura de Inicio, Coleccion, Bandeja, Club y
  Administrar.
- Hacer visible la cadena `archivo fisico -> identidad compartida -> ficha personal`
  y los recibos de cada operacion.
- Reducir carga cognitiva, revisar responsive, teclado, lectores de pantalla y estados
  vacios/error con los flujos reales ya estabilizados.
- Cerrar con una nueva auditoria y una pasada de `$impeccable polish`.

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
