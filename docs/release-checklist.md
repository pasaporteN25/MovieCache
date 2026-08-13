# Gate de release

Este gate prepara `v0.2.0-rc2` sin agregar capacidades. Combina pruebas automaticas
con una aceptacion manual sobre una biblioteca descartable. Nunca se ejecuta por primera
vez contra la unica copia de un catalogo o un disco sin backup.

Para el despliegue Docker, ejecutar esta aceptacion dentro del contenedor siguiendo
`docker.md`; la primera ruta visible por la aplicacion sera `/media/library/disco1`.

## 1. Validacion automatica

Desde la raiz del checkout:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

En Linux:

```bash
bash scripts/check.sh
```

El gate debe compilar `src`, `scripts` y `tests`, ejecutar toda la suite y terminar con
`git diff --check` limpio. El workflow de GitHub debe construir e instalar tambien el
wheel en un entorno limpio.

## 2. Preparacion segura

1. Crear y verificar un backup completo con `bash scripts/docker-backup.sh` antes de empezar.
2. Elegir una carpeta descartable con dos o tres videos de prueba.
3. Iniciar Movie Inbox habilitando solamente esa raiz con `--library-root`.
4. Confirmar que el usuario del proceso tiene lectura y recorrido, pero no necesita
   escritura sobre los videos.

## 3. Secuencia principal

1. Crear una biblioteca horaria o diaria. Debe comenzar como `Sin verificar` e inactiva.
2. Intentar aplicar antes de probar. La operacion debe rechazarse.
3. Ejecutar `Probar recorrido`. Debe clasificar archivos sin cambiar inventario ni
   disponibilidad.
4. Intentar automatizar antes de aplicar. La operacion debe rechazarse.
5. Ejecutar `Aplicar inventario`. Los archivos deben persistir y aportar disponibilidad
   compartida sin modificar estados personales.
6. Habilitar `Escaneo automatico`. Debe mostrar una proxima ejecucion.
7. Cambiar la frecuencia a manual. La automatizacion debe apagarse y `Escanear ahora`
   debe quedar disponible.

## 4. Busqueda y curaduria

1. Buscar `Evil Dead Burn 2026`. Wikipedia debe mostrar la obra exacta antes que
   resultados similares aunque el otro idioma no responda.
2. Buscar `https://en.wikipedia.org/wiki/Evil_Dead_Burn`. La URL debe resolverse de
   forma directa y la busqueda local debe encontrar una entrada del mismo titulo aunque
   todavia no tenga ese link.
3. Simular un error temporal de una fuente y repetir la consulta. El vacio fallido no
   debe quedar cacheado; una respuesta vacia valida puede durar como maximo 30 segundos.
4. Comparar una coincidencia ambigua. El ranking mejorado no debe convertir un titulo
   sin evidencia de ano o ID externo en un merge automatico.

## 5. Comparador del Scanner

1. Agregar un archivo con identidad ambigua y aplicar un recorrido.
2. Abrir `Bandeja > Scanner` y comparar titulo, ano, tipo, aliases, similitud y fuentes.
3. Vincular una candidata. Debe asociar inventario fisico sin crear una obra personal.
4. Omitir otro archivo y confirmar el aviso. No debe borrarse del disco ni del catalogo.

## 6. Recuperacion

Usar siempre la biblioteca descartable preparada para este gate.

1. Retirar o renombrar la raiz despues de un inventario valido y ejecutar un recorrido.
   El resultado debe ser `offline`; el inventario y la disponibilidad anteriores deben
   conservarse.
2. Denegar lectura a una subcarpeta o archivo y repetir. El recorrido debe terminar con
   advertencias, informar el permiso y no marcar como ausentes los archivos no vistos.
3. Restaurar el permiso y repetir. Un recorrido completo debe volver a estado listo.
4. Interrumpir el proceso durante un recorrido y reiniciarlo. La ejecucion anterior debe
   quedar fallida, la biblioteca en advertencia y el inventario previo intacto.

## 7. Criterio de salida

- Suite local y CI en verde.
- Sin perdida de inventario ante offline, permisos o reinicio.
- Rutas y fingerprints visibles solamente para el owner.
- Backup completo con checksum verificable y restauracion de `instance.db` ensayada.
- Sin errores nuevos en consola durante la secuencia principal.
- Changelog, version de paquete y version runtime sincronizados.

Una candidata que no cumple cualquiera de estos puntos no se etiqueta ni se despliega.
