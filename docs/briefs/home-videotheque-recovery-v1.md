# Recuperación de Inicio: videoteca material v1

## Estado y referencia vinculante

Este brief reemplaza la dirección visual de `home-video-store-v2.md` sin borrar la
historia técnica de U2. El resultado implementado por U2 no superó la aceptación visual
del 2026-09-03: conservó varias interacciones útiles, pero convirtió la portada en un
hero convencional, separó demasiado los lomos y perdió la sensación de mueble continuo.

La referencia visual aceptada es
`docs/design/u2-recovery-north-star-v1.png`. Es una composición de producto, no un asset
que se envía al navegador. Cuando una interpretación del texto compita con esa lámina,
prevalecen la composición y densidad de la lámina, con las correcciones explícitas de
este documento.

## Contrato de dirección

La escena es una videoteca nocturna frontal y compacta. El fondo de ladrillo, los
marcos, la marquesina y el mueble forman un único espacio físico; los datos y controles
siguen siendo HTML vivo. No es un dashboard de tarjetas, un hero con una grilla debajo
ni una réplica fotográfica sin jerarquía operativa.

En escritorio, Inicio debe entrar en un viewport de al menos 1280 × 720 a zoom 100 % sin
scroll vertical. La composición puede reducir densidad entre 1280 y 1600 px, pero no
ocultar acciones ni texto crítico. Altura insuficiente, zoom alto y necesidades de
accesibilidad habilitan flujo vertical: evitar el scroll no justifica recortar contenido
o atrapar el foco. Esta reconstrucción es desktop-first; móvil conserva o recupera la
composición previa a U2 y se rediseñará en una entrega separada.

### Cabecera y navegación

- La marca lleva a `Inicio`.
- `Colección` y `Menú` permanecen visibles juntos, arriba a la derecha.
- `Colección` engloba examinar, buscar, filtrar y agregar. U2-R sólo la enlaza; el
  rediseño de esa superficie pertenece a U3.
- `Menú` reúne Bandeja, Club, Al azar, usuario, administración disponible y cierre de
  sesión. No se eliminan rutas ni permisos existentes.

### Cartelera y lista tipo Winamp

La zona superior tiene dos piezas coordinadas pero no acopladas de forma destructiva:

1. Una cartelera vertical pequeña a la izquierda, con poster dinámico e indicadores.
  El marco conserva su relación vertical 2:3; el poster entero se encastra en el hueco
  interior sin recortar sus laterales ni invadir la placa o el zócalo. La placa superior
  muestra `Hoy` o `Ayer` según la programación cargada, pero no repite título, estado ni
  disponibilidad. No lleva flechas propias: rota automáticamente y la exploración manual
  vive en la playlist. Los puntos se apoyan en el zócalo inferior del marco, no en una
  caja exterior.
2. Una lista tabular densa tipo Winamp con título, año, tipo, géneros y duración, más un
  panel compacto de preview debajo. La programación diaria muestra hasta seis funciones
  visibles en el encuadre desktop objetivo.

La cartelera automática y la selección manual son estados distintos. El temporizador
sólo cambia `carouselItemId`; jamás mueve foco, `selectedItemId`, scroll de la lista ni
preview. Si el item al aire está presente en la lista activa, su fila recibe un brillo
leve distinto del estado seleccionado. Al hacer click o Enter sobre la cartelera, la
fuente vuelve a `Cartelera del día` y se selecciona el item actualmente al aire.

La lista muestra siempre su procedencia: `Cartelera del día` o el nombre de la
estantería activa. Flechas arriba/abajo recorren filas, Home/End saltan a extremos y
Enter confirma la selección. Puntero y touch producen el mismo estado sin ser el único
camino. La fila seleccionada, el lomo seleccionado y el preview representan siempre la
misma obra.

No se reserva una barra horizontal independiente para repetir el título de la
cartelera. Hoy/Ayer vive en el flujo del encabezado del reproductor como un interruptor
físico compacto, no posicionado sobre él: debe ser claro y accesible sin tapar la fuente,
la lista ni sus encabezados.

La posible transición futura entre posters como una tira vertical continua —un cuadro
sale mientras el siguiente entra, como cinta detrás del marco— se prototipa fuera del
cierre de recuperación. Requiere mantener dos imágenes simultáneas, medir rendimiento y
ofrecer una equivalencia sin movimiento; hasta entonces el cambio automático directo es
el comportamiento aceptado.

### Mueble continuo y estanterías

La mitad inferior es una biblioteca horizontal continua, no filas aisladas sobre fondo
vacío. Contiene cuatro módulos editoriales existentes —por ejemplo `Disponible esta
noche`, `Tu archivo pide memoria`, una ruta temática y `Estrenadas un día como hoy`— y
cada módulo tiene una placa propia, sin rótulos gigantes cortados detrás del mueble.

El ancho responsive deja un módulo dominante y parte del siguiente (o del tercero en
pantallas amplias) para comunicar que el recorrido continúa. No hay barra inferior
visible. Rueda vertical sobre el mueble, rueda horizontal, trackpad, Shift+rueda y
flechas izquierda/derecha desplazan lateralmente con límites reales y scroll-snap suave.
Debe existir un equivalente visible y enfocable para teclado/touch; ocultar la barra no
puede volver invisible la navegación.

