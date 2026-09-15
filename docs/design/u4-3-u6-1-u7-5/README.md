# Dos carteleras y una consola — estudio conjunto

2026-09-12. Modo Operate. **Comparador histórico: B elegida e integrada en la Home
real el 2026-09-13.** Evidencia y alcance actual en
[`../u4-3-b-integration/README.md`](../u4-3-b-integration/README.md).
Lo que sigue documenta el estudio original, no el cierre completo de U7.5.

## Abrir

Desde la raíz: `node docs/design/u4-3-u6-1-u7-5/serve-preview.mjs`.
El proceso imprime su URL aleatoria en loopback. No abre la red local ni accede al
catálogo. No requiere login y no permite escrituras. Detener con Ctrl+C.
El archivo HTML necesita ese servidor para cargar los módulos y assets locales.

El renderer y la base CSS son los actuales de Home, con un adaptador exclusivo de
esta muestra. Las capturas preservan el corte; el laboratorio puede variar si cambia
el renderer. No se usan frameworks nuevos, descargas ni un segundo backend.

## Alcance y evaluación

- **U6.1:** estudio espacial de dos composiciones, con marcos pares y cuatro anchos.
  Izquierda Hoy/Ayer; derecha consulta. Opciones preparadas para elección.
- **U4.3:** integración visual de acciones, datos, ventanas y créditos bajo una sola
  profundidad. Corte de diseño listo; traslado a producción después de elegir.
- **U7.5:** comparación 0/1/2 imágenes, una vertical, carga, error, imagen amplia,
  segundo hueco y repetición de imagen. Corrección persistida y procedencia real
  siguen dependiendo de U7.2–4. El diálogo sólo ilustra el acceso a la ficha.

No había subagentes activos ni otra tarea Codex activa del proyecto al comprobarlo.
Había cambios concurrentes ajenos de backend/Android: no se modificaron ni se
incluyeron en ningún commit. Esta entrega sólo agrega el laboratorio y actualiza
su planificación visual. No se hizo commit.

### A — consola central

Marcos de 220 px. Lista y consulta comparten el ancho central. En 1280/1440 los
créditos pasan a una segunda fila; en 1920/2482 entra una retícula de cuatro grupos.
En escritorio amplio es más baja, pero deja zona oscura bajo las carteleras y ofrece
menos espacio para el contenido de consulta. La letra de la lista no se escala.

### B — consola común

Dos carteleras de 206–274 px a los lados de la lista. Una franja de consulta se
extiende bajo ambas **dentro de la misma abertura superior**, antes de la estantería.
No reconstruye el panel inferior eliminado. Acciones y datos tienen más ancho y una
base común; la escala mayor de las portadas en escritorio amplio aumenta la altura.

**Recomendación: B si prima integración material y lectura de la consulta.**
Si prima mostrar más biblioteca en la primera pantalla de escritorio grande, A
es más compacta. No ocultar ese coste: B no ahorra altura en todos los anchos.
No se intercambian automáticamente A/B por breakpoint sin una decisión del owner.

## Evidencia espacial

Medidas DOM en navegador conectado, archivo poblado con dos muestras técnicas.
Puede haber una diferencia de ~15 px en capturas de página completa por la barra
vertical que el capturador retira; la tabla conserva las medidas del viewport normal.

| Viewport | A: marco/lista/alto superior | B: marco/lista/alto superior |
| --- | --- | --- |
| 1280×720 | 220 / 694 / 715 px | 206 / 722 / 623 px |
| 1440×900 | 220 / 847 / 715 px | 206 / 875 / 623 px |
| 1920×1080 | 220 / 1308 / 613 px | 261 / 1226 / 711 px |
| 2482×1254 | 220 / 1720 / 613 px | 274 / 1612 / 732 px |

Ocho capturas `a-{ancho}.png` / `b-{ancho}.png`. En las ocho comprobaciones:
marcos de igual ancho/alto, seis filas, sin scroll vertical local de tabla ni overflow
horizontal del documento. Una sola consola. El carril VHS conserva scroll propio.

