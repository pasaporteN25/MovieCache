# U12 — Una sola lista de búsqueda

Dirección aprobada el 2026-10-02. Modo: Operate. Sustituye la organización por fuente
de [la primera entrega](search-workbench-v1.md), conservando la revisión integrada
de duplicados y la identidad visual del mostrador.

- Buscar muestra una lista común de obras guardadas y referencias externas, en
  filas compactas con miniatura sin recorte. La estantería VHS grande se reserva
  para explorar sin una consulta activa. Limpiar la búsqueda la recupera.
- El servidor entrega relevancia para ambos tipos de resultados. Se ordenan por
  ese valor; ante empate se prioriza una obra guardada. La fuente no impone bloques
  ni turnos alternados. El puntaje sirve para ordenar, no se presenta como una
  probabilidad de identidad ni modifica las reglas de matching de X12.
- Cada obra guardada indica «En tu colección», su estado y disponibilidad. Permite
  abrir la contratapa o editar la ficha. Cada referencia externa identifica su
  fuente y mantiene agregar, comparar y abrir el enlace externo.
- Una única paginación acumula resultados. Las fuentes cargan de forma progresiva;
  sus estados y reintentos permanecen en una sección desplegable compacta y sus
  atribuciones se conservan. Los filtros personales siguen aplicándose al archivo
  guardado y se avisa cuando hay filtros activos.
- La lista debe ser legible a 320 px, soportar títulos largos, imágenes ausentes,
  cargas parciales, errores, búsqueda local sola, teclado e historial. La selección
  de una referencia debe conservar su identidad cuando responde otra fuente.

No se fusionan automáticamente resultados de fuentes diferentes ni se cambian los
comparadores de campos. Las coincidencias de identidad siguen requiriendo los
contratos vigentes de X12 y una decisión explícita cuando corresponde.