Click/Enter sobre una estantería cambia `playlistSource`. Click/Enter sobre un lomo
además selecciona su obra y alinea la fila correspondiente. Recorrer la lista alinea y
lleva a vista el lomo correspondiente. El lomo conserva título, año, formato y señales
de foco/selección como datos HTML superpuestos al shell gráfico.

### Preview y acciones

Debajo de la lista o del módulo activo aparece una franja compacta con miniatura,
identidad, metadatos suficientes y dos acciones. `Ver más` y `Editar mi ficha` se
agrupan **a la izquierda** y usan el mismo lenguaje de botón físico dorado de la
referencia; la acción primaria puede tener mayor intensidad, pero no una forma o paleta
ajena. `Editar mi ficha` sólo aparece con permiso real y abre el editor existente.

### Contratapa de `Ver más`

`Ver más` abre una vista de contratapa VHS, no el dossier genérico actual. La transición
es breve y sobria —fundido y pequeño desplazamiento/profundidad—, reversible con Escape
y compatible con `prefers-reduced-motion`. Conserva foco, nombre accesible y retorno al
control que la abrió.

La contratapa usa entre cuatro y cinco plantillas HTML/CSS fijas inspiradas en la
distribución material de las referencias fotográficas: bloques de sinopsis, créditos,
dirección, reparto, año, duración, géneros, disponibilidad y memoria personal. La
plantilla se asigna con un hash estable del ID opaco de la obra; parece variada, pero no
cambia al recargar ni al volver a renderizar. La misma regla se aplica al crear una obra.

Cada plantilla reserva dos imágenes y admite una tercera sólo cuando la distribución
lo justifica. En U2-R son placeholders neutrales accesibles; no se inventan fotogramas de
películas. La extracción local o adquisición con derechos verificables se evalúa en una
tarea posterior y no bloquea esta recuperación.

## Modelo de estado mínimo

| Estado | Responsabilidad | No puede modificar |
| --- | --- | --- |
| `carouselItemId` | Item al aire y sus indicadores | foco, preview o selección manual |
| `playlistSource` | `daily` o `shelf:<id>` | contenido editorial del servidor |
| `selectedItemId` | fila, lomo y preview coordinados | item al aire automáticamente |
| `activeShelfId` | módulo visible/activo | permisos o datos personales |
| `detailItemId` | contratapa abierta | selección al cerrarse |
| `backCoverTemplate` | variante estable derivada del ID | cambiar por render o sesión |

## Matriz de interacción

| Acción | Lista | Lomo | Preview | Cartelera |
| --- | --- | --- | --- | --- |
| Tick automático | sin cambio; brillo leve si coincide | sin cambio | sin cambio | avanza |
| Click/Enter en cartelera | fuente diaria + selecciona item al aire | alinea si está visible | actualiza | conserva item |
| Click/Enter en estantería | carga esa fuente | conserva/elige primer válido | actualiza | sigue independiente |
| Click/Enter en lomo | selecciona su fila | selecciona y enfoca | actualiza | sigue independiente |
| Flecha arriba/abajo en lista | cambia selección | desplaza/alinea correlato | actualiza | sigue independiente |
| `Ver más` | conserva selección | conserva selección | abre contratapa | pausa sólo si evita distracción |
| Escape en contratapa | recupera foco previo | conserva selección | vuelve a franja | reanuda según política |

## Assets y contenido vivo

El kit `home-videotheque-kit-v1` está documentado en
`docs/assets/home-videotheque-kit-v1.md`. Sus imágenes sólo aportan materialidad:
pared, marco, mueble, lomo y shell de contratapa. Títulos, carteles, posters, botones,
indicadores, barcodes funcionales, metadata y placeholders se componen en HTML/CSS/SVG.
Ningún texto se rasteriza y ninguna película real se representa en estos assets.

## Fuera de alcance

- Rediseñar móvil, Colección, filtros, comparación, búsqueda externa o el editor.
- Cambiar `/api/home`, rutas públicas, contratos de A1 o permisos.
- Obtener fotogramas de IMDb, Wikipedia u otras páginas sin una licencia y un contrato
  técnico claros.
- Crear animaciones 3D complejas, scroll infinito o una estantería generada como una sola
  imagen con títulos horneados.

## Gate de aceptación

- Verificación visual comparada con el north star en 1280×720, 1440×900 y 1920×1080.
- Casos con 0, 1 y 4 categorías; filas vacías; poster roto; título y género extensos.
- Recorrido completo por teclado, foco visible, lector de pantalla y reduced motion.
- Temporizador probado para demostrar que no roba selección ni foco.
- Lista/lomo/preview coherentes tras click, Enter, flechas y cambio de estantería.
- Mueble con indicio lateral de continuidad, sin scrollbar visible y sin callejón para
  teclado o touch.
- Acciones doradas a la izquierda; edición ausente cuando no hay permiso.
- Contratapa determinista, dos placeholders y retorno de foco correcto.
- Móvil sin regresiones respecto de la composición anterior a U2.
