# Inicio: videoclub material v2

## Referencia durable

La dirección proviene de la «lámina generada 1» mencionada durante la definición de
Inicio. Esa lámina fue una referencia conversacional y no se versionó como archivo del
repositorio; por lo tanto no debe tratarse como un asset que pueda enviarse al navegador.
Este brief preserva las decisiones visuales y de interacción necesarias para que una
sesión futura no invente una interpretación distinta. Si se conserva o se vuelve a
adjuntar la lámina, debe agregarse como referencia de diseño, con procedencia y licencia,
nunca como contenido de una obra.

## Trabajo y dirección

- Una persona abre Inicio para elegir qué ver de su propia biblioteca. El modo es
  **explorar**: la programación editorial debe orientar sin ocultar disponibilidad ni
  convertir la pantalla en un panel administrativo.
- La parte superior es `Cartelera disponible`: ambiente de *noche de cine*, imagen
  original/licenciada y una lista compacta de obras, semejante a una lista WIMP de
  reproducción. Las flechas recorren la lista; Home/End saltan a sus extremos y Enter
  confirma la obra cuyo contexto se muestra. Puntero y touch ofrecen el mismo resultado
  sin ser la única forma de usarla.
- La parte inferior reúne las categorías editoriales ya existentes —por ejemplo
  `Disponible esta noche`, `Tu archivo pide memoria` y rutas por director/género— como
  estanterías físicas horizontales. Cada obra se ve primero por su **lomo**, no por una
  portada frontal: el conjunto debe parecer una repisa real y permitir reconocer foco,
  título y disponibilidad.
- Al seleccionar un lomo aparece una **caja frontal** con portada, razón editorial y
  resumen breve. Esa caja es una puerta a `Ver más`; la transición de apertura revela
  el cassette VHS negro y la ficha extendida. El cassette y cualquier textura son
  decoración accesible con `aria-hidden`; identidad, metadatos y acciones siempre se
  conservan como HTML vivo.
- Editar no se mezcla con elegir ni con abrir la caja. La ficha extendida expondrá una
  acción secundaria explícita y autorizada, a resolver en U2.4; obras de Club o
  superficies de sólo lectura jamás muestran una mutación engañosa.

## Límites de implementación

- Reutilizar el payload editorial, acciones y contratos actuales de Inicio; U2 no abre
  rutas, no cambia `/api/home`, no convierte la cartelera pública en una vista privada y
  no inicia el cliente Android.
- `Noche de cine` necesita ser un asset nuevo, original o con licencia verificable:
  sin logotipos, actores reconocibles, textos, títulos de obras ni datos de una instancia.
  Su prompt/procedencia/hash deben auditarse como `vhs-cassette-frame-v1.png`.
- La transformación visual no puede depender de hover. Debe mantener Tab sin trampas,
  foco visible, Enter, Escape en el dossier, `prefers-reduced-motion`, navegación táctil
  y equivalentes legibles para una a cuatro recomendaciones, filas vacías, imágenes que
  fallen, títulos extensos y pantallas móviles.

## Secuencia de validación

1. U2.1 prueba la nueva cartelera y su ambiente sin modificar la semántica editorial.
2. U2.2 sustituye las tiras de cassettes frontales por lomos y caja seleccionada.
3. U2.3 conecta la apertura de caja con el dossier VHS extendido.
4. U2.4 decide y prueba la entrada a edición; no se presume un editor nuevo antes de
   verificar las acciones y permisos ya disponibles.