Director/géneros/duración dejan de ser columnas a ≤1600 px; siguen en ficha/resumen.
A ≤1100 también se retira tipo de la tabla. Son umbrales del estudio, no contratos
definitivos de producción. En ≤860 se muestran los dos marcos y luego tabla/consulta;
no se encogen letras para simular que la composición de escritorio cabe en móvil.

## Decisión U7 confirmada durante el estudio

Preferir dos imágenes distintas; pueden ser panorámica + portada. La presencia del
mismo póster en la cartelera derecha no prohíbe usarlo en la consola. Si hay una sola,
repetirla está permitido. El comparador permite evaluar repetir vs ventana amplia o
segundo hueco; **permiso para repetir no significa que ese fallback esté elegido
como predeterminado**. Con cero, fallback honesto; nunca imágenes de otra obra.

La investigación de API ya está en U7.1–4 (proveedores existentes/TMDB sobre identidad
confirmada). No se añade otra épica. Dedupe de assets en almacenamiento permanece:
la repetición visual no incrementa cobertura ni fabrica otro registro de imagen.

### Contrato visual para el agente de datos

- Consulta por identidad y origen, no por título parecido. Mostrar título y acciones
  inmediatamente, sin esperar imágenes. Una respuesta vieja nunca cambia la obra.
- Lista ordenada de assets con identidad estable, URL, rol, dimensiones, procedencia
  y autoridad manual. El renderer consume; no guarda tokens ni consulta proveedor.
- Preferir dos imágenes válidas distintas. Si hay una, aplicar el fallback visual
  elegido sin crear datos duplicados. Si ninguna, mostrar ausencia, no error falso.
- Distinguir carga, fallo recuperable y ausencia real; conservar la geometría.
- Corrección en ficha existente: preview, procedencia por imagen y selección manual
  cuando U7.3 lo soporte. Club sin edición personal conserva sus permisos.
- Ver más y Editar mi ficha siguen operativos aunque falle la carga; procedencia
  desconocida se declara como tal. No atribuir un asset genéricamente a TMDB.

## QA y límites

- 0/1/2, vertical, carga y error: en B/1280 la ventana conserva 184 px y la consola
  232 px; sin salto al alternar esos estados. Son fixtures de estado, no prueba
  de descarga lenta, errores del proveedor o cancelación de peticiones reales.
- Ver más abre muestra aun con error y devuelve foco al mismo botón al cerrar.
- Una imagen repetida aparece marcada como tal en la muestra. Se conserva completa
  mediante `object-fit: contain`; no se fabrica una panorámica recortando una portada.
- Clic en un VHS de título largo cambia consulta/derecha y muestra dos filas del
  conjunto de ejemplo. Rotación explícita cambia sólo la izquierda.
- El cambio de fuente se simula con funciones existentes exclusivamente para el
  clic; no implementa el contrato completo U5 de flechas, Tab, Club o fuentes grandes.
- Créditos largos envuelven sin desbordar. La altura puede crecer con contenido,
  distinto del salto causado sólo por cargar o fallar una imagen.
- Smoke emulado 390×844: sin overflow del documento; corregido solapamiento entre
  la última fila y la consulta. No se probó teléfono físico, zoom 200% ni toda MW1.
- Sin errores JS registrados en la revisión conectada. Scan de layout sin hallazgos.
- `node --experimental-vm-modules --test tests/js/home-selection.test.mjs`: 8/8.
  Esa suite prueba el contrato real vigente, no certifica el adaptador del estudio.
  El primer intento sin el flag falló por `vm.SourceTextModule`; se corrigió la invocación.
- `node --check` en ambos módulos nuevos y `git diff --check` para archivos tocados.

Las imágenes horizontales son **assets de ambiente de la interfaz usados sólo para
medir encuadre**, no imágenes atribuidas a películas. La portada de Metropolis es
la muestra previamente incorporada: Boris Bilinsky, 1927, referencia de Wikimedia
conservada en `../u4-2d-1-composition/index.html`. No se descargaron imágenes nuevas.

## Próximo corte

Elegir A o B y el fallback de una imagen. Después trasladar U4.3, conectar U6.2–4
con las reglas U5 y completar U7.5 cuando exista el contrato de assets. U4.4/U4.6,
la adquisición real U7 y MW1 siguen abiertas; no declarar terminado el conjunto
por haber validado una muestra aislada.
