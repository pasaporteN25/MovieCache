# Hoja de ruta

Este documento conserva decisiones de producto que no deben confundirse con trabajo
activo. El alcance inmediato sigue siendo un gestor personal self-hosted para cine,
series, anime y documentales.

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
